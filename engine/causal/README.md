# Causal Path / Graph Traversal (v1)

```
EVENT + KNOWLEDGE → CAUSAL PATH
```

Descubre y representa los caminos **estructurales** por los que un evento podría transmitirse. **No calcula** probabilidad, impacto, signo económico ni mispricing: primero hay que demostrar que el sistema recorre correctamente la estructura que ya tiene.

```bash
python3 engine/causal/caminos.py sec:NVDA.NASDAQ --explicar 1
python3 engine/causal/caminos.py sec:BTC --profundidad 1
python3 engine/causal/caminos.py sec:XRP --a-fecha 2022-01-01
python3 engine/causal/caminos.py sec:NVDA.NASDAQ --hasta-no-financiera
```

## La distinción que más importa

`traversal_direction` (`FORWARD`/`REVERSE`) es la orientación **estructural** con la que se recorrió una arista: si se fue del sujeto al objeto o al revés. **No es `economic_direction`.** Que un camino se recorra en sentido inverso no dice nada sobre si el efecto sube o baja — ese signo es P5B, y aquí no existe ningún campo que lo insinúe. Un test lo comprueba **sobre el esquema**, no sobre el texto del módulo: `CAMPOS_CAMINO` y `CAMPOS_ARISTA` no contienen ningún nombre económico.

Lo mismo con `polarity`: `AFFIRMS`/`DENIES` es una propiedad del **conocimiento** (si la relación se da o se ha comprobado que no), no del efecto.

## Dos ejes, no un enum

| | |
|---|---|
| `validity` | `VERIFIED` · `PROVISIONAL` · `CONTESTED` — calidad de las aristas |
| `completeness` | `COMPLETE` · `PATH_INCOMPLETE` — si se llegó al objetivo |

Un camino puede estar verificado y no llegar, o llegar por aristas provisionales. Colapsarlos obligaría a ocultar una de las dos verdades — el mismo argumento que en P1b para cobertura y frescura.

Y `incomplete_reason` separa dos cosas que tampoco son la misma: **`DEPTH_LIMIT`** es un límite técnico de esa ejecución; **`NO_FURTHER_KNOWLEDGE`** es que el sistema no sabe más. La profundidad no altera el Knowledge, y hay un test que lo demuestra: subir la profundidad **añade** caminos y no cambia los que ya había.

## Reglas de traversal

1. Sólo aristas **vigentes** en `as_of` (`modelo.vigente`).
2. `polarity=DENIES` **nunca se recorre** — afirma que el enlace no existe, y recorrerlo sería inventar el camino. Pero sí se **detecta** como contradicción sobre las aristas que sí se recorren.
3. Una sola arista `PROVISIONAL` marca el camino entero, y su origen `internal_rule` viaja en `source_refs`.
4. Conjunto de visitados por camino → sin ciclos, con terminación probada sobre una fixture `A→B→C→A`.
5. Las aristas **referencian**, no copian: un test compara campo a campo la proyección con la relación de `knowledge/`.

## Medido sobre el Knowledge real

| | |
|---|---|
| T1 | `NVDA →ISSUED_BY→ nvidia →DOMICILED_IN→ US` · `VERIFIED`, profundidad 2 |
| T2 | `BTC →EXPOSED_TO→ US` · `PROVISIONAL`, fuente `src:thesis-macro-uniforme` (`INTERNAL_RULE`) |
| T3 | XRP↔Coinbase: inalcanzable a 2022-01-01, alcanzable a 2024-01-01 |
| T4 | hacia entidad no financiera: **todos `PATH_INCOMPLETE`**, con los dos motivos representados |
| T7 | profundidad 1/2/3 → 4 / 25 / 89 caminos |

T4 sale incompleto **sin fabricar el caso**: la única entidad no financiera declarada (`tech:defi-smart-contracts`) tiene como únicas relaciones las dos `DENIES`, y una negación no se recorre. La cadena de NVIDIA sigue en `knowledge/pendiente/`, fuera del conocimiento válido, y sólo entrará por el procedimiento de alta de P2.

## Invariancia

P5A es una transformación derivada. `caminos.py` no tiene ninguna llamada de escritura a fichero, y la suite comprueba por hash que `knowledge/` y `data/` no cambian al recorrer.

---

# Economic Causal Mechanism & Direction (v1) — P5B

```
Event + CausalPath + Evidence → CausalAssessment
```

Representa el mecanismo económico, la dirección, la evidencia que la sostiene y lo que falta. **No calcula** impacto, probabilidad, exposición, transmisión, tiempo, mispricing ni oportunidad. Sin ningún campo numérico y sin LLM: los siete mecanismos son reglas declaradas con `rule_id` y `rule_version` que viajan en cada tramo.

```bash
python3 engine/causal/valoracion.py sec:NVDA.NASDAQ --profundidad 2
python3 engine/causal/valoracion.py sec:BTC --accion demand_change --direccion UP
```

## Ausencia no es evidencia de ausencia

La regla más importante de P5B, y la corrección que el diseño recibió antes de implementarse. Que Knowledge no contenga una fila `X SUBSTITUTES Y` significa **«no conozco un sustituto declarado»**, no «no existe sustituto». La comprobación tiene tres estados, no dos:

| en Knowledge | estado | `pricing_power` |
|---|---|---|
| `SUBSTITUTES` AFFIRMS vigente | `KNOWN_SUBSTITUTE` | `UNKNOWN` — hay alternativa, no se puede inferir |
| `SUBSTITUTES` **DENIES** vigente | `VERIFIED_ABSENCE` | `POSITIVE` · **`SUPPORTED`** |
| ninguna fila | `UNKNOWN` | `POSITIVE` · **`PARTIAL`** + supuesto declarado |

Sólo la ausencia **comprobada** permite soporte completo. Es la tercera aparición de la misma invariante: P1b la aplicó a la ausencia de TVL (`NO_APLICA` distingue «no aplica» de «falta») y P2 con `polarity=DENIES`.

## `USES` ≠ `CONSUMES` · `SUPPLIES` ≠ `PRODUCES`

Las fixtures usan **exclusivamente** predicados del vocabulario cerrado de P2. `CONSUMES` y `PRODUCES` no existen ahí y **no se mapean** a los que sí existen, porque no son equivalentes: `USES` puede ser tecnología o infraestructura mientras `CONSUMES` implica flujo económico o físico; `SUPPLIES` es organización→organización mientras `PRODUCES` es organización→producto y no dice a quién se vende. Quedan como candidatos futuros, para cuando un caso real los exija por el procedimiento de alta de P2. No se reabre P2.

## `NO_MECHANISM` es la respuesta correcta a la mayoría de las aristas

`ISSUED_BY`, `LISTED_ON`, `DOMICILED_IN`, `CLASSIFIED_AS` y `EXPOSED_TO` no transmiten nada económicamente. `NVDA →ISSUED_BY→ nvidia` son el mismo sujeto económico visto de dos formas: estampar un signo ahí sería fabricar una inferencia donde sólo hay un cambio de punto de vista.

## El resumen se hace sobre una sola vara de medir

Sumar signos de variables distintas da falsos positivos: *el coste sube* y *el margen baja* son la misma historia contada dos veces, no una divergencia. `overall_direction` sólo cuenta `revenue`, `margin`, `pricing_power` y `demand`; **`cost` queda fuera a propósito**, porque su efecto en la rentabilidad pasa por el margen. Con eso T2 sale `NEGATIVE` —lo que económicamente ocurre— y el cambio de signo real (ingreso arriba y margen abajo en el mismo nodo) sale `DIVERGENT`.

`DIVERGENT` y no `MIXED`: `MIXED` ya es un valor de `traversal_direction` en P5A. Los tres vocabularios de dirección —`AFFIRMS/DENIES`, `FORWARD/REVERSE/MIXED`, `POSITIVE/NEGATIVE/NEUTRAL/UNKNOWN/DIVERGENT`— son disjuntos, y un test lo mantiene.

## Un signo con supuesto nunca está completamente sostenido

El margen no baja *mecánicamente* porque suba el coste: depende de si la empresa puede repercutirlo. Ese supuesto se escribe en `assumptions[]` y el validador **rechaza** cualquier tramo `SUPPORTED` que tenga supuestos declarados.

## El resultado real, hoy

Sobre el Knowledge real, **los 25 caminos desde NVDA dan `UNKNOWN`**. Tres motivos medidos: no existe ni una relación `SUPPLIES`, `USES` o `SUBSTITUTES` afirmativa; las cuatro relaciones verificadas son de identidad o clasificación; y Evidence no mide demanda, capacidad, coste de insumo ni plazo en ninguno de sus tres dominios.

Eso no es un fallo. `UNKNOWN` no significa `economic_direction = 0`: significa *no resuelto*, y cada assessment dice en `requires_evidence[]` exactamente qué variable haría falta. Ese campo convierte un «no lo sé» en una lista accionable de requisitos de información — y es el mecanismo con el que decidir, más adelante, qué fuente nueva merece la pena incorporar.
