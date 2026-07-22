"""Indicadores tecnicos, implementacion en Python puro (sin numpy/pandas).

Fase 0, dominio Market Behavior. Principio explicito: "no utilizar
indicadores como senales aisladas, buscar confluencias" -- por eso
score.py combina estos indicadores en una lectura de confluencia en vez
de reportar cada uno como una senal independiente.
"""
import math


def sma(values, period):
    out = [None] * len(values)
    for i in range(period - 1, len(values)):
        out[i] = sum(values[i - period + 1:i + 1]) / period
    return out


def ema(values, period):
    out = [None] * len(values)
    if len(values) < period:
        return out
    k = 2 / (period + 1)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    for i in range(period, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(closes, period=14):
    """RSI de Wilder."""
    out = [None] * len(closes)
    if len(closes) < period + 1:
        return out
    gains, losses = [], []
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    out[period] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = max(change, 0)
        loss = max(-change, 0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def macd(closes, fast=12, slow=26, signal=9):
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = [
        (a - b) if (a is not None and b is not None) else None
        for a, b in zip(ema_fast, ema_slow)
    ]
    valid = [v for v in macd_line if v is not None]
    signal_valid = ema(valid, signal)
    signal_line = [None] * (len(macd_line) - len(valid)) + signal_valid
    hist = [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(macd_line, signal_line)
    ]
    return macd_line, signal_line, hist


def atr(ohlc, period=14):
    """ohlc: lista de dicts con high/low/close (o tuplas h,l,c)."""
    trs = [None]
    for i in range(1, len(ohlc)):
        h, l, prev_c = ohlc[i]["high"], ohlc[i]["low"], ohlc[i - 1]["close"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        trs.append(tr)
    out = [None] * len(ohlc)
    if len(ohlc) < period + 1:
        return out
    seed = sum(trs[1:period + 1]) / period
    out[period] = seed
    for i in range(period + 1, len(ohlc)):
        out[i] = (out[i - 1] * (period - 1) + trs[i]) / period
    return out


def historical_volatility(closes, window=30, periods_per_year=365):
    """Volatilidad anualizada de retornos logaritmicos, ultima ventana."""
    if len(closes) < window + 1:
        return None
    rets = [
        math.log(closes[i] / closes[i - 1])
        for i in range(len(closes) - window, len(closes))
        if closes[i - 1] > 0
    ]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return round(math.sqrt(var) * math.sqrt(periods_per_year) * 100, 1)


def roc(closes, period=12):
    if len(closes) < period + 1 or closes[-period - 1] == 0:
        return None
    return round((closes[-1] - closes[-period - 1]) / closes[-period - 1] * 100, 1)


def swing_structure(closes, window=10, lookback_swings=4):
    """Detecta maximos/minimos locales (ventana de `window` velas a cada
    lado) y clasifica la secuencia de los ultimos swings como
    Higher-High/Higher-Low, Lower-High/Lower-Low, o mixta."""
    highs, lows = [], []
    for i in range(window, len(closes) - window):
        seg = closes[i - window:i + window + 1]
        if closes[i] == max(seg):
            highs.append((i, closes[i]))
        if closes[i] == min(seg):
            lows.append((i, closes[i]))

    def classify(points, kind):
        pts = points[-lookback_swings:]
        if len(pts) < 2:
            return "datos insuficientes"
        diffs = [pts[i][1] - pts[i - 1][1] for i in range(1, len(pts))]
        if all(d > 0 for d in diffs):
            return f"Higher {kind}s consecutivos"
        if all(d < 0 for d in diffs):
            return f"Lower {kind}s consecutivos"
        return "mixto / sin estructura clara"

    return {
        "estructura_maximos": classify(highs, "High"),
        "estructura_minimos": classify(lows, "Low"),
        "n_maximos_detectados": len(highs),
        "n_minimos_detectados": len(lows),
    }
