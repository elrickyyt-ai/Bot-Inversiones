"""Thesis Ledger -- Fase 0, punto 21.

Registra cada tesis generada con fecha y precio del momento, para poder
comprobar mas adelante si acerto -- el mismo mecanismo de memoria
historica que ya aplicamos a personas_influyentes.json (Fase 4), ahora
aplicado al propio sistema. Sin esto, todo lo construido es una caja de
herramientas sofisticada de la que no sabemos si es buena.

Append-only: nunca se reescribe una entrada ya registrada. Cuando llega
su horizonte de evaluacion, se completa el campo "evaluacion" de esa
misma entrada (no se crea una entrada nueva ni se borra la original) --
es anadir el dato que faltaba, no reescribir historia.

Umbral de "movimiento significativo": en vez de un numero arbitrario
igual para todos los activos, se deriva de la volatilidad historica
anualizada que ya calcula el motor tecnico (distinta por activo -- ADA
es mucho mas volatil que BTC), escalada al horizonte de evaluacion con
la regla estandar de escala por raiz del tiempo:

    umbral_pct = volatilidad_anualizada_pct * sqrt(horizonte_dias / 365)

Con eso, el veredicto (se cumplio el bull/base/bear case) es objetivo y
auditable, no una impresion subjetiva de si "parecio que acerto".
"""
import json
import math
import os
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger")

HORIZONTE_DIAS_DEFECTO = 90


def _load_module(subdir, modname):
    path = os.path.join(ROOT, subdir)
    sys.path.insert(0, path)
    try:
        if modname in sys.modules:
            del sys.modules[modname]
        return __import__(modname)
    finally:
        sys.path.remove(path)


def _ledger_path(symbol):
    return os.path.join(LEDGER_DIR, f"{symbol}.jsonl")


def record_thesis(symbol, tvl_chain, horizonte_dias=HORIZONTE_DIAS_DEFECTO):
    """Genera la tesis de hoy y la anade como una entrada nueva al ledger
    del activo, con el precio actual y el umbral de evaluacion."""
    reasoning_mod = _load_module("reasoning", "thesis")
    technical_mod = _load_module("technical", "score")

    tesis = reasoning_mod.build_thesis(symbol, tvl_chain)
    tecnico = technical_mod.score_asset(symbol)

    vol = tecnico["volatilidad_hist_30d_anualizada_pct"]
    umbral_pct = round(vol * math.sqrt(horizonte_dias / 365), 1) if vol else None

    entrada = {
        "id": f"{symbol}_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "activo": symbol,
        "fecha_registro": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "precio_en_el_momento": tecnico["precio"],
        "horizonte_evaluacion_dias": horizonte_dias,
        "umbral_movimiento_significativo_pct": umbral_pct,
        "umbral_metodologia": "volatilidad histórica anualizada (30d) escalada por raíz del tiempo al horizonte de evaluación",
        "tesis": tesis,
        "evaluacion": None,
    }

    os.makedirs(LEDGER_DIR, exist_ok=True)
    with open(_ledger_path(symbol), "a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    return entrada


def _read_entries(symbol):
    path = _ledger_path(symbol)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _rewrite_entries(symbol, entries):
    with open(_ledger_path(symbol), "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def evaluate_pending(symbol, precio_actual, hoy=None):
    """Completa el campo 'evaluacion' de las entradas cuyo horizonte ya
    se cumplió. No inventa evaluaciones para entradas que aún no han
    llegado a su fecha."""
    hoy = hoy or datetime.date.today()
    entries = _read_entries(symbol)
    evaluadas = []
    for e in entries:
        if e["evaluacion"] is not None:
            continue
        fecha_registro = datetime.date.fromisoformat(e["fecha_registro"])
        dias_transcurridos = (hoy - fecha_registro).days
        if dias_transcurridos < e["horizonte_evaluacion_dias"]:
            continue

        variacion_pct = round((precio_actual - e["precio_en_el_momento"]) / e["precio_en_el_momento"] * 100, 2)
        umbral = e["umbral_movimiento_significativo_pct"]
        if umbral is not None and variacion_pct > umbral:
            veredicto = "bull_case"
        elif umbral is not None and variacion_pct < -umbral:
            veredicto = "bear_case"
        else:
            veredicto = "base_case"

        e["evaluacion"] = {
            "fecha_evaluacion": hoy.isoformat(),
            "dias_transcurridos": dias_transcurridos,
            "precio_en_evaluacion": precio_actual,
            "variacion_pct": variacion_pct,
            "veredicto": veredicto,
        }
        evaluadas.append(e)

    if evaluadas:
        _rewrite_entries(symbol, entries)
    return evaluadas


if __name__ == "__main__":
    ASSETS_TVL = {"BTC": None, "ETH": "Ethereum", "ADA": "Cardano", "SOL": "Solana",
                  "DOT": "Polkadot", "XRP": None}
    for sym, chain in ASSETS_TVL.items():
        e = record_thesis(sym, chain)
        print(f"{sym}: registrada {e['id']} — precio {e['precio_en_el_momento']}, "
              f"umbral ±{e['umbral_movimiento_significativo_pct']}% a {e['horizonte_evaluacion_dias']} días")
