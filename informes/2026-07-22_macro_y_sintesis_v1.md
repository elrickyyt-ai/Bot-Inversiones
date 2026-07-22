# Informe — Motor Macro v1 (Fase 5) y síntesis cruzada con Fundamentales + Técnico

**Fecha del dato:** 2026-07-22 · **Motor:** `engine/macro/` · **Fuente:** FRED (EE.UU. + Eurozona)

## Régimen por región

| Región | Inflación interanual | Tipos del banco central | Régimen estimado | Confidence |
|---|---|---|---|---|
| EE.UU. | 3,46% (objetivo 2%) | Fed en 3,63%, estable últimos 6 meses tras un ciclo de recortes | **Expansión con inflación pegajosa** — desempleo bajando (4,2%), curva 10Y-2Y no invertida (+0,37%): sin señal de recesión | 100% |
| Eurozona | 2,73% (objetivo 2%) | BCE subió de 2,00% a 2,25% en los últimos ~3 meses, tras un año plano/a la baja | **Pivote hawkish reciente** — la Fed sigue en pausa, el BCE ya empezó a subir: política monetaria divergente entre ambos bloques | 60% (gap: sin desempleo ni curva de tipos de la Eurozona en esta v1) |

## Corrección de un dato propio

En la sesión anterior cité, vía búsqueda web, una inflación del "4,2% interanual, la mayor desde 2023". Contra la fuente primaria (FRED) ahora mismo, la cifra real de EE.UU. es **3,46%** — la de 4,2% probablemente correspondía a otro país o índice mencionado en aquellos resultados de búsqueda, no a EE.UU. Lo dejo corregido aquí explícitamente: un dato de una búsqueda web genérica no tiene la misma fiabilidad que una serie oficial verificada, y cuando entran en conflicto, gana la fuente primaria.

## HECHOS vs. INTERPRETACIÓN vs. HIPÓTESIS (aplicando el marco del proyecto)

**HECHOS (verificados, FRED + Kraken + CoinGecko):**
- Los tipos de interés en EE.UU. y la Eurozona están en niveles altos para el estándar de la última década (3,63% y 2,25% respectivamente), con el BCE acabando de subirlos.
- Los 6 criptoactivos analizados tienen su market cap y su precio cerca de mínimos de 365 días (motor de fundamentales) y están por debajo de su SMA200 (motor técnico).
- No hay señal de recesión en EE.UU. (curva no invertida, desempleo bajando).

**INTERPRETACIÓN (mía, razonable pero no un hecho):**
- Un entorno de tipos altos y un BCE recién endurecido reduce el atractivo relativo de activos sin rendimiento (como la mayoría de las criptomonedas) frente a activos que sí pagan interés — es una explicación macro plausible para la debilidad de precio observada en los tres activos con más peso de tu cartera.
- El hecho de que **no** haya señal de recesión sugiere que la debilidad de precio cripto no viene de un miedo generalizado a una crisis económica, sino más bien de condiciones de liquidez más restrictivas.

**HIPÓTESIS (sin confirmar, y que el proyecto no debe presentar como más que eso):**
- Que esta divergencia de política monetaria (Fed en pausa, BCE subiendo) se mantenga o se revierta en los próximos meses — no hay forma de saberlo con los datos disponibles hoy, y **no lo voy a predecir como si lo supiera**.

## Qué añade esto que los otros dos motores no daban

Fundamentales y técnico, cada uno por separado, mostraban "esto está barato/deprimido dentro de su propio rango reciente" — pero ninguno explicaba **por qué**. El motor macro aporta un motivo de fondo razonable (tipos altos, liquidez más restrictiva) sin necesidad de inventar una causa. Esto es exactamente el tipo de conexión entre dominios que en la Fase 7 (Motor de Razonamiento) se automatizará — de momento lo hago yo a mano, explicando el razonamiento paso a paso.

## Limitaciones explícitas de esta v1

- Sin PMI/ISM, ventas minoristas, ni confianza del consumidor (quedan para siguiente iteración si aportan señal adicional).
- Sin desempleo ni curva de tipos de la Eurozona (gap documentado).
- La regla de clasificación de régimen es una heurística explícita de 4 señales, no un modelo econométrico — es auditable pero simple a propósito.
