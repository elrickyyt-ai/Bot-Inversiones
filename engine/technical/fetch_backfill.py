"""Ingesta de OHLC histórico para el backfill del motor técnico
(2026-09-04, Bloque 3 -- ver informes/2026-09-04_estrategia_backfill_historico.md
y la actualización de ese análisis en el informe de este bloque).

Fuente: Coinbase Exchange, endpoint público de velas
(`/products/{ID}/candles`), sin clave. Elegida sobre Yahoo Finance
(la otra candidata evaluada) por dos motivos, no solo por profundidad:

1. API oficial y documentada (docs.cloud.coinbase.com), a diferencia del
   endpoint no oficial de Yahoo Finance (el mismo que usa la librería
   `yfinance`) -- mismo criterio de riesgo/términos de uso ya aplicado en
   este proyecto al descartar Google News RSS (engine/news/, Fase 4 v2).
2. Da pares cotizados en EUR (BTC-EUR, ETH-EUR, ...) -- la misma divisa
   que ya usa engine/technical/ vía Kraken, sin necesidad de convertir
   con un tipo de cambio histórico (una fuente de error adicional que
   Yahoo, solo con pares en USD de forma nativa para HTTP, habría exigido
   evitar aquí).

A cambio da algo menos de profundidad que Yahoo para ETH/XRP/ADA (~años
menos) -- aceptable: el objetivo pedido era "varios meses/años", no el
máximo histórico posible, y Coinbase ya da varios años reales para los 6
activos.

Cada vela se convierte a la MISMA forma cruda que ya usa
engine/technical/_data/{symbol}_ohlc.json (Kraken): [time, open, high,
low, close, vwap, volume, count] -- vwap/count no vienen de Coinbase, se
guardan como 0 (campos que _load_ohlc() no lee). Así score.py::
_load_ohlc()/historical_series() no necesitan saber de dónde vino cada
fichero -- ninguna metodología nueva de parseo ni de cálculo.

Rango: desde un ancla antigua (Coinbase devuelve [] para fechas antes de
la cotización real, sin error) hasta el día ANTERIOR a la primera vela ya
cacheada de Kraken (_ohlc.json) -- backfill e incremental cubren rangos
disjuntos, nunca la misma fecha con dos fuentes distintas (ver
adapt_technical_backfill() en engine/contract/adapters.py).

Uso:
    python3 engine/technical/fetch_backfill.py          # los 6 activos
    python3 engine/technical/fetch_backfill.py BTC       # un solo activo (prueba piloto)
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

from score import _load_ohlc

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


def _kraken_earliest_date(symbol):
    """Frontera exclusiva: primera fecha ya cacheada por Kraken hoy."""
    ohlc = _load_ohlc(symbol)
    return datetime.fromtimestamp(ohlc[0]["time"], tz=timezone.utc)


def fetch_one(symbol, sleep_seconds=0.4):
    pair = COINBASE_PAIR[symbol]
    boundary = _kraken_earliest_date(symbol)
    rows = []
    start = ANCHOR_START
    while start < boundary:
        end = min(start + timedelta(days=PAGE_DAYS - 1), boundary - timedelta(days=1))
        if end < start:
            break
        url = (f"https://api.exchange.coinbase.com/products/{pair}/candles"
               f"?granularity=86400&start={start.strftime('%Y-%m-%dT00:00:00Z')}"
               f"&end={end.strftime('%Y-%m-%dT00:00:00Z')}")
        candles = _get(url)
        for c in candles:  # Coinbase: [time, low, high, open, close, volume]
            t, low, high, open_, close, volume = c
            rows.append([t, open_, high, low, close, 0, volume, 0])  # forma Kraken
        start = end + timedelta(days=1)
        time.sleep(sleep_seconds)

    rows.sort(key=lambda r: r[0])
    # de-duplicar por si dos paginas se solaparan en el limite (mismo dia)
    dedup = {r[0]: r for r in rows}
    rows = sorted(dedup.values(), key=lambda r: r[0])

    out_path = f"{OUT_DIR}/{symbol}_ohlc_backfill.json"
    with open(out_path, "w") as f:
        json.dump(rows, f)

    if rows:
        first = datetime.fromtimestamp(rows[0][0], tz=timezone.utc).strftime("%Y-%m-%d")
        last = datetime.fromtimestamp(rows[-1][0], tz=timezone.utc).strftime("%Y-%m-%d")
        print(f"{symbol}: {len(rows)} velas ({first} -> {last}, frontera Kraken excluida: {boundary.strftime('%Y-%m-%d')})")
    else:
        print(f"{symbol}: 0 velas (sin histórico previo a la frontera de Kraken)")
    return rows


def fetch_all():
    os.makedirs(OUT_DIR, exist_ok=True)
    for symbol in COINBASE_PAIR:
        fetch_one(symbol)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        fetch_one(args[0])
    else:
        fetch_all()
