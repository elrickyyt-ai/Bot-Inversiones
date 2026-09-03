"""Genera data/metrics/{TICKER}.json y data/thesis/{TICKER}.json a partir
de los motores existentes, validando cada fila contra el Data Contract
(schema.py) antes de escribirla. A diferencia de _data/, data/ SI se
versiona en git -- es lo que leeran la futura Web App y Power BI.

Uso:
    python3 engine/contract/build.py
"""
import json
import os

from adapters import adapt_crypto, adapt_technical, adapt_macro, adapt_equity, adapt_thesis
from schema import validate_metric_row, validate_thesis_row, ContractError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, "data")

CRYPTO_ASSETS = {"BTC": None, "ETH": "Ethereum", "ADA": "Cardano", "SOL": "Solana",
                 "DOT": "Polkadot", "XRP": None}
EQUITY_ASSETS = ["IBM", "NVDA", "XOM"]


def _write_metric_rows(asset_id, rows):
    for row in rows:
        validate_metric_row(row)
    path = os.path.join(DATA_DIR, "metrics", f"{asset_id}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    return len(rows)


def _write_thesis_row(asset_id, row):
    validate_thesis_row(row)
    path = os.path.join(DATA_DIR, "thesis", f"{asset_id}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(row, f, ensure_ascii=False, indent=2)


def build_all():
    import sys
    reasoning_path = os.path.join(ROOT, "engine", "reasoning")
    sys.path.insert(0, reasoning_path)
    try:
        if "thesis" in sys.modules:
            del sys.modules["thesis"]
        thesis_mod = __import__("thesis")
    finally:
        sys.path.remove(reasoning_path)

    errors = []

    # --- macro: no es por activo, se escribe una vez ---
    try:
        macro_rows = adapt_macro()
        for row in macro_rows:
            validate_metric_row(row)
        os.makedirs(os.path.join(DATA_DIR, "metrics"), exist_ok=True)
        with open(os.path.join(DATA_DIR, "metrics", "_macro.json"), "w", encoding="utf-8") as f:
            json.dump(macro_rows, f, ensure_ascii=False, indent=2)
        print(f"macro: {len(macro_rows)} filas")
    except ContractError as e:
        errors.append(f"macro: {e}")

    for symbol, tvl_chain in CRYPTO_ASSETS.items():
        try:
            rows = adapt_crypto(symbol, tvl_chain) + adapt_technical(symbol)
            n = _write_metric_rows(symbol, rows)
            thesis = thesis_mod.build_thesis(symbol, tvl_chain)
            _write_thesis_row(symbol, adapt_thesis(thesis, "crypto"))
            print(f"{symbol}: {n} filas de metrica + 1 tesis")
        except ContractError as e:
            errors.append(f"{symbol}: {e}")

    for symbol in EQUITY_ASSETS:
        try:
            rows = adapt_equity(symbol)
            n = _write_metric_rows(symbol, rows)
            thesis = thesis_mod.build_thesis_equity(symbol)
            _write_thesis_row(symbol, adapt_thesis(thesis, "equity"))
            print(f"{symbol}: {n} filas de metrica + 1 tesis")
        except ContractError as e:
            errors.append(f"{symbol}: {e}")

    if errors:
        print("\nERRORES DE VALIDACION (no se escribieron esos ficheros):")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    build_all()
