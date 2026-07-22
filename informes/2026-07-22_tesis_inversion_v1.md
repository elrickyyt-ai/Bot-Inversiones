# Informe — Tesis de Inversión v1 (Fase 7, Motor de Razonamiento)

**Fecha:** 2026-07-22 · **Motor:** `engine/reasoning/thesis.py` · **Activos:** BTC, ETH, ADA, SOL, DOT, XRP

Primera vez que el sistema, y no yo a mano, detecta las relaciones entre dominios. Reglas fijas y documentadas en el código — nada de esto lo decide un modelo libremente.

## Tabla de tesis

| Activo | Relación fundamental↔técnico | Hallazgo adicional | Confidence |
|---|---|---|---|
| BTC | **Divergencia**: fundamental cerca de mínimos 365d, técnico ya alcista (3/4) | — | 80% |
| ETH | **Divergencia**: mismo patrón que BTC | TVL también en mínimos (8,8%) | 80% |
| ADA | **Convergencia bajista**: fundamental y técnico (1/4) alineados | Dilución por encima de la media (FDV/MCap 1,21) | 80% |
| SOL | Sin convergencia ni divergencia clara (técnico 2/4, zona neutral) | — | 80% |
| DOT | **Convergencia bajista** | Confidence reducido por incidencia de datos ya detectada en Fase 2 | **45%** |
| XRP | Sin convergencia ni divergencia clara | **Contradicción heredada de Fase 4** (catalizador regulatorio positivo vs. flujos ETF negativos) | 80% |

## Lo más interesante: BTC y ETH en divergencia, no en convergencia

A diferencia de ADA y DOT (donde fundamentales y técnico están alineados a la baja), **BTC y ETH muestran una divergencia real**: siguen cerca de mínimos de 365 días en fundamentales, pero el técnico ya da 3 de 4 señales alcistas. El motor lo señala explícitamente como ambiguo — *"posible giro temprano, o rebote técnico dentro de una tendencia de fondo aún débil, no se puede distinguir con los datos actuales"* — en vez de forzar una lectura limpia. Esto es exactamente el tipo de matiz que se perdía cuando mirábamos cada motor por separado.

## DOT: la confianza baja de verdad, no solo se menciona

El Confidence de la tesis de DOT es 45% (frente al 80% del resto) porque el motor multiplica el confidence técnico por el Data Quality fundamental (que ya venía penalizado por la incidencia de datos detectada en la Fase 2). La penalización se propaga de extremo a extremo por el sistema, no se queda en un aviso aislado en un informe antiguo.

## Qué falta para que esto sea una Tesis de Inversión completa (Fase 0, punto 21)

Esta v1 no tiene todavía **memoria histórica**: no guarda la tesis de hoy para compararla dentro de 30/90/180 días contra lo que realmente ocurra con el precio — eso es lo que la Fase 0 llama el Thesis Ledger, y es el siguiente paso natural una vez que hay algo que registrar.
