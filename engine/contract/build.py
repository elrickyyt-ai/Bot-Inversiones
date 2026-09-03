"""Genera/actualiza data/metrics/{ID}.json y data/thesis/{ID}.json a
partir de los motores existentes, validando cada fila contra el Data
Contract (schema.py) antes de escribirla. A diferencia de _data/, data/
SI se versiona en git -- es lo que leeran la futura Web App y Power BI.

HISTORIZACION (desde 2026-09-03): cada archivo es un histórico
append-only, no un snapshot que se sobrescribe. Ejecutar build.py varias
veces el mismo día NO duplica filas -- ver "Clave lógica de
idempotencia" en engine/contract/README.md.

Uso:
    python3 engine/contract/build.py
"""
import json
import os
import sys

from adapters import (
    adapt_crypto, adapt_technical, adapt_macro, adapt_equity, adapt_thesis,
    adapt_asset_crypto, adapt_asset_equity, adapt_asset_macro,
)
from schema import validate_metric_row, validate_thesis_row, validate_asset_row, ContractError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, "data")

CRYPTO_ASSETS = {"BTC": None, "ETH": "Ethereum", "ADA": "Cardano", "SOL": "Solana",
                 "DOT": "Polkadot", "XRP": None}
EQUITY_ASSETS = ["IBM", "NVDA", "XOM"]

# Clave logica de idempotencia -- documentada tambien en README.md.
# NUNCA incluye retrieved_at: dos ejecuciones el mismo dia con el mismo
# data_as_of deben coincidir en esta clave y no duplicar la fila.
def _metric_key(row):
    return (row["asset_id"], row["domain"], row["metric"], row["data_as_of"], row["source"])


def _thesis_key(row):
    return (row["asset_id"], row["data_as_of"])


def _load_existing(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def _write_metric_rows(asset_id, new_rows):
    for row in new_rows:
        validate_metric_row(row)
    path = os.path.join(DATA_DIR, "metrics", f"{asset_id}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing = _load_existing(path)
    existing_keys = {_metric_key(r) for r in existing}
    added = [r for r in new_rows if _metric_key(r) not in existing_keys]
    merged = existing + added
    merged.sort(key=lambda r: (r["metric"], r["data_as_of"]))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return len(merged), len(added), len(new_rows) - len(added)


def _write_asset_row(asset_id, row):
    """DimAsset: atributos estaticos, NO se historizan (a diferencia de
    metricas/tesis) -- se sobrescriben, porque nombre/sector/pais/divisa
    no cambian dia a dia y no aporta valor guardar un historico de eso."""
    validate_asset_row(row)
    path = os.path.join(DATA_DIR, "assets", f"{asset_id}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(row, f, ensure_ascii=False, indent=2)


def _write_thesis_row(asset_id, new_row):
    validate_thesis_row(new_row)
    path = os.path.join(DATA_DIR, "thesis", f"{asset_id}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing = _load_existing(path)
    if isinstance(existing, dict):  # formato antiguo: un solo objeto, no historico
        existing = [existing]
    existing_keys = {_thesis_key(r) for r in existing}
    if _thesis_key(new_row) in existing_keys:
        merged = existing
        added = 0
    else:
        merged = existing + [new_row]
        added = 1
    merged.sort(key=lambda r: r["data_as_of"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return len(merged), added


def build_all():
    reasoning_path = os.path.join(ROOT, "engine", "reasoning")
    sys.path.insert(0, reasoning_path)
    try:
        if "thesis" in sys.modules:
            del sys.modules["thesis"]
        thesis_mod = __import__("thesis")
    finally:
        sys.path.remove(reasoning_path)

    errors = []
    summary = []  # (asset_id, total_metric_rows, added_metric_rows, skipped, thesis_total, thesis_added)

    # --- macro: EE.UU. y Eurozona como "activos" propios (US, EA), mismo
    # tratamiento historizado que el resto -- ya no un fichero especial. ---
    try:
        macro_rows = adapt_macro()
        by_region = {}
        for row in macro_rows:
            by_region.setdefault(row["asset_id"], []).append(row)
        for region, rows in by_region.items():
            total, added, skipped = _write_metric_rows(region, rows)
            _write_asset_row(region, adapt_asset_macro(region))
            summary.append((region, total, added, skipped, None, None))
            print(f"{region}: {total} filas históricas ({added} nuevas, {skipped} ya existían) + DimAsset")
    except ContractError as e:
        errors.append(f"macro: {e}")

    for symbol, tvl_chain in CRYPTO_ASSETS.items():
        try:
            rows = adapt_crypto(symbol, tvl_chain) + adapt_technical(symbol)
            total, added, skipped = _write_metric_rows(symbol, rows)
            _write_asset_row(symbol, adapt_asset_crypto(symbol))
            thesis = thesis_mod.build_thesis(symbol, tvl_chain)
            t_total, t_added = _write_thesis_row(symbol, adapt_thesis(thesis, "crypto"))
            summary.append((symbol, total, added, skipped, t_total, t_added))
            print(f"{symbol}: {total} filas históricas ({added} nuevas, {skipped} ya existían) + {t_total} tesis ({t_added} nueva) + DimAsset")
        except ContractError as e:
            errors.append(f"{symbol}: {e}")

    for symbol in EQUITY_ASSETS:
        try:
            rows = adapt_equity(symbol)
            total, added, skipped = _write_metric_rows(symbol, rows)
            _write_asset_row(symbol, adapt_asset_equity(symbol))
            thesis = thesis_mod.build_thesis_equity(symbol)
            t_total, t_added = _write_thesis_row(symbol, adapt_thesis(thesis, "equity"))
            summary.append((symbol, total, added, skipped, t_total, t_added))
            print(f"{symbol}: {total} filas históricas ({added} nuevas, {skipped} ya existían) + {t_total} tesis ({t_added} nueva) + DimAsset")
        except ContractError as e:
            errors.append(f"{symbol}: {e}")

    if errors:
        print("\nERRORES DE VALIDACION (no se escribieron esos ficheros):")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)

    return summary


if __name__ == "__main__":
    build_all()
