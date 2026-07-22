# News / Sentiment Engine (v1)

Fase 4 — dominio consolidado de la Fase 0 (Narrative & Sentiment Domain): noticias, personas influyentes y sentimiento comparten aquí la misma infraestructura, tal como se rediseñó en el Paso 2 de la Fase 0, en vez de ser tres motores separados.

## Componentes

- `sources.py` — jerarquía de credibilidad de fuentes (Fase 0, punto 10): Prioridad 1 (primarias) a 5 (redes sociales), por dominio.
- `fetch_news.py` — conector a **GDELT DOC 2.0 API** (proyecto académico público, sin clave), que etiqueta cada artículo con su nivel de credibilidad según `sources.py`.
- `personas_influyentes.json` — registro de divulgadores/expertos seguidos, con mecanismo de histórico de aciertos (ver más abajo).

## Limitación descubierta en este entorno

GDELT devuelve **HTTP 429 (Too Many Requests) de forma persistente** al ejecutarse desde esta sesión, incluso con reintentos y backoff creciente (15s/30s/45s) — muy probablemente la IP de salida compartida de este entorno ya ha agotado la cuota pública de GDELT. El conector (`fetch_news.py`) está construido correctamente y debería funcionar en un entorno con IP propia o cuando la cuota se libere; **no se ha forzado ni sustituido por una fuente peor** para disimular el problema. Mientras tanto, el informe de esta v1 se generó con búsqueda web puntual, citando fuentes igual que un artículo de GDELT citaría su dominio.

## Principio de diseño: separar HECHO de INTERPRETACIÓN

El motor da el hecho verificable ("este medio publicó este titular, en esta fecha, con esta credibilidad de fuente"). La relevancia, el sentimiento y el "Impact Score" (fórmula conceptual de la Fase 0: relevancia × sorpresa × credibilidad × alcance × persistencia) son **juicio interpretativo explícito**, no un número que el código calcule solo — así se evita la falsa precisión ya señalada en la crítica de la Fase 0 sobre esa misma fórmula.

## Personas influyentes: credibilidad ganada, no asumida

En vez de decidir a priori si un divulgador es fiable, `personas_influyentes.json` registra sus llamadas de mercado con fecha, y se comparan después contra lo que realmente ocurrió — el mismo mecanismo de memoria histórica que el proyecto ya usa para sus propias tesis (Fase 0, punto 21), aplicado también a terceros.
