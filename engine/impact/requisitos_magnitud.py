"""Que necesita cada mecanismo para dar magnitud -- P6 v1 (2026-09-07).

Fichero de DECLARACION, hermano de `contract/cadencias.py` y
`requirements/catalogo.py`. Se mantiene a mano y nada se deduce en
tiempo de ejecucion.

LA CONCLUSION QUE ESTE FICHERO HACE EJECUTABLE
----------------------------------------------
    No todos los mecanismos que explican DIRECCION pueden producir
    MAGNITUD.

Es el error mas comun en sistemas causales: dar por hecho que si
podemos describir la causalidad podemos cuantificarla. Aqui esta
separado por declaracion, no por casualidad.

Y la distincion importa en los dos sentidos:

    NOT_QUANTIFIABLE            no da magnitud POR SU NATURALEZA
    CONDITIONALLY_QUANTIFIABLE  podria darla; hoy le faltan piezas

Un mecanismo NOT_QUANTIFIABLE no se arregla consiguiendo mas datos. Uno
CONDITIONALLY_QUANTIFIABLE si, y por eso son dos estados y no uno.
"""
import os
import sys

_R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_p = os.path.join(_R, "engine", "causal")
if _p not in sys.path:
    sys.path.insert(0, _p)

import mecanismos as M  # noqa: E402

# NINGUN mecanismo es QUANTIFIABLE en v1. El valor existe en el
# vocabulario porque describe un estado alcanzable, no porque hoy se
# alcance: es la diferencia entre un vocabulario y un inventario.
CAPACIDAD = {
    "CUSTOMER_DEMAND": ("CONDITIONALLY_QUANTIFIABLE",
        "el cambio de demanda del cliente se puede medir, pero traducirlo a "
        "ingreso del proveedor exige saber que fraccion de sus ingresos viene "
        "de ese cliente"),
    "INPUT_COST": ("CONDITIONALLY_QUANTIFIABLE",
        "el cambio de precio del insumo se puede medir; su efecto en el margen "
        "exige el peso del insumo en la base de coste y cuanto se repercute"),
    "CAPACITY_CONSTRAINT": ("NOT_QUANTIFIABLE",
        "no produce signo ni magnitud por diseno: habilita PRICING_POWER. "
        "Cuantificar 'estar restringido' no significa nada por si solo"),
    "PRICING_POWER": ("NOT_QUANTIFIABLE",
        "necesitaria una elasticidad precio, y no hay ninguna fuente para ella. "
        "Una elasticidad inventada convierte todo el motor en decoracion, asi "
        "que en v1 este mecanismo da signo y nunca numero"),
    "SUBSTITUTION": ("NOT_QUANTIFIABLE",
        "el grado de sustituibilidad se declara, no se estima (P5B, literal). "
        "Sin grado no hay magnitud"),
    "SUPPLY_SHORTAGE": ("CONDITIONALLY_QUANTIFIABLE",
        "la escasez se puede medir contra un inventario normal; su efecto exige "
        "que fraccion del suministro esta afectada"),
    "LEAD_TIME": ("NOT_QUANTIFIABLE",
        "aporta HORIZONTE, no magnitud. P5B lo dejo escrito: 'es un "
        "desplazamiento temporal, no un signo, y v1 no tiene donde colocar el "
        "desfase'. P6 es donde"),
    M.NO_MECHANISM: ("NOT_QUANTIFIABLE",
        "la arista no transmite nada economicamente"),
}

# Entradas minimas, por mecanismo. `observada` es lo que P5B ya declara
# en MECANISMOS[*]['necesita']; el resto es lo que P6 anade y hoy no
# existe en ninguna parte del sistema.
ENTRADAS = {
    "CUSTOMER_DEMAND": {
        "observada": ["demand"],
        "linea_base": "demanda normal del cliente",
        "materialidad": "% de los ingresos del proveedor que vienen de ese cliente",
        "coeficiente": "paso de demanda a ingreso",
        "aporta": ["direccion", "magnitud"],
    },
    "INPUT_COST": {
        "observada": ["price"],
        "linea_base": "precio normal del insumo",
        "materialidad": "peso del insumo en la base de coste",
        "coeficiente": "paso de coste a margen; distinto de 1 porque depende de "
                       "cuanto se puede repercutir",
        "aporta": ["direccion", "magnitud"],
    },
    "CAPACITY_CONSTRAINT": {
        "observada": ["capacity_utilization"],
        "linea_base": "utilizacion normal del recurso",
        "materialidad": None,
        "coeficiente": None,
        "aporta": [],
    },
    "PRICING_POWER": {
        "observada": ["capacity_utilization"],
        "linea_base": "utilizacion normal del recurso",
        "materialidad": "cuanto del negocio pasa por ese recurso",
        "coeficiente": "elasticidad precio — SIN FUENTE IDENTIFICADA",
        "aporta": ["direccion"],
    },
    "SUBSTITUTION": {
        "observada": [],
        "linea_base": None,
        "materialidad": None,
        "coeficiente": "grado de sustituibilidad — se declara, no se estima",
        "aporta": ["direccion"],
    },
    "SUPPLY_SHORTAGE": {
        "observada": ["inventory"],
        "linea_base": "inventario normal",
        "materialidad": "% del suministro afectado",
        "coeficiente": "paso de escasez a precio o a volumen",
        "aporta": ["direccion", "magnitud"],
    },
    "LEAD_TIME": {
        "observada": ["lead_time"],
        "linea_base": "plazo normal",
        "materialidad": None,
        "coeficiente": None,
        "aporta": ["horizonte"],
    },
    M.NO_MECHANISM: {
        "observada": [], "linea_base": None, "materialidad": None,
        "coeficiente": None, "aporta": [],
    },
}

# Coeficientes de transmision declarados, con su fuente. VACIO en v1, y
# esa es la decision de la fase: sin entrada aqui, no hay magnitud.
# Cuando alguna exista, sera {(mecanismo, relationship_id): (valor,
# origen, referencia)} con origen en {OBSERVED, DECLARED} -- nunca
# ESTIMATED, que es de la futura capa de modelo.
COEFICIENTES = {}

# Materialidad declarada por relacion. VACIO en v1: ninguna relacion de
# Knowledge lleva peso. Es la deuda registrada de P5C hecha ejecutable --
# rel:0046 dice que TSMC suministra a NVIDIA y no dice en que proporcion.
MATERIALIDAD = {}


# Lineas base declaradas por relacion. VACIA en v1. Una linea base no es
# "el valor anterior": es el nivel normal contra el que un cambio
# significa algo, y decidirlo es una declaracion, no un calculo.
LINEAS_BASE = {}


def linea_base(relationship_id):
    return LINEAS_BASE.get(relationship_id)


def capacidad(mecanismo):
    return CAPACIDAD.get(mecanismo, ("NOT_QUANTIFIABLE", "mecanismo no declarado"))


def entradas(mecanismo):
    return ENTRADAS.get(mecanismo, ENTRADAS[M.NO_MECHANISM])


def coeficiente(mecanismo, relationship_id):
    return COEFICIENTES.get((mecanismo, relationship_id))


def materialidad(relationship_id):
    return MATERIALIDAD.get(relationship_id)
