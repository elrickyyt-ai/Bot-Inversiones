# -*- coding: utf-8 -*-
"""Autoridad de la suite del CRON -- plano de datos (S0.11, D-60).

NO CONTIENE NINGUN NUMERO NI NINGUNA LISTA DE MODULOS. Ambos viven en
`contrato.json::ci_cron` y aqui se LEEN. Y no contiene la REGLA: reutiliza
`suite_pr.leer()` y `suite_pr.evaluar()`, que son funciones puras. Si esta
autoridad llegase a reimplementar el criterio seria una segunda copia, el
mismo defecto que DF-1 corrigio con la lista de arboles.

POR QUE EXISTE
--------------
El cron de datos y el gate de PR validan dos planos distintos:

    PR    gobernanza    contexto, alcance, cierre, IMPORTADO, merge-base,
                        HUMAN-ASSERTED, integridad historica
                        -> NECESITA historia git completa (fetch-depth: 0)

    CRON  datos         fuentes, build, Data Contract, schema, temporalidad,
                        claves logicas, duplicados, incoming, parquet, QA
                        -> NO necesita historia: clon de profundidad 1

Hasta la integracion de S0 esa distincion no existia, porque la rama canonica
no tenia la suite de F1. El run 34722019555 la hizo visible de golpe: 34 tests
de gobernanza no pueden resolver commits que el clon superficial del cron no
contiene. La respuesta NO es dar historia completa al cron -- eso mezcla las
dos responsabilidades -- sino separar los contratos.

UN TEST FUERA DEL CRON NO ES UN TEST OLVIDADO
---------------------------------------------
Lo que el cron no ejecuta lo ejecuta el gate de PR, y `test_planos.py` exige
que la union de los tres planos sea EXACTAMENTE el contenido de tests/. No hay
forma de que un modulo desaparezca en silencio, que es el riesgo real de
partir una suite en dos.

DOS PERFILES, porque el cron tiene dos jobs con entornos distintos:

    sin-parquet   job `actualizar`, sin dependencias -> saltos DECLARADOS
    con-parquet   job `verificar`, con pyarrow       -> 0 saltos

Falla en los DOS sentidos en ambos perfiles, igual que suite_pr: un salto de
mas es cobertura que se perdio sin avisar; uno de menos es que el entorno no
es el que el contrato declara.
"""
import argparse
import os
import subprocess
import sys

import estado as _estado
import suite_pr as _pr

RAIZ = _estado.RAIZ

PERFILES = ("sin-parquet", "con-parquet")

CRON_SIN_SELECCION = "CRON_SIN_SELECCION"
CRON_PERFIL_DESCONOCIDO = "CRON_PERFIL_DESCONOCIDO"


def declaracion(contrato=None):
    """(seleccion, decl). Sin declaracion NO se asume nada."""
    c = contrato or _estado.cargar_contrato()
    d = c.get("ci_cron") or {}
    return tuple(d.get("cron_ejecuta") or ()), d


def esperados(perfil, contrato=None):
    """Saltos declarados para el perfil. None si no esta declarado."""
    _sel, d = declaracion(contrato)
    return (d.get("skips_esperados") or {}).get(perfil)


def plano(modulo, contrato=None):
    """DATA_OPERATIONAL / GOVERNANCE_ONLY / BOTH, o None si no esta clasificado."""
    _sel, d = declaracion(contrato)
    return (d.get("plano") or {}).get(modulo)


def ejecutar(seleccion, raiz=RAIZ, entorno=None):
    """Los modulos se cargan como los carga `discover`: con tests/ en el path.
    Sin eso, 13 de ellos no importan -- se apoyan en ese sys.path."""
    env = dict(entorno or os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [os.path.join(raiz, "tests")] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    r = subprocess.run([sys.executable, "-m", "unittest"] + list(seleccion),
                       capture_output=True, text=True, cwd=raiz, env=env)
    return r.stdout + r.stderr


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--perfil", choices=PERFILES, required=True,
                    help="entorno declarado del job que la ejecuta")
    ap.add_argument("--salida", help="analiza una salida ya capturada, no ejecuta")
    args = ap.parse_args(argv)

    seleccion, decl = declaracion()
    esp = esperados(args.perfil)

    print(f"SUITE DEL CRON - perfil {args.perfil} - saltos esperados: {esp}")
    print(f"  plano de DATOS: {len(seleccion)} entrada(s) declarada(s) en "
          f"contrato.json::ci_cron.cron_ejecuta")
    if decl.get("por_que_no_fetch_depth_0"):
        print("  el cron NO usa fetch-depth: 0 a proposito -- no valida gobernanza")

    if not seleccion:
        print(f"  {CRON_SIN_SELECCION}: el contrato no declara que ejecutar; "
              f"la ausencia de declaracion nunca se interpreta como 'todo'")
        print("RESULTADO: FAIL")
        return 1

    salida = (open(args.salida, encoding="utf-8").read() if args.salida
              else ejecutar(seleccion))
    ok, codigo, cifras = _pr.evaluar(salida, esp)      # la REGLA, sin duplicar

    if cifras:
        print(f"  tests {cifras['tests']} . skipped {cifras['skipped']} . "
              f"errors {cifras['errors']} . failures {cifras['failures']}")
    if codigo == _pr.SUITE_SKIPS_INESPERADOS:
        print(f"  {codigo}: se saltaron {cifras['skipped']} y el perfil "
              f"{args.perfil} declara {esp}. Un salto no declarado no es cobertura")
    elif codigo:
        print(f"  {codigo}")
    print(f"RESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
