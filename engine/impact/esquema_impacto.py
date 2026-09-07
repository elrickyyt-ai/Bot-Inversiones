"""EconomicImpact -- P6 v1 (2026-09-07).

    Un EconomicImpact es una AFIRMACION CONDICIONADA:

        dado el evento E, el mecanismo M y la evidencia disponible,
        la variable V de la entidad X va en direccion D, en el
        horizonte H, con magnitud <la que se pueda sostener>.

No dice "NVIDIA tendra +X%". Dice bajo que condiciones, con que
mecanismo y con que evidencia. Un impacto con `magnitude UNKNOWN` no es
un fallo: es el resultado correcto de la informacion disponible.

LAS CUATRO PIEZAS SON INDEPENDIENTES
------------------------------------
direccion, magnitud, materialidad y horizonte pueden estar en estados
DISTINTOS a la vez, y por eso son cuatro campos con su propio estado y
no un unico enum. Hoy, sobre la cadena real:

    economic_direction  POSITIVE / UNKNOWN   <- heredada de P5B
    magnitude           UNKNOWN
    materiality         UNKNOWN
    horizon             UNKNOWN

y eso sigue siendo informacion valida.

LO QUE ESTA CAPA NO EMITE, NUNCA
--------------------------------
probabilidad · score · precio objetivo · compra/venta · confianza.
El validador rechaza cualquier campo con esos nombres, no como estilo
sino porque es la unica forma de que no reaparezcan por la puerta de
atras cuando alguien tenga prisa.

Y NO ES IMPACTO DE MERCADO
--------------------------
    P6  que cambia ECONOMICAMENTE          demanda, coste, margen
    P7  que deberia pasar en el PRECIO     valoracion, expectativa

P6 no importa precio. `precio` existe en el contrato y es la metrica
mejor cubierta del sistema; usarla aqui seria el atajo mas facil y
convertiria el motor economico en un motor de mercado disfrazado.
"""
import os
import sys

_R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _s in ("causal", "requirements"):
    _p = os.path.join(_R, "engine", _s)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mecanismos as M  # noqa: E402

RULE_VERSION = "p6/v1"

# --- Estado de cada pieza ----------------------------------------------------
#
# Tres valores, y la distincion entre los dos ultimos es el corazon de la
# capa: "no puedo" y "no se" no son lo mismo. CAPACITY_CONSTRAINT nunca
# dara magnitud por como es el mecanismo (NOT_APPLICABLE); CUSTOMER_DEMAND
# podria darla y hoy no puede por falta de datos (UNKNOWN). Colapsarlos
# perderia justo la informacion que dice donde merece la pena invertir.
ESTADOS_PIEZA = {
    "KNOWN":          "valor puntual sostenido por evidencia y parametros declarados",
    "BOUNDED":        "cota estricta procedente de una observacion real (P6.1). "
                      "No es un KNOWN peor: es una afirmacion distinta -- '<=19%' y "
                      "'19%' no dicen lo mismo",
    "UNKNOWN":        "podria conocerse, y hoy no se conoce",
    "NOT_APPLICABLE": "el mecanismo no produce esta pieza, por como es",
}

# --- Capacidad de magnitud por mecanismo -------------------------------------
#
# NOTA DE VOCABULARIO. La propuesta original era
# SUPPORTED / NOT_SUPPORTED / CONDITIONALLY_SUPPORTED. Medido: SUPPORTED
# ya existe en P5B (`support`) y significa otra cosa -- alli es "esta
# afirmacion concreta tiene respaldo probatorio completo", aqui seria
# "esta CLASE de mecanismo puede en principio dar un numero". Son una
# propiedad de una instancia y una propiedad de un tipo. Bajo la regla
# que el proyecto acaba de reformular -- un token se comparte si y solo
# si significa lo mismo -- no pueden compartirlo, asi que la familia pasa
# a QUANTIFIABLE, que ademas dice exactamente lo que es. Los tres tokens
# estaban libres.
CAPACIDADES = {
    "QUANTIFIABLE":               "el mecanismo puede producir magnitud con lo que hay",
    "CONDITIONALLY_QUANTIFIABLE": "podria, si existieran linea base, materialidad y coeficiente",
    "NOT_QUANTIFIABLE":           "no produce magnitud por su propia naturaleza, no por falta de datos",
}

# --- Origen del coeficiente de transmision -----------------------------------
#
# Vocabulario declarado ENTERO a proposito, aunque v1 solo pueda alcanzar
# dos de sus cuatro valores: escribirlo completo es lo que permite que el
# validador RECHACE ESTIMATED de forma explicita en vez de que ese caso
# simplemente no exista todavia y aparezca un dia sin que nadie lo note.
#
# La decision, literal: "P6 v1 no puede emitir un coeficiente de
# transmision que no proceda de una relacion declarada y verificable".
# ESTIMATED (regresion sobre el historico propio) pertenece a una futura
# capa de Model/Calibration, NO a P6, y lo que salga de ella no sera
# Evidence ni Knowledge: sera salida de un modelo, con su propia
# ontologia (ventana de entrenamiento, validacion fuera de muestra,
# estabilidad, sensibilidad al regimen...). Nada de eso existe.
ORIGENES_COEFICIENTE = {
    "OBSERVED":  "medido directamente en una fuente externa",
    "DECLARED":  "declarado a mano con su fuente y su justificacion",
    "ESTIMATED": "estimado estadisticamente — PROHIBIDO EN v1, capa de modelo futura",
    "UNKNOWN":   "no hay coeficiente",
}
ORIGENES_PERMITIDOS_V1 = {"OBSERVED", "DECLARED", "UNKNOWN"}
ORIGEN_PROHIBIDO_V1 = "ESTIMATED"

# --- Motivos -----------------------------------------------------------------
MOTIVOS = {
    "REQUIRED_EVIDENCE_MISSING":   "falta una variable que el mecanismo necesita observar",
    "EVIDENCE_ONLY_BY_PROXY":      "la variable solo se resuelve con un proxy declarado",
    "MATERIALITY_UNKNOWN":         "no se sabe que fraccion de la entidad toca la variable",
    "MATERIALITY_ONLY_BOUNDED":    "la materialidad es una cota, no un valor: la magnitud "
                                   "puede acotarse pero nunca puntualizarse",
    "NO_TRANSMISSION_COEFFICIENT": "no hay coeficiente declarado y v1 no lo estima",
    "NO_BASELINE":                 "no hay linea base contra la que medir el cambio",
    "MECHANISM_CANNOT_QUANTIFY":   "el mecanismo no produce magnitud por su naturaleza",
    "NO_ECONOMIC_MECHANISM":       "la arista no transmite nada economicamente",
}

# `fitness` se DERIVA de P5D, no se declara aqui. MEASURES y PROXY se
# comparten con catalogo.py porque significan exactamente lo mismo: es el
# caso legitimo de token compartido.
FITNESS = {
    "MEASURES":     "resuelto por una medicion directa de la variable",
    "PROXY":        "resuelto solo por un proxy declarado",
    "INSUFFICIENT": "no resuelto: el dato no existe o no aplica",
    "UNKNOWN":      "no habia con que resolverlo",
}

CAMPOS = {
    "impact_id", "as_of", "rule_version",
    "event_id", "path_id", "relationship_id", "mechanism", "magnitude_capability",
    "entity_id", "affected_variable", "economic_direction",
    "magnitude", "magnitude_basis", "materiality", "horizon",
    "fitness", "evidence_ids", "support", "reasons", "unknowns",
}
# `upper_bound` acompana a BOUNDED igual que en la materialidad: las dos
# piezas comparten forma porque comparten vocabulario de estados. v1 no
# emite magnitud BOUNDED -- seguiria faltandole coeficiente y linea base --
# pero el contrato queda cerrado para cuando los haya.
CAMPOS_MAGNITUD = {"state", "value", "unit", "baseline", "upper_bound"}
CAMPOS_BASE = {"coefficient_origin", "coefficient_ref", "inputs"}
CAMPOS_MATERIALIDAD = {"state", "value", "unit", "source_id", "upper_bound"}
# Horizonte en DIAS, no en categorias. Medido antes de decidir: el
# proyecto no tiene ningun vocabulario categorico de horizonte, y si
# tiene una convencion en dias (ledger.py, horizonte_evaluacion_dias=90).
# Inventar IMMEDIATE/SHORT_TERM/... habria sido crear un vocabulario
# nuevo para algo que ya se expresa de otra forma.
CAMPOS_HORIZONTE = {"state", "dias_min", "dias_max"}

# Nombres que esta capa no puede tener. No es una lista de estilo: es la
# unica manera de que "solo un campito de confianza" no entre nunca.
CAMPOS_PROHIBIDOS = {
    "probability", "probabilidad", "score", "puntuacion", "price_target",
    "precio_objetivo", "confidence", "confidence_pct", "confianza",
    "recommendation", "recomendacion", "signal", "senal", "buy", "sell",
    "expected_return", "rentabilidad_esperada",
}


class ImpactError(Exception):
    pass


def _sub(e, r, campo, esperados):
    v = r.get(campo)
    if not isinstance(v, dict):
        e.append(f"{campo} debe ser una estructura, no un valor suelto")
        return None
    sobra = set(v) - esperados
    if sobra:
        e.append(f"{campo}: campos no reconocidos {sorted(sobra)}")
    return v


def validar(r):
    """Devuelve la lista de incidencias. Vacia = el impacto es valido."""
    e = []
    sobra = set(r) - CAMPOS
    if sobra:
        e.append(f"campos no reconocidos {sorted(sobra)}")
    faltan = CAMPOS - set(r)
    if faltan:
        e.append(f"faltan campos {sorted(faltan)}")
        return e

    prohibidos = {c for c in r if c.lower() in CAMPOS_PROHIBIDOS}
    if prohibidos:
        e.append(f"campos prohibidos en P6 {sorted(prohibidos)}: "
                 f"probabilidad, score, precio y confianza son otra capa")

    if r["mechanism"] not in M.MECANISMOS and r["mechanism"] != M.NO_MECHANISM:
        e.append(f"mechanism fuera del vocabulario: {r['mechanism']!r}")
    if r["magnitude_capability"] not in CAPACIDADES:
        e.append(f"magnitude_capability fuera del vocabulario: {r['magnitude_capability']!r}")
    if r["economic_direction"] not in M.DIRECCIONES:
        e.append(f"economic_direction fuera del vocabulario: {r['economic_direction']!r}")
    if r["affected_variable"] not in M.VARIABLES_AFECTADAS:
        e.append(f"affected_variable fuera del vocabulario: {r['affected_variable']!r}")
    if r["support"] not in M.SOPORTES:
        e.append(f"support fuera del vocabulario: {r['support']!r}")
    if r["fitness"] not in FITNESS:
        e.append(f"fitness fuera del vocabulario: {r['fitness']!r}")
    for m in r["reasons"]:
        if m not in MOTIVOS:
            e.append(f"motivo fuera del vocabulario: {m!r}")

    mag = _sub(e, r, "magnitude", CAMPOS_MAGNITUD)
    base = _sub(e, r, "magnitude_basis", CAMPOS_BASE)
    mat = _sub(e, r, "materiality", CAMPOS_MATERIALIDAD)
    hor = _sub(e, r, "horizon", CAMPOS_HORIZONTE)
    if not all((mag, base, mat, hor)):
        return e

    for nombre, pieza in (("magnitude", mag), ("materiality", mat), ("horizon", hor)):
        if pieza.get("state") not in ESTADOS_PIEZA:
            e.append(f"{nombre}.state fuera del vocabulario: {pieza.get('state')!r}")

    origen = base.get("coefficient_origin")
    if origen not in ORIGENES_COEFICIENTE:
        e.append(f"coefficient_origin fuera del vocabulario: {origen!r}")
    # LA decision de esta fase, hecha ejecutable.
    if origen == ORIGEN_PROHIBIDO_V1:
        e.append(f"coefficient_origin=ESTIMATED no puede existir en {RULE_VERSION}: "
                 f"un coeficiente estimado estadisticamente no es Evidence ni "
                 f"Knowledge, es salida de un modelo, y esa capa no existe")
    if origen in ("OBSERVED", "DECLARED") and not base.get("coefficient_ref"):
        e.append("un coeficiente OBSERVED o DECLARED sin referencia no es verificable")

    # --- Reglas de magnitud ---
    if mag["state"] == "BOUNDED":
        # Una cota en la magnitud exige lo mismo que un punto, salvo el punto.
        if mag.get("upper_bound") is None:
            e.append("magnitude BOUNDED sin upper_bound")
        if mag.get("value") is not None:
            e.append("magnitude BOUNDED con value: si se conociera el punto no seria cota")
        for c in ("unit", "baseline"):
            if not mag.get(c):
                e.append(f"magnitude BOUNDED sin {c}")
        if mat["state"] not in ("KNOWN", "BOUNDED"):
            e.append("magnitude BOUNDED con materiality sin resolver: una cota tambien "
                     "necesita saber que parte de la entidad toca")
    elif mag.get("upper_bound") is not None:
        e.append(f"magnitude {mag['state']} con upper_bound: solo BOUNDED lleva cota")

    if mag["state"] == "KNOWN":
        # (valor, unidad, base): las tres o ninguna. P4 ya exigia las dos
        # primeras; la tercera es de aqui -- un 10% no significa nada sin
        # decir 10% respecto a que.
        for c in ("value", "unit", "baseline"):
            if mag.get(c) in (None, ""):
                e.append(f"magnitude KNOWN sin {c}")
        # Un cero MEDIDO lleva su evidencia. Un cero por ausencia no se
        # puede escribir: es la forma mas silenciosa de inventar un dato.
        if mag.get("value") == 0 and not r["evidence_ids"]:
            e.append("magnitude=0 sin evidence_ids — un cero medido lleva su evidencia; "
                     "un cero por ausencia es informacion inventada")
        # Regla general, no solo para NVDA/TSMC: causalidad != materialidad.
        if mat["state"] == "BOUNDED":
            e.append("magnitude KNOWN con materiality BOUNDED — una cota no puntualiza: "
                     "el maximo alcanzable es una magnitud BOUNDED")
        elif mat["state"] != "KNOWN":
            e.append("magnitude KNOWN con materiality no KNOWN — no se puede valorar el "
                     "efecto sobre una entidad sin saber que parte de su economia toca")
        if origen not in ("OBSERVED", "DECLARED"):
            e.append("magnitude KNOWN sin coeficiente de transmision de origen declarado")
        # Nunca promover lo cualitativo a cuantitativo.
        if r["fitness"] in ("PROXY", "INSUFFICIENT", "UNKNOWN"):
            e.append(f"magnitude KNOWN con fitness={r['fitness']} — P6 puede degradar una "
                     f"afirmacion cuantitativa a cualitativa, nunca al reves")
        if r["magnitude_capability"] == "NOT_QUANTIFIABLE":
            e.append("magnitude KNOWN en un mecanismo NOT_QUANTIFIABLE")
    elif mag["state"] != "BOUNDED":
        if mag.get("value") is not None:
            e.append(f"magnitude {mag['state']} con un value de {mag['value']!r}: "
                     f"si no se conoce, el valor es null y esta presente")
        if not r["reasons"]:
            e.append("magnitude sin resolver y sin motivo declarado")

    # "No puedo" y "no se" no se confunden en ninguna direccion.
    if r["magnitude_capability"] == "NOT_QUANTIFIABLE" and mag["state"] != "NOT_APPLICABLE":
        e.append("un mecanismo NOT_QUANTIFIABLE tiene magnitude NOT_APPLICABLE, "
                 "nunca UNKNOWN: no es que falte el dato, es que no aplica")
    if r["magnitude_capability"] != "NOT_QUANTIFIABLE" and mag["state"] == "NOT_APPLICABLE":
        e.append("magnitude NOT_APPLICABLE en un mecanismo que si podria cuantificar")

    if hor["state"] != "KNOWN" and (hor.get("dias_min") is not None
                                    or hor.get("dias_max") is not None):
        e.append("horizon sin resolver con dias: o se conoce o los dias son null")
    return e
