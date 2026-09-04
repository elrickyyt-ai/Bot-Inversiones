"""Orquesta los indicadores por activo y produce una lectura de
confluencia -- nunca un indicador aislado como senal (Fase 0, dominio
Market Behavior).
"""
import json
import os
from datetime import datetime, timezone

from indicators import sma, rsi, macd, atr, historical_volatility, roc, swing_structure

DATA_DIR = os.path.join(os.path.dirname(__file__), "_data")

ASSETS = ["BTC", "ETH", "ADA", "SOL", "DOT", "XRP"]


def _load_ohlc(symbol):
    with open(f"{DATA_DIR}/{symbol}_ohlc.json") as f:
        raw = json.load(f)
    # Kraken: [time, open, high, low, close, vwap, volume, count]
    return [
        {"time": r[0], "open": float(r[0 + 1]), "high": float(r[2]),
         "low": float(r[3]), "close": float(r[4]), "volume": float(r[6])}
        for r in raw
    ]


def score_asset(symbol):
    ohlc = _load_ohlc(symbol)
    closes = [c["close"] for c in ohlc]
    price = closes[-1]
    # fecha_dato = fecha real de la ultima vela usada, NO datetime.now().
    # Kraken puede devolver una serie desactualizada para un par concreto
    # (visto en vivo con BTC/XRP, ~45 dias de retraso) -- si se usara la
    # fecha de ejecucion, ese precio antiguo quedaria etiquetado como si
    # fuera de hoy. Detectado 2026-09-03, ver informe de la sesion.
    fecha_dato = datetime.fromtimestamp(ohlc[-1]["time"], tz=timezone.utc).strftime("%Y-%m-%d")

    sma20 = sma(closes, 20)[-1]
    sma50 = sma(closes, 50)[-1]
    sma100 = sma(closes, 100)[-1]
    sma200 = sma(closes, 200)[-1]
    rsi14 = rsi(closes, 14)[-1]
    _, _, macd_hist = macd(closes)
    macd_hist_last = macd_hist[-1]
    atr14 = atr(ohlc, 14)[-1]
    hv30 = historical_volatility(closes, 30)
    roc12 = roc(closes, 12)
    structure = swing_structure(closes)

    range_90 = closes[-90:] if len(closes) >= 90 else closes
    lo90, hi90 = min(range_90), max(range_90)
    pct_in_90d = round((price - lo90) / (hi90 - lo90) * 100, 1) if hi90 > lo90 else None

    # --- confluencia: cuenta senales alcistas entre las que SI hay dato ---
    checks = {
        "precio_sobre_sma50": (price > sma50) if sma50 else None,
        "precio_sobre_sma200": (price > sma200) if sma200 else None,
        "rsi_sobre_50": (rsi14 > 50) if rsi14 is not None else None,
        "macd_histograma_positivo": (macd_hist_last > 0) if macd_hist_last is not None else None,
    }
    validos = [v for v in checks.values() if v is not None]
    alcistas = sum(1 for v in validos if v)
    if not validos:
        sesgo = "sin datos suficientes"
    elif alcistas == len(validos):
        sesgo = "confluencia alcista (todas las señales coinciden)"
    elif alcistas == 0:
        sesgo = "confluencia bajista (todas las señales coinciden)"
    else:
        sesgo = f"mixto ({alcistas}/{len(validos)} señales alcistas — sin confluencia clara)"

    confidence = round(len(validos) / len(checks) * 100)

    return {
        "activo": symbol,
        "fecha_dato": fecha_dato,
        "precio": round(price, 6),
        "sma20": round(sma20, 6) if sma20 else None,
        "sma50": round(sma50, 6) if sma50 else None,
        "sma100": round(sma100, 6) if sma100 else None,
        "sma200": round(sma200, 6) if sma200 else None,
        "rsi14": round(rsi14, 1) if rsi14 is not None else None,
        "macd_histograma": round(macd_hist_last, 6) if macd_hist_last is not None else None,
        "atr14": round(atr14, 6) if atr14 is not None else None,
        "atr14_pct_precio": round(atr14 / price * 100, 2) if atr14 else None,
        "volatilidad_hist_30d_anualizada_pct": hv30,
        "roc12": roc12,
        "posicion_rango_90d_pct": pct_in_90d,
        "estructura": structure,
        "confluencia": {"detalle": checks, "sesgo": sesgo, "confidence_pct": confidence},
    }


if __name__ == "__main__":
    out = {sym: score_asset(sym) for sym in ASSETS}
    print(json.dumps(out, indent=2, ensure_ascii=False))
