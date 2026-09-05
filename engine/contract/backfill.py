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
    python3 engine/contract/backfill.py --equity-technical
    python3 engine/contract/backfill.py --gaps        # solo diagnostico, no escribe nada
"""
import json
import os
import sys
from datetime import datetime

from adapters import adapt_macro_backfill, adapt_crypto_backfill, adapt_technical_backfill
import storage
from build import _write_metric_rows, CRYPTO_ASSETS, EQUITY_ASSETS, DATA_DIR

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "technical"))
from trading_calendar import sessions_skipped_between  # noqa: E402


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


def detect_technical_gaps(symbol, asset_type="crypto"):
    """Diagnostico (2026-09-04; generalizado a acciones el mismo dia,
    Bloque 4): lee el Data Contract (history/ + incoming/, migracion
    2026-09-05) y devuelve los huecos
    REALES de sesion en la serie 'precio' (domain=tecnico) ya escrita --
    (fecha_antes, fecha_despues, dias_naturales) para cada par de fechas
    consecutivas donde faltan una o mas sesiones de trading esperadas
    (ver engine/technical/trading_calendar.py). Para asset_type="crypto"
    (por defecto) cualquier dia ausente cuenta -- para asset_type=
    "equity" un fin de semana o festivo bursatil NO cuenta como hueco
    (antes de este cambio, este diagnostico reportaba ~1500 "huecos"
    falsos para una accion con decadas de historico, uno por cada fin de
    semana/festivo -- util para cripto, inutil para acciones). Es la
    misma nocion de "que ya tenemos" que usa adapters.py::
    _existing_technical_dates() para decidir que backfillear -- este es
    el lado de REPORTE, reusable para detectar huecos futuros (ej. si el
    cron diario falla varios dias seguidos) sin tener que volver a
    razonar la logica cada vez."""
    fechas = sorted(storage.technical_dates(symbol))
    gaps = []
    for i in range(1, len(fechas)):
        d1 = datetime.strptime(fechas[i - 1], "%Y-%m-%d").date()
        d2 = datetime.strptime(fechas[i], "%Y-%m-%d").date()
        if sessions_skipped_between(d1, d2, asset_type) > 0:
            gaps.append((fechas[i - 1], fechas[i], (d2 - d1).days))
    return gaps


def report_gaps():
    for symbol in CRYPTO_ASSETS:
        gaps = detect_technical_gaps(symbol, asset_type="crypto")
        if not gaps:
            print(f"{symbol}: sin huecos")
            continue
        for antes, despues, dias in gaps:
            print(f"{symbol}: hueco {antes} -> {despues} ({dias} días)")
    for symbol in EQUITY_ASSETS:
        gaps = detect_technical_gaps(symbol, asset_type="equity")
        if not gaps:
            print(f"{symbol}: sin huecos")
            continue
        for antes, despues, dias in gaps:
            print(f"{symbol}: hueco {antes} -> {despues} ({dias} días)")


def _backfill_technical_generic(symbols, asset_type, source, currency):
    """Requiere el fetcher de OHLC correspondiente ya ejecutado (los
    ficheros _ohlc_backfill.json en _data/ son gitignored, no se
    descargan aqui). Si un activo no tiene ese fichero todavia,
    adapt_technical_backfill() devuelve [] -- no es un error, solo no hay
    nada que escribir para ese activo en esta pasada. adapt_technical_
    backfill() tambien devuelve [] cuando el fichero SI existe pero todo
    lo que contiene ya esta en el Data Contract (idempotencia real, no
    ausencia de datos) -- se distingue aqui para no confundir ambos casos
    en el mensaje."""
    cache_dir = os.path.join(os.path.dirname(DATA_DIR), "engine", "technical", "_data")
    for symbol in symbols:
        cache_path = os.path.join(cache_dir, f"{symbol}_ohlc_backfill.json")
        rows = adapt_technical_backfill(symbol, asset_type=asset_type, source=source, currency=currency)
        if not rows:
            if os.path.exists(cache_path):
                print(f"{symbol}: 0 filas nuevas (todo lo que hay en la caché ya está en el Data Contract)")
            else:
                print(f"{symbol}: sin fichero de backfill todavia")
            continue
        total, added, skipped = _write_metric_rows(symbol, rows)
        print(f"{symbol}: {total} filas históricas ({added} nuevas, {skipped} ya existían)")


def backfill_technical():
    """Cripto -- fetch_backfill.py (Coinbase, EUR)."""
    _backfill_technical_generic(CRYPTO_ASSETS, asset_type="crypto", source="Coinbase", currency="EUR")


def backfill_equity_technical():
    """Acciones (2026-09-04, Bloque 4) -- fetch_backfill_equity.py
    (Yahoo Finance, USD). Mismo mecanismo que backfill_technical(),
    parametrizado -- ninguna logica nueva de escritura."""
    _backfill_technical_generic(EQUITY_ASSETS, asset_type="equity", source="Yahoo Finance", currency="USD")


if __name__ == "__main__":
    if "--macro" in sys.argv:
        backfill_macro()
    elif "--tvl" in sys.argv:
        backfill_tvl()
    elif "--technical" in sys.argv:
        backfill_technical()
    elif "--equity-technical" in sys.argv:
        backfill_equity_technical()
    elif "--gaps" in sys.argv:
        report_gaps()
    else:
        print("Uso: python3 engine/contract/backfill.py [--macro|--tvl|--technical|--equity-technical|--gaps]")
        sys.exit(1)
