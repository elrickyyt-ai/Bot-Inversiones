# Auditoría de compatibilidad arquitectónica — event studies, reacción histórica y PIT

**Fecha**: 2026-09-07 · **Alcance**: auditoría, no implementación. No se ha construido HERE ni se ha cambiado ninguna fase.
**Código escrito**: solo `tests/test_auditoria_pit_eventos.py` (14 pruebas de demostración, ninguna de producción).
**Verificación**: suite completa 99 tests (85 → 99), `engine/contract/qa.py` PASS.

---

## 0. Resumen ejecutivo

La conclusión de la evaluación es correcta, pero por una razón más fuerte que la que se plantea. **La mayor parte de lo que la investigación externa presenta como arquitectura nueva ya está decidido en la Fase 0 de este proyecto y lleva dos años sin implementarse.** No es material nuevo que haya que encajar: es deuda arquitectónica que la investigación externa nombra bien.

Tres cosas concretas de la Fase 0 (`docs/00-arquitectura-conceptual.md`, PASO 2 y PASO 4):

| Lo que la investigación propone | Lo que la Fase 0 ya decidió | Estado real |
|---|---|---|
| `available_at` / PIT gobernando todo | Capa 2 "EVIDENCE LAYER … timestamp de publicación, timestamp de ingestión, versión as-of (point-in-time)" | **No implementada** |
| Event como entidad económica | "Catalyst Domain: eventos futuros con probabilidad/impacto" | **No implementado** |
| Abnormal / market-adjusted return | "Feedback Loop básico: comparación de tesis pasadas (30/90/180 días) vs. resultado real, **contra benchmark**" | **No implementado** |
| Regime conditioning de la reacción | Capa 9: "detecta qué dominios predicen mejor **en qué régimen macro**" | **No implementada** |
| Evidence Sufficiency | "*Confidence Score* = función de … **el tamaño de muestra histórica disponible**" | **Implementada solo en un sitio** |

El encuadre correcto no es "¿incorporamos HERE?" sino **"la Capa 2 (Evidence) y el Catalyst Domain de la Fase 0 nunca se construyeron, y la investigación externa explica por qué eso importa más de lo que parecía"**.

Y hay un hallazgo que cambia la recomendación práctica: **un primer event study es computable hoy, sin ninguna fuente nueva y con 3 llamadas de API** (§5). Eso mueve "Historical Reaction Profile" de *prematuro* a *el primer bloque que de verdad valida la arquitectura*.

---

## 1. Aviso previo: la numeración P6/P6.1/P6.2 no existe en este repositorio

Esto hay que resolverlo antes que nada, porque la evaluación pide explícitamente comprobar si la reordenación rompe decisiones previas. **Rompe.**

La evaluación habla de `P6 Economic Impact`, `P6.1 Materiality (CLOSED)`, `P6.2 Magnitude`, un "Evidence/Causal Engine", "Narrative" y "lo que acabamos de descubrir en P6.1". Búsqueda literal en todo el repositorio (código, docs, informes):

```
materialidad / materiality   0 apariciones
causal                       0
mecanismo / mechanism        0 (solo uso coloquial: "el mismo mecanismo de memoria histórica")
episodio / episode           0
event_id / episode_id        0
available_at / first_tradable_at   0
abnormal / benchmark         0
n_effective / shrinkage      0
```

La numeración vigente, referenciada en `CLAUDE.md`, `docs/03`, `docs/04` y 13 informes:

| Fase | Contenido real | Estado |
|---|---|---|
| Fase 5 | Motor Macro | v1 |
| **Fase 6** | **Scoring consolidado** (`engine/scoring/consolidate.py`) | **v1, cerrada** |
| **Fase 7** | **Motor de Razonamiento / Tesis** (`engine/reasoning/thesis.py`) | **v1, cerrada** |
| **Fase 8** | **Backtesting** (`docs/03`: "un futuro backtesting (Fase 8)") | **sin empezar** |
| Fase 9 | Gestión de cartera | sin empezar |
| Fase 10 | Automatización | sin empezar |

**`CONTRADICTS`.** Adoptar "P6.1 / P6.2 / P6.3" crearía dos sistemas de numeración incompatibles sobre las mismas cifras: `P6.2 = Historical Evidence Layer` colisionaría con `Fase 6 = Scoring consolidado, ya cerrada`. La decisión de la propia evaluación de no renombrar todavía era la correcta.

**Recomendación**: no renumerar. El trabajo descrito no es una subdivisión de la Fase 6 — se reparte entre **la Capa 2 (Evidence) de la Fase 0**, que es transversal y anterior a todas las fases, y **la Fase 8 (backtesting)**, que ya existe y hoy está vacía. Si hace falta un nombre, `Fase 8.0 — Capa de Evidencia Histórica (prerrequisito del backtesting)` encaja sin romper nada.

---

## 2. Clasificación de cada elemento

### 2.1 Timestamps y point-in-time

| Elemento | Estado | Evidencia |
|---|---|---|
| `data_as_of` ≠ `retrieved_at` | **EXISTS** | `engine/contract/schema.py`, validado en las 507.613 filas de `data/metrics/`. Corregido ya dos veces cuando falló (BTC/XRP `fecha_dato`, `adapt_macro()`). |
| `event_occurred_at` | **PARTIAL** | Existe *de facto* como `data_as_of` cuando el dato es un hecho fechado (fin de trimestre, fecha de vela). No está separado conceptualmente. |
| `available_at` | **MISSING (y con un look-ahead real hoy)** | §3 |
| `first_tradable_at` | **MISSING (pero trivial de derivar)** | §5: Alpha Vantage ya da `reportTime` (pre/post-market). |
| Precisión intradía | **PARTIAL** | `data/news/*.json` ya guarda hora exacta (`2026-09-02T21:31:05Z`), pero `schema._parse_date()` la trunca con `s[:10]`. El contrato tiene más precisión de la que valida o usa. |
| `price_move_first` / dirección causal | **MISSING** | Nada distingue "el precio cayó porque salió la noticia" de "la noticia se escribió porque el precio cayó". |
| Snapshots versionados (Knowledge/Evidence/Profile/Regime) | **PREMATURE** | Sin Evidence Layer no hay nada que versionar. La Capa 2 primero. |

### 2.2 Event / Episode

| Elemento | Estado | Evidencia |
|---|---|---|
| Document como unidad | **EXISTS** | `adapt_news()`: `news_id` = sha1 de la URL, una fila por (artículo, activo). 50 filas reales de XRP. |
| **Event ≠ Document** | **MISSING** | `NEWS_FIELDS` no tiene `event_id`. Test: `test_ningun_campo_permite_agrupar_por_hecho_economico`. |
| **Episode (doble conteo)** | **MISSING, y ya está ocurriendo** | En las 50 filas reales de XRP, **7 pertenecen al mismo hilo regulatorio** (Clarity Act, 20-jul → 31-ago). Hoy cuentan como 7 evidencias independientes. |
| Event como dato | **CONTRADICTS la práctica actual** | El único "evento" del sistema es prosa escrita a mano: `NEWS_FINDINGS` en `engine/reasoning/thesis.py:24` es un `dict` con un párrafo hardcodeado para XRP. No es consultable, ni fechable, ni agregable. |
| Taxonomía de 12 clases | **PREMATURE** | De acuerdo con la evaluación. Ver §5: con **una** clase (`earnings_release`) se valida la cadena entera. |

### 2.3 Expectation / Surprise

| Elemento | Estado | Evidencia |
|---|---|---|
| Sorpresa de resultados | **PARTIAL — el dato está, la metodología no** | `earnings_surprise_last_pct` existe en `data/metrics/`. Pero son **3 filas en total** (una por acción), sin historizar. |
| `expected_value` / `actual_value` explícitos | **MISSING en el contrato, EXISTS en la fuente** | Alpha Vantage da `estimatedEPS` + `reportedEPS` + `surprisePercentage`; el adaptador solo escribe el agregado. |
| `expectation_method` (CONSENSUS_PIT / GUIDANCE / …) | **MISSING** | Nada distingue un consenso real de un proxy. |
| "Un proxy no puede presentarse como consenso" | **EXISTS como principio, aplicado en otro sitio** | Es la misma regla de `personas_influyentes.json` ("credibilidad ganada, no asumida") y de `persona_influyente: null` en `adapt_news()`. El principio ya es del proyecto; falta aplicarlo a expectativas. |
| `analyst_target_price` como expectativa | **PARTIAL, con una fecha mal puesta** | El propio adaptador documenta la aproximación, pero sella un consenso de "hoy" con `data_as_of = 2026-06-30`. En un backtest aparecería como conocible 65 días antes de existir. |

### 2.4 Reacción de mercado

| Elemento | Estado | Evidencia |
|---|---|---|
| `raw_return` | **EXISTS** | 50.742 filas de `precio`. IBM/XOM desde 1970, NVDA desde 1999. |
| `market_adjusted_return` | **MISSING — y bloqueado por falta de universo** | No hay ningún índice en `DimAsset`: 11 activos = 6 cripto + 3 acciones + US/EA. Test: `test_no_hay_ningun_benchmark_en_dimasset`. |
| `sector_adjusted_return` | **MISSING** | `DimAsset.sector` existe (TECHNOLOGY / ENERGY / Cripto) pero con 3 acciones no hay agregado sectorial posible. |
| **"Contra benchmark" como decisión** | **EXISTS en la Fase 0, sin implementar** | PASO 4, Versión intermedia, literal. Y beta estaba ya en el MVP ("Risk Domain básico: volatilidad, drawdown, beta"). |
| Veredicto del Ledger | **PARTIAL — hoy es bruto** | `evaluate_pending()` compara variación bruta contra un umbral de volatilidad. Test: +15% bruto → `bull_case`, hiciera lo que hiciera el mercado. |
| `IMPACT` ≠ `REACTION` | **MISSING como separación formal** | Pero §5 demuestra que la distinción es real en los datos del propio proyecto. |
| `reaction_gap` | **MISSING** | Requiere primero el perfil histórico. |

### 2.5 Comparables históricos y suficiencia

| Elemento | Estado | Evidencia |
|---|---|---|
| `HistoricalReactionProfile` | **MISSING** | Nada equivalente. |
| **Evidence Sufficiency** | **PARTIAL — ya tiene precedente en el código** | `engine/crypto/score.py::_pct_in_window()` se niega a calcular con <10 observaciones y **devuelve `None`, no un valor por defecto**. Es exactamente el principio a generalizar, ya escrito y aplicado con consistencia (el backfill de TVL lo respeta punto a punto). |
| Reconocimiento explícito de muestra insuficiente | **EXISTS** | `engine/equity/score.py:110`: `data_quality_pct: 75, # fuente unica, snapshot sin serie historica de fundamentales`. El sistema ya sabe que le falta historia y lo dice. |
| `n_effective` | **MISSING** | |
| Hierarchical shrinkage | **PREMATURE** | Encoger hacia un padre exige tener padre. Con una sola clase de evento no hay jerarquía. Después de §5, no antes. |
| Regime conditioning | **PARTIAL — a un paso, sin fuente nueva** | Ver abajo. |

**Sobre régimen, con precisión.** `regimen_estimado` existe pero solo para "hoy": `adapt_macro_backfill()` lo excluye deliberadamente y con buen criterio ("es una síntesis de hoy, no un dato histórico por fecha"). Ahora bien, `score_us()` clasifica el régimen con **4 señales**, y `historical_series_us()` solo emite **2** (`cpi_yoy_pct` desde 1948, `fed_funds_pct` desde 1954). Las otras dos —`UNRATE` y `T10Y2Y`— **ya se descargan** de FRED (`engine/macro/fetch_data.py:18-27`) y están en `_data/`; simplemente no pasan por el backfill. Etiquetar el régimen históricamente no necesita ninguna fuente nueva: necesita dos líneas más en `historical_series_us()` y decidir si la etiqueta se historiza o se recalcula al vuelo.

### 2.6 Narrativa, sentimiento, GDELT, LLM

| Elemento | Estado | Nota |
|---|---|---|
| Jerarquía Tier 0-7 (hechos → … → LLM arriba) | **EXISTS como principio** | Es la Fase 0 PASO 5: "sistema multiagente completo en modo continuo" excluido; "reglas explícitas y transparentes" en el MVP. La jerarquía formaliza algo ya decidido. |
| Sentimiento relegado | **EXISTS de facto** | La Fase 4 v2 ya usa sentimiento *por ticker* y sin agregar a un promedio, precisamente para no perder el detalle. |
| `narrative_state` (novelty, coverage, framing…) | **PREMATURE** | Dejar sitio, no construir. |
| GDELT | **PREMATURE, y bloqueado** | 429 persistente en este entorno (Fase 4 v2). El código está conservado. Coincido con la evaluación: cobertura/difusión, no verdad económica, y no hace falta para nada de §5. |
| LM / FinBERT / LLM | **PREMATURE** | |
| ALFRED (macro PIT) | **MISSING, pertinente** | FRED revisa series hacia atrás; hoy se usa la última versión, lo que es look-ahead silencioso en macro. Es el mismo problema de §3, en otro dominio. |

---

## 3. Hallazgo con defecto real: look-ahead en la sorpresa de resultados

No es un riesgo teórico. Está en `data/metrics/` ahora mismo.

`adapt_equity()` sella toda la sorpresa de resultados con `fundamental_as_of = LatestQuarter = fiscalDateEnding`:

```
IBM  earnings_surprise_last_pct = 0.0   data_as_of = 2026-06-30
```

Pero esa sorpresa solo fue **conocible** el `reportedDate = 2026-07-22`. **22 días de look-ahead** en IBM; **31 en XOM**; media de 24 y 31 días sobre los 8 trimestres de cada fixture. Y la fuente da ambas fechas en el mismo payload: el adaptador descarta la que importa.

Es el mismo patrón de bug ya corregido dos veces (`datetime.now()` en BTC/XRP, `adapt_macro()`), **pero en la dirección peligrosa**: allí la fecha era demasiado tardía, aquí es demasiado temprana. Una fecha tardía degrada el dato; una temprana lo hace aparecer disponible antes de existir, que es la definición de look-ahead bias.

`qa.py` no podía detectarlo, y no es culpa de `qa.py`: la invariante que valida es `data_as_of ≤ retrieved_at`, y `2026-06-30 ≤ 2026-09-03` pasa sin problema. La invariante que hace falta —"`data_as_of` es la fecha en que el dato fue conocible"— no es expresable con los campos actuales. Por eso `available_at` no es un campo más: es lo que hace verificable la regla.

Demostrado en `TestHallazgoLookAheadEnSorpresaDeResultados` (4 pruebas, una marcada `@expectedFailure` — al corregir el defecto, unittest reportará *unexpected success* y esa es la señal de quitar la marca).

---

## 4. Doble conteo de episodios: ya está ocurriendo

De las 50 filas reales de `data/news/XRP.json`, **7 tratan el mismo hilo regulatorio** (Clarity Act / Senado / claridad regulatoria), entre el 20 de julio y el 31 de agosto. Con el contrato actual son 7 evidencias independientes.

El caso es especialmente ilustrativo porque es justo el que ya obligó a una corrección manual: la Fase 4 v2 tuvo que rectificar la interpretación de julio (aprobación de comité leída como aprobación del Senado). Un `episode_id` habría hecho visible que aquello era **un episodio abierto en curso**, no un hecho resuelto — que es exactamente lo que la corrección tuvo que establecer a mano en `NEWS_FINDINGS`.

---

## 5. El hallazgo que cambia la recomendación: el event study es computable hoy

Verificado **en vivo** el 2026-09-07 (2 llamadas a Alpha Vantage `EARNINGS`, plan gratuito):

```
IBM   123 trimestres   desde 1996-03-31
NVDA  111 trimestres   desde 1999-04-30
```

y **cada trimestre trae los cuatro campos que la investigación pide**:

| Campo de Alpha Vantage | Concepto de la investigación |
|---|---|
| `fiscalDateEnding` | `event_occurred_at` |
| `reportedDate` | `available_at` |
| `estimatedEPS` / `reportedEPS` / `surprisePercentage` | expectativa / realizado / sorpresa escalada |
| **`reportTime`** (`pre-market` / `post-market`) | **`first_tradable_at`**, resoluble sin datos intradía |

`engine/equity/score.py` corta la serie con `earn[:8]` y el adaptador tira todas esas fechas. **El dato PIT lleva ahí desde el principio.**

Cruzado con los precios diarios que el backfill del bloque 4 ya dejó en `data/metrics/` (IBM/XOM 1970→2026, NVDA 1999→2026, 339.816 filas), el resultado sobre eventos reales:

| Activo | reportedDate | reportTime | Sorpresa | 1ª sesión negociable | Retorno bruto 1d |
|---|---|---|---:|---|---:|
| NVDA | 2018-11-15 | post-market | **−2,1%** | 2018-11-16 | **−18,8%** |
| NVDA | 2022-11-16 | post-market | **−18,3%** | 2022-11-17 | **−1,5%** |
| NVDA | 2023-05-24 | post-market | +18,5% | 2023-05-25 | +24,4% |
| IBM | 2014-10-20 | pre-market | −18,1% | 2014-10-20 (misma sesión) | −7,1% |
| IBM | 2018-01-18 | post-market | +0,2% | 2018-01-19 | −4,0% |

Las dos primeras filas son el argumento entero de la investigación, demostrado con datos propios: **la sorpresa negativa más pequeña produjo la reacción más violenta, y la sorpresa negativa más grande casi ninguna.** Ni el signo ni la magnitud de la sorpresa bastan — y el sentimiento de la noticia habría acertado todavía menos. IBM 2018-01-18 es el caso complementario: sorpresa ≈ 0, reacción −4%.

Nótese también que `reportTime` cambia qué sesión se mide (IBM 2014-10-20 es *pre-market*: la primera oportunidad negociable es esa misma sesión, no la siguiente). Sin ese campo, ese evento se mediría un día tarde.

**Consecuencia para la decisión**: el techo de muestra no es `n=24` como sugería el recuento por fixtures, sino **~354 eventos** (IBM 123 + NVDA 111 verificados en vivo; XOM ~120 estimado por analogía, **no consultado** — se gastaron 2 de las 25 llamadas diarias, no 3), todos con expectativa, sorpresa, fecha de publicación y momento del día, y con cobertura de precio completa. **Cero fuentes nuevas. 3 llamadas de API.** Con eso, la Evidence Sufficiency Matrix da verde para `earnings_release` sin condicionar; sigue dando rojo para cualquier cohorte condicionada (sector × régimen × bucket de sorpresa con 3 tickers), que es precisamente lo que la regla debe impedir.

Y hay una limitación que la propia demostración deja escrita: **esos retornos son brutos**. El −18,8% de NVDA incluye lo que hiciera el Nasdaq ese día. Sin índice en `DimAsset` no se puede separar evento de mercado.

---

## 6. Mapa: investigación → arquitectura actual → cambio → fase

```
INVESTIGACIÓN EXTERNA          ARQUITECTURA ACTUAL              CAMBIO REQUERIDO                FASE ADECUADA
─────────────────────          ───────────────────              ────────────────                ─────────────
available_at                   data_as_of (fecha, sin           campo available_at +            Capa 2 Fase 0
                               semántica de "conocible")        regla en qa.py                  (transversal, YA)
                               ↳ look-ahead real de 22-31 d
                                 en earnings_surprise

first_tradable_at              nada                             derivar de reportTime,          Capa 2 Fase 0
                                                                ya presente en la fuente        (con lo anterior)

Event ≠ Document               news_id = sha1(url)              event_id sobre UNA clase        Catalyst Domain
                               NEWS_FINDINGS hardcodeado        (earnings_release)              (Fase 0, sin nº)

Episode                        nada — 7/50 filas de XRP         episode_id                      Catalyst Domain
                               son el mismo episodio                                            (tras event_id)

Expectation / Surprise         agregado de 8 trimestres,        historizar por reportedDate,    Fase 2 (ampliación
                               3 filas, sin historizar          separar expected/actual         del adaptador equity)

Abnormal return                solo raw_return                  índice en DimAsset              Fase 8.0
                               ↳ decisión Fase 0 sin cumplir    (+ beta, ya en el MVP)          (desbloquea Ledger)

Historical Reaction Profile    nada                             ~354 eventos disponibles        Fase 8.0
                                                                sin fuente nueva                (primer bloque real)

Regime conditioning            régimen solo de "hoy";           2 series más en                 Fase 5 (ampliación)
                               2 de 4 señales historizadas      historical_series_us()

Evidence Sufficiency           _pct_in_window() < 10 → None     generalizar la regla que        Transversal
                               (precedente ya aplicado)         ya existe                       (con lo anterior)

n_effective + shrinkage        nada                             requiere el profile primero     Fase 8.0 (después)

reaction_gap                   nada                             requiere el profile primero     Fase 8.0 (después)

ALFRED (macro PIT)             FRED última versión              revisar                         Fase 8.0

GDELT / LM / FinBERT / LLM     GDELT bloqueado (429)            nada ahora                      PREMATURE
Intradía                       nada                             nada ahora                      PREMATURE
HERE como dominio              —                                NO crearlo                      PREMATURE
```

---

## 7. Dónde discrepo de la evaluación

Tres puntos, todos por evidencia, no por preferencia.

**1. `Historical Reaction Profile` no es P1, es parte del P0.** La evaluación lo baja a P1 asumiendo que hace falta construir infraestructura antes. Los datos de §5 dicen lo contrario: 354 eventos con expectativa, sorpresa y timestamps están a 3 llamadas de API. Y hay una razón metodológica para no aplazarlo: `available_at`, `first_tradable_at`, `event_id` y `expectation` **no se pueden validar en abstracto**. Un campo `available_at` sin nada que lo consuma es una columna que nadie comprueba. El event study es lo que demuestra que los timestamps están bien puestos.

**2. La prioridad 0 real es más pequeña que la lista de la evaluación: corregir el look-ahead de `adapt_equity()`.** No es un principio arquitectónico, es un defecto en datos publicados hoy, con fuente ya disponible y arreglo localizado. La regla de este proyecto —corregir el histórico ya escrito, no solo el código, como se hizo con BTC/XRP y con macro— aplica igual aquí.

**3. Cuidado con que `reaction_gap` se convierta en lo que la Fase 6 excluyó.** La Fase 6 decidió explícitamente **no** incluir un "score de compra/venta", y el PASO 5 de la Fase 0 excluye "backtesting/optimización automática de pesos" hasta que la metodología de scoring sea estable. `reaction_gap` como *variable observada que abre una investigación* es plenamente compatible. `reaction_gap` alimentando pesos de scoring **contradice** ambas decisiones. La formulación de la evaluación ("no decide, investiga la discrepancia") es la correcta; conviene que quede escrita como regla, no como intención.

En todo lo demás coincido, en particular en no crear HERE como dominio: el sistema ya tiene 5 motores y un patrón claro de "un dominio = una carpeta en `engine/`". Un sexto motor que necesita leer de los otros cinco y del histórico de precios no es un dominio, es una capa.

---

## 8. Secuencia recomendada

Nada de esto está ejecutado. Es la propuesta para autorizar (o no).

| # | Bloque | Coste | Desbloquea |
|---|---|---|---|
| 1 | Corregir el look-ahead de `adapt_equity()` (`reportedDate` como `data_as_of`) + corregir las filas ya escritas | pequeño, 0 llamadas | credibilidad de todo lo demás |
| 2 | `available_at` explícito en el contrato + regla en `qa.py` que sí pueda detectar el caso de (1) | pequeño | verificabilidad |
| 3 | Historizar expectativa/sorpresa por `reportedDate`, con `reportTime` → `first_tradable_at` | medio, 3 llamadas | ~354 eventos |
| 4 | Índice de mercado en `DimAsset` (decisión de fuente pendiente; Yahoo Finance da `^GSPC`/`^IXIC` gratis, mismo patrón que el bloque 4) | medio | abnormal return, beta, y la decisión "contra benchmark" de la Fase 0 |
| 5 | Primer `HistoricalReactionProfile` sobre `earnings_release`, sin condicionar, con la regla de suficiencia explícita | medio | `reaction_gap` |
| 6 | Régimen histórico: 2 series más en `historical_series_us()` | pequeño, 0 llamadas | conditioning |
| 7 | `event_id` / `episode_id` en noticias | medio | fin del doble conteo |

Los pasos 1, 2 y 6 no consumen cuota de API y son reversibles. El 4 es el único que requiere una decisión de fuente que no está tomada.

**Pregunta abierta para el usuario, que no me corresponde decidir**: el paso 4 amplía `DimAsset` con un activo que no es de la watchlist ni de la cartera, sino un instrumento de medida. Es coherente con la Fase 0 (beta estaba en el MVP), pero cambia qué significa "activo" en el modelo, y eso afecta a Power BI. Conviene decidirlo antes de construirlo, no después.

---

## 9. Pruebas de demostración

`tests/test_auditoria_pit_eventos.py` — 14 pruebas, ninguna de producción. Existen para que ningún hallazgo de este informe quede como prosa sin verificar:

- `TestHallazgoLookAheadEnSorpresaDeResultados` (4) — §3. Una marcada `@expectedFailure`.
- `TestHallazgoDocumentoNoEsEvento` (3) — §4.
- `TestHallazgoReaccionSinBenchmark` (2) — §2.4.
- `TestHallazgoSuficienciaDeEvidenciaYaTienePrecedente` (2) — §2.5.
- `TestHallazgoEventStudyYaEsComputableHoy` (3) — §5.

Suite completa: **99 tests** (85 → 99), `OK (expected failures=1)`. `engine/contract/qa.py`: **PASS**.
