# Informe — Equity Fundamentals Engine v1 (Fase 2, Bloque B)

**Fecha:** 2026-09-03 (cotización del 2026-09-02) · **Activos:** IBM, NVDA, XOM · **Fuente:** Alpha Vantage (conector MCP, cuenta del usuario) · **Motor:** `engine/equity/score.py`

## Tabla comparativa

| | IBM | NVDA | XOM |
|---|---|---|---|
| Precio | $231,70 | $224,41 | $164,15 |
| P/E · PEG | 20,57 · 2,44 | 27,95 · 0,565 | 20,70 · 1,26 |
| Margen beneficio | 15,5% | 63,7% | 9,1% |
| ROE | 34,5% | 117,2% | 12,6% |
| Crecimiento ingresos YoY | +1,1% | +105,9% | +44,1% |
| Crecimiento BPA YoY | **-1,8%** | +127,8% | +112,8% |
| Beta | 0,705 | 2,215 | 0,173 |
| Posición rango 52 semanas | 25,6% | 83,6% | 85,6% |
| vs. SMA50 / SMA200 | por debajo / por debajo | por encima / por encima | por encima / por encima |
| Últimos 8 trim.: aciertos/fallos | 7/0 | 8/0 | 7/1 |
| Última sorpresa de resultados | 0,0% (en línea) | +6,22% | **-4,35% (falló)** |
| Precio objetivo (upside) | $244,91 (+5,7%) | $323,42 (+44,1%) | $169,68 (+3,4%) |
| Confluencia técnica | bajista | alcista | mixta |

## Lectura por activo

- **NVDA**: el más fuerte de los tres en casi todas las dimensiones — márgenes y ROE extraordinarios, crecimiento de ingresos superior al 100% interanual, 8 de 8 trimestres batiendo el consenso, y confluencia técnica alcista (por encima de ambas medias). El P/E de 27,95 parece alto en aislado, pero el PEG de 0,565 (por debajo de 1) sugiere que el crecimiento lo justifica — no se puede juzgar la valoración de NVDA con el mismo criterio que una empresa de crecimiento lento. Beta de 2,215: el doble de volátil que el mercado general.
- **IBM**: el más débil técnicamente — por debajo de su SMA50 y SMA200, en el percentil 25,6% de su rango de 52 semanas (más cerca del suelo que del techo), y con **crecimiento de BPA interanual negativo** (-1,8%) pese a que los ingresos sí crecen levemente. El PEG de 2,44 es el más caro de los tres en relación a su crecimiento. Dato a favor: 7 de 7 trimestres con sorpresa positiva o en línea, nunca ha fallado el consenso en este periodo.
- **XOM**: caso mixto y el más interesante de señalar. El crecimiento de BPA interanual (+112,8%) parece espectacular, pero **el último trimestre reportado falló el consenso por -4,35%** — la cifra de crecimiento anual está dominada por una comparación contra una base baja de hace un año, no por el momento actual. Es exactamente el tipo de contradicción entre "la métrica anual se ve bien" y "el dato más reciente decepcionó" que conviene señalar en vez de promediar. Beta muy baja (0,173): el más defensivo de los tres, coherente con ser una petrolera integrada de gran tamaño.

## HECHO vs. INTERPRETACIÓN

**HECHO:** los tres datos de mercado y fundamentales vienen de Alpha Vantage, verificados en esta sesión (no de la sesión anterior de Cowork, aunque coinciden con los que allí se citaron para NVDA — buena señal de consistencia entre fuentes).

**INTERPRETACIÓN (mía):** la divergencia entre el crecimiento anual de BPA de XOM (+112,8%) y su última sorpresa trimestral negativa (-4,35%) sugiere que el mercado energético puede estar normalizándose desde una base de comparación inusualmente baja — no es una predicción de hacia dónde va el precio, solo una lectura de por qué esas dos cifras aparentemente contradictorias conviven.

## Explícitamente fuera de esta v1

- Sin Debt/Equity, Net Debt/EBITDA ni FCF (balance/cash flow no consultados en esta v1, ver `engine/equity/README.md`).
- Sin comparativa sectorial — los tres pertenecen a sectores demasiado distintos para comparar múltiplos directamente sin normalizar.
- Sin integración todavía con el motor de scoring consolidado (`engine/scoring/`) ni con el motor de razonamiento (`engine/reasoning/`) — son cripto-only hasta ahora; extenderlos a acciones es el siguiente paso natural.
