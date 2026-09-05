"""Cierre de anio: incoming/{ID}_{anio}.csv -> history/{tipo}/{ID}/{anio}.parquet.

Se ejecuta UNA vez al ano, en enero, y por eso es un procedimiento que
estara oxidado cuando haga falta si no se prueba antes. Aceptar eso sin
mas seria un riesgo conocido y no mitigado: --dry-run existe para poder
ensayarlo sobre un anio ya cerrado sin escribir nada.

Verifica ANTES de vaciar nada: numero de filas y suma de control de value
del CSV frente a los del parquet recien escrito. Si la comprobacion falla,
el CSV se queda intacto y no se registra ninguna particion.

Uso:
    python3 engine/contract/compactar.py --dry-run          ensayo, no escribe
    python3 engine/contract/compactar.py --anio 2026        cierra ese anio
"""
import argparse
import math
import os
import sys

import storage


def _suma(filas):
    """math.fsum, no sum(): el total no debe depender del orden de
    acumulacion (sum() sobre float no es asociativo)."""
    return math.fsum(r["value"] for r in filas if r["value"] is not None)


def compactar_activo(asset_id, anio, dry_run=False):
    """Devuelve (estado, detalle). No escribe nada si dry_run."""
    origen = storage.incoming_path(asset_id, anio)
    filas = storage.read_incoming(origen)
    if not filas:
        return "SIN DATOS", {}

    fuera = [r for r in filas if r["data_as_of"].year != anio]
    if fuera:
        return "FAIL", {"motivo": f"{len(fuera)} filas con data_as_of fuera de {anio}"}

    asset_type = filas[0]["asset_type"]
    esperado = {"filas": len(filas), "suma": _suma(filas)}

    if dry_run:
        # Escribe a un temporal para comprobar de verdad que el parquet sale
        # bien, y lo borra. Ensayar sin escribir nada no probaria gran cosa.
        tmp = os.path.join(storage.CURRENT_DIR, f".ensayo_{asset_id}_{anio}.parquet")
        os.makedirs(storage.CURRENT_DIR, exist_ok=True)
        storage.write_parquet(storage.canonical_sort(filas), tmp)
        releidas = storage.read_parquet(tmp)
        os.remove(tmp)
    else:
        path = storage.write_partition(asset_type, asset_id, anio,
                                       filas, revision=_siguiente_revision(asset_type, asset_id, anio))
        releidas = storage.read_parquet(path)

    obtenido = {"filas": len(releidas), "suma": _suma(releidas)}
    if obtenido != esperado:
        return "FAIL", {"esperado": esperado, "obtenido": obtenido}

    if not dry_run:
        # Solo ahora, con la verificacion pasada, se vacia el CSV.
        os.remove(origen)

    return "OK", {"filas": esperado["filas"], "suma": esperado["suma"]}


def _siguiente_revision(asset_type, asset_id, anio):
    man = storage.read_manifest(asset_type, asset_id)
    revs = [e["revision"] for e in man["particiones"] if e["anio"] == anio]
    return max(revs) + 1 if revs else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--anio", type=int, default=storage.anio_abierto() - 1)
    ap.add_argument("--dry-run", action="store_true",
                    help="ensaya la compactación sin escribir en history/ ni vaciar el CSV")
    args = ap.parse_args(argv)

    activos = storage.assets_en_incoming()
    if not activos:
        print("No hay nada en incoming/.")
        return 0

    modo = "ENSAYO (no escribe)" if args.dry_run else "REAL"
    print(f"Compactación de {args.anio} — modo {modo}\n")
    print(f"{'ACTIVO':8} {'ESTADO':10} {'FILAS':>8} {'SUMA DE value':>24}")
    fallos = 0
    for a in activos:
        estado, det = compactar_activo(a, args.anio, dry_run=args.dry_run)
        if estado == "FAIL":
            fallos += 1
            print(f"{a:8} {estado:10} {det}")
        elif estado == "SIN DATOS":
            print(f"{a:8} {estado:10}")
        else:
            print(f"{a:8} {estado:10} {det['filas']:>8,} {det['suma']:>24.6f}")
    print(f"\nRESULTADO: {'PASS' if not fallos else f'FAIL ({fallos} activos)'}")
    if args.dry_run:
        print("Ensayo: no se ha escrito ninguna partición ni vaciado ningún CSV.")
    return 0 if not fallos else 1


if __name__ == "__main__":
    sys.exit(main())
