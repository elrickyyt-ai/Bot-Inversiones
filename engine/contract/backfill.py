"""Backfill historico del Data Contract -- FASE DISTINTA de build.py
(2026-09-04, ver informes/2026-09-04_estrategia_backfill_historico.md).

build.py es INCREMENTAL: cada ejecucion (el cron diario) anade solo
"hoy". Este script es BACKFILL: recorre TODA la historia ya disponible
de una fuente y la escribe de una vez -- se ejecuta una vez, o de forma
ocasional si mas adelante se amplia la profundidad de alguna fuente.
Nunca lo ejecuta el cron diario.

Ambos escriben por la MISMA funcion idempotente
(build.py::_write_metric_rows, clave asset_id+domain+metric+data_as_of+
source) -- nunca pueden duplicar ni chocar entre si, sin necesidad de
ninguna coordinacion especial entre los dos procesos.

Uso:
    python3 engine/contract/backfill.py --macro
    python3 engine/contract/backfill.py --tvl
    python3 engine/contract/backfill.py --technical
    python3 engine/contract/backfill.py --gaps        # solo diagnostico, no escribe nada
"""
import json
import os
import sys
from datetime import datetime

from adapters import adapt_macro_backfill, adapt_crypto_backfill, adapt_technical_backfill
from build import _write_metric_rows, CRYPTO_ASSETS, DATA_DIR


def backfill_macro():
    rows = adapt_macro_backfill()
    by_region = {}
    for row in rows:
        by_region.setdefault(row["asset_id"], []).append(row)
    for region, region_rows in by_region.items():
        total, added, skipped = _write_metric_rows(region, region_rows)
        print(f"{region}: {total} filas históricas ({added} nuevas, {skipped} ya existían)")


def backfill_tvl():
    """BTC/XRP no tienen cadena de TVL (ver CRYPTO_ASSETS) -- se omiten,
    no es un error."""
    for symbol, tvl_chain in CRYPTO_ASSETS.items():
        if not tvl_chain:
            continue
        rows = adapt_crypto_backfill(symbol, tvl_chain)
        total, added, skipped = _write_metric_rows(symbol, rows)
        print(f"{symbol}: {total} filas históricas ({added} nuevas, {skipped} ya existían)")


def detect_technical_gaps(symbol):
    """Diagnostico (2026-09-04): lee data/metrics/{symbol}.json y
    devuelve los huecos de calendario reales en la serie 'precio'
    (domain=tecnico) ya escrita -- (fecha_antes, fecha_despues, dias)
    para cada par de fechas consecutivas con mas de 1 dia de diferencia.
    Es la misma nocion de "que ya tenemos" que usa
    adapters.py::_existing_technical_dates() para decidir que backfillear
    -- este es el lado de REPORTE, reusable para detectar huecos futuros
    (ej. si el cron diario falla varios dias seguidos) sin tener que
    volver a razonar la logica cada vez."""
    path = os.path.join(DATA_DIR, "metrics", f"{symbol}.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    fechas = sorted({r["data_as_of"] for r in rows if r.get("domain") == "tecnico" and r.get("metric") == "precio"})
    gaps = []
    for i in range(1, len(fechas)):
        d1 = datetime.strptime(fechas[i - 1], "%Y-%m-%d")
        d2 = datetime.strptime(fechas[i], "%Y-%m-%d")
        dias = (d2 - d1).days
        if dias > 1:
            gaps.append((fechas[i - 1], fechas[i], dias))
    return gaps


def report_gaps():
    for symbol in CRYPTO_ASSETS:
        gaps = detect_technical_gaps(symbol)
        if not gaps:
            print(f"{symbol}: sin huecos")
            continue
        for antes, despues, dias in gaps:
            print(f"{symbol}: hueco {antes} -> {despues} ({dias} días)")


def backfill_technical():
    """Requiere engine/technical/fetch_backfill.py ya ejecutado (los
    ficheros _ohlc_backfill.json en _data/ son gitignored, no se
    descargan aqui). Si un activo no tiene ese fichero todavia,
    adapt_technical_backfill() devuelve [] -- no es un error, solo no hay
    nada que escribir para ese activo en esta pasada. adapt_technical_
    backfill() tambien devuelve [] cuando el fichero SI existe pero todo
    lo que contiene ya esta en el Data Contract (idempotencia real, no
    ausencia de datos) -- se distingue aqui para no confundir ambos casos
    en el mensaje."""
    cache_dir = os.path.join(os.path.dirname(DATA_DIR), "engine", "technical", "_data")
    for symbol in CRYPTO_ASSETS:
        cache_path = os.path.join(cache_dir, f"{symbol}_ohlc_backfill.json")
        rows = adapt_technical_backfill(symbol)
        if not rows:
            if os.path.exists(cache_path):
                print(f"{symbol}: 0 filas nuevas (todo lo que hay en la caché ya está en el Data Contract)")
            else:
                print(f"{symbol}: sin fichero de backfill todavia (fetch_backfill.py)")
            continue
        total, added, skipped = _write_metric_rows(symbol, rows)
        print(f"{symbol}: {total} filas históricas ({added} nuevas, {skipped} ya existían)")


if __name__ == "__main__":
    if "--macro" in sys.argv:
        backfill_macro()
    elif "--tvl" in sys.argv:
        backfill_tvl()
    elif "--technical" in sys.argv:
        backfill_technical()
    elif "--gaps" in sys.argv:
        report_gaps()
    else:
        print("Uso: python3 engine/contract/backfill.py [--macro|--tvl|--technical|--gaps]")
        sys.exit(1)
