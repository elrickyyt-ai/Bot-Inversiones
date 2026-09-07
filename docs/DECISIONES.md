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
