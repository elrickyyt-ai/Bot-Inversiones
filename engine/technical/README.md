# Technical Analysis Engine (v1)

Motor técnico — Fase 3, dominio Market Behavior de la Fase 0. Implementado en Python puro (sin `numpy`/`pandas`, no disponibles en este entorno de ejecución).

## Uso

```
python3 engine/technical/fetch_data.py       # descarga OHLC diario (Kraken) a engine/technical/_data/ (no versionado)
python3 engine/technical/score.py            # calcula indicadores y confluencia "hoy", imprime JSON
python3 engine/technical/fetch_backfill.py   # descarga OHLC historico (Coinbase) -- ver "Backfill histórico" abajo
```

## Principio de diseño: confluencia, no señales aisladas

La Fase 0 es explícita: *"no utilizar indicadores como señales aisladas, buscar confluencias"*. Por eso `score.py` no reporta el RSI o el MACD como una señal de compra/venta por separado — los combina en un contador de confluencia (`precio > SMA50`, `precio > SMA200`, `RSI > 50`, `MACD histograma positivo`) y solo cuando todas coinciden se etiqueta como "confluencia alcista/bajista"; si no, se marca honestamente como "mixto".

## Indicadores v1

SMA 20/50/100/200, RSI(14) de Wilder, MACD(12,26,9), ATR(14), volatilidad histórica anualizada (30 días), ROC(12), posición en el rango de 90 días, y una detección simple de estructura de swings (Higher/Lower Highs/Lows con ventana de 10 velas).

## Explícitamente fuera de v1

- ADX (fuerza de tendencia).
- Soportes/resistencias más allá del rango de 90 días.
- Volumen relativo, OBV, VWAP (dominio Volumen y Microestructura de la Fase 0 — pendiente).
- Implied Volatility (no aplica sin mercado de derivados accesible).

## Fuente de datos ("hoy", incremental)

Kraken OHLC público (`/0/public/OHLC`, `interval=1440`), sin clave. Da hasta ~720 velas diarias (~2 años) — coherente con la limitación ya documentada en `docs/02-fase1-gaps-y-roadmap-fuentes.md` para el resto de motores cripto.

## Backfill histórico (2026-09-04, Bloque 3) — `fetch_backfill.py`

**Fuente elegida: Coinbase Exchange** (`api.exchange.coinbase.com/products/{ID}/candles`, sin clave), no Yahoo Finance. Comparadas ambas contra los mismos criterios (profundidad, OHLC, volumen, frecuencia, API, estabilidad, límites, coste, términos de uso, automatización, cobertura, riesgo de que deje de funcionar, compatibilidad):

| Criterio | Coinbase Exchange | Yahoo Finance (endpoint no oficial) |
|---|---|---|
| API | Oficial, documentada (docs.cloud.coinbase.com) | No oficial/no documentada -- el mismo endpoint que usa `yfinance` |
| Términos de uso | Endpoint público de mercado, sin restricción de uso automatizado | Zona gris (ToS de uso personal) -- mismo motivo por el que este proyecto ya descartó Google News RSS en `engine/news/` |
| Riesgo de que deje de funcionar | Bajo -- API de producto versionada | Real -- Yahoo ya forzó una migración de endpoint en 2017 |
| Divisa nativa | Pares EUR (`BTC-EUR`, ...) -- misma divisa que ya usa este motor vía Kraken | Tiene tickers `-EUR` también (verificado), pero introducir una fuente de mayor riesgo solo por ~1-3 años más de profundidad no se justificaba |
| Profundidad real (verificada en vivo) | BTC 2015-04, ETH 2017-05, XRP 2019-02, ADA 2021-03, SOL/DOT 2021-06 | Algo mayor (BTC 2014-09, ETH/XRP/ADA 2017-11, SOL 2020-04, DOT 2020-08) |
| Cobertura de los 6 activos | Completa, pares EUR nativos | Completa, pares EUR nativos |

Se evaluaron también Binance (bloqueado por restricción geográfica/ToS desde este entorno) y CryptoCompare (su API gratuita ya exige clave para uso real, rompe el patrón "sin clave" del resto de fuentes del proyecto) -- descartadas. La profundidad de Coinbase (varios años para los 6 activos) ya satisface el objetivo pedido ("desde varios meses/años atrás"); la profundidad algo mayor de Yahoo no compensaba el riesgo/términos de uso.

**Metodología de indicadores -- igual que "hoy", sin excepción**: `score.py::historical_series()` calcula SMA/RSI/ATR/volatilidad con las MISMAS funciones de `indicators.py` que ya usa `score_asset()`, recorriendo el array completo que esas funciones ya devuelven en vez de descartar todo menos el último punto. Ninguna metodología nueva.

**Huecos reales en la serie**: `_split_contiguous()` detecta cualquier hueco de calendario (vela no consecutiva) y trata cada tramo como una serie independiente para el cálculo de indicadores -- una ventana móvil nunca mezcla precios de antes y después de un hueco. Hallazgo real: Coinbase deslistó XRP en EE.UU. entre 2021-01-19 y 2023-07-13 (~905 días) por el litigio con la SEC contra Ripple -- sin esta división, el SMA20 del primer día tras el hueco habría mezclado un precio de 2023 con 19 precios de antes de 2021.

**Métrica nueva**: `volumen` (unidad `"unidades"`, no el ticker del activo -- evita que `qa.py` marque una misma métrica con 6 unidades distintas). Añadida también a `adapt_technical()` ("hoy"), no solo al backfill, para que ambos flujos no diverjan en qué métricas existen.

## Corrección del hueco de proceso (2026-09-04)

**Detectado por el usuario en Power BI**: las series históricas de los 6 activos mostraban un hueco de ~2 años (ej. BTC: 2024-07-29 → 2026-07-20). Diagnóstico: la v1 de este backfill usaba como frontera la primera vela de la caché ROTATIVA de Kraken (`_ohlc.json`, que solo guarda los últimos ~720 días desde HOY, se regenera en cada `fetch_data.py`) -- pero el cron incremental (`adapt_technical()`) solo escribe UN punto por ejecución (el "hoy" de cada día que corrió), nunca toda esa ventana. Antes de que el cron existiera (y entre el final del primer backfill y su primera ejecución real), no se escribió nada en `data/metrics/` para esas fechas -- un hueco real de proceso, no de mercado (Coinbase tenía los datos completos todo este tiempo).

**Corrección**:
- `fetch_backfill.py::update_cache(symbol)` (antes `fetch_one()`) ya NO vuelve a descargar todo el histórico cada vez -- EXTIENDE la caché local ya existente desde su última vela guardada + 1 día hasta hoy, fusionando (nunca re-descarga lo que ya está en disco).
- `adapt_technical_backfill()` ya no excluye por una frontera fija -- excluye cualquier fecha que YA esté en `data/metrics/{symbol}.json` (de cualquier fuente), leído del propio Data Contract vía `_existing_technical_dates()`. Esto cierra cualquier hueco de proceso automáticamente, no solo el que se conocía al escribir el código, y es el mismo mecanismo reutilizable si el cron diario llegara a fallar varios días seguidos.
- `engine/contract/backfill.py::detect_technical_gaps(symbol)` / `python3 backfill.py --gaps`: herramienta de diagnóstico, lee `data/metrics/` y reporta huecos de calendario reales en la serie ya escrita -- el lado de detección que complementa la corrección anterior.

**Resultado**: 44.100 filas nuevas repartidas en los 6 activos (BTC 7650, ETH 7200, ADA 7200, SOL 7200, DOT 7200, XRP 7650). Huecos restantes, todos reales y explicados (no de proceso): BTC 2015-04-24→27 y 2016-07-11→13 (baja liquidez en Coinbase), ETH 2017-05-26→29 (idem), XRP 2021-01-19→2023-07-13 (Coinbase deslistó XRP en EE.UU. por el litigio SEC-Ripple). Se evaluó Yahoo Finance como fuente secundaria para cerrar también el hueco de XRP (tiene cobertura continua en esa ventana) -- precios verificados en ambos extremos del hueco contra Coinbase (2021-01-19: 0.2497 vs 0.2424, ~2.9%; 2023-07-13: 0.7304 vs 0.7265, ~0.5%, ambas diferencias dentro de la variación normal entre exchanges) -- pero no se aplicó: introducir una tercera fuente (con el mismo perfil de riesgo/ToS ya descartado para el backfill principal) solo para 2.4 años de un único activo no se justificaba frente a dejarlo como hueco explicado, que el criterio de aceptación de este bloque permite explícitamente.

## Calendario de sesiones bursátiles (2026-09-04, previo al Bloque 4 de acciones) — `trading_calendar.py`

**Problema identificado antes de tocar ningún dato de acciones**: `_split_contiguous()` definía "hueco" como "cualquier vela que no esté exactamente 1 día natural después de la anterior" -- correcto para cripto (cotiza 24/7, cualquier interrupción es una anomalía real), pero mal aplicado a acciones habría roto el tramo en CADA fin de semana (viernes→lunes) y en cada festivo bursátil, dejando SMA20 prácticamente inutilizable (nunca 20 velas consecutivas disponibles).

**Solución elegida: abstraer un calendario de sesiones (`trading_calendar.py`), no un umbral arbitrario de días.** Se descartó explícitamente una regla tipo "hueco = más de N días naturales" -- fallaría tanto ocultando huecos reales de varios días en cripto como marcando falsos huecos en semanas con festivo bursátil (ej. Acción de Gracias + fin de semana da un salto de 4 días naturales, indistinguible de una sesión real ausente para una regla de umbral fijo). En su lugar, `sessions_skipped_between(fecha1, fecha2, asset_type)` cuenta cuántas sesiones de trading se ESPERABAN entre dos fechas -- 0 sesiones esperadas es continuidad real, sin importar los días naturales de por medio.

- `asset_type="crypto"`: cualquier día es una sesión (24/7) -- 0 sesiones esperadas equivale exactamente a estar 1 día natural aparte, mismo resultado que la comprobación anterior (`== 86400`). **Comportamiento de cripto sin cambios, verificado con un test de regresión explícito** (`historical_series()` sobre la fixture real de BTC, 721 velas, da resultados idénticos con y sin pasar el parámetro).
- `asset_type="equity"`: usa un calendario de festivos NYSE (`us_market_holidays()`) calculado con reglas fijas (Computus para Viernes Santo, "n-ésimo lunes del mes" para el resto, regla de observancia sábado→viernes/domingo→lunes) -- sin dependencias externas (`pandas_market_calendars`, listas descargadas) ni una lista mantenida a mano. Un viernes→lunes o un festivo bursátil no rompen el tramo; una sesión de trading realmente ausente sí.

`_split_contiguous(ohlc, asset_type="crypto")` y `historical_series(symbol, path, asset_type="crypto")` aceptan el nuevo parámetro (valor por defecto preserva el comportamiento exacto anterior). `_historical_series_segment()` no cambia -- nunca dependió de fechas consecutivas, solo de la posición dentro del array que le pase `_split_contiguous()`, así que reutiliza el mismo motor sin duplicar lógica de cálculo entre cripto y acciones.

**Fuente/calendario a usar después para el backfill real de acciones** (todavía no ejecutado): Yahoo Finance para el histórico profundo (ajustado por splits/dividendos, ver evaluación del Bloque 4), Alpha Vantage `TIME_SERIES_DAILY` (`outputsize=compact`) para el flujo incremental -- pendiente de implementar, este bloque solo resolvió la compatibilidad del motor con el calendario de sesiones.
