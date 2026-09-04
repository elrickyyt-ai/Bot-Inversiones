"""Ingesta de OHLC histórico para el backfill del motor técnico
(2026-09-04, Bloque 3; corregido 2026-09-04 -- ver
informes/2026-09-04_estrategia_backfill_historico.md y el informe de
corrección del hueco de proceso).

Fuente: Coinbase Exchange, endpoint público de velas
(`/products/{ID}/candles`), sin clave. Elegida sobre Yahoo Finance por
dos motivos, no solo por profundidad:

1. API oficial y documentada (docs.cloud.coinbase.com), a diferencia del
   endpoint no oficial de Yahoo Finance (el mismo que usa la librería
   `yfinance`) -- mismo criterio de riesgo/términos de uso ya aplicado en
   este proyecto al descartar Google News RSS (engine/news/, Fase 4 v2).
2. Da pares cotizados en EUR (BTC-EUR, ETH-EUR, ...) -- la misma divisa
   que ya usa engine/technical/ vía Kraken, sin conversión de tipo de
   cambio histórico.

Cada vela se convierte a la MISMA forma cruda que ya usa
engine/technical/_data/{symbol}_ohlc.json (Kraken): [time, open, high,
low, close, vwap, volume, count] -- vwap/count no vienen de Coinbase, se
guardan como 0 (campos que _load_ohlc() no lee).

CORRECCIÓN 2026-09-04 -- "no descargar de más" (detectado por el
usuario en Power BI, ver el informe de este bloque): la v1 de este
fichero recalculaba la frontera de backfill a partir de
engine/technical/_data/{symbol}_ohlc.json (la caché ROTATIVA de Kraken,
que solo guarda los últimos ~720 días desde AHORA) y volvía a descargar
TODO el rango [ancla, esa frontera] cada vez que se ejecutaba. Eso tenía
dos problemas: (a) re-descargaba historia que ya teníamos en disco, y
(b) esa "frontera" no reflejaba lo que el Data Contract (data/metrics/)
ya tenía escrito de verdad -- el cron incremental solo escribe UN punto
por ejecución (el "hoy" de cada día que corrió), nunca los ~720 días
que trae la caché de Kraken -- así que entre el final del primer
backfill y el primer día real en que empezó a correr el cron diario
quedó un hueco real de ~2 años en data/metrics/, sin que ningún fichero
_ohlc.json lo reflejara.

v2 (esta): `update_cache(symbol)` EXTIENDE la caché local ya existente
(`{symbol}_ohlc_backfill.json`) desde su última vela guardada + 1 día
hasta HOY, fusionando (nunca re-descarga lo que ya está en disco). Cierra
cualquier hueco de proceso automáticamente sin importar dónde esté --
la exclusión de fechas ya cubiertas por el Data Contract (Kraken u
otra fuente) se hace en engine/contract/adapters.py::
adapt_technical_backfill(), no aquí -- este fichero solo mantiene la
caché de OHLC crudo lo más completa posible.

Uso:
    python3 engine/technical/fetch_backfill.py          # los 6 activos, extiende cada cache hasta hoy
    python3 engine/technical/fetch_backfill.py BTC       # un solo activo
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

OUT_DIR = os.path.join(os.path.dirname(__file__), "_data")

COINBASE_PAIR = {
    "BTC": "BTC-EUR", "ETH": "ETH-EUR", "ADA": "ADA-EUR",
    "SOL": "SOL-EUR", "DOT": "DOT-EUR", "XRP": "XRP-EUR",
}

ANCHOR_START = datetime(2009, 1, 1, tzinfo=timezone.utc)  # antes de que exista cualquier cripto -- Coinbase da [] sin error
PAGE_DAYS = 300  # tope real de Coinbase por petición a granularidad diaria


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "bot-inversiones-research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _fetch_range(symbol, start, end, sleep_seconds=0.4):
    """Descarga [start, end) de Coinbase para `symbol`, paginado (tope
    real ~300 dias por peticion). No toca disco -- solo devuelve filas
    en la misma forma cruda que ya usa Kraken."""
    pair = COINBASE_PAIR[symbol]
    rows = []
    cursor = start
    while cursor < end:
        page_end = min(cursor + timedelta(days=PAGE_DAYS - 1), end - timedelta(days=1))
        if page_end < cursor:
            break
        url = (f"https://api.exchange.coinbase.com/products/{pair}/candles"
               f"?granularity=86400&start={cursor.strftime('%Y-%m-%dT00:00:00Z')}"
               f"&end={page_end.strftime('%Y-%m-%dT00:00:00Z')}")
        candles = _get(url)
        for c in candles:  # Coinbase: [time, low, high, open, close, volume]
            t, low, high, open_, close, volume = c
            rows.append([t, open_, high, low, close, 0, volume, 0])  # forma Kraken
        cursor = page_end + timedelta(days=1)
        time.sleep(sleep_seconds)
    return rows


def _cache_path(symbol):
    return f"{OUT_DIR}/{symbol}_ohlc_backfill.json"


def update_cache(symbol):
    """Extiende la caché local existente hasta hoy, sin re-descargar lo
    que ya tiene guardado. Si no existe caché todavia para este activo,
    hace el backfill inicial completo desde ANCHOR_START."""
    path = _cache_path(symbol)
    existing = []
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)

    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if existing:
        last_cached = datetime.fromtimestamp(existing[-1][0], tz=timezone.utc)
        start = last_cached + timedelta(days=1)
    else:
        start = ANCHOR_START
    # +1 dia: "end" es exclusivo en _fetch_range, hoy debe poder incluirse
    new_rows = _fetch_range(symbol, start, now + timedelta(days=1))

    by_time = {r[0]: r for r in existing}
    for r in new_rows:
        by_time[r[0]] = r
    merged = sorted(by_time.values(), key=lambda r: r[0])

    with open(path, "w") as f:
        json.dump(merged, f)

    if merged:
        first = datetime.fromtimestamp(merged[0][0], tz=timezone.utc).strftime("%Y-%m-%d")
        last = datetime.fromtimestamp(merged[-1][0], tz=timezone.utc).strftime("%Y-%m-%d")
        print(f"{symbol}: {len(merged)} velas en caché ({first} -> {last}), {len(new_rows)} nuevas en esta ejecución")
    else:
        print(f"{symbol}: 0 velas (sin histórico disponible en Coinbase)")
    return merged


def update_all():
    os.makedirs(OUT_DIR, exist_ok=True)
    for symbol in COINBASE_PAIR:
        update_cache(symbol)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        update_cache(args[0])
    else:
        update_all()
