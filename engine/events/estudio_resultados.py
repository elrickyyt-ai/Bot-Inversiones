"""Vertical minima de event study sobre resultados trimestrales -- P6.2c.

Responde UNA pregunta, de extremo a extremo y de forma reproducible:

    ¿Que informacion estaba realmente disponible en ese momento, que
    sorpresa implicaba, cuando pudo negociarse por primera vez y como
    reacciono el activo?

Lo que este modulo NO es. No es un Historical Reaction Engine, no agrega
en perfiles, no calcula medianas por cohorte, no produce señales y no
afirma causalidad. Emite OBSERVACIONES individuales, cada una con lo que
se sabe y con lo que no. La agregacion queda deliberadamente fuera: ver
`suficiencia_de_muestra()` mas abajo, que explica por que.

Los cinco relojes de engine/contract/temporal.py, instanciados aqui:

    period_end        fiscalDateEnding   fin del trimestre
    published_at      reportedDate       dia en que se publico
    available_at      = published_at     (ver la nota sobre semantica)
    first_tradable_at derivado           primera SESION negociable
    retrieved_at      -                  no aplica a un evento

Por que available_at = published_at y no algo mas fino. Alpha Vantage da
el DIA de publicacion y una etiqueta de franja (`reportTime`), no una
marca de tiempo. Llamar a eso "el instante en que se supo" seria inventar
precision. Lo que si es defendible: el dia en que se publico es el primer
dia en que se pudo saber. Por eso `timestamp_semantics` viaja con cada
observacion y vale PROVEEDOR_DIA -- el consumidor no puede confundirlo
con una marca de tiempo real.

Por que first_tradable_at NO es lo mismo. Si la publicacion es
`post-market`, la informacion es publica ese mismo dia pero la primera
oportunidad de negociar es la sesion SIGUIENTE. Medir la reaccion en la
sesion del anuncio, como haria una regla ingenua de "el dia del evento",
mide un dia en el que la noticia todavia no existia. Con `pre-market` la
sesion del propio anuncio SI es la primera negociable. Las tres acciones
del universo se reparten entre las dos franjas -- XOM publica casi
siempre pre-market, IBM y NVDA casi siempre post-market -- asi que no es
un caso de laboratorio.
"""
import bisect
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "engine", "contract"))

import storage  # noqa: E402

sys.path.insert(0, os.path.join(RAIZ, "engine", "knowledge"))
sys.path.insert(0, os.path.join(RAIZ, "engine", "technical"))
import modelo            # noqa: E402
import fetch_benchmark   # noqa: E402


# Semantica declarada del timestamp que da el proveedor. No es una
# marca de tiempo: es el dia que el proveedor reporta como publicacion.
PROVEEDOR_DIA = "PROVEEDOR_DIA"

# Razones por las que una observacion puede no tener reaccion. Ninguna se
# rellena con un valor por defecto: la ausencia se propaga como ausencia.
SIN_MOMENTO = "MOMENTO_DE_PUBLICACION_DESCONOCIDO"
SIN_PRECIO_POSTERIOR = "SIN_SESION_POSTERIOR_EN_EL_CONTRATO"
SIN_PRECIO_ANTERIOR = "SIN_SESION_ANTERIOR_EN_EL_CONTRATO"

# Razon por la que el retorno anormal no se calcula. Es una ausencia
# ESTRUCTURAL, no un fallo: no hay ningun indice en el contrato.
SIN_BENCHMARK = "SIN_BENCHMARK_EN_EL_CONTRATO"


class EstudioError(ValueError):
    pass


def _num(v):
    if v in (None, "None", ""):
        return None
    return float(v)


def leer_eventos(path):
    """Normaliza el payload de Alpha Vantage EARNINGS a eventos.

    Se conserva `surprisePercentage` tal y como lo da la fuente en vez de
    recalcularlo: es el dato del proveedor, y recalcularlo con
    (reportado-estimado)/|estimado| daria numeros distintos y sin sentido
    cuando el estimado es cero o negativo (caso real: NVDA 2009-07-31,
    estimado -0.001 y sorpresa declarada 300%). La comprobacion de que
    ambos son coherentes cuando el estimado es sano vive en los tests.
    """
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    symbol = raw["symbol"]
    eventos = []
    for q in raw["quarterlyEarnings"]:
        eventos.append({
            "asset_id": symbol,
            "event_class": "earnings_release",
            "period_end": q["fiscalDateEnding"],
            "published_at": q["reportedDate"],
            "report_time": q.get("reportTime"),
            "expected_eps": _num(q.get("estimatedEPS")),
            "reported_eps": _num(q.get("reportedEPS")),
            "surprise_pct": _num(q.get("surprisePercentage")),
            "timestamp_semantics": PROVEEDOR_DIA,
        })
    eventos.sort(key=lambda e: e["published_at"])
    return eventos


def serie_de_precios(asset_id):
    """(fechas ordenadas, {fecha: precio}) desde el Data Contract resuelto.

    Lee las tres capas y las resuelve con la regla de precedencia del
    propio almacenamiento; no reimplementa ninguna."""
    asset_type = storage.asset_type_of(asset_id)
    if asset_type is None:
        raise EstudioError(f"{asset_id} no esta en DimAsset")
    px = {}
    for r in storage.resolve(storage.all_layers(asset_type, asset_id)):
        if r["domain"] == "tecnico" and r["metric"] == "precio":
            px[r["data_as_of"].isoformat()] = r["value"]
    return sorted(px), px


def first_tradable_at(fechas, published_at, report_time):
    """Primera sesion en la que la informacion pudo negociarse.

    pre-market   -> la sesion del propio anuncio, si existe; si el anuncio
                    cayo en dia no habil, la siguiente que exista.
    post-market  -> la siguiente sesion, siempre.
    None         -> None. No se elige una de las dos por defecto: elegir
                    seria inventar el dato que falta, y las dos opciones
                    difieren en una sesion entera de reaccion.
    """
    if report_time not in ("pre-market", "post-market"):
        return None, SIN_MOMENTO
    i = (bisect.bisect_left(fechas, published_at) if report_time == "pre-market"
         else bisect.bisect_right(fechas, published_at))
    if i >= len(fechas):
        return None, SIN_PRECIO_POSTERIOR
    return fechas[i], None


def asignacion_de(asset_id, role="MARKET", k=None):
    """(asignacion, entidad_benchmark) declaradas para este activo y rol.

    BUSCA, no elige: si hubiera dos vigentes a la vez seria un error del
    conocimiento -- el validador de Knowledge ya lo rechaza -- y aqui se
    levanta en vez de quedarse con una. Es la mitad de la defensa contra
    el benchmark selection bias; la otra mitad es que `modelo` no tiene
    funciones de escritura (D-04).
    """
    k = k or modelo.cargar()
    entidades = {e["entity_id"]: e for e in k["entities"]}
    sujeto = next((e["entity_id"] for e in k["entities"]
                   if e.get("asset_id") == asset_id and e["type"] == "security"), None)
    if sujeto is None:
        return None, None
    candidatas = [r for r in k["relationships"]
                  if r.get("predicate") == "BENCHMARKED_BY" and r.get("subject") == sujeto
                  and r.get("role") == role and r.get("polarity") == "AFFIRMS"]
    if len(candidatas) > 1:
        raise EstudioError(
            f"{asset_id} tiene {len(candidatas)} benchmarks declarados de rol {role}: "
            f"el calculo no elige entre ellos")
    if not candidatas:
        return None, None
    asig = candidatas[0]
    return asig, entidades.get(asig["object"])


def _benchmark_id(entidad):
    """El identificador con el que la serie esta guardada en
    data/benchmarks/. Se toma del propio entity_id, sin prefijo."""
    return entidad["entity_id"].split(":", 1)[1].upper()


def observar(evento, fechas, px, benchmark=None):
    """Una ObservacionDeReaccion. Nunca inventa: cada ausencia lleva su razon."""
    obs = dict(evento)
    obs["available_at"] = evento["published_at"]  # dia, no instante
    t1, razon = first_tradable_at(fechas, evento["published_at"], evento["report_time"])
    obs["first_tradable_at"] = t1
    obs["raw_return_1s_pct"] = None
    obs["sesion_previa"] = None
    obs["razon_sin_reaccion"] = razon

    if t1 is not None:
        i = fechas.index(t1)
        if i == 0:
            obs["razon_sin_reaccion"] = SIN_PRECIO_ANTERIOR
        else:
            t0 = fechas[i - 1]
            obs["sesion_previa"] = t0
            obs["raw_return_1s_pct"] = round((px[t1] - px[t0]) / px[t0] * 100, 2)

    # Retorno anormal. Un retorno bruto NO es un retorno anormal, y
    # llamarlos igual seria el mismo error de token compartido que el
    # proyecto ya se prohibio: por eso viajan en campos distintos y el
    # ajustado lleva siempre la identidad del benchmark que lo produjo.
    obs["market_adjusted_return_pct"] = None
    obs["benchmark_return_1s_pct"] = None
    obs["benchmark_id"] = None
    obs["benchmark_methodology_version"] = None
    obs["metodo_ajuste"] = None
    obs["razon_sin_ajuste"] = SIN_BENCHMARK

    if benchmark is not None and obs["raw_return_1s_pct"] is not None:
        asig, entidad, bfechas, bpx, calendario = benchmark
        ok, motivo = benchmark_elegible(t1, calendario, asig, entidad)
        if not ok:
            obs["razon_sin_ajuste"] = motivo
        elif obs["sesion_previa"] not in bpx or t1 not in bpx:
            # El benchmark tiene que observar EXACTAMENTE las dos mismas
            # sesiones. Si le falta una, no hay nada que restar y no se
            # sustituye por la sesion mas cercana.
            obs["razon_sin_ajuste"] = SIN_OBSERVACION_BENCHMARK
        else:
            b0, b1 = bpx[obs["sesion_previa"]], bpx[t1]
            bret = (b1 - b0) / b0 * 100
            obs["benchmark_return_1s_pct"] = round(bret, 2)
            obs["market_adjusted_return_pct"] = round(obs["raw_return_1s_pct"] - bret, 2)
            obs["benchmark_id"] = entidad["entity_id"]
            obs["benchmark_methodology_version"] = entidad["benchmark"]["methodology_version"]
            obs["metodo_ajuste"] = DIFERENCIA_SIMPLE
            obs["razon_sin_ajuste"] = None
    return obs


def marcar_solapamientos(observaciones, ventana_sesiones, fechas):
    """Marca las observaciones cuya ventana de reaccion alcanza al
    siguiente evento del MISMO activo.

    Sin esto, una ventana larga atribuiria a un trimestre la reaccion que
    en realidad provoco el siguiente. Se cuenta en SESIONES sobre la serie
    real, no en dias naturales: el proyecto ya rechazo esa aproximacion al
    construir engine/technical/trading_calendar.py.
    """
    por_activo = {}
    for o in observaciones:
        por_activo.setdefault(o["asset_id"], []).append(o)
    for grupo in por_activo.values():
        grupo.sort(key=lambda o: o["published_at"])
        for actual, siguiente in zip(grupo, grupo[1:]):
            actual["solapa_con"] = None
            if actual["first_tradable_at"] is None or siguiente["first_tradable_at"] is None:
                continue
            i = bisect.bisect_left(fechas, actual["first_tradable_at"])
            j = bisect.bisect_left(fechas, siguiente["first_tradable_at"])
            if j - i <= ventana_sesiones:
                actual["solapa_con"] = siguiente["published_at"]
        if grupo:
            grupo[-1].setdefault("solapa_con", None)
    return observaciones


def _benchmark_para(asset_id, k=None):
    """La tupla que `observar()` necesita, o None si no hay asignacion
    declarada. Ninguna de las dos situaciones es un fallo."""
    asig, entidad = asignacion_de(asset_id, "MARKET", k)
    if asig is None or entidad is None:
        return None
    bfechas, bpx = fetch_benchmark.serie(_benchmark_id(entidad))
    if not bfechas:
        return None
    calendario = CALENDARIO_POR_TIPO.get(storage.asset_type_of(asset_id))
    return (asig, entidad, bfechas, bpx, calendario)


def estudiar(asset_id, path_eventos, ventana_sesiones=20, con_benchmark=True):
    fechas, px = serie_de_precios(asset_id)
    eventos = leer_eventos(path_eventos)
    benchmark = _benchmark_para(asset_id) if con_benchmark else None
    obs = [observar(e, fechas, px, benchmark) for e in eventos]
    return marcar_solapamientos(obs, ventana_sesiones, fechas)


# --------------------------------------------------------------------------
# D-21: familias de medida y elegibilidad
# --------------------------------------------------------------------------
# Antes de D-21 habia UNA puerta: sin retorno anormal, no se agregaba nada.
# Era demasiado gruesa. Bloquear la agregacion de retornos anormales sin
# benchmark es correcto; bloquear tambien la de raw_return o volume_change
# no lo es -- esas no necesitan benchmark, y con ellas cripto SI puede
# analizarse aunque su benchmark de mercado no exista.
#
# La elegibilidad es ahora una propiedad de la MEDIDA DERIVADA, no de la
# observacion.
FAMILIAS_DE_MEDIDA = {
    "RAW_RETURN":           "variacion del propio activo; no necesita ninguna referencia",
    "PEER_RELATIVE_RETURN": "variacion respecto a un comparable declarado; NUNCA es retorno anormal",
    "ABNORMAL_RETURN":      "variacion descontado un benchmark formal; exige las cuatro condiciones de abajo",
    "VOLUME_CHANGE":        "variacion del volumen negociado; no necesita referencia",
    "VOLATILITY_CHANGE":    "variacion de la volatilidad; no necesita referencia",
}

# Que necesita cada familia. Solo ABNORMAL_RETURN exige benchmark.
REQUIERE_BENCHMARK = {"ABNORMAL_RETURN"}
REQUIERE_REFERENCIA = {"PEER_RELATIVE_RETURN"}

# Minimos por (familia, pregunta). NO hay un umbral global: el `10` de
# engine/crypto/score.py::_pct_in_window() era el minimo razonable para un
# percentil en ventana movil y no tiene por que servir para estimar la
# reaccion mediana de una clase de evento. Ese modulo NO se toca.
#
# Los numeros son DECLARADOS y conservadores, no estimados. Que
# ABNORMAL_RETURN exija mas que RAW_RETURN no es arbitrario: lleva encima
# el error de estimacion del propio benchmark.
MINIMOS_DECLARADOS = {
    ("RAW_RETURN", "reaccion_mediana_por_clase"): 30,
    ("RAW_RETURN", "reaccion_mediana_condicionada"): 50,
    ("ABNORMAL_RETURN", "reaccion_mediana_por_clase"): 40,
    ("ABNORMAL_RETURN", "reaccion_mediana_condicionada"): 60,
    ("PEER_RELATIVE_RETURN", "reaccion_mediana_por_clase"): 40,
    ("VOLUME_CHANGE", "reaccion_mediana_por_clase"): 30,
    ("VOLATILITY_CHANGE", "reaccion_mediana_por_clase"): 30,
}

# Motivos de no elegibilidad. Ninguno se rellena con un valor por defecto.
SIN_ASIGNACION = "SIN_ASIGNACION_DECLARADA"
FUERA_DE_VIGENCIA = "ASIGNACION_FUERA_DE_VIGENCIA"
FUERA_DE_SERIE = "BENCHMARK_SIN_SERIE_EN_ESA_FECHA"
CALENDARIO_INCOMPATIBLE = "CALENDARIO_INCOMPATIBLE"
SIN_METODOLOGIA = "METODOLOGIA_NO_DECLARADA"
NO_ES_BENCHMARK_FORMAL = "LA_REFERENCIA_NO_ES_BENCHMARK_FORMAL"
SIN_OBSERVACION_BENCHMARK = "BENCHMARK_SIN_OBSERVACION_EN_ESAS_SESIONES"

# Unico metodo de ajuste admitido en v1: r_activo - r_benchmark. El modelo
# de mercado (alfa + beta) exigiria ESTIMAR un coeficiente, y D-10 lo
# prohibe hasta que exista una capa de Model/Calibration con ventana de
# entrenamiento y validacion fuera de muestra.
DIFERENCIA_SIMPLE = "DIFERENCIA_SIMPLE"

CALENDARIO_POR_TIPO = {"equity": "equity", "crypto": "crypto"}


def _entre(fecha, desde, hasta):
    if desde and fecha < desde:
        return False
    if hasta and fecha > hasta:
        return False
    return True


def benchmark_elegible(fecha_reaccion, calendario_activo, asignacion, entidad_benchmark):
    """(bool, motivo) -- las CUATRO condiciones de D-21 para que exista
    retorno anormal. Recibe la asignacion ya resuelta: esta funcion NO
    elige benchmark, lo comprueba. Elegir es un acto de curacion en
    Knowledge (D-04), y ademas el validador solo admite una asignacion por
    (activo, rol, periodo).
    """
    if asignacion is None or entidad_benchmark is None:
        return False, SIN_ASIGNACION
    # 1. semanticamente compatible: una comparison reference no asciende
    if asignacion.get("predicate") != "BENCHMARKED_BY" or asignacion.get("role") == "PEER":
        return False, NO_ES_BENCHMARK_FORMAL
    # 2. temporalmente valida: la asignacion y la serie del benchmark
    if not _entre(fecha_reaccion, asignacion.get("valid_from"), asignacion.get("valid_to")):
        return False, FUERA_DE_VIGENCIA
    bm = entidad_benchmark.get("benchmark") or {}
    if not _entre(fecha_reaccion, bm.get("serie_desde"), bm.get("serie_hasta")):
        return False, FUERA_DE_SERIE
    # 3. observacion disponible: mismo calendario, o no hay nada que restar
    #    en mas de una de cada cuatro sesiones (28,5% en cripto)
    if bm.get("calendar") != calendario_activo:
        return False, CALENDARIO_INCOMPATIBLE
    # 4. metodologia declarada
    if not bm.get("methodology_version") or bm.get("point_in_time_capable") is not True:
        return False, SIN_METODOLOGIA
    return True, None


def elegibilidad(observaciones, familia, pregunta="reaccion_mediana_por_clase",
                 medidas_disponibles=None):
    """(utilizable, informe). NUNCA devuelve un estadistico.

    `medidas_disponibles` es el conjunto de familias que de verdad se han
    podido calcular para estas observaciones. Si no se pasa, se asume la
    unica que el event study calcula hoy.

    El orden de comprobacion es el mismo que ordena todo el proyecto:
    ¿existe la evidencia? ¿es temporalmente valida? ¿es comparable?
    ¿hay muestra suficiente?
    """
    if familia not in FAMILIAS_DE_MEDIDA:
        return False, {"motivo": "FAMILIA_NO_DECLARADA", "familia": familia}
    minimo = MINIMOS_DECLARADOS.get((familia, pregunta))
    if minimo is None:
        return False, {"motivo": "PREGUNTA_NO_DECLARADA", "familia": familia, "pregunta": pregunta}

    disponibles = {"RAW_RETURN"} if medidas_disponibles is None else set(medidas_disponibles)
    con_reaccion = [o for o in observaciones if o["raw_return_1s_pct"] is not None]
    sin_solape = [o for o in con_reaccion if not o.get("solapa_con")]

    informe = {
        "familia": familia,
        "pregunta": pregunta,
        "minimo_declarado": minimo,
        "eventos_totales": len(observaciones),
        "con_medida_calculable": len(con_reaccion),
        "sin_solapamiento": len(sin_solape),
        "n_efectivo_activos": len({o["asset_id"] for o in sin_solape}),
    }

    # La puerta que antes era global ahora es de la familia, y solo se
    # cierra para quien de verdad necesita lo que falta.
    if familia not in disponibles:
        informe["motivo"] = f"MEDIDA_NO_CALCULADA: {familia}"
        if familia in REQUIERE_BENCHMARK:
            informe["motivo"] += f" ({SIN_BENCHMARK})"
        elif familia in REQUIERE_REFERENCIA:
            informe["motivo"] += f" ({SIN_ASIGNACION})"
        return False, informe

    if len(sin_solape) < minimo:
        informe["motivo"] = "MUESTRA_INSUFICIENTE"
        return False, informe
    informe["motivo"] = "SUFICIENTE"
    return True, informe


if __name__ == "__main__":
    base = os.path.join(RAIZ, "tests", "fixtures", "eventos_resultados")
    todas = []
    for sym in ("IBM", "NVDA", "XOM"):
        obs = estudiar(sym, os.path.join(base, f"{sym}_earnings.json"))
        todas += obs
        print(f"\n=== {sym} ===")
        print(f"{'period_end':11} {'published':11} {'franja':12} {'1a negociable':13} "
              f"{'sorpresa%':>10} {'bruto%':>8} {'bench%':>8} {'anormal%':>9}")
        for o in obs:
            def _n(v):
                return f"{v:8.2f}" if v is not None else f"{'—':>8}"
            print(f"{o['period_end']:11} {o['published_at']:11} "
                  f"{str(o['report_time']):12} {str(o['first_tradable_at']):13} "
                  f"{o['surprise_pct'] if o['surprise_pct'] is not None else float('nan'):10.2f} "
                  f"{_n(o['raw_return_1s_pct'])} {_n(o['benchmark_return_1s_pct'])} "
                  f"{_n(o['market_adjusted_return_pct'])}")
    print("\n=== ELEGIBILIDAD POR FAMILIA DE MEDIDA (D-21) ===")
    calculadas = {"RAW_RETURN"}
    if any(o["market_adjusted_return_pct"] is not None for o in todas):
        calculadas.add("ABNORMAL_RETURN")
    for fam in ("RAW_RETURN", "ABNORMAL_RETURN", "PEER_RELATIVE_RETURN", "VOLUME_CHANGE"):
        ok, informe = elegibilidad(todas, fam, medidas_disponibles=calculadas)
        print(f"  {fam:22} utilizable={str(ok):5} n={informe.get('sin_solapamiento')} "
              f"minimo={informe.get('minimo_declarado')} motivo={informe['motivo']}")
