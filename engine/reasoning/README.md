# Motor de Razonamiento (v1)

Fase 7 — el motor central que la Fase 0 describió así: *"No quiero una simple suma ponderada. Quiero que detecte contradicciones, convergencias, divergencias."* Hasta ahora esa síntesis la hacía yo a mano en los informes; este motor la automatiza con reglas fijas y documentadas (no un modelo generando la conclusión libremente).

## Uso

```
python3 engine/reasoning/thesis.py
```

Requiere los mismos datos descargados que `engine/scoring/consolidate.py`.

## Qué hace

1. Reúne fundamental (tokenomics), técnico, macro y noticias por activo (igual que la Fase 6).
2. Clasifica cada dominio en un cubo simple (percentil bajo/medio/alto; técnico alcista/bajista/mixto).
3. Aplica reglas explícitas de convergencia/divergencia entre fundamental y técnico — documentadas en el propio código, no aprendidas.
4. Hereda y propaga las advertencias de calidad de datos de los motores anteriores (ej. DOT) — reduce el `confidence_pct` de la tesis en vez de ignorarlas.
5. Hereda contradicciones ya detectadas en noticias (ej. XRP: catalizador regulatorio positivo vs. flujos de ETF negativos).
6. Genera Bull/Base/Bear case y "factores que invalidarían la tesis" — plantilla del Paso 18 de la Fase 0.

## Lo que NO hace todavía

- No decide comprar/vender/mantener — el proyecto excluyó deliberadamente esa conclusión desde la Fase 0.
- No pondera domains entre sí más allá de la regla fundamental↔técnico — macro y noticias se presentan como contexto/hallazgo, no se fusionan numéricamente.
- El Thesis Ledger (`ledger.py`) solo cubre cripto — extenderlo a acciones necesitaría una serie de precios diaria para calcular volatilidad histórica, que hoy no se descarga para `engine/equity/`.

## Extensión a acciones (`build_thesis_equity`)

Mismas reglas de convergencia/divergencia, aplicadas a `engine/equity/score.py` en vez de a cripto+técnico. Diferencia declarada: el dominio "técnico" es un proxy simplificado (SMA50/SMA200 + sorpresa de resultados, ya calculado por el propio motor de acciones), no el motor técnico completo con RSI/MACD/ATR. Cobertura de dominios 2/4 (fundamental + técnico-proxy), sin macro-por-activo ni noticias todavía. Incluye una regla nueva, específica de acciones: detecta contradicción cuando el crecimiento de BPA interanual es fuerte (>20%) pero el último trimestre reportado falló el consenso — automatiza lo que antes se señalaba a mano (ver `informes/2026-09-03_tesis_acciones_v1.md`, caso XOM).
