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
