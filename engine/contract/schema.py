"""Data Contract -- capa de visualizacion (docs/03-arquitectura-visualizacion-y-acceso.md).

Define la forma comun que va a usar tanto la futura Web App como Power
BI, para que ambos lean el mismo arbol de datos sin logica duplicada.
Dos niveles: METRIC_FIELDS (una fila por observacion) y THESIS_FIELDS
(una fila por tesis generada). Ver el documento de arquitectura para la
justificacion de cada campo -- en particular por que data_as_of y
retrieved_at van por separado (para evitar look-ahead bias en un futuro
backtesting, Fase 8).

Regla de privacidad (no negociable, ver docs/03): ninguno de estos dos
niveles puede contener cantidades ni importes de cartera/. Solo datos de
mercado y de analisis. Ver FORBIDDEN_KEYS mas abajo.
"""
import datetime

# value_text es el desdoble del campo categorico que docs/04-modelo-power-bi.md
# ya habia decidido ("value es texto en algunas filas y numerico en otras -- no
# fuerces un tipo unico"). Con el almacenamiento tipado (history/ en parquet)
# esa decision deja de ser una recomendacion para Power Query y pasa a ser
# estructural: value es numerico, value_text guarda la etiqueta categorica.
# Es opcional -- las filas numericas, que son el 99,997%, lo dejan a None.
METRIC_FIELDS = {
    "asset_id", "asset_type", "domain", "metric", "value", "value_text", "unit",
    "data_as_of", "retrieved_at", "source", "source_priority",
    "confidence_pct", "data_quality_pct", "calculation_method", "source_url",
}

# evidence_validity / evidence (P1, 2026-09-06): una tesis ya no publica
# solo su conclusion, tambien de que evidencia depende y en que estado
# estaba esa evidencia cuando se razono. Sin esto, confidence_pct = None
# no se podria distinguir de "el motor no supo calcularla".
THESIS_FIELDS = {
    "thesis_id", "asset_id", "thesis_type", "bull_case", "base_case", "bear_case",
    "contradictions", "convergences", "divergences", "invalidation_factors",
    "confidence_pct", "evidence_validity", "evidence", "data_as_of", "retrieved_at",
}

VALIDEZ_EVIDENCIA = ("VALID", "INVALID", "UNKNOWN")

# DimAsset -- atributos ESTATICOS del activo (no cambian dia a dia, por
# eso no se historizan como las metricas). Algunos campos son un dato
# extraido literalmente de la fuente (ej. "Sector" de Alpha Vantage para
# acciones), otros son una etiqueta ASIGNADA por este sistema porque la
# fuente no tiene un equivalente limpio (ej. "sector" = "Cripto" para
# criptomonedas) -- documentado explicitamente en cada adaptador, el
# campo "source" de la fila no distingue esto campo a campo.
ASSET_FIELDS = {
    "asset_id", "asset_type", "name", "sector", "industry", "country",
    "currency", "exchange", "active", "retrieved_at", "source",
}

# FactNews -- una fila por (articulo, activo mencionado). NO se agrega a
# un promedio: cada noticia individual se conserva, para que Power BI
# pueda analizar despues volumen/sentimiento/relevancia/fuente por
# separado (a peticion expresa del usuario). "sentiment"/"relevance" son
# especificos del activo dentro del articulo (Alpha Vantage los da por
# ticker, no solo a nivel de articulo completo) -- mas preciso que el
# sentimiento general del articulo.
NEWS_FIELDS = {
    "news_id", "asset_id", "asset_type", "data_as_of", "retrieved_at",
    "source", "source_domain", "source_priority", "headline", "summary",
    "url", "sentiment", "sentiment_label", "relevance", "persona_influyente",
}

# Requeridos de verdad (el resto puede ser None si el motor de origen no lo tiene)
# value NO esta aqui: una fila lleva value (numerica) O value_text
# (categorica), y la exclusividad se comprueba aparte en
# validate_metric_row(). Exigir "value" a secas dejaria fuera las filas
# categoricas; no exigir ninguno de los dos permitiria una fila sin dato.
METRIC_REQUIRED = {"asset_id", "asset_type", "domain", "metric", "data_as_of", "retrieved_at", "source", "source_priority"}
THESIS_REQUIRED = {"thesis_id", "asset_id", "thesis_type", "data_as_of", "retrieved_at"}
ASSET_REQUIRED = {"asset_id", "asset_type", "name", "currency", "retrieved_at", "source"}
NEWS_REQUIRED = {"news_id", "asset_id", "asset_type", "data_as_of", "retrieved_at",
                  "source", "headline", "url", "sentiment", "relevance", "source_priority"}

# Prioridad de FUENTE DE DATOS (mercado), distinta de la jerarquia de
# credibilidad de noticias/periodismo que ya existe en engine/news/sources.py.
# 1 = fuente primaria/oficial. 2 = agregador de mercado establecido.
SOURCE_PRIORITY = {
    "FRED": 1,
    "CoinGecko": 2,
    "DefiLlama": 2,
    "Kraken": 2,
    "Coinbase": 2,
    "Yahoo Finance": 2,
    "Alpha Vantage": 2,
}

# Nunca debe aparecer una fila cuyo "metric" (o cualquier valor) provenga
# de estos ficheros/conceptos -- guardas de privacidad, no solo documentacion.
FORBIDDEN_SOURCE_HINTS = ("cartera_A", "cantidad_neta", "flujo_caja", "CARTERA_A")


class ContractError(ValueError):
    pass


def _parse_date(s):
    if isinstance(s, datetime.date):
        return s
    return datetime.date.fromisoformat(s[:10])


def validate_metric_row(row):
    missing = METRIC_REQUIRED - set(k for k, v in row.items() if v is not None)
    if missing:
        raise ContractError(f"faltan campos requeridos en fila de metrica: {missing}")
    extra = set(row.keys()) - METRIC_FIELDS
    if extra:
        raise ContractError(f"campos no reconocidos por el Data Contract: {extra}")
    if row["source_priority"] not in (1, 2, 3, 4, 5):
        raise ContractError(f"source_priority fuera de rango: {row['source_priority']}")
    # Exactamente uno de value / value_text. Una fila sin ninguno de los dos
    # no transporta dato; una con ambos seria ambigua sobre cual es el valor.
    tiene_num = row.get("value") is not None
    tiene_txt = row.get("value_text") is not None
    if tiene_num and tiene_txt:
        raise ContractError(
            f"value y value_text no pueden venir los dos: {row['metric']} "
            f"= {row['value']!r} / {row['value_text']!r}")
    if not tiene_num and not tiene_txt:
        raise ContractError(f"fila sin dato: ni value ni value_text en {row['metric']}")
    _validate_pct_range(row, "confidence_pct")
    _validate_pct_range(row, "data_quality_pct")
    da, ra = _parse_date(row["data_as_of"]), _parse_date(row["retrieved_at"])
    if da > ra:
        raise ContractError(f"data_as_of ({da}) no puede ser posterior a retrieved_at ({ra})")
    for key, val in row.items():
        if isinstance(val, str) and any(h in val for h in FORBIDDEN_SOURCE_HINTS):
            raise ContractError(f"posible dato de cartera privada en campo '{key}': {val!r}")
    return True


def _validate_pct_range(row, field):
    val = row.get(field)
    if val is not None and not (0 <= val <= 100):
        raise ContractError(f"{field} fuera de rango 0-100: {val}")


def validate_asset_row(row):
    missing = ASSET_REQUIRED - set(k for k, v in row.items() if v is not None)
    if missing:
        raise ContractError(f"faltan campos requeridos en fila de DimAsset: {missing}")
    extra = set(row.keys()) - ASSET_FIELDS
    if extra:
        raise ContractError(f"campos no reconocidos por el Data Contract: {extra}")
    for key, val in row.items():
        if isinstance(val, str) and any(h in val for h in FORBIDDEN_SOURCE_HINTS):
            raise ContractError(f"posible dato de cartera privada en campo '{key}': {val!r}")
    return True


def validate_news_row(row):
    missing = NEWS_REQUIRED - set(k for k, v in row.items() if v is not None)
    if missing:
        raise ContractError(f"faltan campos requeridos en fila de noticia: {missing}")
    extra = set(row.keys()) - NEWS_FIELDS
    if extra:
        raise ContractError(f"campos no reconocidos por el Data Contract: {extra}")
    # jerarquia de credibilidad periodistica (engine/news/sources.py), 1-5 --
    # DISTINTA de SOURCE_PRIORITY (fuentes de datos de mercado, 1-2 arriba).
    if row["source_priority"] not in (1, 2, 3, 4, 5):
        raise ContractError(f"source_priority (credibilidad periodistica) fuera de rango: {row['source_priority']}")
    if not (0 <= row["relevance"] <= 1):
        raise ContractError(f"relevance fuera de rango 0-1: {row['relevance']}")
    da, ra = _parse_date(row["data_as_of"]), _parse_date(row["retrieved_at"])
    if da > ra:
        raise ContractError(f"data_as_of ({da}) no puede ser posterior a retrieved_at ({ra})")
    for key, val in row.items():
        if isinstance(val, str) and any(h in val for h in FORBIDDEN_SOURCE_HINTS):
            raise ContractError(f"posible dato de cartera privada en campo '{key}': {val!r}")
    return True


def validate_thesis_row(row):
    missing = THESIS_REQUIRED - set(k for k, v in row.items() if v is not None)
    if missing:
        raise ContractError(f"faltan campos requeridos en fila de tesis: {missing}")
    extra = set(row.keys()) - THESIS_FIELDS
    if extra:
        raise ContractError(f"campos no reconocidos por el Data Contract: {extra}")
    _validate_pct_range(row, "confidence_pct")
    validez = row.get("evidence_validity")
    if validez is not None and validez not in VALIDEZ_EVIDENCIA:
        raise ContractError(f"evidence_validity fuera del vocabulario: {validez}")
    # Una tesis cuya evidencia requerida esta caducada o sin declarar NO
    # puede publicar un numero de confianza. "No hay base para calcularla"
    # no es "hay poca confianza": un numero reducido invitaria a seguir
    # usandolo igualmente.
    if validez in ("INVALID", "UNKNOWN") and row.get("confidence_pct") is not None:
        raise ContractError(
            f"confidence_pct={row['confidence_pct']} con evidence_validity={validez}: "
            f"una tesis sin evidencia válida no puede declarar confianza")
    da, ra = _parse_date(row["data_as_of"]), _parse_date(row["retrieved_at"])
    if da > ra:
        raise ContractError(f"data_as_of ({da}) no puede ser posterior a retrieved_at ({ra})")
    return True


def now_utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
