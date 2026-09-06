"""metrics -> Evidence y news -> Evidence. P3 (2026-09-06).

Los dos adaptadores son de SOLO LECTURA sobre sus fuentes: no escriben en
data/, no tocan el Data Contract, no modifican Knowledge y no consultan
los cinco motores. Evidence se genera, se mide y se tira.

DECISIONES QUE ESTOS ADAPTADORES NO TOMAN
-----------------------------------------
- No inventan confidence. Los dos unicos numeros de calidad que existen
  vienen de la fila de origen y viajan con nombre de origen
  (origin_confidence_pct, origin_data_quality_pct).
- No convierten relevance en confidence. relevance es "cuanto habla este
  articulo de esta entidad", no "cuanto nos fiamos".
- No unifican escalas de procedencia: cada fila lleva su source_rank Y el
  nombre de la escala a la que pertenece.
- No convierten una noticia en Event.
- No emiten nature=INFERRED. Esta en el vocabulario para P5.
"""
import datetime
import glob
import json
import os
import sys

import esquema

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NEWS_DIR = os.path.join(ROOT, "data", "news")


def _mod(subdir, modname):
    """Importa un modulo de otro paquete de engine/ SIN reimportarlo si ya
    esta cargado.

    adapters.py usa el patron contrario -- borra de sys.modules para
    forzar una importacion limpia -- porque los cinco motores tienen un
    modulo `score` cada uno y hay que quedarse con el del directorio
    correcto. Aqui los nombres (`storage`, `modelo`) son unicos en el
    proyecto, y borrarlos de sys.modules destruye el estado de quien ya
    los tuviera importados: las pruebas de compactacion redirigen los
    directorios de storage y una reimportacion se los devuelve a los
    reales sin avisar. Ese fallo aparecio de verdad al escribir P3.
    """
    if modname in sys.modules:
        return sys.modules[modname]
    path = os.path.join(ROOT, "engine", subdir)
    sys.path.insert(0, path)
    try:
        return __import__(modname)
    finally:
        sys.path.remove(path)


# --- Puentes con P2 --------------------------------------------------------

def indice_entidades():
    """asset_id -> entity_id, resuelto contra knowledge/. No crea nada: si
    un asset_id no resuelve, la fila se registra como no resuelta."""
    kn = _mod("knowledge", "modelo")
    idx = {}
    for e in kn.cargar()["entities"]:
        if e.get("asset_id"):
            idx[e["asset_id"]] = e["entity_id"]
    return idx


# Metricas que implementan un concepto declarado en knowledge/concepts/.
# Las 36 restantes no tienen concepto y su concept_id es null: declarar un
# concepto vacio seria peor que no declararlo.
CONCEPTO_DE_METRICA = {
    "cpi_yoy_pct": "inflation_yoy",
    "hicp_yoy_pct": "inflation_yoy",
    "fed_funds_pct": "policy_rate",
    "ecb_deposit_rate_pct": "policy_rate",
    "posicion_rango_90d_pct": "percentil_en_ventana",
    "posicion_rango_52s_pct": "percentil_en_ventana",
    "market_cap_percentile_365d": "percentil_en_ventana",
    "tvl_percentile_365d": "percentil_en_ventana",
}

# --- Declaraciones por metrica ---------------------------------------------

# Leido de la fuente sin transformarlo.
MEASURED = {
    "precio", "volumen",
    "eps", "revenue_growth_yoy_pct", "profit_margin_pct", "operating_margin_pct",
    "roe_pct", "earnings_beats_8q", "earnings_misses_8q",
    "earnings_surprise_avg_pct", "earnings_surprise_last_pct",
    "analyst_target_price", "analyst_n_analistas",
    "fed_funds_pct", "ecb_deposit_rate_pct",
}

# Derivadas de OTRA fila de Evidence que existe: el precio de la misma
# entidad, la misma fecha y la misma fuente. Son las unicas para las que
# derived_from se puede resolver de verdad.
DERIVADAS_DEL_PRECIO = {
    "sma20": "media movil simple de 20 sesiones sobre el precio de cierre",
    "sma50": "media movil simple de 50 sesiones sobre el precio de cierre",
    "sma100": "media movil simple de 100 sesiones sobre el precio de cierre",
    "sma200": "media movil simple de 200 sesiones sobre el precio de cierre",
    "rsi14": "RSI de 14 periodos sobre el precio de cierre",
    "atr14": "ATR de 14 periodos sobre el rango real",
    "atr14_pct_precio": "ATR14 expresado como porcentaje del precio",
    "volatilidad_hist_30d_anualizada_pct": "desviacion tipica de 30 sesiones, anualizada",
    "posicion_rango_90d_pct": "posicion del precio dentro de su rango de 90 dias",
    "posicion_rango_52s_pct": "posicion del precio dentro de su rango de 52 semanas",
    "confluencia_sesgo": "confluencia de las senales tecnicas del activo",
}

# Derivadas cuyo insumo NO esta en el Data Contract: se declara el metodo
# y derived_from queda VACIO. Decir "derivada de algo que no puedo
# senalar" es mas honesto que apuntar a una fila que no existe.
DERIVADAS_SIN_INSUMO = {
    "cpi_yoy_pct": "variacion interanual del indice CPIAUCSL de FRED (el indice no esta en el contrato)",
    "hicp_yoy_pct": "variacion interanual del indice HICP de la Eurozona en FRED (idem)",
    "market_cap_percentile_365d": "percentil de la capitalizacion en ventana movil de 365 dias",
    "tvl_percentile_365d": "percentil del TVL en ventana movil de 365 dias",
    "fdv_mcap_ratio": "cociente entre valoracion totalmente diluida y capitalizacion",
    "supply_pct_of_max": "oferta circulante como porcentaje de la oferta maxima",
    "pe_ratio": "cociente entre precio y beneficio por accion",
    "peg_ratio": "PER dividido por el crecimiento esperado",
    "analyst_upside_pct": "recorrido implicito entre precio objetivo y precio actual",
}

# Granularidad DECLARADA, no inferida de la cadencia: la cadencia dice
# cada cuanto se publica, la granularidad a que periodo se refiere el
# dato. Un dato trimestral publicado cada dia seguiria siendo trimestral.
GRANULARIDAD = {
    "cpi_yoy_pct": "MONTH", "hicp_yoy_pct": "MONTH", "fed_funds_pct": "MONTH",
    "eps": "QUARTER", "revenue_growth_yoy_pct": "QUARTER",
    "profit_margin_pct": "QUARTER", "operating_margin_pct": "QUARTER",
    "roe_pct": "QUARTER", "earnings_beats_8q": "QUARTER",
    "earnings_misses_8q": "QUARTER", "earnings_surprise_avg_pct": "QUARTER",
    "earnings_surprise_last_pct": "QUARTER",
}
GRANULARIDAD_POR_DEFECTO = "DAY"


def _ev_id_metrica(asset_id, domain, metric, occurred_at, source):
    """Determinista: la misma fila de origen produce siempre el mismo id.
    Es la clave logica del contrato, que ya es unica (507.330 filas =
    507.330 claves, medido en P0)."""
    return f"ev:met:{asset_id}:{domain}:{metric}:{occurred_at}:{source}"


def adaptar_metrica(row, entity_id):
    """Una fila del Data Contract -> una fila de Evidence. 1:1."""
    metric = row["metric"]
    occurred = row["data_as_of"].isoformat() if hasattr(row["data_as_of"], "isoformat") else row["data_as_of"]
    known = row["retrieved_at"].isoformat() if hasattr(row["retrieved_at"], "isoformat") else row["retrieved_at"]

    if metric in DERIVADAS_DEL_PRECIO:
        nature, method = "DERIVED", DERIVADAS_DEL_PRECIO[metric]
        derived = [_ev_id_metrica(row["asset_id"], row["domain"], "precio", occurred, row["source"])]
    elif metric in DERIVADAS_SIN_INSUMO:
        nature, method, derived = "DERIVED", DERIVADAS_SIN_INSUMO[metric], []
    elif metric in MEASURED:
        nature, method, derived = "MEASURED", None, []
    else:
        # Sin declaracion no se adivina: una metrica nueva que nadie haya
        # clasificado no puede pasar por medida.
        nature, method, derived = "DERIVED", None, []

    return {
        "evidence_id": _ev_id_metrica(row["asset_id"], row["domain"], metric, occurred, row["source"]),
        "entity_id": entity_id,
        "entity_role": "SUBJECT",
        "claim_type": "OBSERVATION",
        "domain": row["domain"],
        "metric": metric,
        "concept_id": CONCEPTO_DE_METRICA.get(metric),
        "value_num": row.get("value"),
        "value_text": row.get("value_text"),
        "unit": row.get("unit"),
        "occurred_at": occurred,
        "known_at": known,
        "granularity": GRANULARIDAD.get(metric, GRANULARIDAD_POR_DEFECTO),
        "source": row["source"],
        "source_scale": "market_data_priority",
        "source_rank": row["source_priority"],
        "source_ref": row.get("source_url"),
        "nature": nature,
        # method: que se hizo. method_ref: donde esta documentado, que es
        # lo unico que el contrato guarda. Ver esquema.py.
        "method": method,
        "method_ref": row.get("calculation_method"),
        "derived_from": derived,
        "relevance": None,
        "headline": None,
        "summary": None,
        "origin_confidence_pct": row.get("confidence_pct"),
        "origin_data_quality_pct": row.get("data_quality_pct"),
    }


def reconstruir_metrica(ev, asset_type):
    """Evidence + DimAsset -> la fila original del contrato.

    asset_type no viaja en Evidence porque es un atributo ESTATICO del
    activo y su sitio es DimAsset, que sigue siendo la dimension
    (decision aprobada, no se migra asset_id). La reconstruccion es por
    tanto Evidence + DimAsset, no Evidence sola, y eso se declara en vez
    de disimularlo duplicando la columna."""
    _, _, asset_id, domain, metric, occurred, source = ev["evidence_id"].split(":", 6)
    return {
        "asset_id": asset_id, "asset_type": asset_type, "domain": domain,
        "metric": metric, "value": ev["value_num"], "value_text": ev["value_text"],
        "unit": ev["unit"], "data_as_of": datetime.date.fromisoformat(ev["occurred_at"]),
        "retrieved_at": ev["known_at"], "source": source,
        "source_priority": ev["source_rank"],
        "confidence_pct": ev["origin_confidence_pct"],
        "data_quality_pct": ev["origin_data_quality_pct"],
        "calculation_method": ev["method_ref"], "source_url": ev["source_ref"],
    }


# --- Noticias --------------------------------------------------------------

# Regla DECLARADA, no un clasificador. Distinguir "este medio informa de
# un hecho" de "este medio opina" exige analisis de contenido, que P3
# deliberadamente no hace. El unico caso clasificable sin leer el texto es
# aquel en el que el publicador ES el actor del hecho: un regulador
# publicando su propio acto (tier 1 de news/sources.py). Todo lo demas es
# una afirmacion de ese medio hasta que se corrobore.
TIER_PRIMARIO = 1


def adaptar_noticia(art, entity_id):
    """Un articulo -> DOS filas de Evidence.

    Dos y no una porque el score y su etiqueta son dos observaciones
    distintas y value_num XOR value_text no admite meterlas en la misma
    fila. Ademas la etiqueta es una bucketizacion del score hecha por la
    propia fuente, asi que su derived_from apunta al score: es el unico
    caso de P3 donde una derivacion se puede resolver dentro de las
    noticias.
    """
    claim = "OBSERVATION" if art.get("source_priority") == TIER_PRIMARIO else "ASSERTION"
    base = {
        "entity_id": entity_id,
        "entity_role": "MENTIONED",
        "claim_type": claim,
        "domain": "noticias",
        "concept_id": None,
        "unit": None,
        "occurred_at": art["data_as_of"],
        "known_at": art["retrieved_at"],
        "granularity": "INSTANT",
        "source": art["source"],
        "source_scale": "journalistic_tier",
        "source_rank": art["source_priority"],
        "source_ref": art.get("url"),
        "nature": "DERIVED",
        # relevance NO es confidence: mide cuanto habla el articulo de
        # esta entidad, no cuanto nos fiamos de el.
        "relevance": art.get("relevance"),
        "headline": art.get("headline"),
        "summary": art.get("summary"),
        "origin_confidence_pct": None,
        "origin_data_quality_pct": None,
    }
    id_score = f"ev:news:{art['asset_id']}:{art['news_id']}:news_sentiment"
    fila_score = dict(base, evidence_id=id_score, metric="news_sentiment",
                      value_num=art.get("sentiment"), value_text=None,
                      method="ticker_sentiment_score de Alpha Vantage NEWS_SENTIMENT, "
                             "especifico de esta entidad y no el sentimiento general del articulo",
                      method_ref=None, derived_from=[])
    fila_label = dict(base,
                      evidence_id=f"ev:news:{art['asset_id']}:{art['news_id']}:news_sentiment_label",
                      metric="news_sentiment_label", value_num=None,
                      value_text=art.get("sentiment_label"),
                      method="bucketizacion del score hecha por Alpha Vantage",
                      method_ref=None, derived_from=[id_score])
    return [fila_score, fila_label]


# --- Generacion ------------------------------------------------------------

def evidencia_de_metricas(asset_ids=None, limite=None, con_history=True):
    """Generador, activo por activo. No materializa nada: quien quiera un
    fichero, que lo pida explicitamente.

    derived_from se resuelve DENTRO del activo, que es la unidad natural:
    un indicador tecnico se calcula sobre el precio del mismo activo, la
    misma fecha y la misma fuente. Si esa fila de precio no existe de
    verdad -- porque el indicador vino de una fuente y el precio de otra,
    o porque el contrato no la tiene -- la referencia NO se escribe. Una
    trazabilidad que apunta a algo inexistente es peor que declarar que
    no se puede trazar: el metodo queda igualmente documentado en
    `method`.
    """
    st = _mod("contract", "storage")
    idx = indice_entidades()
    activos = asset_ids or sorted(set(st.assets_en_incoming()) | set(st.assets_en_history()))
    n = 0
    for a in activos:
        eid = idx.get(a)
        if eid is None:
            continue
        tipo = st.asset_type_of(a)
        filas = st.all_layers(tipo, a) if con_history else st.read_incoming_rows(a)
        adaptadas = [adaptar_metrica(r, eid) for r in st.resolve(filas)]
        existentes = {e["evidence_id"] for e in adaptadas}
        for e in adaptadas:
            colgando = [d for d in e["derived_from"] if d not in existentes]
            if colgando:
                e["derived_from"] = [d for d in e["derived_from"] if d in existentes]
            yield e
            n += 1
            if limite and n >= limite:
                return


def evidencia_de_noticias():
    """Devuelve (filas, no_resueltas). Una entidad que no resuelve NO se
    crea en silencio: se registra."""
    idx = indice_entidades()
    filas, no_resueltas = [], []
    for p in sorted(glob.glob(os.path.join(NEWS_DIR, "*.json"))):
        with open(p, encoding="utf-8") as f:
            arts = json.load(f)
        for art in arts:
            eid = idx.get(art["asset_id"])
            if eid is None:
                no_resueltas.append({"asset_id": art["asset_id"], "news_id": art["news_id"],
                                     "motivo": "asset_id no resuelve a ninguna entidad de knowledge/"})
                continue
            filas += adaptar_noticia(art, eid)
    return filas, no_resueltas


def activos_no_resueltos():
    """Metricas cuyo asset_id no resuelve a una entidad."""
    st = _mod("contract", "storage")
    idx = indice_entidades()
    todos = sorted(set(st.assets_en_incoming()) | set(st.assets_en_history()))
    return [a for a in todos if a not in idx]
