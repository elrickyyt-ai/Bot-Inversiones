"""Ingesta de datos para el motor tecnico (Fase 3).

Fuente: Kraken OHLC publico (sin clave), interval diario. Da hasta ~720
velas (aprox. 2 anios), suficiente para SMA200 y el resto de indicadores
de esta v1. Si en el futuro se necesita mas profundidad historica, ver el
gap ya documentado en docs/02-fase1-gaps-y-roadmap-fuentes.md.
"""
import json
import os
import urllib.request

OUT_DIR = os.path.join(os.path.dirname(__file__), "_data")

KRAKEN_PAIR = {
    "BTC": "XBTEUR", "ETH": "ETHEUR", "ADA": "ADAEUR",
    "SOL": "SOLEUR", "DOT": "DOTEUR", "XRP": "XRPEUR",
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "bot-inversiones-research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_all():
    os.makedirs(OUT_DIR, exist_ok=True)
    for sym, pair in KRAKEN_PAIR.items():
        d = _get(f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=1440")
        if d.get("error"):
            print(f"{sym}: error {d['error']}")
            continue
        result_key = [k for k in d["result"].keys() if k != "last"][0]
        candles = d["result"][result_key]
        json.dump(candles, open(f"{OUT_DIR}/{sym}_ohlc.json", "w"))
        print(f"{sym}: {len(candles)} velas diarias")


if __name__ == "__main__":
    fetch_all()
