"""Consulta del Knowledge Model -- P2 (2026-09-06).

El criterio de exito de P2 no es "tenemos 45 relaciones". Es poder
preguntarle al sistema por una relacion y obtener quien, que, desde
cuando, hasta cuando, por que lo creemos y donde esta la evidencia. Un
JSON que valida pero que nadie puede interrogar no demuestra nada.

Uso:
    python3 engine/knowledge/consulta.py NVDA
    python3 engine/knowledge/consulta.py BTC --hacia US
    python3 engine/knowledge/consulta.py XRP --a-fecha 2022-01-01
    python3 engine/knowledge/consulta.py NVDA --camino-a-no-financiero
    python3 engine/knowledge/consulta.py --validar
"""
import argparse
import datetime
import sys

import modelo

TIPOS_NO_FINANCIEROS = {"product", "technology", "material"}


def resolver(k, texto):
    """Acepta un entity_id, un asset_id o un valor de alias. Devuelve
    todas las entidades que coinciden -- si son varias, el identificador
    es ambiguo y eso es informacion, no un fallo."""
    exactos = [e for e in k["entities"] if e["entity_id"] == texto]
    if exactos:
        return exactos
    return [e for e in k["entities"]
            if e.get("asset_id") == texto
            or any(a.get("value") == texto for a in e.get("aliases") or [])]


def relaciones_de(k, entity_id, a_fecha=None):
    fuera = []
    for r in k["relationships"]:
        if r["subject"] != entity_id and r["object"] != entity_id:
            continue
        if a_fecha and not modelo.vigente(r, a_fecha):
            continue
        fuera.append(r)
    return fuera


def _fuente(k, source_id):
    for s in k["sources"]:
        if s["source_id"] == source_id:
            return s
    return None


def _linea_relacion(k, r, entity_id):
    direccion = "→" if r["subject"] == entity_id else "←"
    otro = r["object"] if r["subject"] == entity_id else r["subject"]
    neg = "NO " if r["polarity"] == "DENIES" else ""
    vig = r["valid_from"] + (f" → {r['valid_to']}" if r.get("valid_to") else " → vigente")
    src = _fuente(k, r["source_id"])
    return (f"  {neg}{r['predicate']} {direccion} {otro}\n"
            f"      vigencia     {vig}\n"
            f"      naturaleza   {r['nature']} · estado {r['status']} · respaldo {r['support_level']}\n"
            f"      fuente       {r['source_id']} ({src['tipo'] if src else '?'}) — "
            f"{src['localizador'] if src else '?'}\n"
            f"      dice         {r['statement']}\n"
            f"      comprobado   {r['last_verified']} · {r['verification_method']}")


def _avisos(k, rels):
    """Lo que el lector tiene que saber ANTES de usar estas relaciones."""
    avisos = []
    for r in rels:
        src = _fuente(k, r["source_id"])
        if r["status"] == "PROVISIONAL":
            avisos.append(
                f"{r['subject']} {r['predicate']} {r['object']} es PROVISIONAL: "
                f"{'procede de una regla del propio motor, no de evidencia estructural independiente. ' if src and src['tipo'] == 'INTERNAL_RULE' else ''}"
                f"No debe tratarse como un hecho del mundo.")
        elif src and src["tipo"] == "COMPANY_STATEMENT" and src.get("publisher") in (r["subject"], r["object"]):
            avisos.append(f"{r['relationship_id']}: la única fuente es la parte interesada ({src['publisher']}).")
    return avisos


def describir(k, texto, a_fecha=None):
    ents = resolver(k, texto)
    if not ents:
        print(f"NO CONOCIDO — '{texto}' no resuelve a ninguna entidad declarada.")
        print("El sistema no sabe nada de esto. No es lo mismo que no existir.")
        return 1
    if len(ents) > 1:
        print(f"AMBIGUO — '{texto}' resuelve a {[e['entity_id'] for e in ents]}.")
        return 1
    e = ents[0]
    print(f"ENTIDAD      {e['entity_id']}")
    print(f"  tipo       {e['type']} · estado {e['status']}")
    print(f"  nombre     {e['nombre']}")
    if e.get("asset_id"):
        print(f"  asset_id   {e['asset_id']}  (clave en el Data Contract)")
    if e.get("aliases"):
        print("  aliases")
        for a in e["aliases"]:
            v = f" en {a['venue']}" if a.get("venue") else ""
            print(f"      {a['scheme']:20} {a['value']}{v}   [{a['source_id']}]")
    if e.get("nota"):
        print(f"  nota       {e['nota']}")

    rels = relaciones_de(k, e["entity_id"], a_fecha)
    cuando = f" vigentes a {a_fecha}" if a_fecha else ""
    print(f"\nRELACIONES{cuando} ({len(rels)})")
    if not rels:
        print("  ninguna.")
    for r in sorted(rels, key=lambda x: (x["predicate"], x["object"])):
        print(_linea_relacion(k, r, e["entity_id"]))

    avisos = _avisos(k, rels)
    if avisos:
        print("\nAVISOS")
        vistos = set()
        for a in avisos:
            if a not in vistos:
                print(f"  ! {a}")
                vistos.add(a)
    return 0


def entre(k, a, b, a_fecha=None):
    ea, eb = resolver(k, a), resolver(k, b)
    if len(ea) != 1 or len(eb) != 1:
        print("NO RESOLUBLE — uno de los dos identificadores no resuelve a una entidad única.")
        return 1
    ea, eb = ea[0]["entity_id"], eb[0]["entity_id"]
    rels = [r for r in k["relationships"]
            if {r["subject"], r["object"]} == {ea, eb}
            and (not a_fecha or modelo.vigente(r, a_fecha))]
    print(f"¿QUÉ SABE EL SISTEMA SOBRE {ea} → {eb}?\n")
    if not rels:
        print("NADA DIRECTO. No hay ninguna relación declarada entre las dos entidades")
        print("en esa fecha. El sistema no sabe si existe: sabe que no la ha registrado.")
        return 0
    for r in rels:
        print(_linea_relacion(k, r, ea))
    for a in _avisos(k, rels):
        print(f"\n  ! {a}")
    return 0


def camino_a_no_financiero(k, texto, profundidad=4):
    """Recorrido acotado hasta una entidad no financiera (producto,
    tecnologia o material). Si no llega, lo dice: no completa el camino
    con lo que 'deberia' haber."""
    ents = resolver(k, texto)
    if len(ents) != 1:
        print("NO RESOLUBLE")
        return 1
    origen = ents[0]["entity_id"]
    tipos = {e["entity_id"]: e["type"] for e in k["entities"]}
    vecinos = {}
    for r in k["relationships"]:
        if r["polarity"] == "DENIES":
            continue
        vecinos.setdefault(r["subject"], []).append((r["object"], r))
        vecinos.setdefault(r["object"], []).append((r["subject"], r))

    print(f"¿QUÉ CAMINO CONOCIDO EXISTE ENTRE {origen} Y UNA ENTIDAD NO FINANCIERA?")
    print(f"(no financiera = {', '.join(sorted(TIPOS_NO_FINANCIEROS))} · profundidad máxima {profundidad})\n")
    cola, visto = [(origen, [])], {origen}
    while cola:
        actual, camino = cola.pop(0)
        if len(camino) >= profundidad:
            continue
        for siguiente, r in vecinos.get(actual, []):
            if siguiente in visto:
                continue
            nuevo = camino + [(actual, r, siguiente)]
            if tipos.get(siguiente) in TIPOS_NO_FINANCIEROS:
                print("CAMINO ENCONTRADO")
                for a, rr, b in nuevo:
                    print(f"  {a} --{rr['predicate']}--> {b}   [{rr['status']}, {rr['source_id']}]")
                return 0
            visto.add(siguiente)
            cola.append((siguiente, nuevo))
    print("NO PATH")
    print("  El sistema no conoce ningún camino desde esta entidad hasta un producto,")
    print("  una tecnología o un material. No es que el camino no exista: es que no")
    print("  está representado. La cadena NVIDIA → TSMC → CoWoS → HBM/materiales vive")
    print("  hoy en knowledge/pendiente/, sin fuente documentada, y por eso no se")
    print("  puede recorrer.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("entidad", nargs="?", help="entity_id, asset_id o alias")
    ap.add_argument("--hacia", help="segunda entidad, para preguntar por la relación entre las dos")
    ap.add_argument("--a-fecha", help="consultar el estado a una fecha (ISO)")
    ap.add_argument("--camino-a-no-financiero", action="store_true")
    ap.add_argument("--validar", action="store_true", help="valida todo el conjunto y sale")
    args = ap.parse_args(argv)

    k = modelo.cargar()
    if args.validar:
        errores = modelo.validar(k)
        print(f"Knowledge: {len(k['entities'])} entidades · {len(k['relationships'])} relaciones · "
              f"{len(k['concepts'])} conceptos · {len(k['sources'])} fuentes")
        cand = [x for x in modelo.cargar_pendiente() if x.get("predicate")]
        print(f"Candidatas en pendiente/ (fuera del conjunto válido): {len(cand)}")
        for e in errores:
            print(f"  - {e}")
        print(f"RESULTADO: {'PASS' if not errores else f'FAIL ({len(errores)} incidencias)'}")
        return 0 if not errores else 1

    if not args.entidad:
        ap.error("hace falta una entidad, o --validar")
    fecha = datetime.date.fromisoformat(args.a_fecha) if args.a_fecha else None
    if args.camino_a_no_financiero:
        return camino_a_no_financiero(k, args.entidad)
    if args.hacia:
        return entre(k, args.entidad, args.hacia, fecha)
    return describir(k, args.entidad, fecha)


if __name__ == "__main__":
    sys.exit(main())
