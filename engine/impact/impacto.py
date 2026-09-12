"""Economic Impact v1 -- P6 (2026-09-07).

    CausalAssessment (P5B) + DataRequirement (P5D) -> EconomicImpact

Determinista y sin ninguna formula: en v1 no hay ningun coeficiente de
transmision declarado, asi que no hay nada que multiplicar. Lo que este
modulo hace es decidir, para cada tramo, si el sistema TENDRIA DERECHO a
producir un numero -- y decir con precision por que no lo tiene.

Ese es el objetivo de la version: no producir numeros, sino demostrar
que el sistema sabe exactamente cuando podria producirlos.

QUE NO RECALCULA
----------------
La direccion viene de P5B tal cual. P6 no vuelve a decidir signos: si lo
hiciera, habria dos motores opinando sobre lo mismo y el dia que
discreparan nadie sabria cual leer.

Uso:
    python3 engine/impact/impacto.py org:nvidia
    python3 engine/impact/impacto.py org:nvidia --combinar
"""
import datetime
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _s in ("causal", "contract", "impact", "knowledge", "requirements"):
    _p = os.path.join(RAIZ, "engine", _s)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import esquema_impacto as E  # noqa: E402
import materialidad as MT  # noqa: E402
import mecanismos as M  # noqa: E402
import requisitos_magnitud as RM  # noqa: E402
import resolver as R5D  # noqa: E402


def _pieza(state, **kw):
    """Toda pieza no resuelta lleva sus claves PRESENTES y a null. Un
    campo ausente se lee como un descuido; un null se lee como un hueco,
    que es lo que es."""
    d = {"state": state}
    d.update(kw)
    return d


def _fitness(requisitos, requiere):
    """Proyeccion de lo que P5D ya calculo. No es un catalogo nuevo: es
    ponerle nombre para que P6 no pueda confundirlo con la frescura.

    FRESH no habilita nada por si solo: `demand(org:nvidia)` esta FRESH y
    aun asi solo resuelve por proxy."""
    if not requiere:
        return "UNKNOWN"
    peor = "MEASURES"
    orden = {"MEASURES": 0, "PROXY": 1, "INSUFFICIENT": 2, "UNKNOWN": 3}
    for texto in requiere:
        req = requisitos.get(texto)
        if req is None:
            f = "UNKNOWN"
        elif req["availability"] == "AVAILABLE":
            f = "MEASURES"
        elif req["availability"] == "PARTIAL":
            f = "PROXY"
        elif req["availability"] in ("MISSING", "NOT_APPLICABLE"):
            f = "INSUFFICIENT"
        else:
            f = "UNKNOWN"
        if orden[f] > orden[peor]:
            peor = f
    return peor


def derecho_a_magnitud(mecanismo, relationship_id, fitness, materialidad=None):
    """Tendria el sistema DERECHO a emitir un numero para este tramo?

    Es el nucleo de P6 v1. La version NO produce magnitudes -- no hay
    ninguna formula en este modulo, a proposito -- asi que lo que se
    entrega no es el numero sino la comprobacion de si podria existir, y
    exactamente que le falta si no.

    Devuelve (bool, [motivos]). Hoy devuelve False en el 100% de los
    casos reales; con COEFICIENTES y MATERIALIDAD poblados devolveria
    True, y hay un test que lo comprueba para que la comprobacion no sea
    una rama muerta que nadie ha ejecutado nunca.

    Las cuatro precondiciones, ninguna sustituible por un valor implicito:
    """
    motivos = []
    cap, _ = RM.capacidad(mecanismo)
    ent = RM.entradas(mecanismo)

    if cap == "NOT_QUANTIFIABLE":
        motivos.append("NO_ECONOMIC_MECHANISM" if mecanismo == M.NO_MECHANISM
                       else "MECHANISM_CANNOT_QUANTIFY")
        return False, motivos       # no mejora con datos: no se sigue mirando

    # 1. La variable observada tiene que estar MEDIDA, no aproximada.
    if fitness == "INSUFFICIENT":
        motivos.append("REQUIRED_EVIDENCE_MISSING")
    elif fitness in ("PROXY", "UNKNOWN"):
        motivos.append("EVIDENCE_ONLY_BY_PROXY")
    # 2. Materialidad: causalidad no es materialidad. Y una COTA no
    #    puntualiza: da derecho a una magnitud acotada, nunca a un punto.
    if ent["materialidad"]:
        est = (materialidad or {}).get("status", "UNKNOWN")
        if est == "BOUNDED":
            motivos.append("MATERIALITY_ONLY_BOUNDED")
        elif est != "KNOWN":
            motivos.append("MATERIALITY_UNKNOWN")
    # 3. Coeficiente de transmision de origen declarado.
    if ent["coeficiente"] and not RM.coeficiente(mecanismo, relationship_id):
        motivos.append("NO_TRANSMISSION_COEFFICIENT")
    # 4. Linea base contra la que medir el cambio.
    if ent["linea_base"] and not RM.linea_base(relationship_id):
        motivos.append("NO_BASELINE")
    return not motivos, motivos


def _fecha(v):
    return datetime.date.fromisoformat(v) if isinstance(v, str) else v


def impacto_de_tramo(assessment, tramo, requisitos, k):
    """Un tramo de P5B -> un EconomicImpact."""
    mec = tramo["mechanism"]
    cap, motivo_cap = RM.capacidad(mec)
    fit = _fitness(requisitos, tramo["requires_evidence"])
    razones, unknowns = [], []

    # --- materialidad: derivada (P6.1), no declarada ---
    decl = RM.basis_de(mec)
    resuelta = None
    if decl is None:
        materialidad = _pieza("NOT_APPLICABLE", value=None, unit=None, source_id=None)
    else:
        basis, extremo = decl
        sujeto = tramo["to_entity"] if extremo == "to" else tramo["from_entity"]
        contraparte = tramo["from_entity"] if extremo == "to" else tramo["to_entity"]
        resuelta = MT.resolver_materialidad(basis, sujeto, contraparte, k,
                                            _fecha(assessment["as_of"]))
        if resuelta["status"] == "BOUNDED":
            materialidad = _pieza("BOUNDED", value=None, unit=resuelta["unit"],
                                  source_id=resuelta["applied_via"])
            materialidad["upper_bound"] = resuelta["upper_bound"]
        else:
            materialidad = _pieza(resuelta["status"], value=None, unit=None, source_id=None)
        unknowns += resuelta["unknowns"]
        if resuelta["status"] not in ("KNOWN", "BOUNDED"):
            unknowns.append(
                f"{tramo['relationship_id']} acredita que la relacion existe, no en que "
                f"proporcion: falta {RM.entradas(mec)['materialidad']}. Causalidad no es "
                f"materialidad")

    # --- coeficiente de transmision ---
    coef = RM.coeficiente(mec, tramo["relationship_id"])
    if coef:
        base = {"coefficient_origin": coef["origin"], "coefficient_ref": coef["ref"],
                "inputs": list(tramo["requires_evidence"])}
    else:
        base = {"coefficient_origin": "UNKNOWN", "coefficient_ref": None,
                "inputs": list(tramo["requires_evidence"])}

    # --- magnitud ---
    # v1 NUNCA la emite. Lo que se calcula es el DERECHO a emitirla, y
    # cuando no lo hay, exactamente por que. No hay ninguna formula en
    # este modulo y eso es el diseno, no una carencia.
    tiene_derecho, motivos = derecho_a_magnitud(mec, tramo["relationship_id"], fit,
                                                resuelta)
    razones += motivos
    if cap == "NOT_QUANTIFIABLE":
        # "No puedo" no es "no se". Un mecanismo asi no mejora con datos.
        magnitud = _pieza("NOT_APPLICABLE", value=None, unit=None, baseline=None)
        unknowns.append(f"{mec}: {motivo_cap}")
    else:
        magnitud = _pieza("UNKNOWN", value=None, unit=None, baseline=None)
        if "EVIDENCE_ONLY_BY_PROXY" in motivos:
            unknowns.append(
                "la variable solo se resuelve con un proxy declarado: P6 puede degradar "
                "una afirmacion cuantitativa a cualitativa, nunca al reves")
        if "NO_TRANSMISSION_COEFFICIENT" in motivos:
            unknowns.append(
                f"no hay coeficiente declarado para {mec}: {RM.entradas(mec)['coeficiente']}. "
                f"v1 no lo estima -- un coeficiente estadistico seria salida de un modelo, "
                f"no evidencia")
        if "NO_BASELINE" in motivos:
            unknowns.append(
                f"no hay linea base declarada ({RM.entradas(mec)['linea_base']}): un cambio "
                f"sin un 'respecto a que' no es una magnitud")
        if tiene_derecho:
            # Alcanzable solo con COEFICIENTES, MATERIALIDAD y LINEAS_BASE
            # poblados. v1 los deja vacios: cuando dejen de estarlo, esta
            # rama tendra que producir el numero, y hasta entonces dice
            # con todas las letras que el sistema SI tendria derecho.
            unknowns.append(
                "todas las precondiciones se cumplen: v1 tendria derecho a emitir una "
                "magnitud y deliberadamente no la emite — calcularla es trabajo de v2")

    # --- horizonte: solo LEAD_TIME lo aporta, y no esta medido ---
    horizonte = _pieza("UNKNOWN", dias_min=None, dias_max=None)

    return {
        "impact_id": f"im:{assessment['assessment_id']}:{tramo['relationship_id']}"
                     f":{tramo['affected_variable']}",
        "as_of": assessment["as_of"],
        "rule_version": E.RULE_VERSION,
        "event_id": assessment["event_id"],
        "path_id": assessment["path_id"],
        "relationship_id": tramo["relationship_id"],
        "mechanism": mec,
        "magnitude_capability": cap,
        "entity_id": tramo["to_entity"],
        "affected_variable": tramo["affected_variable"],
        # Heredada de P5B sin tocar.
        "economic_direction": tramo["economic_direction"],
        "magnitude": magnitud,
        "magnitude_basis": base,
        "materiality": materialidad,
        "horizon": horizonte,
        "fitness": fit,
        "evidence_ids": list(tramo["evidence_ids"]),
        # El soporte nunca mejora al del tramo del que viene.
        "support": tramo["support"],
        "reasons": sorted(set(razones)),
        "unknowns": unknowns + list(tramo["unknowns"]),
    }


def impactos_de(assessment, requisitos, k):
    return [impacto_de_tramo(assessment, t, requisitos, k) for t in assessment["segments"]]


def combinar(impactos):
    """Varios mecanismos -> NUNCA una suma.

    Tres reglas, todas heredadas de decisiones ya tomadas en el proyecto:

    1. Nada se suma. Se entrega la descomposicion. Dos mecanismos sobre
       la misma variable pueden ser la misma historia contada dos veces
       (P5B ya excluyo `cost` del resumen por exactamente esto).
    2. Un UNKNOWN no se deja fuera del reparto: el total es UNKNOWN y la
       parte conocida se reporta APARTE, nunca como si fuera el total.
    3. El estado agregado es el del PEOR componente (P1b y P5B).
    """
    conocido = [i for i in impactos if i["magnitude"]["state"] == "KNOWN"]
    sin_resolver = [i for i in impactos if i["magnitude"]["state"] != "KNOWN"]

    horizontes = {(i["horizon"]["dias_min"], i["horizon"]["dias_max"])
                  for i in conocido if i["horizon"]["state"] == "KNOWN"}
    estado = "KNOWN" if conocido and not sin_resolver else "UNKNOWN"
    notas = []
    if sin_resolver:
        notas.append(f"{len(sin_resolver)} de {len(impactos)} tramos sin magnitud: el total "
                     f"es UNKNOWN y la parte conocida se reporta aparte, nunca como total")
    if len(horizontes) > 1:
        estado = "UNKNOWN"
        notas.append("horizontes distintos entre tramos: dos efectos en plazos distintos "
                     "no son un efecto")
    # El orden ya esta en la tupla de P5B: no se redeclara aqui.
    orden = {s: n for n, s in enumerate(M.SOPORTES)}
    peor = max(impactos, key=lambda i: orden[i["support"]])["support"] if impactos else "UNKNOWN"

    return {
        "state": estado,
        # Deliberadamente NO hay un campo `total`: no existe.
        "conocido": [i["impact_id"] for i in conocido],
        "unresolved": [{"impact_id": i["impact_id"], "mechanism": i["mechanism"],
                        "reasons": i["reasons"]} for i in sin_resolver],
        "support": peor,
        "unknowns": notas,
    }


def explicar(i):
    L = [f"IMPACTO {i['impact_id']}",
         f"  mecanismo   {i['mechanism']}  ({i['magnitude_capability']})",
         f"  sobre       {i['affected_variable']} de {i['entity_id']}",
         f"  direccion   {i['economic_direction']}   (heredada de P5B)",
         f"  magnitud    {i['magnitude']['state']:15} valor {i['magnitude']['value']}",
         f"  materialidad{i['materiality']['state']:>16}"
         + (f"  <= {i['materiality']['upper_bound']}{i['materiality']['unit']}"
            if i["materiality"]["state"] == "BOUNDED" else ""),
         f"  horizonte   {i['horizon']['state']}",
         f"  fitness     {i['fitness']}   ·  soporte {i['support']}",
         f"  coeficiente {i['magnitude_basis']['coefficient_origin']}"]
    if i["reasons"]:
        L.append(f"  motivos     {', '.join(i['reasons'])}")
    for u in i["unknowns"]:
        L.append(f"      · {u}")
    return "\n".join(L)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Impacto economico de los caminos de P5A/P5B.")
    ap.add_argument("entidad")
    ap.add_argument("--accion", default="demand_change")
    ap.add_argument("--direccion", default="UP", choices=["UP", "DOWN"])
    ap.add_argument("--profundidad", type=int, default=2)
    ap.add_argument("--combinar", action="store_true")
    ap.add_argument("--explicar", type=int, default=99, metavar="N")
    args = ap.parse_args(argv)

    import caminos
    import modelo
    import valoracion

    k = modelo.cargar()
    hoy = datetime.date.today()
    evento = {"event_id": f"ev4:p6:{args.accion}", "primary_entity": args.entidad,
              "action": args.accion, "direction": args.direccion}
    cs = caminos.descubrir(evento["event_id"], args.entidad, k, hoy, args.profundidad)
    vals = [valoracion.valorar(evento, c, [], k, modelo.vigente, hoy) for c in cs]
    resueltos = R5D.resolver_valoraciones(vals, k, hoy, True)
    requisitos = {f"{r['variable']}({r['entity_id']})": r for r in resueltos}

    todos = []
    for a in vals:
        todos += impactos_de(a, requisitos, k)

    incidencias = [x for i in todos for x in E.validar(i)]
    print(f"IMPACTO ECONOMICO — {hoy}   ({len(todos)} tramo(s) sobre {len(vals)} camino(s))")
    cuenta = {}
    for i in todos:
        cuenta[i["magnitude"]["state"]] = cuenta.get(i["magnitude"]["state"], 0) + 1
    print(f"  magnitud: {cuenta}")
    print()
    # Los tramos con mecanismo economico primero: los de identidad son
    # correctos y repetitivos, y enterrar lo interesante bajo 37 de ellos
    # es una forma de esconderlo.
    orden_cap = {"QUANTIFIABLE": 0, "CONDITIONALLY_QUANTIFIABLE": 1, "NOT_QUANTIFIABLE": 2}
    vistos = set()
    n = 0
    for i in sorted(todos, key=lambda x: orden_cap[x["magnitude_capability"]]):
        clave = (i["relationship_id"], i["affected_variable"], i["mechanism"])
        if clave in vistos or n >= args.explicar:
            continue
        vistos.add(clave)
        n += 1
        print(explicar(i))
        print()
    if args.combinar:
        c = combinar(todos)
        print("COMBINACION")
        print(f"  estado      {c['state']}")
        print(f"  conocido    {len(c['conocido'])} tramo(s)")
        print(f"  unresolved  {len(c['unresolved'])} tramo(s)")
        print(f"  soporte     {c['support']}   (el del peor componente)")
        for u in c["unknowns"]:
            print(f"      · {u}")
        print("  NO hay campo 'total': no existe un numero que resuma esto.")
    if incidencias:
        print("INCIDENCIAS DE ESQUEMA:")
        for x in sorted(set(incidencias)):
            print(f"  · {x}")
        return 1
    if all(i["magnitude"]["state"] != "KNOWN" for i in todos):
        print("Ningun tramo produce magnitud. No es un fallo: es lo que la evidencia")
        print("y los parametros declarados permiten afirmar hoy, y cada tramo dice")
        print("si es porque el mecanismo no puede o porque falta el dato.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
