# -*- coding: utf-8 -*-
"""Reconciliacion de las filas del cron que F1 no tiene -- S0.5.

EL PROBLEMA
-----------
La rama canonica y la rama de F1 divergieron en `db64475` (2026-09-04). Desde
ahi, el cron diario escribio 8 commits en la canonica sobre `data/metrics/*.json`
-- el formato ANTIGUO -- y F1 borro ese formato completo en `d27f162`, al migrar
a `history/` (parquet) + `incoming/` (CSV). El resultado es un conflicto
modify/delete en 8 ficheros que git NO resuelve solo, y donde elegir un lado
pierde algo:

    quedarse con F1     -> se pierden las filas del cron
    quedarse con el cron -> se deshace la migracion

Ninguna de las dos. Las filas se CONVIERTEN al formato al que ese dato
pertenece ahora, y el borrado de F1 se mantiene.

POR QUE CONVERTIR Y NO RE-DESCARGAR
-----------------------------------
Un refetch produciria `retrieved_at` de hoy, y en las metricas de ventana movil
(percentiles a 365 dias) recalcularia el valor con otra ventana. `retrieved_at`
es procedencia point-in-time: forma parte de la evidencia de lo que realmente
habia en aquella rama, y el proyecto lo separa de `data_as_of` precisamente
para no confundir cuando ocurrio un hecho con cuando se supo.

    NO se consulta Kraken, CoinGecko, DefiLlama ni FRED. Nada de red.
    La fuente son los OBJETOS GIT: `git show <commit>:data/metrics/{ID}.json`.

CARRIL DE DESTINO, medido y no supuesto
---------------------------------------
Las 754 filas tienen `data_as_of` en 2026, el ano ABIERTO, y `history/` llega
a 2025. Asi que el carril es `incoming/{ID}_2026.csv` y NO el carril `late`,
que es para anos ya consolidados en parquet. Consecuencia: ningun parquet se
toca, ningun hash del manifiesto de `history/` cambia y no hace falta
revision de particion.

IDEMPOTENCIA
------------
La clave logica es la que ya usa el cron -- `(asset_id, domain, metric,
data_as_of, source)`, SIN `retrieved_at` -- y se descarta lo que ya este en el
destino. Segunda ejecucion: 0 escrituras. No es un efecto colateral: es la
propiedad que hace segura la operacion.

Todas las primitivas son las que ya existen. `from_json_row()` se escribio
para esta conversion y esta validada sobre las 507.330 filas reales.
"""
import argparse
import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import storage  # noqa: E402

# Commits PINADOS, no refs. Una rama se mueve; un commit no, y la operacion
# tiene que dar el mismo resultado manana.
BASE = "db64475d51c841f62c572d442e5633f1b611fb9f"    # divergencia
CANONICA = "4a94743d25aaa723b0dbcf9e75b57cbc8e3741e2"  # cron, 8 commits despues

ACTIVOS = ("ADA", "BTC", "DOT", "EA", "ETH", "SOL", "US", "XRP")

ANIO_ESPERADO = 2026     # el ano abierto: lo comprueba, no lo asume


def filas_en(commit, asset_id, raiz=RAIZ):
    """Filas del JSON antiguo TAL COMO ESTABAN en `commit`. Sin red."""
    r = subprocess.run(
        ["git", "-C", raiz, "show", f"{commit}:data/metrics/{asset_id}.json"],
        capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return json.loads(r.stdout)


def _clave_json(r):
    """La MISMA clave logica, leida del JSON antiguo sin convertir."""
    return (r["asset_id"], r["domain"], r["metric"], r["data_as_of"], r["source"])


def delta(asset_id, base=BASE, canonica=CANONICA, raiz=RAIZ):
    """Filas que la canonica tiene y la base no. Nada mas."""
    en_base = {_clave_json(r) for r in filas_en(base, asset_id, raiz)}
    return [r for r in filas_en(canonica, asset_id, raiz)
            if _clave_json(r) not in en_base]


def reconciliar(asset_id, base=BASE, canonica=CANONICA, raiz=RAIZ, escribir=True):
    """{leidas, nuevas, ya_presentes, escritas, anios} de un activo."""
    nuevas = delta(asset_id, base, canonica, raiz)
    anios = sorted({r["data_as_of"][:4] for r in nuevas})

    destino = storage.incoming_path(asset_id, ANIO_ESPERADO)
    existentes = {storage.logical_key(f) for f in storage.read_incoming(destino)}

    convertidas, ya = [], 0
    for r in nuevas:
        fila = storage.from_json_row(r)
        if storage.logical_key(fila) in existentes:
            ya += 1
            continue
        convertidas.append(fila)

    escritas = storage.append_incoming(destino, convertidas) if escribir else 0
    return {"asset_id": asset_id, "leidas": len(nuevas), "nuevas": len(convertidas),
            "ya_presentes": ya, "escritas": escritas, "anios": anios,
            "destino": os.path.relpath(destino, raiz)}


def verificar(asset_id, base=BASE, canonica=CANONICA, raiz=RAIZ):
    """Comparacion FILA A FILA contra el origen git, campo por campo.

    Valor a valor y no por sumas: el criterio que `3a1b087` ya tuvo que
    corregir una vez en este proyecto."""
    origen = delta(asset_id, base, canonica, raiz)
    destino = {storage.logical_key(f): f
               for f in storage.read_incoming(
                   storage.incoming_path(asset_id, ANIO_ESPERADO))}

    incidencias, comprobadas = [], 0
    for r in origen:
        esperada = storage.from_json_row(r)
        real = destino.get(storage.logical_key(esperada))
        if real is None:
            incidencias.append(f"{_clave_json(r)}: AUSENTE en incoming")
            continue
        for col in storage.COLUMNS:
            if esperada[col] != real[col]:
                incidencias.append(
                    f"{_clave_json(r)}: {col} {esperada[col]!r} != {real[col]!r}")
        comprobadas += 1
    return comprobadas, incidencias


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verificar", action="store_true",
                    help="no escribe: solo compara fila a fila contra git")
    ap.add_argument("--dry-run", action="store_true", help="cuenta sin escribir")
    args = ap.parse_args(argv)

    print(f"RECONCILIACION S0.5 - base {BASE[:7]} -> canonica {CANONICA[:7]}")
    print(f"  fuente: objetos git. Sin red.")

    if args.verificar:
        total, incidencias = 0, []
        for a in ACTIVOS:
            n, inc = verificar(a)
            total += n
            incidencias += inc
            print(f"  {a:4} {n:4} fila(s) comparadas campo por campo"
                  + (f"  {len(inc)} incidencia(s)" if inc else ""))
        for i in incidencias[:10]:
            print(f"    {i}")
        print(f"  TOTAL comparadas: {total} . incidencias: {len(incidencias)}")
        print(f"RESULTADO: {'PASS' if not incidencias else 'FAIL'}")
        return 0 if not incidencias else 1

    tot = {"leidas": 0, "nuevas": 0, "ya_presentes": 0, "escritas": 0}
    anios = set()
    for a in ACTIVOS:
        r = reconciliar(a, escribir=not args.dry_run)
        for k in tot:
            tot[k] += r[k]
        anios |= set(r["anios"])
        print(f"  {a:4} leidas {r['leidas']:4} . nuevas {r['nuevas']:4} . "
              f"ya {r['ya_presentes']:4} . escritas {r['escritas']:4} -> {r['destino']}")
    print(f"  TOTAL leidas {tot['leidas']} . nuevas {tot['nuevas']} . "
          f"ya presentes {tot['ya_presentes']} . escritas {tot['escritas']}")
    print(f"  anios de data_as_of: {sorted(anios)}")
    if anios and anios != {str(ANIO_ESPERADO)}:
        print(f"  AVISO: hay filas fuera de {ANIO_ESPERADO}; el carril "
              f"incoming/{{ID}}_{ANIO_ESPERADO}.csv no las cubre")
        return 1
    print("RESULTADO: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
