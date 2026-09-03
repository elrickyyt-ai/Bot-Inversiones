# Informe — News/Sentiment Engine v2 (NEWS_SENTIMENT de Alpha Vantage)

**Fecha:** 2026-09-03 · **Fuente:** `NEWS_SENTIMENT` (Alpha Vantage, conector MCP) · **Activos consultados:** NVDA, XRP (2 llamadas, ver gestión de cuota en `engine/news/README.md`)

## Corrección importante sobre XRP y la Clarity Act

El informe de julio (`2026-07-22_noticias_sentimiento_v1.md`) decía que el Senado había "aprobado" la Clarity Act en mayo de 2026. Con datos reales de agosto encontrados ahora, eso era **incompleto**: lo que ocurrió en mayo fue una aprobación a nivel de **Comité** Bancario del Senado (15-9) — un paso previo, no la ley aprobada. Un titular de Decrypt.co del 7 de agosto lo deja claro: **"XRP at a Crossroads as Senate Punts on Clarity Act"** — el Senado completo **aplazó** la votación. El catalizador regulatorio que en julio interpretamos como "ya ocurrido" sigue, de hecho, pendiente de resolución en el Senado pleno.

## Otros hallazgos reales de XRP (24 jul – 2 sep 2026)

- **Incidente de seguridad (12 ago, Decrypt.co, relevancia 0,89, sentimiento levemente bajista)**: "XRP Bridge Drained After Software Treats Fake Deposits as Real" — un puente relacionado con XRP (FXRP de Flare) sufrió una vulnerabilidad. No verificado más allá de este titular; si se quiere usar como hecho hay que profundizar en la fuente original antes de darlo por bueno.
- **XRP tocó mínimo de 52 semanas cerca de $1 (15 ago, Motley Fool)** — coherente con lo que ya habíamos visto en el motor de fundamentales de julio (percentil de mercado cerca de mínimos de 365 días).
- Distribución de sentimiento de los 50 artículos más recientes sobre XRP: 28 neutrales, 18 algo-alcistas, 3 alcistas, 1 algo-bajista — sin una inclinación fuerte en ningún sentido.
- Volumen alto de piezas de opinión/predicción de Motley Fool ("¿Podría XRP cuadruplicarse?", "Predicción: XRP caerá un 50%") — contenido de Prioridad 3-4 en la jerarquía de fuentes (opinión de un contribuidor, no hecho verificado), a tratar como tal.

## NVDA: ruido de bajo valor informativo, con algunas señales reales

La mayoría de los artículos eran notas automáticas de tipo "el fondo X aumentó/redujo su posición en NVDA" (MarketBeat, basadas en filings 13F) — poca señal. Entre el ruido, dos piezas con más contenido: **"Billionaire Dan Loeb Exited Nvidia and Broadcom. Is He Calling the Top in AI Chips?"** (Yahoo Finance) y el contexto de resultados de Broadcom como lectura indirecta de la demanda de chips de IA — ninguna contradice la lectura alcista que ya teníamos de NVDA en fundamentales/técnico, pero tampoco la confirma con fuerza.

## Lo que esto cambia del motor de razonamiento

Con esta corrección, la "contradicción" que el motor de razonamiento tiene registrada para XRP (`engine/reasoning/thesis.py`, `NEWS_FINDINGS`) sigue siendo válida en esencia, pero el texto debería matizarse: no es "catalizador regulatorio ya resuelto vs. flujos negativos", sino "catalizador regulatorio **todavía pendiente en el Senado pleno**, con salidas de ETF y enfriamiento on-chain mientras tanto" — pendiente de actualizar en el código.
