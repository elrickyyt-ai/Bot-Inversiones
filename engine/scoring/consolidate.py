"""Scoring consolidado -- Fase 6.

Objetivo (Fase 0, punto 16 y Paso 2.1): normalizar y reunir en una sola
ficha por activo lo que cada motor ya calculo por separado, con su
propio Confidence y Data Quality -- SIN colapsarlo en un unico numero
de "compra/venta". Esa sintesis con deteccion de contradicciones es
trabajo de la Fase 7 (Motor de Razonamiento), todavia no construida.
Mezclar aqui seria repetir el error que la propia Fase 0 senalo:
"no quiero una simple suma ponderada".

Cada dominio aporta lo que tiene, con su propia confianza. Cuando un
dominio no tiene dato de un activo concreto, se marca explicitamente
como no disponible -- nunca se rellena con un valor inventado.
"""
import json
import os
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module(subdir, modname):
    path = os.path.join(ROOT, subdir)
    sys.path.insert(0, path)
    try:
        if modname in sys.modules:
            del sys.modules[modname]
        module = __import__(modname)
    finally:
        sys.path.remove(path)
    return module


def build_scorecard(symbol, tvl_chain):
    crypto_mod = _load_module("crypto", "score")
    technical_mod = _load_module("technical", "score")
    macro_mod = _load_module("macro", "score")

    fundamental = crypto_mod.score_asset(symbol, tvl_chain)
    tecnico = technical_mod.score_asset(symbol)
    macro_us = macro_mod.score_us()
    macro_ea = macro_mod.score_ea()

    dominios = {
        "fundamental_tokenomics": {
            "disponible": True,
            "confidence_pct": None,  # el motor de cripto no calcula confidence explicito v1, solo data quality
            "data_quality_pct": fundamental["data_quality_pct"],
            "resumen": {
                "market_cap_percentil_365d": fundamental["market_cap_percentile_365d"],
                "tvl_percentil_365d": fundamental["tvl_percentile_365d"],
                "fdv_mcap_ratio": fundamental["fdv_mcap_ratio"],
            },
            "advertencia": "posible incidencia de datos" if fundamental["posible_incidencia_datos"] else None,
        },
        "tecnico": {
            "disponible": True,
            "confidence_pct": tecnico["confluencia"]["confidence_pct"],
            "data_quality_pct": None,  # fuente unica (Kraken); no se ha definido techo propio todavia
            "resumen": {
                "sesgo": tecnico["confluencia"]["sesgo"],
                "posicion_rango_90d_pct": tecnico["posicion_rango_90d_pct"],
                "rsi14": tecnico["rsi14"],
            },
        },
        "macro_contexto": {
            "disponible": True,
            "nota": "contexto transversal, no especifico del activo (Fase 0: el macro contextualiza, no compite)",
            "eeuu_regimen": macro_us["regimen_estimado"],
            "eurozona_regimen": macro_ea["regimen_estimado"],
        },
        "noticias_sentimiento": {
            "disponible": symbol == "XRP",  # unico activo con cobertura en la v1 de la Fase 4
            "nota": "ver informes/2026-07-22_noticias_sentimiento_v1.md" if symbol == "XRP" else "sin cobertura todavia para este activo",
        },
    }

    # Confidence y Data Quality globales: media de los dominios que SI
    # tienen el dato, nunca inventando el que falta. Se declara cuantos
    # de los 4 dominios tienen cobertura, para que la cifra global no
    # oculte cuanto falta.
    confs = [d["confidence_pct"] for d in dominios.values() if isinstance(d, dict) and d.get("confidence_pct") is not None]
    dqs = [d["data_quality_pct"] for d in dominios.values() if isinstance(d, dict) and d.get("data_quality_pct") is not None]
    cobertura = sum(1 for d in dominios.values() if d.get("disponible"))

    return {
        "activo": symbol,
        "fecha": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "dominios": dominios,
        "cobertura_dominios": f"{cobertura}/4",
        "confidence_global_pct": round(sum(confs) / len(confs)) if confs else None,
        "data_quality_global_pct": round(sum(dqs) / len(dqs)) if dqs else None,
        "nota_metodologica": (
            "Esto es una ficha consolidada, NO una senal de compra/venta. "
            "La deteccion de convergencias y contradicciones entre dominios "
            "es trabajo de la Fase 7 (Motor de Razonamiento), todavia no construida."
        ),
    }


ASSETS_TVL = {"BTC": None, "ETH": "Ethereum", "ADA": "Cardano", "SOL": "Solana",
              "DOT": "Polkadot", "XRP": None}

if __name__ == "__main__":
    out = {sym: build_scorecard(sym, chain) for sym, chain in ASSETS_TVL.items()}
    print(json.dumps(out, indent=2, ensure_ascii=False))
