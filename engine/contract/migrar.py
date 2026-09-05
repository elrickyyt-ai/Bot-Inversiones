"""Conversor de data/metrics/*.json a history/ + incoming/ -- UNA SOLA VEZ.

No es parte del flujo diario: se ejecuta en la migracion y despues deja de
tener uso. Genera la estructura nueva AL LADO de la antigua, sin borrar ni
sobrescribir ningun JSON -- la retirada del JSON es un commit posterior y
aislado, y solo despues de que todas las verificaciones hayan pasado.

Uso:
    python3 engine/contract/migrar.py            convierte los 11 activos
    python3 engine/contract/migrar.py IBM XOM    solo los indicados
"""
import collections
import json
import os
import sys

import storage
from storage import DATA_DIR


def _leer_json(asset_id):
    path = os.path.join(DATA_DIR, "metrics", f"{asset_id}.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def convertir_activo(asset_id, anio_abierto=None):
    """JSON de un activo -> particiones de history/ + CSV de incoming/.

    Los anios cerrados van a history/ como revision 1. El anio en curso va
    a incoming/, porque es el unico que todavia cambia a diario y meterlo
    en un parquet reescrito seria justo el patron que la arquitectura evita.
    """
    anio_abierto = anio_abierto or storage.anio_abierto()
    filas = [storage.from_json_row(r) for r in _leer_json(asset_id)]
    asset_type = filas[0]["asset_type"]

    por_anio = collections.defaultdict(list)
    for r in filas:
        por_anio[r["data_as_of"].year].append(r)

    cerrados, abiertas = {}, []
    for anio, rs in sorted(por_anio.items()):
        if anio < anio_abierto:
            storage.write_partition(asset_type, asset_id, anio, rs, revision=1)
            cerrados[anio] = len(rs)
        else:
            abiertas += rs

    if abiertas:
        storage.append_incoming(
            storage.incoming_path(asset_id, anio_abierto), abiertas)

    return {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "filas_origen": len(filas),
        "particiones": len(cerrados),
        "filas_history": sum(cerrados.values()),
        "filas_incoming": len(abiertas),
    }


def main(activos=None):
    metrics = os.path.join(DATA_DIR, "metrics")
    activos = activos or sorted(
        f[:-5] for f in os.listdir(metrics) if f.endswith(".json"))
    total_o = total_h = total_i = 0
    print(f"{'ACTIVO':7} {'TIPO':8} {'ORIGEN':>9} {'HISTORY':>9} {'INCOMING':>9} {'PART.':>6}")
    for a in activos:
        r = convertir_activo(a)
        total_o += r["filas_origen"]
        total_h += r["filas_history"]
        total_i += r["filas_incoming"]
        print(f"{r['asset_id']:7} {r['asset_type']:8} {r['filas_origen']:>9,} "
              f"{r['filas_history']:>9,} {r['filas_incoming']:>9,} {r['particiones']:>6}")
    print(f"{'TOTAL':7} {'':8} {total_o:>9,} {total_h:>9,} {total_i:>9,}")
    if total_h + total_i != total_o:
        print(f"\nFALLO: history+incoming ({total_h + total_i:,}) != origen ({total_o:,})")
        return 1
    print(f"\nhistory + incoming = {total_h + total_i:,} = origen. Sin perdida de filas.")
    print("El JSON original NO se ha tocado.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
