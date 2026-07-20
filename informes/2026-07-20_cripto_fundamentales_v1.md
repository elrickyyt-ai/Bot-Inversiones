# Informe — Crypto Fundamentals Engine v1

**Fecha:** 2026-07-20 · **Activos:** BTC, ETH, ADA, SOL, DOT, XRP · **Motor:** `engine/crypto/` (código en el repo, datos no versionados — reproducible)

## Resumen ejecutivo

Los seis activos muestran su **market cap cerca del mínimo de los últimos 365 días** (entre el percentil 0,3% y el 11%), coherente con la fase de mercado bajista ya detectada de forma independiente en el análisis retrospectivo de `CARTERA_A`. El TVL (actividad económica on-chain) de ETH, SOL y ADA está igual de deprimido. **XRP y ADA son los que muestran mayor riesgo de dilución pendiente** (parte relevante de su oferta máxima aún no está en circulación).

## Tabla comparativa

| Activo | % supply circulante/máx. | FDV/MCap (dilución) | Percentil MCap 365d | TVL actual (USD) | Percentil TVL 365d | Commits GitHub 4sem | Data Quality |
|---|---|---|---|---|---|---|---|
| BTC | 95,5% | 1,00 (sin dilución pendiente) | 11,0% | n/a (no es plataforma DeFi) | n/a | 108 | 80% |
| ETH | 100,0% | 1,00 | 11,0% | 41.483M | 8,8% | 41 | 80% |
| ADA | 82,9% | 1,207 | 2,9% | 70M | 0,0% | 0 ⚠️ verificar | 80% |
| SOL | 92,4% | 1,082 | 10,1% | 4.941M | 5,8% | 171 | 80% |
| DOT | 80,7% | 1,00 | 0,3% | 0 ⚠️ | null | 0 ⚠️ | **45% — posible incidencia de datos** |
| XRP | 62,5% | 1,601 (la mayor dilución pendiente) | 3,4% | n/a | n/a | 4 | 80% |

⚠️ **DOT**: CoinGecko/DefiLlama devuelven TVL=0 y actividad de desarrollo=0, lo cual no es creíble para una red de ese tamaño — probablemente un error de mapeo del repositorio/chain en la fuente, no una ausencia real de actividad. Dato marcado como no fiable, Data Quality reducido, **no se usa para ninguna conclusión**.

## Lectura por activo

- **XRP**: de los seis, el que tiene más oferta pendiente de circular (37,5% del máximo aún no emitido/liberado) y el FDV/MCap más alto (1,6) — quien compre hoy se expone a que esa emisión futura presione el precio si la demanda no crece al mismo ritmo. Esto es un dato objetivo de tokenomics, no una predicción de precio.
- **ADA**: dilución moderada (FDV/MCap 1,21) y el TVL más bajo en términos relativos de los tres con ecosistema DeFi medido (percentil 0%, es decir, el valor actual es el más bajo de los últimos 365 días). El commit count en 0 en las últimas 4 semanas llama la atención pero no se marca como incidencia porque el resto de señales de desarrollo (3.757 stars) sí son coherentes con un proyecto activo — recomendable verificarlo con otra fuente antes de sacar conclusiones.
- **BTC y ETH**: sin presión de dilución (toda o casi toda la oferta ya en circulación). Es la lectura de tokenomics más "limpia" de los seis.
- **SOL**: mayor actividad de desarrollo de los seis (171 commits/4 semanas) pese a tener también el market cap y TVL cerca de mínimos de 365 días — divergencia entre "el precio/actividad económica está deprimida" y "el desarrollo del protocolo sigue siendo intenso", que podría interpretarse como una señal a vigilar (no una recomendación).

## Limitaciones explícitas de esta v1

- Sin ratio de staking ni direcciones activas — quedan como mejora futura (ver `docs/02-fase1-gaps-y-roadmap-fuentes.md`).
- Sin universo de peers cripto: los percentiles son contra el histórico propio del activo, no contra otras criptomonedas.
- Las métricas sin serie histórica (dilución, actividad de desarrollo) son un valor de referencia puntual, no un percentil — se muestran así deliberadamente en vez de forzar una comparación que no existe.
