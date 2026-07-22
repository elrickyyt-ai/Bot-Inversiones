"""Ingesta de noticias -- Fase 4.

Fuente: GDELT DOC 2.0 API (proyecto academico, publico, sin clave).
Cubre miles de medios en muchos idiomas, con fecha y dominio de origen
por articulo -- justo lo necesario para aplicar la jerarquia de fuentes
de sources.py. GDELT pide explicitamente no superar 1 peticion cada 5
segundos.

Importante: GDELT da el HECHO "este medio publico este titular en esta
fecha". No da sentimiento fiable por articulo en el modo usado aqui --
el juicio de relevancia/sentimiento/impacto (Fase 0, formula conceptual
de Impact Score) se hace aparte, como interpretacion explicita, no como
un numero mas que el motor calcule solo.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from sources import tier_for_domain

OUT_DIR = os.path.join(os.path.dirname(__file__), "_data")


def _get(url, retries=4, backoff=15):
    req = urllib.request.Request(url, headers={"User-Agent": "bot-inversiones-research/0.1"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = backoff * (attempt + 1)
                print(f"  429 recibido, esperando {wait}s antes de reintentar...")
                time.sleep(wait)
                continue
            raise


def fetch_topic(query, max_records=40, timespan="7d"):
    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": str(max_records),
        "format": "json",
        "sort": "datedesc",
        "timespan": timespan,
    }
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(params)
    data = _get(url)
    articles = data.get("articles", [])
    for a in articles:
        a["credibility_tier"] = tier_for_domain(a.get("domain", ""))
    return articles


def fetch_all(topics, out_name="news_raw.json", sleep_seconds=15):
    os.makedirs(OUT_DIR, exist_ok=True)
    result = {}
    for topic, query in topics.items():
        result[topic] = fetch_topic(query)
        print(f"{topic}: {len(result[topic])} artículos")
        time.sleep(sleep_seconds)
    json.dump(result, open(f"{OUT_DIR}/{out_name}", "w"), ensure_ascii=False)
    return result


if __name__ == "__main__":
    topics = {
        "bitcoin": "bitcoin",
        "ethereum": "ethereum",
        "xrp": "XRP ripple",
    }
    fetch_all(topics)
