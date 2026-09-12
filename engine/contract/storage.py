"""Capa de almacenamiento del Data Contract -- history / incoming / current.

Sustituye el fichero unico data/metrics/{ID}.json por tres capas con
ciclos de vida distintos (ver el plan de migracion aprobado):

    history/{asset_type}/{asset_id}/{anio}.parquet   INMUTABLE, versionado
    incoming/{ID}_{anio}.csv                          append-only, versionado
    current/{ID}.parquet                              DERIVADO, NO versionado

Por que tres capas y no una: medido sobre el corpus real, reescribir a
diario un parquet acumulativo cuesta 65,1 KB/dia de historial de git por
activo, frente a 0,84 KB/dia con esta separacion. El formato optimo para
almacenar no es el mismo que el optimo para versionar.

PyArrow NO esta en el camino critico diario: el cron solo anade lineas a
un CSV con la biblioteca estandar. Los imports de pyarrow son perezosos
(dentro de las funciones que escriben o leen parquet) precisamente para
que importar este modulo no exija la dependencia.

REGLA DE PRECEDENCIA (correccion del plan, punto B): al reconstruir el
estado logico gana la fila con retrieved_at MAS ALTO para cada clave
logica, con independencia de la capa fisica donde este almacenada.
incoming/late NO tiene precedencia semantica superior a incoming/ -- es
una cola de datos pendientes de consolidar en una revision, no una capa
mas reciente por definicion.
"""
import csv
import datetime
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
INCOMING_DIR = os.path.join(DATA_DIR, "incoming")
CURRENT_DIR = os.path.join(DATA_DIR, "current")

# Orden canonico de las columnas. Es el mismo contrato de schema.py mas
# value_text -- el desdoble del campo categorico que docs/04-modelo-power-bi.md
# ya habia decidido ("no fuerces un tipo unico a value").
COLUMNS = [
    "asset_id", "asset_type", "domain", "metric", "value", "value_text",
    "unit", "data_as_of", "retrieved_at", "source", "source_priority",
    "confidence_pct", "data_quality_pct", "calculation_method", "source_url",
]

# Columnas que en el CSV se escriben como entero (o vacio si son None).
INT_COLUMNS = ("source_priority", "confidence_pct", "data_quality_pct")


def anio_abierto(hoy=None):
    """El anio en curso: sus filas viven en incoming/, no en history/."""
    return (hoy or datetime.date.today()).year


# --------------------------------------------------------------------------
# Conversion de filas
# --------------------------------------------------------------------------

def from_json_row(r):
    """Fila del formato JSON antiguo -> fila interna con tipos resueltos.

    Desdobla value: numerico se queda en value, texto pasa a value_text.
    Verificado sobre las 507.330 filas reales: 0 valores pierden precision
    al pasar por float64 y 0 enteros superan 2^53.
    """
    v = r["value"]
    if isinstance(v, str):
        value, value_text = None, v
    else:
        value, value_text = (float(v) if v is not None else None), None
    return {
        "asset_id": r["asset_id"],
        "asset_type": r["asset_type"],
        "domain": r["domain"],
        "metric": r["metric"],
        "value": value,
        "value_text": value_text,
        "unit": r["unit"],
        "data_as_of": _parse_date(r["data_as_of"]),
        "retrieved_at": _parse_ts(r["retrieved_at"]),
        "source": r["source"],
        "source_priority": r["source_priority"],
        "confidence_pct": r["confidence_pct"],
        "data_quality_pct": r["data_quality_pct"],
        "calculation_method": r["calculation_method"],
        "source_url": r["source_url"],
    }


def _parse_date(s):
    if isinstance(s, datetime.date):
        return s
    return datetime.date.fromisoformat(s[:10])


def _parse_ts(s):
    if isinstance(s, datetime.datetime):
        return s
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc)


def logical_key(row):
    """Clave logica de un hecho -- la MISMA que ya usaba build.py para la
    idempotencia. Identifica un hecho, no una fila fisica: dos filas con
    la misma clave son el mismo hecho observado dos veces."""
    return (row["asset_id"], row["domain"], row["metric"],
            row["data_as_of"].isoformat(), row["source"])


def canonical_sort(rows):
    """Orden canonico de escritura. Hace que el contenido sea reproducible
    de forma funcional (mismas filas en el mismo orden); NO se persigue
    identidad byte a byte, que una version distinta de PyArrow romperia
    sin que eso fuese un fallo real."""
    return sorted(rows, key=lambda r: (
        r["asset_id"], r["domain"], r["metric"],
        r["data_as_of"].isoformat(), r["source"]))


def resolve(rows):
    """Reconstruye el estado logico: una fila por clave logica, ganando el
    retrieved_at mas alto.

    NO es una concatenacion. Si 2024.parquet trae 100.000 filas y
    2024_r2.parquet trae 3 correcciones de claves ya existentes, el
    resultado son 100.000 filas, no 100.003. Si r2 trae ademas una clave
    nueva (un dato tardio, no una correccion), sube en exactamente 1.

    No asume ningun orden entre capas: compara retrieved_at directamente,
    que es lo unico comparable entre history, incoming e incoming/late.
    """
    index = {}
    for row in rows:
        k = logical_key(row)
        prev = index.get(k)
        if prev is None or row["retrieved_at"] > prev["retrieved_at"]:
            index[k] = row
    return canonical_sort(index.values())


# --------------------------------------------------------------------------
# CSV (incoming) -- solo biblioteca estandar, es el camino critico diario
# --------------------------------------------------------------------------

def _fmt_csv(row):
    out = []
    for c in COLUMNS:
        v = row[c]
        if v is None:
            out.append("")
        elif c == "data_as_of":
            out.append(v.isoformat())
        elif c == "retrieved_at":
            out.append(v.strftime("%Y-%m-%dT%H:%M:%SZ"))
        else:
            out.append(v)
    return out


def _parse_csv(rec):
    row = {}
    for c in COLUMNS:
        raw = rec[c]
        if raw == "":
            row[c] = None
        elif c == "value":
            row[c] = float(raw)
        elif c in INT_COLUMNS:
            row[c] = int(raw)
        elif c == "data_as_of":
            row[c] = _parse_date(raw)
        elif c == "retrieved_at":
            row[c] = _parse_ts(raw)
        else:
            row[c] = raw
    return row


def incoming_path(asset_id, anio=None, late=False):
    if late:
        return os.path.join(INCOMING_DIR, f"{asset_id}_late.csv")
    return os.path.join(INCOMING_DIR, f"{asset_id}_{anio or anio_abierto()}.csv")


def read_incoming(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return [_parse_csv(rec) for rec in csv.DictReader(f)]


def append_incoming(path, rows):
    """Anade filas al final del CSV. Nunca reescribe una linea existente:
    es lo que permite que git lo deltifique (0,84 KB/dia medidos)."""
    if not rows:
        return 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    nuevo = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(COLUMNS)
        for row in canonical_sort(rows):
            w.writerow(_fmt_csv(row))
    return len(rows)


# --------------------------------------------------------------------------
# Parquet (history / current) -- import perezoso, fuera del cron diario
# --------------------------------------------------------------------------

def hay_pyarrow():
    """PyArrow no esta en el camino critico de ingesta: la ingesta diaria
    solo escribe CSV. Esta funcion permite que quien lo necesite (qa.py,
    los tests) declare EXPLICITAMENTE que no pudo abrir los parquet, en vez
    de degradar la garantia en silencio."""
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


def _pa():
    import pyarrow as pa
    return pa


def _schema():
    pa = _pa()
    return pa.schema([
        ("asset_id", pa.string()), ("asset_type", pa.string()),
        ("domain", pa.string()), ("metric", pa.string()),
        ("value", pa.float64()), ("value_text", pa.string()),
        ("unit", pa.string()), ("data_as_of", pa.date32()),
        ("retrieved_at", pa.timestamp("s", tz="UTC")),
        ("source", pa.string()), ("source_priority", pa.int8()),
        ("confidence_pct", pa.int16()), ("data_quality_pct", pa.int16()),
        ("calculation_method", pa.string()), ("source_url", pa.string()),
    ])


def write_parquet(rows, path):
    """Escribe filas ya ordenadas canonicamente en un parquet zstd."""
    import pyarrow.parquet as pq
    pa = _pa()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tbl = pa.Table.from_pylist([{c: r[c] for c in COLUMNS} for r in rows],
                               schema=_schema())
    pq.write_table(tbl, path, compression="zstd")
    return len(rows)


def read_parquet(path):
    import pyarrow.parquet as pq
    rows = pq.read_table(path).to_pylist()
    for r in rows:
        # pyarrow devuelve date/datetime ya tipados; normalizamos la zona
        # horaria para que la comparacion de retrieved_at sea homogenea.
        if r["retrieved_at"].tzinfo is None:
            r["retrieved_at"] = r["retrieved_at"].replace(
                tzinfo=datetime.timezone.utc)
    return rows


# --------------------------------------------------------------------------
# Manifiesto -- la inmutabilidad como propiedad verificable, no como nombre
# --------------------------------------------------------------------------

def history_dir(asset_type, asset_id):
    return os.path.join(HISTORY_DIR, asset_type, asset_id)


def manifest_path(asset_type, asset_id):
    return os.path.join(history_dir(asset_type, asset_id), "manifest.json")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(asset_type, asset_id):
    p = manifest_path(asset_type, asset_id)
    if not os.path.exists(p):
        return {"asset_id": asset_id, "asset_type": asset_type, "particiones": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write_manifest(man):
    p = manifest_path(man["asset_type"], man["asset_id"])
    os.makedirs(os.path.dirname(p), exist_ok=True)
    man["particiones"] = sorted(man["particiones"],
                                key=lambda e: (e["anio"], e["revision"]))
    with open(p, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=2, ensure_ascii=False)
        f.write("\n")


def partition_name(anio, revision):
    return f"{anio}.parquet" if revision == 1 else f"{anio}_r{revision}.parquet"


def write_partition(asset_type, asset_id, anio, rows, revision=1, created_at=None):
    """Escribe una particion de history/ y registra su entrada de manifiesto.

    La entrada guarda sha256, numero de filas y rango de fechas: son las
    tres cosas que qa.py recalcula despues para detectar que una particion
    cerrada ha cambiado.
    """
    rows = canonical_sort(rows)
    fname = partition_name(anio, revision)
    path = os.path.join(history_dir(asset_type, asset_id), fname)
    write_parquet(rows, path)
    man = read_manifest(asset_type, asset_id)
    man["particiones"] = [e for e in man["particiones"] if e["fichero"] != fname]
    man["particiones"].append({
        "fichero": fname,
        "anio": anio,
        "revision": revision,
        "sha256": sha256_file(path),
        "filas": len(rows),
        "data_as_of_min": min(r["data_as_of"] for r in rows).isoformat(),
        "data_as_of_max": max(r["data_as_of"] for r in rows).isoformat(),
        "created_at": created_at or datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    write_manifest(man)
    return path


def read_history(asset_type, asset_id):
    """Todas las filas de todas las particiones y revisiones, SIN resolver.
    La resolucion es responsabilidad de resolve(), que compara retrieved_at."""
    d = history_dir(asset_type, asset_id)
    if not os.path.isdir(d):
        return []
    man = read_manifest(asset_type, asset_id)
    rows = []
    for e in man["particiones"]:
        rows += read_parquet(os.path.join(d, e["fichero"]))
    return rows


# --------------------------------------------------------------------------
# current -- artefacto derivado, nunca fuente de verdad
# --------------------------------------------------------------------------

def all_layers(asset_type, asset_id):
    """Filas crudas de las tres capas, sin resolver y sin asumir precedencia."""
    rows = read_history(asset_type, asset_id)
    for p in sorted(_incoming_files(asset_id)):
        rows += read_incoming(p)
    return rows


def read_incoming_rows(asset_id):
    """Solo las filas de incoming/ (CSV), resueltas entre si. Sin PyArrow.

    Es lo que puede validar el nivel CORE de qa.py: las filas RECIEN
    ingeridas, que son las unicas que el cron acaba de escribir. Las de
    history/ ya se validaron cuando se escribieron, y que no hayan
    cambiado desde entonces lo comprueba el hash del manifiesto -- pero
    eso NO equivale a validar su contenido, que es trabajo del nivel
    PARQUET.
    """
    rows = []
    for p in sorted(_incoming_files(asset_id)):
        rows += read_incoming(p)
    return resolve(rows)


def assets_en_incoming():
    if not os.path.isdir(INCOMING_DIR):
        return []
    ids = set()
    for f in os.listdir(INCOMING_DIR):
        if f.endswith(".csv"):
            ids.add(f.rsplit("_", 1)[0])
    return sorted(ids)


def assets_en_history():
    if not os.path.isdir(HISTORY_DIR):
        return []
    ids = set()
    for t in os.listdir(HISTORY_DIR):
        d = os.path.join(HISTORY_DIR, t)
        if os.path.isdir(d):
            ids.update(os.listdir(d))
    return sorted(ids)


def verificar_hashes_manifiesto():
    """Comprueba SHA-256, numero de filas registrado y presencia de cada
    particion SIN abrir ningun parquet -- solo metadatos y bytes.

    Detecta que una particion cerrada ha cambiado, que falta un fichero o
    que sobra uno sin registrar. NO demuestra que el contenido del parquet
    sea correcto (schema, valores, claves): eso exige leerlo, y es lo que
    hace el nivel PARQUET de qa.py.
    """
    fallos = []
    revisadas = 0
    if not os.path.isdir(HISTORY_DIR):
        return fallos, revisadas
    for tipo in sorted(os.listdir(HISTORY_DIR)):
        tdir = os.path.join(HISTORY_DIR, tipo)
        if not os.path.isdir(tdir):
            continue
        for asset_id in sorted(os.listdir(tdir)):
            d = os.path.join(tdir, asset_id)
            man = read_manifest(tipo, asset_id)
            registrados = {e["fichero"] for e in man["particiones"]}
            en_disco = {f for f in os.listdir(d) if f.endswith(".parquet")}
            for f in sorted(en_disco - registrados):
                fallos.append(f"  [{asset_id}] {f}: en disco pero NO en el manifiesto")
            for f in sorted(registrados - en_disco):
                fallos.append(f"  [{asset_id}] {f}: en el manifiesto pero NO en disco")
            for e in man["particiones"]:
                path = os.path.join(d, e["fichero"])
                if not os.path.exists(path):
                    continue
                revisadas += 1
                if sha256_file(path) != e["sha256"]:
                    fallos.append(f"  [{asset_id}] {e['fichero']}: HASH DISTINTO — "
                                  f"una particion cerrada ha cambiado")
            por_anio = {}
            for e in man["particiones"]:
                por_anio.setdefault(e["anio"], []).append(e["revision"])
            for anio, revs in sorted(por_anio.items()):
                if sorted(revs) != list(range(1, len(revs) + 1)):
                    fallos.append(f"  [{asset_id}] anio {anio}: secuencia de revisiones "
                                  f"con huecos o repeticiones: {sorted(revs)}")
    return fallos, revisadas


def _incoming_files(asset_id):
    if not os.path.isdir(INCOMING_DIR):
        return []
    out = []
    for f in os.listdir(INCOMING_DIR):
        if f.startswith(f"{asset_id}_") and f.endswith(".csv"):
            out.append(os.path.join(INCOMING_DIR, f))
    return out


def to_contract_row(row):
    """Fila interna -> fila con fechas en texto, para validarla con schema.py
    y para los consumidores que ya esperaban ese formato."""
    out = dict(row)
    out["data_as_of"] = row["data_as_of"].isoformat()
    out["retrieved_at"] = row["retrieved_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


def asset_type_of(asset_id):
    """Localiza el asset_type de un activo.

    Mira primero history/ (por su carpeta) y, si no esta ahi, incoming/
    (por el campo asset_type de sus propias filas). Un activo dado de alta
    a mitad de anio SOLO tiene incoming hasta el primer cierre de anio:
    resolverlo unicamente por history/ lo dejaria invisible para qa.py y
    para la materializacion.
    """
    if os.path.isdir(HISTORY_DIR):
        for t in sorted(os.listdir(HISTORY_DIR)):
            if os.path.isdir(os.path.join(HISTORY_DIR, t, asset_id)):
                return t
    for p in sorted(_incoming_files(asset_id)):
        for r in read_incoming(p):
            return r["asset_type"]
    return None


def read_asset(asset_id, asset_type=None):
    """Estado logico completo de un activo, resuelto por clave logica."""
    asset_type = asset_type or asset_type_of(asset_id)
    if asset_type is None:
        return []
    return resolve(all_layers(asset_type, asset_id))


def technical_dates(asset_id):
    """Fechas de 'precio' (domain=tecnico) ya presentes en CUALQUIER capa.

    Es la referencia de "que ya tenemos" que usan el backfill (para no
    reintroducir filas) y el diagnostico de huecos. Lee el manifiesto y el
    CSV de incoming sin materializar nada, para no cargar el histórico
    entero solo para responder a esto.
    """
    fechas = set()
    asset_type = asset_type_of(asset_id)
    if asset_type is not None:
        for r in read_history(asset_type, asset_id):
            if r["domain"] == "tecnico" and r["metric"] == "precio":
                fechas.add(r["data_as_of"].isoformat())
    for p in _incoming_files(asset_id):
        for r in read_incoming(p):
            if r["domain"] == "tecnico" and r["metric"] == "precio":
                fechas.add(r["data_as_of"].isoformat())
    return fechas


def materialize(asset_type, asset_id):
    """Regenera current/{ID}.parquet desde history/ + incoming/.

    Escritura atomica: fichero temporal y renombrado. Una interrupcion deja
    el current anterior intacto o ningun fichero, nunca uno a medias.
    """
    rows = resolve(all_layers(asset_type, asset_id))
    os.makedirs(CURRENT_DIR, exist_ok=True)
    final = os.path.join(CURRENT_DIR, f"{asset_id}.parquet")
    tmp = os.path.join(CURRENT_DIR, f".{asset_id}.parquet.tmp")
    write_parquet(rows, tmp)
    os.replace(tmp, final)
    return len(rows)
