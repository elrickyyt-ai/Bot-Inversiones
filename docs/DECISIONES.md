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

## D-21 · Ontología de benchmark en una arquitectura multi-activo

**VIGENTE e IMPLEMENTADA** (2026-09-07). Ontología y validación construidas; **ningún benchmark concreto introducido**. `DimAsset`, `METRIC_FIELDS` y Power BI intactos. Informe: `informes/2026-09-07_implementacion_d21_benchmark.md`.
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

**Revisión 2 (2026-09-07, mismo día): la distinción que cierra la decisión.**

- **Decisión original de la revisión 1**: sin benchmark formal, cripto quedaba fuera de la agregación, y escribí que *"el Historical Reaction Profile nacerá cubriendo solo acciones"*.
- **Corrección del usuario**: **Benchmark ≠ Reaction Analysis.** La ausencia de benchmark limita **qué medidas pueden llamarse retorno anormal**, no si el evento puede analizarse. Era una consecuencia excesiva de no haber separado las dos cosas.
- **Evidencia que la sostiene**: las métricas que no necesitan benchmark **ya están en el contrato para los 9 activos con serie** — `volumen` (6 cripto · 15.182 filas; 3 acciones · 35.527), `volatilidad_hist_30d_anualizada_pct` (6 · 14.948; 3 · 34.381), `atr14` (6 · 15.076; 3 · 34.981). `volume_change`, `volatility_change` y `raw_return` son computables hoy para cripto sin fuente nueva. Y `cross_asset_reaction` es representable: `CAMPOS_EVENTO` ya tiene `other_entities` (presente en los 43 eventos reales, poblado en 0 porque la única consulta de noticias filtraba por un ticker).
- **Decisión vigente**: cinco familias de retorno, y `abnormal_return` **solo** con benchmark formal válido y **temporalmente compatible** — vigencia, observación en ambas sesiones, y **calendario compartido**. Este último no es conceptual: el **28,5%** de las sesiones de BTC y ETH caen en fin de semana (1.184 de 4.150; 966 de 3.390) y IBM tiene **cero**, así que un índice bursátil no puede ser benchmark de un cripto ni queriendo.
- `PEER_RELATIVE_RETURN` **nunca** es retorno anormal: ETH −14% frente a BTC −10% son −4 pp *relativos a un peer*, no una medida de lo idiosincrásico. Y **no es simétrico**: la dirección forma parte de la asignación.
- `ASSET_CLASS_ADJUSTED_RETURN` queda **declarado y sin poblar**: para una acción estadounidense `MARKET` y `ASSET_CLASS` son cosas distintas y para cripto coincidirían; poblarlo sin fijar antes cuál de las dos lecturas es sería el error de token compartido que evitó D-13.

**Hipótesis de v1 congeladas por el usuario**:

| | |
|---|---|
| `MARKET` renta variable | **`^GSPC` (S&P 500)** |
| `^IXIC` · `^NDX` | *comparison reference*, **no** benchmark primario |
| `SECTOR` | *comparison reference*; **sin ETF sectorial en v1** |
| Cripto | sin benchmark formal; análisis de reacción **sí** |

La justificación de `^GSPC` es **ex ante y por lo que cada índice representa**, no por cobertura (los tres cubren el periodo): S&P 500 = referencia general del mercado estadounidense; Nasdaq Composite = exposición Nasdaq; Nasdaq-100 = grandes no financieras, sesgado a *growth*. Queda escrita con fecha de commit **antes** de calcular ningún retorno anormal, que es lo que la hace válida frente al *selection bias*.

**CoinDesk 20: registrado como evidencia, NO introducido.** Verificado el 2026-09-07: lanzado **2024-01-12**, fecha base **2022-10-04**, 20 constituyentes del top 250, ponderación por capitalización con tope (30%/20%), reconstitución trimestral. Cobertura real medida sobre el contrato: **54,7%** de las sesiones cripto desde la fecha base (8.310 de 15.194) y **38,2%** desde el lanzamiento. Entre ambas fechas hay **15 meses de historia retrocalculada**, cuya semántica temporal no es la de un tramo publicado en vivo — la misma familia de problema que P6.2a corrigió en el contrato. Su incorporación futura queda condicionada a los cinco criterios del §18 del informe, de los cuales **licencia/acceso está sin verificar**.

**Formulación de cierre** (sustituye a la propuesta de la revisión 1):

> `DimAsset` representa instrumentos analizados; las referencias de mercado no se convierten en activos por conveniencia. Los benchmarks formales son referencias metodológicas versionadas y temporalmente válidas, distinguiendo nivel publicado de NAV de un instrumento negociable, y rechazando las construidas por el propio sistema. Las *comparison references* contextualizan la reacción sin adquirir semántica de benchmark: son un **rol de la asignación**, no una clase de objeto, y ninguna asciende a benchmark porque falte el bueno. La asignación activo→referencia es una **relación de Knowledge** con rol y vigencia, no una tabla nueva. Un `(activo, rol, periodo)` admite exactamente una asignación. **La ausencia de benchmark no elimina el análisis de reacción: limita qué medidas pueden denominarse *abnormal return*.**

**Implementada el 2026-09-07** en 5 ficheros, sin tocar `data/` ni `knowledge/`: tipo de entidad `benchmark` con bloque de metodología propio, predicados `BENCHMARKED_BY` (habilita `ABNORMAL_RETURN`) y `COMPARED_TO` (no lo habilita nunca), campo `role`, y siete invariantes en el validador. `ASSET_CLASS` queda **declarado y rechazado** hasta que su definición esté cerrada (patrón de D-10 con `ESTIMATED`). Ningún benchmark concreto: `knowledge/` sigue con 25 entidades y 48 relaciones, y dos tests lo vigilan.

## D-22 · La elegibilidad es una propiedad de la medida derivada, no de la observación

**Vigente** (D-21 implementación, 2026-09-07).
- **Decisión original** (P6.2c): `suficiencia_de_muestra()` bloqueaba **toda** agregación con un único motivo, `SIN_RETORNO_ANORMAL`.
- **Evidencia nueva**: tras D-21, las medidas derivadas de un mismo evento no necesitan lo mismo. `RAW_RETURN`, `VOLUME_CHANGE` y `VOLATILITY_CHANGE` no necesitan benchmark — y sus métricas ya están en el contrato para los 9 activos con serie. Bloquearlas por una carencia que no les afecta excluía a cripto de un análisis que sí puede hacer.
- **Decisión vigente**: cinco familias de medida, cada una con sus requisitos y su mínimo declarado por `(familia, pregunta)`. Sobre los mismos 52 eventos: `RAW_RETURN` **utilizable** (n=52 ≥ 30) y `ABNORMAL_RETURN` **no** (`SIN_BENCHMARK`).
- **`ABNORMAL_RETURN` exige más muestra que `RAW_RETURN`** (40 frente a 30): lleva encima el error de estimación del propio benchmark.
- **Se descartó**: un umbral global. El `10` de `_pct_in_window()` era el mínimo razonable para un percentil en ventana móvil y no sirve para estimar la reacción mediana de una clase de evento. `engine/crypto/score.py` **no se ha tocado**, y un test comprueba las dos cosas.

## D-23 · Una asignación de benchmark no es una arista causal

**Vigente** (D-21 implementación, 2026-09-07). **Toca P5A, que estaba cerrada.**
- **Evidencia**: `caminos.indice()` recorre **toda** relación vigente sin mirar el predicado. El día que se declarase el primer benchmark, el motor causal seguiría esa arista y produciría caminos inexistentes — que el S&P 500 sea la referencia de NVIDIA **no conecta** a NVIDIA con las demás empresas del índice.
- **Decisión vigente**: `modelo.PREDICADOS_NO_CAUSALES` y un filtro en `indice()`. Una asignación de referencia es una relación de **medida**, no un mecanismo económico.
- **Por qué se tocó una fase cerrada**: no hacerlo dejaba un fallo plantado que solo se manifestaría cuando ya hubiera datos. La lógica de P5A no cambia: deja de ver un tipo de arista que hasta hoy no existía. Verificado con 3 tests de regresión — 22 nodos con salida antes y después, y la entidad benchmark nunca entra en el grafo.

## D-24 · La serie del benchmark vive fuera del árbol de activos

**Vigente** (2026-09-07, primera declaración de D-21).
- **Evidencia**: `data/history/` está particionado por `asset_type`. Poner ahí la serie del S&P 500 haría que `storage.asset_type_of("SP500")` la devolviese como un activo, que `cadencias.esperadas()` no supiera qué métricas esperar de ella —`PARTIAL` deja de ser calculable— y que `Asset Count` de Power BI subiera de 11 a 12 en silencio. Son los tres efectos que la auditoría de D-21 midió.
- **Decisión vigente**: `data/benchmarks/{benchmark_id}.csv`, versionado, con escritura idempotente propia. Es la "tabla propia" que recomendaba el §13 de la auditoría.
- **Se descartó**: `data/history/benchmark/SP500/`, que encajaría mecánicamente sin tocar `storage.py` y es exactamente por eso peligroso.
- **Deuda**: no está conectada a `qa.py`. Tiene validación propia (`fetch_benchmark.validar_serie()`) y un test que la ejecuta sobre la serie real, pero no entra en el `STATUS: VERIFIED` global.

## D-25 · El nivel publicado del índice, nunca un ETF ni una reconstrucción

**Vigente** (2026-09-07).
- **Evidencia medida** sobre `^GSPC`: la fuente declara `instrumentType: INDEX`; 14.291 sesiones desde 1970-01-02; **cero** eventos de split o dividendo; `close == adjclose` en las 2.299 sesiones comparadas. Un nivel de índice no tiene acciones corporativas que ajustar, así que elegir `close` no es una elección — a diferencia del caso de las acciones, donde el bloque 4 tuvo que decidirlo explícitamente.
- **Decisión vigente**: `composition_source = PUBLISHED_LEVEL`. Con el nivel publicado, el cambio histórico de composición del índice es **irrelevante**: el nivel de una fecha pasada lo incorpora ya y no se restata.
- **Se descartó**: (a) un ETF como SPY, que metería comisión, *tracking error*, distribuciones y acciones corporativas propias dentro del benchmark metodológico; (b) reconstruir el índice desde sus constituyentes, que es `CONSTRUCTED` y el validador lo rechaza.
- **Límite registrado**: la metodología de S&P Dow Jones Indices **no es citable** desde este entorno (403, misma situación que D-07). `point_in_time_capable = true` se afirma sobre la comprobación propia y no sobre una declaración del proveedor; queda el hash de la serie registrado para detectar una reformulación futura. `methodology_version = "yahoo-^GSPC-close-1d/v1"` describe cómo consume la serie **este sistema**, no la versión de S&P.

## D-26 · La validez temporal es también de la ventana, no solo del dato

**Vigente** (HistoricalReactionProfile v1, 2026-09-07).
- **Evidencia**: la primera versión del perfil filtraba por `available_at <= as_of` y nada más. Eso deja pasar un evento **conocible** en `as_of` cuya ventana de 60 sesiones **termina después** de `as_of`. Un perfil fechado en 2020-01-25 no puede saber cómo acabó una ventana que aún no había terminado.
- **Decisión vigente**: la sesión final del horizonte también tiene que ser `<= as_of`, con motivo de exclusión propio. Es la misma familia de error que P6.2a corrigió en el contrato, ahora en la dimensión del horizonte.
- **Consecuencia**: `n` depende del horizonte incluso con el mismo `as_of`, y eso es correcto — un horizonte largo tiene menos historia utilizable que uno corto.

## D-27 · Una medida de nivel no puede usar la sesión del evento como base

**Revisada el 2026-09-07** — ver la revisión al final de esta entrada. **Decisión original** (HistoricalReactionProfile v1, 2026-09-07).
- **Evidencia medida**: acumular `VOLUME_CHANGE` desde `s1` da mediana **−43,5%** a 2_5d con `prob_positive` **0,08**. No mide volumen anormal: mide la vuelta a la normalidad **después del pico**, porque `s1` *es* la sesión del evento. Publicado tal cual, se leería al revés.
- **Decisión vigente**: `VOLUME_CHANGE` y `VOLATILITY_CHANGE` solo se publican en `0_1d` (sesión del evento frente a la anterior, base limpia). En los horizontes de deriva devuelven `INSUFFICIENT_COMPARABILITY` con su motivo.
- **Se descartó**: publicarlas con una advertencia. Un número correcto con una lectura natural equivocada es peor que una ausencia explicada.
- **Lo que desbloquearía**: declarar una **ventana base anterior al evento** para medidas de nivel. Es una decisión metodológica, no un problema de datos, y afecta a 6 de los 10 perfiles no válidos.

## D-28 · Un episodio no aplica a un evento programado

**Vigente** (HistoricalReactionProfile v1, 2026-09-07).
- **Evidencia**: el episodio es una construcción de la capa de noticias — varios documentos sobre el mismo hecho (D-19). Una publicación de resultados no procede de documentos agrupables.
- **Decisión vigente**: `n_episodes` y `n_independent_episodes` valen **`NOT_APPLICABLE`**, no `0` ni `UNKNOWN`. Ningún dato adicional le daría un `episode_id`, y el proyecto ya distingue las dos cosas desde P6: *"`NOT_APPLICABLE` no mejora con más datos; `UNKNOWN` sí"*.
- **Se descartó**: contar cada evento como su propio episodio, que inflaría artificialmente la independencia a nivel de episodio y haría indistinguible una cohorte de resultados de una cohorte de noticias.

### Revisión de D-27 (2026-09-07, mismo día) — la base es una ventana previa, no la sesión anterior

- **Lo que decía la decisión original**: publicar las medidas de nivel **solo en `0_1d`** (sesión del evento frente a la anterior) y devolver `INSUFFICIENT_COMPARABILITY` en los horizontes de deriva. Era correcta como diagnóstico y demasiado restrictiva como solución: una sola sesión de base es tan frágil como la sesión del evento, solo que en la otra dirección.
- **Evidencia nueva medida** sobre los 52 eventos: la ventana `[-20,-1]` existe **completa en 52 de 52**, con **0** contaminadas por otro evento y **0** huecos de volumen. La base previa no era una aspiración: estaba disponible.
- **Comparación de bases, medida en vez de elegida** (mediana / media / z-score sobre la ventana de 20 sesiones):
  - la **media** está contaminada al alza en el **90%** de las ventanas (47/52 a `0_1d`), y **44-47 eventos por horizonte** dan un ratio *menor* usando media que usando mediana — la media esconde sistemáticamente el pico;
  - el **z-score** alcanza **16,92** en `0_1d`: la desviación típica de 20 sesiones de volumen no es una escala estable, la distribución es asimétrica por construcción;
  - la elección **cambia el signo de la conclusión** en `2_60d`: mediana → 1,02 (por encima de lo normal), media → 0,94 (por debajo).
- **Decisión vigente**: `VOLUME_CHANGE` se sustituye por **`VOLUME_RELATIVE_TO_PRE_EVENT`** = `mediana(ventana de reacción) / mediana(estimation_window [-20,-1])`, publicable en **los cuatro horizontes**. Resultado interpretable y monótono: **2,04 → 1,26 → 1,06 → 1,01**, con `prob > 1` de **0,98 → 0,82 → 0,63 → 0,53**.
- **`VOLATILITY_CHANGE` no se rehabilita**: el mismo razonamiento da un resultado distinto. La única volatilidad del contrato es una **media móvil de 30 sesiones**, cuyo valor en el evento ya contiene las 20 sesiones de la ventana de estimación — el cociente compararía dos ventanas solapadas y quedaría comprimido hacia 1 por construcción. Pasa a `INSUFFICIENT_METHODOLOGY`, no a `INSUFFICIENT_COMPARABILITY`: el problema no es la comparación, es que la métrica no existe. La desbloquearía volatilidad **realizada** sobre la ventana de reacción, que es una métrica nueva del contrato.
- **Corolario que la revisión obligó a arreglar**: el neutro de una medida es una propiedad de su **familia semántica**, no una convención global. `prob_positive` valía **1,00** para los cocientes porque los comparaba contra 0; un cociente de 0,4 es una caída y se contaba como positiva. `NEUTRO_POR_FAMILIA` fija `1.0` para `RELATIVE_TO_PRE_EVENT` y `0.0` para las familias de retorno.
- **`[-20,-1]` NO se ha convertido en constante global.** `engine/crypto/score.py::_pct_in_window()` conserva su ventana de 365 días y su mínimo de 10, con el test de regresión de D-22 intacto.
- **Informe**: `informes/2026-09-07_d27_dependencia_y_solapamiento.md`.

## D-29 · Describir no es predecir: dos estados, no uno

**Vigente** (2026-09-07). **Cristaliza el principio `COMPUTABLE ≠ INTERPRETABLE ≠ PREDICTIVO`.**

- **Evidencia**: `HistoricalReactionProfile v1` produjo perfiles `VALID` con muestra suficiente, PIT válido y benchmark formal. Un solo campo `status = VALID` invita a leerlos como una señal, cuando **no se ha hecho ninguna comprobación fuera de muestra**: ni walk-forward, ni partición temporal, ni prueba en activos distintos de los tres que produjeron el perfil. La cohorte, además, tiene **3 activos** (`independence_status = LOW`): son perfiles descriptivos *de IBM, NVDA y XOM*.
- **Decisión vigente**: dos campos independientes en todo perfil.
  - `descriptive_status` — ¿hay muestra, PIT, benchmark y metodología para **describir** lo ocurrido? Toma los 7 valores ya existentes.
  - `predictive_status` — `NOT_EVALUATED` | `VALID` | `INVALID`. **Toda la rejilla de v1.1 vale `NOT_EVALUATED`**, incluidos los 12 perfiles descriptivamente válidos.
- **`NOT_EVALUATED` no significa "probablemente sirve"**: significa que la comprobación no se ha hecho. Es la misma distinción que el proyecto usa entre `UNKNOWN` y `NOT_APPLICABLE` desde P6 — aquí *sí* mejoraría con trabajo, y ese trabajo (P8, Backtesting) no se ha hecho.
- **El perfil no entra en scoring.** Un test recorre `engine/scoring/` y `engine/reasoning/` y exige que ningún fichero mencione `perfil_reaccion`; un segundo test exige `NOT_EVALUATED` en las 20 celdas de la rejilla. La barrera es estructural, no una convención documentada.
- **`status` se mantiene como alias de `descriptive_status`** para no romper a los consumidores de v1.
- **Se descartó**: un único estado con más valores (`VALID_DESCRIPTIVE`, `VALID_PREDICTIVE`…). Son dos preguntas ortogonales — un perfil puede ser descriptivamente inválido y no haber sido evaluado nunca — y meterlas en un enum las obliga a un orden que no tienen.

## D-30 · El solapamiento se marca; no se eliminan eventos

**Vigente** (2026-09-07).

- **Evidencia medida** sobre los 52 eventos: `overlap_event_count` **0 · 0 · 0 · 3** para `0_1d` / `2_5d` / `2_20d` / `2_60d`; `overlap_rate` máximo **0,061**.
- **Decisión vigente**: la política por defecto pasa de `EXCLUDE` a **`FLAG`**. Un perfil publica **las dos** distribuciones —`statistics` (muestra completa) y `statistics_non_overlapping`— junto con `overlap_event_count` y `overlap_rate`. `EXCLUDE` sigue disponible como política explícita, con test propio.
- **Por qué no se elimina**: quitar 3 de 49 observaciones cambia la mediana de `ABNORMAL_RETURN 2_60d` de **−1,02 a −0,88** (delta +0,140) y la de `RAW_RETURN` de **+2,27 a +2,25**. Esas diferencias **no demuestran que el solapamiento sea inocuo**: con 3 observaciones fuera de 49, una mediana estable es el resultado esperado tanto si contamina como si no. **La comparación todavía no discrimina**, que no es lo mismo que no encontrar efecto — es el mismo error que se corrigió al no concluir nada de las dos observaciones de NVDA.
- **Cuando no hay nada que quitar**, `comparar_muestras()` devuelve `comparable: False` con motivo, en vez de duplicar una estadística idéntica y aparentar una validación que no ocurrió.
- **Hallazgo que no se buscaba — contaminación estructural ≠ solapamiento técnico**: el intervalo mediano entre resultados consecutivos es de **63,5 sesiones** (18 intervalos por debajo de 150; 15 de ellos entre 58 y 66). La ventana de `2_60d` cubre por tanto el **94,5%** del trimestre. Con solo el 6% de solapamiento formal, `2_60d` parecería limpio; la cobertura dice que a 60 sesiones "deriva posterior al evento" y "lo que pasó hasta los resultados siguientes" han dejado de ser distinguibles. **Se publican las dos medidas** porque una sola habría llevado a la conclusión contraria.
- **Consecuencia registrada** (de lectura, no de código): `2_20d` (cobertura 0,315) es el horizonte largo interpretable de la rejilla. `2_60d` se conserva y se publica como **contexto de deriva, nunca como medida de reacción** — su IQR casi se duplica frente a `2_20d` mientras la mediana apenas se mueve, que es ruido añadido y no señal añadida.

## D-31 · `n_effective` se mide antes de formularse

**Vigente** (2026-09-07). **Decisión de no construir.**

- **Evidencia**: `n_observations` **52**, `n_events` **52**, `n_assets` **3**, `n_independent_assets` **3**, `events_per_asset` `{IBM: 16, NVDA: 18, XOM: 18}`, `n_episodes` **`NOT_APPLICABLE`** (D-28). El cuello de botella **no es `n_events`**: los mínimos de D-22 se cumplen con holgura sobre 52, y la cohorte tiene tres unidades transversales. Los 16 trimestres de IBM comparten empresa, sector, mercado y régimen.
- **Decisión vigente**: **no se define ninguna fórmula de `n_effective`.** Se publican los conteos, `independence_status` de tres valores con umbrales declarados sobre el número de **activos** (`HIGH` ≥ 30, `MEDIUM` ≥ 10, `LOW` por debajo — esta cohorte: **`LOW`**), y `cluster_recomendado = "asset"` con su razón escrita en el código.
- **Por qué `asset` y no `episode`**: los eventos de un mismo activo comparten empresa, sector, mercado y régimen *y además se suceden en el tiempo*; el episodio **no aplica** a un evento programado (D-28), así que clusterizar por episodio daría exactamente los mismos grupos que no clusterizar.
- **Qué falta para poder formularla**: (a) la unidad de cluster está decidida pero no probada —con 3 grupos, cualquier correlación intra-cluster es inestable—; (b) la dependencia temporal dentro de un activo no está medida —16 observaciones no estiman esa autocorrelación—; (c) la dependencia transversal en fecha común **no existe** en esta cohorte porque las fechas de IBM, NVDA y XOM no coinciden, y sí existirá al ampliar a ~356 eventos.
- **Se descartó**: `n_effective = n_assets` (tira toda la información temporal); `n / (1 + (m−1)ρ)` con un ρ supuesto (el supuesto sería el resultado); bootstrap por activo (correcto como método, pero 3 clusters no lo hacen fiable).
- **Barrera**: un test comprueba que el módulo no publica ningún símbolo que contenga `effective`. Introducir la fórmula exige quitar el test, que es donde queda constancia.

## D-32 · El universo se congela en el pasado, y aun así la fuente solo conoce supervivientes

**Vigente** (auditoría de población, 2026-09-08).

- **Problema**: D-31 midió `n_events = 52` con `n_assets = 3`. Ampliar a ~356 eventos de **los mismos tres activos** daría `n_events = 356` y `n_assets = 3`: más datos y la misma dependencia. El cuello de botella es transversal, no temporal.
- **Decisión vigente**: `universe:v1:djia-2019` — los **30 componentes del DJIA a 2019-01-01** más NVDA (cohorte de HRP v1). **31 activos, 9 sectores**, declarado en `engine/events/universo_v1.json` y curado a mano como `episodios.json` (D-04).
- **Por qué un índice y no una lista propia**: la pertenencia al índice en una fecha pasada es un hecho público **anterior** a cualquier resultado que el proyecto vaya a medir. Una lista elegida por mí, después de haber visto reaccionar a IBM/NVDA/XOM, sería exactamente el sesgo que la auditoría existe para evitar. La regla es **ejecutable**: un test reconstruye la muestra desde ella y la compara con el fichero.
- **Por qué congelado y no la composición de hoy**: tomar la de hoy excluiría a las compañías que peor acabaron. Congelar obliga a incluir **DWDP** y **UTX**, que ya no existen — y esa incomodidad es el punto.
- **Hallazgo que no se buscaba, y que cambia el plan de ampliación**: `EARNINGS` devuelve `{}` para DWDP y UTX, y `SYMBOL_SEARCH` con "DowDuPont" y "United Technologies" devuelve **conjunto vacío**. **La fuente solo conoce supervivientes.** Un universo congelado en el pasado **no se puede reconstruir** con Alpha Vantage: 2 de 31 (**6,5%**) son irrecuperables *precisamente porque* tuvieron una acción corporativa. El sesgo **no es detectable desde dentro de los datos**: DWDP no aparece como hueco, aparece como si nunca hubiera existido.
- **Consecuencia**: ampliar a 300 activos pidiéndoselos a este proveedor daría **300 supervivientes**. Una población históricamente honesta necesitaría una fuente con tickers retirados (SEC EDGAR los conserva, y ya es fuente aceptada, aunque no da `reportTime`).
- **Limitación declarada, no resuelta**: Universe_v1 es **solo gran capitalización**. El usuario pidió *mid cap*; no hay composición histórica verificable de un índice mid cap congelada a 2019-01-01 desde una fuente que este proyecto acepte, y construirla de memoria sería inventarla. Condición explícita de Universe_v2.
- **Se descartó**: usar la composición actual del DJIA (sesgo de superviviencia por diseño); elegir yo 30-50 compañías "representativas" (selección); saltar directamente a 300+ (§11 del informe).

## D-33 · `2_60d` es contexto, no reacción — y se declara en el código

**Vigente** (2026-09-08). **Aplica en código la consecuencia que D-30 midió.**

- **Evidencia** (D-30): intervalo mediano entre resultados consecutivos **63,5 sesiones**; la ventana de `2_60d` cubre el **94,5%** del trimestre.
- **Decisión vigente**: `HORIZON_CLASS` clasifica los cuatro horizontes — `0_1d` `IMMEDIATE_REACTION`, `2_5d` `SHORT_REACTION`, `2_20d` `INTERMEDIATE_REACTION`, `2_60d` **`LONGER_TERM_CONTEXT`** — y `HORIZONTES_DE_REACCION` da los tres primarios sin que el consumidor tenga que conocer la discusión.
- **Reclasificar no es eliminar**: `2_60d` sigue publicándose y sigue siendo `VALID`, con un test que lo comprueba. Lo que deja de poder hacerse es presentarlo como horizonte de reacción de `earnings_release`.
- **Por qué en código y no solo en el informe**: una advertencia en prosa no viaja con el dato. Un consumidor (Power BI, Web App) que lea la rejilla ve ahora la clase en cada celda.

## D-34 · La unidad de dependencia es una propiedad de la clase de evento

**Vigente** (2026-09-08). **Completa D-31 sin violarla.**

- **Evidencia**: D-31 concluyó `cluster_recomendado = "asset"` para `earnings_release`, pero esa conclusión **no es universal**. Tres trimestres de NVDA son tres eventos distintos que comparten empresa, sector, mercado y régimen. Cinco documentos sobre la misma tramitación comparten hilo causal (D-19/D-28). Una publicación de IPC afecta a todos los activos el **mismo día**.
- **Decisión vigente**: `INDEPENDENCE_MODEL` por clase de evento (`earnings_release → ASSET_CLUSTERED`) y un vocabulario de tres modelos (`ASSET_CLUSTERED`, `EPISODE_CLUSTERED`, `EVENT_DATE_CLUSTERED`). Cada perfil declara el suyo.
- **Declarar la dependencia no es corregirla.** `n_effective` **sigue sin existir** y el test estructural de D-31 sigue vigente: ningún símbolo del módulo contiene `effective`.
- **Los dos modelos sin instanciar** (`EPISODE_CLUSTERED`, `EVENT_DATE_CLUSTERED`) están en el vocabulario y **no los usa ninguna clase**: no se ha inventado una clase de evento para poder estrenarlos.
- **Se descartó**: un único cluster universal por activo. Habría sido correcto para earnings y falso para noticias y macro, y el error solo aparecería cuando esas clases existieran.

## D-35 · Un perfil histórico es reproducible; su contabilidad de exclusiones, no

**Vigente** (2026-09-08).

- **Propiedad exigida**: `Profile(as_of=T)` debe salir **idéntico** aunque el dataset contenga observaciones posteriores a `T`. Filtrar por `available_at` no basta: el **resultado** no puede depender de nada que no fuese conocible en `T`.
- **Cómo se probó** (test de resultado, no de filtrado): el mismo perfil calculado sobre las 52 observaciones completas y sobre el dataset truncado a lo que existía en `T`, comparando las 20 celdas. En `as_of` 2015-01-01, 2018-06-30, 2020-01-01, 2023-01-01 y 2026-09-08: **cero diferencias sustantivas**.
- **La excepción legítima, separada en vez de escondida**: `n_excluidas`, `tasa_exclusion` y `exclusiones_por_motivo` **sí** difieren siempre — con 52 observaciones se descartan 34 por PIT, con las 18 de la época no hay nada que descartar. Describen **el dataset que se ofreció**, no el perfil que salió.
- **Decisión vigente**: `CAMPOS_DE_PROCEDENCIA` los nombra y `huella()` hashea el perfil **sin** ellos. La huella es lo que debe coincidir. Un test comprueba además que la huella **sí cambia** al cambiar el `as_of` — sin él no estaría midiendo nada.
- **Se descartó**: debilitar el test para que ignorase las diferencias, y esconderlas recalculando esos campos. Ambas cosas habrían tapado la distinción real entre *resultado* y *procedencia*.

### Nota de D-35 — una bomba de relojería descubierta de paso

- Al pasar el reloj a **2026-09-08**, `test_acciones_con_pe_caducado_pero_tecnico_al_dia_si_publica_confianza` empezó a fallar. Las fixtures de acciones están congeladas en **2026-09-02** y el técnico de IBM (`posicion_rango_52s_pct` y `confluencia_sesgo`, ambos **REQUERIDA**) cruzó su umbral de cadencia entre el día 5 y el día 6. **El motor estaba haciendo lo correcto**: el test comparaba una fixture congelada contra `datetime.now()`, así que tenía garantizado romperse en una fecha que nadie había calculado.
- **Arreglo**: `build_thesis(symbol, tvl_chain, as_of=None)` y `build_thesis_equity(symbol, as_of=None)` exponen el reloj que `_evaluar_evidencia()` **ya aceptaba** y que nadie pasaba. El test fija `as_of` y comprueba **la regla** (una métrica `PUBLICADA` caducada no invalida la tesis), no cuántos días llevan congeladas las fixtures. Parámetro opcional con el comportamiento por defecto intacto.
- **Se añadió la otra cara**: `test_cuando_caduca_el_tecnico_REQUERIDO_la_tesis_deja_de_ser_valida`, para impedir que algún día se "arregle" un test caducado **relajando el umbral de cadencia**, que es la tentación evidente y sería exactamente el error contrario.
- **Deuda**: no se ha revisado sistemáticamente si quedan más tests comparando fixtures congeladas contra el reloj.

