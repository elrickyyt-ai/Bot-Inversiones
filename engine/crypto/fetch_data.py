"""Ingesta de datos para el motor de fundamentales cripto (tokenomics + on-chain).

Fuentes (ambas públicas, sin clave):
- CoinGecko: snapshot de tokenomics (supply, market cap, FDV) y actividad de
  desarrollo (GitHub), y precio+market cap diario de los últimos 365 días.
- DefiLlama: TVL diario histórico por chain (para chains con contratos
  inteligentes: Ethereum, Solana, Cardano, Polkadot).

CoinGecko limita su plan gratuito a pocas peticiones por minuto: hay que
espaciar las llamadas (ver sleep entre activos) o se recibe 429.
"""
import json
import time
import urllib.request
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "_data")

ASSETS = {
    "BTC": {"cg_id": "bitcoin", "tvl_chain": None},
    "ETH": {"cg_id": "ethereum", "tvl_chain": "Ethereum"},
    "ADA": {"cg_id": "cardano", "tvl_chain": "Cardano"},
    "SOL": {"cg_id": "solana", "tvl_chain": "Solana"},
    "DOT": {"cg_id": "polkadot", "tvl_chain": "Polkadot"},
    "XRP": {"cg_id": "ripple", "tvl_chain": None},
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "bot-inversiones-research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_all(sleep_seconds=20):
    os.makedirs(OUT_DIR, exist_ok=True)
    for sym, cfg in ASSETS.items():
        detail = _get(
            f"https://api.coingecko.com/api/v3/coins/{cfg['cg_id']}"
            "?localization=false&tickers=false&market_data=true"
            "&community_data=false&developer_data=true&sparkline=false"
        )
        json.dump(detail, open(f"{OUT_DIR}/{sym}_detail.json", "w"))
        time.sleep(sleep_seconds)

        chart = _get(
            f"https://api.coingecko.com/api/v3/coins/{cfg['cg_id']}/market_chart"
            "?vs_currency=eur&days=365"
        )
        json.dump(chart, open(f"{OUT_DIR}/{sym}_chart.json", "w"))
        time.sleep(sleep_seconds)

        if cfg["tvl_chain"]:
            tvl = _get(f"https://api.llama.fi/v2/historicalChainTvl/{cfg['tvl_chain']}")
            json.dump(tvl, open(f"{OUT_DIR}/{sym}_tvl.json", "w"))
            time.sleep(2)


if __name__ == "__main__":
    fetch_all()
