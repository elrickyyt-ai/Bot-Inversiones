# D-21 — implementación de la ontología de benchmark

**Fecha**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Base**: `34e1f62`
**Alcance**: solo la ontología y su validación. **No se ha introducido ningún benchmark concreto**, ninguna serie de índice, ni `HistoricalReactionProfile`, `reaction_gap`, shrinkage, scoring, pesos, BUY/SELL, rediseño de Power BI ni `Evidence Eligibility` universal.

**Verificación**:

```
python3 -m unittest discover -s tests            491 → 521 tests · OK
python3 engine/contract/qa.py --require-parquet  STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   PASS (25 entidades · 48 relaciones · 10 fuentes)
git status --short data/ knowledge/              vacío
```

Ficheros tocados: **5**. `data/` y `knowledge/` sin cambios — la ontología se implementa sin declarar todavía ningún dato.

---

## 1. Qué se midió antes de tocar nada

| Comprobación | Resultado |
|---|---|
| `modelo.validar(modelo.cargar())` antes del cambio | sin incidencias |
| Predicados que recorre `caminos.indice()` | **todos**, sin filtrar |
| Entidades de tipo `benchmark` en `knowledge/` | 0 |
| Relaciones con predicado de referencia | 0 |

La segunda es la que produjo el hallazgo del §8.

## 2. Cambios realizados

| Fichero | Qué |
|---|---|
| `engine/knowledge/modelo.py` | tipo de entidad `benchmark`, dos predicados, campo `role`, bloque `benchmark` en entidades, cinco reglas de validación nuevas, `PREDICADOS_NO_CAUSALES` |
| `engine/causal/caminos.py` | `indice()` excluye los predicados de referencia (§8) |
| `engine/events/estudio_resultados.py` | elegibilidad **por familia de medida**; `benchmark_elegible()` con las cuatro condiciones |
| `tests/test_estudio_resultados.py` | `TestSuficiencia` reescrito a `TestElegibilidadPorFamilia` |
| `tests/test_benchmark_ontologia.py` | **nuevo**, 27 tests |

## 3. Vocabulario

### Tipo de entidad

```
benchmark = "referencia metodologica contra la que se mide una reaccion;
             no es un instrumento analizado"
```

No es un `security` —*"instrumento negociable"*— porque un índice no se negocia, no tiene sector ni mercado de cotización. Un ETF que replica un índice **sí** es negociable, y por eso el benchmark declara con qué clase de serie se construye.

### Bloque `benchmark` de la entidad

Exigido **solo** cuando `type == "benchmark"`, y prohibido en cualquier otra (un sector no tiene metodología):

```
methodology_version      un cambio de metodología del proveedor no puede pasar inadvertido
composition_source       PUBLISHED_LEVEL · ETF_NAV · CONSTRUCTED
point_in_time_capable    ¿el proveedor restata la serie hacia atrás?
calendar                 equity · crypto
serie_desde / serie_hasta ventana real de disponibilidad
```

### Dos predicados, no uno con un flag

```
BENCHMARKED_BY   (security → benchmark)             habilita ABNORMAL_RETURN
COMPARED_TO      (security → security | benchmark)  NO lo habilita nunca
```

Lo que cambia entre ellos no es un matiz: es si la relación confiere o no semántica de retorno anormal. Que `COMPARED_TO` admita un objeto de tipo `benchmark` es lo que permite que `^NDX` sea *comparison reference* de una acción sin ser su benchmark formal.

### Roles

```
MARKET       referencia general del mercado del activo
SECTOR       referencia del sector económico
ASSET_CLASS  referencia de la clase de activo      ← DECLARADO, NO ACTIVO
PEER         otro instrumento comparable            ← NUNCA benchmark formal
```

`ASSET_CLASS` está en `ROLES_NO_ACTIVOS` y **el validador lo rechaza**. Es el patrón de **D-10** con `ESTIMATED`: el token se nombra para que salte el día que alguien lo use, en vez de aparecer sin que nadie lo note. Su definición no está cerrada — para una acción estadounidense `MARKET` (mercado estadounidense) y `ASSET_CLASS` (renta variable) son cosas distintas, y para un cripto coincidirían. Activarlo antes de fijar cuál de las dos lecturas es sería el error que evitó D-13.

Reactivarlo cuesta **una línea**: quitarlo de `ROLES_NO_ACTIVOS`.

## 4. Invariantes que el validador hace cumplir

| # | Invariante | Por qué |
|---|---|---|
| 1 | Un `PEER` no puede ser benchmark formal | produce `PEER_RELATIVE_RETURN`, nunca `ABNORMAL_RETURN` |
| 2 | `role=PEER` exige objeto `security`; `MARKET`/`SECTOR` exigen objeto `benchmark` | el rol y lo que el objeto es no pueden contradecirse |
| 3 | **Nadie es referencia de sí mismo** | el retorno anormal sería cero por construcción |
| 4 | **Un `(activo, rol, periodo)` admite exactamente una asignación** | defensa estructural contra el *benchmark selection bias* |
| 5 | `composition_source = CONSTRUCTED` se rechaza | una referencia hecha con los activos que el sistema ya sigue está seleccionada *ex post* |
| 6 | `role` obligatorio en los predicados de referencia, prohibido fuera | sin él no se sabe qué representa la referencia |
| 7 | Los predicados de referencia **no son aristas causales** | §8 |

La 4 merece detalle: vigencias que **se solapan** son un error; vigencias que **se suceden** son un cambio de benchmark documentado, y se admiten. Es lo que convierte la elección en un acto de curación con fecha de commit en vez de una decisión del código.

## 5. Elegibilidad por familia de medida

Antes de D-21 había **una** puerta: sin retorno anormal no se agregaba nada. Demasiado gruesa.

```
FAMILIAS_DE_MEDIDA
    RAW_RETURN             no necesita referencia
    PEER_RELATIVE_RETURN   necesita comparison reference declarada
    ABNORMAL_RETURN        necesita benchmark formal + 4 condiciones
    VOLUME_CHANGE          no necesita referencia
    VOLATILITY_CHANGE      no necesita referencia
```

Resultado real, sobre los mismos 52 eventos:

```
RAW_RETURN             utilizable=True   n=52  minimo=30  SUFICIENTE
ABNORMAL_RETURN        utilizable=False  n=52  minimo=40  MEDIDA_NO_CALCULADA (SIN_BENCHMARK_EN_EL_CONTRATO)
PEER_RELATIVE_RETURN   utilizable=False  n=52  minimo=40  MEDIDA_NO_CALCULADA (SIN_ASIGNACION_DECLARADA)
VOLUME_CHANGE          utilizable=False  n=52  minimo=30  MEDIDA_NO_CALCULADA
```

**La misma evidencia, dos respuestas distintas.** Eso es lo que la puerta única impedía.

Los mínimos son por `(familia, pregunta)`, declarados y conservadores. `ABNORMAL_RETURN` exige **40** frente a los **30** de `RAW_RETURN`: no es arbitrario, lleva encima el error de estimación del propio benchmark.

**El `10` de `_pct_in_window()` no se ha convertido en umbral global**, y hay un test que lo comprueba: verifica que `10` no aparece entre los mínimos declarados **y** que el módulo de cripto sigue negándose con menos de 10 observaciones. `engine/crypto/score.py` no se ha tocado.

### Las cuatro condiciones de `benchmark_elegible()`

```
1. semánticamente compatible   predicado BENCHMARKED_BY y rol distinto de PEER
2. temporalmente válido        vigencia de la asignación Y ventana de serie del benchmark
3. observación disponible      calendario del benchmark == calendario del activo
4. metodología declarada       methodology_version y point_in_time_capable = True
```

La función **recibe la asignación ya resuelta**: comprueba, no elige. Elegir es un acto de curación en Knowledge (D-04), y además el validador solo admite una asignación por `(activo, rol, periodo)`.

## 6. Ejemplos — equity

Con la hipótesis de v1 congelada (`MARKET` = S&P 500), la declaración quedaría así — **no está en el repositorio**:

```
entidad     bm:sp500  type=benchmark
            methodology_version, composition_source=PUBLISHED_LEVEL,
            point_in_time_capable=true, calendar=equity, serie_desde=1970-01-02

relación    sec:IBM  BENCHMARKED_BY  bm:sp500   role=MARKET   valid_from=…
relación    sec:NVDA COMPARED_TO     bm:ndx     role=MARKET   ← comparison reference, no benchmark
```

Comprobado en test: con esa forma, `benchmark_elegible("2024-01-25", "equity", …)` devuelve `True`; una asignación con `valid_from = 2020-01-01` devuelve `FUERA_DE_VIGENCIA` para un evento de 2018.

El caso de XLK está probado como `FUERA_DE_SERIE`: un benchmark con `serie_desde = 1998-12-22` no puede medir un evento de 1990. **No es un fallo, es un `valid_from`.**

## 7. Ejemplos — crypto

```
relación    sec:ETH  COMPARED_TO  sec:BTC   role=PEER
```

Produce `PEER_RELATIVE_RETURN` y **nunca** `ABNORMAL_RETURN`. Tres cosas que el validador impide, cada una con su test:

- `sec:BTC BENCHMARKED_BY sec:BTC` → *"no puede ser referencia de sí mismo"*.
- `sec:ETH BENCHMARKED_BY sec:BTC role=PEER` → *"un PEER no puede ser benchmark formal"*.
- Un benchmark con `calendar=equity` aplicado a un activo cripto → `CALENDARIO_INCOMPATIBLE`. Medido en la auditoría: el **28,5%** de las sesiones de BTC y ETH caen en fin de semana y las de IBM **cero**.

**La dirección se conserva.** `ETH → BTC` y `BTC → ETH` son dos relaciones válidas y distintas, y la regla de unicidad —que es por sujeto— no las confunde con un duplicado. Dos tests lo fijan.

## 8. Incompatibilidad encontrada al implementar, y corregida

`engine/causal/caminos.py::indice()` recorre **toda** relación vigente sin mirar el predicado. Sin corregirlo, el día que se declarase el primer benchmark el motor causal seguiría esa arista y produciría caminos inexistentes: **que el S&P 500 sea la referencia de NVIDIA no conecta a NVIDIA con las demás empresas del índice**. Una asignación de benchmark es una relación de **medida**, no un mecanismo económico.

Corregido con `modelo.PREDICADOS_NO_CAUSALES` y un filtro de una línea en `indice()`.

**Toca P5A, que `ESTADO.md` marca como cerrada.** Se ha hecho igualmente porque no hacerlo dejaba un fallo plantado, y la alternativa —descubrirlo cuando el primer benchmark ya estuviera declarado— es peor. La lógica de P5A **no cambia**: solo deja de ver un tipo de arista que hasta hoy no existía. Verificado con tres tests: el índice sobre el conocimiento real sigue teniendo **22 nodos con salida**, declarar un benchmark **no lo altera**, y la entidad benchmark **no aparece** como nodo recorrible.

## 9. Compatibilidad con P4, P6 y P6.1

| Fase | Tocada | Cómo se verificó |
|---|---|---|
| **P2 Knowledge** | vocabulario ampliado | las 48 relaciones y 25 entidades reales siguen validando sin incidencias |
| **P4 Events** | no | `tests/test_events.py` y `test_episodios.py` pasan; el `episode_id` de P6.2d no interactúa con esto |
| **P5A Causal Path** | **sí**, §8 | 3 tests de regresión: 22 nodos antes y después |
| **P5B, P5C, P5D** | no | sin cambios en `engine/causal/valoracion.py`, `mecanismos.py`, `engine/requirements/` |
| **P6 / P6.1** | no | `test_impacto.py` y `test_materialidad.py` pasan sin tocarse |
| **Data Contract** | no | `METRIC_FIELDS`, `ASSET_FIELDS` y `DimAsset` intactos; `qa.py` VERIFIED |

La razón de fondo de que el impacto sea tan pequeño es la de D-21: **la asignación cabía en la estructura que ya existía**. Crear una tabla nueva habría tocado el contrato, `storage.py`, `qa.py` y Power BI.

## 10. Tests

**491 → 521** (+30). `OK`.

| Fichero | Tests | Qué fija |
|---|---:|---|
| `tests/test_benchmark_ontologia.py` *(nuevo)* | 27 | los 10 del encargo, más las 4 condiciones de elegibilidad y la regresión de P5A |
| `tests/test_estudio_resultados.py` | 22 (+3) | `TestSuficiencia` → `TestElegibilidadPorFamilia` |

Los diez del encargo, con dónde se comprueban:

| # | Test | Dónde |
|---|---|---|
| 1 | un índice puede ser `benchmark` sin ser `asset` | `test_un_indice_puede_ser_benchmark_sin_ser_asset` |
| 2 | un asset tiene benchmark mediante Knowledge | `test_un_asset_tiene_benchmark_mediante_knowledge` |
| 3 | una *comparison reference* no se convierte en benchmark | `test_una_comparison_reference_no_se_convierte_en_benchmark` |
| 4 | BTC no puede ser benchmark de BTC | `test_btc_no_puede_ser_benchmark_de_btc` |
| 5 | sin benchmark, `RAW_RETURN` sigue siendo elegible | `test_raw_return_es_elegible_sin_benchmark` |
| 6 | sin benchmark, `ABNORMAL_RETURN` no lo es | `test_abnormal_return_no_es_elegible_sin_benchmark` |
| 7 | `PEER_RELATIVE_RETURN` conserva la dirección | `test_peer_relative_conserva_la_direccion` |
| 8 | calendario incompatible → sin retorno anormal | `test_calendario_incompatible_no_produce_retorno_anormal` |
| 9 | la selección *ex post* no es posible desde el cálculo | `test_no_se_puede_declarar_dos_benchmarks_del_mismo_rol_a_la_vez` · `test_el_calculo_no_puede_escribir_conocimiento` |
| 10 | la suficiencia de `RAW_RETURN` no depende de `ABNORMAL_RETURN` | `test_la_elegibilidad_de_raw_no_depende_de_la_de_abnormal` |

Dos tests que existen para que la prohibición no se olvide: `TestNoSeHaIntroducidoNingunBenchmark` comprueba que en `knowledge/` no hay **ninguna** entidad de tipo benchmark ni ninguna relación de referencia. Fallarán —correctamente— el día que se declare el primero, y ahí habrá que reescribirlos.

## 11. QA

```
QA CORE:    PASS
QA PARQUET: PASS
STATUS:     VERIFIED
```

Sin cambios en `qa.py`. La ontología vive en Knowledge, que tiene su propio validador (`consulta.py --validar`, PASS).

## 12. Qué NO se implementó

- **Ningún benchmark concreto**: ni `^GSPC`, ni `^IXIC`, ni `^NDX`, ni ETF sectoriales, ni CoinDesk 20, ni índice cripto. Cero series descargadas.
- **Ninguna asignación real**: `knowledge/` sigue con 25 entidades y 48 relaciones.
- **`ASSET_CLASS`**: declarado, rechazado por el validador.
- **El cálculo del retorno anormal**: `benchmark_elegible()` dice *si se puede*; no hay código que lo calcule.
- **Campos nuevos en la observación de reacción**: sigue con 17.
- `HistoricalReactionProfile`, `reaction_gap`, shrinkage, condicionamiento por régimen, scoring, pesos, BUY/SELL, Power BI, `Evidence Eligibility` universal.
- **`DimAsset`, `METRIC_FIELDS`, `ASSET_FIELDS`**: intactos.

## 13. Deuda y gaps nuevos

1. **`ASSET_CLASS` sin definición cerrada.** Registrado en `ROLES_NO_ACTIVOS` con su razón.
2. **`point_in_time_capable = False` se puede declarar pero no se usa.** El validador exige que sea booleano; quien lo rechaza para el retorno anormal es `benchmark_elegible()`. Es correcto —Knowledge puede registrar el hecho de que un proveedor restata— pero conviene saber que la regla vive en dos sitios distintos a propósito.
3. **`COMPARED_TO` con rol `SECTOR` y objeto `benchmark` es válido y no tiene todavía ningún caso.** Es la forma prevista para el ETF sectorial cuando se decida.
4. **La unicidad se comprueba solo para `BENCHMARKED_BY` con `polarity=AFFIRMS`.** Un activo puede tener varios `COMPARED_TO` del mismo rol a la vez, y eso es deliberado: varias referencias contextuales no se contradicen, un benchmark formal sí.

## 14. Implicaciones para los consumidores

- **Cron**: sin impacto. No pasa por Knowledge.
- **Power BI**: sin impacto. `FactMetrics`, `DimAsset` y el modelo estrella no cambian.
- **Web App**: sin construir.
- **Quien declare el primer benchmark** tendrá que: crear la entidad con su bloque completo, crear la fuente en `knowledge/sources/`, crear la relación con rol y vigencia, y **reescribir los dos tests de `TestNoSeHaIntroducidoNingunBenchmark`**, que están puestos para saltar en ese momento.
