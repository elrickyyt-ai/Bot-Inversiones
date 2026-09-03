# Informe — Data Contract v1.1 (historización, DimAsset, ampliación, noticias) + Power BI Desktop v1

**Fecha:** 2026-09-03 · **Commits de hoy:** `3f3c7f9` → `ed3a07e` → `9d0e02f` → `a5e0a54` (rama `claude/session-abz5pi`) · **Power BI Desktop:** construido en paralelo, fuera de git (fichero `.pbix` local del usuario).

Este informe tiene un objetivo distinto a los demás en `informes/`: no documenta un motor nuevo, documenta **trazabilidad de sesión** — qué se hizo, en qué orden, con qué validaciones, y una estimación de tiempo. Se generó a petición explícita del usuario para llevar recordatorios/tareas. Los tiempos están marcados como aproximados donde no hay una marca de tiempo real que los respalde — no se inventa precisión que no existe.

## Resumen ejecutivo

Hoy se cerraron dos bloques de trabajo grandes y distintos:

1. **Data Contract v1.1** (4 pasos autorizados por el usuario, en orden fijo): historización de `build.py`, adaptador `DimAsset`, ampliación de `adapt_equity`/`adapt_technical`, adaptador de noticias. Los 4 commiteados por separado, tests 48/48, `qa.py` en PASS general.
2. **Power BI Desktop v1**: primera construcción guiada, paso a paso, desde `data/metrics`/`data/thesis`/`data/assets`/`data/news` hasta un modelo estrella completo con 6 páginas funcionales, validado en varios puntos contra los valores reales de Python (no solo "se ve bien").

Hallazgo real detectado durante la validación cruzada: **BTC y XRP tienen datos técnicos desactualizados (~45 días)** en el Data Contract, mal etiquetados como si fueran de hoy — bug de diseño en `fecha_dato`, no un fallo de Power BI. Documentado y con tarea pendiente registrada (`task_dfeaeb71`), decisión explícita del usuario: arreglar en otra sesión, no ahora.

## Línea temporal completa del proyecto (verificada contra `git log`)

Para las fases anteriores a hoy, remito a sus propios informes en `informes/` en vez de repetir el contenido aquí — esto es solo el índice cronológico:

| Fecha real (commit) | Qué se construyó | Informe/documento |
|---|---|---|
| 2026-07-20 | Fase 0 (arquitectura conceptual + protocolo de privacidad), Fase 1 (MVP, watchlist, `cartera/` pseudonimizada), Crypto Fundamentals Engine v1 | `docs/00-*`, `informes/2026-07-20_cripto_fundamentales_v1.md` |
| 2026-07-22 | Technical Engine v1, Macro Engine v1, News/Sentiment v1, Scoring Consolidado v1, pruebas de humo, Motor de Razonamiento v1 | `informes/2026-07-22_*.md` (4 informes) |
| 2026-09-02 | Thesis Ledger v1 (Fase 0, punto 21) | — |
| **2026-09-03 (hoy)** | Equity Fundamentals Engine v1, Razonamiento extendido a acciones + Airtable, Noticias v2 (Alpha Vantage), planificación de visualización (`docs/03`), Data Contract v1 (pasos 1-3) + Fase A/QA + diseño de Power BI (`docs/04`), **y los dos bloques de este informe** | `informes/2026-09-03_acciones_fundamentales_v1.md`, `2026-09-03_noticias_sentimiento_v2.md`, `2026-09-03_tesis_acciones_v1.md`, `2026-09-03_data_qa_v1.md`, `docs/03`, `docs/04` |

Hoy es, con diferencia, el día con más volumen de trabajo — de ahí que se desglose en detalle a partir de aquí.

## Bloque 1 (hoy) — Data Contract v1.1: 4 pasos autorizados

Orden fijado explícitamente por el usuario, con la condición de no empezar Power BI hasta `qa.py` en PASS.

### Paso 1 — Historizar `build.py` (commit `3f3c7f9`, 12:06 UTC)
- `data/metrics/{ID}.json` y `data/thesis/{ID}.json` pasan de sobrescribirse a ser históricos append-only.
- Clave lógica de idempotencia: métricas `(asset_id, domain, metric, data_as_of, source)`; tesis `(asset_id, data_as_of)` — nunca `retrieved_at`.
- Macro deja de escribir `_macro.json`; EE.UU./Eurozona pasan a ser activos propios (`US`, `EA`).
- Migración automática del formato antiguo de tesis (objeto único → lista) sin pérdida de datos.
- Validación: `build.py` ejecutado dos veces seguidas → 0 filas nuevas en la segunda pasada.

### Paso 2 — `DimAsset` (commit `ed3a07e`, 12:14 UTC)
- Nuevo fichero por activo, `data/assets/{ID}.json`, **no historizado** (se sobrescribe — atributos estáticos).
- `schema.py`: `ASSET_FIELDS`/`ASSET_REQUIRED`/`validate_asset_row()`.
- `adapters.py`: `adapt_asset_equity` (literal de Alpha Vantage `COMPANY_OVERVIEW`), `adapt_asset_crypto` (`sector="Cripto"` asignado, `currency="EUR"` del sistema vía Kraken, `country` solo si CoinGecko lo trae), `adapt_asset_macro` (US/EA).
- Resuelve el hallazgo EUR/USD de la Fase A: `qa.py` pasa a comparar unidades incompatibles por `(metric, asset_type)` en vez de solo `metric`.
- 11 ficheros `data/assets/*.json` generados (6 cripto + 3 acciones + US/EA).

### Paso 3 — Ampliar `adapt_equity`/`adapt_technical` (commit `9d0e02f`, 12:16 UTC)
- Equity, nuevas métricas: `eps`, `profit_margin_pct`, `operating_margin_pct`, `earnings_beats_8q`, `earnings_misses_8q`, `earnings_surprise_avg_pct`, `earnings_surprise_last_pct`, `analyst_target_price`, `analyst_upside_pct`, `analyst_n_analistas`.
- Technical, nuevas métricas: `sma20`, `sma50`, `sma100`, `sma200`, `atr14`, `atr14_pct_precio`, `volatilidad_hist_30d_anualizada_pct`.
- Todo ya calculado por los motores — **cero cambios en la lógica de cálculo**, solo en qué se extrae al contrato.
- `FactMetrics` pasa de 70 a 142 filas totales.

### Paso 4 — Adaptador de noticias (commit `a5e0a54`, 12:24 UTC)
- `schema.py`: `NEWS_FIELDS`/`NEWS_REQUIRED`/`validate_news_row()`.
- `adapt_news(symbol, asset_type)` lee `engine/news/_data/{ID}_news_sentiment.json` (guardado a mano, sin `fetch_data.py`, mismo patrón que equity) y genera `data/news/{ID}.json`.
- Una fila por (artículo, activo) — nunca un promedio agregado. `sentiment`/`relevance` del bloque `ticker_sentiment` específico del activo.
- `persona_influyente` solo se rellena si el autor coincide literalmente con `personas_influyentes.json` — primera consulta real (XRP, 50 artículos): ninguna coincidencia, `null` en las 50 filas.
- `qa.py`: sexto bloque de validación (esquema/privacidad/duplicados/fuente de noticias).

### Cierre del bloque
- Checklist de 10 puntos del usuario, todos verificados (no solo declarados): tests 48/48, `qa.py` PASS general en 6 bloques, idempotencia confirmada dos veces, `data_as_of`/`retrieved_at` separados, `currency` presente en las 11 filas de `DimAsset`, 0 incidencias de privacidad, 0 métricas sin `source`.
- **Tiempo (aproximado, por marca de commit real):** de 09:33 a 12:24 UTC = **~2h51min** de trabajo con commit, cubriendo también el Equity Engine, la extensión del Motor de Razonamiento, Noticias v2 y la planificación de Power BI que precedieron a este bloque de 4 pasos — no es tiempo exclusivo de los 4 pasos, es todo el tramo de la mañana.

## Bloque 2 (hoy) — Power BI Desktop v1: construcción guiada

**Sin marcas de tiempo de commit** (todo el trabajo vive en el `.pbix` local del usuario, no en git) — el tiempo aquí es una **estimación aproximada basada en el volumen y complejidad de la conversación**, no en datos medidos.

### Incidencia inicial: clon anidado
El primer intento de `Get Data → Carpeta` apuntaba a un `data/metrics` que en realidad contenía un clon completo del repo dentro de sí mismo (por un `git clone` ejecutado dentro de la propia carpeta destino). Diagnosticado y corregido re-clonando limpio en `C:\Bot-Inversiones` directamente en la rama `claude/session-abz5pi`.

### Tablas creadas (Power Query / DAX)
| Tabla | Origen | Filas (validadas) | Notas |
|---|---|---|---|
| `FactMetrics` | `data/metrics/*.json` | 142 | Columna `value` dividida en `value_numeric`/`value_text` (bug de la primera versión: `Text.From` convertía también los números — corregido con `if [value_numeric] <> null then null else Text.From([value])`) |
| `FactThesis` | `data/thesis/*.json` | 9 | Sin las 4 columnas de listas (van a `FactThesisFindings`) |
| `FactThesisFindings` | `data/thesis/*.json` (despivotado) | 29 | Una fila por hallazgo (`contradiction`/`convergence`/`divergence`/`invalidation`) |
| `DimAsset` | `data/assets/*.json` | 11 | Un objeto por fichero, no historizado |
| `DimDate` | Calculada en DAX (`CALENDAR`) | 2026-01-01 a 2027-12-31 | Marcada como tabla de fechas |
| `FactNews` | `data/news/*.json` | 50 (solo XRP) | `data_as_of` es datetime completo, no solo fecha — columna `Fecha` añadida aparte para relacionar con `DimDate` |

### Relaciones del modelo estrella
Todas Uno a varios (1:*), dirección de filtro única, desde las dimensiones hacia los hechos:
- `DimAsset[asset_id]` → `FactMetrics`, `FactThesis`, `FactThesisFindings`, `FactNews`
- `DimDate[Date]` → `FactMetrics[data_as_of]`, `FactThesis[data_as_of]`, `FactThesisFindings[data_as_of]`, `FactNews[Fecha]`
- **Corregido**: la detección automática de Power BI había creado `FactThesis`↔`DimAsset` como Uno-a-uno con dirección Ambas (bidireccional) — cambiado a Varios-a-uno, dirección única, porque hoy solo hay 1 tesis por activo (coincidencia del primer día), pero la tabla es estructuralmente varios-por-activo.
- **Eliminada**: relación fact-a-fact `FactThesisFindings[thesis_id]`↔`FactThesis[thesis_id]` que la autodetección había creado (inactiva) — nunca debe existir, ni activa ni inactiva, por diseño.

### Medidas DAX creadas (28 en total)
Genéricas: `Asset Count`, `Metric Count`, `Thesis Count`, `Latest Confidence`, `Latest Data Quality`, `Latest Value`, `Latest Value Text`.
Negocio: `Precio Actual`, `RSI Actual`, `Confluencia Sesgo`, `ROE`, `Crecimiento Ingresos YoY`.
Data Quality: `Filas Totales`, `Fuentes Activas`, `Ultima Actualizacion`, `Metric Rows`, `Distinct Units`, `Unit Consistency Flag`, `Freshness Dias`.
Market Overview: `Crypto Count`, `Equity Count`, `Macro Count`.
Macro: `CPI YoY`, `Fed Funds Rate`, `HICP YoY`, `ECB Deposit Rate`.
News: `News Count`, `Avg Sentiment`, `Avg Relevance`.

Decisión de arquitectura de medidas: **opción (b)** para Asset Research (tabla dinámica `metric`/`Latest Value`/`Latest Value Text`, escalable a nuevas métricas sin tocar el informe) en vez de una medida fija por métrica — decidida tras ver ambas opciones en contexto real, no en abstracto. Reversible sin fricción en cualquier momento (ambas opciones comparten las mismas medidas base).

### Páginas construidas (6 de 6 planificadas)
1. **Data Quality** — KPIs, confidence/calidad por dominio, matriz de cobertura activo×métrica, verificación de unidades (por `metric`+`asset_type`), freshness por activo.
2. **Market Overview** — tabla de los 11 activos con `Precio Actual` siempre junto a `currency` (nunca sola, por el histórico problema EUR/USD).
3. **Asset Research** — ficha de un activo (segmentador de selección única) + tabla dinámica de todas sus métricas.
4. **Thesis** — bull/base/bear + tabla de hallazgos (`FactThesisFindings`), validado con BTC/XRP/IBM/XOM contra los recuentos reales.
5. **Macro** — US/EA, 4 medidas fijas (pocas y estables, aquí sí opción a).
6. **News & Sentiment** — solo XRP tiene datos (aviso explícito en la página); distribución de sentimiento validada contra el dato real (28 Neutral, 18 Somewhat-Bullish, 3 Bullish, 1 Somewhat-Bearish).

Portfolio y Backtesting (de las 8 páginas listadas en `docs/03` §9) **deliberadamente fuera de alcance**: Portfolio necesitaría conectar `cartera/` al Data Contract, que el protocolo de privacidad excluye; Backtesting es la Fase 8, que no existe.

### Validaciones cruzadas Python ↔ Power BI (el criterio de aceptación que fijó el usuario)
- BTC: `precio` 57244.8 EUR y `rsi14` 58.1 en Python == "57,24 mil" y "58,10" en la tarjeta de Power BI.
- IBM: `precio` 231.7 USD y `roe_pct` 34.5% en Python == "231,70" y "34,50" en Power BI.
- Recuentos de filas por tabla, por hallazgo de tesis y por distribución de sentimiento, todos verificados contra `data/` real antes de que el usuario los confirmara en pantalla.

### Hallazgo real: BTC/XRP con datos técnicos desactualizados
Durante la validación de Market Overview, el usuario notó que el precio de BTC (57.244,80 EUR) no coincidía con el precio de mercado real del momento. Investigado: `engine/technical/_data/BTC_ohlc.json` y `XRP_ohlc.json` tienen su última vela real fechada el 2026-07-20 (Kraken devolvió datos desactualizados ~45 días para esos 2 pares en la última descarga), mientras que ETH/ADA/SOL/DOT están al día (2026-09-02). Causa raíz: `fecha_dato` en `engine/technical/score.py`/`engine/crypto/score.py` usa `datetime.now()` en vez de la fecha real de la última vela — por eso el dato antiguo se etiqueta como si fuera de hoy. **Decisión del usuario**: seguir con Power BI, arreglar en Python en otra sesión — tarea registrada (`task_dfeaeb71`, con diagnóstico completo) para no perder el hallazgo.

### Pendiente de pulido (no bloqueante)
- Página Thesis: el texto de bull/base/bear se ve mejor en una "Tarjeta multifila" que en Tabla, pero ese tipo de visual no aparece en la versión de Power BI del usuario — se dejó la Tabla tal cual (ajuste manual de anchos) hasta que haga falta revisarlo.
- Nota del usuario sobre agregación por defecto: columnas como `source_priority`/`relevance` (en `FactNews`) o `confidence_pct` (en `FactThesis`) usan `SUM` por defecto al arrastrarlas a una tabla. Hoy no afecta porque cada fila es única (un artículo/una tesis), pero es un riesgo si en el futuro se agrupa por algo más amplio (ej. por activo sin desglosar por artículo) — el `SUM` sumaría en vez de mostrar un valor con sentido. Recomendado para cuando se retome: cambiar la agregación por defecto de esas columnas a "Promedio" o "No resumir" (Vista de Modelo → columna → Herramientas de columna → Resumen de valores), o seguir usando medidas explícitas con `AVERAGE`/`SELECTEDVALUE` como ya se hace en el resto del modelo.

## Estado final verificado

- Tests: **48/48 OK** (`python3 -m unittest discover -s tests -v`).
- `qa.py`: **PASS general** en los 6 bloques (esquema, privacidad, temporal, fuentes, DimAsset, noticias).
- Working tree de git: limpio, los 4 commits del Bloque 1 ya en remoto (`origin/claude/session-abz5pi`).
- Power BI Desktop: 6 páginas construidas y validadas por el usuario, modelo estrella completo (`DimAsset`, `DimDate`, `FactMetrics`, `FactThesis`, `FactThesisFindings`, `FactNews`).

## Estimación de tiempo — aviso importante

Esta sesión no tiene marcas de tiempo por mensaje, así que las cifras de abajo combinan dos fuentes distintas de fiabilidad muy distinta:

- **Bloque 1 (Data Contract):** basado en las marcas de tiempo **reales** de los commits de git — dato verificable, no estimado. Tramo completo de la mañana (Equity Engine → Data Contract v1.1): 09:33–12:24 UTC, **~2h51min**.
- **Bloque 2 (Power BI):** **estimación aproximada**, sin dato duro que la respalde, basada en el volumen de intercambios y la complejidad de lo construido (6 páginas, 6 tablas, 28 medidas, 3 incidencias reales depuradas). Orden de magnitud razonable: **3-4 horas**, pero podría ser mayor o menor — no lo presento como medido, solo como referencia útil para planificar.

## Próximos pasos

1. **Corregir `fecha_dato`** en `engine/technical/score.py`/`engine/crypto/score.py` (tarea ya en cola, `task_dfeaeb71`) — prioridad alta, es un dato incorrecto mostrándose como correcto, no solo un hueco.
2. **Automatizar la ingesta de fuentes gratuitas** (Kraken, CoinGecko, DefiLlama, FRED) vía GitHub Actions con un cron diario — es justo lo que permitiría que las gráficas de líneas/áreas que pide el usuario tengan sentido con el tiempo, sin depender de ejecutar `fetch_data.py`/`build.py` a mano cada día (ver respuesta detallada en el chat sobre esto).
3. **Decidir sobre Alpha Vantage** (verificación de cuota ilimitada open-source/educativa, o clave propia del usuario) — desbloquea la misma automatización para acciones y noticias.
4. Pulido opcional: resolver la Tarjeta multifila de Thesis, revisar agregación por defecto en columnas señaladas, quizás actualizar `docs/04-modelo-power-bi.md` para que refleje el modelo tal como quedó construido (hoy documenta el diseño previo a la construcción real).
5. Cuando haya más de un día real de histórico acumulado: añadir las medidas de variación (`Previous Value`, `Change %`) que quedaron bloqueadas por falta de profundidad temporal, y gráficas de líneas/áreas por activo usando `DimDate`.
