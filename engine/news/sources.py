"""Jerarquia de credibilidad de fuentes -- Fase 0, punto 10.

PRIORIDAD 1: fuentes primarias (reguladores, bancos centrales, filings,
             comunicados oficiales).
PRIORIDAD 2: agencias y prensa financiera de maxima reputacion.
PRIORIDAD 3: research profesional.
PRIORIDAD 4: expertos individuales / divulgadores.
PRIORIDAD 5: redes sociales.

Un dominio no listado se trata como PRIORIDAD 3 por defecto (prensa
generalista no verificada expresamente) -- nunca se sube de nivel un
dominio desconocido, solo se puede confirmar hacia arriba explicitamente
anadiendolo aqui.
"""

TIER_BY_DOMAIN = {
    # Prioridad 1 -- primarias
    "sec.gov": 1, "federalreserve.gov": 1, "ecb.europa.eu": 1,
    "data.sec.gov": 1, "bde.es": 1, "imf.org": 1,

    # Prioridad 2 -- agencias / prensa financiera de referencia
    "reuters.com": 2, "bloomberg.com": 2, "ft.com": 2, "wsj.com": 2,
    "cincodias.elpais.com": 2, "expansion.com": 2, "efe.com": 2,

    # Prioridad 3 -- research profesional / prensa financiera generalista
    "finance.yahoo.com": 3, "cnbc.com": 3, "marketwatch.com": 3,
    "investing.com": 3, "coindesk.com": 3, "cointelegraph.com": 3,
}

DEFAULT_TIER = 3

TIER_LABEL = {
    1: "fuente primaria",
    2: "agencia/prensa financiera de referencia",
    3: "prensa financiera / research (no verificada expresamente)",
    4: "divulgador / experto individual",
    5: "redes sociales",
}


def tier_for_domain(domain):
    return TIER_BY_DOMAIN.get(domain.lower(), DEFAULT_TIER)
