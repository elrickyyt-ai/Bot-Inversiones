"""Universo congelado y cobertura de fuente -- auditoria de poblacion (2026-09-08).

El diagnostico de cohorte (D-31) dejo el problema en una linea:

    n_events = 52   pero   n_assets = 3   ->   independence_status = LOW

Acumular mas trimestres de los MISMOS tres activos no lo arregla: daria
n_events = 356 y n_assets = 3. El cuello de botella es transversal, no
temporal. Este modulo mide si existe una poblacion con la que arreglarlo.

Dos declaraciones, ninguna calculada:

    universo_v1.json              QUE activos, con su criterio y su fecha
                                  de congelacion. Escrito ANTES de medir.
    cobertura_universo_v1.json    QUE dio la fuente para cada uno.

Lo que este modulo NO hace, a proposito: no descarga nada, no escribe en
data/, no convierte trimestres en eventos y no rellena un activo no medido.
NOT_MEASURED no se estima.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_UNIVERSO = os.path.join(DIR, "universo_v1.json")
RUTA_COBERTURA = os.path.join(DIR, "cobertura_universo_v1.json")

NO_MEDIDO = "NOT_MEASURED"
TICKER_AUSENTE = "TICKER_AUSENTE_DEL_PROVEEDOR"

# Umbrales de D-31, repetidos aqui para que la condicion de avance sea
# comprobable sin importar el diagnostico de cohorte.
MIN_ACTIVOS_ALTO = 30
MIN_ACTIVOS_MEDIO = 10


def universo():
    with open(RUTA_UNIVERSO, encoding="utf-8") as fh:
        return json.load(fh)


def cobertura():
    with open(RUTA_COBERTURA, encoding="utf-8") as fh:
        return json.load(fh)


def simbolos():
    return [a["symbol"] for a in universo()["included_assets"]]


def muestra_declarada():
    return list(universo()["muestra_de_medicion"]["simbolos"])


def _trimestres_contiguos(desde, hasta):
    """Trimestres que habria entre dos fechas si la serie fuese contigua.

    Es la comprobacion de completitud: si el proveedor devuelve menos, hay
    hueco; si devuelve mas, hay duplicado o un trimestre fuera de rejilla.
    Se cuenta en trimestres y no en dias porque la rejilla del dato ES
    trimestral -- el mismo criterio que llevo a contar los horizontes en
    sesiones y no en dias naturales (D-30)."""
    a1, m1 = int(desde[:4]), int(desde[5:7])
    a2, m2 = int(hasta[:4]), int(hasta[5:7])
    return (a2 - a1) * 4 + (m2 - m1) // 3 + 1


def registros_medidos():
    return {r["symbol"]: r for r in cobertura()["medidos"]}


def resumen_cobertura():
    """Los agregados de la muestra medida. Nunca extrapola a los no medidos."""
    med = cobertura()["medidos"]
    con_datos = [r for r in med if r["quarters_available"] > 0]
    vacios = [r for r in med if r["quarters_available"] == 0]
    total_q = sum(r["quarters_available"] for r in con_datos)
    return {
        "medidos": len(med),
        "con_datos": len(con_datos),
        "vacios": len(vacios),
        "simbolos_vacios": [r["symbol"] for r in vacios],
        "trimestres_totales": total_q,
        "trimestres_por_activo": {r["symbol"]: r["quarters_available"] for r in con_datos},
        "sin_reportTime": sum(r["missing_reportTime"] for r in con_datos),
        "sin_estimatedEPS": sum(r["missing_estimatedEPS"] for r in con_datos),
        "sin_reportedEPS": sum(r["missing_reportedEPS"] for r in con_datos),
        "pre_market": sum(r["pre_market_count"] for r in con_datos),
        "post_market": sum(r["post_market_count"] for r in con_datos),
        "contiguos": [r["symbol"] for r in con_datos
                      if r["quarters_available"] == r["quarters_expected_contiguous"]],
        "no_contiguos": [r["symbol"] for r in con_datos
                         if r["quarters_available"] != r["quarters_expected_contiguous"]],
    }


def incoherencias():
    """Lo que no cuadra entre las dos declaraciones. Vacio = coherentes."""
    u, c = universo(), cobertura()
    en_universo = {a["symbol"] for a in u["included_assets"]}
    fallos = []

    for s in u["muestra_de_medicion"]["simbolos"]:
        if s not in en_universo:
            fallos.append(f"la muestra declara {s}, que no esta en el universo")

    for r in c["medidos"]:
        if r["symbol"] not in en_universo:
            fallos.append(f"se midio {r['symbol']}, que no esta en el universo")
        if r["quarters_available"] > 0:
            esperado = _trimestres_contiguos(r["oldest_reportedDate"], r["newest_reportedDate"])
            # Tolerancia de 1: reportedDate es la fecha de PUBLICACION, que
            # cae en el trimestre siguiente al fiscal y puede desplazar el
            # conteo un trimestre segun donde caiga en el calendario.
            if abs(esperado - r["quarters_expected_contiguous"]) > 1:
                fallos.append(
                    f"{r['symbol']}: quarters_expected_contiguous declarado "
                    f"{r['quarters_expected_contiguous']}, calculado {esperado}")

    cubiertos = ({r["symbol"] for r in c["medidos"]}
                 | {r["symbol"] for r in c["medidos_en_sesion_anterior"]}
                 | set(c["no_medidos"]["simbolos_declarados_sin_medir"])
                 | set(c["no_medidos"]["resto_del_universo_sin_medir"]))
    if cubiertos != en_universo:
        faltan = en_universo - cubiertos
        sobran = cubiertos - en_universo
        if faltan:
            fallos.append(f"activos del universo sin clasificar: {sorted(faltan)}")
        if sobran:
            fallos.append(f"clasificados y ajenos al universo: {sorted(sobran)}")
    return fallos


def condicion_de_avance(n_assets_con_datos=None):
    """La condicion del usuario para pasar a HistoricalReactionProfile v2.

    Deliberadamente NO es "si hay mas de N eventos, adelante": el criterio
    es transversal (activos) y de calidad, no de volumen."""
    r = resumen_cobertura()
    n = n_assets_con_datos if n_assets_con_datos is not None else r["con_datos"]
    con_datos = [x for x in cobertura()["medidos"] if x["quarters_available"] > 0]
    completitud = (1.0 if not r["trimestres_totales"]
                   else 1 - r["sin_reportTime"] / r["trimestres_totales"])
    profundidad_ok = all(x["quarters_available"] >= 40 for x in con_datos) if con_datos else False
    return {
        "n_assets_medidos_con_datos": n,
        "n_assets_requerido": MIN_ACTIVOS_ALTO,
        "n_assets_suficiente": n >= MIN_ACTIVOS_ALTO,
        "completitud_de_timestamp": round(completitud, 4),
        "timestamp_suficiente": completitud == 1.0,
        "profundidad_suficiente": profundidad_ok,
        "independencia_razonable": n >= MIN_ACTIVOS_MEDIO,
        # Una sola clase de evento construida (earnings_release). Las 6-8
        # que pide el roadmap no existen todavia.
        "event_class_coverage": 1,
        "event_class_requerido": 6,
        "avanzar_a_v2": n >= MIN_ACTIVOS_ALTO and completitud == 1.0 and profundidad_ok,
    }


if __name__ == "__main__":
    u, r = universo(), resumen_cobertura()
    print(f"=== {u['universe_id']} · as_of {u['as_of_date']} ===")
    print(f"  activos incluidos     {len(u['included_assets'])}")
    print(f"  activos excluidos     {len(u['excluded_assets'])}")
    sectores = {}
    for a in u["included_assets"]:
        sectores[a["sector"]] = sectores.get(a["sector"], 0) + 1
    print(f"  sectores              {len(sectores)}  {sectores}")

    print("\n=== COBERTURA DE LA FUENTE (muestra declarada) ===")
    print(f"  medidos               {r['medidos']} de {len(u['included_assets'])}")
    print(f"  con datos             {r['con_datos']}")
    print(f"  vacios                {r['vacios']}  {r['simbolos_vacios']}")
    print(f"  trimestres totales    {r['trimestres_totales']}")
    print(f"  sin reportTime        {r['sin_reportTime']}")
    print(f"  sin estimatedEPS      {r['sin_estimatedEPS']}")
    print(f"  pre / post market     {r['pre_market']} / {r['post_market']}")
    print(f"  series contiguas      {len(r['contiguos'])}  {r['contiguos']}")

    print("\n=== INCOHERENCIAS ENTRE DECLARACIONES ===")
    fallos = incoherencias()
    print("  ninguna" if not fallos else "\n".join(f"  {x}" for x in fallos))

    print("\n=== CONDICION DE AVANCE A v2 ===")
    for k, v in condicion_de_avance().items():
        print(f"  {k:32} {v}")
