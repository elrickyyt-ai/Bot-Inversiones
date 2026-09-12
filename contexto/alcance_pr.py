# -*- coding: utf-8 -*-
"""Guarda de alcance conectada al diff real de un PR. T9 de F1 (2026-09-12),
reescrita en S0.1 para el contrato de alcance por bloque (DF-1).

NO REIMPLEMENTA NINGUNA REGLA. La regla vive en `validar.veredicto_alcance()`
y aqui solo se hacen dos cosas:

    1. obtener el diff real           git diff --name-only base..head
    2. delegar en la autoridad        validar.guarda_alcance(rutas)

Si este modulo llegara a contener una segunda copia de la regla -- una lista
de arboles protegidos, por ejemplo -- seria un defecto de diseno, no una
optimizacion.

QUE CAMBIO EN S0.1
------------------
Antes existia un INTERRUPTOR: `alcance_bloque.vigente`. Apagarlo dejaba el
repositorio con proteccion CERO, y un bloque solo podia declarar QUE su
alcance aplicaba, nunca CUAL era. Ahora cada bloque declara su propia lista
de escritura y SIEMPRE hay un bloque activo: la transicion de F1 a S0 a PC-1
es una SUSTITUCION de alcance, no un apagado. No queda ningun valor del
contrato que desactive la guarda.

DIFF COMPLETO, NO EL ULTIMO COMMIT
----------------------------------
Sin `--base` se comparaba `HEAD~1..HEAD`, es decir un solo commit. Eso hacia
que un `exit=0` local no dijese nada sobre lo que un PR real contiene. El
workflow inyecta BASE_SHA y HEAD_SHA del PR; cuando faltan, la salida lo
DECLARA en vez de aparentar haber verificado el PR entero.
"""
import os
import subprocess

import estado as _estado
import validar as _validar

RAIZ = _estado.RAIZ

# Reexportados desde la autoridad: un solo sitio los define.
ALCANCE_NO_DECLARADO = _validar.ALCANCE_NO_DECLARADO
PROTEGIDO_GLOBAL = _validar.PROTEGIDO_GLOBAL
PERMITIDO = _validar.PERMITIDO
FUERA_DE_ALCANCE = _validar.FUERA_DE_ALCANCE


def bloque_activo(contrato=None):
    """Delegado en la autoridad. Sin declaracion no se asume nada."""
    return _validar.bloque_activo(contrato)


def ficheros_cambiados(base=None, head="HEAD", raiz=RAIZ):
    """Diff real. Sin base, se compara con el primer padre de head -- un solo
    commit, que NO es el diff de un PR (lo dice `rango_parcial`)."""
    rango = f"{base}..{head}" if base else f"{head}~1..{head}"
    r = subprocess.run(["git", "-C", raiz, "diff", "--name-only", rango],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git diff fallo: {r.stderr.strip()}")
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def rango_parcial(base):
    """True si el rango examinado es un solo commit y no el PR completo."""
    return not base


def verificar(rutas, contrato=None, raiz=RAIZ):
    """(codigo_salida, motivo). Delega la REGLA entera."""
    ok, motivo = _validar.guarda_alcance(rutas, contrato, raiz)
    return (0 if ok else 1), motivo


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Guarda de alcance sobre el diff de un PR.")
    ap.add_argument("--base", default=os.environ.get("BASE_SHA") or None)
    ap.add_argument("--head", default=os.environ.get("HEAD_SHA") or "HEAD")
    args = ap.parse_args(argv)

    rutas = ficheros_cambiados(args.base, args.head)
    codigo, motivo = verificar(rutas)
    bid, decl = bloque_activo()
    veredictos, _ = _validar.veredicto_alcance(rutas)

    print(f"GUARDA DE ALCANCE - {len(rutas)} fichero(s) en el diff")
    print(f"  bloque activo {bid!r}" + ("" if decl else "  <- NO DECLARADO en `bloques`"))
    if decl:
        print(f"  escritura declarada: {list(decl.get('escritura') or ())}")
    if rango_parcial(args.base):
        print("  AVISO: sin BASE_SHA se ha examinado SOLO el ultimo commit, "
              "no el diff completo del PR")
    conteo = {v: sum(1 for x in veredictos.values() if x == v)
              for v in _validar.VEREDICTOS_ALCANCE}
    print("  " + " . ".join(f"{v}={conteo[v]}" for v in _validar.VEREDICTOS_ALCANCE))
    for r in rutas[:20]:
        print(f"    {veredictos.get(r, '?'):20s} {r}")
    if len(rutas) > 20:
        print(f"    ... y {len(rutas) - 20} mas")
    if motivo:
        print(f"  {motivo}")
    print(f"RESULTADO: {'PASS' if codigo == 0 else 'FAIL'}")
    return codigo


if __name__ == "__main__":
    import sys
    sys.exit(main())
