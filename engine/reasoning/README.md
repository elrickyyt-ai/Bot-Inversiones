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
- No tiene memoria histórica todavía (Fase 0, punto 21: comparar la tesis de hoy contra lo que ocurra después) — ese es el siguiente paso natural, el Thesis Ledger.
