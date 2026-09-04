"""Adaptadores: traducen la salida de cada score_asset()/build_thesis()
existente al Data Contract (schema.py), sin modificar los motores
originales. Un adaptador delgado por motor, tal como se acordo en
docs/03-arquitectura-visualizacion-y-acceso.md.
"""
import hashlib
import json
import os
import sys
from datetime import datetime

from schema import now_utc_iso, SOURCE_PRIORITY

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module(subdir, modname):
    path = os.path.join(ROOT, subdir)
    sys.path.insert(0, path)
    try:
        if modname in sys.modules:
            del sys.modules[modname]
        return __import__(modname)
    finally:
        sys.path.remove(path)


def _row(asset_id, asset_type, domain, metric, value, unit, data_as_of, retrieved_at,
         source, confidence_pct=None, data_quality_pct=None, calculation_method=None, source_url=None):
    return {
        "asset_id": asset_id, "asset_type": asset_type, "domain": domain,
        "metric": metric, "value": value, "unit": unit,
        "data_as_of": data_as_of, "retrieved_at": retrieved_at,
        "source": source, "source_priority": SOURCE_PRIORITY.get(source, 3),
        "confidence_pct": confidence_pct, "data_quality_pct": data_quality_pct,
        "calculation_method": calculation_method, "source_url": source_url,
    }


def adapt_crypto(symbol, tvl_chain):
    """Fase 2 -- engine/crypto/score.py. Snapshot: data_as_of == retrieved_at
    (es un dato en vivo, no una observacion de un periodo pasado)."""
    mod = _load_module("crypto", "score")
    f = mod.score_asset(symbol, tvl_chain)
    retrieved_at = now_utc_iso()
    data_as_of = f["fecha_dato"]
    dq = f["data_quality_pct"]
    method = "engine/crypto/README.md"

    rows = []
    if f["market_cap_percentile_365d"] is not None:
        rows.append(_row(symbol, "crypto", "fundamental", "market_cap_percentile_365d",
                          f["market_cap_percentile_365d"], "%", data_as_of, retrieved_at,
                          "CoinGecko", data_quality_pct=dq, calculation_method=method))
    if f["tvl_percentile_365d"] is not None:
        rows.append(_row(symbol, "crypto", "fundamental", "tvl_percentile_365d",
                          f["tvl_percentile_365d"], "%", data_as_of, retrieved_at,
                          "DefiLlama", data_quality_pct=dq, calculation_method=method))
    if f["fdv_mcap_ratio"] is not None:
        rows.append(_row(symbol, "crypto", "fundamental", "fdv_mcap_ratio",
                          f["fdv_mcap_ratio"], "ratio", data_as_of, retrieved_at,
                          "CoinGecko", data_quality_pct=dq, calculation_method=method))
    if f["supply_pct_of_max"] is not None:
        rows.append(_row(symbol, "crypto", "fundamental", "supply_pct_of_max",
                          f["supply_pct_of_max"], "%", data_as_of, retrieved_at,
                          "CoinGecko", data_quality_pct=dq, calculation_method=method))
    return rows


def adapt_technical(symbol):
    """Fase 3 -- engine/technical/score.py. Snapshot en vivo tambien."""
    mod = _load_module("technical", "score")
    t = mod.score_asset(symbol)
    retrieved_at = now_utc_iso()
    data_as_of = t["fecha_dato"]
    conf = t["confluencia"]["confidence_pct"]
    method = "engine/technical/README.md"

    rows = [
        _row(symbol, "crypto", "tecnico", "precio", t["precio"], "EUR", data_as_of, retrieved_at,
             "Kraken", confidence_pct=conf, calculation_method=method),
    ]
    if t["rsi14"] is not None:
        rows.append(_row(symbol, "crypto", "tecnico", "rsi14", t["rsi14"], "indice", data_as_of, retrieved_at,
                          "Kraken", confidence_pct=conf, calculation_method=method))
    if t["posicion_rango_90d_pct"] is not None:
        rows.append(_row(symbol, "crypto", "tecnico", "posicion_rango_90d_pct",
                          t["posicion_rango_90d_pct"], "%", data_as_of, retrieved_at,
                          "Kraken", confidence_pct=conf, calculation_method=method))
    rows.append(_row(symbol, "crypto", "tecnico", "confluencia_sesgo", t["confluencia"]["sesgo"],
                      "categorico", data_as_of, retrieved_at, "Kraken",
                      confidence_pct=conf, calculation_method=method))

    for sma_key in ("sma20", "sma50", "sma100", "sma200"):
        if t[sma_key] is not None:
            rows.append(_row(symbol, "crypto", "tecnico", sma_key, t[sma_key], "EUR",
                              data_as_of, retrieved_at, "Kraken",
                              confidence_pct=conf, calculation_method=method))
    if t["atr14"] is not None:
        rows.append(_row(symbol, "crypto", "tecnico", "atr14", t["atr14"], "EUR",
                          data_as_of, retrieved_at, "Kraken",
                          confidence_pct=conf, calculation_method=method))
    if t["atr14_pct_precio"] is not None:
        rows.append(_row(symbol, "crypto", "tecnico", "atr14_pct_precio", t["atr14_pct_precio"], "%",
                          data_as_of, retrieved_at, "Kraken",
                          confidence_pct=conf, calculation_method=method))
    if t["volatilidad_hist_30d_anualizada_pct"] is not None:
        rows.append(_row(symbol, "crypto", "tecnico", "volatilidad_hist_30d_anualizada_pct",
                          t["volatilidad_hist_30d_anualizada_pct"], "%", data_as_of, retrieved_at,
                          "Kraken", confidence_pct=conf, calculation_method=method))
    return rows


def adapt_macro():
    """Fase 5 -- engine/macro/score.py. data_as_of por metrica es la
    fecha real del ultimo dato publicado en FRED, no la fecha de
    descarga -- reutiliza historical_series_us()/historical_series_ea()
    (las mismas funciones que usa el backfill, ver
    adapt_macro_backfill() mas abajo), tomando de cada una la fila mas
    reciente. Corregido 2026-09-04: mismo patron de bug ya corregido
    para BTC/XRP el mismo dia (fecha de ejecucion en vez de fecha real
    del dato) -- aqui ademas cpi_yoy_pct/fed_funds_pct (o
    hicp_yoy_pct/ecb_deposit_rate_pct) pueden tener fechas reales
    distintas entre si, por eso ya no comparten un unico fecha_dato."""
    mod = _load_module("macro", "score")
    us, ea = mod.score_us(), mod.score_ea()
    retrieved_at = now_utc_iso()

    # ultima fila de cada metrica (las listas van de mas antigua a mas
    # reciente, asi que un dict quedandose con la ultima ocurrencia da
    # exactamente el punto mas reciente de cada serie).
    us_ultimo = {m: (f, v) for m, f, v in mod.historical_series_us()}
    ea_ultimo = {m: (f, v) for m, f, v in mod.historical_series_ea()}

    rows = [
        _row("US", "macro", "macro", "cpi_yoy_pct", us_ultimo["cpi_yoy_pct"][1], "%",
             us_ultimo["cpi_yoy_pct"][0], retrieved_at, "FRED", data_quality_pct=us["data_quality_pct"],
             calculation_method="engine/macro/README.md"),
        _row("US", "macro", "macro", "fed_funds_pct", us_ultimo["fed_funds_pct"][1], "%",
             us_ultimo["fed_funds_pct"][0], retrieved_at, "FRED", data_quality_pct=us["data_quality_pct"],
             calculation_method="engine/macro/README.md"),
        _row("EA", "macro", "macro", "hicp_yoy_pct", ea_ultimo["hicp_yoy_pct"][1], "%",
             ea_ultimo["hicp_yoy_pct"][0], retrieved_at, "FRED", data_quality_pct=ea["data_quality_pct"],
             calculation_method="engine/macro/README.md"),
        _row("EA", "macro", "macro", "ecb_deposit_rate_pct", ea_ultimo["ecb_deposit_rate_pct"][1], "%",
             ea_ultimo["ecb_deposit_rate_pct"][0], retrieved_at, "FRED", data_quality_pct=ea["data_quality_pct"],
             calculation_method="engine/macro/README.md"),
    ]
    return rows


def adapt_macro_backfill():
    """Backfill historico (2026-09-04) -- FASE DISTINTA de adapt_macro()
    (que solo da "hoy"). Recorre TODA la serie ya descargada de FRED
    (score.py::historical_series_us/ea, misma formula de YoY que ya usa
    el flujo incremental) y produce una fila por fecha real -- no una
    metodologia nueva, solo mas fechas de la que ya existia. NO incluye
    regimen_estimado/señales (eso es sintesis de "hoy", no un dato
    historico por fecha, y no forma parte del Data Contract hoy)."""
    mod = _load_module("macro", "score")
    retrieved_at = now_utc_iso()
    rows = []
    for metric, fecha, valor in mod.historical_series_us():
        rows.append(_row("US", "macro", "macro", metric, valor, "%",
                          fecha, retrieved_at, "FRED",
                          calculation_method="engine/macro/README.md"))
    for metric, fecha, valor in mod.historical_series_ea():
        rows.append(_row("EA", "macro", "macro", metric, valor, "%",
                          fecha, retrieved_at, "FRED",
                          calculation_method="engine/macro/README.md"))
    return rows


def adapt_equity(symbol):
    """Fase 2, Bloque B -- engine/equity/score.py. Aqui SI hay una
    distincion real entre data_as_of y retrieved_at: los ratios
    fundamentales corresponden al ultimo trimestre reportado
    (LatestQuarter de Alpha Vantage), no al momento de la descarga."""
    mod = _load_module("equity", "score")
    e = mod.score_asset(symbol)
    retrieved_at = now_utc_iso()
    dq = e["data_quality_pct"]
    method = "engine/equity/README.md"

    with open(os.path.join(ROOT, "equity", "_data", f"{symbol}_overview.json")) as fh:
        overview = json.load(fh)
    fundamental_as_of = overview.get("LatestQuarter", e["fecha_dato"])
    price_as_of = e["fuente_ultima_cotizacion"]

    rows = [
        _row(symbol, "equity", "tecnico", "precio", e["precio"], "USD",
             price_as_of, retrieved_at, "Alpha Vantage", calculation_method=method),
        _row(symbol, "equity", "tecnico", "posicion_rango_52s_pct", e["posicion_rango_52s_pct"], "%",
             price_as_of, retrieved_at, "Alpha Vantage", calculation_method=method),
        _row(symbol, "equity", "tecnico", "confluencia_sesgo", e["confluencia"]["sesgo"], "categorico",
             price_as_of, retrieved_at, "Alpha Vantage", calculation_method=method),
    ]
    if e["pe_ratio"] is not None:
        rows.append(_row(symbol, "equity", "fundamental", "pe_ratio", e["pe_ratio"], "ratio",
                          fundamental_as_of, retrieved_at, "Alpha Vantage",
                          data_quality_pct=dq, calculation_method=method))
    if e["peg_ratio"] is not None:
        rows.append(_row(symbol, "equity", "fundamental", "peg_ratio", e["peg_ratio"], "ratio",
                          fundamental_as_of, retrieved_at, "Alpha Vantage",
                          data_quality_pct=dq, calculation_method=method))
    rows.append(_row(symbol, "equity", "fundamental", "roe_pct", e["roe_pct"], "%",
                      fundamental_as_of, retrieved_at, "Alpha Vantage",
                      data_quality_pct=dq, calculation_method=method))
    rows.append(_row(symbol, "equity", "fundamental", "revenue_growth_yoy_pct", e["revenue_growth_yoy_pct"], "%",
                      fundamental_as_of, retrieved_at, "Alpha Vantage",
                      data_quality_pct=dq, calculation_method=method))

    # EPS: presente en el overview crudo (Alpha Vantage) pero score.py no lo
    # devuelve todavia -- se lee directamente de overview, mismo patron que
    # adapt_asset_equity ya usa para Sector/Industry/etc. No es un calculo
    # nuevo, es un campo de la fuente que faltaba extraer.
    if overview.get("EPS") not in (None, "None"):
        rows.append(_row(symbol, "equity", "fundamental", "eps", float(overview["EPS"]), "USD",
                          fundamental_as_of, retrieved_at, "Alpha Vantage",
                          data_quality_pct=dq, calculation_method=method))

    rows.append(_row(symbol, "equity", "fundamental", "profit_margin_pct", e["profit_margin_pct"], "%",
                      fundamental_as_of, retrieved_at, "Alpha Vantage",
                      data_quality_pct=dq, calculation_method=method))
    rows.append(_row(symbol, "equity", "fundamental", "operating_margin_pct", e["operating_margin_pct"], "%",
                      fundamental_as_of, retrieved_at, "Alpha Vantage",
                      data_quality_pct=dq, calculation_method=method))

    # Sorpresa de resultados -- ya calculada en score.py sobre los ultimos
    # 8 trimestres de engine/equity/_data/{symbol}_earnings.json.
    sorpresa = e["sorpresa_resultados"]
    rows.append(_row(symbol, "equity", "fundamental", "earnings_beats_8q", sorpresa["ultimos_8_trimestres_beats"],
                      "trimestres", fundamental_as_of, retrieved_at, "Alpha Vantage",
                      data_quality_pct=dq, calculation_method=method))
    rows.append(_row(symbol, "equity", "fundamental", "earnings_misses_8q", sorpresa["ultimos_8_trimestres_misses"],
                      "trimestres", fundamental_as_of, retrieved_at, "Alpha Vantage",
                      data_quality_pct=dq, calculation_method=method))
    if sorpresa["sorpresa_media_pct"] is not None:
        rows.append(_row(symbol, "equity", "fundamental", "earnings_surprise_avg_pct",
                          sorpresa["sorpresa_media_pct"], "%", fundamental_as_of, retrieved_at, "Alpha Vantage",
                          data_quality_pct=dq, calculation_method=method))
    if sorpresa["ultima_sorpresa_pct"] is not None:
        rows.append(_row(symbol, "equity", "fundamental", "earnings_surprise_last_pct",
                          sorpresa["ultima_sorpresa_pct"], "%", fundamental_as_of, retrieved_at, "Alpha Vantage",
                          data_quality_pct=dq, calculation_method=method))

    # Precio objetivo de analistas -- real (AnalystTargetPrice de Alpha
    # Vantage), no inventado. Alpha Vantage no expone una fecha propia para
    # el consenso de analistas, asi que se usa fundamental_as_of como el
    # resto de campos derivados del mismo overview -- aproximacion
    # documentada, no una fecha exacta de cuando se fijo el consenso.
    analistas = e["analistas"]
    if analistas["precio_objetivo"] is not None:
        rows.append(_row(symbol, "equity", "fundamental", "analyst_target_price",
                          analistas["precio_objetivo"], "USD", fundamental_as_of, retrieved_at, "Alpha Vantage",
                          data_quality_pct=dq, calculation_method=method))
    if analistas["upside_pct"] is not None:
        rows.append(_row(symbol, "equity", "fundamental", "analyst_upside_pct",
                          analistas["upside_pct"], "%", fundamental_as_of, retrieved_at, "Alpha Vantage",
                          data_quality_pct=dq, calculation_method=method))
    if analistas["n_analistas"]:
        rows.append(_row(symbol, "equity", "fundamental", "analyst_n_analistas",
                          analistas["n_analistas"], "analistas", fundamental_as_of, retrieved_at, "Alpha Vantage",
                          data_quality_pct=dq, calculation_method=method))
    return rows


def _parse_av_time_published(s):
    """'20260902T213105' (formato de Alpha Vantage NEWS_SENTIMENT) -> ISO UTC."""
    dt = datetime.strptime(s, "%Y%m%dT%H%M%S")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def adapt_news(symbol, asset_type):
    """Fase 4 -- engine/news/. A diferencia de los demas motores, NO hay
    fetch_data.py: NEWS_SENTIMENT de Alpha Vantage solo es invocable desde
    el conector MCP dentro de una sesion de Claude (engine/news/README.md),
    asi que el fichero crudo se guarda a mano en
    engine/news/_data/{symbol}_news_sentiment.json -- mismo patron manual
    que engine/equity/. Si ese fichero no existe (no se ha consultado
    todavia ese activo, por la cuota de 25 llamadas/dia), devuelve [] en
    vez de fallar -- build.py debe poder seguir sin noticias para activos
    no consultados.

    Una fila por (articulo, activo) -- NUNCA se agrega a un promedio
    (a peticion expresa del usuario): sentiment/relevance vienen del
    bloque ticker_sentiment especifico de este activo dentro del
    articulo, mas preciso que el sentimiento general del articulo.
    """
    path = os.path.join(ROOT, "news", "_data", f"{symbol}_news_sentiment.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    sources_mod = _load_module("news", "sources")
    with open(os.path.join(ROOT, "news", "personas_influyentes.json"), encoding="utf-8") as fh:
        personas = {p["nombre"] for p in json.load(fh)["personas"]}

    ticker_key = f"CRYPTO:{symbol}" if asset_type == "crypto" else symbol
    retrieved_at = now_utc_iso()

    rows = []
    for article in raw.get("feed", []):
        ts = next((t for t in article.get("ticker_sentiment", []) if t.get("ticker") == ticker_key), None)
        if ts is None:
            continue  # el articulo salio en la busqueda pero no menciona este ticker directamente
        news_id = hashlib.sha1(article["url"].encode("utf-8")).hexdigest()[:16]
        # coincidencia con personas_influyentes.json: credibilidad ganada,
        # no asumida (engine/news/README.md) -- solo se anota el nombre si
        # de verdad aparece como autor, nunca se infiere.
        autor_conocido = next((a for a in article.get("authors", []) if a in personas), None)
        rows.append({
            "news_id": news_id,
            "asset_id": symbol,
            "asset_type": asset_type,
            "data_as_of": _parse_av_time_published(article["time_published"]),
            "retrieved_at": retrieved_at,
            "source": article.get("source"),
            "source_domain": article.get("source_domain"),
            "source_priority": sources_mod.tier_for_domain(article.get("source_domain", "")),
            "headline": article.get("title"),
            "summary": article.get("summary"),
            "url": article["url"],
            "sentiment": float(ts["ticker_sentiment_score"]),
            "sentiment_label": ts.get("ticker_sentiment_label"),
            "relevance": float(ts["relevance_score"]),
            "persona_influyente": autor_conocido,
        })
    return rows


def adapt_thesis(thesis, asset_type):
    """Motor de Razonamiento (Fase 7) -- engine/reasoning/thesis.py, tanto
    build_thesis() (cripto) como build_thesis_equity() (acciones)."""
    retrieved_at = now_utc_iso()
    return {
        "thesis_id": f"{thesis['activo']}_{thesis['fecha']}_{retrieved_at}",
        "asset_id": thesis["activo"],
        "thesis_type": asset_type,
        "bull_case": thesis["bull_case"],
        "base_case": thesis["base_case"],
        "bear_case": thesis["bear_case"],
        "contradictions": thesis["contradicciones"],
        "convergences": thesis["convergencias"],
        "divergences": thesis["divergencias"],
        "invalidation_factors": thesis["factores_que_invalidarian_la_tesis"],
        "confidence_pct": thesis["confidence_pct"],
        "data_as_of": thesis["fecha"],
        "retrieved_at": retrieved_at,
    }


def adapt_asset_macro(region):
    """DimAsset para las 'pseudo-cuentas' macro (US, EA) -- para que
    FactMetrics[asset_id] siempre tenga una fila DimAsset correspondiente
    y no queden relaciones huerfanas en el modelo de Power BI."""
    names = {"US": "Estados Unidos", "EA": "Eurozona"}
    currencies = {"US": "USD", "EA": "EUR"}
    return {
        "asset_id": region,
        "asset_type": "macro",
        "name": names.get(region, region),
        "sector": None,
        "industry": None,
        "country": None,
        "currency": currencies.get(region),
        "exchange": None,
        "active": True,
        "retrieved_at": now_utc_iso(),
        "source": "FRED",
    }


def adapt_asset_crypto(symbol):
    """DimAsset para criptomonedas, a partir del detalle de CoinGecko ya
    descargado (engine/crypto/_data/{symbol}_detail.json).

    Proveniencia por campo (importante, no todo viene de la fuente):
    - name: extraido literalmente de CoinGecko ('name').
    - sector: NO existe un campo limpio equivalente en CoinGecko (la
      lista 'categories' es ruidosa e inconsistente -- para BTC incluye
      'Smart Contract Platform', que no es correcto). Se ASIGNA la
      etiqueta fija 'Cripto' en vez de usar esa lista, documentado aqui
      como decision explicita, no como dato extraido.
    - country: extraido de 'country_origin' solo si no viene vacio (para
      la mayoria de criptomonedas grandes viene vacio -- no se inventa
      un valor como 'Global').
    - currency: 'EUR' -- es la divisa en la que ESTE SISTEMA expresa el
      precio (viene de los pares EUR de Kraken en engine/technical/), no
      una propiedad inherente de la criptomoneda.
    - exchange: None -- no aplica, cotiza en muchos mercados a la vez.
    """
    with open(os.path.join(ROOT, "crypto", "_data", f"{symbol}_detail.json")) as fh:
        detail = json.load(fh)
    country = detail.get("country_origin") or None
    return {
        "asset_id": symbol,
        "asset_type": "crypto",
        "name": detail.get("name"),
        "sector": "Cripto",
        "industry": None,
        "country": country,
        "currency": "EUR",
        "exchange": None,
        "active": True,
        "retrieved_at": now_utc_iso(),
        "source": "CoinGecko",
    }


def adapt_asset_equity(symbol):
    """DimAsset para acciones -- todos los campos extraidos literalmente
    de Alpha Vantage COMPANY_OVERVIEW (engine/equity/_data/{symbol}_overview.json),
    sin ninguna etiqueta asignada por este sistema."""
    with open(os.path.join(ROOT, "equity", "_data", f"{symbol}_overview.json")) as fh:
        overview = json.load(fh)
    return {
        "asset_id": symbol,
        "asset_type": "equity",
        "name": overview.get("Name"),
        "sector": overview.get("Sector"),
        "industry": overview.get("Industry"),
        "country": overview.get("Country"),
        "currency": overview.get("Currency"),
        "exchange": overview.get("Exchange"),
        "active": True,
        "retrieved_at": now_utc_iso(),
        "source": "Alpha Vantage",
    }
