# News / Sentiment Engine (v1)

Fase 4 — dominio consolidado de la Fase 0 (Narrative & Sentiment Domain): noticias, personas influyentes y sentimiento comparten aquí la misma infraestructura, tal como se rediseñó en el Paso 2 de la Fase 0, en vez de ser tres motores separados.

## Componentes

- `sources.py` — jerarquía de credibilidad de fuentes (Fase 0, punto 10): Prioridad 1 (primarias) a 5 (redes sociales), por dominio.
- `fetch_news.py` — conector a **GDELT DOC 2.0 API** (proyecto académico público, sin clave), que etiqueta cada artículo con su nivel de credibilidad según `sources.py`. Bloqueado en este entorno (ver más abajo) — se mantiene el código porque es correcto y podría funcionar en otro entorno.
- **`NEWS_SENTIMENT` de Alpha Vantage (conector MCP, cuenta del usuario)** — fuente principal en la práctica desde el 2026-09-03. Mismo patrón que `engine/equity/`: no hay `fetch_data.py` automatizable (el conector solo es invocable desde una sesión de Claude, y no se guarda ninguna clave de API en el repo). Da sentimiento por ticker ya calculado (`ticker_sentiment_score`/`label`) y relevancia por artículo — más estructurado que GDELT.
- `personas_influyentes.json` — registro de divulgadores/expertos seguidos, con mecanismo de histórico de aciertos (ver más abajo).

## Limitación descubierta en este entorno (GDELT)

GDELT devuelve **HTTP 429 (Too Many Requests) de forma persistente** al ejecutarse desde esta sesión, incluso con reintentos y backoff creciente (15s/30s/45s) — muy probablemente la IP de salida compartida de este entorno ya ha agotado la cuota pública de GDELT. El conector (`fetch_news.py`) está construido correctamente y debería funcionar en un entorno con IP propia o cuando la cuota se libere; **no se ha forzado ni sustituido por una fuente peor** para disimular el problema.

## Gestión de cuota de `NEWS_SENTIMENT`

`tickers` filtra en modo "Y" (un artículo debe mencionar TODOS los tickers pasados), no "O" — pedir los 9 activos de la watchlist en una sola llamada devuelve 0 resultados. Cada llamada real es **por ticker individual** (o grupos pequeños con relación real entre sí), así que cubrir todo el watchlist cuesta ~9 llamadas del límite diario gratuito de Alpha Vantage (25/día) — no conviene lanzarlo automáticamente en cada sesión. Se recomienda priorizar: los activos con holdings reales primero, o solo el activo sobre el que se esté escribiendo un informe.

## Alternativas de scraping/RSS investigadas (2026-09-03)

A petición del usuario, antes de usar más créditos se probaron en vivo dos feeds RSS como alternativa gratuita:

- **Google News RSS** (`news.google.com/rss/search`): funciona técnicamente, pero su propio XML incluye un aviso de copyright que **prohíbe expresamente cualquier uso que no sea un lector de feeds personal, no comercial** ("Any other use of the feed is expressly prohibited"). Descartado — no por ser scraping, sino por incumplir sus propios términos.
- **SEC EDGAR filings feed** (`sec.gov/cgi-bin/browse-edgar...output=atom`): fuente oficial, sin restricción de uso, Prioridad 1. Funciona bien, pero solo cubre presentaciones regulatorias (8-K, 10-Q...) de empresas cotizadas en EE.UU. — no sirve para noticias generales ni para cripto. Buen complemento futuro para el dominio de eventos regulatorios, no sustituye a `NEWS_SENTIMENT`.

## Principio de diseño: separar HECHO de INTERPRETACIÓN

El motor da el hecho verificable ("este medio publicó este titular, en esta fecha, con esta credibilidad de fuente"). La relevancia, el sentimiento y el "Impact Score" (fórmula conceptual de la Fase 0: relevancia × sorpresa × credibilidad × alcance × persistencia) son **juicio interpretativo explícito**, no un número que el código calcule solo — así se evita la falsa precisión ya señalada en la crítica de la Fase 0 sobre esa misma fórmula.

## Personas influyentes: credibilidad ganada, no asumida

En vez de decidir a priori si un divulgador es fiable, `personas_influyentes.json` registra sus llamadas de mercado con fecha, y se comparan después contra lo que realmente ocurrió — el mismo mecanismo de memoria histórica que el proyecto ya usa para sus propias tesis (Fase 0, punto 21), aplicado también a terceros.
