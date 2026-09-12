"""Evidence v1 -- esquema, vocabularios y validacion. P3 (2026-09-06).

Evidence es una VISTA DERIVADA y regenerable del Data Contract y de
data/news/. No sustituye a nada, no es fuente de verdad de nada y ningun
motor la consume todavia. Su unico trabajo en v1 es demostrar que se
pueden representar observaciones de fuentes distintas sin perder
semantica, identidad, temporalidad, procedencia, naturaleza
epistemologica ni trazabilidad.

POR QUE NO ES UN FICHERO POR DEFECTO
------------------------------------
507.330 filas de metricas producen ~200 MB de JSON. Evidence es una
FUNCION que genera filas; materializarla es opcional
(construir.py --materializar) y va a data/evidence/, gitignored, como
data/current/ y data/coverage.json. Un artefacto derivado que se versiona
deja de ser derivado.

LA COLISION DE 'nature' CON KNOWLEDGE, Y POR QUE ES SEGURA
----------------------------------------------------------
engine/knowledge/modelo.py usa nature = {STRUCTURAL, ASSERTED} y PROHIBE
INFERRED. Aqui nature = {MEASURED, DERIVED, INFERRED} y INFERRED SI es
legitimo. Es el mismo nombre de campo con dos vocabularios distintos --
exactamente la forma del defecto de source_priority que encontro P0.

Lo que lo hace seguro es que los dos conjuntos son DISJUNTOS: un valor
identifica sin ambiguedad a que capa pertenece. Eso no es una
coincidencia afortunada, es una invariante, y test_knowledge/test_evidence
la mantienen. Si alguien anadiera ASSERTED aqui o DERIVED alli, el test
falla.

Y la direccion sigue siendo unica: una fila de Evidence con
nature=INFERRED NO puede convertirse en una relacion de Knowledge. La
inferencia analitica vive aqui; el conocimiento estructural vive alli.
"""
import datetime

# --- Vocabularios cerrados -------------------------------------------------

# Que papel juega la entidad en esta observacion.
ROLES = {
    "SUBJECT":   "la observacion mide a esta entidad",
    "MENTIONED": "la observacion la nombra, pero no la mide",
}

CLAIM_TYPES = {
    "OBSERVATION": "un hecho observado o medido",
    "ASSERTION":   "algo que una fuente afirma, sin que este sistema lo haya observado",
}

# MEASURED / DERIVED / INFERRED -- clasificacion epistemologica ya usada en
# el proyecto desde P0. INFERRED esta declarado para P5 (propagacion
# causal); NINGUN adaptador de P3 lo produce.
NATURES = {
    "MEASURED": "leido de la fuente sin transformarlo",
    "DERIVED":  "calculado a partir de otras observaciones con un metodo conocido",
    "INFERRED": "conclusion analitica de este sistema — ningun adaptador de P3 la emite",
}

GRANULARIDADES = {
    "INSTANT":  "un momento concreto (una noticia)",
    "DAY":      "un dia o sesion de mercado",
    "MONTH":    "un mes de referencia",
    "QUARTER":  "un trimestre reportado",
}

# La escala de procedencia NO se unifica. P0 demostro que source_priority
# significa cosas distintas segun el dominio: FRED=1 y Reuters=2 no son
# comparables aunque compartan columna y rango. Evidence conserva el rango
# original Y el nombre de la escala a la que pertenece.
# method vs method_ref: la comprobacion de reversibilidad demostro que un
# solo campo no puede con los dos. `method` dice QUE se hizo ("media movil
# simple de 20 sesiones sobre el precio de cierre"); `method_ref` es el
# puntero a donde esta documentado, que es lo que el Data Contract guarda
# en calculation_method ("engine/crypto/README.md"). Meter los dos en
# `method` obligaba a descartar uno, y descartar el del contrato rompia la
# reconstruccion 1:1.

SOURCE_SCALES = {
    "market_data_priority": "schema.py SOURCE_PRIORITY -- autoridad del proveedor de una serie (1-2 en uso)",
    "journalistic_tier":    "news/sources.py TIER_BY_DOMAIN -- credibilidad de un medio (1-5)",
}

CAMPOS = [
    "evidence_id", "entity_id", "entity_role", "claim_type", "domain", "metric",
    "concept_id", "value_num", "value_text", "unit", "occurred_at", "known_at",
    "granularity", "source", "source_scale", "source_rank", "source_ref",
    "nature", "method", "method_ref", "derived_from", "relevance", "headline", "summary",
    "origin_confidence_pct", "origin_data_quality_pct",
]

OBLIGATORIOS = {
    "evidence_id", "entity_id", "entity_role", "claim_type", "domain", "metric",
    "occurred_at", "known_at", "granularity", "source", "source_scale",
    "source_rank", "nature", "derived_from",
}


class EvidenceError(Exception):
    pass


def _es_fecha(v):
    try:
        datetime.date.fromisoformat(v)
        return True
    except (TypeError, ValueError):
        return False


def _instante(v):
    """Acepta fecha o marca de tiempo ISO. Devuelve date para comparar."""
    if not isinstance(v, str):
        return None
    try:
        return datetime.date.fromisoformat(v[:10])
    except ValueError:
        return None


def validar_fila(row):
    """Lanza EvidenceError con el primer incumplimiento. Devuelve True."""
    sobra = set(row) - set(CAMPOS)
    if sobra:
        raise EvidenceError(f"campos no reconocidos: {sorted(sobra)}")
    faltan = {c for c in OBLIGATORIOS if row.get(c) is None}
    if faltan:
        raise EvidenceError(f"faltan campos obligatorios: {sorted(faltan)}")

    if row["entity_role"] not in ROLES:
        raise EvidenceError(f"entity_role fuera del vocabulario: {row['entity_role']!r}")
    if row["claim_type"] not in CLAIM_TYPES:
        raise EvidenceError(f"claim_type fuera del vocabulario: {row['claim_type']!r}")
    if row["nature"] not in NATURES:
        raise EvidenceError(f"nature fuera del vocabulario: {row['nature']!r}")
    if row["granularity"] not in GRANULARIDADES:
        raise EvidenceError(f"granularity fuera del vocabulario: {row['granularity']!r}")
    if row["source_scale"] not in SOURCE_SCALES:
        raise EvidenceError(f"source_scale fuera del vocabulario: {row['source_scale']!r}")

    # value_num XOR value_text: una observacion tiene UN valor, numerico o
    # textual. Las dos a la vez seria ambiguo; ninguna, una fila vacia.
    tiene_num = row.get("value_num") is not None
    tiene_txt = row.get("value_text") is not None
    if tiene_num and tiene_txt:
        raise EvidenceError(f"{row['evidence_id']}: value_num y value_text a la vez")
    if not tiene_num and not tiene_txt:
        raise EvidenceError(f"{row['evidence_id']}: sin value_num ni value_text")

    # Temporalidad: no se puede saber algo antes de que ocurra.
    oc, kn = _instante(row["occurred_at"]), _instante(row["known_at"])
    if oc is None:
        raise EvidenceError(f"{row['evidence_id']}: occurred_at no es una marca ISO")
    if kn is None:
        raise EvidenceError(f"{row['evidence_id']}: known_at no es una marca ISO")
    if oc > kn:
        raise EvidenceError(
            f"{row['evidence_id']}: occurred_at ({row['occurred_at']}) posterior a "
            f"known_at ({row['known_at']}) — no se puede saber algo antes de que ocurra")

    if not isinstance(row["derived_from"], list):
        raise EvidenceError(f"{row['evidence_id']}: derived_from debe ser una lista")
    if row["nature"] == "MEASURED" and row["derived_from"]:
        raise EvidenceError(
            f"{row['evidence_id']}: nature=MEASURED con derived_from no vacio — "
            f"si se calcula a partir de algo, no es una medicion directa")

    rel = row.get("relevance")
    if rel is not None and not (0 <= rel <= 1):
        raise EvidenceError(f"{row['evidence_id']}: relevance fuera de [0,1]: {rel}")
    return True


def validar(filas, ids_conocidos=None):
    """Valida un lote y comprueba que derived_from resuelve. Devuelve la
    lista de incidencias."""
    errores = []
    ids = set(ids_conocidos or ())
    vistos = set()
    for r in filas:
        try:
            validar_fila(r)
        except EvidenceError as e:
            errores.append(str(e))
            continue
        if r["evidence_id"] in vistos:
            errores.append(f"evidence_id duplicado: {r['evidence_id']}")
        vistos.add(r["evidence_id"])
        ids.add(r["evidence_id"])
    for r in filas:
        for origen in r.get("derived_from") or []:
            if origen not in ids:
                errores.append(f"{r['evidence_id']}: derived_from apunta a {origen}, "
                               f"que no existe en Evidence")
    return errores
