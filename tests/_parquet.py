# -*- coding: utf-8 -*-
"""Guarda de PyArrow para la suite -- DF-6 (S0.2).

EL PROBLEMA QUE RESUELVE
------------------------
`.github/workflows/verificar-contexto.yml` declara «SIN DEPENDENCIAS: Python
estandar puro» y ejecuta la suite completa. Pero 36 clases de 11 ficheros leen
`data/history/**.parquet` a traves de `engine/contract/storage.py`, que importa
pyarrow de forma perezosa. En un runner limpio eso daba **43 errores**, asi que
el gate de PR construido en T9 fallaba de fabrica. No se detecto nunca porque
el repositorio no habia tenido ni un pull request.

DECISION: opcion B
------------------
El PR sigue SIN dependencias, y los tests que necesitan parquet se saltan de
forma DECLARADA. La cobertura de parquet no se pierde, se retrasa: el job
`verificar` del cron diario si instala pyarrow (con version fijada) y corre la
suite completa mas `qa.py --require-parquet`. Ese reparto es el que T9 documento
a proposito.

EL SALTO SILENCIOSO SE ELIMINA POR CONSTRUCCION
-----------------------------------------------
Un PR verde que hubiese saltado tests sin avisar seria peor que el fallo
original. Por eso `contrato.json::ci_pr.skips_esperados` declara el numero y el
workflow FALLA si el numero real no coincide: un test de parquet nuevo sin
declarar rompe el PR, y un test que deja de saltarse, tambien. Es el invariante
del proyecto aplicado aqui -- `UNKNOWN` != `NEUTRAL`, ausencia != cero: no es
"se salto algo", es "se salto exactamente esto, y esta declarado".

POR QUE POR CLASE Y NO POR MODULO
---------------------------------
Saltar los 11 modulos enteros habria sido una linea por fichero, pero habria
perdido cobertura REAL del PR: de las 36 clases afectadas, esos mismos ficheros
contienen otras 38 que funcionan perfectamente sin pyarrow. Se marca exactamente
lo que lee parquet.

UNA SOLA AUTORIDAD PARA EL PREDICADO: `storage.hay_pyarrow()`. Este modulo no
comprueba la disponibilidad por su cuenta -- la delega, igual que hace
`test_storage_parquet.py`.
"""
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_CONTRATO_DIR = os.path.join(RAIZ, "engine", "contract")
if _CONTRATO_DIR not in sys.path:
    sys.path.insert(0, _CONTRATO_DIR)

import storage  # noqa: E402

HAY_PYARROW = storage.hay_pyarrow()

RAZON = ("PyArrow no disponible: este test lee data/history/**.parquet. "
         "Declarado en contrato.json::ci_pr.skips_esperados; la cobertura de "
         "parquet la da el job `verificar` del cron diario, no el PR (T9)")

# Decorador de CLASE. Se aplica solo a las que leen parquet, nunca al modulo
# entero: ver "POR QUE POR CLASE Y NO POR MODULO" arriba.
requiere_parquet = unittest.skipUnless(HAY_PYARROW, RAZON)
