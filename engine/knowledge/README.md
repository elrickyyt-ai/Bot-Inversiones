# Knowledge Model (v1)

Diseño en `https://claude.ai/code/artifact/7a4a03c9-3f6a-418c-826a-ae1b8d2c8153` (P2). Esto **no es un grafo ni una base de datos**: son ficheros JSON pequeños, mantenidos a mano y versionados en git, con un validador que se niega a aceptarlos si incumplen las reglas de abajo.

El objetivo de v1 no es «tener una base de conocimiento». Es demostrar que se puede sacar del código el conocimiento estructural que hoy vive ahí de forma accidental y representarlo de forma explícita, trazable y temporalmente válida, **sin cambiar todavía el comportamiento del sistema**. Ningún motor lo consulta aún.

## Por qué existe

`docs/00-arquitectura-conceptual.md` ya lo pedía en la Fase 0: *«No hay identidad de instrumentos (master data). Splits, cambios de ticker, ADRs, doble cotización, delistados… cada motor puede referirse "al mismo" activo con datos distintos y el sistema fallará en silencio»*. Estaba numerada como **capa 0** en el diagrama del Paso 2 y nunca se construyó.

Trece relaciones del mundo real están hoy escritas dentro del código —seis de ellas son tablas de identidad para los mismos once activos, mantenidas por separado en cuatro ficheros, con el mapeo `symbol → defillama_chain` **duplicado** en dos—. El seed A las extrae y las cita por `fichero:línea`.

## Uso

```bash
python3 engine/knowledge/consulta.py --validar                     # valida todo el conjunto
python3 engine/knowledge/consulta.py NVDA                          # qué sabe el sistema sobre NVDA
python3 engine/knowledge/consulta.py BTC --hacia US                # qué sabe sobre esa relación
python3 engine/knowledge/consulta.py XRP --hacia ven:coinbase --a-fecha 2022-01-01
python3 engine/knowledge/consulta.py NVDA --camino-a-no-financiero
```

El criterio de éxito de P2 no es «tenemos 45 relaciones». Es poder preguntar por una relación y obtener **quién, qué, desde cuándo, hasta cuándo, por qué lo creemos y dónde está la evidencia**. Un JSON que valida pero que nadie puede interrogar no demuestra nada.

## Las cuatro reglas que el validador hace cumplir

1. **Ninguna relación sin fuente resoluble.** Conocer algo y poder citarlo son cosas distintas, y sólo la segunda entra aquí.
2. **`nature` no admite `INFERRED`.** Knowledge representa el mundo que el sistema considera conocido; la inferencia es una *operación* sobre ese conocimiento: se calcula, se muestra y se descarta. Si pudiera persistirse junto al conocimiento, en dos meses nadie sabría cuál de las dos cosas está leyendo.
3. **Toda relación tiene vigencia.** `valid_to: null` significa «vigente hasta nuevo aviso», nunca «para siempre».
4. **Negar exige fuente igual que afirmar.** `polarity: DENIES` es una comprobación, no una ausencia disfrazada.

Y una quinta que no es del validador sino del proceso: **ningún resultado del motor causal puede modificar una relación estructural.** El conocimiento se actualiza sólo por `nueva fuente → verificación → actualización controlada`. Por eso `modelo.py` no tiene ninguna función de escritura.

## `support_level`, no `confidence`

Escala ordinal de tres valores (`ALTO`/`MEDIO`/`BAJO`), deliberadamente no multiplicable: el proyecto ya tiene tres escalas 0-100 y P0 demostró que una de ellas significa cosas distintas según el dominio. Un cuarto número invitaría a multiplicarlos y a producir un decimal con aspecto de medición.

Y **no se llama `confidence` a propósito**: no es la probabilidad de que la relación sea cierta, sino el grado de respaldo que tiene hoy *dentro del sistema*. `confidence` queda reservado para la inferencia posterior.

## `BTC → EXPOSED_TO → US`

La relación que motivó todo esto entra como `nature: ASSERTED`, `status: PROVISIONAL`, `support_level: BAJO`, con fuente de tipo `INTERNAL_RULE`. Su `statement` dice literalmente que `build_thesis()` aplica el contexto macro de esa región a todos los activos por igual **sin ninguna medición de exposición específica**, y su `verification_method` que la regla del software no demuestra exposición económica.

Nunca `STRUCTURAL` ni `VERIFIED`: una regla del propio código no se convierte en un hecho del mundo por el hecho de estar escrita. Es el tipo de conocimiento que este sistema debe **verificar y reemplazar**, no legitimar.

## La fuente es una entidad

`publisher` es un `entity_id`, no una cadena. Eso permite preguntar *qué sabemos únicamente porque lo dijo la parte interesada* — una relación `org:tsmc SUPPLIES org:nvidia` cuya única fuente fuese un comunicado de NVIDIA tiene un sesgo que ningún entero capturaría. Y **no hay escala numérica**: la autoridad se deriva de `tipo` + `publisher`. Las dos escalas de `source_priority` que ya existen (mercado en `schema.py`, periodística en `news/sources.py`) se quedan donde están: la solución a tener dos escalas incompatibles no es fabricar una tercera que las unifique, es no volver a mezclarlas.

## El bloque B no valida, a propósito

`knowledge/pendiente/nvidia_cadena.json` contiene la cadena NVIDIA → TSMC → CoWoS → HBM/materiales. **No existe hoy ninguna fuente en este repositorio que la justifique.** Vive fuera del directorio que `modelo.cargar()` lee, con el documento que habría que citar para promover cada relación y el sesgo a anotar.

La consecuencia observable: `consulta.py NVDA --camino-a-no-financiero` responde `NO PATH` y explica por qué. El sistema demuestra que no conoce el mundo en vez de completarlo.

## Lo que Knowledge reemplazará (todavía no)

`crypto/fetch_data.py:20-25`, `build.py:30-32`, `technical/fetch_data.py:14-16`, `technical/fetch_backfill.py:60-62` y `equity/score.py:114` son seis tablas de identidad para los mismos activos. `trading_calendar.py` deduce el mercado del `asset_type` en vez de leer `LISTED_ON`. `thesis.py:81-82` aplica macro a todo. **Ninguna de estas sustituciones forma parte de v1**: v1 son unos ficheros, un validador, una consulta y 28 tests.
