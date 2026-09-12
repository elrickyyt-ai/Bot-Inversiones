# -*- coding: utf-8 -*-
"""Lectura del contrato de contexto y de la superficie de estado vigente.

ANDAMIAJE (BLOCK 1A). Solo carga y parsea: no resuelve fuentes canonicas
ni valida nada. Esa es la parte que la bala trazadora tiene que hacer
aparecer, y por eso no esta aqui.
"""
import json
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRATO = os.path.join(RAIZ, "contexto", "contrato.json")

# Los bloques de la superficie, EN ORDEN. Es un contrato: el validador exige
# estos y exactamente estos. S0.3 anade ACTIVE BLOCK, OPEN DEBTS y CONTINUITY
# RULES -- los tres cubren lo que NO se puede deducir de nada (que bloque esta
# activo y sobre que rama, que deuda bloquea, y en que orden se recupera el
# estado). Los cinco anteriores no cambian.
BLOQUES_SUPERFICIE = ("CURRENT STATE", "ACTIVE BLOCK", "CANONICAL REFERENCES",
                      "ACTIVE DECISIONS", "OPEN DEBTS", "INVARIANTS",
                      "CONTINUITY RULES", "HISTORICAL POINTERS")


def cargar_contrato(path=CONTRATO):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def consultas(contrato=None):
    return (contrato or cargar_contrato())["state_queries"]


def ruta_superficie(contrato=None):
    return os.path.join(RAIZ, (contrato or cargar_contrato())["superficie"])


def texto_superficie(contrato=None):
    with open(ruta_superficie(contrato), encoding="utf-8") as fh:
        return fh.read()


def bloques(texto):
    """Devuelve {titulo: cuerpo} de los encabezados de nivel 2."""
    partes = re.split(r"(?m)^##\s+(.+?)\s*$", texto)
    return {partes[i].strip(): partes[i + 1] for i in range(1, len(partes), 2)}
