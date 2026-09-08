"""Historical Instrument Master v1 -- resolucion de instrumento por fecha.

D-46 dejo el diagnostico: `BACKFILL_READY = false` no por falta de datos
sino porque `historical instrument identity = incomplete`. Este modulo
cierra el minimo necesario.

    ticker != identity
    CIK    != permanent market identity

Un ticker SOLO produce un instrumento si existe una relacion temporalmente
valida entre ticker, listing/security e issuer. Un ticker reutilizado o sin
mapeo historico se marca AMBIGUOUS o UNRESOLVED -- NUNCA se acepta por el
mero hecho de que una fuente de precios devuelva datos.

No crea estructura paralela: usa `security`, `organization`, `ISSUED_BY`,
`LISTED_ON` y `valid_from`/`valid_to`, que ya existian. Lo unico nuevo en
el modelo es el predicado `SUCCEEDED_BY`, declarado NO CAUSAL (D-23).
"""
import datetime
import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)

import modelo  # noqa: E402

VALID = "VALID"
AMBIGUOUS = "AMBIGUOUS"
UNRESOLVED = "UNRESOLVED"
ESTADOS = (VALID, AMBIGUOUS, UNRESOLVED)

# El motivo NUNCA se deja implicito: un UNRESOLVED sin razon es
# indistinguible de un fallo del resolutor.
SIN_MAPEO = "no existe ningun alias declarado con ese identificador"
FUERA_DE_VIGENCIA = ("el identificador existe pero ninguna vigencia declarada "
                     "cubre esa fecha: puede ser un ticker reutilizado o anterior "
                     "a lo que hemos declarado")
VARIOS_CANDIDATOS = "mas de un instrumento reclama el identificador en esa fecha"
SIN_EMISOR = "hay instrumento pero ninguna relacion ISSUED_BY vigente en esa fecha"


def _fecha(v, defecto):
    try:
        return datetime.date.fromisoformat(v) if v else defecto
    except (TypeError, ValueError):
        return defecto


def _vigente(obj, as_of):
    d = as_of if isinstance(as_of, datetime.date) else datetime.date.fromisoformat(str(as_of)[:10])
    return (_fecha(obj.get("valid_from"), datetime.date.min) <= d
            <= _fecha(obj.get("valid_to"), datetime.date.max))


def resolve_instrument(identifier, as_of, k=None, scheme="ticker"):
    """Resuelve un identificador A UNA FECHA. `as_of` es obligatorio.

    Para historia NUNCA existe `resolve_instrument(identifier)`: sin fecha
    no hay identidad, porque el mismo simbolo designa instrumentos
    distintos en epocas distintas."""
    if as_of is None:
        raise ValueError(
            "resolve_instrument exige as_of: un identificador sin fecha no "
            "determina un instrumento historico (D-40)")
    k = k if k is not None else modelo.cargar()

    candidatos, existe_el_identificador = [], False
    for ent in k["entities"]:
        if ent.get("type") != "security":
            continue
        for al in ent.get("aliases") or []:
            if al.get("scheme") == scheme and al.get("value") == identifier:
                existe_el_identificador = True
                if _vigente(al, as_of):
                    candidatos.append((ent, al))

    base = {"identifier": identifier, "scheme": scheme, "as_of": str(as_of)[:10],
            "security": None, "issuer": None, "valid_from": None, "valid_to": None,
            "source": None, "venue": None}

    if not candidatos:
        return dict(base, identity_status=UNRESOLVED,
                    motivo=FUERA_DE_VIGENCIA if existe_el_identificador else SIN_MAPEO)
    if len(candidatos) > 1:
        return dict(base, identity_status=AMBIGUOUS, motivo=VARIOS_CANDIDATOS,
                    candidatos=sorted(e["entity_id"] for e, _ in candidatos))

    ent, al = candidatos[0]
    emisores = [r for r in k["relationships"]
                if r.get("predicate") == "ISSUED_BY"
                and r.get("subject") == ent["entity_id"]
                and r.get("polarity") == "AFFIRMS"
                and _vigente(r, as_of)]
    if not emisores:
        return dict(base, security=ent["entity_id"], identity_status=AMBIGUOUS,
                    motivo=SIN_EMISOR, valid_from=al.get("valid_from"),
                    valid_to=al.get("valid_to"), venue=al.get("venue"),
                    source=al.get("source_id"))
    if len(emisores) > 1:
        return dict(base, security=ent["entity_id"], identity_status=AMBIGUOUS,
                    motivo="mas de un emisor vigente en esa fecha",
                    candidatos=sorted(r["object"] for r in emisores))

    r = emisores[0]
    return dict(base, identity_status=VALID, security=ent["entity_id"],
                issuer=r["object"], venue=al.get("venue"),
                valid_from=al.get("valid_from"), valid_to=al.get("valid_to"),
                source=al.get("source_id"), issuer_source=r.get("source_id"))


def sucesor_de(security_id, as_of, k=None):
    """Sucesor declarado, si lo hay. La ausencia NO es un `false`: es que
    no se ha declarado ninguno."""
    k = k if k is not None else modelo.cargar()
    for r in k["relationships"]:
        if (r.get("predicate") == "SUCCEEDED_BY" and r.get("subject") == security_id
                and r.get("polarity") == "AFFIRMS" and _vigente(r, as_of)):
            return r["object"]
    return None


def apto_para_event_study(identifier, as_of, price_available, k=None):
    """Punto de control: precio Y identidad. Un precio sin identidad valida
    no entra en un event study identificado (D-43).

    `AMBIGUOUS` no se convierte en `UNAVAILABLE`: son estados distintos y
    el motivo viaja con el resultado."""
    r = resolve_instrument(identifier, as_of, k)
    apto = bool(price_available) and r["identity_status"] == VALID
    return {"identifier": identifier, "as_of": str(as_of)[:10],
            "price_available": bool(price_available),
            "instrument_identity_valid": r["identity_status"] == VALID,
            "identity_status": r["identity_status"], "motivo": r.get("motivo"),
            "security": r["security"], "issuer": r["issuer"],
            "elegible": apto}


if __name__ == "__main__":
    k = modelo.cargar()
    casos = [("XOM", "2019-04-26"), ("XOM", "2026-08-15"), ("XON", "1998-01-01"),
             ("MOB", "1995-06-01"), ("MOB", "2024-01-05"), ("DWDP", "2018-11-01"),
             ("DWDP", "2024-01-01"), ("DD", "2024-01-01"), ("UTX", "2019-01-23"),
             ("RTX", "2024-01-01"), ("WBA", "2019-06-01"), ("IBM", "2020-01-01"),
             ("NVDA", "2020-01-01")]
    print("=== resolve_instrument(identifier, as_of) ===")
    print("  %-6s %-12s %-11s %-16s %-24s %s" % ("ident", "as_of", "status", "security", "issuer", "motivo"))
    for ident, f in casos:
        r = resolve_instrument(ident, f, k)
        print("  %-6s %-12s %-11s %-16s %-24s %s" % (
            ident, f, r["identity_status"], r["security"] or "-", r["issuer"] or "-",
            (r.get("motivo") or "")[:48]))

    print("\n=== sucesion declarada ===")
    for s in ("sec:DWDP.NYSE", "sec:UTX.NYSE", "sec:WBA.NASDAQ", "sec:MOB.NASDAQ"):
        print("  %-16s -> %s" % (s, sucesor_de(s, "2026-09-08", k) or "sin sucesor declarado"))

    print("\n=== punto de control precio + identidad ===")
    for ident, f, precio in (("MOB", "1995-06-01", True), ("XOM", "2019-04-26", True),
                             ("DWDP", "2018-11-01", False), ("IBM", "2020-01-01", True)):
        c = apto_para_event_study(ident, f, precio, k)
        print("  %-5s @ %-11s precio=%-5s identidad=%-11s elegible=%s"
              % (ident, f, c["price_available"], c["identity_status"], c["elegible"]))
