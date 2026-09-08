"""Motor de Razonamiento -- Fase 7.

Toma lo que cada motor calculo por separado (fundamental, tecnico,
macro, noticias) y construye una Tesis de Inversion por activo:
detecta CONVERGENCIAS y CONTRADICCIONES explicitas entre dominios en
vez de promediarlos en un unico numero -- es la pieza que la Fase 0
pidio desde el principio ("no quiero una simple suma ponderada") y que
hasta ahora veniamos haciendo a mano en los informes de sintesis.

Reglas de clasificacion: documentadas aqui mismo, explicitas y
auditables. No es una caja negra ni un modelo de IA generando la
conclusion libremente -- son reglas fijas sobre los datos ya
verificados de los otros motores.
"""
import json
import os
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Notas de noticias/sentimiento: en v1 solo hay cobertura cualitativa
# para XRP (Fase 4). Se declara aqui como dato explicito, no se infiere.
NEWS_FINDINGS = {
    "XRP": {
        "disponible": True,
        "contradiccion_interna": (
            "Catalizador regulatorio TODAVÍA PENDIENTE (el Comité Bancario del Senado aprobó "
            "la Clarity Act en mayo de 2026, pero el Senado pleno aplazó la votación -- "
            "'Senate Punts on Clarity Act', 7 de agosto de 2026) convive con salidas netas de "
            "ETF spot y enfriamiento de demanda on-chain (julio 2026) -- ver "
            "informes/2026-09-03_noticias_sentimiento_v2.md (corrige informes/2026-07-22_noticias_sentimiento_v1.md, "
            "que había interpretado la aprobación de comité como resuelta)"
        ),
    },
}


# --- Evidencia que cada tesis usa, y con que papel (P1, 2026-09-06) ---
#
# Hasta ahora la cobertura de una tesis era sum([True, True, True, ...]):
# tres literales. El sistema ya sabe su cobertura y su frescura reales
# (engine/contract/cobertura.py) y la tesis seguia publicando una ficticia.
#
# El papel importa tanto como el estado. Una metrica caducada NO invalida
# una tesis que no depende de ella: pe_ratio aparece en el texto del
# bear_case y ninguna regla se bifurca por su valor, asi que su retraso
# produce una advertencia, no la anulacion de la conclusion. Solo lo
# REQUERIDO puede invalidar.
#
#   REQUERIDA  una regla de clasificacion se bifurca por su valor, o
#              entra en el calculo de confidence_pct.
#   PUBLICADA  su valor aparece como cifra o afirmacion en la salida,
#              pero ninguna regla depende de el.
#   CONTEXTO   contextualiza sin ser del activo (regimen macro).
#
# Las entradas con entidad "US"/"EA" son, literalmente, la relacion
# implicita que P2 debe modelar: build_thesis() aplica el contexto macro
# de EE.UU. y de la Eurozona a los once activos por igual. Aqui queda
# escrita por primera vez de forma explicita; cuando exista el Knowledge
# Model, esta lista se sustituye por una consulta de EXPOSED_TO en vez
# de por una tabla a mano.
REQUERIDA, PUBLICADA, CONTEXTO = "REQUERIDA", "PUBLICADA", "CONTEXTO"

# (entidad, dominio, metrica, papel, reloj, campo_del_reloj, motivo)
# entidad None = el propio activo. campo_del_reloj None = fecha_dato del motor.
_MACRO_CONTEXTO = [
    ("US", "macro", "cpi_yoy_pct", CONTEXTO, "macro_us", "cpi_yoy_pct",
     "entra en el régimen macro de EE.UU. que se publica como hecho"),
    ("US", "macro", "fed_funds_pct", CONTEXTO, "macro_us", "fed_funds_pct",
     "entra en el régimen macro de EE.UU. que se publica como hecho"),
    ("US", "macro", "desempleo_pct", CONTEXTO, "macro_us", "desempleo_pct",
     "entra en el régimen macro; NO está en el Data Contract (hallazgo P1)"),
    ("US", "macro", "spread_10y2y_pct", CONTEXTO, "macro_us", "spread_10y2y_pct",
     "entra en el régimen macro; NO está en el Data Contract (hallazgo P1)"),
    ("EA", "macro", "hicp_yoy_pct", CONTEXTO, "macro_ea", "hicp_yoy_pct",
     "entra en el régimen macro de la Eurozona que se publica como hecho"),
    ("EA", "macro", "ecb_deposit_rate_pct", CONTEXTO, "macro_ea", "ecb_deposit_rate_pct",
     "entra en el régimen macro de la Eurozona que se publica como hecho"),
]

EVIDENCIA_CRYPTO = [
    (None, "fundamental", "market_cap_percentile_365d", REQUERIDA, "crypto", None,
     "percentil de capitalización: regla de convergencia/divergencia y bull_case"),
    (None, "tecnico", "confluencia_sesgo", REQUERIDA, "technical", None,
     "dirección técnica: regla de convergencia/divergencia, bear_case y base de confidence_pct"),
    (None, "fundamental", "tvl_percentile_365d", PUBLICADA, "crypto", None,
     "se publica como hecho; ninguna regla se bifurca por su valor"),
    (None, "fundamental", "fdv_mcap_ratio", PUBLICADA, "crypto", None,
     "se publica como hecho y puede generar una advertencia de dilución"),
] + _MACRO_CONTEXTO

EVIDENCIA_EQUITY = [
    (None, "tecnico", "posicion_rango_52s_pct", REQUERIDA, "equity", "precio",
     "posición en el rango de 52 semanas: regla de convergencia/divergencia"),
    (None, "tecnico", "confluencia_sesgo", REQUERIDA, "equity", "precio",
     "dirección técnica (proxy) y base de confidence_pct"),
    (None, "fundamental", "earnings_surprise_last_pct", REQUERIDA, "equity", "fundamental",
     "regla de contradicción: crecimiento anual fuerte vs. último trimestre fallado"),
    (None, "fundamental", "earnings_growth_yoy_pct", REQUERIDA, "equity", "fundamental",
     "misma regla de contradicción; NO está en el Data Contract (hallazgo P1)"),
    (None, "fundamental", "revenue_growth_yoy_pct", PUBLICADA, "equity", "fundamental",
     "se publica como hecho"),
    (None, "fundamental", "pe_ratio", PUBLICADA, "equity", "fundamental",
     "se cita en el bear_case; ninguna regla se bifurca por su valor"),
    (None, "fundamental", "peg_ratio", PUBLICADA, "equity", "fundamental",
     "solo puede generar una advertencia de valoración exigente"),
    (None, "fundamental", "analyst_target_price", PUBLICADA, "equity", "fundamental",
     "cifra citada en el bull_case"),
    (None, "fundamental", "analyst_upside_pct", PUBLICADA, "equity", "fundamental",
     "cifra citada en el bull_case"),
] + _MACRO_CONTEXTO


def _evaluar_evidencia(entradas, relojes, symbol, asset_type, hoy=None):
    """Evalua cada evidencia contra su cadencia declarada y decide la
    validez analitica de la tesis.

    VALID    todo lo REQUERIDO está dentro de su cadencia (FRESH o LAGGING).
    INVALID  algo REQUERIDO está STALE o no tiene fecha.
    UNKNOWN  algo REQUERIDO no tiene cadencia declarada — que NO es lo
             mismo que estar al día.
    """
    cadencias = _load_module("contract", "cadencias")
    hoy = hoy or datetime.datetime.now(datetime.timezone.utc).date()
    if isinstance(hoy, str):
        hoy = datetime.date.fromisoformat(hoy[:10])
    tc = cadencias._trading_calendar()

    evaluadas = []
    for entidad, dominio, metrica, papel, reloj, campo, motivo in entradas:
        fechas = relojes.get(reloj) or {}
        cruda = fechas.get(campo) if campo else fechas.get("_default")
        fecha = None
        if cruda:
            try:
                fecha = datetime.date.fromisoformat(cruda)
            except (TypeError, ValueError):
                fecha = None
        tipo = "macro" if entidad in ("US", "EA") else asset_type
        if fecha is None:
            estado, r, unidad = "UNKNOWN", None, None
        else:
            estado, r, unidad = cadencias.estado_frescura(tipo, dominio, metrica, fecha, hoy, tc)
        evaluadas.append({
            "entidad": entidad or symbol, "dominio": dominio, "metrica": metrica,
            "papel": papel, "data_as_of": fecha.isoformat() if fecha else None,
            "frescura": estado, "retraso": r, "unidad": unidad, "motivo": motivo,
        })

    requeridas = [e for e in evaluadas if e["papel"] == REQUERIDA]
    if any(e["frescura"] == "STALE" or e["data_as_of"] is None for e in requeridas):
        validez = "INVALID"
    elif any(e["frescura"] == "UNKNOWN" for e in requeridas):
        validez = "UNKNOWN"
    else:
        validez = "VALID"
    return evaluadas, validez


def _advertencias_de_frescura(evaluadas):
    """Lo que NO invalida pero el lector debe saber: una cifra caducada
    que la tesis publica igualmente."""
    fuera = []
    for e in evaluadas:
        if e["frescura"] != "STALE":
            continue
        que = {REQUERIDA: "de la que depende una regla",
               PUBLICADA: "que se publica como cifra",
               CONTEXTO: "que contextualiza"}[e["papel"]]
        fuera.append(
            f"{e['entidad']}.{e['metrica']} ({que}) tiene fecha {e['data_as_of']} — "
            f"{e['retraso']} {e['unidad']}(s) de retraso sobre su cadencia declarada.")
    return fuera


def _cobertura_real(evaluadas, news_disponible):
    """Sustituye a sum([True, True, True, ...]). Un dominio cuenta como
    cubierto solo si al menos una de sus evidencias tiene fecha."""
    dominios = {"fundamental", "tecnico", "macro", "noticias"}
    cubiertos = {e["dominio"] for e in evaluadas if e["data_as_of"]}
    if news_disponible:
        cubiertos.add("noticias")
    return len(cubiertos & dominios), len(dominios)


def _load_module(subdir, modname):
    path = os.path.join(ROOT, subdir)
    sys.path.insert(0, path)
    try:
        if modname in sys.modules:
            del sys.modules[modname]
        return __import__(modname)
    finally:
        sys.path.remove(path)


def _bucket_percentile(pct):
    if pct is None:
        return None
    if pct < 33:
        return "bajo (cerca de mínimos 365d)"
    if pct > 66:
        return "alto (cerca de máximos 365d)"
    return "medio"


def _tecnico_direccion(tecnico):
    detalle = tecnico["confluencia"]["detalle"]
    validos = [v for v in detalle.values() if v is not None]
    if not validos:
        return None
    alcistas = sum(1 for v in validos if v)
    ratio = alcistas / len(validos)
    if ratio >= 0.75:
        return "alcista"
    if ratio <= 0.25:
        return "bajista"
    return "mixto"


def build_thesis(symbol, tvl_chain, as_of=None):
    crypto_mod = _load_module("crypto", "score")
    technical_mod = _load_module("technical", "score")
    macro_mod = _load_module("macro", "score")

    fund = crypto_mod.score_asset(symbol, tvl_chain)
    tech = technical_mod.score_asset(symbol)
    macro_us = macro_mod.score_us()
    macro_ea = macro_mod.score_ea()
    news = NEWS_FINDINGS.get(symbol, {"disponible": False})

    hechos = []
    convergencias = []
    divergencias = []
    contradicciones = []
    advertencias = []

    mcap_bucket = _bucket_percentile(fund["market_cap_percentile_365d"])
    tvl_bucket = _bucket_percentile(fund["tvl_percentile_365d"])
    tech_dir = _tecnico_direccion(tech)

    if mcap_bucket:
        hechos.append(f"Market cap en percentil {fund['market_cap_percentile_365d']}% de su rango de 365 días ({mcap_bucket}).")
    if tvl_bucket:
        hechos.append(f"TVL en percentil {fund['tvl_percentile_365d']}% de su rango de 365 días ({tvl_bucket}).")
    if tech_dir:
        hechos.append(f"Confluencia técnica: {tech['confluencia']['sesgo']}.")
    if fund["fdv_mcap_ratio"] and fund["fdv_mcap_ratio"] > 1.15:
        hechos.append(f"Ratio FDV/MCap de {fund['fdv_mcap_ratio']} — dilución pendiente por encima de la media de los activos ya analizados.")
        advertencias.append("Riesgo de dilución: parte relevante de la oferta máxima aún no está en circulación.")

    # --- Regla de convergencia/divergencia fundamental vs. técnico ---
    if mcap_bucket == "bajo (cerca de mínimos 365d)" and tech_dir == "bajista":
        convergencias.append(
            "Fundamental (posición cerca de mínimos de 365d) y técnico (sesgo bajista) apuntan en la misma dirección de corto plazo."
        )
    elif mcap_bucket == "alto (cerca de máximos 365d)" and tech_dir == "alcista":
        convergencias.append(
            "Fundamental (posición cerca de máximos de 365d) y técnico (sesgo alcista) apuntan en la misma dirección."
        )
    elif mcap_bucket == "bajo (cerca de mínimos 365d)" and tech_dir == "alcista":
        divergencias.append(
            "Fundamental muestra el activo cerca de mínimos de 365d, pero el técnico ya muestra sesgo alcista de corto plazo — "
            "posible giro temprano, o rebote técnico dentro de una tendencia de fondo aún débil. No se puede distinguir con los datos actuales."
        )
    elif mcap_bucket == "alto (cerca de máximos 365d)" and tech_dir == "bajista":
        divergencias.append(
            "Fundamental muestra el activo cerca de máximos de 365d, pero el técnico ya muestra sesgo bajista — posible agotamiento de la subida."
        )

    # --- Macro como contexto, no como señal del activo ---
    hechos.append(f"Contexto macro EE.UU.: {macro_us['regimen_estimado']}.")
    hechos.append(f"Contexto macro Eurozona: {macro_ea['regimen_estimado']}.")

    # --- Noticias: contradicción interna ya detectada (solo XRP en v1) ---
    if news.get("disponible"):
        contradicciones.append(news["contradiccion_interna"])

    # --- Incidencias de datos: reducen confianza, no se ignoran ---
    if fund["posible_incidencia_datos"]:
        advertencias.append(
            f"El motor de fundamentales marcó una posible incidencia de datos para {symbol} "
            f"(Data Quality {fund['data_quality_pct']}%) — la tesis para este activo tiene menor fiabilidad que las demás."
        )

    # --- Evidencia, frescura y validez analitica (P1) ---
    evidencia, validez = _evaluar_evidencia(
        EVIDENCIA_CRYPTO,
        {"crypto": {"_default": fund.get("fecha_dato")},
         "technical": {"_default": tech.get("fecha_dato")},
         "macro_us": macro_us.get("fechas_dato", {}),
         "macro_ea": macro_ea.get("fechas_dato", {})},
        symbol, "crypto", hoy=as_of)
    advertencias += _advertencias_de_frescura(evidencia)
    cubiertos, total_dominios = _cobertura_real(evidencia, news.get("disponible", False))

    confidence_base = tech["confluencia"]["confidence_pct"]
    confidence_pct = round(confidence_base * (fund["data_quality_pct"] / 100)) if confidence_base else None
    if validez != "VALID":
        # "No hay base para calcular la confianza" no es "hay poca
        # confianza". Un numero reducido invitaria a seguir usandolo.
        confidence_pct = None

    bull_case = (
        f"Si el precio confirma el sesgo técnico actual ({tech['confluencia']['sesgo']}) y el contexto macro "
        f"deja de ser restrictivo (pausa o recortes de tipos), la posición actual cerca de "
        f"{'mínimos' if mcap_bucket == 'bajo (cerca de mínimos 365d)' else 'su rango medio/alto'} de 365d "
        f"dejaría margen de recuperación."
    )
    bear_case = (
        f"Si el entorno de tipos altos persiste y {'la señal bajista técnica se confirma' if tech_dir == 'bajista' else 'el técnico gira a bajista'}, "
        f"no hay en los datos actuales un catalizador fundamental (tokenomics/on-chain) que sostenga un rebote."
    )
    base_case = "Continuación del rango actual sin una confluencia clara en ningún sentido — es la lectura más probable con los datos de hoy, según el propio motor técnico."

    return {
        "activo": symbol,
        "fecha": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "hechos": hechos,
        "convergencias": convergencias,
        "divergencias": divergencias,
        "contradicciones": contradicciones,
        "advertencias": advertencias,
        "bull_case": bull_case,
        "base_case": base_case,
        "bear_case": bear_case,
        "factores_que_invalidarian_la_tesis": [
            "Un cambio de régimen macro (la Fed o el BCE giran a recortes agresivos) alteraría el contexto que sostiene la lectura actual.",
            "Una corrección posterior de los datos marcados con posible incidencia (ver advertencias) cambiaría la lectura fundamental.",
        ],
        "confidence_pct": confidence_pct,
        "validez_evidencia": validez,
        "evidencia": evidencia,
        "cobertura_dominios": f"{cubiertos}/{total_dominios}",
        "nota_metodologica": "Reglas de clasificación fijas y documentadas en engine/reasoning/thesis.py — no es una conclusión generada libremente.",
    }


def build_thesis_equity(symbol, as_of=None):
    """Version del motor de razonamiento para acciones (Fase 2, Bloque B).

    A diferencia de las criptomonedas, aqui NO hay un motor tecnico
    independiente (RSI/MACD/ATR) todavia -- engine/equity/score.py ya
    calcula una confluencia simplificada (precio vs SMA50/SMA200 +
    sorpresa del ultimo trimestre) que se reutiliza aqui como proxy del
    dominio tecnico, etiquetado explicitamente como tal. Tampoco hay
    cobertura de noticias para acciones en v1.
    """
    equity_mod = _load_module("equity", "score")
    macro_mod = _load_module("macro", "score")

    fund = equity_mod.score_asset(symbol)
    macro_us = macro_mod.score_us()
    macro_ea = macro_mod.score_ea()

    hechos = []
    convergencias = []
    divergencias = []
    contradicciones = []
    advertencias = []

    pos_bucket = _bucket_percentile(fund["posicion_rango_52s_pct"])
    tech_dir = _tecnico_direccion(fund)  # reutiliza la misma regla de umbral 75%/25%

    hechos.append(f"Posición en el rango de 52 semanas: {fund['posicion_rango_52s_pct']}% ({pos_bucket}).")
    hechos.append(f"Confluencia técnica (proxy SMA50/SMA200 + sorpresa de resultados): {fund['confluencia']['sesgo']}.")
    hechos.append(f"Crecimiento de ingresos interanual: {fund['revenue_growth_yoy_pct']}% · Crecimiento de BPA interanual: {fund['earnings_growth_yoy_pct']}%.")
    hechos.append(f"Contexto macro EE.UU.: {macro_us['regimen_estimado']}.")
    hechos.append(f"Contexto macro Eurozona: {macro_ea['regimen_estimado']}.")

    if fund["peg_ratio"] and fund["peg_ratio"] > 2:
        advertencias.append(f"PEG de {fund['peg_ratio']} — valoración exigente en relación a su crecimiento esperado.")

    # --- convergencia/divergencia posición 52s vs. confluencia tecnica ---
    if pos_bucket == "bajo (cerca de mínimos 365d)" and tech_dir == "bajista":
        convergencias.append("Posición cerca de mínimos de 52 semanas y confluencia técnica bajista apuntan en la misma dirección.")
    elif pos_bucket == "alto (cerca de máximos 365d)" and tech_dir == "alcista":
        convergencias.append("Posición cerca de máximos de 52 semanas y confluencia técnica alcista apuntan en la misma dirección.")
    elif pos_bucket == "bajo (cerca de mínimos 365d)" and tech_dir == "alcista":
        divergencias.append("Posición cerca de mínimos de 52 semanas pero confluencia técnica ya alcista — posible giro temprano, sin poder confirmarlo con los datos actuales.")
    elif pos_bucket == "alto (cerca de máximos 365d)" and tech_dir == "bajista":
        divergencias.append("Posición cerca de máximos de 52 semanas pero confluencia técnica ya bajista — posible agotamiento de la subida.")

    # --- contradiccion especifica de acciones: crecimiento anual fuerte vs. ultimo trimestre fallado ---
    sorpresa = fund["sorpresa_resultados"]
    if fund["earnings_growth_yoy_pct"] is not None and fund["earnings_growth_yoy_pct"] > 20 and sorpresa["ultima_sorpresa_pct"] is not None and sorpresa["ultima_sorpresa_pct"] < 0:
        contradicciones.append(
            f"El crecimiento de BPA interanual (+{fund['earnings_growth_yoy_pct']}%) parece fuerte, pero el último trimestre "
            f"reportado falló el consenso de analistas ({sorpresa['ultima_sorpresa_pct']}%) — la cifra anual puede estar "
            f"dominada por una base de comparación baja, no por el momento actual."
        )

    # --- Evidencia, frescura y validez analitica (P1) ---
    evidencia, validez = _evaluar_evidencia(
        EVIDENCIA_EQUITY,
        {"equity": fund.get("fechas_dato", {}),
         "macro_us": macro_us.get("fechas_dato", {}),
         "macro_ea": macro_ea.get("fechas_dato", {})},
        symbol, "equity", hoy=as_of)
    advertencias += _advertencias_de_frescura(evidencia)
    cubiertos, total_dominios = _cobertura_real(evidencia, False)

    validos_conf = [v for v in fund["confluencia"]["detalle"].values() if v is not None]
    confidence_base = round(len(validos_conf) / 3 * 100) if validos_conf else None
    confidence_pct = round(confidence_base * (fund["data_quality_pct"] / 100)) if confidence_base else None
    if validez != "VALID":
        confidence_pct = None

    upside = fund["analistas"]["upside_pct"]
    bull_case = (
        f"Si se confirma la confluencia técnica actual ({fund['confluencia']['sesgo']}) y el consenso de analistas "
        f"(objetivo {fund['analistas']['precio_objetivo']}, {upside}% de recorrido) se mantiene, hay margen de subida "
        f"sin necesidad de una revisión al alza de estimaciones."
    )
    bear_case = (
        f"Si el crecimiento de ingresos/BPA se desacelera más de lo que ya muestra el dato interanual, o el mercado "
        f"deja de pagar el múltiplo actual (P/E {fund['pe_ratio']}), el precio objetivo de analistas quedaría en revisión a la baja."
    )
    base_case = "Continuación de la tendencia de precio actual sin sorpresas — es la lectura más probable con los datos de hoy si no cambia el contexto macro."

    return {
        "activo": symbol,
        "fecha": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "hechos": hechos,
        "convergencias": convergencias,
        "divergencias": divergencias,
        "contradicciones": contradicciones,
        "advertencias": advertencias,
        "bull_case": bull_case,
        "base_case": base_case,
        "bear_case": bear_case,
        "factores_que_invalidarian_la_tesis": [
            "Una revisión a la baja del precio objetivo o del consenso de analistas cambiaría la lectura de valoración.",
            "Un cambio de régimen macro (Fed/BCE) alteraría el contexto que sostiene la lectura actual.",
            "Sin cobertura de noticias para acciones en esta v1 — un evento no capturado aquí podría invalidar la tesis sin que el sistema lo detecte.",
        ],
        "confidence_pct": confidence_pct,
        "validez_evidencia": validez,
        "evidencia": evidencia,
        "cobertura_dominios": f"{cubiertos}/{total_dominios}",
        "nota_metodologica": "Reglas de clasificación fijas y documentadas en engine/reasoning/thesis.py — no es una conclusión generada libremente. Dominio técnico es un proxy simplificado, no el motor técnico completo de engine/technical/.",
    }


ASSETS_TVL = {"BTC": None, "ETH": "Ethereum", "ADA": "Cardano", "SOL": "Solana",
              "DOT": "Polkadot", "XRP": None}
EQUITY_ASSETS = ["IBM", "NVDA", "XOM"]

if __name__ == "__main__":
    out = {sym: build_thesis(sym, chain) for sym, chain in ASSETS_TVL.items()}
    out.update({sym: build_thesis_equity(sym) for sym in EQUITY_ASSETS})
    print(json.dumps(out, indent=2, ensure_ascii=False))
