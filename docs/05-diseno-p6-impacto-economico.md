# P6 · Economic Impact — diseño

**Fecha**: 2026-09-07 · **Estado**: DISEÑO, sin código. Pendiente de revisión.
**Encargo**: definir qué significa `impact` y qué entradas mínimas exige cada mecanismo, **antes de escribir una sola fórmula o score**.

---

## 0. Resumen de lo que propongo

| Punto | Propuesta |
|---|---|
| Qué es un impacto | una afirmación sobre **una variable económica de una entidad, en un horizonte**, atribuida a un evento por **un** mecanismo. Nunca un precio, una probabilidad ni un score |
| Descomposición | `signo` (ya lo da P5B) + `magnitud` + `materialidad` + `horizonte`. P5B resolvió **uno de los cuatro** |
| `fitness_for_mechanism` | **derivado**, no un cuarto catálogo. Ya es computable con lo que P5D produce hoy |
| `UNKNOWN` → 0 | prohibido por **validador**, no por convención. La regla ejecutable: `magnitude == 0` exige `evidence_ids` no vacío |
| Combinación | nunca una suma. Descomposición + `unresolved[]`, y el estado agregado es el del **peor** componente |
| Qué puede calcular hoy | **nada** sobre el grafo real, y eso está medido. v1 se valida con fixtures sintéticas, igual que P5B |

---

## 1. Qué es `impact` — la definición

> Un **`EconomicImpact`** es la afirmación de que un evento produce, **a través de un mecanismo concreto**, un cambio de una **magnitud acotada**, en **una variable económica** de **una entidad**, dentro de **un horizonte**.

Cinco cosas van dentro de esa frase, y las cinco tienen que estar o el impacto no existe:

```
evento  ──[mecanismo]──►  variable  de  entidad   Δ magnitud   en horizonte
```

### Lo que un impacto NO es

| No es | Por qué importa decirlo |
|---|---|
| **un precio ni un movimiento de precio** | eso es P7 Mispricing. Un impacto económico puede ser real y estar ya descontado |
| **una probabilidad** | P6 no estima verosimilitud. Un impacto puede ser cierto en dirección y desconocido en magnitud |
| **un score** | la Fase 6 (scoring) ya se negó explícitamente a colapsar dominios en un número, y P6 no puede reintroducirlo por la puerta de atrás |
| **una recomendación** | decisión de ejecución del proyecto: el sistema propone, el usuario ejecuta |
| **un efecto sobre "la empresa"** | siempre sobre **una variable nombrada** (`revenue`, `cost`, `margin`, `pricing_power`, `demand`), las que P5B ya declara en `VARIABLES_AFECTADAS` |

### El campo que hace que la definición se sostenga

`magnitude` **no es un número suelto**: es `(valor, unidad, base_de_comparación)`. P4 ya aprendió esto y lo hace cumplir — *"magnitud sin unidad no significa nada, y una magnitud inventada..."* (`esquema_evento.py:175`). P6 hereda la regla y añade la tercera pieza: **un 10% no significa nada sin decir 10% respecto a qué**.

---

## 2. La descomposición: P5B resolvió uno de cuatro

Un impacto necesita cuatro cosas. Hoy tenemos una.

| Pieza | Estado | Qué la produce | Qué le falta |
|---|---|---|---|
| **signo** | ✅ **hecho** | P5B, reglas R1–R5 declaradas | nada |
| **magnitud** | ❌ | — | un Δ medido **contra una línea base** + un coeficiente de transmisión |
| **materialidad** | ❌ | — | qué **fracción** de la economía de la entidad toca la variable |
| **horizonte** | ❌ | — | el desfase temporal del mecanismo |

### 2.1 Magnitud: el sitio donde un sistema inventa números

La magnitud tiene dos factores y **el segundo es el peligroso**:

```
Δ variable afectada  =  Δ variable observada  ×  coeficiente de transmisión
                        └─ se mide             └─ NO se mide: se declara o no existe
```

El coeficiente de transmisión (elasticidad, repercusión, paso a precio) es exactamente donde un motor causal deja de ser auditable. **Propuesta**: tratarlo con la misma disciplina que P5D aplicó a los proxies — un coeficiente vive en una tabla declarada, con su fuente y su justificación, o el impacto se queda en `UNKNOWN`. Nunca un valor por defecto, nunca 1.0, nunca "asumimos proporcionalidad".

Si eso deja casi todo en `UNKNOWN`, eso es el resultado correcto: P5B ya demostró que un motor que dice "no lo sé" con precisión vale más que uno que estima.

### 2.2 Materialidad: la deuda de P5C, ahora bloqueante

Ya está registrada, y P6 es donde muerde:

> *`rel:0046` documenta la relación de suministro, pero no su **materialidad** — el 10-K no dice qué fracción de los wafers de NVIDIA fabrica TSMC.*

Sin ese peso, una subida del 10% en la demanda de NVIDIA es un impacto del 0,5% o del 25% sobre los ingresos de TSMC, y el sistema no puede distinguirlos. **Materialidad es un dato de Knowledge, no de Evidence**: es una propiedad de la *relación*, no una serie temporal. Eso sugiere que las relaciones necesitarán un campo de peso — con fuente, como todo lo demás — pero **no lo propongo para P6 v1**: es un cambio en P2 y merece su propia decisión.

Mientras tanto: **materialidad `UNKNOWN` ⇒ magnitud `UNKNOWN`**, aunque el Δ esté perfectamente medido.

### 2.3 Horizonte: `LEAD_TIME` encuentra su sitio

P5B declaró un mecanismo que deliberadamente no produce signo:

> `LEAD_TIME` — *"es un desplazamiento temporal, no un signo"* · bloqueo: *"sin medida de plazo; **y v1 no tiene dónde colocar el desfase**"*.

**P6 es dónde.** El horizonte no es un adorno: un impacto de +5% en ingresos "en algún momento" no es accionable, y dos impactos con horizontes distintos no se pueden sumar. Propongo que el horizonte sea **obligatorio y explícito**, con `UNKNOWN` permitido y visible, nunca implícito.

---

## 3. Entradas mínimas por mecanismo

Lo que pediste. Por cada uno de los 7 mecanismos de P5B: qué observa, qué necesita **además** para dar magnitud, y qué aporta al impacto.

| Mecanismo | Variable observada (P5B) | Línea base | Materialidad | Coeficiente | Aporta |
|---|---|---|---|---|---|
| `CUSTOMER_DEMAND` | `demand(cliente)` | demanda normal del cliente | **% de ingresos del proveedor que vienen de ese cliente** | paso de demanda a ingreso | signo + magnitud |
| `INPUT_COST` | `price(insumo)` | precio normal del insumo | **peso del insumo en la base de coste** | paso de coste a margen (≠ 1: depende de repercusión) | signo + magnitud |
| `CAPACITY_CONSTRAINT` | `capacity_utilization(recurso)` | utilización normal | — | — | **no da signo**: habilita `PRICING_POWER` |
| `PRICING_POWER` | `capacity_utilization` + comprobación de sustitución | utilización normal | cuánto del negocio pasa por ese recurso | **elasticidad precio** — el más peligroso de todos | signo + magnitud |
| `SUBSTITUTION` | — | — | — | **grado de sustituibilidad: se declara, no se estima** (P5B, literal) | solo `NEUTRAL` |
| `SUPPLY_SHORTAGE` | `inventory` | inventario normal | % del suministro afectado | paso de escasez a precio/volumen | signo + magnitud |
| `LEAD_TIME` | `lead_time` | plazo normal | — | — | **horizonte**, no magnitud |

### Tres cosas que esta tabla deja claras

1. **Todas las filas necesitan una línea base.** Ninguna existe hoy. "La demanda subió" exige un *respecto a qué*, y P5D resuelve la disponibilidad del **valor**, no de su historia comparable. Es un requisito nuevo que P6 debe pedir explícitamente — probablemente vía el mismo mecanismo de `requires_evidence`.
2. **`CAPACITY_CONSTRAINT` y `SUBSTITUTION` nunca dan magnitud**, y `LEAD_TIME` tampoco. Solo 4 de los 7 pueden llegar a un número, y eso hay que decirlo por adelantado para que nadie espere lo contrario.
3. **`PRICING_POWER` es el mecanismo que hay que vigilar.** Es el único que necesita una elasticidad, y una elasticidad inventada convierte todo el motor en decoración. Recomiendo que en v1 `PRICING_POWER` **no produzca magnitud en ningún caso** — solo signo, como hoy — hasta que exista una fuente para el coeficiente.

---

## 4. `fitness_for_mechanism` — derivado, no un catálogo nuevo

Tu propuesta de un tercer eje es correcta y la recojo, con una precisión importante: **no hace falta construirlo, ya es computable**.

```
availability   ¿existe el dato?          P1b/P5D
freshness      ¿sigue vigente?           P1b
fitness        ¿sirve para ESTE mecanismo?   ← derivado de los dos anteriores
                                             + relation de la candidata que lo resolvió
```

P5D ya guarda `resolved_by` y la `relation` de esa candidata. La proyección es directa:

| `availability` | `relation` de la resolvente | `fitness` |
|---|---|---|
| `AVAILABLE` | `MEASURES` | `MEASURES` |
| `PARTIAL` | `PROXY` | `PROXY` |
| `MISSING` / `NOT_APPLICABLE` | — | `INSUFFICIENT` |
| `UNKNOWN` | — | `UNKNOWN` |

**Sobre el vocabulario**: propusiste `DIRECT` / `PROXY` / `INSUFFICIENT` / `UNKNOWN`. Recomiendo **`MEASURES`** en vez de `DIRECT`, porque `MEASURES` ya significa exactamente eso en `catalogo.py` y `DIRECT` sería **un segundo nombre para una idea que ya tiene el suyo** — el error espejo de reutilizar un nombre para dos ideas, y igual de dañino.

### Lo que `FRESH` significa y lo que no

Esto es lo más importante que P6 tiene que heredar intacto:

> **`FRESH` = "al día respecto a su cadencia declarada".**
> **`FRESH` ≠ "sirve para valorar este mecanismo".**

Hoy `demand(org:nvidia)` es simultáneamente:

```
availability  PARTIAL     hay dato, pero no de la variable
freshness     FRESH       al día para una cadencia trimestral
fitness       PROXY       revenue_growth_yoy_pct no es demanda
granularidad  trimestral  el mecanismo pregunta por un cambio, el dato responde con un YoY
```

Cuatro hechos y **solo uno es sobre el tiempo**. Un P6 que lea `FRESH` y concluya "usable" habría deshecho P5D entero.

> **Nota de diseño**: la cuarta línea sugiere que hará falta un eje más adelante — la **granularidad** del dato frente a la del mecanismo. No lo propongo para v1: prefiero que aparezca como un `UNKNOWN` bien explicado a inventarle un catálogo antes de tener un caso que lo exija.

---

## 5. `UNKNOWN` nunca se convierte en cero — cómo hacerlo ejecutable

Tienes razón en que hay **tres** formas de inventar información, no una. Propongo cerrar las tres con reglas de validador, no con disciplina:

| Se prohíbe | Regla ejecutable |
|---|---|
| `impact = 0` | **`magnitude == 0` exige `evidence_ids` no vacío.** Un cero medido lleva su evidencia; un cero por ausencia no puede escribirse |
| `transmission = 0` | un tramo sin coeficiente declarado **no produce fila de magnitud**, en vez de producir una con cero |
| `confidence = low` | P6 **no emite confianza**. Emite `state` + `reason`. Degradar a "baja confianza" es afirmar que sabes algo con poca seguridad, cuando no sabes nada |

Y la forma canónica de un impacto no resuelto:

```
impact:    UNKNOWN
magnitude: null            ← no 0, no "n/d", no ausente del esquema
reason:    REQUIRED_EVIDENCE_MISSING
missing:   [capacity_utilization(tech:cowos)]
```

`magnitude: null` **presente y a null** es distinto de que el campo no exista: obliga a que quien lo lea vea el hueco.

### El defecto por omisión también está prohibido

Ningún `.get(x, 0)`, ningún `or 0`, ningún valor por defecto numérico en toda la capa. La forma de garantizarlo no es un test que lea el código —el proyecto ya aprendió que los tests no deben inspeccionar la prosa— sino **estructural**: el constructor del impacto no acepta magnitud sin unidad, ni unidad sin base, ni cero sin evidencia. Lo que no se puede construir no se puede colar.

---

## 6. Combinar varios mecanismos — la parte difícil

Aquí es donde P6 puede romperse sin que se note.

### Regla 1 · Nunca una suma

Dos mecanismos sobre la misma variable y entidad **no son sumables por defecto**. `INPUT_COST` subiendo el coste y `PRICING_POWER` permitiendo repercutirlo son la misma historia contada dos veces, no dos efectos. P5B ya tropezó exactamente con esto — el resumen de rentabilidad excluye `cost` (`CUENTA_EN_RENTABILIDAD`) precisamente porque sumar variables de distinta polaridad daba `DIVERGENT` donde había una sola historia.

**Propuesta**: P6 entrega una **descomposición**, no un total. Si alguna vez hay un agregado, exige una declaración explícita de independencia entre mecanismos, con su justificación.

### Regla 2 · Un `UNKNOWN` no se deja fuera del reparto

Con N mecanismos, si uno es `UNKNOWN`:

```
total:      UNKNOWN
conocido:   [los que sí se resolvieron, con su magnitud]
unresolved: [los que no, con su motivo]
```

Lo que **no** puede pasar es presentar la suma de los resueltos como si fuera el total. Es la misma trampa que "la media de los que contestaron".

### Regla 3 · El estado agregado es el del peor componente

Ya es la regla del proyecto en dos sitios: P1b (*"el estado de un dominio es el de su peor componente, nunca el del más reciente"*) y P5B (`support` = el del peor tramo). P6 la hereda sin cambios.

### Regla 4 · Horizontes distintos no se combinan

Dos impactos a 1 mes y a 18 meses no son un impacto. Si los horizontes difieren, se reportan por separado o el agregado es `UNKNOWN`.

---

## 7. Lo que P6 puede calcular hoy: **nada**, y está medido

Igual que hice antes de P5B, mido en vez de suponer:

| Requisito | Estado real hoy |
|---|---|
| Las 5 variables de mecanismo en Evidence | **0 de 5** medidas (fijado por test desde P5B) |
| `demand(org:nvidia)` | `PARTIAL` · proxy trimestral |
| `capacity_utilization(tech:cowos)` | `MISSING`, sin candidatas |
| Materialidad de `rel:0046` | **no documentada** (deuda de P5C) |
| Coeficientes de transmisión | **ninguno declarado**, ninguna fuente identificada |
| Líneas base comparables | **no existen** como requisito todavía |

**Conclusión honesta**: P6 v1 devolverá `UNKNOWN` en el 100% de los caminos reales. Su valor en v1 no es calcular, es **hacer imposible calcular mal** — exactamente el papel que tuvo P5B, que también salió `UNKNOWN` en los 25 caminos reales y aun así fue la fase que más restricciones instaló.

Eso implica que **v1 se valida con fixtures sintéticas declaradas**, con el mismo patrón ya usado en P4 (T3–T7) y P5B (5 casos sintéticos + 1 real).

---

## 8. Hallazgo colateral de la medición: el invariante de vocabularios necesita una corrección

Al medir los solapes entre los once vocabularios cerrados del proyecto encontré que **la regla como estaba escrita ya no describe lo que el proyecto hace**:

```
availability × support     →  PARTIAL, UNKNOWN
validity     × support     →  CONTESTED
availability × freshness   →  UNKNOWN
```

`PARTIAL` y `CONTESTED` están compartidos entre capas desde antes de P5D. No creo que sean errores: significan lo mismo sobre sujetos distintos, igual que `UNKNOWN`. Pero entonces el invariante *"nunca reutilizar un vocabulario para conceptos distintos"* está mal enunciado. **Propongo reformularlo**:

> Un token se comparte **si y solo si** significa lo mismo. Dos nombres para una idea (`DIRECT` junto a `MEASURES`) y un nombre para dos ideas (`source_priority` en P0) son **el mismo error visto por sus dos caras**.

Y un riesgo concreto que la medición saca a la luz: **`MEASURED` (nature de Evidence) y `MEASURES` (relation del catálogo) son ideas distintas con nombres casi idénticos**. Una métrica `DERIVED` como `sma20` puede perfectamente `MEASURES` una variable. No propongo renombrar nada ahora —el coste supera el riesgo actual— pero queda registrado.

---

## 9. Criterios de aceptación propuestos para P6 v1

Cierro cuando:

1. Un `EconomicImpact` no se puede construir sin variable, entidad, mecanismo, horizonte y estado.
2. `magnitude` sin `unit` y sin `baseline` se rechaza.
3. `magnitude == 0` sin `evidence_ids` se rechaza.
4. Un mecanismo sin coeficiente declarado **no emite magnitud** (no emite cero).
5. Materialidad `UNKNOWN` ⇒ magnitud `UNKNOWN`, aunque el Δ esté medido.
6. Combinar N mecanismos con uno `UNKNOWN` da total `UNKNOWN` + `conocido[]` + `unresolved[]`, nunca una suma parcial.
7. `fitness` se **deriva** de P5D; P6 no lo declara por su cuenta.
8. `FRESH` no habilita nada por sí solo: hay un test que lo comprueba con `demand(org:nvidia)`, que es `FRESH` y aun así insuficiente.
9. Sobre el grafo real, los caminos de P5C salen `UNKNOWN` con su motivo — y el test lo exige, para que el día que deje de ser cierto se sepa.
10. P6 no escribe en Knowledge, Evidence, Events ni Requirements. Verificado por hash, como en P3/P4/P5A/P5B.

---

## 10. Lo que NO propongo hacer en P6 v1

- **No** añadir materialidad a las relaciones de P2 — es un cambio de esquema de Knowledge y merece su propia decisión.
- **No** abrir ninguna fuente de datos. P5D ya produce la justificación; abrirlas es una decisión aparte.
- **No** dar magnitud en `PRICING_POWER`, hasta que exista fuente para la elasticidad.
- **No** construir el eje de granularidad. Que aparezca como `UNKNOWN` explicado.
- **No** emitir confianza, probabilidad ni score.

---

## 11. Pregunta abierta que necesita tu decisión

**¿De dónde puede salir un coeficiente de transmisión aceptable?**

Es el único punto del diseño donde no tengo una respuesta que cumpla el estándar del proyecto. Las opciones que veo, con lo que cada una implica:

| Opción | Qué es | Coste epistemológico |
|---|---|---|
| **Declarado con fuente** (10-K, nota de la empresa) | igual que `rel:0046` | el más limpio, pero las empresas rara vez publican elasticidades |
| **Estimado del histórico propio** | regresión sobre `data/history/` | introduce inferencia estadística en un sistema que hasta ahora solo declara. Cambia la naturaleza del proyecto |
| **Rango declarado a mano, con justificación** | "entre 0,3 y 0,7 porque…" | auditable, pero es opinión con formato de dato |
| **Ninguno: magnitud siempre `UNKNOWN` en v1** | P6 da signo, materialidad y horizonte; magnitud no | el más conservador. Deja P6 útil pero sin números |

**Mi recomendación es la cuarta para v1**, y que la tercera se evalúe en v2 con una tabla declarada explícitamente como opinión. Pero es una decisión de fondo sobre qué quiere ser el sistema, y es tuya.
