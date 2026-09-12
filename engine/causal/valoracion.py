"""Event + CausalPath + Evidence -> CausalAssessment. P5B (2026-09-07).

Representa de forma explicita el mecanismo economico, la direccion, la
evidencia que lo sostiene y lo que falta. NO calcula impacto,
probabilidad, exposicion, transmision, tiempo, mispricing ni oportunidad.

Ningun campo numerico. Ningun LLM. Cada tramo lleva el rule_id de la
regla declarada que lo produjo.

P5B no modifica Knowledge, Evidence, Event ni P5A: los consume. No tiene
ninguna llamada de escritura a fichero.
"""
import datetime

import mecanismos as M


class AssessmentError(Exception):
    pass


CAMPOS_TRAMO = {"relationship_id", "from_entity", "to_entity", "mechanism",
                "affected_variable", "economic_direction", "rule_id",
                "requires_evidence", "evidence_ids", "assumptions", "support",
                "unknowns"}
CAMPOS_ASSESSMENT = {"assessment_id", "event_id", "path_id", "as_of", "rule_version",
                     "segments", "overall_direction", "support", "support_reason",
                     "evidence_ids", "unknowns"}

ORDEN_SOPORTE = {"SUPPORTED": 0, "PARTIAL": 1, "UNKNOWN": 2, "CONTESTED": 3}

# Que variables entran en el resumen de rentabilidad y cuales no. Ver el
# comentario de valorar() -- `cost` queda fuera a proposito.
CUENTA_EN_RENTABILIDAD = {"revenue": True, "margin": True, "pricing_power": True,
                          "demand": True, "cost": False, "none": False}


# --- Utilidades sobre la evidencia disponible -------------------------------

def _buscar(evidencias, entity_id, variable):
    """Evidence de una variable de mecanismo para una entidad. Devuelve la
    lista, vacia si no hay: P5B no inventa el valor que falta."""
    return [e for e in evidencias
            if e.get("entity_id") == entity_id and e.get("metric") == variable]


def _sustitucion(k, entity_id, as_of, vigente):
    """Comprobacion de sustitucion sobre una entidad, en TRES estados.

    Esta funcion es el corazon de la correccion mas importante de P5B.
    No basta con preguntar "hay una fila SUBSTITUTES?": que no la haya
    significa que no conocemos un sustituto declarado, no que no exista.

        AFFIRMS vigente   -> KNOWN_SUBSTITUTE   hay alternativa declarada
        DENIES vigente    -> VERIFIED_ABSENCE   se ha comprobado que no hay
        ninguna fila      -> UNKNOWN            no lo sabemos

    Solo el segundo permite afirmar poder de precio con soporte completo.
    """
    afirma, niega = [], []
    for r in k.get("relationships", []):
        if r["predicate"] != "SUBSTITUTES":
            continue
        if entity_id not in (r["subject"], r["object"]):
            continue
        if not vigente(r, as_of):
            continue
        (afirma if r["polarity"] == "AFFIRMS" else niega).append(r)
    if afirma:
        return "KNOWN_SUBSTITUTE", afirma
    if niega:
        return "VERIFIED_ABSENCE", niega
    return "UNKNOWN", []


def _tramo(arista, mecanismo, variable, direccion, rule_id, requiere=(), evidencias=(),
           supuestos=(), soporte="UNKNOWN", unknowns=()):
    return {
        "relationship_id": arista["relationship_id"],
        "from_entity": arista["from"], "to_entity": arista["to"],
        "mechanism": mecanismo, "affected_variable": variable,
        "economic_direction": direccion, "rule_id": rule_id,
        "requires_evidence": list(requiere),
        "evidence_ids": [e["evidence_id"] for e in evidencias],
        "assumptions": list(supuestos), "support": soporte,
        "unknowns": list(unknowns),
    }


# --- Reglas declaradas -------------------------------------------------------

def _r0_sin_mecanismo(arista):
    motivo = M.SIN_MECANISMO[arista["predicate"]]
    return [_tramo(arista, M.NO_MECHANISM, "none", "UNKNOWN", "R0",
                   soporte="UNKNOWN",
                   unknowns=[f"{arista['predicate']}: {motivo}"])]


def _r1_r2_coste(arista, nodo, insumo, evidencias):
    """R1 coste directo, R2 margen bajo supuesto declarado."""
    ev = _buscar(evidencias, insumo, "price")
    if not ev:
        return [_tramo(arista, "INPUT_COST", "cost", "UNKNOWN", "R1",
                       requiere=[f"price({insumo})"], soporte="UNKNOWN",
                       unknowns=[f"existe la relacion de uso pero no hay Evidence del "
                                 f"precio de {insumo}: sin esa variable no se puede "
                                 f"determinar el signo"])]
    return [
        _tramo(arista, "INPUT_COST", "cost", "POSITIVE", "R1",
               requiere=[f"price({insumo})"], evidencias=ev, soporte="SUPPORTED"),
        # El signo del margen NO es una consecuencia mecanica del coste:
        # depende de si la empresa puede trasladarlo al precio de venta.
        # Sin evidencia de eso, el supuesto se declara y el tramo no puede
        # ser SUPPORTED.
        _tramo(arista, "INPUT_COST", "margin", "NEGATIVE", "R2",
               requiere=[f"price({insumo})", f"pricing_power({nodo})"], evidencias=ev,
               supuestos=[f"{nodo} no puede repercutir el encarecimiento en su precio de venta"],
               soporte="PARTIAL",
               unknowns=["no se ha comprobado la capacidad de repercutir el coste"]),
    ]


def _r3_demanda(arista, proveedor, cliente, evidencias):
    ev = _buscar(evidencias, cliente, "demand")
    if not ev:
        return [_tramo(arista, "CUSTOMER_DEMAND", "revenue", "UNKNOWN", "R3",
                       requiere=[f"demand({cliente})"], soporte="UNKNOWN",
                       unknowns=[f"existe la relacion de suministro pero no hay Evidence "
                                 f"de la demanda de {cliente}"])]
    return [_tramo(arista, "CUSTOMER_DEMAND", "revenue", "POSITIVE", "R3",
                   requiere=[f"demand({cliente})"], evidencias=ev, soporte="SUPPORTED")]


def _r4_poder_de_precio(arista, proveedor, recurso, evidencias, k, as_of, vigente):
    """R4: capacidad restringida + comprobacion de sustitucion en TRES estados."""
    ev = _buscar(evidencias, recurso, "capacity_utilization")
    if not ev:
        return [_tramo(arista, "CAPACITY_CONSTRAINT", "pricing_power", "UNKNOWN", "R4",
                       requiere=[f"capacity_utilization({recurso})"], soporte="UNKNOWN",
                       unknowns=[f"sin medida de utilizacion de {recurso} no se puede "
                                 f"saber si hay restriccion de capacidad"])]
    estado, rels = _sustitucion(k, recurso, as_of, vigente)
    if estado == "KNOWN_SUBSTITUTE":
        return [_tramo(arista, "SUBSTITUTION", "pricing_power", "UNKNOWN", "R4",
                       requiere=[f"capacity_utilization({recurso})"], evidencias=ev,
                       soporte="UNKNOWN",
                       unknowns=[f"existe alternativa declarada a {recurso} "
                                 f"({rels[0]['relationship_id']}): no se puede inferir "
                                 f"poder de precio"])]
    if estado == "VERIFIED_ABSENCE":
        return [_tramo(arista, "PRICING_POWER", "pricing_power", "POSITIVE", "R4",
                       requiere=[f"capacity_utilization({recurso})"], evidencias=ev,
                       soporte="SUPPORTED")]
    # Ninguna fila. Ausencia NO es evidencia de ausencia.
    return [_tramo(arista, "PRICING_POWER", "pricing_power", "POSITIVE", "R4",
                   requiere=[f"capacity_utilization({recurso})",
                             f"SUBSTITUTES({recurso}) afirmado o negado"],
                   evidencias=ev,
                   supuestos=[f"no se conoce ningun sustituto declarado de {recurso}"],
                   soporte="PARTIAL",
                   unknowns=["no hay ninguna fila SUBSTITUTES sobre este recurso: eso "
                             "significa que NO CONOCEMOS un sustituto, no que no exista. "
                             "La ausencia de fila no es evidencia de ausencia"])]


def _r5_coste_derivado(arista, nodo, insumo, evidencias):
    """R5: mas volumen presiona el insumo SOLO si el insumo esta limitado."""
    cap = _buscar(evidencias, insumo, "capacity_utilization")
    if not cap:
        return [_tramo(arista, "INPUT_COST", "cost", "UNKNOWN", "R5",
                       requiere=[f"capacity_utilization({insumo})"], soporte="UNKNOWN",
                       unknowns=[f"mas volumen no encarece {insumo} si {insumo} no esta "
                                 f"limitado, y no hay medida de su utilizacion"])]
    return [
        _tramo(arista, "CAPACITY_CONSTRAINT", "cost", "POSITIVE", "R5",
               requiere=[f"capacity_utilization({insumo})"], evidencias=cap,
               supuestos=[f"el aumento de volumen se traduce en mas demanda de {insumo}"],
               soporte="PARTIAL"),
        _tramo(arista, "INPUT_COST", "margin", "NEGATIVE", "R5",
               requiere=[f"capacity_utilization({insumo})", f"pricing_power({nodo})"],
               evidencias=cap,
               supuestos=[f"{nodo} no puede repercutir el encarecimiento"],
               soporte="PARTIAL",
               unknowns=["no se ha comprobado la capacidad de repercutir el coste"]),
    ]


# --- Valoracion de un camino -------------------------------------------------

def valorar(evento, camino, evidencias, k, vigente, as_of=None):
    """Event + CausalPath + Evidence -> CausalAssessment."""
    as_of = as_of or datetime.date.fromisoformat(camino["as_of"])
    impulso = M.impulso_de_evento(evento)
    tramos = []
    unknowns_globales = []

    if impulso is None:
        unknowns_globales.append(
            f"el evento '{evento.get('action')}' no mueve ninguna variable economica que "
            f"P5B sepa propagar: sin impulso no hay nada que transmitir")

    entidad_impulso, variable, direccion = impulso if impulso else (None, None, None)
    # Nodo por el que va el impulso mientras se recorre el camino.
    activo = entidad_impulso

    for arista in camino["edges"]:
        pred = arista["predicate"]
        if pred in M.SIN_MECANISMO:
            tramos += _r0_sin_mecanismo(arista)
            continue
        if impulso is None:
            tramos.append(_tramo(arista, M.NO_MECHANISM, "none", "UNKNOWN", "R0",
                                 soporte="UNKNOWN",
                                 unknowns=["sin impulso economico que propagar"]))
            continue

        destino, origen_a = arista["to"], arista["from"]
        nuevos = []
        if pred in ("USES", "DEPENDS_ON"):
            if variable == "price" and arista["traversal_direction"] == "REVERSE":
                # X (insumo) -> N (quien lo usa): encarecimiento del insumo
                nuevos = _r1_r2_coste(arista, destino, origen_a, evidencias)
            elif variable == "demand" and arista["traversal_direction"] == "FORWARD":
                # N -> P (recurso que usa): mas volumen presiona el recurso
                nuevos = _r5_coste_derivado(arista, origen_a, destino, evidencias)
                nuevos += _r4_poder_de_precio(arista, origen_a, destino, evidencias,
                                              k, as_of, vigente)
            else:
                nuevos = [_tramo(arista, M.NO_MECHANISM, "none", "UNKNOWN", "R0",
                                 soporte="UNKNOWN",
                                 unknowns=[f"ninguna regla declarada cubre "
                                           f"{pred} recorrido {arista['traversal_direction']} "
                                           f"con un impulso de {variable}"])]
        elif pred == "SUPPLIES":
            if variable == "demand" and arista["traversal_direction"] == "REVERSE":
                # cliente -> proveedor: la demanda del cliente sostiene al proveedor
                nuevos = _r3_demanda(arista, destino, origen_a, evidencias)
                if nuevos and nuevos[0]["economic_direction"] == "POSITIVE":
                    activo = destino     # el impulso continua en el proveedor
            else:
                nuevos = [_tramo(arista, M.NO_MECHANISM, "none", "UNKNOWN", "R0",
                                 soporte="UNKNOWN",
                                 unknowns=[f"ninguna regla declarada cubre SUPPLIES "
                                           f"recorrido {arista['traversal_direction']} "
                                           f"con un impulso de {variable}"])]
        elif pred == "SUBSTITUTES":
            nuevos = [_tramo(arista, "SUBSTITUTION", "none", "NEUTRAL", "R6",
                             soporte="PARTIAL",
                             supuestos=["el grado de sustituibilidad se declara, no se estima"],
                             unknowns=["se conoce la existencia de una alternativa, no su grado"])]
        else:
            nuevos = [_tramo(arista, M.NO_MECHANISM, "none", "UNKNOWN", "R0",
                             soporte="UNKNOWN",
                             unknowns=[f"predicado {pred} sin regla declarada en P5B v1"])]
        tramos += nuevos

    # --- resumen -------------------------------------------------------------
    # No se puede resumir sumando signos de variables distintas: "el coste
    # sube" y "el margen baja" son la MISMA historia contada dos veces, no
    # una divergencia. El resumen se hace sobre una unica vara de medir --
    # el efecto en la rentabilidad -- con un mapa declarado:
    #
    #   revenue, margin, pricing_power, demand  ->  cuentan con su signo
    #   cost                                    ->  NO cuenta por si solo:
    #        su efecto en la rentabilidad pasa por el margen, y contarlo
    #        aparte lo contaria dos veces con el signo cambiado.
    #
    # Asi T4 (ingreso arriba y margen abajo en el mismo nodo) sale
    # DIVERGENT porque de verdad lo es, y T2 (coste arriba, margen abajo)
    # sale NEGATIVE, que es lo que economicamente ocurre.
    signos = {t["economic_direction"] for t in tramos
              if t["economic_direction"] in ("POSITIVE", "NEGATIVE")
              and CUENTA_EN_RENTABILIDAD.get(t["affected_variable"], False)}
    if len(signos) > 1:
        overall = "DIVERGENT"
    elif signos:
        overall = signos.pop()
    elif any(t["economic_direction"] == "NEUTRAL" for t in tramos):
        overall = "NEUTRAL"
    else:
        overall = "UNKNOWN"

    # Herencia desde P5A, sin recalcular nada.
    if camino["validity"] == "CONTESTED":
        soporte, motivo = "CONTESTED", ("el camino viene CONTESTED de P5A: hay conocimiento "
                                        "que niega alguna de sus aristas")
    else:
        peor = max((t["support"] for t in tramos), key=lambda s: ORDEN_SOPORTE[s],
                   default="UNKNOWN")
        soporte = peor
        motivo = f"soporte del peor tramo de {len(tramos)}"
        if camino["validity"] == "PROVISIONAL" and soporte == "SUPPORTED":
            soporte = "PARTIAL"
            motivo = ("el camino de P5A es PROVISIONAL: aunque las reglas tengan toda su "
                      "evidencia, el assessment no puede pasar de PARTIAL")

    if all(t["mechanism"] == M.NO_MECHANISM for t in tramos) and tramos:
        unknowns_globales.append(
            "ninguna arista del camino admite un mecanismo economico: las relaciones "
            "verificadas disponibles son de identidad o clasificacion")
    unknowns_globales += sorted({u for t in tramos for u in t["unknowns"]})
    unknowns_globales.append("P5B no calcula impacto, probabilidad, exposicion ni magnitud")

    return {
        "assessment_id": f"ca:{evento['event_id']}:{camino['path_id']}:{M.RULE_VERSION}",
        "event_id": evento["event_id"], "path_id": camino["path_id"],
        "as_of": as_of.isoformat(), "rule_version": M.RULE_VERSION,
        "segments": tramos, "overall_direction": overall,
        "support": soporte, "support_reason": motivo,
        "evidence_ids": sorted({e for t in tramos for e in t["evidence_ids"]}),
        "unknowns": unknowns_globales,
    }


# --- Validacion --------------------------------------------------------------

def validar(a):
    sobra = set(a) - CAMPOS_ASSESSMENT
    if sobra:
        raise AssessmentError(f"assessment: campos no reconocidos {sorted(sobra)}")
    if a["overall_direction"] not in M.DIRECCIONES_CAMINO:
        raise AssessmentError(f"overall_direction {a['overall_direction']!r} fuera del vocabulario")
    if a["support"] not in M.SOPORTES:
        raise AssessmentError(f"support {a['support']!r} fuera del vocabulario")
    if not a["support_reason"]:
        raise AssessmentError("un estado sin motivo escrito no es auditable")
    if not isinstance(a["unknowns"], list) or not a["unknowns"]:
        raise AssessmentError("un assessment tiene que poder declarar lo que no sabe")
    for t in a["segments"]:
        if set(t) != CAMPOS_TRAMO:
            raise AssessmentError(f"tramo con campos {sorted(set(t) ^ CAMPOS_TRAMO)}")
        if t["mechanism"] != M.NO_MECHANISM and t["mechanism"] not in M.MECANISMOS:
            raise AssessmentError(f"mecanismo {t['mechanism']!r} fuera del vocabulario")
        if t["economic_direction"] not in M.DIRECCIONES:
            raise AssessmentError(f"direccion {t['economic_direction']!r} fuera del vocabulario")
        if t["affected_variable"] not in M.VARIABLES_AFECTADAS:
            raise AssessmentError(f"variable {t['affected_variable']!r} fuera del vocabulario")
        if t["support"] not in M.SOPORTES:
            raise AssessmentError(f"soporte de tramo {t['support']!r} fuera del vocabulario")
        if not t["rule_id"]:
            raise AssessmentError("todo tramo declara la regla que lo produjo")
        # Un signo que depende de un supuesto no comprobado NO puede estar
        # completamente sostenido.
        if t["assumptions"] and t["support"] == "SUPPORTED":
            raise AssessmentError(
                f"{t['relationship_id']}: SUPPORTED con supuestos declarados — "
                f"un signo que depende de un supuesto sin comprobar es como mucho PARTIAL")
        if t["economic_direction"] == "UNKNOWN" and not t["unknowns"]:
            raise AssessmentError(f"{t['relationship_id']}: UNKNOWN sin decir por que")
        for valor in t.values():
            if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                raise AssessmentError("P5B no emite numeros: ni magnitud, ni peso, ni probabilidad")
    return True


def explicar(a):
    L = [f"ASSESSMENT {a['assessment_id']}",
         f"  evento {a['event_id']}",
         f"  camino {a['path_id']}",
         f"  reglas {a['rule_version']} · a fecha {a['as_of']}", ""]
    for t in a["segments"]:
        L.append(f"  {t['from_entity']} → {t['to_entity']}   [{t['relationship_id']}]")
        L.append(f"      mecanismo   {t['mechanism']} · {t['rule_id']}")
        L.append(f"      efecto      {t['affected_variable']} = {t['economic_direction']}"
                 f"   ({t['support']})")
        if t["evidence_ids"]:
            L.append(f"      evidencia   {', '.join(t['evidence_ids'])}")
        if t["requires_evidence"]:
            L.append(f"      necesita    {', '.join(t['requires_evidence'])}")
        for s in t["assumptions"]:
            L.append(f"      supuesto    {s}")
        for u in t["unknowns"]:
            L.append(f"      no sabemos  {u}")
    L.append("")
    L.append(f"  DIRECCIÓN GLOBAL  {a['overall_direction']}")
    L.append(f"  SOPORTE           {a['support']} — {a['support_reason']}")
    L.append("  LO QUE NO SABEMOS")
    for u in a["unknowns"]:
        L.append(f"      · {u}")
    return "\n".join(L)


# --- CLI --------------------------------------------------------------------

def main(argv=None):
    import argparse
    import os
    import sys as _sys
    ap = argparse.ArgumentParser(
        description="Valora economicamente los caminos de P5A que parten de una entidad.")
    ap.add_argument("entidad", help="entity_id de origen")
    ap.add_argument("--accion", default="price_change",
                    help="accion del Event: price_change, demand_change, sentiment_assertion...")
    ap.add_argument("--direccion", default="UP", choices=["UP", "DOWN"])
    ap.add_argument("--profundidad", type=int, default=2)
    ap.add_argument("--explicar", type=int, default=1, metavar="N")
    args = ap.parse_args(argv)

    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _sys.path.insert(0, os.path.join(raiz, "engine", "knowledge"))
    import modelo
    import caminos

    k = modelo.cargar()
    hoy = datetime.date.today()
    evento = {"event_id": f"ev4:manual:{args.accion}", "primary_entity": args.entidad,
              "action": args.accion, "direction": args.direccion}
    cs = caminos.descubrir(evento["event_id"], args.entidad, k, hoy, args.profundidad)
    valoraciones = [valorar(evento, c, [], k, modelo.vigente, hoy) for c in cs]

    print(f"VALORACIÓN de {len(valoraciones)} camino(s) desde {args.entidad}")
    resumen = {}
    for a in valoraciones:
        clave = (a["overall_direction"], a["support"])
        resumen[clave] = resumen.get(clave, 0) + 1
    for (d, s), n in sorted(resumen.items()):
        print(f"  {d:10} · {s:10} × {n}")
    if all(a["overall_direction"] == "UNKNOWN" for a in valoraciones):
        print("\n  Ningún camino admite un mecanismo económico con el conocimiento y la")
        print("  evidencia actuales. No es que el efecto sea neutro: es que no se puede")
        print("  determinar, y cada assessment dice exactamente qué le falta.")
    for a in valoraciones[:args.explicar]:
        print()
        print(explicar(a))
    return 0


if __name__ == "__main__":
    import sys as _s
    _s.exit(main())
