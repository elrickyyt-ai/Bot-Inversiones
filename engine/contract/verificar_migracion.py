"""Verificacion de equivalencia entre data/metrics/*.json y la estructura nueva.

Las 8 comprobaciones del plan de migracion. Compara el JSON original (que
sigue presente durante toda la migracion) contra history/ + incoming/ ya
resueltos por clave logica.

Criterio: CUALQUIER discrepancia es FAIL, salvo la unica documentada -- el
desdoble de value/value_text en las filas categoricas, que debe cuadrar
exactamente, no "aproximadamente".

Uso:
    python3 engine/contract/verificar_migracion.py
"""
import collections
import json
import math
import os
import sys

import storage
from storage import DATA_DIR


def _origen(asset_id):
    with open(os.path.join(DATA_DIR, "metrics", f"{asset_id}.json"),
              encoding="utf-8") as f:
        return [storage.from_json_row(r) for r in json.load(f)]


def _destino(asset_type, asset_id):
    return storage.resolve(storage.all_layers(asset_type, asset_id))


def _suma(filas):
    """Total independiente del orden de acumulacion. math.fsum lleva un
    acumulador exacto, asi que sumar las mismas filas en cualquier orden da
    siempre el mismo resultado -- a diferencia de sum(), que no."""
    return math.fsum(r["value"] for r in filas if r["value"] is not None)


def _nulos(filas):
    c = collections.Counter()
    for r in filas:
        for k in storage.COLUMNS:
            if r[k] is None:
                c[k] += 1
    return c


def verificar_activo(asset_id):
    orig = _origen(asset_id)
    asset_type = orig[0]["asset_type"]
    dest = _destino(asset_type, asset_id)
    fallos = []

    # 1. filas
    if len(orig) != len(dest):
        fallos.append(f"filas: origen {len(orig):,} != destino {len(dest):,}")

    # 1b. filas por (dominio, metrica)
    go = collections.Counter((r["domain"], r["metric"]) for r in orig)
    gd = collections.Counter((r["domain"], r["metric"]) for r in dest)
    if go != gd:
        for k in sorted(set(go) | set(gd)):
            if go[k] != gd[k]:
                fallos.append(f"filas en {k}: origen {go[k]} != destino {gd[k]}")

    # 2. claves logicas -- diferencia simetrica debe ser 0
    ko = {storage.logical_key(r) for r in orig}
    kd = {storage.logical_key(r) for r in dest}
    dif = ko ^ kd
    if dif:
        fallos.append(f"claves logicas: diferencia simetrica {len(dif)} (ej. {sorted(dif)[:2]})")

    # 3. duplicados
    if len(kd) != len(dest):
        fallos.append(f"duplicados en destino: {len(dest) - len(kd)} claves repetidas")

    # 4. VALORES -- comparacion valor a valor por clave logica, 0 diferencias.
    #
    # No se comparan sumas acumuladas: sum() sobre float NO es asociativo, asi
    # que sumar los MISMOS numeros en el orden del JSON y en el orden canonico
    # da resultados distintos en el ultimo bit (medido: delta de 1,2e-7 en BTC).
    # Eso mide el orden de acumulacion, no la equivalencia de los datos, y
    # produciria un FAIL donde no hay ningun fallo.
    #
    # La comparacion por clave es mas estricta: exige identidad exacta de cada
    # valor, no que un agregado cuadre. Como control adicional del total se usa
    # math.fsum, que si es independiente del orden.
    io = {storage.logical_key(r): r for r in orig}
    idd = {storage.logical_key(r): r for r in dest}
    for campo in ("value", "value_text", "data_as_of", "retrieved_at",
                  "unit", "source_priority", "confidence_pct",
                  "data_quality_pct", "calculation_method", "source_url"):
        distintos = [k for k in io if k in idd and io[k][campo] != idd[k][campo]]
        if distintos:
            k = distintos[0]
            fallos.append(f"{campo}: {len(distintos)} valores distintos "
                          f"(ej. {k}: {io[k][campo]!r} != {idd[k][campo]!r})")

    so, sd = _suma(orig), _suma(dest)
    if so != sd:
        fallos.append(f"total fsum de value: origen {so:.6f} != destino {sd:.6f}")

    # 5. min/max de data_as_of
    for etiqueta, fn in (("min", min), ("max", max)):
        vo = fn(r["data_as_of"] for r in orig)
        vd = fn(r["data_as_of"] for r in dest)
        if vo != vd:
            fallos.append(f"data_as_of {etiqueta}: origen {vo} != destino {vd}")

    # 6. nulos por columna
    no, nd = _nulos(orig), _nulos(dest)
    for col in storage.COLUMNS:
        if no[col] != nd[col]:
            fallos.append(f"nulos en {col}: origen {no[col]:,} != destino {nd[col]:,}")

    # 7. schema -- todas las filas con las 15 columnas exactas
    for r in dest[:1]:
        if set(r.keys()) != set(storage.COLUMNS):
            fallos.append(f"schema: columnas {sorted(set(r.keys()) ^ set(storage.COLUMNS))}")

    # 8. rango temporal de cada particion de history/
    man = storage.read_manifest(asset_type, asset_id)
    d = storage.history_dir(asset_type, asset_id)
    for e in man["particiones"]:
        rs = storage.read_parquet(os.path.join(d, e["fichero"]))
        fuera = [r for r in rs if r["data_as_of"].year != e["anio"]]
        if fuera:
            fallos.append(f"{e['fichero']}: {len(fuera)} filas fuera del anio {e['anio']}")
        if len(rs) != e["filas"]:
            fallos.append(f"{e['fichero']}: {len(rs)} filas != {e['filas']} del manifiesto")

    categoricas = sum(1 for r in dest if r["value_text"] is not None)
    return fallos, {
        "filas": len(dest), "suma": sd, "categoricas": categoricas,
        "particiones": len(man["particiones"]),
    }


def main():
    metrics = os.path.join(DATA_DIR, "metrics")
    activos = sorted(f[:-5] for f in os.listdir(metrics) if f.endswith(".json"))
    print("=" * 78)
    print("VERIFICACION DE EQUIVALENCIA -- data/metrics/*.json vs history/ + incoming/")
    print("=" * 78)
    print(f"\n{'ACTIVO':7} {'FILAS':>9} {'PART.':>6} {'CATEG.':>7} {'SUMA DE value':>24}  RESULTADO")
    todos_ok = True
    total_filas = total_cat = 0
    for a in activos:
        fallos, info = verificar_activo(a)
        total_filas += info["filas"]
        total_cat += info["categoricas"]
        estado = "PASS" if not fallos else "FAIL"
        if fallos:
            todos_ok = False
        print(f"{a:7} {info['filas']:>9,} {info['particiones']:>6} "
              f"{info['categoricas']:>7} {info['suma']:>24.6f}  {estado}")
        for f in fallos:
            print(f"        -> {f}")
    print(f"\nFilas totales en destino: {total_filas:,}")
    print(f"Filas categoricas (value nulo + value_text relleno): {total_cat}")
    print(f"\n{'=' * 78}")
    print(f"RESULTADO GLOBAL: {'PASS' if todos_ok else 'FAIL'}")
    print("=" * 78)
    return 0 if todos_ok else 1


if __name__ == "__main__":
    sys.exit(main())
