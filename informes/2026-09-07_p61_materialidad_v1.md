# P6.1 · Materiality v1

**Fecha**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2`
**Diseño previo**: `docs/06-diseno-p61-materialidad.md` (revisión 2, cerrado)

---

## 1. El resultado

```
MATERIALIDAD mat:SUPPLIER_REVENUE_EXPOSURE:org:tsmc:org:nvidia
  base       SUPPLIER_REVENUE_EXPOSURE  (POPULATION_BOUND)
  ESTADO     BOUNDED  <= 19.0%
  observado  org:tsmc · 2025 · aplicada via rel:0046
  motivos    DERIVED_FROM_POPULATION_BOUND
      · cota, no atribución: la fuente dice que el mayor cliente de org:tsmc
        representa 19.0%, sin nombrarlo. Que org:nvidia sea ese cliente NO se afirma
      · 2 observaciones descartadas por no ser aplicables, no por ser peores:
        obs:…2024 (RELATIONSHIP_NOT_VALID_IN_PERIOD), obs:…2023 (idem)
```

Y en P6, sobre el tramo real de la cadena de P5C:

```
  materialidad   BOUNDED  <= 19.0%          ← antes UNKNOWN
  motivos        MATERIALITY_ONLY_BOUNDED   ← antes MATERIALITY_UNKNOWN
```

La magnitud **sigue `UNKNOWN`**, y es correcto: le faltan coeficiente y línea base. Lo que ha cambiado es que uno de los cuatro bloqueos ha pasado de *"no sabemos nada"* a *"sabemos que es como mucho el 19%"*.

---

## 2. Los cuatro pasos, separados como pediste

```
OBSERVATION → APPLICABILITY CHECK (entidad · relación · vigencia) → DERIVATION → status
```

La separación no es estética. Si la aplicabilidad estuviera mezclada con la búsqueda, una observación **válida pero inaplicable** acabaría indistinguible de un hueco de datos — y el sistema mandaría a buscar una fuente que ya tiene. De ahí los dos motivos:

| Caso | `status` | motivo |
|---|---|---|
| TSMC ← IBM | `UNKNOWN` | `EVIDENCE_EXISTS_BUT_NOT_APPLICABLE` + `NO_RELATIONSHIP` |
| NVIDIA ← CoWoS (`COST_SHARE`) | `UNKNOWN` | `NO_SUPPORTING_EVIDENCE` |

Los dos dan `UNKNOWN`, pero **no son el mismo `UNKNOWN`**, y hay un test que lo fija. El primero dice *"no os molestéis, ya la tenemos y no sirve para esto"*; el segundo, *"buscad una fuente"*.

---

## 3. El test central: no es `MIN`, ni `MAX`, ni `LATEST`

Sobre el Knowledge real, el 19% es a la vez **la menor y la más reciente** de las tres cotas — así que un `min()` o un `latest` accidental habrían pasado el test por casualidad.

La fixture invierte el caso: con `rel:0046` vigente **solo en 2023**, la aplicable pasa a ser el **25%**, que es la **mayor** y la **más antigua**.

```python
self.assertEqual(m["upper_bound"], 25.0, "se eligió por aplicabilidad, no por valor")
```

La selección es por **intersección temporal con la vigencia de la relación causal**, y ahora está demostrado, no afirmado.

---

## 4. Tres decisiones que tomé al implementar

### 4.1 `POINT` no se introduce

El diseño pedía `POINT` / `BOUNDED` / `UNKNOWN` / `NOT_APPLICABLE`. Pero `ESTADOS_PIEZA` de P6 ya tiene **`KNOWN`** con exactamente el significado de `POINT`: *"hay un valor puntual sostenido"*. Añadir `POINT` al lado serían **dos nombres para una idea**, el error espejo que el proyecto acaba de codificar como invariante.

Magnitud y materialidad comparten por tanto el mismo vocabulario de cuatro estados, y `BOUNDED` se añade a las dos: una cota es igual de expresable en ambas, y de hecho **una materialidad acotada nunca podrá dar una magnitud puntual**.

### 4.2 Una inversión en tu mensaje

Escribiste: *"No se introducen `DEMAND_SHARE` ni el alias semánticamente redundante `SUPPLIER_REVENUE_EXPOSURE`"*. El diseño aprobado decía lo contrario: el alias redundante es **`CUSTOMER_REVENUE_SHARE`**, y el que se conserva es `SUPPLIER_REVENUE_EXPOSURE`, porque **nombra al sujeto**, que es lo que hay que resolver.

Como todos los demás puntos de tu lista reflejaban el diseño con exactitud, lo he tomado por un lapsus de transcripción y he implementado lo diseñado. **Si lo que querías era el nombre contrario, es un cambio de una línea** en `BASES` y `POBLACION`.

### 4.3 La fila real no cabía en el contrato

El diseño concluía que la observación es de entidad y por tanto cabe sin tocar `METRIC_FIELDS`. Al ir a escribirla apareció el límite real, medido:

```
storage.asset_type_of("TSM") → None
data/assets/ → ADA BTC DOT EA ETH IBM NVDA SOL US XOM XRP
```

**El contrato guarda observaciones sobre ACTIVOS, y TSMC es una ENTIDAD que no es un activo.** Meterla exigiría inventar un activo `TSM` sin serie de precios, sin dominio y sin cadencia, solo para colgar una fila: ensuciaría DimAsset, cobertura y frescura a cambio de nada.

Es la misma familia de hueco que `capacity_utilization(tech:cowos)`. Las tres observaciones viven de momento en `engine/impact/observaciones.py`, **explícitamente marcado como lo que es**: un fichero de observaciones fechadas con fuente citable, no un fichero de declaración como `cadencias.py` o `catalogo.py`. **Deuda registrada, no disimulada** — cuando el contrato admita observaciones de entidad, esas filas se mueven y el fichero desaparece.

Lo que no hice: guardarlas en `knowledge/` (una observación fechada no es una relación estructural) ni inventar el activo.

---

## 5. Lo que el validador impide

| Regla | Forma ejecutable |
|---|---|
| cota trivial | `upper_bound >= 100` rechazado: un tope aritmético parece información sin serlo |
| cota sin origen | `BOUNDED` exige `evidence_ids` **y** `applied_via` |
| cota que puntualiza | `BOUNDED` con `value` rechazado |
| punto que acota | `KNOWN` con `upper_bound` rechazado |
| cota → punto | `magnitude KNOWN` con `materiality BOUNDED` rechazado |
| sin resolver con número | `UNKNOWN`/`NOT_APPLICABLE` con `value` o `upper_bound` rechazado |
| par sin fuente del par | una cota sobre una contraparte concreta solo puede venir de `POPULATION_BOUND` |

Y la materialidad **no se almacena**: un test comprueba que `materialidad.py` no contiene `open(` ni `json.dump`.

---

## 6. Verificación

```bash
python3 -m unittest discover -s tests            # 447 tests · OK   (422 → +25)
python3 engine/contract/qa.py --require-parquet  # STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   # PASS
python3 engine/impact/impacto.py org:nvidia
```

**Nuevos**: `engine/impact/{esquema_materialidad,observaciones,materialidad}.py` · `tests/test_materialidad.py`
**Modificados**: `esquema_impacto.py` (`BOUNDED`, cota en magnitud, `MATERIALITY_ONLY_BOUNDED`) · `requisitos_magnitud.py` (`BASIS_POR_MECANISMO`) · `impacto.py` (cableado) · `tests/test_impacto.py` (firmas) · `README.md`

**Knowledge, Evidence, el contrato, P5A, P5B y P5D no se han tocado.** Ninguna deuda de arquitectura anterior abierta.

---

## 7. Estado de los bloqueos hacia una magnitud

| Bloqueo | Antes de P6.1 | Ahora |
|---|---|---|
| Materialidad | `UNKNOWN` | **`BOUNDED ≤19%`** |
| Fitness de la variable | `PROXY` | `PROXY` |
| Coeficiente de transmisión | ninguno | ninguno |
| Línea base | ninguna | ninguna |

De los cuatro, uno resuelto a cota. Los otros tres siguen, y el orden de valor no cambia: líneas base y coeficientes son declaraciones que requieren decidir de dónde salen; el *fitness* requiere una fuente de demanda que no sea el ingreso.
