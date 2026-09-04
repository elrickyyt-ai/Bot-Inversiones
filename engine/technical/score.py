"""Orquesta los indicadores por activo y produce una lectura de
confluencia -- nunca un indicador aislado como senal (Fase 0, dominio
Market Behavior).
"""
import json
import os
from datetime import datetime, timezone

from indicators import sma, rsi, macd, atr, historical_volatility, historical_volatility_series, roc, swing_structure
from trading_calendar import sessions_skipped_between

DATA_DIR = os.path.join(os.path.dirname(__file__), "_data")

ASSETS = ["BTC", "ETH", "ADA", "SOL", "DOT", "XRP"]


def _load_ohlc(symbol, path=None):
    """path=None (por defecto): fichero incremental de Kraken, como
    siempre. Backfill (2026-09-04): acepta una ruta alternativa (ej. el
    fichero de Coinbase Exchange, engine/technical/fetch_backfill.py) para
    reutilizar exactamente el mismo parseo -- ambos ficheros se guardan en
    la misma forma cruda [time, open, high, low, close, vwap, volume,
    count] precisamente para esto, sin duplicar logica de parseo."""
    path = path or f"{DATA_DIR}/{symbol}_ohlc.json"
    with open(path) as f:
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
        "volumen": round(ohlc[-1]["volume"], 6),
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


def _split_contiguous(ohlc, asset_type="crypto"):
    """Divide en tramos donde no falta ninguna sesión de trading
    esperada entre una vela y la siguiente (ver trading_calendar.py).
    Un hueco real en la serie (ej. XRP: Coinbase lo deslistó en EEUU
    entre 2021-01 y 2023-07 por el litigio con la SEC, ~905 días sin
    cotización en esa fuente) NO debe mezclarse dentro de una misma
    ventana móvil de SMA/RSI/ATR/volatilidad -- eso calcularía, por
    ejemplo, un "SMA20" combinando un precio de 2023 con 19 precios de
    antes del hueco, algo que no es una media móvil de 20 días real.
    Cada tramo se trata como una serie independiente, con su propio
    periodo de calentamiento -- mismo principio que ya aplica al inicio
    de cualquier serie con menos de N velas disponibles.

    asset_type="crypto" (por defecto, preserva el comportamiento previo
    exacto): cotiza 24/7, cualquier día ausente es un hueco real, 0
    sesiones esperadas entre dos fechas consecutivas equivale a estar
    exactamente 1 día natural aparte -- mismo resultado que la
    comprobación anterior (`== 86400`), ahora expresada como caso
    particular de la misma función que también sirve para acciones.
    asset_type="equity": un viernes seguido de un lunes, o un festivo
    bursátil NYSE, no cuentan como sesión esperada -- no rompen el
    tramo. Una sesión de trading real ausente sí lo rompe."""
    if not ohlc:
        return []
    segments = [[ohlc[0]]]
    for c in ohlc[1:]:
        prev_date = datetime.fromtimestamp(segments[-1][-1]["time"], tz=timezone.utc).date()
        curr_date = datetime.fromtimestamp(c["time"], tz=timezone.utc).date()
        if sessions_skipped_between(prev_date, curr_date, asset_type) == 0:
            segments[-1].append(c)
        else:
            segments.append([c])
    return segments


def _historical_series_segment(ohlc):
    closes = [c["close"] for c in ohlc]

    sma20_s = sma(closes, 20)
    sma50_s = sma(closes, 50)
    sma100_s = sma(closes, 100)
    sma200_s = sma(closes, 200)
    rsi14_s = rsi(closes, 14)
    atr14_s = atr(ohlc, 14)
    hv30_s = historical_volatility_series(closes, 30)

    out = []
    for i, c in enumerate(ohlc):
        fecha_dato = datetime.fromtimestamp(c["time"], tz=timezone.utc).strftime("%Y-%m-%d")
        precio = closes[i]
        atr14 = atr14_s[i]
        out.append({
            "fecha_dato": fecha_dato,
            "precio": round(precio, 6),
            "volumen": round(c["volume"], 6),
            "sma20": round(sma20_s[i], 6) if sma20_s[i] is not None else None,
            "sma50": round(sma50_s[i], 6) if sma50_s[i] is not None else None,
            "sma100": round(sma100_s[i], 6) if sma100_s[i] is not None else None,
            "sma200": round(sma200_s[i], 6) if sma200_s[i] is not None else None,
            "rsi14": round(rsi14_s[i], 1) if rsi14_s[i] is not None else None,
            "atr14": round(atr14, 6) if atr14 is not None else None,
            "atr14_pct_precio": round(atr14 / precio * 100, 2) if atr14 else None,
            "volatilidad_hist_30d_anualizada_pct": hv30_s[i],
        })
    return out


def historical_series(symbol, path, asset_type="crypto"):
    """Backfill (2026-09-04): serie historica completa de precio/volumen/
    indicadores -- misma metodologia que score_asset() usa para "hoy"
    (mismas funciones de indicators.py: sma/rsi/atr/historical_volatility,
    sobre el mismo OHLC parseado por _load_ohlc), recorriendo TODO el
    array que esas funciones ya devuelven en vez de descartar todo menos
    el ultimo punto ([-1]). No introduce ningun calculo nuevo.

    `path` (obligatorio, a diferencia de score_asset()): el fichero de
    origen del backfill, normalmente
    engine/technical/_data/{symbol}_ohlc_backfill.json (Coinbase
    Exchange, ver fetch_backfill.py) -- nunca el fichero incremental de
    Kraken, para no re-procesar lo que el flujo incremental ya cubre.

    `asset_type` (2026-09-04, Bloque 4): pasa directo a
    _split_contiguous() -- "crypto" (por defecto, sin cambios de
    comportamiento) trata cualquier dia de calendario ausente como
    hueco; "equity" usa el calendario de sesiones NYSE (trading_calendar.py)
    para no romper el tramo en fines de semana/festivos bursatiles.

    Los primeros ~200 puntos de cada tramo contiguo (ver
    _split_contiguous) no tendran sma200 (ni rsi14/atr14/volatilidad en
    sus propios primeros N puntos) por la misma razon que "hoy" tampoco
    los tendria con menos de 200 velas disponibles -- honesto, no un
    fallo."""
    ohlc = _load_ohlc(symbol, path=path)
    out = []
    for segment in _split_contiguous(ohlc, asset_type=asset_type):
        out.extend(_historical_series_segment(segment))
    return out


if __name__ == "__main__":
    out = {sym: score_asset(sym) for sym in ASSETS}
    print(json.dumps(out, indent=2, ensure_ascii=False))
