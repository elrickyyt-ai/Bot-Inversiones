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
"""
import sys

from adapters import adapt_macro_backfill, adapt_crypto_backfill
from build import _write_metric_rows, CRYPTO_ASSETS


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


if __name__ == "__main__":
    if "--macro" in sys.argv:
        backfill_macro()
    elif "--tvl" in sys.argv:
        backfill_tvl()
    else:
        print("Uso: python3 engine/contract/backfill.py [--macro|--tvl]")
        sys.exit(1)
