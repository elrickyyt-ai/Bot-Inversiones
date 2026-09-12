# P6.2a-d — Integridad temporal y event study mínimo

**Fecha**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2`
**Alcance**: cuatro bloques autorizados por el usuario. No se ha construido HERE, no se ha renombrado ninguna fase y no se ha tocado P6, P6.1, scoring, `DimAsset`, Power BI ni Narrative.

**Verificación**:

```
python3 -m unittest discover -s tests            447 → 491 tests · OK
python3 engine/contract/qa.py --require-parquet  STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   PASS (25 entidades · 48 relaciones · 10 fuentes)
git status --short data/ knowledge/              3 CSV modificados (la corrección del §3)
```

---

## Aviso previo: el alcance de la auditoría del 2026-09-07 estaba equivocado

La auditoría de esta mañana (`informes/2026-09-07_auditoria_event_studies_y_pit.md`, rama `architecture-gio4pl`) concluyó que *"P6/P6.1 no existen en el repositorio"* y recomendó no renumerar. **Era falso del proyecto y solo cierto de aquella rama.** P1→P6.1 están cerradas aquí, con `docs/ESTADO.md`, `docs/DECISIONES.md` y un roadmap `P6.2 → P7 → … → P11`. Aquella auditoría se hizo contra la rama asignada sin comprobar si había otras.

Qué sobrevive de ella, ya reverificado contra esta rama:

| Hallazgo | Estado real aquí |
|---|---|
| Look-ahead en la familia `earnings_*` | **Vivo y sin registrar** — `DEFECTO_DE_FECHADO` cubría otras cinco métricas, de signo contrario |
| Alpha Vantage `EARNINGS` da la serie completa con `reportedDate` y `reportTime` | Confirmado en vivo para los tres activos |
| `episode_id` no existe | Confirmado: cero apariciones |
| `first_tradable_at`, `available_at`, `benchmark`, `abnormal` | Cero apariciones en código |
| "Event ≠ Document está MISSING" | **Falso**: P4 ya lo resuelve. Solo faltaba Episode |
| "QA PASS es demasiado grueso" | **Falso**: ya era `VERIFIED / UNVERIFIED / FAIL` por capas |

---

## 1. El look-ahead encontrado

`adapt_equity()` fechaba nueve métricas del trimestre con `LatestQuarter` del `COMPANY_OVERVIEW`, que es `fiscalDateEnding`: **el día en que el trimestre terminó**. Esas métricas no fueron conocibles hasta que la empresa publicó resultados.

| Activo | `fiscalDateEnding` | `reportedDate` | Días de adelanto |
|---|---|---|---:|
| IBM | 2026-06-30 | 2026-07-22 | **22** |
| XOM | 2026-06-30 | 2026-07-31 | **31** |
| NVDA | 2026-07-31 | 2026-08-26 | **26** |

Sobre los ocho trimestres de cada fixture el desfase va de 22 a 32 días (IBM media 24,0; XOM media 31,2).

Un análisis fechado dentro de esa ventana —por ejemplo el 2026-07-01— habría visto la sorpresa de resultados de IBM del segundo trimestre **21 días antes de que existiera**. No es un riesgo hipotético: son 27 filas que estaban escritas así en `data/incoming/`.

**Por qué `qa.py` no lo veía**, y no es culpa suya: la invariante que validaba es `data_as_of ≤ retrieved_at`, y `2026-06-30 ≤ 2026-09-03` pasa sin problema. Esa invariante compara la fecha del dato con la de **descarga**, no con la del análisis. Es ciega justo a la dirección peligrosa.

---

## 2. La causa

No es un descuido puntual: **`data_as_of` no significa lo mismo en todas las filas del contrato**.

```
tecnico/precio        2026-09-04   el cierre de esa sesión          → available_at
fundamental/eps       2026-06-30   el fin del trimestre             → period_end
macro/cpi_yoy_pct     2026-06-01   el mes que describe              → period_end
fundamental/pe_ratio  2026-06-30   ...pero el valor es de HOY       → ninguno de los dos
```

Cuatro relojes distintos en la misma columna. Es exactamente el error que este proyecto ya se prohibió a sí mismo dos veces: **"un token se comparte si y solo si significa lo mismo"** (P0, con `source_priority`, que significaba dos cosas) y la decisión de no introducir `POINT` junto a `KNOWN` en P6.1. Aquí el token compartido es la propia columna de fecha.

Y explica por qué el defecto reaparece: se corrigió `datetime.now()` en BTC/XRP (P1), se corrigió en macro (P1), se registró en las cinco métricas de precio/consenso (P1b) — cada vez como un caso aislado, porque no había un sitio donde estuviera escrito qué reloj lleva cada métrica.

---

## 3. Correcciones aplicadas

### 3.1 El motor expone el tercer reloj

`engine/equity/score.py`: `_trimestre_reportado()` empareja el `LatestQuarter` del overview con su bloque en `quarterlyEarnings` **buscando por `fiscalDateEnding`**, no cogiendo `earn[0]`: si overview y serie vinieran de descargas distintas, el primer elemento podría emparejar un trimestre con la fecha de publicación de otro. Si no hay coincidencia devuelve `None` y nadie inventa una fecha.

Dos campos nuevos en la salida: `fecha_publicacion_fundamental` (`reportedDate`) y `momento_publicacion` (`reportTime`).

### 3.2 El adaptador usa el reloj correcto

`adapt_equity()` maneja ahora tres relojes explícitos, y separa **dos grupos que no pueden compartir fecha**:

| Grupo | Métricas | Se fecha con | Clasificación |
|---|---|---|---|
| **A** (9) | `eps`, `roe_pct`, `revenue_growth_yoy_pct`, `profit_margin_pct`, `operating_margin_pct`, `earnings_beats_8q`, `earnings_misses_8q`, `earnings_surprise_avg_pct`, `earnings_surprise_last_pct` | **`reportedDate`** | `SAFE` |
| **B** (5) | `pe_ratio`, `peg_ratio`, `analyst_target_price`, `analyst_upside_pct`, `analyst_n_analistas` | `LatestQuarter` *(sin tocar)* | `STALE` — ya registrado |

Para los agregados de ocho trimestres la fecha es la del **más reciente** de los ocho: un agregado no es conocible hasta que se conoce su último componente. Es la regla contraria a *"la fecha del bloque es la del componente más antiguo"*, que sigue siendo la correcta **para la frescura** — son dos preguntas distintas (*¿de cuándo es este bloque?* frente a *¿desde cuándo se pudo saber?*) y por eso admiten respuestas opuestas sin contradicción.

Si `publicacion_as_of` es `None`, las nueve **no se emiten**. No se cae de vuelta a `fundamental_as_of`: sería reintroducir a propósito el look-ahead que la corrección elimina. La ausencia la ve la cobertura declarada en `cadencias.ESPERADAS`.

### 3.3 Las filas ya escritas

**27 filas re-fechadas** en `data/incoming/{IBM,NVDA,XOM}_2026.csv` (9 métricas × 3 activos). El diff toca **solo la columna `data_as_of`**: 27 inserciones, 27 borrados, ningún valor alterado.

Están en `incoming/` (año en curso, capa mutable), **no en `history/`**: no se ha reescrito ninguna partición inmutable ni ningún manifiesto. Hizo falta reescribir en vez de reemitir porque `storage.logical_key()` incluye `data_as_of`: reemitir habría creado una clave lógica nueva y la fila mal fechada habría sobrevivido como un "hecho" distinto.

Procedencia de las tres fechas: IBM y XOM de las fixtures congeladas del repo; NVDA verificado en vivo (su fixture de `_earnings` no existe).

### 3.4 Un test que caducó

`test_adapt_equity_incluye_eps_margenes_sorpresa_y_analistas` afirmaba que `eps` y `pe_ratio` comparten fecha *"porque vienen del mismo overview"*. Era cierto y era el defecto: venir del mismo overview no los hace conocibles el mismo día. Reescrito a la propiedad que sigue siendo cierta —son dos relojes y **no deben** coincidir— más dos afirmaciones nuevas: el grupo A comparte fecha entre sí, y esa fecha es posterior a la del grupo B. Es el caso que `docs/07-protocolo-de-informes.md` §3 anticipa.

---

## 4. Las invariantes temporales

`engine/contract/temporal.py` (nuevo). Declara los cinco relojes:

```
period_end      fin del periodo económico que el dato describe
occurred_at     cuándo ocurrió el hecho
published_at    cuándo la fuente lo hizo público
available_at    primer momento en que ESTE sistema podría haberlo conocido
retrieved_at    cuándo lo descargó de hecho
```

y el orden que deben cumplir **los que existan** (no exige que existan todos):

```
event_occurred_at ≤ available_at ≤ retrieved_at
```

Más la condición que faltaba, la que gobierna cualquier evaluación fechada:

```
available_at ≤ analysis_as_of
```

### Por qué `available_at` no es un campo nuevo del contrato

Mismo criterio que **D-12** para la materialidad: se **deriva**, no se almacena. Es función de la familia de la métrica y de la semántica declarada de su fuente, no un dato que la fuente entregue fila a fila. Añadirlo a `METRIC_FIELDS` tocaría el esquema que sostienen el cron, los parquet de `history/` y Power BI, para guardar en 507.330 filas un valor que una tabla de 30 líneas calcula.

### Cuatro clasificaciones que no son intercambiables

| | Qué significa |
|---|---|
| `SAFE` | `data_as_of` coincide con `available_at` o lo aproxima por exceso |
| `LOOK_AHEAD` | `data_as_of` es **anterior** a cuando el dato fue conocible |
| `STALE` | la fecha no representa la temporalidad económica, pero el error va **en la dirección contraria**: el valor parece caducado, no anticipado |
| `AMBIGUOUS` | la semántica de la fuente no permite determinarlo con el dato que se descarga |

`STALE` **no es un `LOOK_AHEAD` suave**. Convertir uno en otro escondería el único que puede falsear un backtest hacia el futuro.

Tres estados para la derivación, y el consumidor no puede tratarlos igual: `EXACTO` (la fuente da la fecha), `COTA_CONSERVADORA` (no la da, pero hay un límite defendible — sirve para **excluir**, nunca para afirmar que algo se supo tal día) y `DESCONOCIDO`. **`DESCONOCIDO` nunca es utilizable**, regla dura heredada de `cadencias.py`.

`comprobar_coherencia_con_cadencias()` verifica que `DEFECTO_DE_FECHADO` y `SEMANTICA_DATA_AS_OF` no divergen: si alguien corrige el grupo B en un sitio y se olvida del otro, salta.

### Resultado sobre las 507.330 filas del contrato

| | Filas | Detalle |
|---|---:|---|
| `SAFE` | **505.167** | todo el técnico, el fundamental cripto, y el grupo A ya corregido |
| `LOOK_AHEAD` | **2.148** | `cpi_yoy_pct` 941 · `fed_funds_pct` 864 · `hicp_yoy_pct` 343 |
| `STALE` | **15** | las cinco del grupo B × 3 activos, ya registradas |
| `AMBIGUOUS` | **0** | ninguna métrica sin reloj declarado |

**Corrección de una primera clasificación mía**: al principio metí las cuatro series macro en el mismo saco por defecto de dominio, y salían 12.213 filas `LOOK_AHEAD`. Es imprecisión en la dirección contraria: el tipo de depósito del BCE del día D es el que rige ese día y se conoce ese día (10.065 filas), y la pendiente 10a-2a se publica al cierre de la propia sesión, igual que un precio. Declaradas serie a serie, el número real es **2.148**. Las que sí tienen retraso real de publicación son el IPC, el HICP y la media mensual del tipo efectivo de la Fed.

### El nuevo bloque de QA

`qa.py` gana un bloque `INTEGRIDAD TEMPORAL`, que **sí bloquea** en tres casos:

1. Cualquier métrica **sin declaración** (`AMBIGUOUS`). Una métrica nueva no puede entrar al contrato sin decir qué reloj lleva.
2. **Colisión de relojes**: si en un activo de renta variable el grupo A y el grupo B vuelven a compartir `data_as_of`, es que alguien volvió a fechar el trimestre con `LatestQuarter`. Es la comprobación que habría cazado este defecto.
3. **Incoherencia** entre `cadencias.py` y `temporal.py`.

Los `LOOK_AHEAD` **declarados** no bloquean: están reconocidos, acotados y con su razón escrita. Lo que bloquea es uno nuevo.

---

## 5. El fixture de fallo

`tests/fixtures/temporal/look_ahead.json`: la **misma** observación —la sorpresa de IBM del trimestre cerrado el 2026-06-30— con las dos fechas que ha tenido.

```
                data_as_of    retrieved_at              data_as_of ≤ retrieved_at
defectuosa      2026-06-30    2026-09-03T12:15:39Z      ✓  la invariante vieja la acepta
corregida       2026-07-22    2026-09-03T12:15:39Z      ✓  y también acepta ésta
```

Con `analysis_as_of = 2026-07-01` —después del cierre del trimestre, antes de su publicación:

| Comprobación | Fila defectuosa | Fila corregida |
|---|---|---|
| `schema.validate_metric_row()` | **pasa** | pasa |
| `data_as_of ≤ retrieved_at` | **pasa** | pasa |
| filtrar por `data_as_of ≤ analysis_as_of` | **la incluye** ← el look-ahead | la excluye |
| `temporal.usable_en(fila, "2026-07-01")` | — | **`False`, estado `EXACTO`** |
| `temporal.usable_en(fila, "2026-07-22")` | — | `True` |

Es el caso exacto que el usuario pidió demostrar: `data_as_of < retrieved_at` **y aun así inválida** porque `available_at > analysis_as_of`.

---

## 6. Diseño mínimo de Event: lo que ya existía

**No se ha construido ninguna capa de eventos.** P4 (`a9ba0c6`) ya la tiene, y es más completa de lo que la auditoría de la mañana suponía:

- `event_id` y `identity_key` — deduplicación por `(entidad, tipo, acción, fecha, magnitud bucketizada)`, con **ningún campo de texto libre en la clave**.
- Cuatro relojes ya separados: `published_at`, `occurred_at`, `effective_at`, `known_at`, con invariantes de orden ya validadas.
- **`expected`, `actual`, `surprise` ya son campos del evento.** La expectativa y la sorpresa eran representables desde P4; lo que faltaba era alimentarlas desde una fuente.
- `evidence_count` frente a `independent_support_count` — *"tres artículos del mismo medio son 3 evidencias y 1 fuente"*.

Lo único añadido: **`episode_id`, opcional**, en `CAMPOS_EVENTO`. Añadir a ese conjunto no rompe nada (el validador solo rechaza campos *de más*), y los 43 eventos reales de XRP siguen validando.

---

## 7. Document → Event → Episode

P4 ya distinguía las dos primeras. La tercera faltaba, y su ausencia tiene una consecuencia medida.

```
DOCUMENTO   una pieza concreta (un artículo)     → Evidence, con su source_ref
EVENTO      un hecho identificable               → Event, deduplicado por identity_key
EPISODIO    una secuencia causal en curso        → NUEVO
```

P4 ya evitaba el doble conteo por **redundancia** (varios artículos del mismo medio sobre el mismo hecho). No evitaba el doble conteo por **continuidad**: cinco piezas sobre momentos distintos del mismo hilo legislativo son legítimamente cinco eventos, y aun así **un solo asunto abierto**.

Sobre los datos reales de XRP:

```
50 documentos  →  100 evidencias  →  43 eventos  →  5 eventos en 1 episodio
```

### Corrección de un número mío

La auditoría de la mañana dijo *"7 de las 50 filas son el mismo episodio"*. **Era un recuento malo**: el patrón incluía `regulat`, que barre la aprobación irlandesa del fondo de Aviva y la actividad de Sberbank, que no tienen nada que ver. Con un criterio explícito, escrito y auditable, los documentos del episodio son **5**. Está en el propio criterio del registro, que dice qué se excluye y por qué.

### El mecanismo: declarado, nunca inferido

`engine/events/episodios.json` (registro curado, versionado) + `engine/events/episodios.py`.

Un episodio declara: `episode_id`, título, entidad principal, **estado** (`OPEN` / `RESOLVED`), **criterio de pertenencia escrito**, la lista de documentos **con la justificación de cada uno**, y sus fuentes. El validador rechaza un episodio sin criterio, un documento sin `por_que`, un estado fuera del vocabulario y un documento declarado en dos episodios.

La pertenencia se ancla al `news_id` del Data Contract (sha1 de la URL, estable), **no al `event_id`**, que es derivado y se regenera en cada consolidación.

**Por qué no hay clustering automático.** Agrupar por parecido de texto es justo lo que P4 se prohibió en su regla de identidad. Y con estos cinco documentos no funcionaría: uno es un *"Hodler's Digest"* semanal y otro habla de las elecciones de medio mandato. Un criterio textual o los deja fuera o mete noticias de otra regulación cripto. La agrupación es un acto de curación con fuente, igual que `knowledge/` (**D-04**: el motor no escribe conocimiento).

`episode_id = None` significa *"no se ha declarado que pertenezca a ningún episodio"*, **no** *"es un hecho aislado"*.

### Por qué importa, con el caso real

En julio de 2026 el sistema registró la aprobación en **comité** de la CLARITY Act como si el catalizador estuviera resuelto. El 7 de agosto el Senado pleno aplazó la votación y hubo que corregirlo a mano en la v2 de la Fase 4. **Un episodio con estado `OPEN` habría hecho visible que el hilo seguía abierto**, en vez de dejar cinco documentos sueltos contados como cinco evidencias independientes. Por eso el episodio de la Clarity Act está declarado `OPEN`, y un test lo fija.

---

## 8. El event study mínimo

`engine/events/estudio_resultados.py`. Emite **observaciones individuales**, nunca perfiles agregados.

```
earnings event → reportedDate + reportTime → available_at → first_tradable_at
              → expected vs actual EPS → surprise → reacción EOD
```

### `available_at` no se disfraza de marca de tiempo

Alpha Vantage da el **día** de publicación y una etiqueta de franja, no una hora. Llamar a eso *"el instante en que se supo"* sería inventar precisión. Cada observación viaja con `timestamp_semantics = PROVEEDOR_DIA`, así que el consumidor no puede confundirlo con un timestamp real. Lo que sí es defendible: **el día en que se publicó es el primer día en que se pudo saber**.

### `first_tradable_at` es otra pregunta

| `reportTime` | Primera sesión negociable |
|---|---|
| `pre-market` | la sesión **del propio anuncio** |
| `post-market` | la sesión **siguiente** |
| ausente | **`None`** — no se elige una por defecto |

No es un caso de laboratorio: **XOM publica casi siempre pre-market (16 de 18 en la muestra), IBM y NVDA casi siempre post-market**. Una regla ingenua de *"el día del evento"* mediría, en 28 de los 52 eventos, una sesión en la que la noticia todavía no existía.

Caso real que lo fija en un test: XOM publicó post-market el **viernes** 2024-04-26 → primera sesión negociable el **lunes** 2024-04-29.

Cuando falta la franja no se elige: las dos opciones difieren en una sesión entera de reacción, y elegir sería inventar el dato que falta.

### Resultado sobre 52 eventos reales

Fixtures congeladas en `tests/fixtures/eventos_resultados/` desde la consulta en vivo del 2026-09-07: IBM 16, NVDA 18, XOM 18 — **un subconjunto** de los 356 verificados (IBM 123 desde 1996-03-31, NVDA 111 desde 1999-04-30, XOM 122 desde 1996-03-31), elegido para cubrir las dos franjas y tres décadas. La ingesta completa es el paso manual que `engine/equity/README.md` ya documenta para acciones.

**Los 52 tienen reacción medible**: el histórico de precios del contrato (IBM y XOM desde 1970, NVDA desde su OPV de 1999) cubre todas las fechas de evento.

Cinco de los casos:

| Activo | Publicado | Franja | 1ª negociable | Sorpresa | Retorno bruto 1s |
|---|---|---|---|---:|---:|
| NVDA | 2018-11-15 | post-market | 2018-11-16 | −2,13% | **−18,76%** |
| NVDA | 2022-11-16 | post-market | 2022-11-17 | −18,31% | **−1,46%** |
| NVDA | 2023-05-24 | post-market | 2023-05-25 | +18,48% | +24,37% |
| IBM | 2014-10-20 | **pre-market** | **2014-10-20** | −18,06% | −7,11% |
| XOM | 2024-04-26 | post-market | **2024-04-29** | +0,98% | +1,42% |

### Lo que estos casos permiten y no permiten decir

Las dos primeras filas se prestan a una conclusión que **no es válida**. Con dos observaciones no se puede afirmar que la sorpresa no explique la reacción. Lo que sí sostienen: **la sorpresa aislada es insuficiente para explicar la reacción observada en estos casos**, y por tanto hace falta el contexto —régimen, expectativas previas, comparables— antes de interpretar ninguna reacción. Sirven como demostración de una necesidad, no como evidencia estadística. La regla de suficiencia del §11 existe precisamente para que este sistema no pueda convertir un `n` pequeño en una narrativa causal.

### Solapamiento

`marcar_solapamientos()` marca las observaciones cuya ventana alcanza al siguiente evento del mismo activo, contando en **sesiones sobre la serie real**, no en días naturales (el proyecto ya rechazó esa aproximación al construir `trading_calendar.py`).

A 20 sesiones no hay ningún solapamiento —dos trimestres distan ~63 sesiones— y **que salga cero no significa que la comprobación no sirva**: a 90 sesiones aparece, y hay un test que lo fija. Sin esta marca, una ventana larga atribuiría a un trimestre la reacción del siguiente.

---

## 9. Retorno bruto ≠ retorno anormal

**No se calcula el retorno anormal, y se dice por qué.** Cada observación lleva `market_adjusted_return_pct = None` con `razon_sin_ajuste = SIN_BENCHMARK_EN_EL_CONTRATO`. Es una ausencia estructural: no hay ningún índice en el contrato. Los 11 activos son 6 cripto, 3 acciones y 2 regiones macro.

Llamar "reacción al evento" a un retorno bruto sería el mismo error de token compartido que el proyecto ya se prohibió.

**Cuánto importa**, medido con datos del propio contrato — y con la advertencia de que **dos acciones no son un índice de mercado**: esto ilustra que existe una componente común no despreciable, no la mide.

| Evento | Retorno del activo | Las otras dos acciones (media) | Lectura |
|---|---:|---:|---|
| NVDA 2018-11-16 | −18,76% | +0,55% | casi todo idiosincrásico |
| IBM 2021-01-22 | −9,91% | −1,27% | mayoritariamente idiosincrásico |
| **XOM 2020-05-01** | **−7,17%** | **−3,09%** | **~40% del movimiento es común al mercado** |

En el tercer caso, atribuir −7,17% al evento sobreestima su efecto en varios puntos porcentuales. Y no se sabe de antemano en cuál de los tres casos se está.

---

## 10. El problema de los timestamps

Tres cosas que este sistema **no** puede afirmar hoy, y que quedan marcadas como tales en vez de aproximadas:

1. **La hora exacta de publicación.** Alpha Vantage da el día y la franja. Por eso `timestamp_semantics = PROVEEDOR_DIA` viaja con cada observación. `reported_at` (lo que la fuente dice) y `source_available_at` (cuándo estuvo disponible de verdad) **no son lo mismo**, y lo primero se usa como *proxy* declarado de lo segundo, nunca como verdad universal.
2. **La fecha de publicación de las series macro.** Vive en ALFRED (vintages), no en FRED. Se deriva una cota conservadora a partir del retraso declarado en `RETRASO_PUBLICACION_DECLARADO`, marcada `COTA_CONSERVADORA`: sirve para decir *"esto seguro que no se sabía"*, nunca *"esto se supo tal día"*.
3. **La dirección causal noticia↔precio.** No se representa. Una noticia puede escribirse *porque* el precio ya se movió, y nada distingue hoy un caso del otro. Queda como gap registrado, sin inventar un campo que no se pueda rellenar.

---

## 11. Suficiencia de muestra

Generalización del principio que `engine/crypto/score.py::_pct_in_window()` ya aplicaba: **con menos de N observaciones no se devuelve un número peor, se devuelve `None`**.

Dos decisiones sobre cómo generalizarlo:

**El mínimo se declara por pregunta, no como umbral global.** El `10` de `_pct_in_window` era el mínimo razonable para un percentil en una ventana móvil; no tiene por qué servir para estimar la reacción mediana de una clase de evento. `MINIMOS_DECLARADOS` da 30 para una clase sin condicionar y 50 para una condicionada. Son números **declarados y conservadores, no estimados**: no hay ninguna medición propia que justifique un valor concreto, y ponerlo más bajo "para que salga" sería justo lo que la regla evita.

**El orden de comprobación importa.** ¿Existe la evidencia? → ¿es temporalmente válida? → ¿es comparable? → ¿hay muestra suficiente?

Resultado sobre los 52 eventos:

```
utilizable: False
  eventos_totales:         52
  con_reaccion_medible:    52
  sin_solapamiento:        52
  n_efectivo_activos:       3
  ajustado_por_mercado:     0
  motivo: SIN_RETORNO_ANORMAL: SIN_BENCHMARK_EN_EL_CONTRATO
```

**Bloquea antes de mirar el tamaño de muestra**, y eso es deliberado: aunque hubiera 356 eventos, agregar retornos **brutos** y llamarlos "reacción al evento" atribuiría al evento lo que hizo el mercado. `suficiencia_de_muestra()` no devuelve ningún estadístico, y hay un test que comprueba que su informe no contiene las palabras `mediana`, `media`, `p10` ni `p90`.

---

## 12. Decisión pendiente: dónde vive el benchmark

**No se ha tocado `DimAsset`.** Este es el análisis que el usuario pidió antes de decidir.

### Opción A — el índice como un activo más de `DimAsset`

**A favor**: cero cambios de esquema; `^GSPC` reutilizaría todo el camino del backfill de acciones (Yahoo Finance, calendario NYSE, las mismas diez métricas técnicas); Power BI lo vería sin tocar el modelo estrella.

**En contra**, y es lo que pesa: `ASSET_FIELDS` describe **instrumentos** — `sector`, `industry`, `country`, `exchange`, `currency`. Un índice no tiene sector ni cotiza en un mercado: rellenar esos campos obliga a inventar etiquetas, que es lo que `DimAsset` hizo con `sector = "Cripto"` y quedó documentado como *asignado por el sistema, no propiedad del activo*. Repetirlo empeora la ontología. Y **`DimAsset` pasaría a mezclar dos cosas**: lo que se analiza y lo que se usa para medir. Toda consulta de "activos" tendría que acordarse de excluirlo — el mismo problema que el proyecto ya evitó al declarar `US`/`EA` como activos macro propios en vez de colgarlos de un `_macro.json`.

### Opción B — `DimBenchmark` + `AssetBenchmarkMap`

**A favor**: preserva el significado de `DimAsset`; permite que un activo tenga **varios** benchmarks (NVDA → mercado *y* sector), que es lo que hace falta para separar `raw` / `market_adjusted` / `sector_adjusted`; la relación activo→benchmark es una **decisión declarada con fuente**, no un atributo del activo, y encaja con `knowledge/relationships/`.

**En contra**: dos entidades nuevas y una relación; Power BI necesita una tabla y una relación más; y la serie de precios del índice tiene que vivir en algún sitio — o `FactMetrics` con un `asset_id` que no está en `DimAsset` (rompe la integridad referencial del modelo estrella), o una tabla de hechos propia.

### Recomendación, y por qué no la aplico

**Opción B**, por una razón concreta: `data/incoming/` y `data/history/` están particionados por `asset_id` y `asset_type`. Un `asset_type = "index"` encajaría mecánicamente sin tocar `storage.py`, pero es precisamente lo que haría que `DimAsset` dejara de significar "lo que analizamos". El coste de B es una tabla; el de A es un token compartido más, que es el error que ha causado todo lo del §2.

**Hay además una tercera cuestión, previa a las dos**: el 60% del contrato es cripto, y **para cripto no hay un benchmark obvio** (¿BTC? ¿un índice de capitalización?). Decidir la ontología solo con acciones en la cabeza dejaría la mitad del sistema fuera. La decisión es del usuario y este informe no la toma.

---

## 13. Qué NO se implementó

Por instrucción explícita, y merece quedar escrito para que dentro de seis meses nadie lo reevalúe desde cero:

- **HERE como módulo independiente.** No existe y no se ha creado.
- **Historical Reaction Profile.** Ninguna agregación, mediana, percentil ni probabilidad. La suficiencia bloquea antes.
- **Shrinkage jerárquico, `n_effective` estadístico, `reaction_gap`.** Requieren el perfil, que no existe.
- **`DimAsset`, Power BI, benchmark ontology.** Solo el análisis del §12.
- **Story** como cuarta unidad. Solo Document / Event / Episode.
- **Clustering automático de episodios.** Declarado, no inferido.
- **P6, P6.1, scoring, pesos, BUY/SELL, Narrative.** Sin tocar.
- **Corrección del grupo B** (`pe_ratio`, `peg_ratio`, `analyst_*`). Defecto distinto, ya registrado, sigue abierto. **No se re-fechó ninguna de sus 15 filas.**
- **ALFRED.** Las 2.148 filas macro `LOOK_AHEAD` quedan acotadas por cota conservadora, no corregidas.
- **Ventanas [+2,+20] y [+2,+60] del event study.** Solo [0,+1]. Las ventanas largas necesitan el retorno anormal para significar algo.

---

## 14. Tests

**447 → 491** (+44). `OK`.

| Fichero | Tests | Qué fija |
|---|---:|---|
| `tests/test_temporal.py` *(nuevo)* | 14 | los cinco relojes, el fixture negativo, `STALE ≠ LOOK_AHEAD`, la cota macro, la coherencia entre tablas |
| `tests/test_estudio_resultados.py` *(nuevo)* | 19 | transcripción de fixtures, `first_tradable_at` por franja, bruto ≠ anormal, solapamiento, suficiencia |
| `tests/test_episodios.py` *(nuevo)* | 11 | registro declarado, 50→43→5→1 sobre datos reales, P4 sigue validando |
| `tests/test_contract.py` | 43 | 1 test reescrito (§3.4) |

Los tests de fixtures comprueban que `surprisePercentage` es coherente con los EPS declarados donde el estimado es sano — un error de transcripción no puede pasar inadvertido y contaminar todo lo demás. Se excluye el caso NVDA 2009-07-31, con estimado **negativo** (−0,001) y sorpresa declarada de 300%: recalcularla daría un número sin sentido, así que se conserva la de la fuente.

---

## 15. QA

```
QA CORE:    PASS
QA PARQUET: PASS
STATUS:     VERIFIED
```

Bloque nuevo `INTEGRIDAD TEMPORAL`, incorporado a `core_ok` (bloquea). Los tres casos que bloquean están en el §4.

**Sobre la sugerencia de convertir `QA PASS` en una matriz**: ya lo era. `qa.py` da `VERIFIED / UNVERIFIED / FAIL` sobre dos niveles (CORE y PARQUET), con la regla explícita de que *"no se pudo verificar" no es "verificado"*. Lo que faltaba no era el estado global sino **una comprobación temporal que mereciera ese estado**, y es lo que se ha añadido. No se ha tocado la estructura de estados.

---

## Informe separado, en el formato pedido

### 1. Defectos `SAFE` — 505.167 filas

Todo el dominio técnico (Coinbase 148.268, Yahoo Finance 339.816, Kraken 132, Alpha Vantage 9): la fecha es la de la vela y el cierre de la sesión D se conoce al cerrar D. Fundamental cripto (CoinGecko 36, DefiLlama 6.814): snapshot fechado por la propia fuente (`last_updated`) y percentiles en ventana móvil que solo mira hacia atrás. Macro diaria (`ecb_deposit_rate_pct` 10.065, `spread_10y2y_pct`): valor vigente ese día. Fundamental de acciones grupo A (27): **`SAFE` tras la corrección de este informe**.

### 2. Defectos `LOOK_AHEAD` — 2.148 filas

`macro/cpi_yoy_pct` 941 · `macro/fed_funds_pct` 864 · `macro/hicp_yoy_pct` 343. Fecha del periodo, no de publicación. **No corregidos**: la fecha exacta requiere ALFRED, que este sistema no usa, y el usuario pidió no inventar precisión. Acotados por cota conservadora y visibles en cada ejecución de QA.

Antes de la corrección de este informe había además **27 filas** de fundamental de acciones (grupo A), con 22-31 días de adelanto. Ya no.

### 3. Defectos `AMBIGUOUS` — 0 filas

Ninguna métrica del contrato queda sin reloj declarado. Cualquiera nueva que entre sin declararse **bloqueará** QA.

### 4. Defectos `STALE` ya conocidos — 15 filas

`pe_ratio`, `peg_ratio`, `analyst_target_price`, `analyst_upside_pct`, `analyst_n_analistas` × 3 activos. Registrados por P1b en `cadencias.DEFECTO_DE_FECHADO`. Valor de hoy con fecha del trimestre: sale `STALE` con decenas de sesiones de retraso, pero **no falsea ningún backtest hacia el futuro**. Siguen abiertos por decisión explícita. `temporal.py` los clasifica como `STALE`, nunca como `LOOK_AHEAD`.

### 5. Correcciones aplicadas

| Qué | Dónde |
|---|---|
| Tercer reloj expuesto por el motor | `engine/equity/score.py` |
| Grupo A fechado con `reportedDate` | `engine/contract/adapters.py::adapt_equity` |
| Fila sin fecha → no se emite | `engine/contract/adapters.py::adapt_equity` |
| 27 filas re-fechadas | `data/incoming/{IBM,NVDA,XOM}_2026.csv` |
| Test caducado reescrito | `tests/test_contract.py` |
| Semántica temporal declarada | `engine/contract/temporal.py` *(nuevo)* |
| Bloque de QA temporal | `engine/contract/qa.py` |
| `episode_id` opcional | `engine/events/esquema_evento.py` |

### 6. Tests nuevos

44: `test_temporal.py` 14, `test_estudio_resultados.py` 19, `test_episodios.py` 11.

### 7. QA

`QA CORE: PASS` · `QA PARQUET: PASS` · `STATUS: VERIFIED`. Bloque temporal incorporado a `core_ok`.

### 8. Commits

Ver `informes/2026-09-07_trazabilidad_fases_P0_P61.md`, actualizado con P6.2a-d.

### 9. Qué datos NO se modificaron

- **`data/history/`**: ninguna partición, ningún manifiesto, ningún hash. Verificado por `qa.py` (integridad CORE por hash + nivel PARQUET).
- **Las 15 filas del grupo B**: siguen con `data_as_of = LatestQuarter`.
- **Las 2.148 filas macro `LOOK_AHEAD`**: sin re-fechar.
- **`knowledge/`**: sin cambios (`git status --short knowledge/` vacío).
- **`data/assets/`, `data/thesis/`, `data/news/`**: sin cambios.
- **Ningún valor**: el diff de los 3 CSV toca exclusivamente la columna `data_as_of` (27 inserciones, 27 borrados).

---

## Impacto sobre fases anteriores

| Fase | Tocada | Cómo se verificó |
|---|---|---|
| P1 / P1b | `cadencias.py` **no** se modificó | `comprobar_coherencia_con_cadencias()` en QA y en test |
| P2 Knowledge | no | `consulta.py --validar` PASS · `git status knowledge/` vacío |
| P3 Evidence | no | sin cambios en `engine/evidence/` |
| P4 Events | solo un campo **opcional** añadido | los 43 eventos reales revalidados contra `esquema_evento` |
| P5A-D, P6, P6.1 | no | sin cambios en `engine/causal/`, `engine/impact/`, `engine/requirements/` |

## Implicaciones para los consumidores

- **Cron** (`.github/workflows/actualizar-datos-libres.yml`): no cambia. Cripto y macro no pasan por `adapt_equity`. El bloque temporal de QA se ejecuta en su nivel CORE, sin PyArrow.
- **Power BI**: `FactMetrics` no cambia de esquema. Sí cambia el `data_as_of` de 27 filas: cualquier medida que compare fundamentales de acciones contra una fecha las verá 22-31 días más tarde. **Es la corrección, no un efecto secundario.**
- **Web App**: sin construir, sin impacto.
- **Ingesta manual de acciones**: quien la ejecute debe guardar el payload de `EARNINGS` **con `reportTime`**. Sin ese campo, `momento_publicacion` queda `None` y el event study no puede fechar la primera sesión negociable — lo dice en vez de suponerla. Las fixtures antiguas del repo (8 trimestres, sin `reportTime`) son un caso real de esto.

---

## Gaps nuevos registrados

1. **Fecha de publicación de las series macro** — necesita ALFRED. 2.148 filas acotadas, no corregidas.
2. **Dirección causal noticia↔precio** — no representada.
3. **Sin benchmark** — bloquea el retorno anormal y, con él, cualquier agregación. Decisión del §12 pendiente, y sin resolver para cripto.
4. **`reportTime` ausente en las fixtures antiguas de `equity`** — `momento_publicacion` sale `None` para IBM y XOM por la vía de `score_asset`.
5. **Episodios: uno solo declarado.** El mecanismo existe y está probado; el registro tiene un episodio. Poblarlo es trabajo de curación, no de código.
