"""Clasificacion de regimen macro -- Fase 5, dominio transversal de la
Fase 0 (no compite con los demas motores, los contextualiza).

Metodologia v1: heuristica explicita de confluencia entre senales (mismo
principio de diseno que el motor tecnico), NUNCA un unico indicador. Se
documenta la regla exacta para que sea auditable, no una caja negra.
"""
import json
import os
import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "_data")


def _load(name):
    with open(f"{DATA_DIR}/{name}.json") as f:
        return json.load(f)


def _yoy(series):
    latest_date, latest_val = series[-1]
    target = datetime.date.fromisoformat(latest_date) - datetime.timedelta(days=365)
    best = None
    for d, v in series:
        if datetime.date.fromisoformat(d) <= target:
            best = (d, v)
    if not best:
        return None
    return {
        "fecha": latest_date, "valor_indice": latest_val,
        "fecha_hace_1a": best[0], "valor_indice_hace_1a": best[1],
        "yoy_pct": round((latest_val / best[1] - 1) * 100, 2),
    }


def _yoy_series(series):
    """Serie completa de variacion interanual -- misma formula que
    _yoy(), aplicada a CADA punto de la serie (no solo al ultimo), para
    el backfill historico (2026-09-04). Devuelve [(fecha, yoy_pct), ...]
    solo para las fechas donde existe un valor de ~12 meses antes
    disponible en la propia serie."""
    out = []
    for i, (d, v) in enumerate(series):
        target = datetime.date.fromisoformat(d) - datetime.timedelta(days=365)
        base = None
        for d2, v2 in series[:i]:
            if datetime.date.fromisoformat(d2) <= target:
                base = v2
        if base:
            out.append((d, round((v / base - 1) * 100, 2)))
    return out


def historical_series_us():
    """Backfill (2026-09-04): serie historica completa de las metricas
    macro de EE.UU. que ya expone el Data Contract -- NO el
    regimen_estimado/señales de score_us() (esa es una sintesis de
    "hoy", no un dato historico por fecha). Devuelve
    [(metric, fecha, valor), ...]. Misma formula de YoY que score_us(),
    aplicada a toda la historia ya descargada de FRED en vez de solo al
    ultimo punto."""
    cpi = _load("us_cpi")
    fedfunds = _load("us_fedfunds")
    rows = [("cpi_yoy_pct", d, v) for d, v in _yoy_series(cpi)]
    rows += [("fed_funds_pct", d, v) for d, v in fedfunds]
    return rows


def historical_series_ea():
    """Backfill (2026-09-04): equivalente a historical_series_us() para
    la Eurozona."""
    hicp = _load("ea_hicp")
    ecb = _load("ea_ecb_rate")
    rows = [("hicp_yoy_pct", d, v) for d, v in _yoy_series(hicp)]
    rows += [("ecb_deposit_rate_pct", d, v) for d, v in ecb]
    return rows


def _trend(series, lookback=6, flat_threshold=0.05):
    """Compara el valor actual con el de `lookback` observaciones atras."""
    if len(series) < lookback + 1:
        return "datos insuficientes"
    now = series[-1][1]
    then = series[-1 - lookback][1]
    diff = now - then
    if diff > flat_threshold:
        return "subiendo"
    if diff < -flat_threshold:
        return "bajando"
    return "estable"


def score_us():
    cpi_yoy = _yoy(_load("us_cpi"))["yoy_pct"]
    fedfunds = _load("us_fedfunds")
    fedfunds_trend = _trend(fedfunds, lookback=6, flat_threshold=0.1)
    unrate = _load("us_unemployment")
    unrate_trend = _trend(unrate, lookback=6, flat_threshold=0.1)
    spread = _load("us_10y2y_spread")
    spread_now = spread[-1][1]
    curva_invertida = spread_now < 0

    señales = {
        "inflacion_por_encima_objetivo_2pct": cpi_yoy > 2.5,
        "tipos_en_subida_o_altos_y_estables": fedfunds_trend in ("subiendo", "estable") and fedfunds[-1][1] > 3.0,
        "desempleo_deteriorandose": unrate_trend == "subiendo",
        "curva_invertida": curva_invertida,
    }

    if señales["desempleo_deteriorandose"] and señales["curva_invertida"]:
        regimen = "posible recesión (desempleo subiendo + curva invertida)"
    elif señales["inflacion_por_encima_objetivo_2pct"] and not señales["desempleo_deteriorandose"] and not curva_invertida:
        regimen = "expansión con inflación pegajosa (banco central en pausa vigilante)"
    elif not señales["inflacion_por_encima_objetivo_2pct"] and not señales["desempleo_deteriorandose"]:
        regimen = "expansión estable / recuperación"
    else:
        regimen = "mixto — sin confluencia clara"

    return {
        "region": "EE.UU.",
        "fecha_dato": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "cpi_yoy_pct": cpi_yoy,
        "fed_funds_pct": fedfunds[-1][1],
        "fed_funds_tendencia_6m": fedfunds_trend,
        "desempleo_pct": unrate[-1][1],
        "desempleo_tendencia_6m": unrate_trend,
        "spread_10y2y_pct": spread_now,
        "curva_invertida": curva_invertida,
        "señales": señales,
        "regimen_estimado": regimen,
        "confidence_pct": round(sum(1 for v in señales.values() if v is not None) / len(señales) * 100),
        "data_quality_pct": 85,
    }


def _rate_n_days_ago(series, days):
    latest_date = datetime.date.fromisoformat(series[-1][0])
    target = latest_date - datetime.timedelta(days=days)
    best = None
    for d, v in series:
        if datetime.date.fromisoformat(d) <= target:
            best = v
    return best


def score_ea():
    hicp_yoy = _yoy(_load("ea_hicp"))["yoy_pct"]
    ecb = _load("ea_ecb_rate")
    rate_now = ecb[-1][1]
    rate_3m = _rate_n_days_ago(ecb, 90)
    rate_12m = _rate_n_days_ago(ecb, 365)

    # Pivote: subio en los ultimos 3 meses tras haber estado plano/bajando
    # en el año previo a esos 3 meses.
    subio_recientemente = rate_3m is not None and rate_now > rate_3m
    venia_de_plano_o_bajando = rate_12m is not None and rate_3m is not None and rate_3m <= rate_12m
    pivote_reciente = subio_recientemente and venia_de_plano_o_bajando

    if pivote_reciente:
        regimen = (
            f"pivote hawkish reciente: el BCE subió de {rate_3m:.2f}% a {rate_now:.2f}% "
            f"en los últimos ~3 meses, tras mantenerlo plano o a la baja el año anterior "
            f"({rate_12m:.2f}% hace 12 meses)"
        )
    elif subio_recientemente:
        regimen = f"tipos al alza ({rate_3m:.2f}% → {rate_now:.2f}% en ~3 meses), continuación de una tendencia ya en marcha"
    else:
        regimen = "sin subida de tipos reciente"

    return {
        "region": "Eurozona",
        "fecha_dato": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "hicp_yoy_pct": hicp_yoy,
        "ecb_deposit_rate_pct": rate_now,
        "ecb_rate_hace_3m_pct": rate_3m,
        "ecb_rate_hace_12m_pct": rate_12m,
        "pivote_hawkish_reciente": pivote_reciente,
        "regimen_estimado": regimen,
        "confidence_pct": 60,  # solo 2 señales, sin desempleo/curva de tipos en v1
        "data_quality_pct": 70,
        "gap": "sin serie de desempleo ni curva de tipos de la Eurozona actualizada y gratuita encontrada en esta v1",
    }


if __name__ == "__main__":
    print(json.dumps({"EE.UU.": score_us(), "Eurozona": score_ea()}, indent=2, ensure_ascii=False))
