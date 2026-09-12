# -*- coding: utf-8 -*-
"""Autoridad de la suite en el gate de PR -- DF-6 (S0.2).

NO CONTIENE NINGUN NUMERO. El numero de saltos esperados vive en
`contrato.json::ci_pr.skips_esperados` y aqui se LEE. Si este modulo o el
workflow llegaran a llevar el numero como dato, seria una segunda copia -- el
mismo defecto que DF-1 corrigio con la lista de arboles.

QUE COMPRUEBA, y las tres cosas son necesarias:

    0 fallos          un test rojo es un PR rojo
    0 errores         un ImportError no es un salto: es el gate roto
    saltos == declarados

La tercera es la que elimina el PASS SILENCIOSO, y es la razon de que la
opcion B sea aceptable. Un PR verde que hubiese saltado 187 tests sin avisar
seria peor que el fallo original de DF-6: parece cobertura y no lo es. Aqui la
ausencia esta DECLARADA y verificada, que es el invariante del proyecto --
`UNKNOWN` != `NEUTRAL`, ausencia != cero.

Falla en los DOS sentidos, a proposito:
  un test de parquet nuevo sin declarar       -> saltos > declarados -> FAIL
  un test que deja de saltarse (o pyarrow en
  el runner del PR, que no debe estar)        -> saltos < declarados -> FAIL

El reparto que T9 fijo sigue intacto: el PR cubre codigo y contexto SIN
dependencias; el job `verificar` del cron diario instala pyarrow con version
fijada y corre la suite completa mas `qa.py --require-parquet`.
"""
import os
import re
import subprocess
import sys

import estado as _estado

RAIZ = _estado.RAIZ

SUITE_SKIPS_INESPERADOS = "SUITE_SKIPS_INESPERADOS"
SUITE_CON_ERRORES = "SUITE_CON_ERRORES"
SUITE_NO_INTERPRETABLE = "SUITE_NO_INTERPRETABLE"
SUITE_SIN_DECLARACION = "SUITE_SIN_DECLARACION"

_RAN = re.compile(r"(?m)^Ran (\d+) tests?")
_SKIP = re.compile(r"skipped=(\d+)")
_ERR = re.compile(r"errors=(\d+)")
_FAIL = re.compile(r"failures=(\d+)")
_OK = re.compile(r"(?m)^OK\b")


def declaracion(contrato=None):
    """(esperados, decl). Sin declaracion NO se asume nada."""
    c = contrato or _estado.cargar_contrato()
    d = c.get("ci_pr") or {}
    return d.get("skips_esperados"), d


def leer(salida):
    """Cifras de una salida de unittest. Funcion PURA: es la que se muta."""
    m = _RAN.search(salida)
    if not m:
        return None
    return {
        "tests": int(m.group(1)),
        "skipped": int(_SKIP.search(salida).group(1)) if _SKIP.search(salida) else 0,
        "errors": int(_ERR.search(salida).group(1)) if _ERR.search(salida) else 0,
        "failures": int(_FAIL.search(salida).group(1)) if _FAIL.search(salida) else 0,
        "ok": bool(_OK.search(salida)),
    }


def evaluar(salida, esperados):
    """(ok, codigo, cifras). La REGLA, en un solo sitio y sin numeros."""
    if esperados is None:
        return False, SUITE_SIN_DECLARACION, None
    cifras = leer(salida)
    if cifras is None:
        return False, SUITE_NO_INTERPRETABLE, None
    if cifras["errors"] or cifras["failures"]:
        return False, SUITE_CON_ERRORES, cifras
    if cifras["skipped"] != esperados:
        return False, SUITE_SKIPS_INESPERADOS, cifras
    return True, None, cifras


def _hay_pyarrow():
    """Solo para DIAGNOSTICO del mensaje. La regla no depende de esto."""
    sys.path.insert(0, os.path.join(RAIZ, "engine", "contract"))
    try:
        import storage
        return storage.hay_pyarrow()
    except Exception:                                        # noqa: BLE001
        return False


def ejecutar(raiz=RAIZ):
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                       capture_output=True, text=True, cwd=raiz)
    return r.stdout + r.stderr


def main(argv=None):
    esperados, decl = declaracion()
    salida = open(argv[0], encoding="utf-8").read() if argv else ejecutar()
    ok, codigo, cifras = evaluar(salida, esperados)

    print(f"SUITE DEL PR - saltos esperados: {esperados}")
    if decl.get("motivo"):
        print(f"  motivo declarado: {decl['motivo']}")
    if cifras:
        print(f"  tests {cifras['tests']} . skipped {cifras['skipped']} . "
              f"errors {cifras['errors']} . failures {cifras['failures']}")
    if codigo == SUITE_SKIPS_INESPERADOS:
        print(f"  {codigo}: se saltaron {cifras['skipped']} y se declararon "
              f"{esperados}. Un salto no declarado no es cobertura")
        if cifras["skipped"] < esperados and _hay_pyarrow():
            print("  DIAGNOSTICO: este entorno TIENE pyarrow, asi que los tests "
                  "de parquet no se saltan. No es el entorno del gate de PR, que "
                  "corre sin dependencias -- el FAIL es correcto aqui. Para "
                  "reproducir el PR: PYTHONPATH=<dir con un pyarrow.py que lance "
                  "ImportError>")
    elif codigo:
        print(f"  {codigo}")
    print(f"RESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
