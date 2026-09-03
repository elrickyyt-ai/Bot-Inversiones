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

METRIC_FIELDS = {
    "asset_id", "asset_type", "domain", "metric", "value", "unit",
    "data_as_of", "retrieved_at", "source", "source_priority",
    "confidence_pct", "data_quality_pct", "calculation_method", "source_url",
}

THESIS_FIELDS = {
    "thesis_id", "asset_id", "thesis_type", "bull_case", "base_case", "bear_case",
    "contradictions", "convergences", "divergences", "invalidation_factors",
    "confidence_pct", "data_as_of", "retrieved_at",
}

# Requeridos de verdad (el resto puede ser None si el motor de origen no lo tiene)
METRIC_REQUIRED = {"asset_id", "asset_type", "domain", "metric", "value", "data_as_of", "retrieved_at", "source", "source_priority"}
THESIS_REQUIRED = {"thesis_id", "asset_id", "thesis_type", "data_as_of", "retrieved_at"}

# Prioridad de FUENTE DE DATOS (mercado), distinta de la jerarquia de
# credibilidad de noticias/periodismo que ya existe en engine/news/sources.py.
# 1 = fuente primaria/oficial. 2 = agregador de mercado establecido.
SOURCE_PRIORITY = {
    "FRED": 1,
    "CoinGecko": 2,
    "DefiLlama": 2,
    "Kraken": 2,
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
    da, ra = _parse_date(row["data_as_of"]), _parse_date(row["retrieved_at"])
    if da > ra:
        raise ContractError(f"data_as_of ({da}) no puede ser posterior a retrieved_at ({ra})")
    return True


def now_utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
