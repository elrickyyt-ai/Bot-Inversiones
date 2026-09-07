"""Causal Path / Graph Traversal v1. P5A (2026-09-07).

    EVENT + KNOWLEDGE -> CAUSAL PATH

Descubre y representa los caminos ESTRUCTURALES por los que un evento
podria transmitirse. No calcula probabilidad, ni impacto, ni signo
economico, ni mispricing: primero hay que demostrar que el sistema
recorre correctamente la estructura que ya tiene.

LA DISTINCION QUE MAS IMPORTA
-----------------------------
`traversal_direction` (FORWARD / REVERSE) es la orientacion ESTRUCTURAL
con la que se recorrio una arista: si se fue del sujeto al objeto o al
reves. NO es `economic_direction`. Que un camino se recorra en sentido
inverso no dice nada sobre si el efecto economico sube o baja. Ese signo
es P5B y aqui no existe ningun campo que lo insinue.

Igual con `polarity`: AFFIRMS/DENIES es una propiedad del CONOCIMIENTO
(si la relacion se da o se ha comprobado que no), no del efecto.

DOS EJES, NO UN ENUM
--------------------
  validity      VERIFIED | PROVISIONAL | CONTESTED   calidad de las aristas
  completeness  COMPLETE | PATH_INCOMPLETE           si se llego al objetivo

Un camino puede estar verificado y no llegar, o llegar por aristas
provisionales. Colapsarlos obligaria a ocultar una de las dos verdades
(mismo argumento que P1b para cobertura y frescura).

Y `incomplete_reason` separa dos cosas que tampoco son la misma:
DEPTH_LIMIT es un limite tecnico de esta ejecucion; NO_FURTHER_KNOWLEDGE
es que el sistema no sabe mas. La profundidad no altera el Knowledge.

NO ESCRIBE NADA
---------------
Event + Knowledge -> CausalPath es una transformacion derivada. Este
modulo no tiene ninguna llamada de escritura a fichero, y un test lo
comprueba sobre el codigo ademas de verificar por hash que knowledge/,
data/ y las capas anteriores no cambian.
"""
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROFUNDIDAD_POR_DEFECTO = 3

VALIDECES = {
    "VERIFIED":    "todas las aristas del camino estan verificadas",
    "PROVISIONAL": "alguna arista es PROVISIONAL: el camino hereda esa condicion",
    "CONTESTED":   "alguna arista usada esta contradicha por una relacion DENIES",
}
COMPLETITUDES = {
    "COMPLETE":        "el camino alcanzo una entidad objetivo",
    "PATH_INCOMPLETE": "el camino no alcanzo ninguna entidad objetivo",
}
MOTIVOS_INCOMPLETO = {
    "DEPTH_LIMIT":          "se agoto la profundidad maxima de ESTA ejecucion (limite tecnico)",
    "NO_FURTHER_KNOWLEDGE": "no hay mas relaciones vigentes desde el ultimo nodo (falta conocimiento)",
}
DIRECCIONES = {"FORWARD", "REVERSE", "MIXED"}

CAMPOS_ARISTA = {"relationship_id", "from", "to", "traversal_direction", "predicate",
                 "source_id", "validity", "status", "support_level", "nature"}
CAMPOS_CAMINO = {"path_id", "event_id", "origin_entity", "nodes", "edges", "depth",
                 "direction_status", "validity", "completeness", "incomplete_at",
                 "incomplete_reason", "contradictions", "source_refs", "as_of", "unknowns"}


class PathError(Exception):
    pass


def _knowledge_mod():
    path = os.path.join(ROOT, "engine", "knowledge")
    sys.path.insert(0, path)
    try:
        if "modelo" in sys.modules:
            return sys.modules["modelo"]
        return __import__("modelo")
    finally:
        sys.path.remove(path)


# --- Construccion del indice ------------------------------------------------

def indice(k, as_of):
    """Aristas recorribles a la fecha dada, mas las negaciones vigentes.

    Una relacion con polarity=DENIES afirma que el enlace NO existe:
    recorrerla seria inventar un camino. Se aparta, pero no se descarta
    -- se usa para detectar contradicciones sobre las aristas que si se
    recorren.
    """
    mod = _knowledge_mod()
    salidas, negadas = {}, {}
    for r in k["relationships"]:
        if not mod.vigente(r, as_of):
            continue
        clave = (r["subject"], r["predicate"], r["object"])
        if r["polarity"] == "DENIES":
            negadas.setdefault(clave, []).append(r)
            continue
        salidas.setdefault(r["subject"], []).append((r["object"], r, "FORWARD"))
        salidas.setdefault(r["object"], []).append((r["subject"], r, "REVERSE"))
    return salidas, negadas


def _arista(r, desde, hasta, direccion):
    """Proyeccion de la relacion, no una copia con vida propia: la
    relacion sigue siendo la unica fuente de verdad y un test comprueba
    campo a campo que esta proyeccion coincide con ella."""
    return {
        "relationship_id": r["relationship_id"],
        "from": desde, "to": hasta,
        "traversal_direction": direccion,   # ESTRUCTURAL, no economico
        "predicate": r["predicate"],
        "source_id": r["source_id"],
        "validity": {"valid_from": r["valid_from"], "valid_to": r.get("valid_to")},
        "status": r["status"],
        "support_level": r["support_level"],
        "nature": r["nature"],
    }


# --- Traversal --------------------------------------------------------------

def _componer(event_id, origen, camino, negadas, as_of, tipos, completeness,
              incomplete_at, incomplete_reason, objetivo_tipos):
    nodos = [origen] + [a["to"] for a in camino]
    direcciones = {a["traversal_direction"] for a in camino}
    direction_status = direcciones.pop() if len(direcciones) == 1 else "MIXED"

    contradicciones = []
    for a in camino:
        for clave, rels in negadas.items():
            s, p, o = clave
            if p == a["predicate"] and {s, o} == {a["from"], a["to"]}:
                contradicciones += [{"relationship_id": r["relationship_id"],
                                     "contradice": a["relationship_id"],
                                     "source_id": r["source_id"],
                                     "statement": r["statement"]} for r in rels]

    if contradicciones:
        validity = "CONTESTED"
    elif any(a["status"] == "PROVISIONAL" for a in camino):
        validity = "PROVISIONAL"
    else:
        validity = "VERIFIED"

    unknowns = []
    if validity == "PROVISIONAL":
        provisionales = [a["relationship_id"] for a in camino if a["status"] == "PROVISIONAL"]
        unknowns.append(f"el camino usa {len(provisionales)} relacion(es) PROVISIONAL "
                        f"({', '.join(provisionales)}): registradas pero sin evidencia "
                        f"estructural independiente")
    if validity == "CONTESTED":
        unknowns.append("hay conocimiento que niega alguna arista de este camino y P5A no "
                        "resuelve la contradiccion: la registra")
    if completeness == "PATH_INCOMPLETE":
        unknowns.append(f"camino incompleto en {incomplete_at}: "
                        f"{MOTIVOS_INCOMPLETO[incomplete_reason]}")
        if objetivo_tipos:
            unknowns.append(f"no se alcanzo ninguna entidad de tipo {sorted(objetivo_tipos)}")
    unknowns.append("P5A solo descubre estructura: no dice si el efecto sube o baja, "
                    "ni con que probabilidad, ni con que magnitud")

    return {
        "path_id": f"cp:{event_id}:{as_of.isoformat()}:"
                   + ">".join(a["relationship_id"] for a in camino) or f"cp:{event_id}:vacio",
        "event_id": event_id,
        "origin_entity": origen,
        "nodes": [{"entity_id": n, "type": tipos.get(n),
                   "role": "origin" if i == 0 else ("terminal" if i == len(nodos) - 1
                                                    else "intermediate")}
                  for i, n in enumerate(nodos)],
        "edges": camino,
        "depth": len(camino),
        "direction_status": direction_status if camino else "FORWARD",
        "validity": validity,
        "completeness": completeness,
        "incomplete_at": incomplete_at,
        "incomplete_reason": incomplete_reason,
        "contradictions": contradicciones,
        "source_refs": sorted({a["source_id"] for a in camino}),
        "as_of": as_of.isoformat(),
        "unknowns": unknowns,
    }


def descubrir(event_id, origen, k, as_of=None, max_depth=PROFUNDIDAD_POR_DEFECTO,
              tipos_objetivo=None):
    """Todos los caminos desde `origen`, hasta `max_depth` saltos.

    Con `tipos_objetivo` busca alcanzar una entidad de esos tipos y marca
    PATH_INCOMPLETE cuando no lo consigue, diciendo en que nodo se quedo
    y por que. Sin objetivo, enumera lo alcanzable.
    """
    as_of = as_of or datetime.date.today()
    salidas, negadas = indice(k, as_of)
    tipos = {e["entity_id"]: e["type"] for e in k["entities"]}
    if origen not in tipos:
        raise PathError(f"{origen} no es una entidad declarada — P5A no crea entidades")

    caminos = []
    # Pila explicita en vez de recursion: la profundidad es un limite
    # tecnico configurable, no una propiedad del Knowledge.
    pila = [(origen, [], {origen})]
    while pila:
        nodo, camino, visitados = pila.pop()
        vecinos = sorted(salidas.get(nodo, []), key=lambda x: x[1]["relationship_id"])
        # Ciclos: un nodo ya visitado en ESTE camino no se vuelve a pisar.
        avanzables = [(o, r, d) for o, r, d in vecinos if o not in visitados]

        if camino:
            alcanzado = tipos.get(nodo) in (tipos_objetivo or ())
            if tipos_objetivo and alcanzado:
                caminos.append(_componer(event_id, origen, camino, negadas, as_of, tipos,
                                         "COMPLETE", None, None, tipos_objetivo))
                continue
            if not tipos_objetivo:
                caminos.append(_componer(event_id, origen, camino, negadas, as_of, tipos,
                                         "COMPLETE", None, None, None))

        if len(camino) >= max_depth:
            if tipos_objetivo and camino:
                caminos.append(_componer(event_id, origen, camino, negadas, as_of, tipos,
                                         "PATH_INCOMPLETE", nodo, "DEPTH_LIMIT", tipos_objetivo))
            continue
        if not avanzables:
            if tipos_objetivo and camino:
                caminos.append(_componer(event_id, origen, camino, negadas, as_of, tipos,
                                         "PATH_INCOMPLETE", nodo, "NO_FURTHER_KNOWLEDGE",
                                         tipos_objetivo))
            continue
        for o, r, d in avanzables:
            pila.append((o, camino + [_arista(r, nodo, o, d)], visitados | {o}))

    return sorted(caminos, key=lambda c: (c["depth"], c["path_id"]))


# --- Validacion -------------------------------------------------------------

def validar(camino, k=None):
    sobra = set(camino) - CAMPOS_CAMINO
    if sobra:
        raise PathError(f"camino: campos no reconocidos {sorted(sobra)}")
    if camino["validity"] not in VALIDECES:
        raise PathError(f"validity {camino['validity']!r} fuera del vocabulario")
    if camino["completeness"] not in COMPLETITUDES:
        raise PathError(f"completeness {camino['completeness']!r} fuera del vocabulario")
    if camino["direction_status"] not in DIRECCIONES:
        raise PathError(f"direction_status {camino['direction_status']!r} fuera del vocabulario")
    if camino["completeness"] == "PATH_INCOMPLETE":
        if not camino["incomplete_at"]:
            raise PathError("un camino incompleto tiene que decir DONDE se interrumpio")
        if camino["incomplete_reason"] not in MOTIVOS_INCOMPLETO:
            raise PathError(f"motivo {camino['incomplete_reason']!r} fuera del vocabulario")
    if camino["depth"] != len(camino["edges"]):
        raise PathError("depth no coincide con el numero de aristas")
    if len(camino["nodes"]) != camino["depth"] + 1:
        raise PathError("nodes no encaja con depth")
    if not isinstance(camino["unknowns"], list) or not camino["unknowns"]:
        raise PathError("un camino tiene que poder declarar lo que no sabe")
    for a in camino["edges"]:
        if set(a) != CAMPOS_ARISTA:
            raise PathError(f"arista con campos {sorted(set(a) ^ CAMPOS_ARISTA)}")
        if a["traversal_direction"] not in ("FORWARD", "REVERSE"):
            raise PathError(f"traversal_direction {a['traversal_direction']!r} no valida")
    if k is not None:
        # La proyeccion no puede divergir de la relacion: Knowledge es la
        # unica fuente de verdad y el camino solo la referencia.
        por_id = {r["relationship_id"]: r for r in k["relationships"]}
        for a in camino["edges"]:
            r = por_id.get(a["relationship_id"])
            if r is None:
                raise PathError(f"arista {a['relationship_id']} no existe en Knowledge")
            for campo in ("predicate", "source_id", "status", "support_level", "nature"):
                if a[campo] != r[campo]:
                    raise PathError(f"arista {a['relationship_id']}: {campo} divergente")
    return True


# --- Las diez preguntas -----------------------------------------------------

def explicar(camino, k):
    por_id = {r["relationship_id"]: r for r in k["relationships"]}
    fuentes = {s["source_id"]: s for s in k["sources"]}
    L = [f"CAMINO {camino['path_id']}"]
    L.append(f" 1. Evento origen        {camino['event_id']}")
    L.append(f" 2. Entidades            " + " → ".join(
        f"{n['entity_id']}({n['type']})" for n in camino["nodes"]))
    L.append(f" 3. Relaciones           " + (", ".join(
        f"{a['predicate']}[{a['traversal_direction'][0]}]" for a in camino["edges"]) or "ninguna"))
    L.append(" 4. Fuentes")
    for a in camino["edges"]:
        s = fuentes.get(a["source_id"], {})
        L.append(f"      {a['relationship_id']}  {a['source_id']} ({s.get('tipo','?')}) "
                 f"— {s.get('localizador','?')}")
    estados = [f"{a['relationship_id']}:{a['status']}" for a in camino["edges"]]
    L.append(f" 5. Verificado/provisional  {', '.join(estados) or '—'}")
    L.append(f" 6. Válido en            {camino['as_of']}")
    L.append(f" 7. Termina              " + (
        f"{camino['incomplete_at']} — {MOTIVOS_INCOMPLETO[camino['incomplete_reason']]}"
        if camino["completeness"] == "PATH_INCOMPLETE" else "alcanzó su objetivo"))
    L.append(f" 8. Contradicciones      " + (
        "; ".join(f"{c['relationship_id']} niega {c['contradice']}" for c in camino["contradictions"])
        or "ninguna"))
    L.append(f" 9. Profundidad          {camino['depth']} (dirección {camino['direction_status']}, "
             f"estructural — no es signo económico)")
    L.append(f"10. Reproducible         path_id determinista: mismo evento, misma fecha y "
             f"misma secuencia de relaciones dan el mismo id")
    L.append(f"    Lo que NO sabemos    " + "\n                         ".join(camino["unknowns"]))
    return "\n".join(L)


# --- CLI --------------------------------------------------------------------

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Recorre el Knowledge desde una entidad.")
    ap.add_argument("entidad", help="entity_id de origen (P5A no crea entidades)")
    ap.add_argument("--evento", default="ev4:manual", help="event_id que origina el recorrido")
    ap.add_argument("--profundidad", type=int, default=PROFUNDIDAD_POR_DEFECTO)
    ap.add_argument("--a-fecha", help="recorrer el grafo tal y como era en esa fecha (ISO)")
    ap.add_argument("--hasta-no-financiera", action="store_true",
                    help="buscar un camino hasta un producto, tecnologia o material")
    ap.add_argument("--explicar", type=int, default=0, metavar="N",
                    help="responde las diez preguntas para los N primeros caminos")
    args = ap.parse_args(argv)

    k = _knowledge_mod().cargar()
    fecha = datetime.date.fromisoformat(args.a_fecha) if args.a_fecha else datetime.date.today()
    objetivo = {"product", "technology", "material"} if args.hasta_no_financiera else None
    cs = descubrir(args.evento, args.entidad, k, fecha, args.profundidad, objetivo)

    print(f"CAMINOS desde {args.entidad} · profundidad ≤ {args.profundidad} · a fecha {fecha}")
    print(f"  encontrados: {len(cs)}")
    for etiqueta, campo in (("validez", "validity"), ("completitud", "completeness")):
        cuenta = {}
        for c in cs:
            cuenta[c[campo]] = cuenta.get(c[campo], 0) + 1
        print(f"  {etiqueta}: {cuenta}")
    if objetivo and not any(c["completeness"] == "COMPLETE" for c in cs):
        print("  NO PATH — ningún camino alcanza un producto, tecnología o material.")
        print("  No es que no exista: es que no está representado.")
    for c in cs[:args.explicar]:
        print()
        print(explicar(c, k))
    return 0


if __name__ == "__main__":
    sys.exit(main())
