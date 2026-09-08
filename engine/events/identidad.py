"""Identidad historica de instrumento -- auditoria (2026-09-08).

D-36 dejo el hueco senalado: entre un ticker historico y un CIK no hay
puente autoritativo. Este modulo no lo cierra -- lo MODELA, que es lo que
faltaba, porque el problema no es una tabla de tickers sino que las
acciones corporativas TRANSFORMAN el instrumento.

    A -> A       split, cambio de ticker, holdco  (exposicion intacta)
    A -> B       fusion                            (exposicion combinada)
    A -> B + C   escision                          (exposicion repartida)

El principio que ordena el modulo:

    Un proveedor que no conoce un instrumento no puede convertirlo en
    inexistente; y un ticker sucesor no puede convertirse silenciosamente
    en el instrumento predecesor.

Lo que este modulo NO hace: no descarga, no escribe en data/, no resuelve
tickers y no construye ningun master. Declara el modelo y hace ejecutable
la regla de elegibilidad.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
RUTA = os.path.join(DIR, "identidad_instrumento.json")

# --- Capas de identidad. El ticker NO es una de las estables ------------
CAPAS = ("LEGAL_ENTITY", "SEC_CIK", "MARKET_INSTRUMENT", "TICKER")

# --- Continuidad: tres preguntas distintas, no una ----------------------
PRICE_LEVEL = "PRICE_LEVEL_CONTINUITY"
RETURN = "RETURN_CONTINUITY"
ECONOMIC = "ECONOMIC_INSTRUMENT_CONTINUITY"
TIPOS_CONTINUIDAD = (PRICE_LEVEL, RETURN, ECONOMIC)

CONTINUOUS = "CONTINUOUS"
ADJUSTED = "CORPORATE_ACTION_ADJUSTED"
SUCCESSOR = "SUCCESSOR_MAPPING"
AMBIGUOUS = "AMBIGUOUS"
DISCONTINUOUS = "DISCONTINUOUS"
CLASES_CONTINUIDAD = (CONTINUOUS, ADJUSTED, SUCCESSOR, AMBIGUOUS, DISCONTINUOUS)

# --- Transformaciones -------------------------------------------------
# La particion que importa: cuales preservan la exposicion economica.
AJUSTABLES = ("SPLIT", "TICKER_CHANGE", "HOLDCO_REORG")
CAMBIAN_INSTRUMENTO = ("MERGER", "SPINOFF")
ROMPEN_IDENTIDAD = ("DELISTING", "TICKER_REUSE")
TRANSFORMACIONES = AJUSTABLES + CAMBIAN_INSTRUMENTO + ROMPEN_IDENTIDAD

FUERA_DE_VENTANA = "FUERA_DE_VENTANA"
AJUSTABLE_EN_VENTANA = "AJUSTABLE_EN_VENTANA"
CAMBIA_INSTRUMENTO_EN_VENTANA = "CAMBIA_INSTRUMENTO_EN_VENTANA"
CASO_AMBIGUO = "CASO_AMBIGUO"


def declaracion():
    with open(RUTA, encoding="utf-8") as fh:
        return json.load(fh)


def casos():
    return {c["caso"]: c for c in declaracion()["casos"]}


def mapping_status():
    return declaracion()["HISTORICAL_INSTRUMENT_MAPPING"]


def continuidad_de(transformacion):
    """Que tipos de continuidad sobreviven a cada transformacion.

    Medido, no supuesto: tras una escision el cociente entre dos precios
    ajustados es aritmeticamente correcto -- RETURN sobrevive -- y compara
    dos empresas distintas -- ECONOMIC no."""
    if transformacion in AJUSTABLES:
        return {PRICE_LEVEL: False, RETURN: True, ECONOMIC: True}
    if transformacion in CAMBIAN_INSTRUMENTO:
        return {PRICE_LEVEL: False, RETURN: True, ECONOMIC: False}
    return {PRICE_LEVEL: False, RETURN: False, ECONOMIC: False}


def clasificar_accion(transformacion, dentro_de_ventana):
    """Los cuatro casos que pidio la regla de elegibilidad."""
    if not dentro_de_ventana:
        return FUERA_DE_VENTANA
    if transformacion in AJUSTABLES:
        return AJUSTABLE_EN_VENTANA
    if transformacion in CAMBIAN_INSTRUMENTO:
        return CAMBIA_INSTRUMENTO_EN_VENTANA
    return CASO_AMBIGUO


def elegibilidad_event_study(acciones_en_ventana):
    """¿Puede usarse una observacion con estas acciones en sus ventanas?

    `acciones_en_ventana`: [(transformacion, ventana)] con ventana en
    {"estimation", "reaction", None}. None = fuera de ambas.

    La regla NO es "excluir si hay accion corporativa": un split dentro de
    la ventana no invalida nada, porque el ajuste multiplicativo se cancela
    en el cociente. Lo que invalida es que CAMBIE EL INSTRUMENTO."""
    clasificadas = [(t, v, clasificar_accion(t, v is not None))
                    for t, v in acciones_en_ventana]
    bloqueantes = [c for c in clasificadas
                   if c[2] in (CAMBIA_INSTRUMENTO_EN_VENTANA, CASO_AMBIGUO)]
    if not clasificadas:
        continuidad = CONTINUOUS
    elif bloqueantes:
        continuidad = AMBIGUOUS
    elif any(c[2] == AJUSTABLE_EN_VENTANA for c in clasificadas):
        continuidad = ADJUSTED
    else:
        continuidad = CONTINUOUS
    return {
        "eligible": not bloqueantes,
        "continuity_class": continuidad,
        "acciones": [{"transformacion": t, "ventana": v, "clasificacion": c}
                     for t, v, c in clasificadas],
        "motivo": None if not bloqueantes else
                  "cambia el instrumento economico dentro de la ventana: "
                  + ", ".join(f"{t} en {v}" for t, v, _ in bloqueantes),
    }


def matriz_casos():
    """Matriz de cobertura de los casos minimos. Lo no medido, NOT_MEASURED."""
    m = declaracion()["matriz_casos"]
    cols = m["_columnas"]
    return cols, {c: {k: m["celdas"].get(c, {}).get(k, "NOT_MEASURED") for k in cols}
                  for c in casos()}


AMBIGUO_SIN_INTERVALO = "AMBIGUOUS: ningun intervalo declarado cubre esa fecha"
AMBIGUO_VARIOS = "AMBIGUOUS: mas de un intervalo cubre esa fecha"


def resolver_identidad(ticker, fecha):
    """Resuelve un ticker A UNA FECHA. Sin fecha no hay identidad.

    Devuelve (cik, entidad) o (None, motivo). NUNCA devuelve el candidato
    mas probable: un falso positivo de identidad es mas peligroso que un
    dato ausente -- es la leccion de MOB, cuyo ticker devuelve hoy una
    empresa que no existia cuando Mobil cotizaba."""
    intervalos = declaracion()["resolucion_temporal"]["intervalos"].get(ticker)
    if not intervalos:
        return None, AMBIGUO_SIN_INTERVALO
    cubren = [i for i in intervalos
              if (i["desde"] is None or i["desde"] <= fecha)
              and (i["hasta"] is None or fecha <= i["hasta"])]
    if not cubren:
        return None, AMBIGUO_SIN_INTERVALO
    if len(cubren) > 1:
        return None, AMBIGUO_VARIOS
    return cubren[0]["cik"], cubren[0]["entidad"]


def incoherencias():
    d = declaracion()
    fallos = []
    if set(d["capas_de_identidad"]) != set(CAPAS):
        fallos.append("las capas declaradas no coinciden con las del modulo")
    if set(d["transformaciones"]) != set(TRANSFORMACIONES):
        fallos.append("las transformaciones declaradas no coinciden con las del modulo")
    if set(d["clasificacion_de_continuidad"]) != set(CLASES_CONTINUIDAD):
        fallos.append("las clases de continuidad no coinciden")
    for nombre, t in d["transformaciones"].items():
        basta = t["ajuste_multiplicativo_basta"]
        if (nombre in AJUSTABLES) != bool(basta):
            fallos.append(f"{nombre}: 'ajuste_multiplicativo_basta' contradice la particion del modulo")
    for c in d["casos"]:
        if c["continuidad"].split()[0] not in CLASES_CONTINUIDAD:
            fallos.append(f"{c['caso']}: clase de continuidad desconocida")
        for t in c["transformaciones"]:
            if t["tipo"] not in TRANSFORMACIONES:
                fallos.append(f"{c['caso']}: transformacion desconocida {t['tipo']}")
    return fallos


if __name__ == "__main__":
    d = declaracion()
    print("=== PRINCIPIO ===\n ", d["principio"])
    print("\n=== CAPAS DE IDENTIDAD ===")
    for k in CAPAS:
        print("  %-18s %s" % (k, d["capas_de_identidad"][k]["que_es"]))
    print("\n=== TRANSFORMACION x CONTINUIDAD ===")
    print("  %-15s %-12s %-8s %-8s %s" % ("transformacion", "forma", "PRICE", "RETURN", "ECONOMIC"))
    for t in TRANSFORMACIONES:
        c = continuidad_de(t)
        print("  %-15s %-12s %-8s %-8s %s" % (t, d["transformaciones"][t]["forma"],
              c[PRICE_LEVEL], c[RETURN], c[ECONOMIC]))
    print("\n=== CASOS ===")
    for c in d["casos"]:
        tipos = sorted({t["tipo"] for t in c["transformaciones"]})
        print("  %-5s %-30s %s" % (c["caso"], ",".join(tipos), c["continuidad"][:52]))
    print("\n=== ELEGIBILIDAD ===")
    for etiqueta, acc in (("sin acciones", []),
                          ("split en estimacion", [("SPLIT", "estimation")]),
                          ("escision en reaccion", [("SPINOFF", "reaction")]),
                          ("fusion fuera de ventana", [("MERGER", None)]),
                          ("reutilizacion de ticker", [("TICKER_REUSE", "estimation")])):
        r = elegibilidad_event_study(acc)
        print("  %-26s eligible=%-6s %s" % (etiqueta, r["eligible"], r["continuity_class"]))
    cols, mat = matriz_casos()
    print("\n=== MATRIZ DE COBERTURA (casos minimos) ===")
    print("  %-5s " % "asset" + " ".join("%-13s" % c[:13] for c in cols))
    for c in ("DWDP", "UTX", "IBM", "NVDA", "XOM"):
        print("  %-5s " % c + " ".join("%-13s" % mat[c][k] for k in cols))

    print("\nHISTORICAL_INSTRUMENT_MAPPING:", mapping_status())
    print("\n=== RESOLUCION TEMPORAL ===")
    for tk, f in (("XOM", "2019-04-26"), ("XOM", "2026-08-15"), ("XON", "1998-01-01"),
                  ("MOB", "1995-06-01"), ("MOB", "2024-01-05"), ("IBM", "2020-01-01")):
        cik, ent = resolver_identidad(tk, f)
        print("  %-4s @ %s -> %s" % (tk, f, (cik or "") + " " + str(ent)))

    print("\n=== INCOHERENCIAS ===")
    f = incoherencias()
    print("  ninguna" if not f else "\n".join("  " + x for x in f))
