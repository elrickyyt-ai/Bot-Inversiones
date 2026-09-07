"""HistoricalReactionProfile v1 -- DESCRIPTIVO, no predictivo.

Responde una pregunta y solo una:

    ¿Como ha reaccionado historicamente el mercado ante eventos
    comparables, con que distribucion y cuanta evidencia independiente
    tenemos?

Lo que NO hace, a proposito: no produce señales, ni BUY/SELL, ni pesos,
ni shrinkage, ni reaction_gap, ni confianza predictiva. Y no afirma que
una clase de evento "prediga" rentabilidad -- describe lo que paso.

LA PROPIEDAD QUE ORDENA TODO EL MODULO
--------------------------------------
Un perfil NUNCA desaparece por falta de datos: devuelve el motivo por el
que no se puede construir. Es el mismo principio que ya sostienen P6.1
(materialidad), temporal.py (available_at) y D-21 (benchmark), aqui
llevado a su conclusion: el sistema no intenta producir una conclusion
cuando la evidencia no lo permite; produce explicitamente por que no.

ALCANCE DE v1 (decision del usuario, 2026-09-07)
------------------------------------------------
Una sola familia homogenea: renta variable estadounidense, eventos
corporativos, benchmark S&P 500, datos de cierre. Macro y cripto quedan
para versiones posteriores, con estructura distinta -- probar tres
regimenes metodologicos a la vez contaminaria la primera implementacion.
"""
import datetime
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import estudio_resultados as er  # noqa: E402

METHODOLOGY_VERSION = "historical_reaction_profile/v1"

# --- Taxonomia -------------------------------------------------------------
# Una sola clase, la unica que hoy se identifica de forma robusta en el
# repositorio: tiene fecha de publicacion, franja horaria, expectativa y
# sorpresa, todo de la misma fuente. Los eventos de P4 sobre noticias son
# `ASSERTS_SENTIMENT` -- la postura declarada por un medio, no un hecho
# economico -- y el propio P4 lo dice en sus `unknowns`.
#
# NO se amplia la taxonomia para aumentar n.
CLASES_DE_EVENTO = {
    "earnings_release": "publicacion de resultados trimestrales",
}

# --- Semantica de las medidas (D-27) ---------------------------------------
# "change" era demasiado ambiguo: volume(evento)/volume(-1) y
# volume(evento)/median(volume[-20,-1]) son cosas distintas, y ninguna de
# las dos es necesariamente "volumen anormal". El nombre de la variable no
# puede esconder la metodologia.
#
# Solo las tres primeras familias estan implementadas; las dos ultimas se
# nombran para que quien las quiera usar tenga que declararlas antes --
# mismo patron que D-10 con ESTIMATED.
FAMILIAS_SEMANTICAS = {
    "RETURN":                  "variacion de precio entre dos extremos; no necesita estado previo",
    "RELATIVE_TO_BENCHMARK":   "retorno menos el del benchmark formal",
    "RELATIVE_TO_PEER":        "retorno menos el de un comparable declarado; NUNCA es anormal",
    "RELATIVE_TO_PRE_EVENT":   "nivel de la ventana de reaccion sobre el de la ventana de estimacion",
    "STANDARDIZED_DEVIATION":  "desviacion tipificada respecto a la ventana de estimacion -- NO IMPLEMENTADA",
    "LEVEL":                   "el nivel en bruto, sin referencia -- NO IMPLEMENTADA",
}
FAMILIAS_NO_IMPLEMENTADAS = {"STANDARDIZED_DEVIATION", "LEVEL"}

SEMANTICA_DE_MEDIDA = {
    "RAW_RETURN":                       "RETURN",
    "ABNORMAL_RETURN":                  "RELATIVE_TO_BENCHMARK",
    "PEER_RELATIVE_RETURN":             "RELATIVE_TO_PEER",
    "VOLUME_RELATIVE_TO_PRE_EVENT":     "RELATIVE_TO_PRE_EVENT",
    "VOLATILITY_RELATIVE_TO_PRE_EVENT": "RELATIVE_TO_PRE_EVENT",
}
MEDIDAS = tuple(SEMANTICA_DE_MEDIDA)

# Medidas cuya metodologia NO esta suficientemente justificada. Se declaran
# y se rechazan con su razon: es preferible a publicar un numero ambiguo.
#
# La volatilidad del contrato es `volatilidad_hist_30d_anualizada_pct`, una
# MEDIA MOVIL de 30 sesiones. El valor del dia del evento ya contiene las
# 30 anteriores, entre ellas la ventana de estimacion [-20,-1] entera:
# comparar los dos compara ventanas SOLAPADAS, el cociente esta amortiguado
# por construccion y los terminos no son independientes. Una reaccion de un
# dia no se mide con una media movil de 30.
MEDIDAS_SIN_METODOLOGIA = {
    "VOLATILITY_RELATIVE_TO_PRE_EVENT": (
        "la volatilidad disponible es una media movil de 30 sesiones: el valor del evento ya "
        "contiene la ventana de estimacion completa, asi que el cociente compara dos ventanas "
        "solapadas. Haria falta volatilidad realizada sobre la ventana de reaccion, que no esta "
        "en el contrato."),
}

HORIZONTES = tuple(er.HORIZONTES)

# --- Estados del perfil ----------------------------------------------------
ESTADOS = {
    "VALID":                     "hay muestra suficiente y la medida es elegible",
    "INSUFFICIENT_SAMPLE":       "la medida es elegible pero no hay eventos independientes suficientes",
    "NO_BENCHMARK":              "la medida exige benchmark formal y no hay ninguno valido",
    "INSUFFICIENT_COMPARABILITY": "no hay referencia declarada contra la que comparar",
    "PIT_INVALID":               "ningun evento era conocible en la fecha as_of",
    "UNSTABLE":                  "hay muestra, pero las dos mitades temporales no coinciden en signo",
    "INSUFFICIENT_METHODOLOGY":  "la medida no tiene una definicion suficientemente justificada",
}

# --- Dos estados, no uno (D-29) --------------------------------------------
# Un perfil puede ser COMPUTABLE y descriptivamente correcto sin tener
# ninguna capacidad predictiva demostrada. Colapsarlos en un unico VALID
# invita justo al error que este proyecto evita: convertir una cifra
# calculable en una certeza economica.
#
#     COMPUTABLE  !=  INTERPRETABLE  !=  PREDICTIVO
PREDICTIVE_STATUS = {
    "NOT_EVALUATED": "no se ha hecho ninguna validacion predictiva -- el estado de v1",
    "VALID":         "hay validacion walk-forward fuera de muestra que la sostiene",
    "INVALID":       "se evaluo y no se sostiene",
}

# --- Motivos de exclusion --------------------------------------------------
# Ninguna observacion se descarta en silencio: toda exclusion lleva uno.
EXCL_PIT = "PIT: available_at posterior a as_of"
# Un evento puede ser conocible en as_of y su ventana terminar despues.
# Usar esa ventana seria look-ahead igualmente: el perfil de una fecha
# historica no puede saber como acabo una ventana que aun no habia
# terminado. Es la misma familia de error que P6.2a corrigio en el
# contrato, aqui en la dimension del horizonte.
EXCL_PIT_VENTANA = "PIT: la ventana del horizonte termina despues de as_of"
EXCL_TIMING = "TIMING: sin primera sesion negociable (franja de publicacion desconocida)"
EXCL_CLASE = "CLASE: event_class fuera de la taxonomia"
EXCL_SOLAPE = "SOLAPE: la ventana del horizonte alcanza al evento siguiente del mismo activo"

# --- Politica de solapamiento (D-30) ---------------------------------------
# v1 EXCLUIA los eventos solapados. Ahora no: se MARCAN y se publican las
# dos muestras. Eliminarlos de entrada impedia medir cuanto cambia la
# distribucion al quitar la contaminacion -- que es justo lo que hay que
# saber antes de ampliar la cohorte.
POLITICA_SOLAPE = ("FLAG", "EXCLUDE")
EXCL_BENCHMARK = "BENCHMARK: sin benchmark formal elegible para esa sesion"
EXCL_OBSERVACION = "OBSERVACION: la medida no tiene valor en esas dos sesiones"

# Episodio: una publicacion de resultados NO procede de documentos
# agrupables. No es que se desconozca su episodio -- es que el concepto no
# aplica a esta clase. El proyecto ya distingue "no puedo" de "no se"
# (P6): NOT_APPLICABLE no mejora con mas datos, UNKNOWN si.
NO_APLICA = "NOT_APPLICABLE"


class PerfilError(ValueError):
    pass


# --- Poblacion -------------------------------------------------------------

def poblacion(observaciones, measure_type, horizonte, as_of, politica_solape="FLAG"):
    """(incluidas, exclusiones) aplicando los filtros EN ORDEN.

    El orden importa y es el mismo que ordena el resto del proyecto:
    ¿existe la evidencia? ¿es temporalmente valida? ¿es comparable?
    Un evento excluido por PIT no vuelve a evaluarse por benchmark: se
    registra la PRIMERA razon por la que sale, que es la que de verdad lo
    saca.
    """
    as_of = str(as_of)[:10]
    incluidas, exclusiones = [], []

    for o in observaciones:
        def fuera(motivo):
            exclusiones.append({"asset_id": o["asset_id"], "period_end": o["period_end"],
                                "published_at": o["published_at"], "motivo": motivo})

        if o["available_at"][:10] > as_of:
            fuera(EXCL_PIT); continue
        if o.get("event_class") not in CLASES_DE_EVENTO:
            fuera(EXCL_CLASE); continue
        if o["first_tradable_at"] is None:
            fuera(EXCL_TIMING); continue
        ventana = o.get("ventanas", {}).get(horizonte)
        if ventana and ventana[1] is not None and ventana[1] > as_of:
            fuera(EXCL_PIT_VENTANA); continue
        if politica_solape == "EXCLUDE" and o.get("solapa_por_horizonte", {}).get(horizonte):
            fuera(EXCL_SOLAPE); continue

        valor = o["medidas"].get((measure_type, horizonte))
        if valor is None:
            motivo = o["motivos"].get((measure_type, horizonte), EXCL_OBSERVACION)
            if measure_type == "ABNORMAL_RETURN" and motivo in (
                    er.SIN_BENCHMARK, er.SIN_ASIGNACION, er.CALENDARIO_INCOMPATIBLE,
                    er.FUERA_DE_VIGENCIA, er.FUERA_DE_SERIE, er.SIN_METODOLOGIA,
                    er.NO_ES_BENCHMARK_FORMAL, er.SIN_OBSERVACION_BENCHMARK):
                fuera(f"{EXCL_BENCHMARK} ({motivo})")
            elif measure_type == "PEER_RELATIVE_RETURN":
                fuera(f"{EXCL_OBSERVACION} ({motivo})")
            else:
                fuera(f"{EXCL_OBSERVACION} ({motivo})")
            continue

        incluidas.append((o, valor))
    return incluidas, exclusiones


def conteos(incluidas):
    """Los cinco conteos, separados aunque coincidan.

    Que coincidan hoy es informacion, no ruido: dice que en esta cohorte
    cada observacion es un evento distinto y que ningun evento comparte
    episodio con otro."""
    eventos = {(o["asset_id"], o["event_class"], o["period_end"]) for o, _v in incluidas}
    # Tras el filtro de solape, lo que queda no se pisa con otro evento del
    # mismo activo dentro del horizonte: por construccion es independiente.
    episodios = {o.get("episode_id") for o, _v in incluidas if o.get("episode_id")}
    return {
        "n_observations": len(incluidas),
        "n_events": len(eventos),
        "n_independent_events": len(eventos),
        "n_episodes": len(episodios) if episodios else NO_APLICA,
        "n_independent_episodes": len(episodios) if episodios else NO_APLICA,
        "n_activos": len({o["asset_id"] for o, _v in incluidas}),
    }


# --- Estadisticos ----------------------------------------------------------

def _percentil(ordenados, p):
    """Percentil por interpolacion lineal. Implementado a mano y no con
    statistics.quantiles para que el resultado no dependa de la version de
    Python ni de un `method` implicito."""
    if not ordenados:
        return None
    if len(ordenados) == 1:
        return ordenados[0]
    k = (len(ordenados) - 1) * p
    bajo, alto = int(k), min(int(k) + 1, len(ordenados) - 1)
    return round(ordenados[bajo] + (ordenados[alto] - ordenados[bajo]) * (k - bajo), 2)


# Valor NEUTRO de cada familia: el punto respecto al cual "positivo"
# significa algo. Para un retorno es 0; para un cociente contra la ventana
# de estimacion es 1. Usar 0 en un cociente daria prob_positive = 1,00
# siempre -- un numero cierto y completamente vacio.
NEUTRO_POR_FAMILIA = {"RETURN": 0.0, "RELATIVE_TO_BENCHMARK": 0.0,
                      "RELATIVE_TO_PEER": 0.0, "RELATIVE_TO_PRE_EVENT": 1.0}


def estadisticos(valores, neutro=0.0):
    """La distribucion, no un numero. La mediana va primero a proposito:
    con muestras pequeñas y colas gruesas la media sola engaña."""
    if not valores:
        return None
    o = sorted(valores)
    n = len(o)
    p25, p75 = _percentil(o, 0.25), _percentil(o, 0.75)
    return {
        "median": _percentil(o, 0.50),
        "mean": round(sum(o) / n, 2),
        "p10": _percentil(o, 0.10),
        "p25": p25,
        "p75": p75,
        "p90": _percentil(o, 0.90),
        "neutro": neutro,
        "prob_positive": round(sum(1 for v in o if v > neutro) / n, 3),
        "dispersion_iqr": round(p75 - p25, 2),
        "min": o[0],
        "max": o[-1],
    }


def _minimo_declarado(measure_type):
    """Se reutiliza el minimo POR MEDIDA de D-22, no un umbral global.

    El horizonte NO lleva un minimo propio inventado: influye a traves de
    la poblacion real -- una ventana de 60 sesiones excluye por solape lo
    que una de 1 no -- asi que un horizonte largo sale INSUFFICIENT_SAMPLE
    por evidencia, no por un numero elegido a mano.
    """
    return er.MINIMOS_DECLARADOS.get((measure_type, "reaccion_mediana_por_clase"))


def _estabilidad(incluidas, minimo):
    """(estable, detalle). Split-half por fecha de publicacion: si las dos
    mitades no coinciden en el signo de la mediana, la cohorte no se
    describe bien con un numero.

    Solo se evalua con al menos 2x el minimo declarado: partir una muestra
    que apenas llega al minimo produciria dos mitades sin significado.
    """
    if len(incluidas) < 2 * minimo:
        return None, {"evaluable": False, "motivo": f"hacen falta {2 * minimo} observaciones para partir la muestra"}
    ordenadas = sorted(incluidas, key=lambda x: x[0]["published_at"])
    mitad = len(ordenadas) // 2
    m1 = _percentil(sorted(v for _o, v in ordenadas[:mitad]), 0.50)
    m2 = _percentil(sorted(v for _o, v in ordenadas[mitad:]), 0.50)
    estable = (m1 >= 0) == (m2 >= 0)
    return estable, {"evaluable": True, "median_primera_mitad": m1, "median_segunda_mitad": m2}


def perfil(observaciones, event_class, measure_type, horizonte, as_of,
           politica_solape="FLAG"):
    """Un HistoricalReactionProfile. Siempre devuelve algo: si no puede
    construirse, devuelve por que."""
    if measure_type not in MEDIDAS:
        raise PerfilError(f"medida fuera del vocabulario: {measure_type}")
    if horizonte not in HORIZONTES:
        raise PerfilError(f"horizonte fuera del vocabulario: {horizonte}")

    if measure_type in MEDIDAS_SIN_METODOLOGIA:
        return {
            "event_class": event_class, "measure_type": measure_type, "horizon": horizonte,
            "as_of_date": str(as_of)[:10], "methodology_version": METHODOLOGY_VERSION,
            "benchmark_id": None, "benchmark_methodology_version": None, "metodo_ajuste": None,
            "n_observations": 0, "n_events": 0, "n_independent_events": 0,
            "n_episodes": NO_APLICA, "n_independent_episodes": NO_APLICA, "n_activos": 0,
            "n_excluidas": 0, "tasa_exclusion": None, "exclusiones_por_motivo": {},
            "statistics": None, "estabilidad": None,
            "status": "INSUFFICIENT_METHODOLOGY",
            "status_reason": MEDIDAS_SIN_METODOLOGIA[measure_type],
            "descriptive_status": "INSUFFICIENT_METHODOLOGY",
            "predictive_status": "NOT_EVALUATED",
            "semantica": SEMANTICA_DE_MEDIDA[measure_type],
            "estimation_window": None, "reaction_window": horizonte,
            "politica_solape": politica_solape,
            "overlap_event_count": 0, "overlap_rate": None,
            "statistics_non_overlapping": None,
        }

    del_clase = [o for o in observaciones if o.get("event_class") == event_class]
    incluidas, exclusiones = poblacion(del_clase, measure_type, horizonte, as_of, politica_solape)
    c = conteos(incluidas)
    solapadas = [x for x in incluidas
                 if x[0].get("solapa_por_horizonte", {}).get(horizonte)]
    limpias = [x for x in incluidas if x not in solapadas]

    p = {
        "event_class": event_class,
        "measure_type": measure_type,
        "horizon": horizonte,
        "as_of_date": str(as_of)[:10],
        "methodology_version": METHODOLOGY_VERSION,
        "semantica": SEMANTICA_DE_MEDIDA[measure_type],
        "estimation_window": f"[-{er.LARGO_VENTANA_ESTIMACION},-1]" if
                             SEMANTICA_DE_MEDIDA[measure_type] == "RELATIVE_TO_PRE_EVENT" else None,
        "reaction_window": horizonte,
        "politica_solape": politica_solape,
        "overlap_event_count": len(solapadas),
        "overlap_rate": round(len(solapadas) / len(incluidas), 3) if incluidas else None,
        "statistics_non_overlapping": None,
        "descriptive_status": None,
        "predictive_status": "NOT_EVALUATED",
        "benchmark_id": None,
        "benchmark_methodology_version": None,
        "metodo_ajuste": None,
        **c,
        "n_excluidas": len(exclusiones),
        "tasa_exclusion": round(len(exclusiones) / len(del_clase), 3) if del_clase else None,
        "exclusiones_por_motivo": {},
        "statistics": None,
        "estabilidad": None,
        "status": None,
        "status_reason": None,
    }
    for x in exclusiones:
        clave = x["motivo"].split(" (")[0]
        p["exclusiones_por_motivo"][clave] = p["exclusiones_por_motivo"].get(clave, 0) + 1

    # Un perfil de retorno anormal sin la identidad de su benchmark es
    # irreproducible: se exige, no se rellena.
    if measure_type == "ABNORMAL_RETURN" and incluidas:
        bids = {o["benchmark_id"] for o, _v in incluidas if o.get("benchmark_id")}
        vers = {o["benchmark_methodology_version"] for o, _v in incluidas if o.get("benchmark_id")}
        met = {o["metodo_ajuste"] for o, _v in incluidas if o.get("metodo_ajuste")}
        if len(bids) != 1 or len(vers) != 1 or len(met) != 1:
            p["status"] = "INSUFFICIENT_COMPARABILITY"
            p["status_reason"] = (f"el perfil mezclaria {len(bids)} benchmarks / {len(vers)} versiones "
                                  f"de metodologia: seria irreproducible")
            p["descriptive_status"] = p["status"]
            return p
        p["benchmark_id"], = bids
        p["benchmark_methodology_version"], = vers
        p["metodo_ajuste"], = met

    # --- estado ---
    if not incluidas:
        motivos = set(p["exclusiones_por_motivo"])
        if del_clase and motivos <= {EXCL_PIT, EXCL_PIT_VENTANA}:
            p["status"], p["status_reason"] = "PIT_INVALID", "ningun evento era conocible en as_of"
        elif measure_type == "ABNORMAL_RETURN":
            p["status"], p["status_reason"] = "NO_BENCHMARK", "sin benchmark formal elegible para ningun evento"
        elif measure_type == "PEER_RELATIVE_RETURN":
            p["status"] = "INSUFFICIENT_COMPARABILITY"
            p["status_reason"] = "no hay ninguna comparison reference declarada para estos activos"
        else:
            p["status"], p["status_reason"] = "INSUFFICIENT_SAMPLE", "ninguna observacion supera los filtros"
        p["descriptive_status"] = p["status"]
        return p

    minimo = _minimo_declarado(measure_type)
    p["minimo_declarado"] = minimo
    if minimo is None:
        p["status"] = "INSUFFICIENT_COMPARABILITY"
        p["status_reason"] = f"no hay minimo declarado para {measure_type} (D-22)"
        p["descriptive_status"] = p["status"]
        return p

    neutro = NEUTRO_POR_FAMILIA[SEMANTICA_DE_MEDIDA[measure_type]]
    p["statistics"] = estadisticos([v for _o, v in incluidas], neutro)
    # La muestra sin contaminacion, siempre que quede algo distinto que
    # comparar. No sustituye a la completa: se publican las dos.
    if solapadas and limpias:
        p["statistics_non_overlapping"] = estadisticos([v for _o, v in limpias], neutro)
        p["n_non_overlapping"] = len(limpias)
    estable, detalle = _estabilidad(incluidas, minimo)
    p["estabilidad"] = detalle

    if c["n_independent_events"] < minimo:
        p["status"] = "INSUFFICIENT_SAMPLE"
        p["status_reason"] = f"{c['n_independent_events']} eventos independientes < minimo declarado {minimo}"
    elif estable is False:
        p["status"] = "UNSTABLE"
        p["status_reason"] = (f"las dos mitades temporales no coinciden en signo: "
                              f"{detalle['median_primera_mitad']} vs {detalle['median_segunda_mitad']}")
    else:
        p["status"] = "VALID"
        p["status_reason"] = None
    p["descriptive_status"] = p["status"]
    return p


def rejilla(observaciones, as_of, clases=None, medidas=MEDIDAS, horizontes=HORIZONTES):
    """Todos los perfiles de la rejilla event_class x measure_type x horizon.
    Ninguno se omite: los que no se pueden construir salen con su estado."""
    clases = clases or list(CLASES_DE_EVENTO)
    return [perfil(observaciones, c, m, h, as_of)
            for c in clases for m in medidas for h in horizontes]


# --- Ejecucion -------------------------------------------------------------

SIMBOLOS_V1 = ("IBM", "NVDA", "XOM")
FIXTURES = os.path.join(RAIZ, "tests", "fixtures", "eventos_resultados")


def observaciones_v1():
    obs = []
    for sym in SIMBOLOS_V1:
        obs += er.estudiar(sym, os.path.join(FIXTURES, f"{sym}_earnings.json"))
    return obs


def _fmt(p):
    st = p["statistics"]
    cuerpo = (f"med={st['median']:>7.2f} p25={st['p25']:>7.2f} p75={st['p75']:>7.2f} "
              f"prob+={st['prob_positive']:.2f} iqr={st['dispersion_iqr']:>6.2f}") if st else "—"
    return (f"  {p['measure_type']:22} {p['horizon']:6} n={p['n_independent_events']:>3} "
            f"excl={p['n_excluidas']:>3} {p['status']:26} {cuerpo}")


if __name__ == "__main__":
    as_of = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    obs = observaciones_v1()
    print(f"HistoricalReactionProfile v1 · as_of={as_of} · {METHODOLOGY_VERSION}")
    print(f"observaciones de partida: {len(obs)} ({', '.join(SIMBOLOS_V1)})\n")
    for p in rejilla(obs, as_of):
        print(_fmt(p))
