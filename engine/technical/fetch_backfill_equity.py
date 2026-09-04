"""Ingesta de OHLC histórico para el backfill del motor técnico de
acciones (2026-09-04, Bloque 4 -- ver evaluación previa y
engine/technical/README.md).

Fuente: Yahoo Finance, endpoint no oficial de gráficas
(`query1.finance.yahoo.com/v8/finance/chart/{TICKER}`), sin clave --
evaluada explícitamente contra Alpha Vantage (verificado en vivo:
`TIME_SERIES_DAILY_ADJUSTED` y `outputsize=full` están bloqueados en el
plan gratuito -- solo da ~100 velas recientes sin ajustar, insuficiente
para un backfill profundo). Mismo perfil de riesgo/ToS ya aceptado para
el backfill de cripto (Coinbase se prefirió allí por ser oficial, pero
no existe un equivalente oficial y gratuito para profundidad de acciones
-- ver la comparación completa en README.md).

**Precio usado: `close`, nunca `adjclose`.** Verificado en vivo que
Yahoo devuelve `close` ya ajustado por TODOS los splits de forma
retroactiva y continua (ej. el precio de NVDA en 2024-06-07, un día
antes de su split 10:1, ya viene dividido por 10 en el campo `close` --
comprobado contra el hecho histórico real, ~$1208 sin ajustar) -- así
que no hace falta ningún cálculo de ajuste por split en este proyecto,
Yahoo ya lo hace. `adjclose` añade ADEMÁS un ajuste por dividendos que
NO se usa aquí: una caída de precio en el ex-dividendo es una variación
real de mercado (no un artefacto mecánico como un split) y no debe
"corregirse", y `adjclose` se recalcula con cada dividendo futuro
(inestable frente a re-ejecuciones); `close` solo cambiaría si el propio
activo hace un split nuevo -- un evento raro y detectable, no una deriva
continua.

Cada vela se convierte a la MISMA forma cruda que ya usa
engine/technical/_data/{symbol}_ohlc.json (Kraken) y
{symbol}_ohlc_backfill.json (Coinbase): [time, open, high, low, close,
vwap, volume, count] -- vwap/count no aplican aquí, se guardan como 0.
Así score.py::_load_ohlc()/historical_series() no necesitan saber de
dónde vino cada fichero -- ninguna metodología nueva de parseo ni de
cálculo, el mismo motor técnico sirve para cripto y acciones.

Uso:
    python3 engine/technical/fetch_backfill_equity.py          # IBM, NVDA, XOM
    python3 engine/technical/fetch_backfill_equity.py NVDA     # un solo activo
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

OUT_DIR = os.path.join(os.path.dirname(__file__), "_data")

YAHOO_TICKERS = ["IBM", "NVDA", "XOM"]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "bot-inversiones-research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _cache_path(symbol):
    return f"{OUT_DIR}/{symbol}_ohlc_backfill.json"


def update_cache(symbol):
    """Extiende la caché local existente hasta hoy, sin re-descargar lo
    que ya tiene guardado -- mismo patrón que
    fetch_backfill.py::update_cache() (cripto). Si no existe caché
    todavía, Yahoo devuelve toda la historia disponible en una sola
    petición (sin paginar, a diferencia de Coinbase -- verificado en
    vivo: IBM/XOM dan sus ~14000 velas completas en una sola llamada)."""
    path = _cache_path(symbol)
    existing = []
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)

    start = 0 if not existing else existing[-1][0] + 86400
    end = int(datetime.now(timezone.utc).timestamp()) + 86400  # +1 dia: incluir "hoy"

    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?period1={start}&period2={end}&interval=1d&events=div,split")
    data = _get(url)
    result = data.get("chart", {}).get("result")
    if not result:
        print(f"{symbol}: sin datos nuevos ({data.get('chart', {}).get('error')})")
        return existing
    r = result[0]
    ts = r.get("timestamp", [])
    q = r["indicators"]["quote"][0]
    splits = r.get("events", {}).get("splits", {})

    new_rows = []
    for i, t in enumerate(ts):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, l, c, v):
            continue  # sesion con dato incompleto (ej. medio dia festivo con feed roto) -- no inventar
        new_rows.append([t, o, h, l, c, 0, v, 0])

    by_time = {row[0]: row for row in existing}
    for row in new_rows:
        by_time[row[0]] = row
    merged = sorted(by_time.values(), key=lambda row: row[0])

    with open(path, "w") as f:
        json.dump(merged, f)

    if merged:
        first = datetime.fromtimestamp(merged[0][0], tz=timezone.utc).strftime("%Y-%m-%d")
        last = datetime.fromtimestamp(merged[-1][0], tz=timezone.utc).strftime("%Y-%m-%d")
        splits_txt = f", {len(splits)} split(s) en el rango descargado" if splits else ""
        print(f"{symbol}: {len(merged)} velas en caché ({first} -> {last}), {len(new_rows)} nuevas en esta ejecución{splits_txt}")
    else:
        print(f"{symbol}: 0 velas")
    return merged


def update_all():
    os.makedirs(OUT_DIR, exist_ok=True)
    for symbol in YAHOO_TICKERS:
        update_cache(symbol)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        update_cache(args[0])
    else:
        update_all()
