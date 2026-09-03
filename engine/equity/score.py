"""Motor de fundamentales de acciones -- Fase 2 (Bloque B).

A diferencia de los demas motores de este proyecto, la ingesta de datos
NO es un fetch_data.py ejecutable de forma independiente: los datos
vienen del conector MCP de Alpha Vantage ya autenticado en la cuenta del
usuario, y ese conector solo es invocable desde una sesion de Claude, no
desde un script externo. Guardar aqui una clave de API propia violaria
el protocolo de privacidad del proyecto (nunca almacenar claves/tokens).
Por eso: los datos se descargan a mano vía las herramientas MCP durante
la sesion y se guardan en _data/ (no versionado, igual que los demas
motores) -- score.py solo calcula sobre lo que ya este ahi.

Metodologia: igual disciplina que el resto -- valores puntuales (sin
serie historica de fundamentales en v1) se reportan como referencia, no
como percentil inventado. La unica metrica con verdadera posicion
relativa es la posicion en el rango de 52 semanas (dato real de Alpha
Vantage, no calculado a mano).
"""
import json
import os
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), "_data")


def _load(symbol, suffix):
    with open(f"{DATA_DIR}/{symbol}_{suffix}.json") as f:
        return json.load(f)


def score_asset(symbol):
    quote = _load(symbol, "quote")
    ov = _load(symbol, "overview")
    earn = _load(symbol, "earnings")["quarterlyEarnings"]

    price = quote["price"]
    high52, low52 = float(ov["52WeekHigh"]), float(ov["52WeekLow"])
    posicion_52w_pct = round((price - low52) / (high52 - low52) * 100, 1) if high52 > low52 else None

    sma50, sma200 = float(ov["50DayMovingAverage"]), float(ov["200DayMovingAverage"])

    ultimos_8 = earn[:8]
    sorpresas = [float(q["surprisePercentage"]) for q in ultimos_8 if q.get("surprisePercentage") not in (None, "None")]
    beats = sum(1 for s in sorpresas if s > 0)
    misses = sum(1 for s in sorpresas if s < 0)
    sorpresa_media_pct = round(sum(sorpresas) / len(sorpresas), 2) if sorpresas else None
    ultima_sorpresa_pct = sorpresas[0] if sorpresas else None

    target = float(ov["AnalystTargetPrice"]) if ov.get("AnalystTargetPrice") else None
    upside_pct = round((target - price) / price * 100, 1) if target else None

    ratings = {
        "strong_buy": int(ov.get("AnalystRatingStrongBuy", 0)),
        "buy": int(ov.get("AnalystRatingBuy", 0)),
        "hold": int(ov.get("AnalystRatingHold", 0)),
        "sell": int(ov.get("AnalystRatingSell", 0)),
        "strong_sell": int(ov.get("AnalystRatingStrongSell", 0)),
    }
    n_analistas = sum(ratings.values())

    # --- confluencia tecnica simple, mismo principio que engine/technical ---
    checks = {
        "precio_sobre_sma50": price > sma50,
        "precio_sobre_sma200": price > sma200,
        "ultima_sorpresa_positiva": (ultima_sorpresa_pct > 0) if ultima_sorpresa_pct is not None else None,
    }
    validos = [v for v in checks.values() if v is not None]
    alcistas = sum(1 for v in validos if v)
    if not validos:
        sesgo = "sin datos suficientes"
    elif alcistas == len(validos):
        sesgo = "confluencia alcista"
    elif alcistas == 0:
        sesgo = "confluencia bajista"
    else:
        sesgo = f"mixto ({alcistas}/{len(validos)} señales alcistas)"

    return {
        "activo": symbol,
        "fecha_dato": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "fuente_ultima_cotizacion": quote["latestDay"],
        "precio": price,
        "market_cap_usd": int(ov["MarketCapitalization"]),
        "pe_ratio": float(ov["PERatio"]) if ov.get("PERatio") not in (None, "None") else None,
        "peg_ratio": float(ov["PEGRatio"]) if ov.get("PEGRatio") not in (None, "None") else None,
        "ev_ebitda": float(ov["EVToEBITDA"]) if ov.get("EVToEBITDA") not in (None, "None") else None,
        "profit_margin_pct": round(float(ov["ProfitMargin"]) * 100, 1),
        "operating_margin_pct": round(float(ov["OperatingMarginTTM"]) * 100, 1),
        "roe_pct": round(float(ov["ReturnOnEquityTTM"]) * 100, 1),
        "roa_pct": round(float(ov["ReturnOnAssetsTTM"]) * 100, 1),
        "revenue_growth_yoy_pct": round(float(ov["QuarterlyRevenueGrowthYOY"]) * 100, 1),
        "earnings_growth_yoy_pct": round(float(ov["QuarterlyEarningsGrowthYOY"]) * 100, 1),
        "beta": float(ov["Beta"]) if ov.get("Beta") not in (None, "None") else None,
        "posicion_rango_52s_pct": posicion_52w_pct,
        "sma50": sma50,
        "sma200": sma200,
        "sorpresa_resultados": {
            "ultimos_8_trimestres_beats": beats,
            "ultimos_8_trimestres_misses": misses,
            "sorpresa_media_pct": sorpresa_media_pct,
            "ultima_sorpresa_pct": ultima_sorpresa_pct,
        },
        "analistas": {
            "precio_objetivo": target,
            "upside_pct": upside_pct,
            "n_analistas": n_analistas,
            "distribucion": ratings,
        },
        "confluencia": {"detalle": checks, "sesgo": sesgo},
        "data_quality_pct": 75,  # fuente unica (Alpha Vantage), snapshot sin serie historica de fundamentales
    }


ASSETS = ["IBM", "NVDA", "XOM"]

if __name__ == "__main__":
    out = {sym: score_asset(sym) for sym in ASSETS}
    print(json.dumps(out, indent=2, ensure_ascii=False))
