# P6.1 · Materiality Model — diseño

**Fecha**: 2026-09-07 · **Estado**: DISEÑO, sin código. Pendiente de revisión.
**Pregunta única**: ¿qué significa *"qué parte de X está realmente expuesta a Y"*?
**Restricción previa**: auditar si la respuesta cabe en `Evidence` **antes** de tocar el esquema de `Knowledge`.

---

## 0. Resumen

| Hallazgo | Consecuencia |
|---|---|
| **P6 v1 ya contiene la ambigüedad**: cuatro significados distintos comparten el nombre `materialidad` | hay que tipar antes de poblar nada |
| **La tabla está mal claveada**: `MATERIALIDAD[relationship_id]` no puede expresar dirección | defecto real de P6 v1, registrado |
| **La cifra existe en fuente primaria, pero anonimizada**: TSMC publica "mayor cliente 19%" sin nombrarlo | atribuirla a NVIDIA sería inferencia |
| **Varía 25% → 22% → 19% en tres años** | es una **observación**, no una propiedad estructural → **Evidence, no Knowledge** |
| Pero el contrato está claveado por **un solo** `asset_id` | falta una **contraparte**, no un `weight` en Knowledge |
| Se puede acotar sin conocer | propongo un estado **`BOUNDED`**: información real sin atribución |

---

## 1. Primero, dos defectos de mi propio P6 v1

Antes de proponer nada, medí lo que ya escribí. Las dos cosas son mías, no heredadas.

### 1.1 Cuatro significados ya comparten el nombre

```
CUSTOMER_DEMAND    % de los ingresos del proveedor que vienen de ese cliente
INPUT_COST         peso del insumo en la base de coste
PRICING_POWER      cuánto del negocio pasa por ese recurso
SUPPLY_SHORTAGE    % del suministro afectado
```

Los cuatro se llaman `materialidad` y los cuatro entran por el mismo hueco (`RM.materialidad(...)`). Es exactamente el `weight = 0.25` genérico contra el que avisas, solo que con un nombre en vez de un número. **Que el validador exija materialidad no sirve de nada si no exige *cuál*.**

### 1.2 La tabla no puede expresar dirección

```python
MATERIALIDAD[relationship_id] -> un solo valor
```

Pero `rel:0046` es `org:tsmc SUPPLIES org:nvidia`, y sobre esa **única** relación hay al menos tres porcentajes distintos:

| Porcentaje | Sujeto | Qué responde |
|---|---|---|
| % de los ingresos de **TSMC** que vienen de NVIDIA | TSMC | si NVIDIA tose, ¿cuánto le importa a TSMC? |
| % de las obleas de **NVIDIA** que fabrica TSMC | NVIDIA | si TSMC falla, ¿cuánto le importa a NVIDIA? |
| % de la **capacidad** de TSMC comprometida con NVIDIA | TSMC | ¿queda margen para otros? |

Una clave por relación solo puede guardar uno. **Materialidad es una propiedad de un par ordenado, no de una relación.**

---

## 2. La medición decisiva: qué publican de verdad las fuentes

No teoricé sobre dónde guardarlo antes de comprobar si existe. Busqué en los dos *filings* que P5C ya tiene verificados.

### TSMC, 20-F FY2025 — lo publica, **anonimizado**

> *"Our largest customer in 2023, 2024 and 2025 accounted for **25%, 22% and 19%** of our net revenue in the respective year."*
> *"Our second largest customer in 2023, 2024 and 2025 accounted for **11%, 12%, and 17%**..."*
> *"our ten largest customers ... accounted for approximately **70%, 76% and 78%** of our net revenue."*

**El número existe. La atribución no.** El 20-F no dice quién es ese cliente. Que "todo el mundo sepa" que los dos primeros son Apple y NVIDIA no es una fuente: escribir `19% → NVIDIA` sería exactamente la inferencia disfrazada de hecho que el proyecto lleva catorce fases impidiendo.

### NVIDIA, 10-K FY2026 — publica lo contrario de lo que hace falta

> *"For fiscal year 2026, sales to one direct customer represented **22%** of total revenue and sales to another direct customer represented **14%**..."*

Es la concentración de **sus clientes**, no de sus proveedores. No dice nada sobre su dependencia de TSMC.

### Lo que **nadie** publica

El porcentaje de obleas de NVIDIA fabricadas por TSMC. Ni el 10-K ni el 20-F lo dan. La deuda registrada en P5C sigue siendo real y **no se resuelve leyendo mejor**.

---

## 3. La respuesta a tu pregunta: `Evidence`, y está medido

No hace falta razonarlo en abstracto. La propia cifra lo dice:

```
mayor cliente de TSMC:   2023 → 25%     2024 → 22%     2025 → 19%
```

**Seis puntos de variación en tres años.** Una propiedad estructural estable no se mueve así. Es una **observación fechada**, con fuente y con periodo — que es la definición exacta de Evidence en este proyecto.

Y hay una segunda prueba, cualitativa: si fuera `Knowledge`, cada publicación anual del 20-F obligaría a editar a mano una relación estructural. `Knowledge` se mantiene a mano *porque su historial de cambios es información*; un número que cambia cada año por el mero paso del tiempo no es eso.

> **Veredicto: no hay que tocar el esquema de P2.** `TSMC SUPPLIES NVIDIA` sigue siendo la relación estructural; el porcentaje es una observación sobre ella.

### Pero hay un problema, y no es donde se esperaba

`Evidence` es una **vista derivada y regenerable** del Data Contract — no es un sitio donde escribir a mano. Y el contrato está claveado así:

```python
METRIC_REQUIRED = {"asset_id", "asset_type", "domain", "metric",
                   "data_as_of", "retrieved_at", "source", "source_priority"}
```

**Un solo `asset_id`.** Una fila de materialidad necesita dos entidades: el sujeto y la contraparte. Ese, y no el esquema de Knowledge, es el cambio mínimo real:

```
     hoy   (asset_id, domain, metric, value, unit, data_as_of, source)
    haría  (asset_id, counterparty, materiality_type, value, unit, ...)
             falta ──┘            └── falta
```

Es un cambio **acotado y en la capa correcta**: el contrato ya sabe de observaciones fechadas con fuente; solo no sabe de pares.

---

## 4. `BOUNDED` — el hallazgo que creo más útil

Que no podamos atribuir el 19% a NVIDIA **no significa que no sepamos nada**. Del 20-F se deduce, sin inferir nada:

```
la exposición de TSMC a CUALQUIER cliente individual es ≤ 19% (2025)
y la de sus diez mayores juntos, 78%
```

Eso está publicado, fechado y es citable. Y es **suficiente para acotar un impacto** aunque nunca lleguemos a conocerlo:

> *el efecto sobre los ingresos de TSMC es, como mucho, el 19% de lo que le pase a un cliente*

Propongo por tanto un cuarto estado para la pieza:

| estado | significa |
|---|---|
| `KNOWN` | valor puntual con fuente y atribución |
| **`BOUNDED`** | **cota superior (o intervalo) con fuente, sin atribución** |
| `UNKNOWN` | podría conocerse, hoy no |
| `NOT_APPLICABLE` | el mecanismo no la necesita |

Y la consecuencia en P6, que me parece lo más valioso de esta fase:

> **una materialidad `BOUNDED` produce una magnitud `BOUNDED`, nunca puntual.**

El sistema podría decir *"como mucho X"* sin decir nunca *"X"*. Sospecho que ése es el techo honesto de este proyecto durante bastante tiempo, y prefiero que sea un estado explícito a que se presente como una limitación temporal.

**`BOUNDED` está libre**: auditado contra los 18 vocabularios cerrados del sistema (42 tokens), no colisiona con ninguno.

---

## 5. La taxonomía: materialidad es una magnitud **tipada y dirigida**

No un porcentaje. Cuatro cosas, siempre juntas:

```
(tipo, sujeto, contraparte, base)
```

De los seis candidatos que listaste, éstos son los que P6 pide de verdad hoy, uno por mecanismo:

| `materiality_type` | Sujeto | Base | Lo pide | ¿Publicado? |
|---|---|---|---|---|
| `revenue_share_from_counterparty` | proveedor | ingresos totales | `CUSTOMER_DEMAND` | **sí, anonimizado** (TSMC 19%) |
| `input_share_of_cost` | quien usa | base de coste | `INPUT_COST` | no |
| `supply_share_from_counterparty` | cliente | suministro total | `SUPPLY_SHORTAGE` | no |
| `capacity_share_committed` | dueño del recurso | capacidad total | `PRICING_POWER` | no |

Cuatro tipos, no un `weight`. Y `revenue_share_from_counterparty(TSMC ← NVIDIA)` es **una fila distinta** de `supply_share_from_counterparty(NVIDIA ← TSMC)`: mismo par, sentido opuesto, conclusiones opuestas.

**Regla que propongo**: cada mecanismo declara **qué tipo** de materialidad necesita, y el validador rechaza una de otro tipo. Hoy `RM.materialidad()` aceptaría cualquiera.

---

## 6. Lo que NO propongo

- **No** añadir `weight` a Knowledge. La medición dice que no es estructural.
- **No** tocar el esquema de P2 en absoluto.
- **No** atribuir el 19% a NVIDIA por plausibilidad, ni con una nota, ni con `support_level: BAJO`. Una atribución sin fuente no mejora por venir etiquetada.
- **No** tocar P5B por lo de CoWoS. Coincido contigo: `INPUT_COST` y `CAPACITY_CONSTRAINT` responden a preguntas económicas distintas, y una relación `USES` no debe implicar automáticamente ninguna de las dos. Que P5D/P6 descubran qué evidencia pediría de verdad `CAPACITY_CONSTRAINT`, como pasó con `capacity_utilization(tech:cowos)`.
- **No** implementar nada de esto todavía.

---

## 7. Alcance propuesto para P6.1, si lo apruebas

Pequeño, y en este orden:

1. **Tipar** `materiality_type` (4 valores) y hacer que cada mecanismo declare cuál necesita. Cierra el defecto 1.1.
2. **Reclavear** la materialidad por `(tipo, sujeto, contraparte)` en vez de por relación. Cierra el defecto 1.2.
3. **`BOUNDED`** como estado de pieza, con la regla `materialidad BOUNDED ⇒ magnitud BOUNDED`.
4. **Una sola fila real**: la exposición de TSMC a su mayor cliente, `BOUNDED` a 19%, citando el 20-F — **sin atribuir a NVIDIA**, y comprobando que P6 la usa para acotar sin llegar a `KNOWN`.
5. Decidir si esa fila vive en el contrato con `counterparty` o en una tabla declarada aparte.

El punto 4 es el que de verdad valida la fase: demuestra que el sistema puede usar una cifra anonimizada para acotar, sin convertirla en una atribución.

---

## 8. La pregunta que te devuelvo

**¿Dónde vive la fila?** Tres opciones, y no tengo una preferencia clara:

| Opción | A favor | En contra |
|---|---|---|
| **Contrato + `counterparty`** | el sitio semánticamente correcto; hereda cobertura, frescura y QA | toca `METRIC_FIELDS`, que hoy alimenta Power BI y el cron |
| **Tabla declarada en `engine/impact/`** | cero riesgo para lo que ya funciona; es lo que ya hacen `cadencias.py` y `catalogo.py` | una observación fechada con fuente **no es** una declaración; sería la primera vez que el proyecto guarda un dato externo fuera del contrato |
| **`knowledge/` como fuente, no como relación** | ya sabe de fuentes citables | Knowledge no guarda series, y esto va a cambiar cada año |

Mi instinto es la primera, precisamente porque `data_as_of` / `retrieved_at` / `source_priority` / cobertura / frescura ya existen y esta cifra los necesita todos. Pero es un cambio en el esquema que sostiene el cron y Power BI, y ésa es una decisión tuya, no mía.
