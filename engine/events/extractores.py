"""Extractores de Claims a partir de Evidence. P4 (2026-09-07).

CADA EXTRACTOR ES UNA REGLA DECLARADA, NO ANALISIS DE TEXTO. Lleva
nombre y version, y ese identificador viaja en cada claim que produce
(extraction_method), asi que siempre se puede saber que regla creo una
afirmacion y volver a ejecutarla.

Lo que NINGUN extractor de v1 sabe hacer -- y por tanto no hace -- es
leer el contenido de un titular. "Ripple Is Bringing Agentic AI Payments
to the XRP Blockchain" contiene un acontecimiento real que este sistema
no puede convertir en (sujeto, predicado, objeto) sin inventarselo. Esa
evidencia produce una claim de sentimiento y nada mas, y la parte no
extraida se declara en los `unknowns` del evento.
"""
import datetime

import esquema_evento as esquema

# Umbral declarado, no ajustado a los datos: 10% de variacion diaria en
# una criptomoneda esta muy por encima de su comportamiento normal
# (mediana medida de |cambio| diario de XRP: 1,69%; p95: 8,62%). Se
# declara aqui para que sea revisable, no se calcula sobre la marcha.
UMBRAL_CAMBIO_PRECIO_PCT = 10.0
# Volatilidad historica anualizada por encima del doble de su mediana
# tipica en cripto (~65%).
UMBRAL_VOLATILIDAD_PCT = 130.0


def _claim(claim_id, evidence_ids, subject, predicate, temporal, metodo,
           object_entity=None, object_value=None, polarity="AFFIRMS",
           status="EXTRACTED"):
    return {
        "claim_id": claim_id, "evidence_ids": list(evidence_ids),
        "subject_entity": subject, "predicate": predicate,
        "object_entity": object_entity, "object_value": object_value,
        "temporal_ref": temporal, "polarity": polarity, "status": status,
        "extraction_method": metodo,
    }


# --- 1. Sentimiento afirmado por un medio ----------------------------------

METODO_SENTIMIENTO = "sentiment_assertion/v1"


def extraer_sentimiento(evidencias_noticia):
    """Una claim por (articulo, entidad).

    El sujeto es la entidad y el objeto es la etiqueta, pero la claim NO
    dice "XRP es alcista": dice que ESE MEDIO afirma esa postura. Por eso
    el predicado es ASSERTS_SENTIMENT y no IS_BULLISH, y por eso el
    emisor viaja en la evidencia. Convertir la afirmacion de un medio en
    un hecho del mundo es justo lo que P4 tiene prohibido.
    """
    por_articulo = {}
    for e in evidencias_noticia:
        base = e["evidence_id"].rsplit(":", 1)[0]
        por_articulo.setdefault(base, {})[e["metric"]] = e
    claims = []
    for base, par in sorted(por_articulo.items()):
        score = par.get("news_sentiment")
        label = par.get("news_sentiment_label")
        if not score or not label or label.get("value_text") is None:
            continue
        claims.append(_claim(
            claim_id=f"cl:{base.split(':', 2)[2]}:sentiment",
            evidence_ids=[score["evidence_id"], label["evidence_id"]],
            subject=score["entity_id"], predicate="ASSERTS_SENTIMENT",
            object_value=label["value_text"],
            temporal={"published_at": score["occurred_at"],
                      "occurred_at": score["occurred_at"],
                      "known_at": score["known_at"]},
            metodo=METODO_SENTIMIENTO))
    return claims


def evidencias_sin_claim(evidencias_noticia, claims):
    """Lo que quedo fuera. Se mide en vez de ignorarse: es la respuesta a
    "que partes siguen siendo desconocidas"."""
    usadas = {eid for c in claims for eid in c["evidence_ids"]}
    return [e for e in evidencias_noticia if e["evidence_id"] not in usadas]


# --- 2. Movimiento de precio medido ----------------------------------------

METODO_PRECIO = f"price_change_threshold/v1(umbral={UMBRAL_CAMBIO_PRECIO_PCT}%)"


def extraer_movimientos_precio(evidencias_precio, umbral=UMBRAL_CAMBIO_PRECIO_PCT):
    """Claims MOVED_PRICE a partir de Evidence MEASURED.

    Solo compara sesiones CONSECUTIVAS de la misma fuente: un salto entre
    dos puntos separados por un hueco de la serie no es un movimiento de
    mercado, es un hueco (XRP tiene uno de 905 dias por el deslistado de
    Coinbase, ver knowledge/relationships/identidad.json).
    """
    por_fuente = {}
    for e in evidencias_precio:
        por_fuente.setdefault(e["source"], []).append(e)
    claims = []
    for fuente, filas in sorted(por_fuente.items()):
        filas.sort(key=lambda x: x["occurred_at"])
        for i in range(1, len(filas)):
            ant, act = filas[i - 1], filas[i]
            d1 = datetime.date.fromisoformat(ant["occurred_at"])
            d2 = datetime.date.fromisoformat(act["occurred_at"])
            if (d2 - d1).days != 1 or not ant["value_num"]:
                continue
            cambio = (act["value_num"] / ant["value_num"] - 1) * 100
            if abs(cambio) < umbral:
                continue
            claims.append(_claim(
                claim_id=f"cl:{act['entity_id']}:{act['occurred_at']}:{fuente}:price_move",
                evidence_ids=[ant["evidence_id"], act["evidence_id"]],
                subject=act["entity_id"], predicate="MOVED_PRICE",
                object_value=round(cambio, 2),
                temporal={"occurred_at": act["occurred_at"], "known_at": act["known_at"]},
                metodo=METODO_PRECIO))
    return claims


METODO_VOLATILIDAD = f"volatility_threshold/v1(umbral={UMBRAL_VOLATILIDAD_PCT}%)"


def extraer_picos_volatilidad(evidencias_vol, umbral=UMBRAL_VOLATILIDAD_PCT):
    claims = []
    for e in sorted(evidencias_vol, key=lambda x: x["occurred_at"]):
        if e["value_num"] is None or e["value_num"] < umbral:
            continue
        claims.append(_claim(
            claim_id=f"cl:{e['entity_id']}:{e['occurred_at']}:vol_spike",
            evidence_ids=[e["evidence_id"]], subject=e["entity_id"],
            predicate="VOLATILITY_ROSE", object_value=round(e["value_num"], 2),
            temporal={"occurred_at": e["occurred_at"], "known_at": e["known_at"]},
            metodo=METODO_VOLATILIDAD))
    return claims
