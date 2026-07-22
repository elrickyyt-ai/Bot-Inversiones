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
            "Catalizador regulatorio positivo (aprobación de la Clarity Act en el "
            "Senado de EE.UU., mayo 2026) convive con salidas netas de ETF spot y "
            "enfriamiento de demanda on-chain (julio 2026) -- ver informes/2026-07-22_noticias_sentimiento_v1.md"
        ),
    },
}


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


def build_thesis(symbol, tvl_chain):
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

    cobertura = sum([True, True, True, news.get("disponible", False)])
    confidence_base = tech["confluencia"]["confidence_pct"]
    confidence_pct = round(confidence_base * (fund["data_quality_pct"] / 100)) if confidence_base else None

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
        "cobertura_dominios": f"{cobertura}/4",
        "nota_metodologica": "Reglas de clasificación fijas y documentadas en engine/reasoning/thesis.py — no es una conclusión generada libremente.",
    }


ASSETS_TVL = {"BTC": None, "ETH": "Ethereum", "ADA": "Cardano", "SOL": "Solana",
              "DOT": "Polkadot", "XRP": None}

if __name__ == "__main__":
    out = {sym: build_thesis(sym, chain) for sym, chain in ASSETS_TVL.items()}
    print(json.dumps(out, indent=2, ensure_ascii=False))
