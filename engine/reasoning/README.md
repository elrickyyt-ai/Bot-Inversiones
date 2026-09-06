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

## Evidencia y validez analítica (P1, desde 2026-09-06)

Antes, la cobertura de una tesis era literalmente `sum([True, True, True, news])`: tres constantes. Sólo podía dar `3/4` o `4/4`, pasara lo que pasara con los datos. El sistema ya conocía su cobertura y su frescura reales (`engine/contract/cobertura.py`) y la tesis seguía publicando una ficticia.

Cada tesis declara ahora **de qué evidencia depende y con qué papel** (`EVIDENCIA_CRYPTO` / `EVIDENCIA_EQUITY`):

| Papel | Qué significa | Si está caducada |
|---|---|---|
| `REQUERIDA` | una regla de clasificación se bifurca por su valor, o entra en `confidence_pct` | **invalida** la tesis |
| `PUBLICADA` | su valor aparece como cifra o afirmación en la salida, pero ninguna regla depende de él | advertencia |
| `CONTEXTO` | contextualiza sin ser del activo (régimen macro) | advertencia |

La distinción es la que evita el falso positivo obvio: `pe_ratio` de IBM lleva 47 sesiones de retraso y sólo aparece en el texto del `bear_case`. Anular por eso una tesis cuyo técnico y cuya regla de contradicción están al día sería un error tan grave como ignorarlo.

**`validez_evidencia`** resume el resultado: `VALID` (todo lo requerido dentro de su cadencia), `INVALID` (algo requerido `STALE` o sin fecha) o `UNKNOWN` (algo requerido sin cadencia declarada — que **no** es lo mismo que estar al día). Cuando no es `VALID`, `confidence_pct` vale `None`, nunca un número reducido: «no hay base para calcular la confianza» y «hay poca confianza» son afirmaciones distintas, y un número pequeño invitaría a seguir usándolo. `schema.py` rechaza la combinación en el propio validador, no sólo aquí.

**Hallazgo del propio mapa**: escribir la lista de evidencias destapó tres cantidades de las que el razonamiento depende y que nadie había declarado — `earnings_growth_yoy_pct` (bifurca la regla de contradicción de acciones), `desempleo_pct` y `spread_10y2y_pct` (alimentan el `regimen_estimado` que la tesis publica como hecho). Las dos últimas se descargan de FRED y **no llegan al Data Contract**. Sus cadencias quedaron declaradas en `cadencias.py`; emitirlas al contrato sigue pendiente.

**Las entradas con entidad `US`/`EA` son la relación implícita que P2 debe modelar.** `build_thesis()` aplica el contexto macro de EE.UU. y de la Eurozona a los once activos por igual, sin distinguirlos. Aquí queda escrita por primera vez de forma explícita; cuando exista el Knowledge Model, esta tabla a mano se sustituye por una consulta de `EXPOSED_TO`.
