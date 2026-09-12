"""Descarga del NIVEL PUBLICADO de un indice de referencia -- D-21.

Distinto de fetch_backfill_equity.py aunque use la misma API: lo que baja
aqui NO es un instrumento analizado. Un indice no se negocia, no tiene
sector ni mercado de cotizacion, y por eso su serie no vive en
data/history/ (el arbol de activos) sino en data/benchmarks/. Meterla en
el arbol de activos haria que `storage.asset_type_of()` la devolviese
como un activo mas, que `cadencias.esperadas()` no supiera que metricas
esperar de ella y que `Asset Count` de Power BI subiera en silencio --
los tres efectos que la auditoria de D-21 midio.

Por que el nivel publicado y no un ETF que replique el indice: un ETF
tiene comision, tracking error, distribuciones y acciones corporativas
propias, y todo eso entraria en el benchmark metodologico. El nivel del
indice no tiene nada de eso -- verificado en vivo para ^GSPC: cero
eventos de split o dividendo en 14.291 sesiones, y close == adjclose en
todas ellas.

Uso:
    python3 engine/technical/fetch_benchmark.py          # actualiza SP500
"""
import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_data")
DESTINO_DIR = os.path.join(RAIZ, "data", "benchmarks")

# ticker de la fuente -> (benchmark_id, nombre de la fuente en el contrato)
BENCHMARKS = {
    "^GSPC": ("SP500", "Yahoo Finance"),
}

COLUMNAS = ["benchmark_id", "data_as_of", "value", "source", "retrieved_at"]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 bot-inversiones-research/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _cache_path(ticker):
    return os.path.join(CACHE_DIR, f"{ticker.replace('^', '')}_index_level.json")


def update_cache(ticker, reintentos=3):
    """Extiende la cache local hasta hoy sin re-descargar lo ya guardado,
    mismo patron que fetch_backfill_equity.py::update_cache()."""
    path = _cache_path(ticker)
    existing = []
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)

    start = 0 if not existing else existing[-1][0] + 86400
    end = int(datetime.now(timezone.utc).timestamp()) + 86400
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}"
           f"?period1={start}&period2={end}&interval=1d")

    data = None
    for intento in range(reintentos):
        try:
            data = _get(url)
            break
        except Exception as exc:  # noqa: BLE001 -- la descarga larga se corta a veces
            if intento == reintentos - 1:
                raise
            print(f"  {ticker}: reintento {intento + 1} tras {type(exc).__name__}")

    result = data.get("chart", {}).get("result")
    if not result:
        print(f"{ticker}: sin datos nuevos ({data.get('chart', {}).get('error')})")
        return existing
    r = result[0]
    ts = r.get("timestamp", [])
    # Cuando la cache ya esta al dia, Yahoo devuelve un `result` sin bloque
    # de cotizaciones. No es un error: es "no hay nada nuevo".
    quote = (r.get("indicators", {}).get("quote") or [{}])[0]
    close = quote.get("close")
    if not ts or close is None:
        print(f"{ticker}: cache ya al dia ({len(existing)} sesiones)")
        return existing

    nuevas = []
    for i, t in enumerate(ts):
        if close[i] is None:
            continue  # sesion sin cierre: no se inventa
        nuevas.append([t, close[i]])

    por_tiempo = {fila[0]: fila for fila in existing}
    for fila in nuevas:
        por_tiempo[fila[0]] = fila
    merged = sorted(por_tiempo.values(), key=lambda f: f[0])

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(merged, f)
    if merged:
        p = datetime.fromtimestamp(merged[0][0], tz=timezone.utc).strftime("%Y-%m-%d")
        u = datetime.fromtimestamp(merged[-1][0], tz=timezone.utc).strftime("%Y-%m-%d")
        print(f"{ticker}: {len(merged)} sesiones en cache ({p} -> {u}), {len(nuevas)} en esta ejecucion")
    return merged


def escribir(benchmark_id, filas, source, retrieved_at=None):
    """Escribe data/benchmarks/{benchmark_id}.csv. Idempotente y
    determinista: mismas sesiones -> mismo fichero byte a byte salvo
    retrieved_at, que solo cambia en las filas NUEVAS (igual que el
    contrato de metricas, que nunca reescribe por solo retrieved_at)."""
    os.makedirs(DESTINO_DIR, exist_ok=True)
    destino = os.path.join(DESTINO_DIR, f"{benchmark_id}.csv")
    previas = {r["data_as_of"]: r for r in leer(benchmark_id)}
    retrieved_at = retrieved_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    salida = {}
    for t, valor in filas:
        fecha = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
        # Se compara el valor YA REDONDEADO, no el crudo: el fichero guarda
        # cuatro decimales, asi que comparar contra la precision completa
        # marcaba como "cambiada" cada fila en cada ejecucion y rompia la
        # idempotencia -- el mismo error que el contrato de metricas evita
        # al no reescribir por solo retrieved_at.
        texto = f"{valor:.4f}"
        anterior = previas.get(fecha)
        if anterior and anterior["value"] == texto:
            salida[fecha] = anterior          # sin cambio real: conserva su retrieved_at
        else:
            salida[fecha] = {"benchmark_id": benchmark_id, "data_as_of": fecha,
                             "value": texto, "source": source,
                             "retrieved_at": retrieved_at}
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        for fecha in sorted(salida):
            w.writerow(salida[fecha])
    nuevas = len(salida) - sum(1 for fecha in salida if fecha in previas)
    print(f"{benchmark_id}: {len(salida)} sesiones escritas ({nuevas} nuevas)")
    return len(salida), nuevas


def leer(benchmark_id):
    destino = os.path.join(DESTINO_DIR, f"{benchmark_id}.csv")
    if not os.path.exists(destino):
        return []
    with open(destino, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def serie(benchmark_id):
    """(fechas ordenadas, {fecha: nivel})."""
    niveles = {r["data_as_of"]: float(r["value"]) for r in leer(benchmark_id)}
    return sorted(niveles), niveles


def validar_serie(benchmark_id):
    """Incidencias de la serie almacenada. Lista vacia = correcta."""
    e = []
    filas = leer(benchmark_id)
    if not filas:
        return [f"{benchmark_id}: serie vacia"]
    vistas = set()
    anterior = None
    for r in filas:
        if set(r) != set(COLUMNAS):
            e.append(f"{benchmark_id}: columnas inesperadas {sorted(r)}")
            break
        if r["benchmark_id"] != benchmark_id:
            e.append(f"{benchmark_id}: fila con benchmark_id {r['benchmark_id']}")
        if r["data_as_of"] in vistas:
            e.append(f"{benchmark_id}: fecha duplicada {r['data_as_of']}")
        vistas.add(r["data_as_of"])
        if anterior and r["data_as_of"] <= anterior:
            e.append(f"{benchmark_id}: fechas sin orden en {r['data_as_of']}")
        anterior = r["data_as_of"]
        try:
            if float(r["value"]) <= 0:
                e.append(f"{benchmark_id}: nivel no positivo en {r['data_as_of']}")
        except ValueError:
            e.append(f"{benchmark_id}: nivel no numerico en {r['data_as_of']}")
        if r["data_as_of"] > r["retrieved_at"][:10]:
            e.append(f"{benchmark_id}: {r['data_as_of']} posterior a su retrieved_at")
    return e


def main():
    for ticker, (bid, source) in BENCHMARKS.items():
        filas = update_cache(ticker)
        escribir(bid, filas, source)
        inc = validar_serie(bid)
        print(f"{bid}: validacion -> {inc or 'sin incidencias'}")


if __name__ == "__main__":
    import urllib.parse  # noqa: F401 -- usado en update_cache
    main()
