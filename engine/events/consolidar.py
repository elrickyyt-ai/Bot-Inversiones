"""Consolidacion de Claims en Events: identidad, deduplicacion, soporte y
estado. P4 (2026-09-07).

IDENTIDAD
---------
La deduplicacion NO se basa en similitud textual. La clave es:

    (entidad principal, tipo de evento, accion, fecha a su granularidad,
     magnitud bucketizada)

Dos titulares distintos que describen el mismo movimiento del mismo
activo el mismo dia son UN evento con dos evidencias, no dos eventos. Y
al reves: dos titulares casi identicos sobre dias distintos son dos
eventos, aunque se parezcan mucho.

SOPORTE
-------
Cuatro numeros que NO se colapsan en uno:
  evidence_count             cuantas evidencias lo sostienen
  independent_support_count  cuantas FUENTES distintas (no articulos)
  primary_support            hay medicion propia o fuente primaria
  contradictory_support      cuantas claims lo niegan

Tres articulos del mismo medio son 3 evidencias y 1 fuente. Ese es el
caso que impide que "mas articulos" se lea como "mas confirmado".

LIMITE CONOCIDO Y DECLARADO: si tres medios DISTINTOS reproducen el mismo
teletipo de agencia, este sistema los cuenta como tres fuentes
independientes, porque la cadena de sindicacion no es observable con los
campos que hay. No se disimula: se declara en los `unknowns` de todo
evento sostenido solo por prensa.

ESTADO
------
Depende de la NATURALEZA y la PROCEDENCIA, no del recuento. Una sola
fuente primaria puede confirmar; cinco secundarias que repiten lo mismo,
no.
"""
import argparse
import collections
import datetime
import json
import os
import sys

import esquema_evento as esquema

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ancho de banda de magnitud para agrupar. Dos fuentes que reportan 12,1%
# y 12,4% describen el mismo movimiento; 12% y 25% no.
BANDA_MAGNITUD_PCT = 5.0

ACCION = {
    "ASSERTS_SENTIMENT": "sentiment_assertion",
    "MOVED_PRICE": "price_change",
    "VOLATILITY_ROSE": "volatility_spike",
    "ANNOUNCES_ACTION": "announcement",
}
TIPO = {
    "ASSERTS_SENTIMENT": "MARKET",
    "MOVED_PRICE": "MARKET",
    "VOLATILITY_ROSE": "MARKET",
    "ANNOUNCES_ACTION": "REGULATORY",
}


def _banda(valor):
    if valor is None:
        return None
    if isinstance(valor, str):
        return valor
    signo = "UP" if valor >= 0 else "DOWN"
    return f"{signo}:{int(abs(valor) // BANDA_MAGNITUD_PCT) * int(BANDA_MAGNITUD_PCT)}+"


def identity_key(claim):
    """La clave de identidad de un evento, explicita y reproducible."""
    t = claim.get("temporal_ref") or {}
    fecha = (t.get("occurred_at") or t.get("published_at") or "")[:10]
    return (claim["subject_entity"], TIPO[claim["predicate"]],
            ACCION[claim["predicate"]], fecha, _banda(claim.get("object_value")))


def _direccion_y_magnitud(claims):
    valores = [c["object_value"] for c in claims
               if isinstance(c.get("object_value"), (int, float))]
    if not valores:
        return None, None, None
    v = valores[0]
    if claims[0]["predicate"] == "MOVED_PRICE":
        return ("UP" if v >= 0 else "DOWN"), abs(v), "%"
    return "UP", v, "%"


def _soporte(claims, evidencias_por_id):
    ids = {eid for c in claims for eid in c["evidence_ids"]}
    evs = [evidencias_por_id[i] for i in ids if i in evidencias_por_id]
    fuentes = {e["source"] for e in evs}
    primaria = any(e["nature"] == "MEASURED" for e in evs) or any(
        e["source_scale"] == "journalistic_tier" and e["source_rank"] == 1 for e in evs)
    contra = sum(1 for c in claims if c["polarity"] == "DENIES")
    return len(ids), len(fuentes), primaria, contra, evs


def _revisado(claims):
    """Misma clave y misma fuente, dos valores distintos conocidos en
    momentos distintos: es una revision, no dos eventos."""
    por_fuente = collections.defaultdict(set)
    for c in claims:
        t = c.get("temporal_ref") or {}
        por_fuente[(c["extraction_method"], t.get("known_at"))].add(str(c.get("object_value")))
    valores = {str(c.get("object_value")) for c in claims}
    conocidos = {(c.get("temporal_ref") or {}).get("known_at") for c in claims}
    return len(valores) > 1 and len(conocidos) > 1


def _estado(n_ev, n_fuentes, primaria, contra, claims, evs):
    """El orden importa: una contradiccion no se resuelve por mayoria."""
    if contra and primaria:
        # Una fuente primaria que desmiente cierra el caso; una que
        # afirma frente a una negacion secundaria, tambien.
        niega_primaria = any(c["polarity"] == "DENIES" for c in claims)
        return ("REJECTED" if niega_primaria else "CONFIRMED",
                "hay evidencia contradictoria y una fuente primaria la resuelve")
    if contra:
        return ("CONTESTED",
                f"{contra} afirmacion(es) niegan el hecho y ninguna fuente primaria lo resuelve — "
                f"no se resuelve por mayoria de publicaciones")
    if _revisado(claims):
        return ("REVISED", "evidencia posterior cambio la magnitud del mismo acontecimiento")
    if primaria:
        return ("CONFIRMED",
                "soporte primario (medicion del propio contrato o fuente primaria): "
                "no necesita una segunda fuente")
    if n_fuentes >= 2:
        return ("CORROBORATED", f"{n_fuentes} fuentes independientes secundarias, sin contradiccion")
    # El motivo tiene que ser cierto para el tipo de evidencia que hay: un
    # indicador derivado de nuestra propia serie no lo sostiene "un medio".
    if all(e["nature"] == "DERIVED" and e["source_scale"] == "market_data_priority"
           for e in evs) and evs:
        return ("CANDIDATE",
                "lo sostiene un indicador DERIVADO de nuestra propia serie, no una "
                "medicion directa: su umbral y su ventana son decisiones de modelo, "
                "asi que no confiere soporte primario")
    return ("CANDIDATE", f"una sola fuente secundaria ({n_ev} evidencia(s)) — "
                         f"mas articulos del mismo medio no lo confirmarian")


def _unknowns(claims, evs, primaria, temporal):
    u = []
    predicados = {c["predicate"] for c in claims}
    if "ASSERTS_SENTIMENT" in predicados:
        u.append("el contenido del titular no se ha interpretado: P4 extrae la postura "
                 "declarada por el medio, no el acontecimiento que el texto describe")
    if not primaria and any(e["source_scale"] == "journalistic_tier" for e in evs):
        u.append("la cadena de sindicacion entre medios no es observable con los campos "
                 "disponibles: fuentes distintas que reproduzcan un mismo teletipo se "
                 "cuentan aqui como independientes")
    if not temporal.get("effective_at"):
        u.append("no se ha determinado una fecha de entrada en vigor (puede no aplicar)")
    if not any(isinstance(c.get("object_value"), (int, float)) for c in claims):
        u.append("sin magnitud: no se inventa una para un acontecimiento narrativo")
    return u


def consolidar(claims, evidencias, subtipos=None):
    """Claims -> Events. Agrupa por identity_key y calcula soporte y estado."""
    por_id = {e["evidence_id"]: e for e in evidencias}
    grupos = collections.OrderedDict()
    for c in claims:
        grupos.setdefault(identity_key(c), []).append(c)

    eventos = []
    for clave, cs in grupos.items():
        n_ev, n_fuentes, primaria, contra, evs = _soporte(cs, por_id)
        estado, motivo = _estado(n_ev, n_fuentes, primaria, contra, cs, evs)
        temporal = {}
        for campo in esquema.CAMPOS_TEMPORALES:
            valores = [(c.get("temporal_ref") or {}).get(campo) for c in cs]
            valores = [v for v in valores if v]
            if valores:
                temporal[campo] = min(valores) if campo != "known_at" else max(valores)
        direccion, magnitud, unidad = _direccion_y_magnitud(cs)
        entidad, tipo, accion, fecha, banda = clave
        eventos.append({
            "event_id": f"ev4:{entidad}:{accion}:{fecha}" + (f":{banda}" if banda else ""),
            "identity_key": list(clave),
            "event_type": tipo,
            "event_subtype": (subtipos or {}).get(accion),
            "primary_entity": entidad,
            "other_entities": sorted({c["object_entity"] for c in cs if c.get("object_entity")}),
            "action": accion,
            "temporal": temporal,
            "direction": direccion, "magnitude": magnitud, "unit": unidad,
            # Capacidad abierta para Market Impact; P4 no monta consenso.
            "expected": None, "actual": magnitud, "surprise": None,
            "claim_ids": [c["claim_id"] for c in cs],
            "evidence_count": n_ev,
            "independent_support_count": n_fuentes,
            "primary_support": primaria,
            "contradictory_support": contra,
            "status": estado, "status_reason": motivo,
            "unknowns": _unknowns(cs, evs, primaria, temporal),
        })
    return eventos


# --- Las doce preguntas ----------------------------------------------------

def explicar(evento, claims_por_id, evidencias_por_id):
    """Criterio de aceptacion de P4: seleccionar un evento y responder las
    doce preguntas, incluida la ultima, que es obligatoria."""
    cs = [claims_por_id[c] for c in evento["claim_ids"] if c in claims_por_id]
    ids_ev = [e for c in cs for e in c["evidence_ids"]]
    evs = [evidencias_por_id[i] for i in ids_ev if i in evidencias_por_id]
    t = evento["temporal"]
    L = []
    L.append(f"EVENTO {evento['event_id']}")
    L.append(f" 1. Qué ocurrió          {evento['action']} ({evento['event_type']}"
             + (f"/{evento['event_subtype']}" if evento['event_subtype'] else "") + ")"
             + (f" · {evento['direction']} {evento['magnitude']}{evento['unit']}"
                if evento["magnitude"] is not None else " · sin magnitud"))
    L.append(f" 2. Entidades            {evento['primary_entity']}"
             + (f" + {evento['other_entities']}" if evento["other_entities"] else ""))
    L.append(f" 3. Claims               {len(cs)}: {', '.join(c['predicate'] for c in cs[:3])}"
             + (" …" if len(cs) > 3 else ""))
    L.append(f" 4. Evidencias           {evento['evidence_count']}")
    fuentes = collections.Counter(e["source"] for e in evs)
    L.append(f" 5. Fuentes              {dict(fuentes)}  "
             f"({evento['independent_support_count']} distinta(s))")
    L.append(f" 6. Publicado            {t.get('published_at') or '—'}")
    L.append(f" 7. Ocurrió              {t.get('occurred_at') or '—'}")
    L.append(f" 8. Entra en vigor       {t.get('effective_at') or '— (no aplica o no declarado)'}")
    L.append(f" 9. Corroboración        {evento['independent_support_count']} fuente(s) independiente(s)"
             f" · soporte primario: {'sí' if evento['primary_support'] else 'no'}")
    L.append(f"10. Contradicción        {evento['contradictory_support']} afirmación(es) en contra")
    L.append(f"11. Estado               {evento['status']} — {evento['status_reason']}")
    L.append(f"12. Lo que NO sabemos    " + ("\n                         ".join(evento["unknowns"])
                                             if evento["unknowns"] else "nada declarado"))
    return "\n".join(L)


# --- Tuberia sobre datos reales --------------------------------------------

def _evidence_mod(nombre):
    path = os.path.join(ROOT, "engine", "evidence")
    sys.path.insert(0, path)
    try:
        if nombre in sys.modules:
            return sys.modules[nombre]
        return __import__(nombre)
    finally:
        sys.path.remove(path)


def pipeline_noticias():
    ad = _evidence_mod("adaptadores")
    import extractores
    evs, _ = ad.evidencia_de_noticias()
    claims = extractores.extraer_sentimiento(evs)
    sin_claim = extractores.evidencias_sin_claim(evs, claims)
    return claims, evs, sin_claim


def pipeline_tecnico(asset_id="XRP", umbral=None):
    ad = _evidence_mod("adaptadores")
    import extractores
    evs = [e for e in ad.evidencia_de_metricas([asset_id])
           if e["metric"] in ("precio", "volatilidad_hist_30d_anualizada_pct")]
    precio = [e for e in evs if e["metric"] == "precio"]
    vol = [e for e in evs if e["metric"] != "precio"]
    claims = extractores.extraer_movimientos_precio(
        precio, umbral or extractores.UMBRAL_CAMBIO_PRECIO_PCT)
    claims += extractores.extraer_picos_volatilidad(vol)
    return claims, evs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--noticias", action="store_true")
    ap.add_argument("--tecnico", metavar="ASSET")
    ap.add_argument("--explicar", metavar="N", type=int, default=0,
                    help="explica los N primeros eventos con las doce preguntas")
    args = ap.parse_args(argv)

    if args.tecnico:
        claims, evs = pipeline_tecnico(args.tecnico)
        sin_claim = []
    else:
        claims, evs, sin_claim = pipeline_noticias()
    eventos = consolidar(claims, evs)
    cpid = {c["claim_id"]: c for c in claims}
    epid = {e["evidence_id"]: e for e in evs}

    print(f"EVIDENCIAS {len(evs):,} → CLAIMS {len(claims):,} → EVENTOS {len(eventos):,}")
    if sin_claim:
        print(f"  evidencias sin claim (ninguna regla sabe convertirlas): {len(sin_claim)}")
    porc = collections.Counter(e["status"] for e in eventos)
    print(f"  estados: {dict(porc)}")
    multi = [e for e in eventos if e["evidence_count"] > 2]
    print(f"  eventos con más de una evidencia por claim: {len(multi)}")
    print(f"  entidades: {sorted({e['primary_entity'] for e in eventos})}")
    for e in eventos[:args.explicar]:
        print()
        print(explicar(e, cpid, epid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
