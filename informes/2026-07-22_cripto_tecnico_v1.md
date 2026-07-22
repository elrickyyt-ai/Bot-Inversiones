# Informe — Motor Técnico v1 (Fase 3)

**Fecha del dato:** 2026-07-22 · **Activos:** BTC, ETH, ADA, SOL, DOT, XRP · **Motor:** `engine/technical/` (Python puro, sin numpy/pandas — no disponibles en este entorno) · **Fuente:** Kraken OHLC diario (~720 velas, ~2 años)

## Resumen ejecutivo

Los seis activos muestran un patrón consistente: **por encima de su media de 20-50 días (rebote de corto plazo en marcha) pero por debajo de su media de 200 días en todos los casos** (tendencia de fondo todavía bajista). Ninguno alcanza confluencia plena (4/4 señales alineadas) — el motor lo reporta como "mixto" en vez de forzar una lectura limpia que no existe.

Esto **converge** con lo ya visto en el informe de fundamentales cripto (`2026-07-20_cripto_fundamentales_v1.md`): allí el market cap de los seis estaba cerca de mínimos de 365 días. Aquí, el técnico añade matiz: hay un repunte de corto plazo sobre esos mínimos, pero la estructura de largo plazo (SMA200) no lo confirma todavía. Es exactamente el tipo de lectura cruzada entre dominios que el futuro Motor de Razonamiento (Fase 7) automatizará.

## Tabla comparativa

| Activo | Precio | vs SMA50 | vs SMA200 | RSI(14) | MACD hist. | Volatilidad 30d anualizada | Posición rango 90d | Confluencia |
|---|---|---|---|---|---|---|---|---|
| BTC | 57.245 | por encima | por debajo | 58,1 | + | 31,1% | 32,1% | 3/4 alcistas |
| ETH | 1.662 | por encima | por debajo | 62,9 | + | 44,4% | 44,9% | 3/4 alcistas |
| ADA | 0,1449 | por debajo | por debajo | 48,6 | + | 71,3% | 16,5% | 1/4 alcistas |
| SOL | 67,95 | por encima | por debajo | 54,3 | − | 46,5% | 48,6% | 2/4 alcistas |
| DOT | 0,7163 | por debajo | por debajo | 37,3 | + | 45,3% | 1,0% | 1/4 alcistas |
| XRP | 0,9731 | por debajo | por debajo | 51,1 | + | 35,4% | 17,3% | 2/4 alcistas |

## Lecturas destacadas

- **DOT** es el más débil técnicamente de los seis: por debajo de SMA50 y SMA200, RSI en 37,3 (zona de debilidad, sin llegar a sobreventa extrema) y en el percentil 1% de su rango de 90 días — prácticamente en el mínimo reciente. Coincide con que fue también el activo con la incidencia de calidad de datos en el informe de fundamentales — dos motores independientes señalando que DOT merece más atención antes de sacar conclusiones.
- **ADA** es el único de los seis con una estructura de mínimos decrecientes clara ("Lower Lows consecutivos") — el resto no muestra una estructura de swings limpia en ninguna dirección, solo ruido de corto plazo.
- **BTC y ETH** son los que más cerca están de una confluencia alcista de corto plazo (3 de 4 señales), aunque ambos siguen por debajo de su SMA200.
- **Volatilidad:** ADA es, con diferencia, el más volátil (71,3% anualizado) — más del doble que BTC (31,1%). Relevante para cualquier futuro dimensionamiento de posición (Fase 9).

## Limitaciones explícitas de esta v1

- Sin ADX (fuerza de tendencia) ni niveles de soporte/resistencia explícitos más allá del rango de 90 días — quedan para una siguiente iteración si aportan señal adicional a la confluencia.
- Sin volumen relativo, OBV ni VWAP todavía (dominio Volumen y Microestructura de la Fase 0, no incluido en esta primera versión).
- La detección de estructura de swings (Higher High/Lower Low) usa una ventana fija de 10 velas — es una heurística simple, no un algoritmo de price action validado.
