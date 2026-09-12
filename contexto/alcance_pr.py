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

EL RANGO ES EL DEL BLOQUE, NO EL DIFF CONTRA LA BASE
---------------------------------------------------
    BLOQUE = desde + hasta      ->   rango = desde~1..hasta

Un bloque responde de los commits que ESCRIBIO. Evaluar el diff contra la
rama base confunde dos preguntas distintas -- "que escribio este bloque
fuera de su alcance" y "que le falta a la rama base" -- y medido sobre el PR
de integracion real daba 389 FUERA_DE_ALCANCE, todos obra de bloques
anteriores (P1-P6.2, F1) que la canonica no tiene. Ampliar `escritura` para
taparlo habria sido falso, y exceptuar los PR de integracion habria sido el
interruptor renacido con otro nombre.

Mientras el bloque esta abierto, `hasta` es null y aqui se resuelve a HEAD
como valor OPERATIVO. Al cerrarlo se fija al commit real y el rango queda
reproducible: el significado historico de un bloque cerrado no depende de
HEAD.

BASE_SHA/HEAD_SHA siguen leyendose del entorno para el caso en que un bloque
no declare rango: entonces se cae al diff del PR y la salida lo DECLARA, en
vez de aparentar haber verificado algo que no verifico.
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


def _diff(rango, raiz=RAIZ):
    r = subprocess.run(["git", "-C", raiz, "diff", "--name-only", rango],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git diff fallo: {r.stderr.strip()}")
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def rango_del_bloque(contrato=None, head="HEAD"):
    """(rango, origen). `desde~1..hasta` del bloque activo.

    origen  "bloque"           el bloque declara `desde`
            "bloque-abierto"   ademas `hasta` es null -> HEAD operativo
            None               el bloque no declara rango"""
    desde, hasta, operativo = _validar.rango_bloque(contrato=contrato)
    if not desde:
        return None, None
    return f"{desde}~1..{hasta or head}", ("bloque-abierto" if operativo else "bloque")


def rutas_a_evaluar(base=None, head="HEAD", raiz=RAIZ, contrato=None):
    """(rutas, origen, rango). Prioridad: rango del bloque > diff del PR >
    ultimo commit. `origen` y `rango` viajan con el resultado para que la
    salida pueda DECLARAR que se ha medido en realidad, en vez de aparentar
    haber verificado algo distinto."""
    rango, origen = rango_del_bloque(contrato, head)
    if rango:
        return _diff(rango, raiz), origen, rango
    if base:
        return _diff(f"{base}..{head}", raiz), "pr", f"{base}..{head}"
    return _diff(f"{head}~1..{head}", raiz), "ultimo-commit", f"{head}~1..{head}"


def ficheros_cambiados(base=None, head="HEAD", raiz=RAIZ, contrato=None):
    """Solo las rutas. Firma estable para quien no necesita la procedencia."""
    return rutas_a_evaluar(base, head, raiz, contrato)[0]


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

    rutas, origen, rango = rutas_a_evaluar(args.base, args.head)
    codigo, motivo = verificar(rutas)
    bid, decl = bloque_activo()
    veredictos, _ = _validar.veredicto_alcance(rutas)

    print(f"GUARDA DE ALCANCE - {len(rutas)} fichero(s) en {rango}")
    print(f"  bloque activo {bid!r}" + ("" if decl else "  <- NO DECLARADO en `bloques`"))
    if decl:
        print(f"  escritura declarada: {list(decl.get('escritura') or ())}")
    if origen == "bloque-abierto":
        print("  rango del BLOQUE, con `hasta` abierto: HEAD es un valor operativo, "
              "no el cierre del bloque")
    elif origen == "bloque":
        print("  rango del BLOQUE, cerrado y reproducible")
    elif origen == "pr":
        print("  AVISO: el bloque activo no declara `desde`; se evalua el diff del "
              "PR, que incluye lo que la rama base todavia no tiene")
    else:
        print("  AVISO: sin `desde` ni BASE_SHA se ha examinado SOLO el ultimo "
              "commit, no el rango del bloque")
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
