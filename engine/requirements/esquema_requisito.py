"""DataRequirement -- P5D (2026-09-07).

    P5B dice QUE le falta.  P5D dice SI existe, DONDE y CON QUE CALIDAD.

P5B ya producia lo mas valioso que tiene el motor causal hoy:

    requires_evidence = ["demand(org:nvidia)", "capacity_utilization(tech:cowos)"]

Eso es una cadena de texto dentro de un tramo. P5D la convierte en una
especificacion resoluble:

    requisito -> concepto -> metrica(s) candidata(s) -> fuente
             -> disponibilidad -> frescura

y la responde con los MISMOS cinco estados que P1b ya usa para cobertura.
No se inventa un vocabulario paralelo: es la misma pregunta ("existe el
dato?") sobre un sujeto distinto (un requisito de mecanismo en vez de un
par activo x dominio), asi que se importa de `cadencias`, no se copia.

TRES REGLAS QUE EL VALIDADOR HACE CUMPLIR
-----------------------------------------
1. Una metrica NO es la variable que necesita el mecanismo hasta que
   alguien lo declara. `revenue` no se convierte en `demand` porque
   ambos suban: la relacion se declara con su justificacion o no existe.
2. Un requisito resuelto SOLO por proxy no puede llegar a AVAILABLE.
   Como maximo PARTIAL. Es la misma regla que P5B aplica a un signo que
   depende de un supuesto no verificado.
3. NOT_APPLICABLE exige declaracion. La ausencia de dato NO degrada a
   "no aplica": eso convertiria un hueco en una respuesta.

LA DISTINCION QUE ESTA CAPA EXISTE PARA MANTENER
------------------------------------------------
    NO SOURCE            != SOURCE SAYS IT DOES NOT EXIST
    MISSING              != NOT_APPLICABLE
    no lo tenemos           esta declarado que no aplica

Es la tercera vez que aparece el mismo patron en el proyecto (P1b con el
TVL de BTC, P2 con `polarity=DENIES`, P5B con la comprobacion de
sustitucion de tres estados). Aqui se aplica a las fuentes de datos.
"""
import os
import sys

_CONTRACT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contract")
if _CONTRACT not in sys.path:
    sys.path.insert(0, _CONTRACT)

import cadencias  # noqa: E402

# Los dos ejes de P1b, importados y no redefinidos. Si alguien anade un
# estado alli, esta capa lo hereda; si lo copiara, divergirian en
# silencio -- que es exactamente como `source_priority` acabo
# significando dos cosas distintas en P0.
DISPONIBILIDAD = cadencias.ESTADOS_COBERTURA
FRESCURA = cadencias.ORDEN_FRESCURA

# Como se relaciona una metrica del contrato con la variable que el
# mecanismo necesita. No hay un tercer valor "quiza": una metrica que no
# esta en el catalogo simplemente no es candidata.
RELACIONES = {
    "MEASURES": "la metrica ES la variable, en su unidad canonica",
    "PROXY":    "la metrica se mueve con la variable pero NO es la variable; "
                "la relacion se declara con su justificacion y su confusor",
}
SOLO_PROXY_MAXIMO = "PARTIAL"

# Por que un requisito no se puede resolver. Vocabulario cerrado para que
# "no se sabe" no sea siempre la misma frase vaga.
MOTIVOS = {
    "ENTITY_NOT_DECLARED":  "la entidad no existe en Knowledge: no hay ni a quien preguntar",
    "NO_OBSERVABLE":        "la entidad no tiene ningun observable en este sistema "
                            "(ni asset_id propio ni un valor que la represente)",
    "NO_CANDIDATE_METRIC":  "ninguna metrica del contrato esta declarada para esta variable",
    "CANDIDATE_WITHOUT_DATA": "la metrica candidata esta declarada pero no tiene filas "
                              "para esta entidad",
    "ONLY_PROXY":           "solo se resuelve por proxy declarado, nunca por medicion directa",
    "DECLARED_NOT_APPLICABLE": "declarado explicitamente como no aplicable, con motivo",
}

CAMPOS = {
    "requirement_id", "variable", "entity_id", "entity_type", "concept_id",
    "concept_status", "observable_asset_id", "candidates", "availability",
    "freshness", "resolved_by", "blocking_for", "reasons", "unknowns",
}
CAMPOS_CANDIDATA = {"metric", "domain", "relation", "justification", "confounder",
                    "asset_id", "data_as_of", "retrieved_at", "freshness", "presente"}

ESTADOS_CONCEPTO = {
    "DECLARED":   "existe un concept_id en knowledge/concepts/ para esta variable",
    "UNDECLARED": "no existe: declarar un concepto vacio seria peor que no declararlo",
}


class RequirementError(Exception):
    pass


def validar(r):
    """Devuelve la lista de incidencias. Vacia = el requisito es valido."""
    e = []
    donde = f"requisito {r.get('requirement_id')}"
    sobra = set(r) - CAMPOS
    if sobra:
        e.append(f"{donde}: campos no reconocidos {sorted(sobra)}")
    faltan = CAMPOS - set(r)
    if faltan:
        e.append(f"{donde}: faltan campos {sorted(faltan)}")
        return e

    if r["availability"] not in DISPONIBILIDAD:
        e.append(f"{donde}: availability fuera del vocabulario: {r['availability']!r}")
    if r["freshness"] not in FRESCURA:
        e.append(f"{donde}: freshness fuera del vocabulario: {r['freshness']!r}")
    if r["concept_status"] not in ESTADOS_CONCEPTO:
        e.append(f"{donde}: concept_status fuera del vocabulario: {r['concept_status']!r}")
    for m in r["reasons"]:
        if m not in MOTIVOS:
            e.append(f"{donde}: motivo fuera del vocabulario: {m!r}")

    # Regla 1: toda candidata declara su relacion y la justifica.
    for c in r["candidates"]:
        sobra_c = set(c) - CAMPOS_CANDIDATA
        if sobra_c:
            e.append(f"{donde}: candidata con campos no reconocidos {sorted(sobra_c)}")
        if c.get("relation") not in RELACIONES:
            e.append(f"{donde}: candidata {c.get('metric')!r} sin relacion declarada")
        if not c.get("justification"):
            e.append(f"{donde}: candidata {c.get('metric')!r} sin justificacion — "
                     f"una equivalencia sin explicar no es una equivalencia")
        if c.get("relation") == "PROXY" and not c.get("confounder"):
            e.append(f"{donde}: proxy {c.get('metric')!r} sin confusor declarado — "
                     f"un proxy sin decir en que se diferencia de la variable es una "
                     f"equivalencia disfrazada")

    # Regla 2: solo proxy nunca llega a AVAILABLE.
    usadas = [c for c in r["candidates"] if c.get("presente")]
    if usadas and all(c["relation"] == "PROXY" for c in usadas):
        if r["availability"] == "AVAILABLE":
            e.append(f"{donde}: AVAILABLE resuelto solo con proxies — "
                     f"el maximo alcanzable es {SOLO_PROXY_MAXIMO}")

    # Regla 3: NOT_APPLICABLE exige declaracion explicita.
    if r["availability"] == "NOT_APPLICABLE" and "DECLARED_NOT_APPLICABLE" not in r["reasons"]:
        e.append(f"{donde}: NOT_APPLICABLE sin declaracion — la ausencia de dato es "
                 f"MISSING, nunca 'no aplica'")

    # Un requisito que no se resuelve tiene que decir por que.
    if r["availability"] in ("MISSING", "UNKNOWN") and not r["reasons"]:
        e.append(f"{donde}: sin resolver y sin motivo declarado")
    # Y uno que si se resuelve tiene que decir con que.
    if r["availability"] in ("AVAILABLE", "PARTIAL") and not r["resolved_by"]:
        e.append(f"{donde}: resuelto sin decir con que metrica")
    return e
