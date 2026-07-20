"""Cálculo de métricas y scoring del motor de fundamentales cripto.

Metodología (Fase 0, Paso 2.1): normalización por percentil dentro de un
universo de comparación declarado. En esta v1 el único universo disponible
es el HISTÓRICO PROPIO de cada activo (todavía no hay fuente de peers
cripto) -- se calcula percentil sobre series con histórico real (market
cap y TVL, 365 días). Las métricas sin serie histórica accesible en v1
(supply/max, FDV/MCap, actividad de desarrollo) se reportan como valor de
referencia puntual, NUNCA como un percentil inventado.
"""
import json
import os
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), "_data")


def _pct_in_window(values):
    if len(values) < 10:
        return None
    lo, hi = min(values), max(values)
    current = values[-1]
    if hi <= lo:
        return None
    return round((current - lo) / (hi - lo) * 100, 1)


def score_asset(symbol, tvl_chain):
    detail = json.load(open(f"{DATA_DIR}/{symbol}_detail.json"))
    chart = json.load(open(f"{DATA_DIR}/{symbol}_chart.json"))
    md = detail.get("market_data", {})
    dd = detail.get("developer_data", {})

    circ = md.get("circulating_supply")
    denom = md.get("max_supply") or md.get("total_supply")
    supply_pct_of_max = round(circ / denom * 100, 1) if (circ and denom) else None

    mcap = md.get("market_cap", {}).get("eur")
    fdv = md.get("fully_diluted_valuation", {}).get("eur")
    fdv_mcap_ratio = round(fdv / mcap, 3) if (fdv and mcap) else None

    mcap_series = [v for _, v in chart["market_caps"]]
    mcap_percentile = _pct_in_window(mcap_series)

    tvl_now = None
    tvl_percentile = None
    tvl_data_issue = False
    if tvl_chain:
        tvl_series = json.load(open(f"{DATA_DIR}/{symbol}_tvl.json"))
        vals = [r["tvl"] for r in tvl_series][-365:]
        tvl_now = vals[-1] if vals else None
        tvl_percentile = _pct_in_window(vals)
        if tvl_now is not None and tvl_now == 0:
            tvl_data_issue = True

    dev_issue = (dd.get("commit_count_4_weeks") == 0 and dd.get("stars", 0) == 0)

    # Data Quality: techo bajo por fuente única (CoinGecko/DefiLlama), y
    # más bajo aún si se detecta una posible incidencia de mapeo de datos.
    data_quality = 80
    if tvl_data_issue or dev_issue:
        data_quality = 45

    return {
        "activo": symbol,
        "fecha_dato": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "supply_pct_of_max": supply_pct_of_max,
        "fdv_mcap_ratio": fdv_mcap_ratio,
        "market_cap_percentile_365d": mcap_percentile,
        "tvl_usd_actual": tvl_now,
        "tvl_percentile_365d": tvl_percentile,
        "dev_commits_4_semanas": dd.get("commit_count_4_weeks"),
        "dev_stars": dd.get("stars"),
        "dev_forks": dd.get("forks"),
        "posible_incidencia_datos": tvl_data_issue or dev_issue,
        "data_quality_pct": data_quality,
    }


ASSETS_TVL = {"BTC": None, "ETH": "Ethereum", "ADA": "Cardano", "SOL": "Solana",
              "DOT": "Polkadot", "XRP": None}

if __name__ == "__main__":
    out = {sym: score_asset(sym, chain) for sym, chain in ASSETS_TVL.items()}
    print(json.dumps(out, indent=2, ensure_ascii=False))
