# P6.1 · Materiality Model — diseño

**Fecha**: 2026-09-07 · **Revisión 2** · **Estado: CERRADO**, listo para implementar.
**Pregunta única**: ¿qué significa *"qué parte de X está realmente expuesta a Y"*?

---

## 0. La corrección que cambia el diseño

La revisión 1 decía *"materialidad es propiedad de un par ordenado"*. Es demasiado fuerte, y por serlo me llevó a plantear un cambio en el contrato que resulta que **no hace falta**. La formulación correcta:

> **La materialidad usada por una evaluación causal debe estar resuelta respecto al sujeto y, cuando corresponda, a su contraparte; la evidencia que la sustenta puede ser de entidad, de relación, o una cota derivada sobre un conjunto de contrapartes.**

De ahí sale todo lo demás. En particular: **la materialidad no se almacena, se deriva.**

### Lo que esto disuelve

La revisión 1 terminaba con una pregunta abierta — *¿añadimos `counterparty` a `METRIC_FIELDS`?* — con el aviso de que eso tocaría el esquema que sostiene el cron y Power BI.

**La pregunta desaparece.** Si la materialidad es derivada, la observación que la sustenta es **de entidad**:

```
asset_id   TSMC
metric     largest_customer_revenue_share
value      19        unit  %
data_as_of 2025-12-31
source     TSMC 20-F FY2025
```

Una sola entidad. **Cabe en el contrato tal cual, sin tocar `METRIC_FIELDS`.** La contraparte aparece únicamente en la derivación, que se calcula y no se guarda — igual que `data/coverage.json`, `data/requirements.json` y la propia Evidence.

---

## 1. Tres niveles, y solo el primero se almacena

### A · Evidence — el hecho publicado

```
TSMC · largest_customer_revenue_share · 19% · 2025 · TSMC 20-F
```

Es una observación fechada, con fuente, sobre **una** entidad. Va a Evidence (vía el contrato). **No toca Knowledge.**

### B · Materiality — la derivación auditable

```
Evidence:   el mayor cliente de TSMC representó ≤19% de sus ingresos (2025)
Knowledge:  TSMC SUPPLIES NVIDIA, vigente en 2025
─────────────────────────────────────────────────────────────────────
Materiality: TSMC ← NVIDIA
             status      BOUNDED
             upper_bound 19 %
             basis       SUPPLIER_REVENUE_EXPOSURE
             scope       POPULATION_BOUND
             derivation  largest_customer_revenue_share
             evidence_ids [...]
             support     SUPPORTED
```

**Esto ya no es el hecho publicado: es una derivación**, y por eso lleva su propia trazabilidad. No se guarda: se recalcula, como todo lo derivado del proyecto.

### C · Economic Impact — el consumo

```
materiality BOUNDED ≤19%  →  magnitude BOUNDED, nunca POINT
```

Y nunca, bajo ninguna circunstancia:

```
19%  →  exposición asumida = 19%
```

---

## 2. La derivación, y las dos condiciones que la hacen válida

La cota se deduce sin inferir nada: si el mayor cliente de TSMC es el 19%, **cualquier** cliente concreto es ≤19%. Es deductivo, no probabilístico. Pero solo si se cumplen dos cosas.

### 2.1 La relación tiene que existir en Knowledge

Sin `TSMC SUPPLIES NVIDIA` no sabemos siquiera que NVIDIA está en esa población. Es exactamente el papel que le corresponde a Knowledge: **aporta la relación que permite aplicar la cota**, no la cota.

### 2.2 La relación tiene que estar vigente en el periodo de la evidencia

Esto no lo había visto en la revisión 1, y tiene una consecuencia concreta. El 20-F publica **tres** cifras:

| Ejercicio | Mayor cliente | `rel:0046` vigente | ¿Aplicable a NVIDIA? |
|---|---|---|---|
| 2023 | 25% | no | **no** |
| 2024 | 22% | no | **no** |
| 2025 | **19%** | sí (desde 2025-01-27) | **sí** |

`rel:0046` está atestiguada desde el 2025-01-27 porque eso es lo que el 10-K acredita —P5C decidió deliberadamente no extrapolar hacia atrás—, así que **las cotas de 2023 y 2024 no se pueden aplicar a NVIDIA**. No porque sean viejas, sino porque en esos años el sistema no sabe que NVIDIA fuera cliente de TSMC.

> **Regla**: una cota poblacional solo se aplica a una contraparte si la relación que la incluye en la población está vigente en el periodo de la observación.

Es la misma disciplina de no extrapolar `valid_from`, propagada un nivel hacia arriba.

### 2.3 Y el alcance de la población limita a quién puede acotar

Una cota observada sobre la entidad **S** solo acota contrapartes **C** para las que hay una relación S↔C atestiguada. De ahí que:

```
org:samsung SUPPLIES org:nvidia   +   TSMC: mayor cliente ≤19%
        →  NADA sobre Samsung
```

Samsung no es contraparte de TSMC en Knowledge: es proveedor de NVIDIA. La cota no le alcanza, y el sistema tiene que decirlo en vez de callarse.

---

## 3. Los cuatro vocabularios, cerrados

Auditados contra los 18 vocabularios cerrados del sistema.

### `materiality_status`

| Valor | Significa | Token |
|---|---|---|
| `POINT` | valor puntual con fuente y atribución | libre |
| `BOUNDED` | cota (o intervalo) con fuente, sin atribución puntual | libre |
| `UNKNOWN` | podría conocerse, hoy no | compartido, mismo significado |
| `NOT_APPLICABLE` | el mecanismo no la necesita | compartido, mismo significado |

**`BOUND` y `BOUNDED` no pueden existir los dos.** En tu revisión aparecen ambos (`BOUND` en el objeto derivado, `BOUNDED` en el resto); me quedo con **`BOUNDED`**, que es el que ya estaba auditado y el que concuerda con `magnitude BOUNDED`.

`POINT` y `BOUNDED` son epistemológicamente distintos y por eso son dos valores: `19%` y `≤19%` no son la misma afirmación.

### `materiality_scope`

`ENTITY` · `RELATIONSHIP` · `POPULATION_BOUND` — los tres libres.

Hoy **solo `POPULATION_BOUND` es alcanzable**: es el único tipo de evidencia que existe. `RELATIONSHIP` requeriría que alguien publicara el par explícito, que es justo lo que ninguna fuente hace.

### `materiality_basis` — cuatro de tus seis, y por qué no las otras dos

Aplicando tu regla — *solo los que aparezcan en mecanismos existentes*:

| `basis` | Mecanismo | Sujeto | Base | ¿Publicado? |
|---|---|---|---|---|
| `SUPPLIER_REVENUE_EXPOSURE` | `CUSTOMER_DEMAND` | proveedor | sus ingresos | **sí, anonimizado** |
| `COST_SHARE` | `INPUT_COST` | quien usa el insumo | su base de coste | no |
| `VOLUME_SHARE` | `SUPPLY_SHORTAGE` | cliente | su suministro total | no |
| `CAPACITY_SHARE` | `PRICING_POWER` | dueño del recurso | su capacidad total | no |

**`DEMAND_SHARE` no se introduce**: ningún mecanismo actual la pide.

**`CUSTOMER_REVENUE_SHARE` tampoco, y esto merece un párrafo**: describe *la misma magnitud* que `SUPPLIER_REVENUE_EXPOSURE`, mirada desde el otro lado de la mesa. Tener las dos sería dos nombres para una idea — el error espejo que el proyecto acaba de reformular como invariante. Me quedo con `SUPPLIER_REVENUE_EXPOSURE` porque **nombra al sujeto**, que es justo lo que hay que resolver.

### `materiality_basis_evidence`

Toda materialidad derivada tiene que poder responder a las cinco preguntas, y son campos, no prosa:

| Pregunta | Campo |
|---|---|
| ¿de dónde sale? | `evidence_ids` |
| ¿sobre qué entidad? | `observed_on` |
| ¿sobre qué fecha? | `observed_period` |
| ¿qué relación permite aplicarla? | `applied_via` (el `relationship_id`) |
| ¿punto o cota? | `status` |

---

## 4. La cota trivial no se emite

`UNKNOWN` no es `0%`, y tampoco es `BOUNDED ≤100%`. Un límite matemáticamente cierto pero vacío es peor que un `UNKNOWN` honesto, porque **parece información**.

> **Regla**: una cota solo se emite si es **estricta** — menor que el 100%, y procedente de una observación, nunca de un tope aritmético. Sin observación no hay `BOUNDED`; hay `UNKNOWN`.

---

## 5. Los fixtures que cierran la fase

Los tres primeros son tuyos; el cuarto sale de la condición temporal.

| # | Entrada | Debe producir | Y **no** debe producir |
|---|---|---|---|
| 1 | `largest_customer 19%` + `TSMC SUPPLIES NVIDIA` (2025) | `NVIDIA ≤ 19%`, `BOUNDED` | `NVIDIA = 19%` |
| 2 | lo mismo + `Samsung SUPPLIES NVIDIA` | **nada sobre Samsung** | cualquier cota sobre Samsung |
| 3 | materialidad `BOUNDED` en P6 | `magnitude BOUNDED` | `magnitude POINT`, ni `UNKNOWN` |
| 4 | `largest_customer 25%` (2023) + `rel:0046` desde 2025 | **nada**: fuera de vigencia | aplicar el 25% a NVIDIA |

El 2 y el 4 son los que de verdad prueban la fase: demuestran que el sistema sabe **hasta dónde llega** una cota poblacional, en el eje de las entidades y en el del tiempo.

---

## 6. Lo que NO hay que tocar

- **`METRIC_FIELDS`**: la observación es de entidad y cabe tal cual. La revisión 1 se equivocaba.
- **Knowledge (P2)**: ni `weight` ni `counterparty`. La cifra va 25% → 22% → 19% en tres años; no es estructural.
- **P5B**: `INPUT_COST` y `CAPACITY_CONSTRAINT` responden a preguntas distintas y `USES` no implica ninguna. Que P5D/P6 descubran qué evidencia pediría de verdad.
- **Power BI y Web App**: quedan desacoplados. Ver §7.
- **La atribución del 19% a NVIDIA**: ni con nota, ni con `support_level: BAJO`. Una atribución sin fuente no mejora por venir etiquetada.

---

## 7. Power BI y Web App: especificación de consumo, no contrato arquitectónico

`docs/03` y `docs/04` se escribieron cuando el mundo era `JSON → Data Contract → Power BI/Web App`. Siguen siendo válidos en lo que importa —la división de funciones, y sobre todo la regla de que **ambos son consumidores y no la lógica analítica**— pero ya no describen el backend.

Lo que ha quedado obsoleto en ellos: `FactMetrics` como representación principal, `data/*.json`, las métricas como único nivel analítico, y los conteos de septiembre. **La regla de que el Data Contract precede a la UI sigue vigente; lo que cambió es qué representa hoy el Data Contract.**

No se rediseñan ahora. Cuando llegue el momento, ambos consumirán una **proyección** del estado del motor, no al revés.

---

## 8. Alcance de implementación propuesto

1. Cerrar los cuatro vocabularios (`esquema_materialidad.py`), con la regla de la cota trivial y `BOUNDED` en `ESTADOS_PIEZA` de P6.
2. `resolver_materialidad(basis, sujeto, contraparte, as_of)` — deriva; no almacena. Comprueba vigencia y alcance de población.
3. Cablear `RM.materialidad()` a esa derivación, tipada por mecanismo: cada mecanismo declara **qué `basis`** necesita y el validador rechaza otra.
4. Reclavear por `(basis, sujeto, contraparte)` en vez de por `relationship_id`.
5. Regla `materialidad BOUNDED ⇒ magnitud BOUNDED` en el validador de P6.
6. Una fila real de Evidence: `TSMC · largest_customer_revenue_share · 19% · 2025`, citando el 20-F.
7. Los cuatro fixtures de §5.

---

## 9. Roadmap acordado

```
P0 … P6      ✅
P6.1  Materiality            ← esta fase
P6.2  Quantification unlocks
P7    Market Impact
P8    Mispricing
P9    Thesis integration
P10   Portfolio
P11   Outcome / Calibration
──────────────────────────────
CONSUMPTION  Power BI + Web App — se adaptan al modelo consolidado, no lo dictan
```

---

## 10. Lo que P6.1 añade al desacoplamiento

Con esta fase, `UNKNOWN` deja de ser binario:

```
direction    POSITIVE     (P5B)
materiality  BOUNDED ≤19% (P6.1)
magnitude    BOUNDED      (P6)
```

Mucho más informativo que `UNKNOWN`, y sin haber inventado una sola cifra puntual. La cadena de desacoplamiento queda:

```
CAUSE ≠ MECHANISM ≠ EVIDENCE ≠ MATERIALITY ≠ QUANTIFIABILITY ≠ MAGNITUDE ≠ MARKET IMPACT
```
