"""Integridad temporal del Data Contract -- los cinco relojes.

P6.2a (2026-09-07). Este fichero no mide nada nuevo: DECLARA que reloj
lleva de verdad `data_as_of` en cada familia de metrica, y con eso hace
verificable una pregunta que hasta ahora no lo era:

    ¿que informacion estaba REALMENTE disponible en una fecha dada?

El hallazgo que lo motiva. `data_as_of` no significa lo mismo en todas
las filas del contrato:

    tecnico/precio        2026-09-04  = el cierre de esa sesion
    fundamental/eps       2026-06-30  = el fin del trimestre
                                        (publicado el 2026-07-22)
    macro/cpi_yoy_pct     2026-06-01  = el mes que describe
                                        (publicado ~45 dias despues)

Las tres filas usan la misma columna para tres relojes distintos. Es
exactamente el error que el proyecto ya se prohibio a si mismo en P0 con
`source_priority` ("un token se comparte si y solo si significa lo
mismo") y en P6.1 al no introducir `POINT` junto a `KNOWN`.

Por que `available_at` NO es un campo nuevo de METRIC_FIELDS. Mismo
criterio que D-12 para la materialidad: es DERIVADO de la familia de la
metrica y de la semantica declarada de su fuente, no un dato que la
fuente entregue fila a fila. Anadirlo a METRIC_FIELDS tocaria el esquema
que sostienen el cron, los parquet de history/ y Power BI, para guardar
en 500.000 filas un valor que esta tabla calcula. Se deriva, no se
almacena.

REGLA DURA, heredada de cadencias.py: UNKNOWN no es permisivo. Una
observacion cuyo `available_at` no se puede determinar NO es utilizable
en una evaluacion as-of. "No se pudo demostrar cuando se supo" no es
"se supo a tiempo".
"""

import datetime


# --------------------------------------------------------------------------
# Los cinco relojes
# --------------------------------------------------------------------------
# No son sinonimos ni etapas de lo mismo: responden a preguntas distintas
# y pueden separarse meses entre si.
RELOJES = {
    "period_end":   "fin del periodo economico que el dato describe (un trimestre, un mes)",
    "occurred_at":  "cuando ocurrio el hecho",
    "published_at": "cuando la fuente lo hizo publico",
    "available_at": "primer momento en que ESTE sistema podria haberlo conocido",
    "retrieved_at": "cuando este sistema lo descargo de hecho",
}

# Orden que debe cumplirse cuando los relojes existen. No exige que
# existan todos: exige que los que existan no se contradigan.
ORDEN_ESPERADO = ("period_end", "occurred_at", "published_at", "available_at", "retrieved_at")


# --------------------------------------------------------------------------
# Vocabulario de clasificacion
# --------------------------------------------------------------------------
# Cuatro estados que NO son intercambiables. En particular STALE no es un
# LOOK_AHEAD suave: son defectos de signo contrario y convertir uno en
# otro por comodidad esconde el unico que puede falsear un backtest.
CLASIFICACIONES = {
    "SAFE": (
        "`data_as_of` coincide con `available_at` o lo aproxima por exceso: "
        "la fila no puede aportar informacion que no existiese en su fecha."),
    "LOOK_AHEAD": (
        "`data_as_of` es ANTERIOR al momento en que el dato fue conocible. "
        "Filtrar por `data_as_of <= analysis_as_of` deja pasar informacion futura."),
    "STALE": (
        "`data_as_of` no representa la temporalidad economica del valor, pero el "
        "error va en la direccion contraria: la fecha es mas VIEJA que el dato, "
        "asi que el valor parece caducado, no anticipado. No falsea un backtest "
        "hacia el futuro; ensucia la medicion de frescura."),
    "AMBIGUOUS": (
        "la semantica temporal de la fuente no permite determinar `available_at` "
        "con el dato que se descarga. No se resuelve suponiendo."),
}

# Los tres estados que puede devolver la derivacion de available_at.
EXACTO = "EXACTO"                        # la fuente da la fecha de disponibilidad
COTA_CONSERVADORA = "COTA_CONSERVADORA"  # no la da, pero hay un limite defendible
DESCONOCIDO = "DESCONOCIDO"              # no se puede determinar -- no permisivo


class TemporalError(ValueError):
    pass


# --------------------------------------------------------------------------
# Que reloj lleva `data_as_of` en cada familia
# --------------------------------------------------------------------------
# Clave: (domain, metric) o (domain, None) como defecto del dominio.
# Valor: (reloj_real, clasificacion, nota)
#
# Lo que NO esta declarado aqui queda AMBIGUOUS, no SAFE: la ausencia de
# declaracion es ausencia de criterio, igual que en cadencias.py.
SEMANTICA_DATA_AS_OF = {

    # --- tecnico: la fecha de la vela ---------------------------------------
    # El cierre de la sesion D se conoce al terminar la sesion D. Las medias
    # y osciladores de esa fila se calculan con D y anteriores, nunca con
    # posteriores (verificado en engine/technical/indicators.py). Para un
    # sistema que opera con datos de cierre, available_at == data_as_of.
    ("tecnico", None): ("available_at", "SAFE",
        "fecha de la vela; el cierre se conoce al cerrar la sesion"),

    # --- fundamental cripto: snapshot en vivo -------------------------------
    # fecha_dato = detail['last_updated'] de CoinGecko, es decir el momento
    # al que el propio proveedor dice que corresponde el snapshot.
    ("fundamental", "supply_pct_of_max"): ("available_at", "SAFE",
        "snapshot de CoinGecko fechado por la fuente (last_updated)"),
    ("fundamental", "fdv_mcap_ratio"): ("available_at", "SAFE",
        "snapshot de CoinGecko fechado por la fuente (last_updated)"),
    ("fundamental", "market_cap_percentile_365d"): ("available_at", "SAFE",
        "percentil en ventana movil que solo mira hacia atras"),
    ("fundamental", "tvl_percentile_365d"): ("available_at", "SAFE",
        "percentil en ventana movil que solo mira hacia atras"),

    # --- fundamental acciones, GRUPO A: hechos del trimestre reportado ------
    # Corregido el 2026-09-07: antes se fechaban con LatestQuarter
    # (= fiscalDateEnding, el FIN DEL TRIMESTRE) y solo fueron conocibles en
    # reportedDate, entre 22 y 32 dias despues. Ahora llevan reportedDate.
    ("fundamental", "eps"): ("available_at", "SAFE", "reportedDate del trimestre"),
    ("fundamental", "roe_pct"): ("available_at", "SAFE", "reportedDate del trimestre"),
    ("fundamental", "revenue_growth_yoy_pct"): ("available_at", "SAFE", "reportedDate del trimestre"),
    ("fundamental", "profit_margin_pct"): ("available_at", "SAFE", "reportedDate del trimestre"),
    ("fundamental", "operating_margin_pct"): ("available_at", "SAFE", "reportedDate del trimestre"),
    ("fundamental", "earnings_beats_8q"): ("available_at", "SAFE",
        "reportedDate del trimestre MAS RECIENTE de los ocho: un agregado no es "
        "conocible hasta que se conoce su ultimo componente"),
    ("fundamental", "earnings_misses_8q"): ("available_at", "SAFE",
        "reportedDate del trimestre mas reciente de los ocho"),
    ("fundamental", "earnings_surprise_avg_pct"): ("available_at", "SAFE",
        "reportedDate del trimestre mas reciente de los ocho"),
    ("fundamental", "earnings_surprise_last_pct"): ("available_at", "SAFE",
        "reportedDate de su propio trimestre"),

    # --- fundamental acciones, GRUPO B: valores de HOY con fecha de ayer ----
    # Defecto YA REGISTRADO por P1b en cadencias.DEFECTO_DE_FECHADO. Es de
    # signo contrario al anterior: el valor es de hoy y la fecha es del
    # trimestre, asi que sale STALE con decenas de sesiones de retraso. NO
    # se corrige en esta iteracion (decision del usuario, 2026-09-07):
    # corregirlo obliga a re-fechar filas ya escritas para resolver un
    # defecto que no falsea ningun backtest hacia el futuro.
    ("fundamental", "pe_ratio"): ("period_end", "STALE",
        "valor calculado con el precio de hoy, fechado con el trimestre"),
    ("fundamental", "peg_ratio"): ("period_end", "STALE",
        "valor calculado con el precio de hoy, fechado con el trimestre"),
    ("fundamental", "analyst_target_price"): ("period_end", "STALE",
        "consenso vivo de analistas, fechado con el trimestre"),
    ("fundamental", "analyst_upside_pct"): ("period_end", "STALE",
        "consenso vivo de analistas, fechado con el trimestre"),
    ("fundamental", "analyst_n_analistas"): ("period_end", "STALE",
        "consenso vivo de analistas, fechado con el trimestre"),

    # --- macro (FRED): hay que declarar SERIE A SERIE, no por dominio ------
    # No todas tienen retraso de publicacion, y meterlas todas en el mismo
    # saco inflaria el problema en 10.065 filas que no lo son. Dos grupos:
    #
    # (a) Series de PERIODO con retraso real. El IPC de junio se fecha
    #     2026-06-01 y se publica ~45 dias despues. FRED entrega la serie
    #     con la fecha del periodo; la de publicacion vive en ALFRED
    #     (vintages), que este sistema no usa. El available_at exacto NO es
    #     derivable con la fuente actual -- pero la DIRECCION del error si
    #     es cierta y demostrable, y es la peligrosa.
    ("macro", "cpi_yoy_pct"): ("period_end", "LOOK_AHEAD",
        "IPC mensual, publicado ~45 dias despues del periodo que fecha"),
    ("macro", "hicp_yoy_pct"): ("period_end", "LOOK_AHEAD",
        "HICP mensual, publicado ~45 dias despues del periodo que fecha"),
    ("macro", "fed_funds_pct"): ("period_end", "LOOK_AHEAD",
        "media mensual del tipo efectivo, publicada tras cerrar el mes"),
    ("macro", "desempleo_pct"): ("period_end", "LOOK_AHEAD",
        "tasa de paro mensual, publicada tras cerrar el mes"),
    #
    # (b) Series DIARIAS de un valor vigente ese mismo dia. El tipo de
    #     deposito del BCE del dia D es el que rige el dia D y se conoce
    #     ese dia (de hecho se anuncia antes); la pendiente 10a-2a se
    #     publica al cierre de la propia sesion, igual que un precio.
    #     Clasificarlas como las de arriba seria imprecision en la
    #     direccion contraria.
    ("macro", "ecb_deposit_rate_pct"): ("available_at", "SAFE",
        "tipo en vigor ese dia, conocido ese dia"),
    ("macro", "spread_10y2y_pct"): ("available_at", "SAFE",
        "dato de mercado diario, publicado al cierre de la sesion"),
    #
    # Defecto del dominio: conservador. Una serie macro nueva y sin
    # declarar se trata como si tuviese retraso, que es la suposicion
    # segura -- al reves que en el resto del contrato, donde lo no
    # declarado es AMBIGUOUS y bloquea.
    ("macro", None): ("period_end", "LOOK_AHEAD",
        "serie macro sin declaracion propia; se asume retraso de publicacion"),
}

# Retraso de publicacion declarado, en dias, para las series macro. NO es
# una medicion: sale del mismo razonamiento que ya sostiene la cadencia
# declarada en cadencias.py (mensual + retraso de publicacion). Se usa
# SOLO para dar una cota conservadora, nunca como fecha real.
RETRASO_PUBLICACION_DECLARADO = {
    "cpi_yoy_pct": 45,
    "hicp_yoy_pct": 45,
    "fed_funds_pct": 35,
    "ecb_deposit_rate_pct": 1,
    "desempleo_pct": 35,
    "spread_10y2y_pct": 1,
}

# Metricas cuyo defecto de fechado YA estaba registrado antes de esta
# fase. Se importa de cadencias.py en vez de duplicar la lista: si alli
# se corrige, aqui deja de estar sola. La comprobacion de coherencia
# entre las dos tablas la hace comprobar_coherencia_con_cadencias().
def _stale_ya_registradas():
    try:
        import cadencias
        return set(cadencias.DEFECTO_DE_FECHADO)
    except ImportError:
        return set()


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

def semantica(domain, metric):
    """(reloj_real, clasificacion, nota) declarada para esa metrica.

    Lo no declarado es AMBIGUOUS, nunca SAFE."""
    if (domain, metric) in SEMANTICA_DATA_AS_OF:
        return SEMANTICA_DATA_AS_OF[(domain, metric)]
    if (domain, None) in SEMANTICA_DATA_AS_OF:
        return SEMANTICA_DATA_AS_OF[(domain, None)]
    return (None, "AMBIGUOUS", "sin declaracion en SEMANTICA_DATA_AS_OF")


def clasificar(domain, metric):
    return semantica(domain, metric)[1]


def _fecha(v):
    if v is None:
        return None
    if isinstance(v, datetime.date):
        return v
    return datetime.date.fromisoformat(str(v)[:10])


def available_at(row):
    """(fecha, estado) -- DERIVADO, nunca almacenado (mismo criterio que D-12).

    estado es EXACTO, COTA_CONSERVADORA o DESCONOCIDO. El llamante no
    puede tratar los tres igual: solo EXACTO afirma cuando se supo.
    """
    domain, metric = row["domain"], row["metric"]
    reloj, clase, _ = semantica(domain, metric)
    fecha = _fecha(row["data_as_of"])

    if clase == "SAFE":
        return fecha, EXACTO

    if clase == "LOOK_AHEAD" and metric in RETRASO_PUBLICACION_DECLARADO:
        # Cota, no verdad: el dato NO estuvo disponible antes de esto.
        # Puede haberlo estado despues. Sirve para excluir, no para incluir.
        return fecha + datetime.timedelta(days=RETRASO_PUBLICACION_DECLARADO[metric]), COTA_CONSERVADORA

    if clase == "STALE":
        # El valor es de "hoy" y la fecha es vieja: fue conocible en la
        # descarga, no en data_as_of. retrieved_at es la unica cota que
        # tenemos, y es conservadora en la direccion correcta.
        return _fecha(row["retrieved_at"]), COTA_CONSERVADORA

    return None, DESCONOCIDO


def usable_en(row, analysis_as_of, admitir_cota=True):
    """¿Puede esta observacion participar en un analisis fechado en
    `analysis_as_of`?

    Es la comprobacion que `data_as_of <= retrieved_at` NO hace. Una fila
    puede cumplir esa invariante y aun asi ser inutilizable, porque la
    invariante compara la fecha del dato con la de la DESCARGA, no con la
    fecha del analisis.

    DESCONOCIDO nunca es utilizable (regla dura del modulo). Con
    admitir_cota=False tampoco lo es COTA_CONSERVADORA -- el modo que
    exigiria un backtest formal.
    """
    analysis_as_of = _fecha(analysis_as_of)
    fecha, estado = available_at(row)
    if estado == DESCONOCIDO:
        return False, DESCONOCIDO
    if estado == COTA_CONSERVADORA and not admitir_cota:
        return False, COTA_CONSERVADORA
    return fecha <= analysis_as_of, estado


def validar_orden(relojes):
    """Comprueba ORDEN_ESPERADO sobre los relojes presentes. No exige que
    esten todos; exige que los que esten no se contradigan."""
    presentes = [(n, _fecha(relojes[n])) for n in ORDEN_ESPERADO
                 if relojes.get(n) is not None]
    for (n1, f1), (n2, f2) in zip(presentes, presentes[1:]):
        if f1 > f2:
            raise TemporalError(f"{n1} ({f1}) es posterior a {n2} ({f2})")
    return True


def comprobar_coherencia_con_cadencias():
    """Las dos tablas hablan de las mismas metricas y no pueden divergir:
    todo lo que cadencias.py marca como defecto de fechado tiene que estar
    aqui como STALE, y nada mas puede estarlo. Si alguien corrige el
    defecto en un sitio y no en el otro, esto lo dice."""
    registradas = _stale_ya_registradas()
    aqui = {m for (d, m), (_, c, _n) in SEMANTICA_DATA_AS_OF.items() if c == "STALE"}
    if registradas != aqui:
        raise TemporalError(
            f"cadencias.DEFECTO_DE_FECHADO y temporal.SEMANTICA_DATA_AS_OF divergen: "
            f"solo en cadencias={registradas - aqui}, solo aqui={aqui - registradas}")
    return True
