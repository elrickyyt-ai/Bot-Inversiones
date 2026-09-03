# Informe — Tesis de Inversión, acciones v1 (Fase 7 extendida a Bloque B)

**Fecha:** 2026-09-03 · **Motor:** `engine/reasoning/thesis.py` → `build_thesis_equity()` · **Activos:** IBM, NVDA, XOM

Extensión del motor de razonamiento (hasta ahora solo cripto) a las tres acciones de prueba, reutilizando las mismas reglas de convergencia/divergencia — con una diferencia declarada: **no hay motor técnico independiente para acciones todavía**, así que el dominio "técnico" es un proxy simplificado (SMA50/SMA200 + sorpresa del último trimestre) que ya calculaba `engine/equity/score.py`, no el RSI/MACD/ATR completo que sí tiene cripto.

## Resultado por activo

| Activo | Relación posición 52s ↔ confluencia | Hallazgo adicional | Confidence |
|---|---|---|---|
| IBM | **Convergencia bajista**: cerca de mínimos de 52 semanas y confluencia técnica bajista alineadas | PEG 2,44 — valoración exigente para su crecimiento | 75% |
| NVDA | **Convergencia alcista**: cerca de máximos de 52 semanas y confluencia técnica alcista alineadas | Sin advertencias | 75% |
| XOM | Sin convergencia ni divergencia clara (confluencia mixta) | **Contradicción detectada automáticamente**: BPA interanual +112,8% vs. último trimestre fallado (-4,35%) | 75% |

## Lo más relevante: la contradicción de XOM ya no la escribo yo a mano

En el informe de fundamentales de acciones (2026-09-03) señalé manualmente que el crecimiento anual de XOM estaba "dominado por una base de comparación baja, no por el momento actual". El motor de razonamiento **ahora detecta esto solo**, con una regla explícita (crecimiento de BPA interanual > 20% + última sorpresa de resultados negativa → contradicción) — es la validación de que la regla generaliza más allá del caso concreto que la motivó.

## Limitaciones explícitas de esta extensión

- Cobertura de dominios 2/4 (fundamental + técnico-proxy), frente a hasta 4/4 en cripto — sin macro por activo (se usa el mismo contexto compartido) ni noticias todavía.
- El "técnico" de acciones no es comparable en profundidad al motor técnico completo de `engine/technical/` — no tiene RSI, MACD, ATR ni volatilidad histórica, por eso tampoco se ha extendido el Thesis Ledger a acciones en esta v1 (necesitaría una serie de precios diaria que hoy no se descarga para acciones).
- Sin cobertura de noticias — un evento reciente no capturado por este motor podría invalidar cualquiera de las tres tesis sin que el sistema lo detecte.
