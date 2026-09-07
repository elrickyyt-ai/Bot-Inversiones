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


def series_del_activo(asset_id):
    """{metrica: {fecha: valor}} para las metricas que el perfil necesita.

    Una sola lectura del contrato para las tres: volver a resolver las
    capas por cada metrica multiplicaria por tres el coste sin ganar nada.
    """
    asset_type = storage.asset_type_of(asset_id)
    if asset_type is None:
        raise EstudioError(f"{asset_id} no esta en DimAsset")
    quiero = {"precio", "volumen", "volatilidad_hist_30d_anualizada_pct"}
    out = {m: {} for m in quiero}
    for r in storage.resolve(storage.all_layers(asset_type, asset_id)):
        if r["domain"] == "tecnico" and r["metric"] in quiero:
            out[r["metric"]][r["data_as_of"].isoformat()] = r["value"]
    return out


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


def _sesiones_del_horizonte(fechas, s0, s1, horizonte):
    """(desde, hasta) del horizonte, o (None, None, motivo) si la serie no
    llega. Nunca se acorta la ventana para que quepa: un horizonte de 60
    sesiones medido sobre 12 no es ese horizonte."""
    origen, adelante = HORIZONTES[horizonte]
    desde = s0 if origen == "previa" else s1
    i1 = fechas.index(s1)
    if i1 + adelante >= len(fechas):
        return None, None, SIN_SESIONES_SUFICIENTES
    return desde, fechas[i1 + adelante], None


def ventana_estimacion(fechas, s1, largo=None):
    """Las `largo` sesiones que terminan en la anterior a `s1`.

    Devuelve [] si la serie no llega: no se acorta la ventana para que
    quepa, igual que no se acorta un horizonte."""
    largo = LARGO_VENTANA_ESTIMACION if largo is None else largo
    i1 = fechas.index(s1)
    if i1 - largo < 0:
        return []
    return fechas[i1 - largo:i1]


def sesiones_reaccion(fechas, s1, horizonte):
    """Sesiones sobre las que se mide una metrica de NIVEL.

    No coincide con la ventana de un retorno: un retorno se mide entre dos
    extremos, un nivel se resume sobre las sesiones del intervalo. En
    0_1d es la propia sesion del evento; en los de deriva, las posteriores
    (s1 queda fuera: ya esta contada en 0_1d y meterla otra vez mezclaria
    el pico con la deriva)."""
    _origen, adelante = HORIZONTES[horizonte]
    i1 = fechas.index(s1)
    if adelante == 0:
        return [s1]
    if i1 + adelante >= len(fechas):
        return []
    return fechas[i1 + 1:i1 + adelante + 1]


def _mediana(xs):
    o = sorted(xs)
    n = len(o)
    if not n:
        return None
    return o[n // 2] if n % 2 else (o[n // 2 - 1] + o[n // 2]) / 2


def _variacion(serie, desde, hasta):
    """(hasta/desde - 1) en %, o (None, motivo) si falta alguna de las dos
    observaciones. No se sustituye por la sesion mas cercana."""
    if desde not in serie or hasta not in serie:
        return None, SIN_SERIE_DE_LA_MEDIDA
    v0 = serie[desde]
    if not v0:
        return None, SIN_SERIE_DE_LA_MEDIDA
    return round((serie[hasta] - v0) / v0 * 100, 2), None


def observar(evento, fechas, px, benchmark=None, series=None):
    """Una ObservacionDeReaccion. Nunca inventa: cada ausencia lleva su razon.

    `medidas` lleva una entrada por (measure_type, horizonte) con su valor
    o su motivo. Los campos planos `raw_return_1s_pct`,
    `market_adjusted_return_pct` y compania son la entrada de 0_1d, que se
    conserva porque es la interfaz que el Event Study MVP ya publicaba.
    """
    obs = dict(evento)
    obs["available_at"] = evento["published_at"]  # dia, no instante
    t1, razon = first_tradable_at(fechas, evento["published_at"], evento["report_time"])
    obs["first_tradable_at"] = t1
    obs["raw_return_1s_pct"] = None
    obs["sesion_previa"] = None
    obs["razon_sin_reaccion"] = razon
    obs["medidas"] = {}
    obs["motivos"] = {}
    # Sesiones que ocupa la ventana de cada horizonte. Las necesita el
    # perfil para no usar, en un analisis fechado en as_of, una ventana que
    # TERMINA despues de as_of -- eso seria look-ahead aunque el evento si
    # fuese conocible.
    obs["ventanas"] = {}

    s0 = None
    if t1 is not None:
        i = fechas.index(t1)
        if i == 0:
            obs["razon_sin_reaccion"] = SIN_PRECIO_ANTERIOR
        else:
            s0 = fechas[i - 1]
            obs["sesion_previa"] = s0
            obs["raw_return_1s_pct"] = round((px[t1] - px[s0]) / px[s0] * 100, 2)

    obs["market_adjusted_return_pct"] = None
    obs["benchmark_return_1s_pct"] = None
    obs["benchmark_id"] = None
    obs["benchmark_methodology_version"] = None
    obs["metodo_ajuste"] = None
    obs["razon_sin_ajuste"] = SIN_BENCHMARK

    if s0 is None:
        return obs

    series = series or {"precio": px}
    bench_ok, bench_motivo, bpx, entidad = False, SIN_BENCHMARK, None, None
    if benchmark is not None:
        asig, entidad, _bf, bpx, calendario = benchmark
        bench_ok, bench_motivo = benchmark_elegible(t1, calendario, asig, entidad)
        if not bench_ok:
            bench_motivo = bench_motivo or SIN_BENCHMARK

    ventana_est = ventana_estimacion(fechas, t1)
    obs["ventana_estimacion"] = (ventana_est[0], ventana_est[-1]) if ventana_est else None
    contaminada = False   # lo rellena marcar_contaminacion(), que ve toda la cohorte
    obs["ventana_estimacion_contaminada"] = None

    for h in HORIZONTES:
        desde, hasta, motivo = _sesiones_del_horizonte(fechas, s0, t1, h)
        obs["ventanas"][h] = (desde, hasta)
        if motivo:
            for m in ("RAW_RETURN", "ABNORMAL_RETURN", "VOLUME_RELATIVE_TO_PRE_EVENT"):
                obs["motivos"][(m, h)] = motivo
            obs["motivos"][("PEER_RELATIVE_RETURN", h)] = SIN_REFERENCIA
            continue

        raw, mot = _variacion(series["precio"], desde, hasta)
        obs["medidas"][("RAW_RETURN", h)] = raw
        if mot:
            obs["motivos"][("RAW_RETURN", h)] = mot

        # ABNORMAL: mismas dos sesiones, benchmark declarado, y siempre con
        # la identidad de quien lo produjo.
        if not bench_ok:
            obs["motivos"][("ABNORMAL_RETURN", h)] = bench_motivo
        else:
            bret, mot_b = _variacion(bpx, desde, hasta)
            if mot_b:
                obs["motivos"][("ABNORMAL_RETURN", h)] = SIN_OBSERVACION_BENCHMARK
            elif raw is None:
                obs["motivos"][("ABNORMAL_RETURN", h)] = mot
            else:
                obs["medidas"][("ABNORMAL_RETURN", h)] = round(raw - bret, 2)
                if h == "0_1d":
                    obs["benchmark_return_1s_pct"] = bret
                    obs["market_adjusted_return_pct"] = round(raw - bret, 2)
                    obs["benchmark_id"] = entidad["entity_id"]
                    obs["benchmark_methodology_version"] = entidad["benchmark"]["methodology_version"]
                    obs["metodo_ajuste"] = DIFERENCIA_SIMPLE
                    obs["razon_sin_ajuste"] = None

        # VOLUMEN relativo al estado PREVIO, no a la sesion del evento
        # (D-27). La base es la MEDIANA de la ventana de estimacion:
        # medido sobre la cohorte, el 90% de las ventanas tiene media >
        # mediana -- cola derecha -- asi que una base con media queda
        # inflada por picos anteriores y hunde el ratio (47 de 52 eventos
        # dan un ratio menor con media que con mediana).
        base_v = _mediana([series["volumen"][d] for d in ventana_est
                           if d in series.get("volumen", {})]) if ventana_est else None
        reaccion = sesiones_reaccion(fechas, t1, h)
        vols = [series["volumen"][d] for d in reaccion if d in series.get("volumen", {})]
        if not ventana_est:
            obs["motivos"][("VOLUME_RELATIVE_TO_PRE_EVENT", h)] = SIN_VENTANA_ESTIMACION
        elif contaminada:
            obs["motivos"][("VOLUME_RELATIVE_TO_PRE_EVENT", h)] = VENTANA_ESTIMACION_CONTAMINADA
        elif not base_v or not vols or len(vols) < len(reaccion):
            obs["motivos"][("VOLUME_RELATIVE_TO_PRE_EVENT", h)] = SIN_SERIE_DE_LA_MEDIDA
        else:
            obs["medidas"][("VOLUME_RELATIVE_TO_PRE_EVENT", h)] = round(_mediana(vols) / base_v, 3)

        # PEER_RELATIVE: no hay ninguna comparison reference declarada.
        obs["motivos"][("PEER_RELATIVE_RETURN", h)] = SIN_REFERENCIA

    if obs["razon_sin_ajuste"] is None:
        pass
    elif bench_motivo:
        obs["razon_sin_ajuste"] = bench_motivo
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
    series = series_del_activo(asset_id)
    px = series["precio"]
    fechas = sorted(px)
    eventos = leer_eventos(path_eventos)
    benchmark = _benchmark_para(asset_id) if con_benchmark else None
    obs = [observar(e, fechas, px, benchmark, series) for e in eventos]
    marcar_solapamientos(obs, ventana_sesiones, fechas)
    # Solapamiento POR HORIZONTE: una ventana de 60 sesiones alcanza al
    # trimestre siguiente y una de 1 no. Un solo booleano no sirve.
    for h, ventana in VENTANA_SESIONES.items():
        marcados = marcar_solapamientos([dict(o) for o in obs], ventana, fechas)
        for o, m in zip(obs, marcados):
            o.setdefault("solapa_por_horizonte", {})[h] = m["solapa_con"]
    return obs


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
    "VOLUME_RELATIVE_TO_PRE_EVENT": "nivel de volumen sobre la mediana de la ventana de estimacion",
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
    ("VOLUME_RELATIVE_TO_PRE_EVENT", "reaccion_mediana_por_clase"): 30,
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

# --- Horizontes (D-26) -----------------------------------------------------
# Todos se cuentan en SESIONES REALES de la serie del activo, nunca en dias
# naturales: el proyecto ya rechazo esa aproximacion al construir
# trading_calendar.py. `s0` es la sesion previa al evento y `s1` la primera
# NEGOCIABLE (que depende de reportTime, no del dia del anuncio).
#
#   0_1d    s0 -> s1        la reaccion inmediata: lo que el MVP ya media
#   2_5d    s1 -> s1+4      deriva posterior, dias +2..+5 en notacion de evento
#   2_20d   s1 -> s1+19
#   2_60d   s1 -> s1+59
#
# Los tres ultimos arrancan en s1 y no en s0 a proposito: si arrancasen en
# s0 incluirian la reaccion inmediata y no serian deriva, serian la misma
# medida con mas ruido.
HORIZONTES = {
    "0_1d":  ("previa", 0),
    "2_5d":  ("primera", 4),
    "2_20d": ("primera", 19),
    "2_60d": ("primera", 59),
}

# Sesiones que ocupa la ventana de cada horizonte, para detectar
# solapamiento con el evento siguiente.
VENTANA_SESIONES = {"0_1d": 1, "2_5d": 5, "2_20d": 20, "2_60d": 60}

SIN_SESIONES_SUFICIENTES = "SERIE_SIN_SESIONES_SUFICIENTES_PARA_EL_HORIZONTE"
SIN_SERIE_DE_LA_MEDIDA = "SIN_SERIE_PARA_ESA_MEDIDA_EN_ESAS_SESIONES"
SIN_REFERENCIA = "SIN_COMPARABLE_DECLARADO"
SIN_VENTANA_ESTIMACION = "SIN_VENTANA_DE_ESTIMACION_COMPLETA"
VENTANA_ESTIMACION_CONTAMINADA = "VENTANA_DE_ESTIMACION_CON_OTRO_EVENTO_DENTRO"

# --- Ventana de estimacion (D-27) ------------------------------------------
# `reaction_window` la definen los horizontes. `estimation_window` es el
# estado PREVIO contra el que se compara una metrica de nivel. Son cosas
# distintas y por eso llevan nombres distintos.
#
# [-20,-1]: las 20 sesiones que terminan en s0 (la anterior a la primera
# negociable). Medido sobre la cohorte real: 52/52 eventos la tienen
# completa, 0 estan contaminadas por otro evento del mismo activo -- con
# intervalos de 58+ sesiones entre resultados, una ventana de 20 no llega
# a alcanzar el trimestre anterior. NO se adopta como constante universal:
# es la ventana declarada para ESTA cohorte y hay que revalidarla en otra.
LARGO_VENTANA_ESTIMACION = 20


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
