# Informe — Scoring Consolidado v1 (Fase 6)

**Fecha:** 2026-07-22 · **Motor:** `engine/scoring/consolidate.py` · **Activos:** BTC, ETH, ADA, SOL, DOT, XRP

## Qué es y qué NO es esto

Una **ficha consolidada** por activo que reúne lo que cada motor (fundamentales, técnico, macro, noticias) ya calculó por separado, con su propio Confidence y Data Quality. **No es una señal de compra/venta ni una nota única 0-10.** Colapsar los cuatro dominios en un solo número sería repetir el error que la propia Fase 0 señaló desde el principio: *"no quiero una simple suma ponderada"*. Detectar si los dominios convergen o se contradicen es trabajo de la Fase 7 (Motor de Razonamiento), que no está construida todavía — hoy solo se consolida y normaliza.

## Ficha por activo

| Activo | MCap percentil 365d | TVL percentil 365d | Dilución (FDV/MCap) | Sesgo técnico | RSI(14) | Posición rango 90d | Cobertura dominios | Data Quality global |
|---|---|---|---|---|---|---|---|---|
| BTC | 11,0% | n/a | 1,00 | mixto (3/4 alcistas) | 58,1 | 32,1% | 3/4 | 80% |
| ETH | 11,0% | 8,8% | 1,00 | mixto (3/4 alcistas) | 62,9 | 44,9% | 3/4 | 80% |
| ADA | 2,9% | 0,0% | 1,207 | mixto (1/4 alcistas) | 48,6 | 16,5% | 3/4 | 80% |
| SOL | 10,1% | 5,8% | 1,082 | mixto (2/4 alcistas) | 54,3 | 48,6% | 3/4 | 80% |
| **DOT** | 0,3% | n/a ⚠️ | 1,00 | mixto (1/4 alcistas) | 37,3 | 1,0% | 3/4 | **45%** |
| XRP | 3,4% | n/a | 1,601 | mixto (2/4 alcistas) | 51,1 | 17,3% | **4/4** | 80% |

**Cobertura de dominios:** ningún activo llega a 4/4 salvo XRP (el único con informe de noticias/sentimiento hasta ahora) — el resto está en 3/4 porque el motor de noticias aún no cubre BTC/ETH/ADA/SOL/DOT. Esto queda explícito en la ficha, no oculto.

**DOT sigue arrastrando su Data Quality reducida (45% vs. 80% del resto)** — la ficha consolidada propaga automáticamente la incidencia de datos que el motor de fundamentales detectó, en vez de diluirla al mezclarla con los demás dominios. Es la prueba de que el diseño de "confidence/data quality por dominio, nunca un número único inventado" funciona de extremo a extremo.

## Lo que esta ficha permite ver de un vistazo, sin decidir por ti

- **XRP y DOT** son los dos con menor percentil de market cap (3,4% y 0,3%) — los más "baratos" relativos a su propio histórico de 365 días, pero DOT con calidad de dato dudosa.
- **BTC y ETH** son los únicos con 3 de 4 señales técnicas alcistas simultáneamente.
- **ADA** combina el sesgo técnico más débil (1/4) con el TVL más bajo (0,0% — en su mínimo de 365 días) — dos dominios distintos apuntando en la misma dirección para este activo en concreto.

## Próximo paso natural (Fase 7)

Esta ficha es exactamente el insumo que la Fase 7 necesitará para automatizar lo que hasta ahora hemos hecho a mano en los informes de síntesis (macro↔técnico↔fundamentales): leer estas cuatro columnas por activo y señalar dónde convergen y dónde se contradicen.
