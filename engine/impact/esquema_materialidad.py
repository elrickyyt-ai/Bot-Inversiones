"""Materiality -- P6.1 (2026-09-07).

    Evidence (de entidad)  +  Knowledge (la relacion)  ->  Materiality (derivada)

La materialidad NO se almacena. Se deriva, cada vez, de una observacion
fechada y de la relacion que permite aplicarla. Por eso no hay aqui
ninguna funcion de escritura y no existe ningun fichero de
materialidades: si se guardara, en dos meses nadie sabria si el 19% es
lo que dijo el 20-F o lo que dedujo el sistema.

LA REGLA QUE ORDENA TODO
------------------------
    La materialidad usada por una evaluacion causal debe estar RESUELTA
    respecto al sujeto y, cuando corresponda, a su contraparte; la
    EVIDENCIA que la sustenta puede ser de entidad, de relacion, o una
    cota derivada sobre un conjunto de contrapartes.

De ahi que la observacion sea de UNA entidad (TSMC) y la materialidad de
un PAR (TSMC <- NVIDIA). La contraparte aparece en la derivacion, no en
el dato.

NOTA DE VOCABULARIO: `POINT` no se introduce
--------------------------------------------
El diseno pedia `POINT` / `BOUNDED` / `UNKNOWN` / `NOT_APPLICABLE`. Pero
P6 ya tiene `KNOWN` en ESTADOS_PIEZA con exactamente el significado de
`POINT` -- "hay un valor puntual sostenido". Anadir `POINT` al lado de
`KNOWN` serian dos nombres para una idea, que es el error espejo que el
proyecto acaba de codificar como invariante. Asi que magnitud y
materialidad comparten el MISMO vocabulario de cuatro estados, y
`BOUNDED` se anade a los dos: una cota es igual de expresable en las dos
piezas, y de hecho una materialidad acotada nunca podra dar una magnitud
puntual.
"""
import os
import sys

_R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _s in ("causal", "impact"):
    _p = os.path.join(_R, "engine", _s)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import esquema_impacto as EI  # noqa: E402

RULE_VERSION = "p61/v1"

# Compartido con la magnitud, no redeclarado. Ver la nota del docstring.
ESTADOS = EI.ESTADOS_PIEZA

ALCANCES = {
    "ENTITY":           "observada sobre la entidad, sin contraparte",
    "RELATIONSHIP":     "observada sobre el par explicito -- ninguna fuente lo publica hoy",
    "POPULATION_BOUND": "cota sobre un conjunto de contrapartes, aplicable a cada una",
}

# Cuatro, uno por mecanismo que la pide. `DEMAND_SHARE` no entra porque
# ningun mecanismo la necesita. `CUSTOMER_REVENUE_SHARE` tampoco: describe
# LA MISMA magnitud que SUPPLIER_REVENUE_EXPOSURE vista desde el otro lado
# de la mesa, y tener las dos serian dos nombres para una idea. Se
# conserva la que NOMBRA AL SUJETO, que es lo que hay que resolver.
BASES = {
    "SUPPLIER_REVENUE_EXPOSURE": {
        "sujeto": "el proveedor",
        "base": "sus ingresos totales",
        "mide": "que fraccion de los ingresos del sujeto viene de la contraparte",
    },
    "COST_SHARE": {
        "sujeto": "quien usa el insumo",
        "base": "su base de coste",
        "mide": "que peso tiene el insumo en el coste del sujeto",
    },
    "VOLUME_SHARE": {
        "sujeto": "el cliente",
        "base": "su suministro total",
        "mide": "que fraccion del suministro del sujeto viene de la contraparte",
    },
    "CAPACITY_SHARE": {
        "sujeto": "el dueno del recurso",
        "base": "su capacidad total",
        "mide": "cuanta capacidad del sujeto esta comprometida con la contraparte",
    },
}

# Motivos de resolucion. La distincion que pediste conservar --
# NO_SUPPORTING_EVIDENCE frente a EVIDENCE_EXISTS_BUT_NOT_APPLICABLE --
# no crea dos estados publicos: crea dos motivos, para que una evidencia
# valida pero inaplicable no acabe indistinguible de un hueco de datos.
MOTIVOS = {
    "DERIVED_FROM_POPULATION_BOUND": "cota poblacional aplicada a esta contraparte",
    "NO_SUPPORTING_EVIDENCE":        "no hay ninguna observacion de esta base sobre el sujeto",
    "EVIDENCE_EXISTS_BUT_NOT_APPLICABLE": "la observacion existe y es valida, pero no "
                                          "alcanza a esta contraparte o a este periodo",
    "NO_RELATIONSHIP":               "no hay relacion que meta a la contraparte en la poblacion",
    "RELATIONSHIP_NOT_VALID_IN_PERIOD": "la relacion no estaba vigente cuando se observo la cota",
    "TRIVIAL_BOUND_DISCARDED":       "la cota no era estricta: un tope aritmetico no es una cota",
    "BASIS_NOT_REQUIRED":            "el mecanismo no necesita materialidad",
}

CAMPOS = {
    "materiality_id", "as_of", "rule_version", "basis", "scope", "status",
    "subject", "counterparty", "value", "upper_bound", "unit",
    "observed_on", "observed_period", "applied_via", "evidence_ids",
    "reasons", "unknowns",
}

# Una cota que no es estricta no es informacion: es aritmetica. "<=100%"
# es cierto siempre y PARECE un dato, que es lo que lo hace peor que un
# UNKNOWN honesto.
COTA_TRIVIAL_PCT = 100.0


class MaterialityError(Exception):
    pass


def validar(m):
    """Devuelve la lista de incidencias. Vacia = la materialidad es valida."""
    e = []
    sobra = set(m) - CAMPOS
    if sobra:
        e.append(f"campos no reconocidos {sorted(sobra)}")
    faltan = CAMPOS - set(m)
    if faltan:
        e.append(f"faltan campos {sorted(faltan)}")
        return e

    if m["basis"] not in BASES:
        e.append(f"basis fuera del vocabulario: {m['basis']!r}")
    if m["scope"] not in ALCANCES:
        e.append(f"scope fuera del vocabulario: {m['scope']!r}")
    if m["status"] not in ESTADOS:
        e.append(f"status fuera del vocabulario: {m['status']!r}")
    for r in m["reasons"]:
        if r not in MOTIVOS:
            e.append(f"motivo fuera del vocabulario: {r!r}")
    if not m["subject"]:
        e.append("sin sujeto: una materialidad sin sujeto no esta resuelta")

    if m["status"] == "KNOWN":
        if m["value"] is None:
            e.append("KNOWN sin value")
        if m["upper_bound"] is not None:
            e.append("KNOWN con upper_bound: un valor puntual no es una cota")
    elif m["status"] == "BOUNDED":
        if m["upper_bound"] is None:
            e.append("BOUNDED sin upper_bound")
        elif m["upper_bound"] >= COTA_TRIVIAL_PCT:
            e.append(f"cota no estricta ({m['upper_bound']}): un tope aritmetico no es una "
                     f"cota, y parece informacion sin serlo")
        if m["value"] is not None:
            e.append("BOUNDED con value: si se conociera el punto no seria una cota")
        # Una cota sin la observacion de la que sale, y sin la relacion que
        # permite aplicarla, no es derivable ni auditable.
        if not m["evidence_ids"]:
            e.append("BOUNDED sin evidence_ids: una cota sin observacion es una suposicion")
        if not m["applied_via"]:
            e.append("BOUNDED sin applied_via: falta la relacion que la hace aplicable")
        if not m["observed_on"] or not m["observed_period"]:
            e.append("BOUNDED sin decir sobre que entidad y periodo se observo")
    else:
        for c in ("value", "upper_bound"):
            if m[c] is not None:
                e.append(f"{m['status']} con {c} a {m[c]!r}: si no se resuelve, va a null")
        if not m["reasons"]:
            e.append("sin resolver y sin motivo declarado")

    if m["status"] in ("KNOWN", "BOUNDED") and not m["unit"]:
        e.append("una materialidad resuelta sin unidad no significa nada")
    if m["counterparty"] and m["status"] == "BOUNDED" and m["scope"] != "POPULATION_BOUND":
        e.append("una cota sobre una contraparte concreta solo puede venir de una "
                 "cota poblacional mientras ninguna fuente publique el par")
    return e
