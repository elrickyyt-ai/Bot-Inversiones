"""Mecanismos economicos y reglas de direccion. P5B (2026-09-07).

Vocabulario cerrado de siete mecanismos y las reglas declaradas que los
disparan. NO hay LLM ni NLP: cada regla tiene un rule_id que viaja en el
tramo que produce y se puede volver a ejecutar.

DOS PRINCIPIOS QUE ORDENAN TODO
-------------------------------
1. Una relacion estructural NUNCA basta. `A SUPPLIES B` demuestra que
   existe el vinculo; no demuestra que si la demanda de B sube, el margen
   de A suba. Eso exige la variable que lo determina. Sin ella el tramo
   es UNKNOWN, y el sistema lo dice en vez de rellenarlo.

2. AUSENCIA NO ES EVIDENCIA DE AUSENCIA. Que Knowledge no contenga una
   fila `X SUBSTITUTES Y` significa "no conozco un sustituto declarado",
   no "no existe sustituto". La diferencia decide si PRICING_POWER puede
   estar SUPPORTED o solo PARTIAL. Es la misma invariante que P1b aplico
   a la ausencia de TVL (NO_APLICA distingue "no aplica" de "falta") y
   que P2 aplica con polarity=DENIES. Aqui es la tercera aparicion.

VOCABULARIO DE PREDICADOS
-------------------------
Se usan EXCLUSIVAMENTE los que existen en el vocabulario cerrado de P2:
USES, SUPPLIES, SUBSTITUTES, DEPENDS_ON. En particular NO se usan
CONSUMES ni PRODUCES, y no se mapean a los existentes porque NO son
equivalentes:

    USES     puede ser tecnologia, herramienta o infraestructura
    CONSUMES implica un flujo economico o fisico
    -> "NVIDIA USES CUDA" no es "NVIDIA consume CUDA"

    SUPPLIES es organizacion -> organizacion (a quien vende)
    PRODUCES es organizacion -> producto (que fabrica)
    -> "SUMCO PRODUCES obleas" no dice a quien se las vende

Quedan como candidatos futuros, para cuando un caso real los exija por
el procedimiento de alta de P2. No se reabre P2 ahora.
"""

# --- Mecanismos -------------------------------------------------------------

MECANISMOS = {
    "CUSTOMER_DEMAND": {
        "relacion": "A SUPPLIES B",
        "necesita": ["demand"],
        "puede_producir": ["POSITIVE", "NEGATIVE"],
        "bloqueo": "sin medida de demanda del cliente",
    },
    "INPUT_COST": {
        "relacion": "A USES X  ·  A DEPENDS_ON X",
        "necesita": ["price"],
        "puede_producir": ["POSITIVE", "NEGATIVE"],
        "bloqueo": "sin precio del insumo, o sin saber su peso en el coste total",
    },
    "CAPACITY_CONSTRAINT": {
        "relacion": "A USES P",
        "necesita": ["capacity_utilization"],
        "puede_producir": [],   # no produce signo: habilita PRICING_POWER
        "bloqueo": "sin medida de utilizacion de la capacidad",
    },
    "PRICING_POWER": {
        "relacion": "CAPACITY_CONSTRAINT + comprobacion de sustitucion",
        "necesita": ["capacity_utilization"],
        "puede_producir": ["POSITIVE"],
        "bloqueo": "existe un SUBSTITUTES vigente, o no se sabe si existe",
    },
    "SUBSTITUTION": {
        "relacion": "X SUBSTITUTES Y",
        "necesita": [],
        "puede_producir": ["NEUTRAL"],
        "bloqueo": "el grado de sustituibilidad se declara, no se estima",
    },
    "SUPPLY_SHORTAGE": {
        "relacion": "A SUPPLIES B",
        "necesita": ["inventory"],
        "puede_producir": ["POSITIVE", "NEGATIVE"],
        "bloqueo": "sin medida de escasez",
    },
    "LEAD_TIME": {
        "relacion": "A SUPPLIES B",
        "necesita": ["lead_time"],
        "puede_producir": [],   # es un desplazamiento temporal, no un signo
        "bloqueo": "sin medida de plazo; y v1 no tiene donde colocar el desfase",
    },
}

# No es un mecanismo: es la respuesta correcta a la mayoria de las aristas
# que hay hoy en Knowledge.
NO_MECHANISM = "NO_MECHANISM"

# Predicados que NO transmiten nada economicamente. La identidad y la
# clasificacion situan a una entidad; no le transmiten un efecto. Recorrer
# NVDA ->ISSUED_BY-> nvidia y estampar un signo seria fabricar una
# inferencia donde solo hay un cambio de punto de vista.
SIN_MECANISMO = {
    "ISSUED_BY":    "la accion y la empresa son el mismo sujeto economico visto de dos formas",
    "LISTED_ON":    "donde se negocia el instrumento; cambia liquidez y calendario, no el negocio",
    "DOMICILED_IN": "pertenencia geografica: situa a la entidad, no le transmite un efecto",
    "CLASSIFIED_AS": "clasificacion sectorial: situa a la entidad, no le transmite un efecto",
    "EXPOSED_TO":   "relacion PROVISIONAL que procede de una regla del propio motor aplicada "
                    "a todos los activos por igual; construir un signo sobre ella heredaria "
                    "esa arbitrariedad",
}

# --- Variables ---------------------------------------------------------------

# Lo que un mecanismo necesita observar. NINGUNA de estas existe en
# Evidence v1: medido, sus tres dominios (tecnico, fundamental, noticias)
# no contienen ninguna metrica de demanda, capacidad, coste de insumo,
# inventario ni plazo.
VARIABLES_MECANISMO = ("demand", "capacity_utilization", "price", "inventory", "lead_time")

# Lo que un tramo puede afectar.
VARIABLES_AFECTADAS = ("demand", "revenue", "cost", "margin", "pricing_power", "none")

DIRECCIONES = ("POSITIVE", "NEGATIVE", "NEUTRAL", "UNKNOWN")
# DIVERGENT solo existe a nivel de camino: sin el, el resumen obligaria a
# inventar un signo unico para un camino que cambia de signo. Y no se
# llama MIXED porque MIXED ya es un valor de traversal_direction en P5A:
# los tres vocabularios de direccion tienen que ser disjuntos.
DIRECCIONES_CAMINO = DIRECCIONES + ("DIVERGENT",)

SOPORTES = ("SUPPORTED", "PARTIAL", "UNKNOWN", "CONTESTED")

# --- Impulso -----------------------------------------------------------------

# Que variable economica mueve cada tipo de Event de P4. Un Event que no
# aparezca aqui no produce impulso, y su camino entero sale UNKNOWN.
IMPULSO_POR_ACCION = {
    "price_change": "price",
    "volatility_spike": None,   # la volatilidad no es una variable economica de transmision
    # Una opinion publicada NO es un cambio observado en una variable
    # economica. Que un medio afirme una postura no mueve nada.
    "sentiment_assertion": None,
    "announcement": None,       # P4 no extrae que se anuncio
    # Ningun extractor de P4 produce estas dos: existen para las fixtures,
    # mismo patron que ANNOUNCES_ACTION en P4 e INFERRED en Evidence.
    "demand_change": "demand",
    "capacity_change": "capacity_utilization",
}

RULE_VERSION = "p5b/v1"


def impulso_de_evento(evento):
    """(entity_id, variable, direccion) o None si el evento no mueve
    ninguna variable economica que P5B sepa propagar."""
    variable = IMPULSO_POR_ACCION.get(evento.get("action"))
    if variable is None:
        return None
    direccion = evento.get("direction")
    if direccion not in ("UP", "DOWN"):
        return None
    return (evento["primary_entity"], variable, direccion)
