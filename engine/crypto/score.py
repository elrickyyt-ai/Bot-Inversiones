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


def historical_tvl_percentile(symbol, tvl_chain):
    """Backfill (2026-09-04): serie historica completa de
    tvl_percentile_365d -- misma formula que score_asset() ya usa para
    "hoy" (_pct_in_window sobre una ventana movil de 365 dias), aplicada
    a cada punto de la serie de DefiLlama ya descargada en vez de solo
    al ultimo. Devuelve [] para activos sin cadena de TVL (BTC/XRP, por
    diseno -- ver ASSETS_TVL) y [] tambien para los primeros ~365 dias
    de cada cadena, donde todavia no hay ventana suficiente
    (_pct_in_window exige al menos 10 puntos, igual que en "hoy")."""
    if not tvl_chain:
        return []
    with open(f"{DATA_DIR}/{symbol}_tvl.json") as f:
        tvl_series = json.load(f)
    valores = [r["tvl"] for r in tvl_series]
    fechas = [datetime.fromtimestamp(r["date"], tz=timezone.utc).strftime("%Y-%m-%d") for r in tvl_series]
    out = []
    for i in range(len(valores)):
        ventana = valores[max(0, i - 364):i + 1]
        pct = _pct_in_window(ventana)
        if pct is not None:
            out.append((fechas[i], pct))
    return out


def score_asset(symbol, tvl_chain):
    with open(f"{DATA_DIR}/{symbol}_detail.json") as f:
        detail = json.load(f)
    with open(f"{DATA_DIR}/{symbol}_chart.json") as f:
        chart = json.load(f)
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
        with open(f"{DATA_DIR}/{symbol}_tvl.json") as f:
            tvl_series = json.load(f)
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

    # fecha_dato = fecha real que CoinGecko reporta para este snapshot
    # (detail['last_updated']), NO datetime.now(). Comprobado en vivo:
    # CoinGecko puede devolver un snapshot desactualizado para un activo
    # concreto (visto con BTC/XRP, mismo dia ~45 dias de retraso que
    # Kraken) -- usar la fecha de ejecucion etiquetaria ese dato antiguo
    # como si fuera de hoy. Fallback a hoy solo si la fuente no trae el
    # campo (no deberia faltar nunca en la practica).
    last_updated = detail.get("last_updated")
    fecha_dato = last_updated[:10] if last_updated else datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return {
        "activo": symbol,
        "fecha_dato": fecha_dato,
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
