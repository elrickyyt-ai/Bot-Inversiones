"""Regenera data/current/{ID}.parquet desde history/ + incoming/.

current/ es un artefacto DERIVADO: no se versiona, no es fuente de verdad
y borrarlo entero no pierde ni un dato. Es lo unico que lee Power BI --
nunca history/ ni incoming/ directamente, porque leer history/ en crudo
uniria las revisiones r1 y r2 como si fueran filas independientes.

Se ejecuta a mano despues de un git pull, o tras la ingesta diaria si se
quiere refrescar Power BI. NO forma parte del cron: mantenerlo fuera es lo
que permite que el camino critico diario siga sin depender de PyArrow.

Uso:
    python3 engine/contract/materializar.py            todos los activos
    python3 engine/contract/materializar.py IBM BTC    solo los indicados
"""
import os
import sys

import storage


def activos_disponibles():
    ids = set()
    if os.path.isdir(storage.HISTORY_DIR):
        for t in os.listdir(storage.HISTORY_DIR):
            d = os.path.join(storage.HISTORY_DIR, t)
            if os.path.isdir(d):
                ids.update(os.listdir(d))
    if os.path.isdir(storage.INCOMING_DIR):
        for f in os.listdir(storage.INCOMING_DIR):
            if f.endswith(".csv"):
                ids.add(f.rsplit("_", 1)[0])
    return sorted(ids)


def main(activos=None):
    activos = activos or activos_disponibles()
    if not activos:
        print("No hay nada que materializar: history/ e incoming/ están vacíos.")
        return 1
    total = 0
    print(f"{'ACTIVO':8} {'TIPO':8} {'FILAS':>10}  {'MB':>7}")
    for a in activos:
        tipo = storage.asset_type_of(a)
        if tipo is None:
            print(f"{a:8} {'?':8} {'--':>10}  (sin datos)")
            continue
        n = storage.materialize(tipo, a)
        mb = os.path.getsize(os.path.join(storage.CURRENT_DIR, f"{a}.parquet")) / 1048576
        total += n
        print(f"{a:8} {tipo:8} {n:>10,} {mb:>8.2f}")
    print(f"\n{total:,} filas materializadas en data/current/")
    print("Power BI debe apuntar a esa carpeta, nunca a history/ ni a incoming/.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
