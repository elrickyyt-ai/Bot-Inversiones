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

**Frontera backfill/incremental**: `fetch_backfill.py` descarga solo hasta el día ANTERIOR a la primera vela ya cacheada de Kraken (frontera exclusiva, recalculada en cada ejecución) -- nunca la misma fecha con dos fuentes. `adapt_technical_backfill()` (Data Contract) vuelve a aplicar esa misma frontera de forma defensiva al escribir. Fuente = `"Coinbase"` en las filas del backfill, `"Kraken"` en las del flujo incremental -- honesto sobre el cambio de fuente en esa fecha, no oculto.

**Métrica nueva**: `volumen` (unidad `"unidades"`, no el ticker del activo -- evita que `qa.py` marque una misma métrica con 6 unidades distintas). Añadida también a `adapt_technical()` ("hoy"), no solo al backfill, para que ambos flujos no diverjan en qué métricas existen.
