"""Evidence Gap -> Data Requirement -- P5D (2026-09-07).

Cierra el bucle que P5C dejo abierto:

    EVENT -> CAUSAL PATH -> ECONOMIC MECHANISM -> REQUIRED EVIDENCE
          -> [P5D] -> AVAILABLE EVIDENCE -> (P6 ECONOMIC IMPACT)

P5B deja `requires_evidence` como cadenas de texto dentro de cada tramo.
Este modulo las parsea, las deduplica (el mismo requisito aparece en
decenas de caminos) y las resuelve contra el contrato REAL, diciendo por
cada una si el dato existe, con que metrica, de que fuente y con que
frescura.

Lo que NO hace, a proposito:
  - No descarga nada. Lee `data/` como lo lee cobertura.py.
  - No declara equivalencias: las lee de `catalogo.py`, que es de mano.
  - No abre fuentes nuevas. Produce la JUSTIFICACION para abrirlas, que
    es el orden correcto y no el contrario.

Uso:
    python3 engine/requirements/resolver.py sec:NVDA.NASDAQ
    python3 engine/requirements/resolver.py --requisito "demand(org:nvidia)"
    python3 engine/requirements/resolver.py sec:NVDA.NASDAQ --json
"""
import datetime
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _sub in ("contract", "causal", "knowledge", "requirements"):
    _p = os.path.join(RAIZ, "engine", _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cadencias        # noqa: E402
import catalogo         # noqa: E402
import cobertura        # noqa: E402
import esquema_requisito as E  # noqa: E402
import storage          # noqa: E402

REQUIREMENTS_PATH = os.path.join(storage.DATA_DIR, "requirements.json")

_RE_REQUISITO = re.compile(r"^([a-z_]+)\(([^)]+)\)$")


def parsear(texto):
    """'demand(org:nvidia)' -> ('demand', 'org:nvidia'). El formato lo fija
    P5B; si algun dia cambia, esto falla en vez de adivinar."""
    m = _RE_REQUISITO.match(texto.strip())
    if not m:
        raise E.RequirementError(f"requisito con formato desconocido: {texto!r}")
    return m.group(1), m.group(2)


def observable_de(entity_id, k):
    """Que asset_id del contrato observa a esta entidad.

    Directo si la entidad lo lleva; si no, a traves de ISSUED_BY. Ese
    predicado esta en SIN_MECANISMO de P5B porque no transmite ningun
    efecto economico -- y por la misma razon (P5B, literal: "la accion y
    la empresa son el mismo sujeto economico visto de dos formas") es
    exactamente el predicado correcto para IDENTIFICAR. Distinguir
    transmitir de identificar es justo lo que hace que esto no sea una
    inferencia.
    """
    ent = {e["entity_id"]: e for e in k["entities"]}
    e = ent.get(entity_id)
    if e is None:
        return None, None
    if e.get("asset_id"):
        return e["asset_id"], entity_id
    for r in k["relationships"]:
        if (r["predicate"] == "ISSUED_BY" and r["polarity"] == "AFFIRMS"
                and r["object"] == entity_id):
            sec = ent.get(r["subject"])
            if sec and sec.get("asset_id"):
                return sec["asset_id"], r["subject"]
    return None, None


def resolver(variable, entity_id, k, indice_metricas):
    """Un requisito -> un DataRequirement completo."""
    ent = {e["entity_id"]: e for e in k["entities"]}
    req = {
        "requirement_id": f"req:{variable}:{entity_id}",
        "variable": variable,
        "entity_id": entity_id,
        "entity_type": ent[entity_id]["type"] if entity_id in ent else None,
        "concept_id": catalogo.concepto(variable),
        "concept_status": "DECLARED" if catalogo.concepto(variable) else "UNDECLARED",
        "observable_asset_id": None,
        "candidates": [],
        "availability": "UNKNOWN",
        "freshness": "UNKNOWN",
        "resolved_by": None,
        "blocking_for": [],
        "reasons": [],
        "unknowns": [],
    }

    if entity_id not in ent:
        req["reasons"].append("ENTITY_NOT_DECLARED")
        req["unknowns"].append(f"{entity_id} no esta en Knowledge: P5D no crea entidades")
        return req

    motivo = catalogo.no_aplica(variable, entity_id)
    if motivo:
        req["availability"] = "NOT_APPLICABLE"
        req["reasons"].append("DECLARED_NOT_APPLICABLE")
        req["unknowns"].append(motivo)
        return req

    asset_id, via = observable_de(entity_id, k)
    req["observable_asset_id"] = asset_id

    candidatas = catalogo.candidatas(variable, req["entity_type"])
    if not candidatas:
        req["availability"] = "MISSING"
        req["reasons"].append("NO_CANDIDATE_METRIC")
        req["unknowns"].append(
            f"ninguna metrica del contrato esta declarada para observar "
            f"{variable} en una entidad de tipo {req['entity_type']}")
        if asset_id is None:
            req["reasons"].append("NO_OBSERVABLE")
            req["unknowns"].append(
                f"{entity_id} ademas no tiene ningun observable: ni asset_id propio "
                f"ni un valor que la represente via ISSUED_BY")
        return req

    if asset_id is None:
        req["availability"] = "MISSING"
        req["reasons"].append("NO_OBSERVABLE")
        req["unknowns"].append(
            f"hay metricas candidatas para {variable}, pero {entity_id} no tiene "
            f"ningun observable en el contrato al que aplicarlas")
        return req

    presentes = []
    for c in candidatas:
        fila = indice_metricas.get((asset_id, c["domain"], c["metric"]))
        cand = dict(c)
        cand["asset_id"] = asset_id
        cand["presente"] = fila is not None
        cand["data_as_of"] = fila["data_as_of"] if fila else None
        cand["retrieved_at"] = fila["retrieved_at"] if fila else None
        cand["freshness"] = fila["estado_frescura"] if fila else "UNKNOWN"
        req["candidates"].append(cand)
        if fila:
            presentes.append(cand)

    if not presentes:
        req["availability"] = "MISSING"
        req["reasons"].append("CANDIDATE_WITHOUT_DATA")
        req["unknowns"].append(
            f"las {len(candidatas)} metrica(s) candidata(s) estan declaradas pero "
            f"ninguna tiene filas para {asset_id}")
        return req

    # Preferencia: una medicion directa manda sobre cualquier proxy.
    directas = [c for c in presentes if c["relation"] == "MEASURES"]
    elegida = directas[0] if directas else presentes[0]
    req["resolved_by"] = elegida["metric"]
    req["freshness"] = elegida["freshness"]
    if directas:
        req["availability"] = "AVAILABLE"
    else:
        req["availability"] = E.SOLO_PROXY_MAXIMO
        req["reasons"].append("ONLY_PROXY")
        req["unknowns"].append(
            f"{elegida['metric']} es un proxy declarado de {variable}, no una medicion: "
            f"{elegida['confounder']}")
    if via and via != entity_id:
        req["unknowns"].append(
            f"el dato se observa sobre {via} ({asset_id}), no sobre {entity_id} "
            f"directamente: ISSUED_BY identifica al mismo sujeto, no transmite nada")
    return req


def _indice_metricas(hoy, con_history):
    cob = cobertura.evaluar(hoy=hoy, con_history=con_history)
    return {(f["asset_id"], f["domain"], f["metric"]): f for f in cob["por_metrica"]}


def requisitos_de(valoraciones):
    """(requisito, [tramos que bloquea]) deduplicado. El mismo requisito
    aparece en decenas de caminos: se resuelve una vez y se registra a
    quien bloquea."""
    vistos = {}
    for a in valoraciones:
        for t in a["segments"]:
            for texto in t["requires_evidence"]:
                v, e = parsear(texto)
                vistos.setdefault((v, e), []).append({
                    "assessment_id": a["assessment_id"],
                    "relationship_id": t["relationship_id"],
                    "mechanism": t["mechanism"],
                    "affected_variable": t["affected_variable"],
                })
    return vistos


def resolver_valoraciones(valoraciones, k, hoy=None, con_history=True):
    hoy = hoy or datetime.date.today()
    idx = _indice_metricas(hoy, con_history)
    salida = []
    for (v, e), bloquea in sorted(requisitos_de(valoraciones).items()):
        r = resolver(v, e, k, idx)
        r["blocking_for"] = bloquea
        salida.append(r)
    return salida


def explicar(r):
    L = [f"REQUISITO {r['requirement_id']}",
         f"  variable   {r['variable']} sobre {r['entity_id']} ({r['entity_type']})",
         f"  concepto   {r['concept_id'] or '— sin declarar'} ({r['concept_status']})",
         f"  observable {r['observable_asset_id'] or '— ninguno'}"]
    if r["candidates"]:
        L.append("  candidatas")
        for c in r["candidates"]:
            marca = "·" if c["presente"] else "✗"
            L.append(f"    {marca} {c['metric']:26} {c['relation']:8} "
                     f"{c['freshness']:8} {c['data_as_of'] or '—'}")
            L.append(f"        {c['justification']}")
            if c.get("confounder"):
                L.append(f"        confusor: {c['confounder']}")
    else:
        L.append("  candidatas  — ninguna declarada")
    L.append(f"  DISPONIBILIDAD {r['availability']}   FRESCURA {r['freshness']}")
    if r["resolved_by"]:
        L.append(f"  resuelto con   {r['resolved_by']}")
    if r["reasons"]:
        L.append(f"  motivos        {', '.join(r['reasons'])}")
    for u in r["unknowns"]:
        L.append(f"      · {u}")
    if r["blocking_for"]:
        mecs = sorted({b["mechanism"] for b in r["blocking_for"]})
        L.append(f"  bloquea        {len(r['blocking_for'])} tramo(s) · {', '.join(mecs)}")
    return "\n".join(L)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description="Resuelve los requisitos de evidencia que produce P5B.")
    ap.add_argument("entidad", nargs="?", help="entity_id de origen del recorrido")
    ap.add_argument("--requisito", action="append", default=[],
                    metavar="VAR(ENTIDAD)", help="resolver un requisito suelto")
    ap.add_argument("--accion", default="demand_change")
    ap.add_argument("--direccion", default="UP", choices=["UP", "DOWN"])
    ap.add_argument("--profundidad", type=int, default=3)
    ap.add_argument("--sin-history", action="store_true",
                    help="leer solo incoming/, sin PyArrow")
    ap.add_argument("--json", action="store_true", help=f"escribir {REQUIREMENTS_PATH}")
    args = ap.parse_args(argv)

    import caminos
    import modelo
    import valoracion

    k = modelo.cargar()
    hoy = datetime.date.today()

    if args.requisito:
        idx = _indice_metricas(hoy, not args.sin_history)
        reqs = []
        for texto in args.requisito:
            v, e = parsear(texto)
            reqs.append(resolver(v, e, k, idx))
    elif args.entidad:
        evento = {"event_id": f"ev4:p5d:{args.accion}", "primary_entity": args.entidad,
                  "action": args.accion, "direction": args.direccion}
        cs = caminos.descubrir(evento["event_id"], args.entidad, k, hoy, args.profundidad)
        vals = [valoracion.valorar(evento, c, [], k, modelo.vigente, hoy) for c in cs]
        reqs = resolver_valoraciones(vals, k, hoy, not args.sin_history)
    else:
        ap.error("hace falta una entidad o al menos un --requisito")

    incidencias = [x for r in reqs for x in E.validar(r)]
    print(f"REQUISITOS DE EVIDENCIA — {hoy}   ({len(reqs)} distinto(s))")
    cuenta = {}
    for r in reqs:
        cuenta[r["availability"]] = cuenta.get(r["availability"], 0) + 1
    print(f"  disponibilidad: {cuenta}")
    print()
    for r in reqs:
        print(explicar(r))
        print()
    if incidencias:
        print("INCIDENCIAS DE ESQUEMA:")
        for i in incidencias:
            print(f"  · {i}")
        return 1
    if args.json:
        with open(REQUIREMENTS_PATH, "w", encoding="utf-8") as f:
            json.dump({"generado_para": hoy.isoformat(), "requisitos": reqs}, f,
                      ensure_ascii=False, indent=1)
        print(f"escrito {REQUIREMENTS_PATH}")
    if not reqs:
        return 0
    if all(r["availability"] in ("MISSING", "UNKNOWN") for r in reqs):
        print("Ningun requisito se resuelve con las fuentes actuales. Eso NO es un")
        print("fallo: es la especificacion de que datos harian falta para que P6")
        print("pudiera calcular algo, y cada uno dice por que no esta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
