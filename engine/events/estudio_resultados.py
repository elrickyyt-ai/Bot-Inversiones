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


def observar(evento, fechas, px):
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

    # Retorno anormal: NO se calcula, y se dice por que. Un retorno bruto
    # no es un retorno anormal, y llamarlos igual seria el mismo error de
    # token compartido que el proyecto ya se prohibio.
    obs["market_adjusted_return_pct"] = None
    obs["razon_sin_ajuste"] = SIN_BENCHMARK
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


def estudiar(asset_id, path_eventos, ventana_sesiones=20):
    fechas, px = serie_de_precios(asset_id)
    eventos = leer_eventos(path_eventos)
    obs = [observar(e, fechas, px) for e in eventos]
    return marcar_solapamientos(obs, ventana_sesiones, fechas)


# --------------------------------------------------------------------------
# Suficiencia de muestra
# --------------------------------------------------------------------------
# Generalizacion del principio que engine/crypto/score.py ya aplicaba con
# _pct_in_window(): con menos de N observaciones no se devuelve un numero
# peor, se devuelve None. Aqui se declara POR PREGUNTA, no como un umbral
# global: "10" era el minimo razonable para un percentil en una ventana
# movil, y no tiene por que servir para estimar la reaccion mediana de una
# clase de evento.
#
# Los minimos de abajo son DECLARADOS y conservadores, no estimados: no
# hay todavia ninguna medicion propia que justifique un numero concreto, y
# ponerlo mas bajo "para que salga" seria justo lo que esta regla evita.
MINIMOS_DECLARADOS = {
    "reaccion_mediana_por_clase": 30,
    "reaccion_mediana_condicionada": 50,
}


def suficiencia_de_muestra(observaciones, pregunta="reaccion_mediana_por_clase"):
    """(utilizable, informe). NUNCA devuelve un estadistico.

    Comprueba en este orden -- el mismo que ordena todo el proyecto:
    ¿existe la evidencia? ¿es temporalmente valida? ¿es comparable?
    ¿hay muestra suficiente?
    """
    minimo = MINIMOS_DECLARADOS.get(pregunta)
    if minimo is None:
        return False, {"motivo": "PREGUNTA_NO_DECLARADA", "pregunta": pregunta}

    con_reaccion = [o for o in observaciones if o["raw_return_1s_pct"] is not None]
    sin_solape = [o for o in con_reaccion if not o.get("solapa_con")]
    activos = {o["asset_id"] for o in sin_solape}

    informe = {
        "pregunta": pregunta,
        "minimo_declarado": minimo,
        "eventos_totales": len(observaciones),
        "con_reaccion_medible": len(con_reaccion),
        "sin_solapamiento": len(sin_solape),
        "n_efectivo_activos": len(activos),
        "ajustado_por_mercado": 0,  # ninguno: no hay benchmark
    }
    # Aunque hubiese muestra, el retorno es BRUTO: incluye lo que hiciera
    # el mercado ese dia. Agregar retornos brutos y llamarlos "reaccion al
    # evento" seria atribuir al evento un movimiento que no es suyo.
    if informe["ajustado_por_mercado"] == 0:
        informe["motivo"] = "SIN_RETORNO_ANORMAL: " + SIN_BENCHMARK
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
              f"{'sorpresa%':>10} {'ret bruto%':>11} {'anormal':>8}")
        for o in obs:
            print(f"{o['period_end']:11} {o['published_at']:11} "
                  f"{str(o['report_time']):12} {str(o['first_tradable_at']):13} "
                  f"{o['surprise_pct'] if o['surprise_pct'] is not None else float('nan'):10.2f} "
                  f"{o['raw_return_1s_pct'] if o['raw_return_1s_pct'] is not None else float('nan'):11.2f} "
                  f"{'—':>8}")
    ok, informe = suficiencia_de_muestra(todas)
    print(f"\n=== SUFICIENCIA DE MUESTRA ===\nutilizable: {ok}")
    for k, v in informe.items():
        print(f"  {k}: {v}")
