# Data Contract (v1)

Capa de visualización — ver `docs/03-arquitectura-visualizacion-y-acceso.md` para la planificación general y `docs/04-modelo-power-bi.md` para el modelo de datos de Power BI (Fases B-G). Esta pieza cubre los pasos 1-4 del orden acordado con el usuario el 2026-09-03 (historización, DimAsset, ampliar adaptadores equity/technical, adaptador de noticias) más los pasos 1-3 originales (Data Contract, adaptadores, tests) y la Fase A de diagnóstico (`qa.py`) — **la Web App y Power BI todavía no se han construido**, quedan para cuando se autorice explícitamente.

## Diagnóstico (`qa.py`)

```
python3 engine/contract/qa.py
```

Lee `data/`, valida cada fila contra el contrato y produce un informe legible (no JSON crudo), con PASS/FAIL en seis bloques: esquema, privacidad, temporal (`data_as_of` vs. `retrieved_at`), fuentes, DimAsset, y noticias. Ejecutarlo después de cada `build.py` para saber si el sistema funciona sin inspeccionar los ficheros a mano — ver `informes/2026-09-03_data_qa_v1.md` para la primera ejecución real, que encontró un hallazgo genuino (precio en EUR para cripto vs. USD para acciones) y un defecto real en `schema.py` (rango de `confidence_pct`/`data_quality_pct` sin validar, ya corregido). El hallazgo del EUR/USD quedó resuelto con DimAsset (ver más abajo): la comprobación de unidades incompatibles en `qa.py` ahora compara por `(metric, asset_type)` en vez de solo `metric` — una unidad distinta entre asset_types distintos es esperada y queda explicada por `DimAsset.currency`, no es una incidencia.

## Qué hace

`schema.py` define cuatro formas de fila (métrica, tesis, DimAsset, y noticia) que va a consumir tanto la futura Web App como Power BI, sin lógica duplicada entre ambas. `adapters.py` traduce la salida de cada motor existente (`engine/crypto`, `engine/technical`, `engine/macro`, `engine/equity`, `engine/news`, `engine/reasoning`) a esas formas, **sin modificar los motores originales**. `build.py` orquesta todos los adaptadores, valida cada fila contra el contrato antes de escribirla, y genera `data/metrics/{TICKER}.json`, `data/thesis/{TICKER}.json`, `data/assets/{TICKER}.json` y `data/news/{TICKER}.json` en la raíz del repo.

## Uso

```
python3 engine/contract/build.py
```

Requiere que ya existan los datos descargados de cada motor (`_data/` de crypto/technical/macro/equity) — ejecutar sus `fetch_data.py` primero si no existen. Para noticias no hay `fetch_data.py` (ver sección de noticias más abajo) — sin `engine/news/_data/{ID}_news_sentiment.json`, `build.py` simplemente no genera noticias para ese activo, no falla.

## Historización (desde 2026-09-03) — append-only, idempotente

`data/metrics/{ID}.json` y `data/thesis/{ID}.json` ya **no se sobrescriben** en cada ejecución de `build.py` — son un histórico que crece con el tiempo. Ejecutar `build.py` varias veces el mismo día (o el mismo minuto) no duplica filas.

**Clave lógica de idempotencia para métricas**: `(asset_id, domain, metric, data_as_of, source)` — **nunca** `retrieved_at`, porque dos ejecuciones el mismo día tendrían un `retrieved_at` distinto (la hora exacta) pero deben considerarse la misma observación si `data_as_of` coincide.

**Clave lógica de idempotencia para tesis**: `(asset_id, data_as_of)` — como máximo una tesis registrada por activo y fecha de dato.

**Semántica exacta**: si ya existe una fila con esa clave, la fila nueva se descarta (no se sobrescribe el valor existente). Esto significa que la primera captura de un `data_as_of` concreto es la que queda — una revisión posterior del mismo dato histórico (poco común, pero posible en filings) no se reflejaría automáticamente. Se documenta como decisión explícita, no como limitación oculta.

**Macro ya no escribe un fichero `_macro.json` especial** — EE.UU. y Eurozona pasan a tratarse como activos propios (`US.json`, `EA.json`), con el mismo tratamiento historizado que cripto y acciones.

**Migración del formato de tesis**: antes de historizar, `data/thesis/{ID}.json` era un objeto único (la última tesis). Ahora es una lista de objetos. `build.py` migra automáticamente el formato antiguo la primera vez que se ejecuta, sin perder la tesis que ya hubiera.

## DimAsset (`data/assets/{ID}.json`) — atributos estáticos, no historizados

A diferencia de métricas y tesis, `data/assets/{ID}.json` **se sobrescribe** en cada `build.py` (un objeto, no una lista) — nombre, sector, país, divisa no cambian día a día, así que no aporta valor guardar un histórico. Campos: `asset_id`, `asset_type`, `name`, `sector`, `industry`, `country`, `currency`, `exchange`, `active`, `retrieved_at`, `source`.

**Procedencia de cada campo, documentada por tipo de activo** (en el docstring de cada función `adapt_asset_*` de `adapters.py`, no solo aquí):
- **Acciones** (`adapt_asset_equity`): todos los campos extraídos literalmente de `COMPANY_OVERVIEW` de Alpha Vantage (`Name`, `Sector`, `Industry`, `Country`, `Currency`, `Exchange`) — ninguno asignado por el sistema.
- **Cripto** (`adapt_asset_crypto`): `name` viene de CoinGecko. `sector="Cripto"` es una etiqueta **asignada** por este sistema (CoinGecko no tiene un equivalente limpio de "sector" para criptomonedas). `currency="EUR"` es la divisa del **sistema** (todo el motor cripto cotiza vía Kraken en EUR), no una propiedad inherente del activo — esto es precisamente lo que resuelve la ambigüedad EUR/USD que `qa.py` detectó. `country` solo se rellena si CoinGecko trae `country_origin`; si viene vacío se deja `None`, nunca se inventa "Global".
- **Macro** (`adapt_asset_macro`): pseudo-activos para EE.UU. (`US`, `currency="USD"`) y Eurozona (`EA`, `currency="EUR"`) — nombres y divisas fijados por definición de la región, `source="FRED"`.

**Por qué resuelve el hallazgo EUR/USD de `qa.py`**: antes, una fila con `metric="precio"` no dejaba claro en qué divisa estaba sin ir a mirar el motor de origen. Ahora, unir cualquier fila de métrica con `data/assets/{asset_id}.json` por `asset_id` da la divisa real de forma explícita — es la relación que en el modelo de Power BI (`docs/04-modelo-power-bi.md`) corresponde a la tabla `DimAsset`.

## Ampliación de equity y technical (desde 2026-09-03)

`adapt_equity()` y `adapt_technical()` inicialmente solo extraían un subconjunto de lo que sus motores ya calculaban. Ampliado a lo que `score.py` de cada motor ya tenía calculado y verificado — **sin tocar la lógica de cálculo de ningún motor**:

- **`adapt_equity()`** (nuevo): `eps` (leído directamente de `overview["EPS"]`, presente en la fuente cruda de Alpha Vantage pero que `engine/equity/score.py` todavía no devolvía — mismo patrón que ya usa `adapt_asset_equity` para Sector/Industry), `profit_margin_pct`, `operating_margin_pct`, `earnings_beats_8q`/`earnings_misses_8q`/`earnings_surprise_avg_pct`/`earnings_surprise_last_pct` (de `sorpresa_resultados`, ya calculado sobre los últimos 8 trimestres), `analyst_target_price`/`analyst_upside_pct`/`analyst_n_analistas` (de `AnalystTargetPrice`, dato real de Alpha Vantage, no inventado). Todas comparten `data_as_of = fundamental_as_of` (el mismo `LatestQuarter` que ya usaban `pe_ratio`/`peg_ratio`/`roe_pct`) — para el precio objetivo de analistas esto es una aproximación documentada: Alpha Vantage no expone una fecha propia del consenso, así que se le asigna la misma fecha que el resto del overview en vez de inventar una.
- **`adapt_technical()`** (nuevo): `sma20`/`sma50`/`sma100`/`sma200`, `atr14`, `atr14_pct_precio`, `volatilidad_hist_30d_anualizada_pct` — todos ya calculados por `engine/technical/indicators.py` y devueltos por `score_asset()`, solo faltaba extraerlos al contrato.

## Adaptador de noticias (`data/news/{ID}.json`, desde 2026-09-03)

`adapt_news(symbol, asset_type)` traduce `NEWS_SENTIMENT` de Alpha Vantage al contrato. A diferencia del resto de motores, `engine/news/` **no tiene `fetch_data.py`**: el conector MCP solo es invocable desde una sesión de Claude (`engine/news/README.md`), así que el JSON crudo se guarda a mano en `engine/news/_data/{ID}_news_sentiment.json` (gitignored, igual que `_data/` del resto de motores) durante la sesión en la que se consulta ese activo. `build.py` no falla si ese fichero no existe para un activo — simplemente no genera noticias para él (`adapt_news` devuelve `[]`).

**Una fila por (artículo, activo) -- nunca un promedio agregado**, a petición expresa del usuario: cada artículo de `NEWS_SENTIMENT` trae un bloque `ticker_sentiment` con `sentiment`/`relevance` propios de cada ticker que menciona, más preciso que el sentimiento general del artículo (`overall_sentiment_score`), que no se usa. Esto es lo que permite a Power BI analizar después volumen, distribución de sentimiento, relevancia y fuente por separado, en vez de solo una media.

**Campos**: `news_id` (hash estable del `url`, no lo da la fuente), `asset_id`, `asset_type`, `data_as_of` (fecha real de publicación, `time_published` de Alpha Vantage — no la fecha de descarga), `retrieved_at`, `source`, `source_domain`, `source_priority` (jerarquía de credibilidad periodística de `engine/news/sources.py`, 1-5 — ver más abajo), `headline`, `summary`, `url`, `sentiment`, `sentiment_label`, `relevance`, `persona_influyente`.

**`persona_influyente`**: solo se rellena si el autor del artículo aparece literalmente en `engine/news/personas_influyentes.json` — nunca se infiere. En la primera consulta real (XRP, 50 artículos, 2026-09-03) ningún autor coincidió con las 13 personas registradas; el campo queda en `null` para las 50 filas, documentado como ausencia real, no como campo sin completar.

**Historizado igual que métricas** (append-only, idempotente): clave lógica `(asset_id, news_id)`. Como el mismo artículo no cambia de contenido con el tiempo, ejecutar `build.py` varias veces solo añade artículos nuevos que hayan aparecido desde la última consulta.

## `data_as_of` vs. `retrieved_at`

La razón de separarlos (a petición explícita del usuario, y es correcta): un ratio fundamental de una acción corresponde al último trimestre reportado, no al momento en que se descarga. Ejemplo real de XOM en esta misma sesión: `precio` con `data_as_of=2026-09-02` (fecha de la cotización) y `pe_ratio` con `data_as_of=2026-06-30` (fecha del último trimestre) — ambos con el mismo `retrieved_at` (cuándo se ejecutó `build.py`). Sin esta distinción, un futuro backtesting (Fase 8) podría usar sin darse cuenta un dato que en la fecha simulada todavía no existía.

## Gap conocido: macro

`adapt_macro()` usa la fecha de descarga como `data_as_of` en vez de la fecha real del último dato publicado (ej. el mes exacto del CPI) — `engine/macro/score.py` no expone todavía esa fecha en su valor de retorno. Corregirlo es un cambio pequeño pero está fuera del alcance acordado para esta pieza (solo Data Contract + adaptadores, sin tocar los motores). Documentado también en el código.

## Regla de privacidad (aplicada en el propio validador, no solo en la documentación)

`schema.py` rechaza cualquier fila que contenga un campo no reconocido por el contrato, o que mencione literalmente `cartera_A`, `cantidad_neta` o `flujo_caja` en cualquier valor — para que un adaptador futuro no pueda colar por error un dato de `cartera/` en lo que acabará en el bundle de la Web App. Ver `docs/03-arquitectura-visualizacion-y-acceso.md` para la razón completa (un dato en el bundle de una app estática no es equivalente a un dato en backend, aunque el acceso esté protegido).

## Fuentes de datos vs. fuentes de noticias

`SOURCE_PRIORITY` en `schema.py` es una jerarquía **distinta** de la que ya existe en `engine/news/sources.py` — esa es para credibilidad periodística (Reuters vs. un blog), esta es para fiabilidad de fuentes de datos de mercado (FRED como fuente primaria vs. agregadores como Alpha Vantage/CoinGecko). Ambas conviven, no se fusionan. `NEWS_FIELDS.source_priority` usa la jerarquía periodística de `sources.py` (`tier_for_domain()`, 1-5) precisamente porque una fila de noticia es del segundo tipo, no del primero.
