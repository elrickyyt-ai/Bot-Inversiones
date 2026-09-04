# Estrategia de backfill histórico + ingesta incremental

**Fecha:** 2026-09-04 · **Tipo:** análisis y propuesta de arquitectura, **sin código todavía** (a petición explícita del usuario) · **Precede a:** cualquier cambio de Power BI, Web App, Alpha Vantage o Thesis Ledger.

## Aclaración de partida (la que motivó este informe)

Hasta ahora, "histórico" en este proyecto se ha construido como **acumulación desde hoy hacia adelante** (Fase de historización de `build.py`, 2026-09-03). Esto es correcto pero incompleto: no rellena lo que pasó *antes* de empezar a capturar. Este informe separa expresamente las dos funciones, tal como pidió el usuario:

- **HISTORICAL BACKFILL** = llenar el pasado (una vez, o de forma ocasional para ampliar profundidad).
- **INCREMENTAL INGESTION** = seguir desde el presente hacia adelante (lo que el cron diario ya hace).

No son la misma pieza de código ni deben serlo — pero **sí deben escribir en el mismo sitio con la misma disciplina**: ambas pasan por `_write_metric_rows()` en `engine/contract/build.py`, que ya es idempotente por `(asset_id, domain, metric, data_as_of, source)`. Esa es la razón por la que no hace falta rediseñar nada de lo ya construido — sí hace falta un proceso nuevo (`backfill`) que alimente esa misma función con muchas fechas de golpe en vez de una.

## 1-5. Qué histórico ofrece realmente cada fuente (verificado en vivo hoy, no supuesto)

| Fuente | Qué cubre | Profundidad real verificada | Cómo se verificó |
|---|---|---|---|
| **Kraken** (`OHLC`, cripto) | Precio, OHLC, volumen técnico | **~721 velas diarias (~2 años), tope duro** — probado con `since` fijado en 2015 y sigue devolviendo solo los últimos ~2 años | Llamada real a la API con `since=1420070400`: devolvió 2024-09-14 → 2026-09-04, 721 puntos, ignorando el `since` antiguo |
| **CoinGecko** (`market_chart`, `/history`, cripto) | Fundamental (market cap, FDV, supply), precio de referencia | **365 días exactos, tope duro de plan gratuito, sin excepción** — ni siquiera el endpoint `/history` (día suelto) da fechas más antiguas | Dos llamadas reales: `days=max` y `/history?date=15-06-2018` — ambas devuelven el mismo error explícito: *"Public API users are limited to querying historical data within the past 365 days"* |
| **DefiLlama** (`historicalChainTvl`, cripto) | TVL histórico | **Completo desde el origen de la cadena — ya lo tenemos capturado** (ETH: 3264 puntos, desde 2017-09-27) | Inspección directa de `engine/crypto/_data/ETH_tvl.json`, ya descargado hoy |
| **FRED** (macro) | Inflación, tipos, desempleo, curva de tipos | **Completo desde el origen de cada serie — ya lo tenemos capturado** (DGS10 desde 1962, CPI desde 1947, FEDFUNDS desde 1954) | Inspección directa de `engine/macro/_data/*.json`, ya descargado hoy |
| **Alpha Vantage** (equity + noticias) | Precio/OHLC equity, EPS/revenue, `NEWS_SENTIMENT` | **No verificado en vivo hoy** (cuota deliberadamente no gastada, baja prioridad declarada por el usuario) — según documentación pública: `TIME_SERIES_DAILY` con `outputsize=full` da ~20+ años en 1 sola llamada; `EARNINGS` normalmente da bastantes más trimestres de los que tenemos guardados (hoy solo 8, verificado en `_data/IBM_earnings.json` — probablemente porque solo se guardó un recorte en su momento, no porque la API dé solo eso); `NEWS_SENTIMENT` con cobertura históricamente más limitada (aprox. desde 2022, sin confirmar) | Sin llamada — sujeto a verificación de bajo coste cuando se decida abordar esto |

**Hallazgo nuevo, no pedido explícitamente pero directamente relevante**: probé **Yahoo Finance** (gratis, sin clave, ya usado en este proyecto para acciones/índices según `docs/02`) como fuente candidata para tapar el hueco de Kraken/CoinGecko en cripto:

| Ticker Yahoo | Profundidad real verificada |
|---|---|
| BTC-USD / BTC-EUR | 4371 puntos diarios, desde 2014-09-17 |
| ETH-USD | 3222 puntos, desde 2017-11-09 |
| XRP-USD | 3222 puntos, desde 2017-11-09 |
| ADA-USD | 3222 puntos, desde 2017-11-09 |
| SOL-USD | 2339 puntos, desde 2020-04-10 (coherente, SOL nació ese año) |
| DOT-USD | 2207 puntos, desde 2020-08-20 (coherente, DOT nació ese año) |

Gratis, sin clave, sin límite de 365 días. **Es la pieza que falta para cubrir el ejemplo que diste (2020→2026) en cripto**, algo que ni Kraken ni CoinGecko pueden dar hoy en su plan gratuito.

## Distinción pedida: histórico de mercado vs. histórico de indicadores

**Confirmado, ya construido así**: `engine/technical/indicators.py` (`sma`, `rsi`, `macd`, `atr`, `historical_volatility`) recibe arrays de precios/OHLC crudos y calcula internamente — nunca llama a una fuente externa de indicadores. Es exactamente el principio que pediste (RSI de 2022 y RSI de mañana calculados con la misma metodología). No hay que rediseñar esto, hay que **reutilizarlo sobre más historia**.

Hallazgo técnico relevante: `sma(closes, 20)` ya devuelve un **array completo** (una SMA por cada punto de la serie) — `score_asset()` hoy solo usa `[-1]` (el último). Para generar histórico de indicadores no hace falta indicador histórico externo (que no existe y no lo buscamos) — hace falta **dejar de descartar el resto del array** y recorrerlo para producir una fila por fecha pasada, sobre el mismo OHLC que se backfillee.

## 6-7. Qué merece la pena recuperar y qué no

**Sí, prioridad alta (mejor relación valor/esfuerzo)**:
1. **Macro (FRED)** — ya está descargado completo, 60+ años. Solo falta el adaptador que lo historice entero en vez de solo "hoy". Cero llamadas nuevas, cero fuente nueva.
2. **DefiLlama TVL** — mismo caso: ya descargado completo desde 2017. Mismo tipo de adaptador.
3. **Precio/OHLC/técnico cripto vía Yahoo Finance** — resuelve el hueco real de Kraken (2 años) y CoinGecko (365 días). Alimenta directamente `indicators.py` para generar RSI/SMA/ATR/volatilidad históricos con la misma metodología que hoy.

**Sí, prioridad media (cuando se retome Alpha Vantage)**:
4. **Precio/OHLC equity vía Alpha Vantage `outputsize=full`** — 1 sola llamada por ticker da ~20 años, coste de cuota mínimo (3 llamadas para IBM/NVDA/XOM). Bloqueado solo por la decisión de cuota ya en curso (mensaje a soporte).
5. **EARNINGS histórico completo** — ya se paga la llamada hoy (cuota ya consumida en el ciclo normal), solo falta guardar más trimestres/años de lo que se guardó la primera vez.

**No merece la pena todavía**:
- **Fundamental cripto vía CoinGecko más allá de 365 días** — tope duro de plan gratuito sin excepción verificada; forzarlo no es posible gratis. Se irá acumulando solo, de forma incremental, según pase el tiempo real — no hay backfill posible aquí sin pasar a plan de pago.
- **Noticias (Alpha Vantage `NEWS_SENTIMENT`)** — coste alto en cuota (1 llamada/activo) para un histórico de profundidad incierta y de menor prioridad declarada. Encaja con tu propio orden: dejarlo para después.

## 8. Cómo se integra con la historización incremental ya construida

**No hace falta ninguna integración nueva de "pegamento"** — es la razón de que la Fase 1 de historización (2026-09-03) siga siendo válida sin tocarla:

```
                    HISTÓRICO (backfill, nuevo proceso)
                              ↓
              adapt_*_backfill()  -- recorre TODA la serie ya
              descargada/calculada, produce una fila por fecha
                              ↓
              _write_metric_rows()  -- YA EXISTE, sin cambios.
              Misma clave de idempotencia: (asset_id, domain,
              metric, data_as_of, source). Una fecha ya presente
              se descarta sola, sin duplicar.
                              ↓
                        data/metrics/{ID}.json
                              ↑
              _write_metric_rows()  -- MISMA función
                              ↑
              adapt_crypto() / adapt_technical() / adapt_macro()
              -- YA EXISTEN, sin cambios, solo "hoy"
                              ↑
                    Cron diario ya en marcha (GitHub Actions)
```

El backfill se ejecuta **una vez** (o de forma ocasional, si se decide ampliar profundidad más adelante). El cron sigue exactamente igual, sin saber ni necesitar saber que el backfill existió — simplemente sigue añadiendo "hoy" cada día, y como la clave de idempotencia ya existe y funciona, nunca puede pisar ni duplicar lo que puso el backfill.

## 9. Estrategia óptima para que Power BI vea series temporales útiles cuanto antes

Orden por **valor/esfuerzo**, no por dificultad técnica pura:

1. **Backfill de macro (FRED)** — el más rápido de todos: los datos ya están en disco, no hay fuente nueva que integrar, no hay límite de cuota, no hay coste de red. Da inmediatamente 60+ años de tipos/inflación en Power BI. Es el primer bloque que yo construiría.
2. **Backfill de TVL cripto (DefiLlama)** — mismo razonamiento, mismo tipo de trabajo, datos ya en disco desde 2017.
3. **Backfill de precio/técnico cripto (Yahoo Finance, fuente nueva)** — el que más impacto visual da en Power BI (gráficas de precio/RSI/SMA de años, no solo un punto), pero requiere: un fetcher nuevo (similar a los que ya existen, mismo patrón `_data/`), y adaptar `indicators.py`/`score.py` para recorrer todo el histórico en vez de solo el último punto.
4. **Backfill de equity (Alpha Vantage)** — alto valor, coste de cuota mínimo, pero deliberadamente después de resolver la conversación con Alpha Vantage sobre la cuota, para no competir con el resto de usos ya establecidos.

## Fuente nueva a añadir — respuesta a tu pregunta explícita

**Sí, una: Yahoo Finance**, exclusivamente para precio/OHLC histórico de cripto (Kraken y CoinGecko no llegan gratis a la profundidad que pides). Ya se usa en este proyecto para acciones/índices según `docs/02`, así que no es una fuente completamente nueva al ecosistema — es extender un uso ya validado a un dominio donde hoy no se usa. Ninguna otra fuente nueva parece necesaria: macro y TVL cripto ya dan profundidad completa gratis con lo que ya tenemos.

## Orden de implementación propuesto (sin escribir código todavía)

1. `engine/macro/backfill.py` (o una función `historize_all()` en el propio `adapt_macro`) — recorre toda la serie FRED ya descargada.
2. Lo mismo para TVL de DefiLlama en `engine/crypto/`.
3. `engine/technical/fetch_yahoo.py` (fetcher nuevo, mismo patrón `_data/` que los demás) + extender `indicators.py`/`score.py` con una variante que calcule la serie completa de SMA/RSI/ATR/volatilidad sobre el histórico backfillado, no solo el último punto.
4. Adaptador de Data Contract para cada uno de los tres anteriores, reutilizando `_write_metric_rows()` sin tocarla.
5. Equity vía Alpha Vantage, cuando se resuelva la cuota.

Ningún paso de este orden modifica Power BI, la Web App, el Thesis Ledger de acciones, ni el flujo de noticias — quedan exactamente donde están hoy.
