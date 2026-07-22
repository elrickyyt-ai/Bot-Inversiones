# Technical Analysis Engine (v1)

Motor técnico — Fase 3, dominio Market Behavior de la Fase 0. Implementado en Python puro (sin `numpy`/`pandas`, no disponibles en este entorno de ejecución).

## Uso

```
python3 engine/technical/fetch_data.py   # descarga OHLC diario a engine/technical/_data/ (no versionado)
python3 engine/technical/score.py        # calcula indicadores y confluencia, imprime JSON
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

## Fuente de datos

Kraken OHLC público (`/0/public/OHLC`, `interval=1440`), sin clave. Da hasta ~720 velas diarias (~2 años) — coherente con la limitación ya documentada en `docs/02-fase1-gaps-y-roadmap-fuentes.md` para el resto de motores cripto.
