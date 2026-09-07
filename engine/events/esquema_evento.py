"""Event & Claim Layer v1 -- vocabularios y validacion. P4 (2026-09-07).

    SOURCE -> EVIDENCE -> CLAIM -> EVENT CANDIDATE -> EVENT

No toda Evidence es un Event. Una fuente puede afirmar algo sin que el
sistema pueda confirmar que haya ocurrido, y P4 conserva esa diferencia
en vez de aplanarla.

LO QUE P4 NO HACE, Y POR QUE IMPORTA
------------------------------------
P4 NO interpreta texto. Los extractores son REGLAS DECLARADAS Y
AUDITABLES, no analisis de lenguaje: cada claim lleva el nombre y la
version del extractor que la produjo. Un titular como "Ripple Is
Bringing Agentic AI Payments to the XRP Blockchain" contiene un
acontecimiento que este sistema NO sabe extraer, y lo correcto es no
extraerlo en vez de fabricar una tripleta plausible. Esa incapacidad se
mide y se publica en `unknowns`.

P4 tampoco responde "que impacto economico tendra". Eso es Assessment.

REGLA ARQUITECTONICA
--------------------
Un Event puede CONSUMIR Knowledge para resolver entidades, pero jamas
escribirlo. Ni un evento ni una inferencia modifican una relacion
estructural: eso exige nueva fuente -> verificacion -> actualizacion
controlada. Este modulo no tiene ninguna funcion de escritura sobre
knowledge/, y hay un test que lo comprueba.
"""
import datetime

# --- CLAIM -----------------------------------------------------------------

# Vocabulario cerrado y minusculo a proposito: solo lo que un extractor
# declarado sabe producir hoy. Anadir un predicado exige anadir el
# extractor que lo emite.
PREDICADOS = {
    "ASSERTS_SENTIMENT": "un medio afirma una postura sobre una entidad "
                         "(NO dice que la entidad sea alcista: dice que ese medio lo afirma)",
    "MOVED_PRICE":       "el precio de una entidad vario entre dos sesiones consecutivas",
    "VOLATILITY_ROSE":   "la volatilidad historica supero su umbral declarado",
    # NINGUN extractor de v1 emite este predicado a partir de datos
    # reales: hacerlo exigiria leer el contenido de un texto, que P4 no
    # hace. Existe porque el modelo TIENE que poder representar un anuncio
    # cuyo efecto es posterior -- si no, la separacion entre occurred_at y
    # effective_at seria un campo sin uso demostrado -- y porque es la
    # unica forma de probar que una fuente primaria unica puede confirmar.
    # Mismo patron que INFERRED en Evidence: declarado para una necesidad
    # demostrada, no producido todavia.
    "ANNOUNCES_ACTION":  "una fuente anuncia una accion, que puede tener efecto posterior "
                         "(ningun extractor de v1 lo produce: ver tests/fixtures/eventos/)",
}

POLARIDADES = {"AFFIRMS": "la afirmacion sostiene el hecho",
               "DENIES":  "la afirmacion lo niega"}

ESTADOS_CLAIM = {
    "EXTRACTED":  "una regla declarada la produjo a partir de Evidence",
    "UNRESOLVED": "hay evidencia, pero ninguna regla sabe convertirla en una afirmacion",
}

CAMPOS_CLAIM = {
    "claim_id", "evidence_ids", "subject_entity", "predicate", "object_entity",
    "object_value", "temporal_ref", "polarity", "status", "extraction_method",
}

# --- EVENT -----------------------------------------------------------------

TIPOS_EVENTO = {
    "CORPORATE":    "hechos de una empresa concreta",
    "MACRO":        "indicadores agregados de una region",
    "MONETARY":     "decisiones de politica monetaria",
    "REGULATORY":   "actos de reguladores y legisladores",
    "GEOPOLITICAL": "conflictos, sanciones, tensiones entre estados",
    "MARKET":       "movimientos observados de precio, volumen o volatilidad",
    "SUPPLY_CHAIN": "produccion, capacidad y suministro",
}

# Solo para GEOPOLITICAL: amenazar no es actuar, y tratarlos igual
# convertiria una declaracion en un hecho. No se generaliza al resto de
# tipos porque no hay ningun consumidor que lo pida.
SUBTIPOS = {
    "GEOPOLITICAL": {"THREAT": "se anuncia una accion futura o condicional",
                     "ACTION": "la accion se ha ejecutado",
                     "ESCALATION": "una accion previa se intensifica"},
}

ESTADOS_EVENTO = {
    "CANDIDATE":    "una sola fuente secundaria lo sostiene",
    "CORROBORATED": "dos o mas fuentes independientes secundarias, sin contradiccion",
    "CONFIRMED":    "soporte primario (medicion propia o fuente primaria), sin contradiccion",
    "CONTESTED":    "hay evidencia que lo niega y ninguna primaria la resuelve",
    "REJECTED":     "una fuente primaria lo desmiente",
    "REVISED":      "evidencia posterior cambio su magnitud",
}

DIRECCIONES = {"UP", "DOWN"}

CAMPOS_EVENTO = {
    "event_id", "identity_key", "event_type", "event_subtype", "primary_entity",
    "other_entities", "action", "temporal", "direction", "magnitude", "unit",
    "expected", "actual", "surprise", "claim_ids", "evidence_count",
    "independent_support_count", "primary_support", "contradictory_support",
    "status", "status_reason", "unknowns",
}

# Cuatro relojes distintos. Ninguno se inventa: si no existe, es None.
# Un anuncio sobre una accion futura NO se representa como si la accion
# ya hubiese ocurrido -- occurred_at es cuando se anuncio, effective_at
# cuando aplica, y son campos distintos precisamente para eso.
CAMPOS_TEMPORALES = ("published_at", "occurred_at", "effective_at", "known_at")


class EventError(Exception):
    pass


def _fecha(v):
    if v is None:
        return None
    try:
        return datetime.date.fromisoformat(v[:10])
    except (TypeError, ValueError):
        raise EventError(f"marca temporal no ISO: {v!r}")


def validar_claim(c):
    sobra = set(c) - CAMPOS_CLAIM
    if sobra:
        raise EventError(f"claim: campos no reconocidos {sorted(sobra)}")
    for campo in ("claim_id", "subject_entity", "predicate", "polarity", "status",
                  "extraction_method"):
        if not c.get(campo):
            raise EventError(f"claim {c.get('claim_id')}: falta {campo}")
    if c["predicate"] not in PREDICADOS:
        raise EventError(f"claim {c['claim_id']}: predicado {c['predicate']!r} fuera del vocabulario")
    if c["polarity"] not in POLARIDADES:
        raise EventError(f"claim {c['claim_id']}: polarity {c['polarity']!r} fuera del vocabulario")
    if c["status"] not in ESTADOS_CLAIM:
        raise EventError(f"claim {c['claim_id']}: status {c['status']!r} fuera del vocabulario")
    if not c.get("evidence_ids"):
        raise EventError(f"claim {c['claim_id']}: sin evidence_ids — una afirmacion sin "
                         f"evidencia detras no es una claim")
    if c.get("object_entity") and c.get("object_value") is not None:
        raise EventError(f"claim {c['claim_id']}: object_entity y object_value a la vez")
    tr = c.get("temporal_ref") or {}
    for k in tr:
        if k not in CAMPOS_TEMPORALES:
            raise EventError(f"claim {c['claim_id']}: reloj desconocido {k!r}")
        _fecha(tr[k])
    return True


def validar_evento(e, claims_por_id=None):
    sobra = set(e) - CAMPOS_EVENTO
    if sobra:
        raise EventError(f"evento: campos no reconocidos {sorted(sobra)}")
    for campo in ("event_id", "identity_key", "event_type", "primary_entity",
                  "action", "status", "status_reason"):
        if not e.get(campo):
            raise EventError(f"evento {e.get('event_id')}: falta {campo}")
    if e["event_type"] not in TIPOS_EVENTO:
        raise EventError(f"evento {e['event_id']}: tipo {e['event_type']!r} fuera del vocabulario")
    sub = e.get("event_subtype")
    if sub is not None:
        permitidos = SUBTIPOS.get(e["event_type"])
        if not permitidos:
            raise EventError(f"evento {e['event_id']}: {e['event_type']} no admite subtipo "
                             f"(THREAT/ACTION no son estados universales)")
        if sub not in permitidos:
            raise EventError(f"evento {e['event_id']}: subtipo {sub!r} no valido para {e['event_type']}")
    if e["status"] not in ESTADOS_EVENTO:
        raise EventError(f"evento {e['event_id']}: estado {e['status']!r} fuera del vocabulario")
    if e.get("direction") is not None and e["direction"] not in DIRECCIONES:
        raise EventError(f"evento {e['event_id']}: direction {e['direction']!r} no valida")
    # Magnitud sin unidad no significa nada, y una magnitud inventada para
    # un evento narrativo es peor que ninguna.
    if e.get("magnitude") is not None and not e.get("unit"):
        raise EventError(f"evento {e['event_id']}: magnitude sin unit")
    if not isinstance(e.get("unknowns"), list):
        raise EventError(f"evento {e['event_id']}: unknowns debe ser una lista — "
                         f"un evento tiene que poder declarar lo que no sabe")
    if not e.get("claim_ids"):
        raise EventError(f"evento {e['event_id']}: sin claim_ids")
    if claims_por_id is not None:
        for cid in e["claim_ids"]:
            if cid not in claims_por_id:
                raise EventError(f"evento {e['event_id']}: claim {cid} no existe")
    t = e.get("temporal") or {}
    for k in t:
        if k not in CAMPOS_TEMPORALES:
            raise EventError(f"evento {e['event_id']}: reloj desconocido {k!r}")
    oc, ef = _fecha(t.get("occurred_at")), _fecha(t.get("effective_at"))
    if oc and ef and ef < oc:
        raise EventError(f"evento {e['event_id']}: effective_at anterior a occurred_at")
    pu, kn = _fecha(t.get("published_at")), _fecha(t.get("known_at"))
    if pu and kn and kn < pu:
        raise EventError(f"evento {e['event_id']}: known_at anterior a published_at")
    if e["independent_support_count"] > e["evidence_count"]:
        raise EventError(f"evento {e['event_id']}: mas fuentes independientes que evidencias")
    return True
