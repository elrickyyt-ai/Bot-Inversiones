"""Herramienta de diagnostico del Data Contract -- Fase A de la
preparacion de Power BI (docs/03-arquitectura-visualizacion-y-acceso.md).

Lee el Data Contract (history/ + incoming/ resueltos, y data/thesis/,
data/assets/, data/news/), valida cada fila contra
schema.py, y produce un informe legible por una persona -- nada de JSON
crudo. No modifica ningun motor ni el propio data/, solo lo inspecciona.

Dos niveles, con estados explicitos:

    QA-CORE     siempre, solo biblioteca estandar, obligatorio.
                Valida las filas de incoming/ y la integridad de history/
                por hash del manifiesto, sin abrir ningun parquet.

    QA-PARQUET  solo si PyArrow esta disponible. Abre cada particion y
                comprueba schema, filas, rango y duplicados logicos.

El resultado global es VERIFIED, UNVERIFIED o FAIL -- nunca un PASS cuando
una comprobacion no se ha podido ejecutar. "No se pudo verificar" no es
"verificado correctamente", y el informe lo dice con esas palabras.

Uso:
    python3 engine/contract/qa.py                     ingesta (CORE obligatorio)
    python3 engine/contract/qa.py --require-parquet   mantenimiento/CI (exige ambos)
"""
import datetime
import json
import os
import re

import storage
from schema import (
    validate_metric_row, validate_thesis_row, validate_asset_row, validate_news_row, ContractError,
    METRIC_FIELDS, THESIS_FIELDS, ASSET_FIELDS, NEWS_FIELDS,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, "data")

# Patrones de credenciales -- por nombre de campo, no por contenido (los
# valores del Data Contract nunca deberian tener un campo con estos
# nombres; si lo tienen, es un adaptador mal escrito, no un dato legitimo).
CREDENTIAL_KEY_PATTERN = re.compile(r"(password|secret|token|api[_-]?key|credential)", re.IGNORECASE)

CARTERA_HINTS = ("cartera_A", "CARTERA_A", "cantidad_neta", "flujo_caja")


def _load_json_files(subdir):
    path = os.path.join(DATA_DIR, subdir)
    files = {}
    if not os.path.isdir(path):
        return files
    for fname in sorted(os.listdir(path)):
        if fname.endswith(".json"):
            with open(os.path.join(path, fname), encoding="utf-8") as f:
                files[fname] = json.load(f)
    return files


def _fmt_pass_fail(ok):
    return "PASS" if ok else "FAIL"


def _assets_en_contract():
    """Activos presentes en la estructura nueva (history/ o incoming/)."""
    ids = set()
    if os.path.isdir(storage.HISTORY_DIR):
        for t in os.listdir(storage.HISTORY_DIR):
            d = os.path.join(storage.HISTORY_DIR, t)
            if os.path.isdir(d):
                ids.update(os.listdir(d))
    if os.path.isdir(storage.INCOMING_DIR):
        for f in os.listdir(storage.INCOMING_DIR):
            if f.endswith(".csv"):
                ids.add(f.rsplit("_", 1)[0])
    return sorted(ids)


def _validar_manifiestos():
    """Septimo bloque: la inmutabilidad de history/ como propiedad
    verificada, no como convencion de nombres.

    Seis comprobaciones, cada una con un diagnostico distinto:
    hash (la particion cambio), filas (truncamiento), rango temporal (una
    fila archivada en el anio equivocado), schema (columnas o tipos que ya
    no son los del contrato), duplicado logico (la resolucion de revisiones
    esta rota) y secuencia de revisiones (manifiesto y disco divergen).
    """
    fallos = []
    revisado = 0
    if not os.path.isdir(storage.HISTORY_DIR):
        return fallos, revisado
    for tipo in sorted(os.listdir(storage.HISTORY_DIR)):
        tdir = os.path.join(storage.HISTORY_DIR, tipo)
        if not os.path.isdir(tdir):
            continue
        for asset_id in sorted(os.listdir(tdir)):
            d = os.path.join(tdir, asset_id)
            man = storage.read_manifest(tipo, asset_id)
            registrados = {e["fichero"] for e in man["particiones"]}
            en_disco = {f for f in os.listdir(d) if f.endswith(".parquet")}
            for f in sorted(en_disco - registrados):
                fallos.append(f"  [{asset_id}] {f}: en disco pero NO en el manifiesto")
            for f in sorted(registrados - en_disco):
                fallos.append(f"  [{asset_id}] {f}: en el manifiesto pero NO en disco")

            claves = set()
            for e in man["particiones"]:
                path = os.path.join(d, e["fichero"])
                if not os.path.exists(path):
                    continue
                revisado += 1
                if storage.sha256_file(path) != e["sha256"]:
                    fallos.append(f"  [{asset_id}] {e['fichero']}: HASH DISTINTO — "
                                  f"una particion cerrada ha cambiado")
                    continue
                rows = storage.read_parquet(path)
                if len(rows) != e["filas"]:
                    fallos.append(f"  [{asset_id}] {e['fichero']}: {len(rows)} filas, "
                                  f"el manifiesto dice {e['filas']}")
                fuera = [r for r in rows if r["data_as_of"].year != e["anio"]]
                if fuera:
                    fallos.append(f"  [{asset_id}] {e['fichero']}: {len(fuera)} filas "
                                  f"fuera del anio {e['anio']}")
                for r in rows:
                    if set(r.keys()) != set(storage.COLUMNS):
                        fallos.append(f"  [{asset_id}] {e['fichero']}: schema distinto del contrato")
                        break
                if e["revision"] == 1:
                    claves |= {storage.logical_key(r) for r in rows}

            revisiones = sorted((e["anio"], e["revision"]) for e in man["particiones"])
            por_anio = {}
            for anio, rev in revisiones:
                por_anio.setdefault(anio, []).append(rev)
            for anio, revs in sorted(por_anio.items()):
                if revs != list(range(1, len(revs) + 1)):
                    fallos.append(f"  [{asset_id}] anio {anio}: secuencia de revisiones "
                                  f"con huecos o repeticiones: {revs}")

            resueltas = storage.read_asset(asset_id, tipo)
            if len({storage.logical_key(r) for r in resueltas}) != len(resueltas):
                fallos.append(f"  [{asset_id}] DUPLICADO LOGICO tras resolver revisiones")
    return fallos, revisado


def run_qa(require_parquet=False):
    lines = []
    p = lines.append

    thesis_files = _load_json_files("thesis")
    assets_files = _load_json_files("assets")
    news_files = _load_json_files("news")

    # Metricas. CON PyArrow se valida el ESTADO LOGICO completo (history/ +
    # incoming/ resueltos por clave logica). SIN PyArrow solo se validan las
    # filas de incoming/ -- las recien ingeridas, que son las unicas que el
    # cron acaba de escribir. Lo que NO se puede comprobar queda declarado
    # como tal en el informe, nunca como PASS.
    hay_parquet = storage.hay_pyarrow()
    metrics_files = {}
    all_metric_rows = []
    for asset_id in _assets_en_contract():
        rows = storage.read_asset(asset_id) if hay_parquet else storage.read_incoming_rows(asset_id)
        if not rows:
            continue
        metrics_files[asset_id] = rows
        for row in rows:
            all_metric_rows.append((asset_id, storage.to_contract_row(row)))

    all_thesis_rows = []
    for fname, content in thesis_files.items():
        # historizado (desde 2026-09-03): lista de tesis, una por data_as_of.
        # formato antiguo (anterior a la historizacion): un solo objeto.
        rows = content if isinstance(content, list) else [content]
        for row in rows:
            all_thesis_rows.append((fname, row))

    assets = sorted({row["asset_id"] for _, row in all_metric_rows} | {row["asset_id"] for _, row in all_thesis_rows})
    sources = sorted({row.get("source") for _, row in all_metric_rows if row.get("source")})
    retrieved_ats = [row.get("retrieved_at") for _, row in all_metric_rows if row.get("retrieved_at")]
    last_update = max(retrieved_ats) if retrieved_ats else None

    p("=" * 70)
    p("DIAGNÓSTICO DEL DATA CONTRACT — data/")
    p("=" * 70)
    p("")
    p("## RESUMEN")
    p(f"Archivos de métricas:     {len(metrics_files)}")
    p(f"Archivos de tesis:        {len(thesis_files)}")
    p(f"Archivos de DimAsset:     {len(assets_files)}")
    p(f"Archivos de noticias:     {len(news_files)}")
    p(f"Activos distintos:        {len(assets)} ({', '.join(assets)})")
    p(f"Filas de métrica totales: {len(all_metric_rows)}")
    p(f"Tesis totales:            {len(all_thesis_rows)}")
    p(f"Última actualización:     {last_update or 'sin datos'}")
    p(f"Fuentes utilizadas:       {', '.join(sources) if sources else 'ninguna'}")
    p("")

    # --- VALIDACIÓN DEL DATA CONTRACT ---
    p("## VALIDACIÓN DEL DATA CONTRACT")
    schema_errors = []
    for fname, row in all_metric_rows:
        try:
            validate_metric_row(row)
        except ContractError as e:
            schema_errors.append(f"  [metrics/{fname}] {e}")
    for fname, row in all_thesis_rows:
        try:
            validate_thesis_row(row)
        except ContractError as e:
            schema_errors.append(f"  [thesis/{fname}] {e}")

    # duplicados: misma (asset_id, domain, metric, data_as_of) dos veces
    seen = {}
    duplicates = []
    for fname, row in all_metric_rows:
        key = (row.get("asset_id"), row.get("domain"), row.get("metric"), row.get("data_as_of"))
        if key in seen:
            duplicates.append(f"  {key} -- en {seen[key]} y {fname}")
        else:
            seen[key] = fname

    # metricas incompatibles: mismo nombre de metrica con unidades distintas
    # DENTRO del mismo asset_type. Entre asset_types distintos (ej. "precio"
    # cripto en EUR vía Kraken vs "precio" equity en USD vía Alpha Vantage)
    # una unidad distinta es esperada y no es una incidencia -- la moneda
    # real de cada activo ya queda documentada de forma explícita en
    # DimAsset.currency (ver validación de DimAsset más abajo), que es lo
    # que resuelve la ambigüedad, no forzar una unidad común aquí.
    metric_units = {}
    incompatible = []
    for _, row in all_metric_rows:
        m, u, at = row.get("metric"), row.get("unit"), row.get("asset_type")
        if m is None:
            continue
        metric_units.setdefault((m, at), set()).add(u)
    for (m, at), units in metric_units.items():
        if len(units) > 1:
            incompatible.append(f"  métrica '{m}' (asset_type={at}) aparece con unidades distintas: {units}")

    n_checks = len(all_metric_rows) + len(all_thesis_rows)
    p(f"Filas comprobadas: {n_checks}")
    p(f"Errores de esquema (campos ausentes/no reconocidos, tipos, rango 0-100, fechas): {len(schema_errors)}")
    for e in schema_errors[:20]:
        p(e)
    p(f"Duplicados (misma métrica+fecha repetida): {len(duplicates)}")
    for d in duplicates[:20]:
        p(d)
    p(f"Métricas con unidades incompatibles entre activos: {len(incompatible)}")
    for i in incompatible:
        p(i)
    p(f"RESULTADO: {_fmt_pass_fail(not schema_errors and not duplicates and not incompatible)}")
    p("")

    # --- VALIDACIÓN DE PRIVACIDAD ---
    p("## VALIDACIÓN DE PRIVACIDAD")
    privacy_issues = []
    for fname, row in all_metric_rows + all_thesis_rows:
        for key, val in row.items():
            if CREDENTIAL_KEY_PATTERN.search(key):
                privacy_issues.append(f"  [{fname}] campo con nombre sospechoso de credencial: '{key}'")
            if isinstance(val, str) and any(h in val for h in CARTERA_HINTS):
                privacy_issues.append(f"  [{fname}] posible dato de cartera privada en '{key}': {val!r}")
        extra_fields = set(row.keys()) - (THESIS_FIELDS if "thesis_id" in row else METRIC_FIELDS)
        if extra_fields:
            privacy_issues.append(f"  [{fname}] campos fuera del contrato (no deberían poder llevar nada no previsto): {extra_fields}")
    p("Comprobado: cartera_A, cantidad_neta, flujo_caja, credenciales, API keys, tokens, passwords, secretos.")
    p(f"Incidencias encontradas: {len(privacy_issues)}")
    for i in privacy_issues:
        p(i)
    p(f"RESULTADO: {_fmt_pass_fail(not privacy_issues)}")
    p("")

    # --- VALIDACIÓN TEMPORAL ---
    p("## VALIDACIÓN TEMPORAL (data_as_of independiente de retrieved_at)")
    independent_examples = []
    same_examples = []
    for fname, row in all_metric_rows:
        da, ra = row.get("data_as_of"), row.get("retrieved_at")
        if da and ra and da != ra[:10]:
            independent_examples.append((row["asset_id"], row["metric"], da, ra))
        elif da and ra:
            same_examples.append((row["asset_id"], row["metric"], da, ra))
    p(f"Filas donde data_as_of ≠ retrieved_at (fecha): {len(independent_examples)} de {len(all_metric_rows)}")
    p("Ejemplos reales:")
    for asset, metric, da, ra in independent_examples[:6]:
        p(f"  {asset}.{metric}: data_as_of={da} · retrieved_at={ra}")
    if not independent_examples:
        p("  (ninguno -- revisar si los adaptadores están usando 'ahora' para todo)")
    p(f"Filas donde coinciden (normal para datos en vivo: precio, técnico cripto): {len(same_examples)}")
    p("")

    # --- VALIDACIÓN DE FUENTES ---
    p("## VALIDACIÓN DE FUENTES (asset → metric → source)")
    no_source = [row for _, row in all_metric_rows if not row.get("source")]
    by_asset = {}
    for _, row in all_metric_rows:
        by_asset.setdefault(row["asset_id"], []).append((row["metric"], row.get("source")))
    for asset in assets:
        pairs = by_asset.get(asset, [])
        if not pairs:
            continue
        p(f"  {asset}:")
        for metric, source in pairs:
            p(f"    {metric:32s} ← {source}")
    p(f"Métricas sin fuente: {len(no_source)}")
    p(f"RESULTADO: {_fmt_pass_fail(not no_source)}")
    p("")

    # --- VALIDACIÓN DE DimAsset ---
    p("## VALIDACIÓN DE DimAsset (data/assets/*.json)")
    asset_schema_errors = []
    asset_privacy_issues = []
    no_currency = []
    for fname, row in assets_files.items():
        try:
            validate_asset_row(row)
        except ContractError as e:
            asset_schema_errors.append(f"  [assets/{fname}] {e}")
        for key, val in row.items():
            if CREDENTIAL_KEY_PATTERN.search(key):
                asset_privacy_issues.append(f"  [assets/{fname}] campo con nombre sospechoso de credencial: '{key}'")
            if isinstance(val, str) and any(h in val for h in CARTERA_HINTS):
                asset_privacy_issues.append(f"  [assets/{fname}] posible dato de cartera privada en '{key}': {val!r}")
        extra_fields = set(row.keys()) - ASSET_FIELDS
        if extra_fields:
            asset_privacy_issues.append(f"  [assets/{fname}] campos fuera del contrato: {extra_fields}")
        if not row.get("currency"):
            no_currency.append(row.get("asset_id", fname))
    p(f"Archivos de DimAsset: {len(assets_files)}")
    p(f"Errores de esquema: {len(asset_schema_errors)}")
    for e in asset_schema_errors[:20]:
        p(e)
    p(f"Incidencias de privacidad: {len(asset_privacy_issues)}")
    for i in asset_privacy_issues:
        p(i)
    p(f"Activos sin 'currency' documentada: {len(no_currency)}" + (f" ({', '.join(no_currency)})" if no_currency else ""))
    p(f"RESULTADO: {_fmt_pass_fail(not asset_schema_errors and not asset_privacy_issues and not no_currency)}")
    p("")

    # --- VALIDACIÓN DE NOTICIAS (data/news/*.json) ---
    p("## VALIDACIÓN DE NOTICIAS (data/news/*.json)")
    all_news_rows = []
    for fname, rows in news_files.items():
        for row in rows:
            all_news_rows.append((fname, row))

    news_schema_errors = []
    for fname, row in all_news_rows:
        try:
            validate_news_row(row)
        except ContractError as e:
            news_schema_errors.append(f"  [news/{fname}] {e}")

    news_privacy_issues = []
    for fname, row in all_news_rows:
        for key, val in row.items():
            if CREDENTIAL_KEY_PATTERN.search(key):
                news_privacy_issues.append(f"  [news/{fname}] campo con nombre sospechoso de credencial: '{key}'")
            if isinstance(val, str) and any(h in val for h in CARTERA_HINTS):
                news_privacy_issues.append(f"  [news/{fname}] posible dato de cartera privada en '{key}': {val!r}")
        extra_fields = set(row.keys()) - NEWS_FIELDS
        if extra_fields:
            news_privacy_issues.append(f"  [news/{fname}] campos fuera del contrato: {extra_fields}")

    # duplicados: mismo news_id repetido para el mismo activo
    seen_news = {}
    news_duplicates = []
    for fname, row in all_news_rows:
        key = (row.get("asset_id"), row.get("news_id"))
        if key in seen_news:
            news_duplicates.append(f"  {key} -- en {seen_news[key]} y {fname}")
        else:
            seen_news[key] = fname

    news_no_source = [row for _, row in all_news_rows if not row.get("source")]
    articles_by_asset = {}
    for _, row in all_news_rows:
        articles_by_asset.setdefault(row.get("asset_id"), 0)
        articles_by_asset[row.get("asset_id")] += 1

    p(f"Filas de noticia totales: {len(all_news_rows)}")
    if articles_by_asset:
        p("Artículos por activo:")
        for asset_id, n in sorted(articles_by_asset.items()):
            p(f"  {asset_id}: {n}")
    else:
        p("  (sin datos -- ningún activo tiene _data/{ID}_news_sentiment.json consultado todavía, ver engine/news/README.md)")
    p(f"Errores de esquema: {len(news_schema_errors)}")
    for e in news_schema_errors[:20]:
        p(e)
    p(f"Incidencias de privacidad: {len(news_privacy_issues)}")
    for i in news_privacy_issues:
        p(i)
    p(f"Duplicados (mismo news_id repetido para el mismo activo): {len(news_duplicates)}")
    for d in news_duplicates[:20]:
        p(d)
    p(f"Noticias sin fuente: {len(news_no_source)}")
    p(f"RESULTADO: {_fmt_pass_fail(not news_schema_errors and not news_privacy_issues and not news_duplicates and not news_no_source)}")
    p("")

    # --- QA-CORE: integridad de history/ por hash, SIN abrir los parquet ---
    p("## INTEGRIDAD DE history/ — nivel CORE (hash, sin abrir los parquet)")
    hash_errors, particiones_hasheadas = storage.verificar_hashes_manifiesto()
    p(f"Particiones comprobadas por hash: {particiones_hasheadas}")
    p("Detecta que una partición cerrada ha cambiado, que falta un fichero o que")
    p("sobra uno sin registrar. NO demuestra que su contenido sea correcto.")
    p(f"Incidencias: {len(hash_errors)}")
    for e in hash_errors[:20]:
        p(e)
    p(f"RESULTADO: {_fmt_pass_fail(not hash_errors)}")
    p("")

    # --- COBERTURA Y FRESCURA: informativo, nunca falla ---
    # No es una puerta y no debe serlo: que el IPC envejezca hasta su
    # cadencia normal de publicacion es correcto, y convertirlo en FAIL
    # pararia el cron un dia de cada dos por un comportamiento esperado.
    # Aqui se declara el estado; quien decida bloquear con el es el motor
    # de razonamiento, no la ingesta.
    p("## COBERTURA Y FRESCURA (informativo — no condiciona el resultado)")
    try:
        import cobertura
        cob = cobertura.evaluar()
        por_cobertura, por_frescura = {}, {}
        for f in cob["por_dominio"]:
            por_cobertura[f["cobertura"]] = por_cobertura.get(f["cobertura"], 0) + 1
            por_frescura[f["estado_frescura"]] = por_frescura.get(f["estado_frescura"], 0) + 1
        p(f"Dominios evaluados: {len(cob['por_dominio'])} (solo incoming/, sin PyArrow)")
        p("Cobertura:  " + " · ".join(f"{v} {k}" for k, v in sorted(por_cobertura.items())))
        p("Frescura:   " + " · ".join(f"{v} {k}" for k, v in sorted(por_frescura.items())))
        peores = [f for f in cob["por_dominio"] if f["estado_frescura"] in ("STALE", "UNKNOWN")]
        for f in sorted(peores, key=lambda x: -(x["retraso"] or 0))[:8]:
            p(f"  {f['asset_id']}.{f['domain']}: {f['estado_frescura']} "
              f"{f['retraso']} {f['unidad'] or ''} — manda {f['metrica_que_manda']} "
              f"(último dato {f['data_as_of_peor']})")
        incompletos = [f for f in cob["por_dominio"] if f["faltan"]]
        for f in incompletos:
            p(f"  {f['asset_id']}.{f['domain']}: {f['cobertura']} — faltan {', '.join(f['faltan'])}")
        p("Detalle completo: python3 engine/contract/cobertura.py")
    except Exception as e:  # noqa: BLE001 -- bloque informativo
        p(f"NO EVALUADO ({type(e).__name__}: {e})")
    p("")

    core_ok = (
        not schema_errors and not duplicates and not incompatible and not privacy_issues and not no_source
        and not asset_schema_errors and not asset_privacy_issues and not no_currency
        and not news_schema_errors and not news_privacy_issues and not news_duplicates and not news_no_source
        and not hash_errors
    )

    # --- QA-PARQUET: contenido real de las particiones. Solo con PyArrow. ---
    p("## CONTENIDO DE history/ — nivel PARQUET (abre cada partición)")
    if not hay_parquet:
        manifest_errors = []
        parquet_estado = "NOT RUN"
        p("NO EJECUTADO — PyArrow no está disponible en este entorno.")
        p("Sin abrir los parquet NO se ha comprobado: schema, número real de filas,")
        p("rango temporal de cada partición ni duplicados lógicos tras resolver")
        p("revisiones. El hash del nivel CORE detecta que los bytes cambiaron, pero")
        p("no sustituye a esta comprobación.")
        p(f"Alcance de las métricas validadas arriba: solo incoming/ ({len(all_metric_rows)} filas).")
    else:
        manifest_errors, particiones_revisadas = _validar_manifiestos()
        parquet_estado = "PASS" if not manifest_errors else "FAIL"
        p(f"Particiones abiertas y verificadas: {particiones_revisadas}")
        p("Comprueba schema, número real de filas, rango temporal y ausencia de")
        p("duplicados lógicos tras resolver revisiones.")
        p(f"Incidencias: {len(manifest_errors)}")
        for e in manifest_errors[:20]:
            p(e)
    p(f"RESULTADO: {parquet_estado}")
    p("")

    # Tres estados, nunca dos. "No se pudo verificar" no es "verificado".
    if not core_ok or parquet_estado == "FAIL":
        estado = "FAIL"
    elif parquet_estado == "NOT RUN":
        estado = "UNVERIFIED"
    else:
        estado = "VERIFIED"

    p("=" * 70)
    p(f"QA CORE:    {_fmt_pass_fail(core_ok)}")
    p(f"QA PARQUET: {parquet_estado}" + ("" if hay_parquet else "   (REASON: PyArrow unavailable)"))
    p(f"STATUS:     {estado}")
    p("=" * 70)

    # ok=False solo bloquea. UNVERIFIED no bloquea la ingesta -- sus filas
    # (incoming/) SI se han validado por completo -- pero tampoco se declara
    # verificada. Con require_parquet=True (CI de mantenimiento) tambien falla.
    ok = estado == "VERIFIED" or (estado == "UNVERIFIED" and not require_parquet)
    return "\n".join(lines), ok


if __name__ == "__main__":
    import sys
    report, ok = run_qa(require_parquet="--require-parquet" in sys.argv)
    print(report)
    raise SystemExit(0 if ok else 1)
