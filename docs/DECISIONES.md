# Registro de decisiones

**Regla**: la historia no se borra. Cuando una medición cambia una decisión, queda la cadena completa — `decisión original → evidencia nueva → revisión → decisión vigente` — porque una decisión revisada con evidencia es información sobre el dominio, no un error que convenga esconder.

Formato: cada entrada dice **qué se decidió**, **con qué evidencia** y **qué se descartó**. Las revisadas llevan la cadena entera.

---

## D-01 · El sistema propone, el usuario ejecuta

**Vigente.** Sin credenciales de trading en ninguna parte del sistema. Aplica a toda automatización futura (Fase 10).

## D-02 · `EXPOSED_TO` no es un hecho del mundo

**Vigente** (P2). Una regla del código de este sistema no puede elevarse a hecho estructural sin evidencia externa. `nature: ASSERTED`, `status: PROVISIONAL`, `support_level: BAJO`, fuente `INTERNAL_RULE`.
**Se descartó**: tratarla como `STRUCTURAL` porque "el motor ya la usa".

## D-03 · `support_level`, no `confidence`

**Vigente** (P2). No es la probabilidad de que la relación sea cierta, sino el grado de respaldo que tiene **dentro del sistema**. `confidence` queda reservado para la inferencia posterior.

## D-04 · Ningún resultado del motor causal modifica una relación estructural

**Vigente** (P2). El conocimiento se actualiza solo por *nueva fuente → verificación → actualización controlada*. `modelo.py` no tiene funciones de escritura, a propósito.

## D-05 · La validez de la tesis distingue el rol de cada evidencia

**Vigente** (P1 cierre). Una métrica obsoleta no invalida la tesis si la tesis no depende de ella. Evidencia `REQUERIDA` / `PUBLICADA` / `CONTEXTO`.

## D-06 · `USES ≠ CONSUMES`, `SUPPLIES ≠ PRODUCES`

**Vigente** (P5B). Se rechazó mapearlos como equivalentes: `USES` puede ser tecnología o infraestructura mientras `CONSUMES` implica flujo; `SUPPLIES` es organización→organización mientras `PRODUCES` es organización→producto.

## D-07 · Fuente de TSMC: el 20-F, no la página comercial

**Vigente** (P5C).
- **Decisión original del diseño**: citar `tsmc.com/.../cowos` como `COMPANY_STATEMENT`, según lo previsto en `knowledge/pendiente/`.
- **Evidencia nueva**: la página no tiene fecha estable, está tras protección anti-bot (`curl` recibe *"Just a moment…"*) y su contenido puede cambiar sin dejar rastro. El validador exige un localizador **reabrible**.
- **Revisión**: se buscó la misma afirmación en el 20-F de TSMC en EDGAR y está, literal.
- **Decisión vigente**: `src:tsmc-20f-fy2025`, tipo `FILING`, URL inmutable.

## D-08 · `tech:cowos`, no `prod:cowos`

**Vigente** (P5C). `product` es *"bien o servicio concreto, con capacidad y precio"*; `technology` es *"proceso o capacidad que se emplea, no se compra"*. NVIDIA no compra "un CoWoS": compra encapsulado hecho **con** CoWoS, y su 10-K dice *"CoWoS technology"*.
**Contraargumento anotado, no escondido**: TSMC lo vende como *"CoWoS advanced packaging services"*, y la capacidad CoWoS es la variable económicamente interesante. Si hace falta tratarla como magnitud, será un `concept`, no un cambio de tipo.

## D-09 · La vigencia no se extrapola

**Vigente** (P5C). `valid_from` es el primer día del ejercicio que cubre el documento citado. TSMC fabrica para NVIDIA desde mucho antes de 2025, pero **esa fuente no lo acredita**.
**Consecuencia descubierta en P6.1**: de las tres cotas del 20-F (25% 2023, 22% 2024, 19% 2025) **solo la de 2025 es aplicable** — no por ser reciente, sino porque en 2023-2024 el sistema no sabe que NVIDIA fuera cliente de TSMC.

## D-10 · Los coeficientes de transmisión no se estiman en v1

**Vigente** (P6).
- **Opciones evaluadas**: declarado con fuente · estimado del histórico propio · rango declarado a mano · magnitud siempre `UNKNOWN`.
- **Decisión vigente**: la cuarta. `ORIGENES_COEFICIENTE` declara `ESTIMATED` **y el validador lo rechaza**, para que el caso no aparezca un día sin que nadie lo note.
- **Razón de fondo**: un coeficiente estimado estadísticamente **no es Evidence ni Knowledge** — es salida de un modelo, y esa capa (ventana de entrenamiento, validación fuera de muestra, estabilidad, sensibilidad al régimen) no existe. Introducirla ahora crearía una categoría sin ontología ni control.
- **Puerta abierta**: `OBSERVED` / `DECLARED` sí son admisibles; `ESTIMATED` pertenece a una futura capa de Model/Calibration.

## D-11 · `QUANTIFIABLE`, no `SUPPORTED`

**Vigente** (P6).
- **Decisión original propuesta**: `SUPPORTED` / `NOT_SUPPORTED` / `CONDITIONALLY_SUPPORTED` para `magnitude_capability`.
- **Evidencia nueva**: auditoría de los 14 vocabularios cerrados — `SUPPORTED` ya existe en P5B y significa *"esta afirmación concreta tiene respaldo probatorio"*, mientras aquí significaría *"esta clase de mecanismo puede dar un número"*. Propiedad de instancia vs propiedad de tipo.
- **Decisión vigente**: familia `QUANTIFIABLE`, los tres tokens libres.

## D-12 · Dónde vive la materialidad

**Vigente** (P6.1), con dos revisiones encadenadas.
- **Decisión original (revisión 1 del diseño)**: *"materialidad es propiedad de un par ordenado"* → haría falta un `counterparty` en `METRIC_FIELDS`, tocando el esquema que sostiene el cron y Power BI.
- **Evidencia nueva**: la materialidad **se deriva, no se almacena**; la observación que la sustenta es de **una entidad** (`TSMC · largest_customer_revenue_share`).
- **Revisión**: no hace falta tocar `METRIC_FIELDS` ni el esquema de Knowledge.
- **Segunda evidencia, al implementar**: `storage.asset_type_of("TSM") → None`. El contrato guarda observaciones sobre **activos**, y TSMC es una **entidad** que no lo es.
- **Decisión vigente**: las tres observaciones del 20-F viven aisladas en `engine/impact/observaciones.py`, marcado como fichero de observaciones y no de declaración. **Deuda registrada.**
- **Se descartó**: inventar un activo `TSM` sin serie, dominio ni cadencia (ensuciaría DimAsset, cobertura y frescura) y guardarlas en `knowledge/` (una observación fechada no es una relación estructural).

## D-13 · `POINT` no se introduce

**Vigente** (P6.1).
- **Decisión original propuesta**: `materiality_status = POINT | BOUNDED | UNKNOWN | NOT_APPLICABLE`.
- **Evidencia nueva**: `ESTADOS_PIEZA` de P6 ya tiene `KNOWN` con exactamente el significado de `POINT`.
- **Decisión vigente**: magnitud y materialidad comparten vocabulario; `BOUNDED` se añade a ambas. Añadir `POINT` serían **dos nombres para una idea** — el error espejo del invariante de vocabularios.

## D-14 · `SUPPLIER_REVENUE_EXPOSURE`, no `CUSTOMER_REVENUE_SHARE`

**Vigente** (P6.1). Describen la misma magnitud desde los dos lados de la mesa; tener las dos serían dos nombres para una idea. Se conserva la que **nombra al sujeto**, que es lo que hay que resolver.
**Nota**: en la aprobación de P6.1 este punto apareció invertido. Se implementó lo diseñado y se dejó constancia; invertirlo sería un cambio de una línea en `BASES` y `POBLACION`.

## D-15 · Power BI y Web App, desacoplados

**Vigente** (2026-09-07).
- **Decisión original**: `docs/03` y `docs/04` describían la arquitectura `JSON → Data Contract → Power BI/Web App`.
- **Evidencia nueva**: el motor ha crecido con Knowledge, Evidence, Events, Causal Path, Assessment, Impact y Materiality. `FactMetrics` ya no representa el sistema.
- **Decisión vigente**: ambos documentos pasan a ser **especificación de consumo, no contrato arquitectónico**. Sigue vigente que **son consumidores y no la lógica analítica**, y que el Data Contract precede a la UI. **Ningún motor se diseña pensando primero en `FactMetrics`.**

## D-16 · Los fundamentales de acciones no admiten línea base

**Vigente** (2026-09-07, medición previa a P6.2).
- **Evidencia**: las **42** series fundamentales de IBM/NVDA/XOM tienen **exactamente 1 observación** cada una. Las únicas series fundamentales con profundidad son los percentiles de TVL de cripto (backfill de DefiLlama).
- **Causa conocida**: la ingesta de acciones es manual vía Alpha Vantage MCP y nunca se automatizó; hay una única captura, del 2026-09-03.
- **Decisión vigente**: **ninguna** — la decisión está abierta y descrita en `informes/2026-09-07_medicion_lineas_base.md`. No se implementa nada hasta tomarla.

## D-17 · `available_at` se deriva, no se almacena

**Vigente** (P6.2a, 2026-09-07).
- **Evidencia**: `data_as_of` llevaba **cuatro relojes distintos** según la familia de métrica — la fecha de la vela en técnico, el fin del trimestre en fundamental de acciones, el mes descrito en macro, y ninguno de los dos en `pe_ratio`. Es el mismo error de token compartido que ya obligó a separar `source_priority` en P0.
- **Opciones evaluadas**: (a) añadir `available_at` a `METRIC_FIELDS`; (b) derivarlo de una tabla de semántica declarada.
- **Decisión vigente**: la segunda, **mismo criterio que D-12 para la materialidad**. Es función de la familia de la métrica y de la semántica de su fuente, no un dato que la fuente entregue fila a fila. La opción (a) tocaría el esquema que sostienen el cron, los parquet de `history/` y Power BI, para guardar en 507.330 filas un valor que una tabla de 30 líneas calcula.
- **Consecuencia**: `engine/contract/temporal.py`, y una invariante nueva que el contrato no tenía — `available_at ≤ analysis_as_of` — que es la que `data_as_of ≤ retrieved_at` no puede expresar.

## D-18 · `STALE` no es un `LOOK_AHEAD` suave

**Vigente** (P6.2a).
- **Evidencia**: los fundamentales de acciones tenían **dos defectos de fechado a la vez y de signo contrario**. El grupo A (9 métricas) llevaba fecha *anterior* a cuando el dato fue conocible — 22 días en IBM, 31 en XOM: falsea un backtest hacia el futuro. El grupo B (5 métricas, ya registrado en `cadencias.DEFECTO_DE_FECHADO`) lleva fecha *más vieja* que el valor: ensucia la medición de frescura y **no** puede filtrar información futura.
- **Decisión vigente**: cuatro clasificaciones que no se convierten unas en otras — `SAFE`, `LOOK_AHEAD`, `STALE`, `AMBIGUOUS`. Solo se corrigió el grupo A.
- **Se descartó**: tratar los dos como "fechas mal puestas" y arreglarlos juntos. Habría obligado a re-fechar 15 filas más para resolver un defecto que no falsea ningún backtest, y habría borrado la distinción que hace útil el vocabulario.
- **Garantía**: `comprobar_coherencia_con_cadencias()` falla si las dos tablas divergen, en QA y en test.

## D-19 · Un episodio se declara, nunca se infiere

**Vigente** (P6.2d).
- **Evidencia**: P4 ya evita el doble conteo por **redundancia** (`evidence_count` vs `independent_support_count`), pero no por **continuidad**. Cinco documentos reales de XRP tratan la misma tramitación de la CLARITY Act en el Senado, en cinco momentos distintos: son cinco eventos legítimos y **un solo asunto abierto**.
- **Opciones evaluadas**: agrupar por similitud de texto · agrupar por proximidad temporal · declarar la pertenencia a mano con criterio escrito.
- **Decisión vigente**: la tercera, **mismo trato que `knowledge/` da a las relaciones (D-04)**. Agrupar por parecido textual es justo lo que P4 se prohibió en su regla de identidad (*"ningún campo de texto libre entra en la clave"*), y con estos cinco documentos no funcionaría: uno es un *"Hodler's Digest"* semanal y otro habla de las elecciones de medio mandato.
- **Anclaje**: la pertenencia se declara contra el `news_id` del Data Contract (sha1 de la URL, estable), **no contra `event_id`**, que es derivado y se regenera en cada consolidación.
- **Consecuencia descubierta**: el episodio necesita **estado**. En julio el sistema trató la aprobación en comité como catalizador resuelto y hubo que corregirlo a mano cuando el Senado aplazó la votación. Un episodio `OPEN` lo habría hecho visible. `episode_id = None` significa *"no se ha declarado"*, no *"es un hecho aislado"*.

## D-20 · La suficiencia de muestra se declara por pregunta, no como umbral global

**Vigente** (P6.2c).
- **Evidencia**: `engine/crypto/score.py::_pct_in_window()` ya se negaba a calcular con menos de 10 observaciones y devolvía `None` en vez de un número peor. Generalizarlo con ese mismo `10` habría sido tomar un mínimo pensado para un percentil en ventana móvil y aplicarlo a estimar la reacción mediana de una clase de evento.
- **Decisión vigente**: `MINIMOS_DECLARADOS` por pregunta (30 sin condicionar, 50 condicionada). Son números **declarados y conservadores, no estimados**: no hay ninguna medición propia que justifique un valor concreto, y bajarlo "para que salga" sería justo lo que la regla evita.
- **Orden de comprobación**: ¿existe la evidencia? → ¿es temporalmente válida? → ¿es comparable? → ¿hay muestra suficiente?
- **Consecuencia medida**: con 52 eventos reales la respuesta es `False`, y **bloquea antes de mirar el tamaño de muestra**: `SIN_RETORNO_ANORMAL`. Aunque hubiera 356 eventos, agregar retornos brutos y llamarlos "reacción al evento" atribuiría al evento lo que hizo el mercado.

## D-21 · El benchmark no entra en `DimAsset` sin decidirlo antes

**Abierta** (P6.2c, 2026-09-07). **No se ha tocado `DimAsset`.**
- **Evidencia**: el contrato no tiene ningún índice (11 activos: 6 cripto, 3 acciones, 2 regiones macro), así que el retorno anormal no es calculable. Medido sobre datos propios: en XOM 2020-05-01 el retorno bruto fue −7,17% mientras las otras dos acciones hacían −3,09% de media — **~40% del movimiento es común**, y atribuirlo entero al evento lo sobreestima en varios puntos.
- **Opciones evaluadas**: (A) el índice como un activo más de `DimAsset`; (B) `DimBenchmark` + `AssetBenchmarkMap`.
- **Recomendación**: **B**. `ASSET_FIELDS` describe instrumentos (`sector`, `industry`, `exchange`); un índice no tiene sector ni cotiza, y rellenar esos campos repetiría lo que ya pasó con `sector = "Cripto"`. Y `DimAsset` pasaría a mezclar **lo que se analiza** con **lo que se usa para medir**.
- **Bloqueo previo, no resuelto**: el 60% del contrato es cripto y **para cripto no hay benchmark obvio**. Decidir la ontología solo con acciones en la cabeza dejaría fuera media base de datos. Análisis completo en `informes/2026-09-07_integridad_temporal_y_event_study_mvp.md` §12.

**Auditoría de ontología (2026-09-07, misma fecha, `informes/2026-09-07_auditoria_ontologia_benchmark.md`)**. El usuario planteó que el problema real no es *"¿`DimBenchmark` o índices dentro de `DimAsset`?"* sino **qué significa benchmark en una arquitectura multi-activo**, y pidió auditar la ontología antes de implementar. Resultado:

- **Confirmado que la opción A rompe cosas verificables**, no solo la estética de la ontología: `cadencias.calendario("tecnico","precio","index")` devuelve `'crypto'` (calendario 24/7 para un índice que no cotiza fines de semana) y `cadencias.esperadas("X","index","tecnico")` devuelve `None`, con lo que `PARTIAL` deja de ser calculable y la frescura cae a `UNKNOWN` — el peor valor del eje, no un intermedio. Y `Asset Count = DISTINCTCOUNT(FactMetrics[asset_id])` pasaría de 11 a 12 en silencio.
- **La asignación no necesita ser una tabla nueva.** Una relación de Knowledge ya tiene `subject`/`object`/`valid_from`/`valid_to`/`source_id`/`nature`/`status`/`last_verified`: es una `AssetBenchmarkAssignment` completa. Y trae **D-04** (ningún motor escribe conocimiento → el código que calcula el retorno no puede elegir el benchmark) y **D-09** (la vigencia no se extrapola) sin escribir una línea. Eso convierte la defensa contra el *selection bias* en una propiedad estructural, no en disciplina.
- **Cripto: `MARKET = UNAVAILABLE`**, medido. CoinGecko `/global` da solo el valor actual; `/global/market_cap_chart` responde **401** (clave de pago, rompería el patrón "sin clave" de todas las fuentes). Un índice construido con los 6 cripto del contrato sería **sesgo de selección y supervivencia por construcción**: son los holdings actuales de `CARTERA_A`. BTC como benchmark de cripto da AR ≡ 0 para BTC. Consecuencia aceptada: el primer Historical Reaction Profile cubrirá solo acciones.
- **Equity: construible sin fuente nueva.** ^GSPC cubre 1970-01-02 → 2026-09-04, el mismo tramo que IBM/XOM ya tienen y por la misma fuente (Yahoo). El **benchmark sectorial no es construible con lo propio**: `knowledge/entities/sectors.json` tiene 2 sectores derivados del propio `DimAsset`, con 2 y 1 constituyentes.
- **El look-ahead de composición tiene salida limpia**: usando el **nivel publicado** del índice, la composición es irrelevante y no se restata. El problema solo aparece en benchmarks construidos por nosotros — que quedan prohibidos.
- **Hallazgo lateral**: `engine/equity/score.py:150` ya extrae `beta` de Alpha Vantage — una magnitud ajustada por mercado con benchmark, ventana y frecuencia **desconocidos**. No llega al Data Contract (verificado) y **no debe llegar** mientras siga sin declararse.

**Formulación propuesta**, con dos modificaciones sobre la del usuario, ambas por evidencia:

> `DimAsset` representa instrumentos analizados. `DimBenchmark` representa referencias metodológicas versionadas, distinguiendo si su serie es un nivel publicado o el NAV de un instrumento negociable, y **rechazando las construidas por el propio sistema** (mismo patrón que D-10 con `ESTIMATED`: se declara el token para que salte, no para usarlo). La asignación activo→referencia es una **relación de Knowledge** con rol y vigencia, no una tabla nueva. Un `(activo, rol, periodo)` admite **exactamente una** asignación. La ausencia se propaga como `UNAVAILABLE` y no se sustituye por otra referencia, ni en silencio ni ascendiendo un `PEER` a benchmark.

**Roles propuestos**: `MARKET` y `SECTOR` como benchmark; `PEER` como *comparison reference*, que **no** entra en ningún retorno anormal. `ASSET_CLASS` y `FACTOR` no se introducen (el primero sería dos nombres para una idea mientras cada activo tenga una sola clase — D-13; el segundo exige la capa de modelo que D-10 declaró inexistente).

**Sigue abierta.** Tres preguntas que la auditoría no puede responder sola: (1) ¿se acepta que cripto quede sin retorno anormal? (2) ¿ETF sectorial, con su comisión y su tracking error, o ningún benchmark sectorial en v1? (3) ¿`^GSPC`, `^IXIC` o `^NDX` como `MARKET` de acciones — decidido por criterio declarado y **antes** de mirar ningún resultado?
