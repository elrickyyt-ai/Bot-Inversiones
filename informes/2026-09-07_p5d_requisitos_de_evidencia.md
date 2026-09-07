# P5D · Evidence Gap → Data Requirement

**Fecha**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2`
**Encargo**: una etapa pequeña entre P5B y P6. Convertir `requires_evidence` en una especificación formal resoluble, sin afirmar equivalencias no demostradas.

---

## 1. Qué se ha construido

`engine/requirements/` — tres ficheros, ningún motor existente tocado salvo una declaración añadida a `cadencias.py`.

```
EVENT → CAUSAL PATH → ECONOMIC MECHANISM → REQUIRED EVIDENCE
                                              ↓  [P5D]
                                        AVAILABLE EVIDENCE → (P6 IMPACT)
```

P5B dejaba `requires_evidence = ["demand(org:nvidia)", "capacity_utilization(tech:cowos)"]` como texto dentro de un tramo. P5D lo parsea, lo **deduplica** y lo resuelve contra el contrato real, con los cinco estados que pediste.

---

## 2. El resultado sobre la cadena de P5C

```
REQUISITOS DE EVIDENCIA — 2026-09-07   (2 distintos)
  disponibilidad: {'MISSING': 1, 'PARTIAL': 1}
```

### `demand(org:nvidia)` → `PARTIAL` · `FRESH`

```
  concepto   — sin declarar (UNDECLARED)
  observable NVDA
  candidatas
    · revenue_growth_yoy_pct   PROXY   FRESH   2026-07-31
        confusor: ingreso = precio x volumen. Una subida del ingreso puede venir
        enteramente del precio con demanda plana, o incluso cayendo. Además es
        interanual y trimestral: no distingue un cambio de demanda de un efecto
        de comparación contra el año anterior.
  DISPONIBILIDAD PARTIAL   resuelto con revenue_growth_yoy_pct
  motivos        ONLY_PROXY
  bloquea        2 tramos · CUSTOMER_DEMAND
```

**El límite que pusiste, implementado literalmente**: `revenue` no se convierte en `demand`. Se declara como proxy, con su confusor, y `PARTIAL` es el techo — lo impone el validador, no la buena voluntad de quien lo lea.

De los cinco observables que listaste (revenue, revenue de centros de datos, unidades enviadas, pedidos, cartera de pedidos), este sistema tiene **uno, y en variación en vez de en nivel**. Los otros cuatro no están en el catálogo: una lista de candidatas que no se pueden leer sería una lista de deseos, no una declaración.

### `capacity_utilization(tech:cowos)` → `MISSING`

```
  observable — ninguno
  candidatas — ninguna declarada
  motivos    NO_CANDIDATE_METRIC, NO_OBSERVABLE
      · ninguna métrica del contrato observa capacity_utilization en una entidad
        de tipo technology
      · tech:cowos además no tiene ningún observable: ni asset_id propio ni un
        valor que la represente vía ISSUED_BY
  bloquea    6 tramos · CAPACITY_CONSTRAINT, INPUT_COST
```

**Éste es el hallazgo que justifica la fase**: lo que bloquea a P6 no es el algoritmo de impacto. Es que la utilización de capacidad de CoWoS **no la publica ninguna fuente que este sistema tenga**, y ahora eso está escrito con nombre, motivo y a cuántos tramos bloquea — en vez de ser un `UNKNOWN` sin explicar.

---

## 3. Las tres reglas del validador

| Regla | Qué impide |
|---|---|
| **1. Relación declarada o no existe** | que `revenue` pase a ser `demand` porque ambos suban. Toda candidata lleva `relation` + `justification`; todo `PROXY` lleva su `confounder` o se rechaza |
| **2. Solo-proxy nunca llega a `AVAILABLE`** | que un proxy se haga pasar por medición. Techo `PARTIAL`. Misma regla que P5B aplica a un signo que depende de un supuesto |
| **3. `NOT_APPLICABLE` exige declaración** | que la ausencia de dato se degrade a "no aplica", convirtiendo un hueco en una respuesta |

La tabla `NO_APLICA_VARIABLE` está **vacía hoy**, y eso importa: ningún requisito puede salir `NOT_APPLICABLE`. Su análoga de P1b (`cadencias.NO_APLICA`) sí tiene entradas — el TVL de BTC y XRP, comprobado. Esa diferencia es la que separa una comprobación de una suposición, y hay un test que la fija.

---

## 4. Vocabulario: importado, no copiado

Los cinco estados que pediste (`AVAILABLE`/`PARTIAL`/`MISSING`/`NOT_APPLICABLE`/`UNKNOWN`) **ya existían** en `cobertura.py` desde P1b, como literales dentro de una función. Se han subido a `cadencias.ESTADOS_COBERTURA` y P5D los **importa**, no los redefine.

Es la misma pregunta ("¿existe el dato?") sobre un sujeto distinto: un requisito de mecanismo en vez de un par activo × dominio. Copiarlos es exactamente como `source_priority` acabó significando dos cosas según quién lo leyera (hallazgo de P0).

**Un matiz que descubrí escribiendo el test**: exigí que los dos ejes fueran conjuntos disjuntos, por analogía con las tres direcciones de P5B, y falló. La analogía era mía, no del proyecto — en P5B `MIXED` y `DIVERGENT` son conceptos **distintos** y por eso no pueden compartir token; aquí `UNKNOWN` significa **lo mismo** en ambos ejes ("no había declaración con la que comparar", literal en `cobertura.py`), así que compartirlo es correcto y separarlo habría creado dos nombres para una idea. El test ahora fija que compartan `UNKNOWN` **y nada más**.

---

## 5. Un fallo real que este mismo diseño atrapó

Al escribir `catalogo.py` declaré la candidata de `price` sobre el dominio `"technical"`. El contrato lo llama **`"tecnico"`**.

El resolutor **no fallaba**: devolvía `MISSING` con motivo `CANDIDATE_WITHOUT_DATA` — es decir, **presentaba una errata mía del catálogo como si fuera un hueco de datos**, que es exactamente la confusión que toda esta capa existe para impedir. `price(sec:BTC)` salía `MISSING` teniendo BTC treinta mil filas de precio.

Corregido, y con guardia permanente: `catalogo.dominios_metricas_declaradas()` + un test que comprueba que cada par `(dominio, métrica)` declarado existe de verdad en `cadencias.CADENCIAS`. Ahora `price(sec:BTC)` sale `AVAILABLE` · `STALE` — disponible y caducado a la vez, que es justo el punto de los dos ejes de P1b aplicado a un requisito.

---

## 6. `ISSUED_BY`: transmitir ≠ identificar

`demand(org:nvidia)` pregunta por una **organización**, pero las métricas viven bajo `NVDA`, que pertenece a `sec:NVDA.NASDAQ` — un **security**. El puente es `ISSUED_BY`.

Ese predicado está en `SIN_MECANISMO` de P5B porque **no transmite ningún efecto económico**. Y por la misma razón —P5B, literal: *"la acción y la empresa son el mismo sujeto económico visto de dos formas"*— es exactamente el predicado correcto para **identificar**. Distinguir *transmitir* de *identificar* es lo que hace que esto no sea una inferencia encubierta.

Se anota en el resultado, no se esconde:

> *el dato se observa sobre `sec:NVDA.NASDAQ` (NVDA), no sobre `org:nvidia` directamente: ISSUED_BY identifica al mismo sujeto, no transmite nada*

---

## 7. La regla epistemológica, ahora transversal y con test

Recogí las tres formas que nombraste en un bloque único, `TestInvariantesEpistemicos`, que comprueba cada una **donde vive**:

| Distinción | Capa | Cómo se comprueba |
|---|---|---|
| `NO RELATION` ≠ `RELATION DENIES` | P2 | toda relación `DENIES` tiene `source_id` y `verification_method` |
| `NO EVIDENCE` ≠ `EVIDENCE OF NO EFFECT` | P5B | `UNKNOWN` y `NEUTRAL` son valores distintos; la cadena real sale `UNKNOWN` y **ningún** tramo sale `NEUTRAL` |
| `NO SOURCE` ≠ `SOURCE SAYS IT DOES NOT EXIST` | P5D | `MISSING` y `NOT_APPLICABLE` distintos; el segundo exige `DECLARED_NOT_APPLICABLE` |

Y una cuarta que las une: **`UNKNOWN` nunca es permisivo en ninguno de los tres ejes** — es el peor valor, no uno intermedio.

Están juntas a propósito: si alguien afloja una, se rompen las cuatro a la vez.

---

## 8. Sobre Samsung

Coincido en no añadirlo automáticamente, y **el sistema ya marca ese límite solo**: crear `SUBSTITUTES` porque dos empresas suministren a NVIDIA sería precisamente inferir una relación desde una coincidencia. La sustituibilidad técnica/económica necesita su propia evidencia.

Lo que sí desbloquearía darlo de alta como `SUPPLIES` es distinto y menor: hoy la comprobación de tres estados de P5B devuelve `UNKNOWN` sin poder decir si es que no hay alternativa o que no se sabe. Queda como candidata documentada en `pendiente/`, sin promover.

---

## 9. Criterio de cierre

Lo que pediste, punto por punto:

```
P5B → requires_evidence
  → P5D resuelve cada requirement como AVAILABLE|PARTIAL|MISSING|NOT_APPLICABLE|UNKNOWN   ✅
  → requirement → concept → candidate metric(s) → source → freshness → evidence          ✅
  → sin afirmar equivalencias no demostradas                                             ✅ (regla 1 + 2 del validador)
```

`concept` sale `UNDECLARED` en las cinco variables: ninguna tiene concepto en `knowledge/concepts/`. Es una **ausencia medida**, no un hueco por rellenar — declarar un concepto vacío para que la casilla no quede a `null` sería el error que el proyecto lleva diez fases evitando. Hay un test que exige que, si algún día se declara uno, exista de verdad.

---

## 10. Verificación

```bash
python3 -m unittest discover -s tests            # 381 tests · OK   (354 → +27)
python3 engine/contract/qa.py --require-parquet  # STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   # PASS
python3 engine/requirements/resolver.py org:nvidia
```

**Ficheros nuevos**: `engine/requirements/{esquema_requisito,catalogo,resolver}.py` + `README.md` · `tests/test_requisitos.py`
**Modificados**: `engine/contract/cadencias.py` (declara `ESTADOS_COBERTURA`) · `.gitignore` (`data/requirements.json`, derivado)

Ningún motor existente cambia de comportamiento: `cadencias.py` solo gana una declaración que antes vivía como literales en `cobertura.py`.

---

## 11. Lo siguiente

P6 ya tiene una base empírica en vez de solo una arquitectura: sabe **qué** le falta, **por qué** y **a cuántos tramos bloquea**. El orden natural ahora:

1. **Decidir sobre `capacity_utilization(tech:cowos)`** — hoy `MISSING` sin candidatas. La pregunta ya no es "¿abrimos una fuente?" sino "¿existe alguna fuente pública que publique esto?", que es una pregunta contestable.
2. **Ampliar el catálogo solo con lo que el contrato ya emite** — cada entrada nueva es una declaración con justificación, no un descubrimiento.
3. **P6 · Economic Impact**, sabiendo de antemano qué requisitos entrarán como `PARTIAL` y cuáles bloquearán.

**Deuda registrada**: `demand(org:nvidia)` sale `FRESH` con `revenue_growth_yoy_pct` del 2026-07-31 porque su cadencia declarada es trimestral. Es correcto por cadencia, pero un requisito de demanda resuelto con un dato de hace cinco semanas merece que P6 lo mire dos veces — la frescura dice que el dato está al día para su cadencia, no que sirva para el mecanismo.
