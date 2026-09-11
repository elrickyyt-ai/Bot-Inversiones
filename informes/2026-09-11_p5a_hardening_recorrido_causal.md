# P5A hardening — el recorrido causal deja de definirse por ausencia

**Fecha**: 2026-09-11 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Decisión**: **D-53**
**Cierra**: D-49 (recomendación registrada) y D-52 (coste medido de la lista negra)
**Fase**: P5A — Causal Path / Graph Traversal. No avanza a ninguna fase nueva.

---

## 0. Qué problema se cerraba

La definición no se reinventó: se recuperó **literal** de `docs/DECISIONES.md`, D-49:

> **C — no restringir el recorrido; exigir ≥1 arista `CAUSAL` en el camino emitido**

D-49 midió las tres variantes y descartó A y B. Dejó C **evaluada y no aplicada**, con una
recomendación explícita: aplicarla como refactor propio (`P5A hardening`), fuera del backfill,
porque *el sistema no debe deducir semántica por ausencia de una excepción*.

D-52 convirtió ese coste en evidencia: declarar identidad **correcta y verificada** (los
instrumentos de WBA y Mobilicom) hizo aparecer cuatro caminos que conectaban NVDA con esas
empresas por el solo hecho de cotizar en el mismo mercado. Ninguno con una arista causal.
La lista negra no los veía porque **no estaban en ella**.

---

## 1. FACT — lo que se midió

Comando reproducible (no escribe nada; el script vive en el scratchpad de la sesión y su
contenido está transcrito íntegro al final de este informe, §9):

```
python3 auditoria_d53.py
```

### 1.1 Caminos totales / con contenido causal / sin él / eliminados / añadidos

```
origen                 prof   total  causales   sin-causal  eliminados  anadidos
sec:NVDA.NASDAQ           3      98        87           11          11         0
sec:IBM.NYSE              3      98        85           13          13         0
sec:XOM.NYSE              3      86        78            8           8         0
org:nvidia                3      73        59           14          14         0
sec:BTC                   2      33        21           12          12         0
sec:XRP                   2      33        21           12          12         0
sec:NVDA.NASDAQ           2      29        23            6           6         0
sec:NVDA.NASDAQ           1       4         2            2           2         0
TOTAL                           454       376           78          78         0
```

**Añadidos: 0.** No puede ser de otro modo: la variante C **no restringe el recorrido**, así
que el conjunto causal es por construcción un subconjunto del conjunto recorrido. Hay un test
que lo comprueba como propiedad, no como conteo.

### 1.2 Las 78 formas eliminadas, clasificadas una a una

```
    30  LISTED_ON|LISTED_ON                           causal=False
     9  LISTED_ON                                     causal=False
     8  LISTED_ON|LISTED_ON|ISSUED_BY                 causal=False
     6  ISSUED_BY                                     causal=False
     4  ISSUED_BY|DOMICILED_IN|DOMICILED_IN           causal=False
     3  ISSUED_BY|DOMICILED_IN                        causal=False
     3  ISSUED_BY|CLASSIFIED_AS                       causal=False
     2  ISSUED_BY|CLASSIFIED_AS|CLASSIFIED_AS         causal=False
     2  DOMICILED_IN|DOMICILED_IN                     causal=False
     2  ISSUED_BY|LISTED_ON|LISTED_ON                 causal=False
     2  DOMICILED_IN|DOMICILED_IN|CLASSIFIED_AS       causal=False
     1  DOMICILED_IN                                  causal=False
     1  CLASSIFIED_AS                                 causal=False
     1  ISSUED_BY|LISTED_ON                           causal=False
     1  CLASSIFIED_AS|CLASSIFIED_AS                   causal=False
     1  DOMICILED_IN|DOMICILED_IN|ISSUED_BY           causal=False
     1  CLASSIFIED_AS|CLASSIFIED_AS|ISSUED_BY         causal=False
     1  CLASSIFIED_AS|CLASSIFIED_AS|DOMICILED_IN      causal=False

  caminos legitimos eliminados (con arista causal): 0
  caminos espurios eliminados: 78 (100%)
```

**Legítimos eliminados: 0.** Es el criterio que hizo descartar la variante B, y aquí se
comprueba forma a forma, no por muestreo.

### 1.3 La forma concreta que hizo descartar la variante B

```
  sec:NVDA.NASDAQ        EXPOSED_TO|EXPOSED_TO|LISTED_ON  28 -> 28
  sec:IBM.NYSE           EXPOSED_TO|EXPOSED_TO|LISTED_ON  28 -> 28
  sec:XOM.NYSE           EXPOSED_TO|EXPOSED_TO|LISTED_ON  28 -> 28
```

Sobrevive entera. El contenido económico está en las dos primeras aristas; la tercera solo
sitúa el resultado. La variante B la habría destruido (84 caminos, D-49).

### 1.4 Fixtures sintéticas — el criterio que D-49 no pudo cumplir

```
  T5_ciclo             4 -> 4
  T6_contradiccion     1 -> 1
```

Y una contradicción sigue saliendo `CONTESTED`: ser causal no la silencia.

### 1.5 Los cuatro caminos de D-52

```
  STRUCTURAL_ONLY_PATH   LISTED_ON|LISTED_ON           sec:NVDA.NASDAQ -> ven:NASDAQ -> sec:WBA.NASDAQ
  STRUCTURAL_ONLY_PATH   LISTED_ON|LISTED_ON           sec:NVDA.NASDAQ -> ven:NASDAQ -> sec:MOB.NASDAQ
  STRUCTURAL_ONLY_PATH   LISTED_ON|LISTED_ON|ISSUED_BY sec:NVDA.NASDAQ -> ven:NASDAQ -> sec:WBA.NASDAQ -> org:walgreens
  STRUCTURAL_ONLY_PATH   LISTED_ON|LISTED_ON|ISSUED_BY sec:NVDA.NASDAQ -> ven:NASDAQ -> sec:MOB.NASDAQ -> org:mobilicom
```

Los cuatro **siguen existiendo** y los cuatro **salen del conjunto causal**. Que sigan
existiendo importa: cotizar en el mismo mercado es un hecho verdadero; lo falso era
presentarlo como causalidad.

### 1.6 `IDENTITY_MONOTONICITY`, medida sobre fixture sintética

```
  BASE            total=  3  causales=  2   ['ISSUED_BY|SUPPLIES', 'ISSUED_BY|USES']
  CON_IDENTIDAD   total=  8  causales=  2   ['ISSUED_BY|SUPPLIES', 'ISSUED_BY|USES']
```

`CON_IDENTIDAD` añade emisión, cotización en el **mismo** mercado, domicilio en el **mismo**
país y una sucesión de instrumento. Todo verdadero, nada causal. El grafo crece 3 → 8; el
conjunto causal **no se mueve**.

---

## 2. FINDING — lo que la medición descubrió y no se buscaba

### 2.1 La primera aplicación de la variante C era arquitectónicamente incorrecta

**Esto no es un detalle de implementación y no se presenta como si el diseño final hubiera
sido el primero.**

La lectura inmediata de *"exigir ≥1 arista `CAUSAL` en el camino emitido"* fue filtrar dentro
de `descubrir()` (con `solo_causales=True` por defecto). **Rompió 7 tests.** Antes de tocarlos
se clasificaron uno a uno, según §3 del protocolo de informes, en vez de darlos por caducados:

| Test | Qué usaba | Veredicto |
|---|---|---|
| `TestTresVigencia` (×3) | un camino `LISTED_ON` para comprobar la **vigencia temporal** (XRP/Coinbase 2020/2022/2024) | **uso legítimo no causal** |
| `TestUnoRecorridoReal` (×3) | `ISSUED_BY\|DOMICILED_IN` como el camino canónico T1 | **uso legítimo no causal** |
| `test_valoracion.TestReal` | el mismo camino, **a propósito sin mecanismo**, para exigir que P5B devuelva `UNKNOWN` | **uso legítimo no causal** |

Ninguno estaba caducado. Los siete preguntaban cosas verdaderas que **no son causales**.
`descubrir()` no es el recorrido causal: es el recorrido, y tiene consumidores legítimos que
preguntan por estructura, por identidad y por vigencia.

**El error de fondo**: se confundió *"qué caminos se emiten como causales"* con *"qué caminos
existen"*. La variante C habla de lo primero. Filtrar lo segundo habría sido, otra vez,
hacer desaparecer conocimiento verdadero — la misma clase de fallo que la lista negra, con el
signo cambiado.

**Cómo se supo**: porque los tests fallaron y se clasificaron en vez de reescribirse. Si se
hubieran relajado, el cambio habría pasado en verde y habría sido incorrecto igual.

### 2.2 Siguen existiendo DOS mecanismos, y solo uno es semántico

`PREDICADOS_NO_CAUSALES` (D-23 / D-45 / D-50) **saca aristas del índice**: `BENCHMARKED_BY`,
`COMPARED_TO` y `SUCCEEDED_BY` no se recorren en absoluto. Medido:

```
sec:DWDP.NYSE, profundidad 2 → 0 caminos   (rel:0057 SUCCEEDED_BY existe y está vigente)
```

Con la variante C esa lista deja de ser necesaria **como salvaguarda causal** — un camino de
solo `SUCCEEDED_BY` saldría `STRUCTURAL_ONLY_PATH` de todos modos. Pero sigue teniendo un
efecto que **no** es el que se le pedía: suprime conocimiento estructural verdadero del
recorrido, incluso para las preguntas no causales que §2.1 acaba de demostrar que existen.
No se toca en esta iteración (queda en §6, deuda abierta), pero la duplicidad queda registrada.

### 2.3 El validador no comprobaba la semántica del camino

`validar()` verificaba `validity`, `completeness` y `direction_status` contra su vocabulario,
pero un camino podía llegar sin `path_semantics` y pasar. Corregido: un camino que no la
declara o que la declara fuera del vocabulario es un error. **No declararla dejaría que el
consumidor la dedujera por ausencia**, que es exactamente lo que D-49 prohíbe.

---

## 3. INTERPRETATION — qué significan los números

- **78 de 454 (17,2%)** de los caminos emitidos sobre el Knowledge real no tenían ninguna
  causalidad declarada dentro. No eran caminos "débiles": eran caminos **vacíos** presentados
  con la misma forma que los llenos.
- **El 51% de lo eliminado (40 de 78) cruza un hub de mercado** — dos aristas `LISTED_ON`
  seguidas, que es literalmente *"y ademas alguien mas cotiza aqui"*. Es la forma
  que crece cuando se declara identidad correcta: cada instrumento nuevo en un mercado ya
  declarado multiplica pares. **La lista negra empeoraba conforme el sistema mejoraba.**
- **`IDENTITY_MONOTONICITY` es compatible con los casos legítimos existentes** — 777 tests en
  verde, cero regresión — pero **no se declara invariante permanente**, como pedía el encargo.
  Se ha comprobado sobre una fixture sintética y sobre el Knowledge real de hoy; no se ha
  comprobado sobre un grafo con relaciones causales *derivadas* de identidad, que es el caso
  donde podría fallar legítimamente (una fusión **sí** transfiere exposición económica).
  Hasta que exista ese caso, la propiedad queda **propuesta y medida**, no cerrada.

---

## 4. DECISION — qué se decidió y qué se hizo

**D-53** (registrada en `docs/DECISIONES.md`): se aplica la variante C de D-49, **etiquetando,
no filtrando**.

| | |
|---|---|
| `descubrir()` | **firma intacta**, devuelve **todos** los caminos. Cada uno etiquetado con `path_semantics` |
| `caminos_causales()` | **nueva**. Es el recorrido causal: los caminos con `path_semantics == CAUSAL_PATH` |
| `path_semantics` | `CAUSAL_PATH` \| `STRUCTURAL_ONLY_PATH`. Campo del contrato, validado |
| La regla | `≥1` arista de clase `CAUSAL`. **Una basta**; no se exige que todas lo sean (eso era la variante B) |

**La regla es semántica y no menciona ninguna entidad.** Un test lo comprueba con
`inspect.getsource()` sobre las cuatro funciones que la implementan, con un patrón derivado de
los prefijos del propio modelo — no sobre una lista fija de nombres prohibidos.

### 4.1 Clasificación semántica (cinco clases, refina las cuatro de D-45)

```
CAUSAL       SUPPLIES · USES · DEPENDS_ON · SUBSTITUTES · EXPOSED_TO
IDENTITY     ISSUED_BY · SUCCEEDED_BY          qué entidad hay detrás / en qué se convirtió
STRUCTURAL   LISTED_ON                          dónde cotiza
MEASUREMENT  BENCHMARKED_BY · COMPARED_TO       relación de medida (D-21)
REFERENCE    DOMICILED_IN · CLASSIFIED_AS       atributo de clasificación o localización
```

Se separó `IDENTITY` de `STRUCTURAL` porque no es lo mismo *"qué entidad está detrás de este
instrumento"* que *"en qué mercado cotiza"*: la primera resuelve identidad y es el **puente**
imprescindible para llegar del instrumento a su cadena económica; la segunda solo sitúa.

**`semantica_de()` devuelve `REFERENCE` para lo no declarado.** Un predicado nuevo no se
vuelve causal por que nadie lo haya prohibido. Es la inversión exacta de la lista negra, y
tiene test propio.

### 4.2 Qué NO se hizo

- **No se restringió el recorrido.** Era la variante B: D-49 midió que destruye 84 caminos
  legítimos.
- **No se usó una lista `ALLOW = {predicate1, …}`** con el sentido que el encargo prohibía
  (una lista cuyo efecto sea eliminar caminos causales legítimos). La lista existe, pero
  **clasifica**, no filtra el recorrido: su efecto medido sobre caminos legítimos es 0.
- **No se cambió ningún consumidor** (`valoracion.py`, `resolver.py`, `impacto.py`). Los cuatro
  puntos que llaman a `descubrir()` están en bloques `__main__` de CLI y siguen viendo todos
  los caminos, ahora etiquetados. Cambiarlos es P5B/P5D/P6, no P5A — §6.
- **No se tocó `data/`, `history/`, `knowledge/` ni ninguna fase posterior.** P5A es una
  transformación derivada y hay un test que comprueba por hash que no escribe nada.
- **No se avanzó** a recuperación histórica de precios A/B/C, `Run Record`, `Hypothesis Object`
  ni `Backtest Evidence Protocol`.

---

## 5. Qué cambió — ficheros

| Fichero | Qué |
|---|---|
| `engine/knowledge/modelo.py` | **nuevo**: `CAUSAL`/`IDENTITY`/`STRUCTURAL`/`MEASUREMENT`/`REFERENCE`, `SEMANTICA_PREDICADO`, `PREDICADOS_CAUSALES`, `semantica_de()`, `tiene_contenido_causal()` |
| `engine/causal/caminos.py` | **nuevo**: `CAUSAL_PATH`, `STRUCTURAL_ONLY_PATH`, `SEMANTICAS_CAMINO`, `caminos_causales()`. **modificado**: `CAMPOS_CAMINO` (+`path_semantics`), `_componer()` etiqueta, `validar()` comprueba el vocabulario, `explicar()` lo dice en la pregunta 3 |
| `tests/test_p5a_hardening.py` | **nuevo**, 27 tests |
| `tests/fixtures/caminos/identidad_monotonia.json` | **nuevo**, fixture sintética `BASE` / `CON_IDENTIDAD` |
| `tests/test_caminos.py` | **modificado**: el test frágil de D-52 se reescribe (§3 del protocolo) |

### 5.1 Los diez tests obligatorios del encargo

| # | Pedido | Test |
|---|---|---|
| 1 | NVDA/NASDAQ/MOB deja de ser causal | `TestTresGrafoReal::test_el_camino_al_instrumento_reutilizado_deja_de_ser_causal` |
| 2 | NVDA/NASDAQ/WBA deja de ser causal | `…::test_el_camino_a_la_otra_empresa_del_mercado_deja_de_ser_causal` |
| 3 | arista de benchmark | `TestDosPredicadosNoCausales::test_la_arista_de_benchmark_no_aporta_contenido_causal` |
| 4 | `SUCCEEDED_BY` | `…::test_succeeded_by_no_aporta_contenido_causal` |
| 5 | `ISSUED_BY` | `…::test_issued_by_solo_no_hace_causal_un_camino` |
| 6 | `LISTED_ON` | `…::test_listed_on_solo_no_hace_causal_un_camino` |
| 7 | caso causal legítimo a través de una relación estructural | `TestTresGrafoReal::test_un_camino_causal_que_atraviesa_una_relacion_estructural_sobrevive` |
| 8 | comparación completa antes/después sobre fixture | `TestCuatroFixturesCompletas` (T5 4→4, T6 1→1) |
| 9 | `as_of` | `TestCincoVigencia` (3 tests) |
| 10 | identidad nueva correcta no crea causalidad espuria | `TestSeisIdentidadMonotonia` (4 tests) |

Los tests 3 y 4 llevan **doble guarda**: el predicado sigue fuera del índice (lista negra
previa) **y**, si alguien lo dejara entrar, no haría causal a ningún camino. La segunda mitad
se comprueba sobre `tiene_contenido_causal()` directamente, porque la primera impide llegar a
ella por el recorrido.

Los nombres reales (NVDA, NASDAQ, MOB, WBA) aparecen **en los tests** porque son la evidencia
medida en D-52, no parte de la regla. El test
`TestUnoLaReglaEsSemantica::test_la_regla_no_menciona_ninguna_entidad_concreta` vigila
justamente esa separación.

---

## 6. OPEN DEBT — deuda abierta

| Deuda | Dónde queda registrada | Estado |
|---|---|---|
| **`IDENTITY_MONOTONICITY` no es invariante permanente** | este informe §3 + `TestSeisIdentidadMonotonia` | **Deliberado**, como pedía el encargo. Falta el caso donde podría fallar con razón: una fusión **sí** transfiere exposición económica, y ahí añadir identidad verdadera **debe** crear causalidad. Hasta declarar ese caso, la propiedad está medida, no cerrada |
| **Dos mecanismos para lo mismo**: `PREDICADOS_NO_CAUSALES` (saca del índice) y la variante C (etiqueta lo emitido) | §2.2 + comentario en `caminos.indice()` | `SUCCEEDED_BY` fuera del índice hace que `sec:DWDP.NYSE` no tenga **ningún** camino, ni siquiera no causal. La respuesta a *"¿qué instrumento sucedió a este?"* vive hoy solo en `instrumentos.sucesor_de()`. No se unificó: sería un cambio de comportamiento de P5A fuera del alcance |
| **Ningún consumidor usa `caminos_causales()` todavía** | §4.2 | P5B usa a propósito un camino sin mecanismo (`ISSUED_BY\|DOMICILED_IN`) para demostrar que devuelve `UNKNOWN`. Cambiarlo al conjunto causal borraría esa demostración. Decidir qué capa consume qué conjunto es trabajo de P5B/P5D/P6 |
| **`path_semantics` no llega a Power BI ni a la Web App** | §8 | P5A no escribe en `data/`. Ningún consumidor externo lee caminos hoy |
| **La clasificación es por predicado, no por relación** | `SEMANTICA_PREDICADO` | Una relación `EXPOSED_TO` con soporte débil pesa igual que una fuerte para decidir si el camino es causal. `support_level` y `status` siguen viajando en la arista y **no** se han fundido con la semántica: son ejes distintos, igual que `validity` y `completeness` |

---

## 7. Supuestos invalidados

1. **Propio, el más importante**: *"aplicar la variante C = filtrar en `descubrir()`"*. Falso.
   Lo demostraron 7 tests que resultaron ser usos legítimos no causales, no tests caducados
   (§2.1).
2. **De D-49**: *"la variante C pierde caminos y eso convierte el cambio en una revisión de los
   tests de una fase cerrada"*. Cierto para el diseño que D-49 tenía en mente (filtrar).
   Con etiquetado, la pérdida es **0**: 777 tests en verde, ningún test de P5A reescrito por
   conteos. El único test reescrito es el que **D-52 escribió frágil a propósito para que se
   rompiera hoy**.
3. **Del validador**: se daba por supuesto que el vocabulario de un camino estaba completo.
   `path_semantics` podía faltar y pasar (§2.3).

---

## 8. Impacto sobre fases anteriores, y cómo se verificó

- **P5A**: única fase modificada. `descubrir()` conserva firma y conteos.
- **P5B/P5C/P5D/P6/P6.1**: sin cambios de código. Verificado con la suite completa.
- **Knowledge**: sin cambios. `python3 engine/knowledge/consulta.py --validar` → `PASS`
  (39 entidades · 66 relaciones · 3 conceptos · 14 fuentes).
- **Data Contract**: sin cambios. `python3 engine/contract/qa.py --require-parquet` →
  `QA CORE: PASS · QA PARQUET: PASS · STATUS: VERIFIED` (287 particiones, 0 incidencias).
- **Consumidores** (Power BI, Web App, cron): **cero impacto**. P5A no escribe en `data/` y un
  test lo comprueba por hash además de revisar el código fuente en busca de aperturas de
  escritura.

### Tests

```
antes:   750
después: 777   (+27, todos en tests/test_p5a_hardening.py)
python3 -m unittest discover -s tests   →   Ran 777 tests — OK
```

---

## 9. El script de auditoría, íntegro

Se ejecuta desde la raíz del repositorio y no escribe nada. Se transcribe aquí en vez de
versionarlo porque es una medición puntual, no una herramienta del sistema; las propiedades que
deben seguir siendo ciertas viven en `tests/test_p5a_hardening.py`, que sí está versionado.

```python
import collections, datetime, json, os, sys
R = "/home/user/Bot-Inversiones"
sys.path.insert(0, os.path.join(R, "engine", "causal"))
sys.path.insert(0, os.path.join(R, "engine", "knowledge"))
import caminos, modelo

HOY = datetime.date(2026, 9, 7)
k = modelo.cargar()
forma = lambda c: "|".join(a["predicate"] for a in c["edges"])

COMBOS = [("sec:NVDA.NASDAQ", 3), ("sec:IBM.NYSE", 3), ("sec:XOM.NYSE", 3),
          ("org:nvidia", 3), ("sec:BTC", 2), ("sec:XRP", 2),
          ("sec:NVDA.NASDAQ", 2), ("sec:NVDA.NASDAQ", 1)]

for origen, prof in COMBOS:
    todos = caminos.descubrir("ev:d53", origen, k, HOY, max_depth=prof)
    caus  = caminos.caminos_causales("ev:d53", origen, k, HOY, max_depth=prof)
    ids_c = {c["path_id"] for c in caus}
    elim  = [c for c in todos if c["path_id"] not in ids_c]
    anad  = ids_c - {c["path_id"] for c in todos}
    print(origen, prof, len(todos), len(caus), len(elim), len(anad))
    # y para cada eliminado: modelo.tiene_contenido_causal(c["edges"]) debe ser False
```

(La versión ejecutada imprime además el desglose por forma, la comparación de
`EXPOSED_TO|EXPOSED_TO|LISTED_ON`, las fixtures sintéticas, `IDENTITY_MONOTONICITY` y los
cuatro caminos de D-52; todos esos resultados están literales en §1.)

---

## 10. Estado al cerrar

- **D-49**: recomendación **ejecutada**. La variante C está aplicada como `P5A hardening`,
  fuera del backfill, tal y como se registró.
- **D-52**: el coste de la lista negra **deja de existir**. El test frágil que se escribió para
  romperse hoy se ha reescrito a lo que sigue siendo cierto.
- **El sistema ya no deduce semántica por ausencia de una excepción** en la capa causal. Un
  camino es causal porque **contiene** causalidad declarada.

**Detenido aquí**, como pedía el encargo.
