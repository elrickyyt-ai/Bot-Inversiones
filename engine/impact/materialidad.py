"""Resolucion de materialidad -- P6.1 (2026-09-07).

    OBSERVATION
        |
    APPLICABILITY CHECK   entidad · relacion · vigencia temporal
        |
    DERIVATION
        |
    materiality status

Los cuatro pasos estan separados a proposito. Si la comprobacion de
aplicabilidad estuviera mezclada con la busqueda, una observacion VALIDA
pero INAPLICABLE acabaria indistinguible de un hueco de datos, y el
sistema mandaria a buscar una fuente que ya tiene.

Por eso hay dos motivos y no uno:

    NO_SUPPORTING_EVIDENCE               no hay observacion: hace falta una fuente
    EVIDENCE_EXISTS_BUT_NOT_APPLICABLE   la hay y es valida, pero no alcanza

No son dos estados publicos -- los dos dan UNKNOWN -- pero si dos
motivos, y esa trazabilidad es la diferencia entre "buscad datos" y "no
os molesteis, ya los tenemos y no sirven para esto".
"""
import datetime
import os
import sys

_R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _s in ("causal", "impact", "knowledge"):
    _p = os.path.join(_R, "engine", _s)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import esquema_materialidad as EM  # noqa: E402
import observaciones as OBS  # noqa: E402

# Que relacion mete a la contraparte en la poblacion de cada base, y en
# que sentido. Sin esto, "cliente de TSMC" y "proveedor de NVIDIA" serian
# indistinguibles y la cota de TSMC acabaria aplicada a Samsung.
POBLACION = {
    "SUPPLIER_REVENUE_EXPOSURE": ("SUPPLIES", "sujeto_es_sujeto"),
    "VOLUME_SHARE":              ("SUPPLIES", "sujeto_es_objeto"),
    "COST_SHARE":                ("USES", "sujeto_es_sujeto"),
    "CAPACITY_SHARE":            ("USES", "sujeto_es_objeto"),
}


def _f(v):
    return datetime.date.fromisoformat(v) if isinstance(v, str) else v


def _solapa(rel, periodo):
    """La relacion tiene que estar vigente EN EL PERIODO OBSERVADO, no
    hoy. Es la disciplina de P5C de no extrapolar valid_from, propagada
    un nivel arriba: una cota de 2023 no dice nada de una contraparte que
    el sistema no sabia que existiera en 2023."""
    ini, fin = _f(periodo[0]), _f(periodo[1])
    desde = _f(rel.get("valid_from"))
    hasta = _f(rel.get("valid_to"))
    if desde is None or desde > fin:
        return False
    return hasta is None or hasta > ini


def relaciones_de_poblacion(basis, subject, counterparty, k):
    """Paso 2a/2b: entidad y relacion. Todas las relaciones AFIRMATIVAS
    que meten a `counterparty` en la poblacion de `subject`, sin mirar
    todavia la vigencia."""
    pred, sentido = POBLACION[basis]
    out = []
    for r in k["relationships"]:
        if r["predicate"] != pred or r["polarity"] != "AFFIRMS":
            continue
        if sentido == "sujeto_es_sujeto":
            ok = r["subject"] == subject and r["object"] == counterparty
        else:
            ok = r["object"] == subject and r["subject"] == counterparty
        if ok:
            out.append(r)
    return out


def aplicabilidad(obs, counterparty, k):
    """Paso 2: ¿alcanza esta observacion a esta contraparte?

    Devuelve (relacion_que_la_hace_aplicable, motivo_si_no)."""
    rels = relaciones_de_poblacion(obs["basis"], obs["subject"], counterparty, k)
    if not rels:
        return None, "NO_RELATIONSHIP"
    vigentes = [r for r in rels if _solapa(r, obs["periodo"])]
    if not vigentes:
        return None, "RELATIONSHIP_NOT_VALID_IN_PERIOD"
    return vigentes[0], None


def resolver_materialidad(basis, subject, counterparty, k, as_of=None):
    """Los cuatro pasos, en orden y sin mezclarlos."""
    as_of = as_of or datetime.date.today()
    m = {
        "materiality_id": f"mat:{basis}:{subject}:{counterparty}",
        "as_of": as_of.isoformat() if hasattr(as_of, "isoformat") else as_of,
        "rule_version": EM.RULE_VERSION,
        "basis": basis, "scope": "POPULATION_BOUND", "status": "UNKNOWN",
        "subject": subject, "counterparty": counterparty,
        "value": None, "upper_bound": None, "unit": None,
        "observed_on": None, "observed_period": None, "applied_via": None,
        "evidence_ids": [], "reasons": [], "unknowns": [],
    }

    # --- 1. OBSERVATION ---
    candidatas = OBS.de(basis, subject)
    if not candidatas:
        m["reasons"].append("NO_SUPPORTING_EVIDENCE")
        m["unknowns"].append(
            f"ninguna observacion de {basis} sobre {subject}: hace falta una fuente")
        return m

    # --- 2. APPLICABILITY CHECK ---
    aplicables, rechazos = [], []
    for o in candidatas:
        rel, motivo = aplicabilidad(o, counterparty, k)
        if rel is not None:
            aplicables.append((o, rel))
        else:
            rechazos.append((o, motivo))

    if not aplicables:
        # La distincion que importa: la evidencia EXISTE y es valida.
        m["reasons"].append("EVIDENCE_EXISTS_BUT_NOT_APPLICABLE")
        for o, motivo in rechazos:
            if motivo not in m["reasons"]:
                m["reasons"].append(motivo)
            m["unknowns"].append(
                f"{o['observation_id']} ({o['upper_bound']}{o['unit']}, "
                f"{o['periodo'][0][:4]}) no aplica a {counterparty}: {EM.MOTIVOS[motivo]}")
        return m

    # --- 3. DERIVATION ---
    # La cota mas estricta de entre las APLICABLES. El orden importa: no
    # se elige la ultima ni la menor de todas, se elige entre las que han
    # pasado la comprobacion.
    o, rel = min(aplicables, key=lambda x: x[0]["upper_bound"])
    if o["upper_bound"] >= EM.COTA_TRIVIAL_PCT:
        m["reasons"].append("TRIVIAL_BOUND_DISCARDED")
        m["unknowns"].append(
            f"{o['observation_id']} da {o['upper_bound']}{o['unit']}: un tope aritmetico "
            f"no es una cota")
        return m

    # --- 4. STATUS ---
    m["status"] = "BOUNDED"
    m["upper_bound"] = o["upper_bound"]
    m["unit"] = o["unit"]
    m["observed_on"] = o["subject"]
    m["observed_period"] = list(o["periodo"])
    m["applied_via"] = rel["relationship_id"]
    m["evidence_ids"] = [o["observation_id"]]
    m["reasons"].append("DERIVED_FROM_POPULATION_BOUND")
    m["unknowns"].append(
        f"cota, no atribucion: la fuente dice que el mayor cliente de {subject} "
        f"representa {o['upper_bound']}{o['unit']}, sin nombrarlo. Que {counterparty} "
        f"sea ese cliente NO se afirma")
    if rechazos:
        m["unknowns"].append(
            f"{len(rechazos)} observacion(es) descartada(s) por no ser aplicables, no por "
            f"ser peores: " + ", ".join(f"{o['observation_id']} ({mo})" for o, mo in rechazos))
    return m


def explicar(m):
    L = [f"MATERIALIDAD {m['materiality_id']}",
         f"  base       {m['basis']}  ({m['scope']})",
         f"  sujeto     {m['subject']}   contraparte {m['counterparty']}",
         f"  ESTADO     {m['status']}" + (f"  <= {m['upper_bound']}{m['unit']}"
                                          if m["status"] == "BOUNDED" else "")]
    if m["applied_via"]:
        L.append(f"  observado  {m['observed_on']} · {m['observed_period'][0][:4]} · "
                 f"aplicada via {m['applied_via']}")
    if m["reasons"]:
        L.append(f"  motivos    {', '.join(m['reasons'])}")
    for u in m["unknowns"]:
        L.append(f"      · {u}")
    return "\n".join(L)
