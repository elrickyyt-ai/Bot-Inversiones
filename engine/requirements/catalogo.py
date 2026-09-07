"""Catalogo declarado de observables -- P5D (2026-09-07).

Fichero de DECLARACION, hermano de `engine/contract/cadencias.py`: se
mantiene a mano, cada entrada cuesta una linea con su justificacion, y
nada de lo que hay aqui se deduce en tiempo de ejecucion.

Existe por una regla concreta:

    Una metrica NO es la variable que necesita el mecanismo
    hasta que alguien lo declara aqui, y lo justifica.

El ejemplo que motiva la regla: `revenue` de NVIDIA NO debe convertirse
automaticamente en `demand(org:nvidia)`. Puede ser un proxy -- y de
hecho lo es -- pero la relacion tiene que quedar escrita COMO proxy,
con su confusor, para que ningun consumidor posterior la lea como una
medicion directa. Un `MEASURES` mal puesto aqui se propaga como un
hecho hasta el final de la cadena causal sin que nadie lo vuelva a
mirar.
"""

# --- Concepto por variable ---------------------------------------------------
#
# NINGUNA de las cinco variables de mecanismo tiene hoy un concepto
# declarado en knowledge/concepts/ (que solo tiene tres: inflation_yoy,
# policy_rate, percentil_en_ventana). Eso es una ausencia MEDIDA, no un
# hueco por rellenar: declarar un concepto vacio para que la casilla no
# quede a null seria exactamente el error que este proyecto lleva diez
# fases evitando. Mismo criterio que CONCEPTO_DE_METRICA en
# engine/evidence/adaptadores.py, donde 36 metricas tienen concept_id
# null a proposito.
CONCEPTO_DE_VARIABLE = {
    "demand": None,
    "capacity_utilization": None,
    "price": None,
    "inventory": None,
    "lead_time": None,
}


# --- Observables candidatos --------------------------------------------------
#
# Clave: (variable, tipo de entidad). Valor: lista de candidatas, en
# orden de preferencia. Una candidata `MEASURES` resuelve el requisito;
# una `PROXY` como mucho lo deja PARTIAL, y esa degradacion la aplica el
# validador, no la buena voluntad de quien lo lea.
OBSERVABLES = {
    ("price", "security"): [
        {"metric": "precio", "domain": "tecnico", "relation": "MEASURES",
         "justification": "el precio de cierre ES el precio del instrumento, en su "
                          "divisa declarada en DimAsset"},
    ],

    # La entrada que motiva todo el fichero.
    #
    # El usuario listo cinco observables posibles para la demanda de una
    # empresa: revenue, revenue de centros de datos, unidades enviadas,
    # pedidos y cartera de pedidos. De esos cinco, este sistema tiene UNO
    # y ademas en variacion, no en nivel: `revenue_growth_yoy_pct`, de
    # Alpha Vantage. Los otros cuatro no existen en el contrato y por eso
    # no aparecen aqui: un catalogo de candidatas que no se pueden leer
    # seria una lista de deseos, no una declaracion.
    ("demand", "organization"): [
        {"metric": "revenue_growth_yoy_pct", "domain": "fundamental", "relation": "PROXY",
         "justification": "el ingreso se mueve con la demanda y es lo unico parecido "
                          "que el contrato tiene hoy para una empresa",
         "confounder": "ingreso = precio x volumen. Una subida del ingreso puede venir "
                       "enteramente del precio con demanda plana, o incluso cayendo. "
                       "Ademas es interanual y trimestral: no distingue un cambio de "
                       "demanda de un efecto de comparacion contra el ano anterior"},
    ],
}

# Variables x entidad declaradas explicitamente como NO APLICABLES, con
# su motivo. Hoy VACIO, y eso importa: significa que ningun requisito
# puede salir NOT_APPLICABLE. La ausencia de dato es MISSING; degradarla
# a "no aplica" convertiria un hueco en una respuesta.
#
# El analogo de esta tabla en P1b (cadencias.NO_APLICA) si tiene
# entradas: el TVL de BTC y XRP no aplica porque no tienen cadena DeFi,
# y eso esta comprobado. Aqui no hay nada comprobado todavia.
NO_APLICA_VARIABLE = {
    # ("capacity_utilization", "sec:BTC"): "motivo comprobado, con su fuente",
}


def dominios_metricas_declaradas():
    """(dominio, metrica) de todas las candidatas del catalogo.

    Existe por un fallo real cometido al escribir este fichero: la
    candidata de `price` se declaro sobre el dominio "technical" cuando
    el contrato lo llama "tecnico". El resolutor no fallaba -- devolvia
    MISSING con el motivo CANDIDATE_WITHOUT_DATA, o sea presentaba una
    errata del catalogo como si fuera un hueco de datos, que es
    justamente la confusion que toda esta capa existe para impedir.
    `tests/test_requisitos.py` comprueba que cada par existe de verdad en
    cadencias.CADENCIAS.
    """
    return {(c["domain"], c["metric"]) for cs in OBSERVABLES.values() for c in cs}


def concepto(variable):
    return CONCEPTO_DE_VARIABLE.get(variable)


def variable_declarada(variable):
    return variable in CONCEPTO_DE_VARIABLE


def candidatas(variable, tipo_entidad):
    return list(OBSERVABLES.get((variable, tipo_entidad), ()))


def no_aplica(variable, entity_id):
    return NO_APLICA_VARIABLE.get((variable, entity_id))
