"""Cadencia esperada y conjunto esperado de metricas -- DECLARACION.

P1b (2026-09-06). Este fichero no mide nada: declara. Es la mitad del
trabajo que ninguna medicion puede hacer por si sola.

Por que declarar y no inferir la cadencia de la propia serie: una serie
parada se autodeclararia sana. Si el IPC lleva tres meses sin publicarse,
el hueco mediano observado es de tres meses y la serie parece puntual.
La cadencia tiene que venir de como publica la fuente, no de lo que la
serie hizo.

Por que la cadencia es (unidad, n) y no un numero de dias: el 2026-09-06,
un sabado, IBM llevaba dos dias naturales sin dato y cero sesiones sin
dato -- su ultimo cierre era el viernes. Medido en dias naturales sale
retrasado; medido en sesiones esta al dia. El proyecto ya resolvio esto
para la deteccion de huecos (engine/technical/trading_calendar.py) y
aqui se reutiliza sin tocarlo.

Por que la unidad "sesion" tambien se usa en cripto: sessions_skipped_between()
con asset_type="crypto" cuenta todos los dias naturales (mercado 24/7),
asi que la misma declaracion sirve para los dos tipos de activo sin
duplicar tablas.

REGLA DURA: lo que no esta declarado aqui queda en UNKNOWN, y UNKNOWN
NO es un estado permisivo. "No se pudo determinar la frescura" no es
"la frescura es correcta".
"""

SESION = "sesion"
DIA = "dia"

# Clave: (dominio, metrica). La metrica None es el comodin del dominio.
# El valor es (unidad, n): se considera FRESH hasta n, LAGGING hasta 2n,
# STALE a partir de ahi.
CADENCIAS = {
    # --- tecnico: todas las metricas se recalculan con cada vela ---
    ("tecnico", None): (SESION, 1),

    # --- fundamental de cripto: CoinGecko y DefiLlama publican a diario ---
    ("fundamental", "market_cap_percentile_365d"): (SESION, 1),
    ("fundamental", "fdv_mcap_ratio"): (SESION, 1),
    ("fundamental", "supply_pct_of_max"): (SESION, 1),
    ("fundamental", "tvl_percentile_365d"): (SESION, 1),

    # --- fundamental de acciones, bloque TRIMESTRAL ---
    # 92 dias de trimestre + ~45 de retraso de publicacion. Un dato de
    # 68 dias NO esta caduco aqui: es que la empresa todavia no ha
    # reportado el trimestre siguiente.
    ("fundamental", "eps"): (DIA, 137),
    ("fundamental", "revenue_growth_yoy_pct"): (DIA, 137),
    ("fundamental", "profit_margin_pct"): (DIA, 137),
    ("fundamental", "operating_margin_pct"): (DIA, 137),
    ("fundamental", "roe_pct"): (DIA, 137),
    ("fundamental", "earnings_beats_8q"): (DIA, 137),
    ("fundamental", "earnings_misses_8q"): (DIA, 137),
    ("fundamental", "earnings_surprise_avg_pct"): (DIA, 137),
    ("fundamental", "earnings_surprise_last_pct"): (DIA, 137),

    # --- fundamental de acciones, bloque DIARIO ---
    # Estas cinco NO son trimestrales aunque hoy se escriban con la
    # fecha del trimestre (ver DEFECTO_DE_FECHADO abajo): dependen del
    # precio de hoy o del consenso vivo de analistas.
    ("fundamental", "pe_ratio"): (SESION, 1),
    ("fundamental", "peg_ratio"): (SESION, 1),
    ("fundamental", "analyst_target_price"): (SESION, 1),
    ("fundamental", "analyst_upside_pct"): (SESION, 1),
    ("fundamental", "analyst_n_analistas"): (SESION, 1),

    # --- macro: cada serie de FRED tiene su propio calendario ---
    # IPC/HICP: mensual + ~45 dias de retraso de publicacion.
    ("macro", "cpi_yoy_pct"): (DIA, 75),
    ("macro", "hicp_yoy_pct"): (DIA, 75),
    # Fed funds: mensual + ~35 dias.
    ("macro", "fed_funds_pct"): (DIA, 65),
    # Tipo de deposito del BCE: serie diaria.
    ("macro", "ecb_deposit_rate_pct"): (SESION, 1),
}

# Metricas que el sistema deberia tener para cada (tipo de activo, dominio).
# Sin esta declaracion, PARTIAL no es calculable: "faltan metricas"
# exige saber cuales se esperaban.
ESPERADAS = {
    ("crypto", "fundamental"): frozenset({
        "market_cap_percentile_365d", "fdv_mcap_ratio", "supply_pct_of_max",
        "tvl_percentile_365d"}),
    ("crypto", "tecnico"): frozenset({
        "precio", "volumen", "rsi14", "atr14", "atr14_pct_precio",
        "sma20", "sma50", "sma100", "sma200",
        "volatilidad_hist_30d_anualizada_pct", "posicion_rango_90d_pct",
        "confluencia_sesgo"}),
    ("equity", "fundamental"): frozenset({
        "eps", "pe_ratio", "peg_ratio", "roe_pct", "profit_margin_pct",
        "operating_margin_pct", "revenue_growth_yoy_pct",
        "earnings_beats_8q", "earnings_misses_8q",
        "earnings_surprise_avg_pct", "earnings_surprise_last_pct",
        "analyst_target_price", "analyst_upside_pct", "analyst_n_analistas"}),
    ("equity", "tecnico"): frozenset({
        "precio", "volumen", "rsi14", "atr14", "atr14_pct_precio",
        "sma20", "sma50", "sma100", "sma200",
        "volatilidad_hist_30d_anualizada_pct", "posicion_rango_52s_pct",
        "confluencia_sesgo"}),
}

# Excepcion por activo, no por tipo. EE.UU. y la Eurozona no comparten
# NI UNA metrica (interseccion medida = 0): cpi_yoy_pct/fed_funds_pct
# frente a hicp_yoy_pct/ecb_deposit_rate_pct. Son los mismos dos
# conceptos con cuatro nombres, y hasta que exista la capa CONCEPT (P2)
# no hay forma de declararlos como un unico conjunto esperado sin
# marcar a las dos regiones como incompletas para siempre.
ESPERADAS_POR_ACTIVO = {
    ("US", "macro"): frozenset({"cpi_yoy_pct", "fed_funds_pct"}),
    ("EA", "macro"): frozenset({"hicp_yoy_pct", "ecb_deposit_rate_pct"}),
}

# Ausencias COMPROBADAS que no son huecos. Sin esta tabla, las tres
# ausencias de tvl_percentile_365d (BTC, XRP, DOT) son la misma casilla
# vacia teniendo causas que no se parecen en nada.
#
# DOT no esta aqui a proposito: su TVL falta por una incidencia real de
# la fuente (DefiLlama reporta 0 en toda la serie de Polkadot), no
# porque la metrica no aplique. Debe contar como hueco.
NO_APLICA = {
    ("BTC", "fundamental", "tvl_percentile_365d"):
        "Bitcoin no tiene TVL de DeFi en el sentido que mide DefiLlama "
        "(engine/crypto/fetch_data.py: tvl_chain None)",
    ("XRP", "fundamental", "tvl_percentile_365d"):
        "El XRP Ledger tiene DeFi marginal y no se solicita cadena a "
        "DefiLlama (engine/crypto/fetch_data.py: tvl_chain None)",
}

# Registrado, no corregido (P1, 2026-09-06): adapters.py::adapt_equity
# escribe estas cinco metricas con fundamental_as_of (LatestQuarter) en
# vez de con price_as_of, aunque dependen del precio del dia. Por eso
# salen STALE con decenas de sesiones de retraso: el dato es de hoy y
# la fecha es del trimestre. La cadencia declarada arriba es la correcta
# (diaria); lo que esta mal es la fecha con la que se escriben.
DEFECTO_DE_FECHADO = frozenset({
    "pe_ratio", "peg_ratio", "analyst_target_price", "analyst_upside_pct",
    "analyst_n_analistas"})


def cadencia(domain, metric):
    """(unidad, n) declarada, o None si no hay declaracion -> UNKNOWN."""
    if (domain, metric) in CADENCIAS:
        return CADENCIAS[(domain, metric)]
    return CADENCIAS.get((domain, None))


def esperadas(asset_id, asset_type, domain):
    """Conjunto declarado de metricas, o None si no hay declaracion."""
    if (asset_id, domain) in ESPERADAS_POR_ACTIVO:
        return ESPERADAS_POR_ACTIVO[(asset_id, domain)]
    return ESPERADAS.get((asset_type, domain))


def no_aplica(asset_id, domain, metric):
    """Motivo declarado por el que la metrica no aplica, o None."""
    return NO_APLICA.get((asset_id, domain, metric))
