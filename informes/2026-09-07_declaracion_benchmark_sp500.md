# Declaración del primer benchmark formal: S&P 500

**Fecha**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Base**: `605d08a`
**Alcance**: el benchmark de mercado para las tres acciones. **Nada más** — ni Nasdaq Composite, ni Nasdaq-100, ni ETF sectoriales, ni CoinDesk 20, ni índices cripto, ni `HistoricalReactionProfile`.

**Verificación**:

```
python3 -m unittest discover -s tests            521 → 547 tests · OK
python3 engine/contract/qa.py --require-parquet  STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   PASS (26 entidades · 51 relaciones · 11 fuentes)
python3 engine/technical/fetch_benchmark.py      14.291 sesiones · validación sin incidencias
```

---

## 1. Qué es exactamente la serie que usamos

Verificado en vivo el 2026-09-07 contra la propia API, **antes** de declarar la entidad:

| Propiedad | Valor |
|---|---|
| Ticker | `^GSPC` |
| `instrumentType` **declarado por la fuente** | **`INDEX`** |
| Nombre | S&P 500 |
| Divisa | USD |
| Mercado / zona horaria | SNP · `America/New_York` |
| Granularidad | `1d` |
| Tipo de observación | **nivel de cierre** de la sesión |
| Periodo | **1970-01-02 → 2026-09-04**, 14.291 sesiones |
| Sesiones en fin de semana | **0** |
| Eventos de split o dividendo | **ninguno** |
| `close` vs `adjclose` | **idénticos** en las 2.299 sesiones comparadas |

Las dos últimas filas son las que resuelven la pregunta del ajuste: **un nivel de índice no tiene acciones corporativas que ajustar**, así que elegir `close` no es una elección. Es distinto del caso de las acciones, donde el bloque 4 tuvo que decidir explícitamente entre `close` y `adjclose`.

Que la propia fuente declare `instrumentType: INDEX` es, además, una confirmación externa de la ontología de D-21: no es un `security`.

### No se reconstruye el índice a partir de sus constituyentes

Usamos el **nivel publicado**, y por eso el cambio histórico de composición es irrelevante: el nivel del 2018-11-16 es el que se publicó ese día y lo incorpora todo. El problema de composición solo aparece en benchmarks construidos por nosotros — y `composition_source = CONSTRUCTED` está **prohibido por el validador**.

### No se usa un ETF

Ni SPY ni ningún otro. Un ETF introduciría comisión, *tracking error*, distribuciones y acciones corporativas propias dentro del benchmark metodológico. Hay un test que comprueba que el alias apunta al índice y no a un ETF.

## 2. Fuente, y un límite que se registra en vez de taparse

`src:yahoo-gspc`, tipo `DATA_PROVIDER`, con la URL de la API como localizador reabrible y la metadata verificada dentro del propio localizador.

**No se cita la documentación metodológica de S&P Dow Jones Indices**: `spglobal.com` responde **403 Forbidden** desde este entorno, tanto la página del índice como el PDF de metodología. Es exactamente la situación de **D-07**, que resolvió prefiriendo un localizador reabrible antes que una URL tras protección anti-bot.

Consecuencia honesta, anotada en la propia fuente: **`point_in_time_capable: true` se afirma sobre nuestra comprobación** —cero acciones corporativas, `close == adjclose`— **y no sobre una declaración del proveedor**. Para poder detectar una reformulación futura de la serie queda registrado el hash de hoy:

```
sha256(data/benchmarks/SP500.csv) = 26f902b2ec9645f2…   14.291 sesiones · 872 KB
nivel 1970-01-02 = 93,00      nivel 2026-09-04 = 7.718,60
```

Y `methodology_version = "yahoo-^GSPC-close-1d/v1"` describe **cómo consume este sistema la serie**, no la versión de la metodología de S&P — que no podemos citar. Nombrarlo de otro modo sería fingir una precisión que no tenemos.

## 3. Dónde vive la serie, y por qué no en `data/history/`

Nueva ubicación: **`data/benchmarks/SP500.csv`**, versionada, 14.291 filas, columnas `benchmark_id, data_as_of, value, source, retrieved_at`.

**No va a `data/history/`** porque ese es el árbol de activos, particionado por `asset_type`. Meterla allí produciría los tres efectos que la auditoría de D-21 midió: `storage.asset_type_of("SP500")` la devolvería como un activo, `cadencias.esperadas()` no sabría qué métricas esperar de ella, y `Asset Count` de Power BI subiría de 11 a 12 en silencio. Es la "tabla propia" que recomendaba el §13 de la auditoría.

`fetch_benchmark.py` sigue el patrón de los demás fetchers: caché incremental en `_data/` (gitignored) y escritura idempotente en el store versionado.

**Fallo de idempotencia encontrado y corregido durante la implementación**: la primera versión comparaba el valor descargado con precisión completa contra el valor almacenado con cuatro decimales, así que marcaba cada fila como cambiada en cada ejecución y reescribía las 14.291 `retrieved_at`. Es el mismo error que el contrato de métricas evita al no reescribir por solo `retrieved_at`. Corregido comparando el valor ya redondeado; verificado con dos ejecuciones consecutivas que dan **el mismo hash**.

## 4. Declaración en Knowledge

Sin ninguna tabla nueva, usando los mecanismos que ya existían:

```
entidad    bm:sp500   type=benchmark   asset_id=None
           alias yahoo:^GSPC (desde 1970-01-02)
           benchmark: methodology_version, composition_source=PUBLISHED_LEVEL,
                      point_in_time_capable=true, calendar=equity,
                      serie_desde=1970-01-02

relación   rel:0049   sec:IBM.NYSE     BENCHMARKED_BY  bm:sp500  role=MARKET  desde 1970-01-02
relación   rel:0050   sec:NVDA.NASDAQ  BENCHMARKED_BY  bm:sp500  role=MARKET  desde 1999-01-22
relación   rel:0051   sec:XOM.NYSE     BENCHMARKED_BY  bm:sp500  role=MARKET  desde 1970-01-02
```

**La vigencia la fija el activo, no el benchmark**: el S&P 500 cubre desde 1970, pero NVDA no existía hasta su OPV. `valid_from = 1999-01-22` es la primera sesión de NVDA en el Data Contract, no una fecha elegida. Es **D-09** aplicada: la vigencia no se extrapola.

**La justificación de `^GSPC` frente a `^IXIC` y `^NDX` está escrita en la propia entidad**, y es *ex ante*: los tres cubren el periodo, así que la elección no puede justificarse por cobertura — se justifica por lo que cada uno representa. Que quede con fecha de commit **antes** de calcular ningún retorno anormal es lo que la hace válida frente al *selection bias*.

## 5. Elegibilidad comprobada

Las cuatro condiciones de D-21, verificadas para las tres asignaciones:

| Condición | IBM · NVDA · XOM |
|---|---|
| Semánticamente compatible | `BENCHMARKED_BY`, rol `MARKET` (no `PEER`) |
| Temporalmente válida | vigencia de la asignación y ventana de serie del benchmark |
| Observación disponible | calendario `equity` == calendario del activo |
| Metodología declarada | `methodology_version` presente, `point_in_time_capable` = true |

Y las que **fallan**, también comprobadas: el mismo benchmark aplicado a un activo cripto da `CALENDARIO_INCOMPATIBLE`; ningún activo cripto tiene asignación (`asignacion_de("BTC")` → `None`).

## 6. Event study de validación — la cadena completa

```
event → available_at → first_tradable_at → surprise → raw_return
      → benchmark_return → abnormal_return
```

**52 de 52 eventos** tienen retorno anormal. Ninguna sustitución silenciosa: el retorno del benchmark se mide **entre las mismas dos sesiones** que el del activo (la previa y la primera negociable), y si al benchmark le faltara una de ellas la observación quedaría en `SIN_OBSERVACION_BENCHMARK` en vez de usar la sesión más cercana.

**Sin look-ahead**, y hay un test que lo fija: las dos sesiones del benchmark son `sesion_previa < first_tradable_at`, y `first_tradable_at >= available_at`. Ninguna es posterior al momento en que la información pudo negociarse.

Método: **`DIFERENCIA_SIMPLE`** (r_activo − r_benchmark), el único admisible en v1. El modelo de mercado (α + βr) exigiría **estimar** un coeficiente, y **D-10** lo prohíbe hasta que exista una capa de Model/Calibration.

### Raw frente a abnormal

| | |
|---|---|
| Eventos con ajuste | **52 / 52** |
| Mediana de \|bruto − anormal\| | **0,57 pp** |
| Máximo | **2,81 pp** |
| Eventos donde el mercado explica más de 2 pp | **7** |
| **Eventos donde bruto y anormal tienen signo distinto** | **3** |

Los tres cambios de signo, que son el argumento entero de tener benchmark:

| Activo | Publicado | Bruto | Benchmark | Anormal |
|---|---|---:|---:|---:|
| IBM | 1999-04-21 | **+1,25%** | +2,29% | **−1,04%** |
| XOM | 2012-01-31 | **+0,27%** | +0,89% | **−0,62%** |
| XOM | 2020-07-31 | **+0,50%** | +0,77% | **−0,27%** |

Y los casos donde el mercado explica la mayor parte:

| Activo | Publicado | Bruto | Benchmark | Anormal |
|---|---|---:|---:|---:|
| XOM | 2020-05-01 | −7,17% | −2,81% | **−4,36%** |
| NVDA | 2021-02-24 | −8,22% | −2,45% | **−5,77%** |
| NVDA | 2018-11-16 | −18,76% | +0,22% | **−18,98%** |
| NVDA | 2024-11-21 | +0,53% | +0,53% | **−0,00%** |

**XOM 2020-05-01 confirma la estimación de la auditoría.** Allí, usando las otras dos acciones como aproximación grosera, calculé que *"~40% del movimiento es común al mercado"*. Con el benchmark real: 2,81 de los 7,17 puntos, **39,2%**. La aproximación era correcta y ahora está medida.

**NVDA 2024-11-21 es el caso que ninguna lectura del bruto habría dado**: +0,53% bruto y **−0,00%** anormal. El evento no aportó nada sobre lo que hizo el mercado ese día.

**NVDA 2018-11-16 es el contrario**: el mercado subió +0,22% y el anormal (**−18,98%**) es *peor* que el bruto.

### Lo que estos números NO son

**No son un perfil de reacción.** No se ha calculado ninguna mediana de reacción, percentil, probabilidad ni `reaction_gap`, y hay un test que comprueba que la observación no contiene ninguno de esos campos. Son la verificación de que la cadena produce números correctos y reproducibles, nada más.

Con el ajuste calculado, `ABNORMAL_RETURN` pasa a ser **elegible** (n=52 ≥ mínimo declarado de 40) — que es la condición para poder construir el perfil, **no el perfil**.

```
RAW_RETURN             utilizable=True   n=52  minimo=30  SUFICIENTE
ABNORMAL_RETURN        utilizable=True   n=52  minimo=40  SUFICIENTE
PEER_RELATIVE_RETURN   utilizable=False  SIN_ASIGNACION_DECLARADA
VOLUME_CHANGE          utilizable=False  MEDIDA_NO_CALCULADA
```

## 7. Cada retorno ajustado lleva la identidad de su benchmark

Cada observación con ajuste guarda `benchmark_id`, `benchmark_methodology_version` y `metodo_ajuste`. Un `market_adjusted_return` sin saber contra qué es irreproducible — es el problema de `beta` que la auditoría encontró en `engine/equity/score.py:150`, donde Alpha Vantage da una magnitud ajustada por mercado cuyo mercado, ventana y frecuencia son desconocidos. Ese `beta` sigue **sin llegar al Data Contract**.

## 8. Tests

**521 → 547** (+26). `OK`.

| Fichero | Qué |
|---|---|
| `tests/test_benchmark_sp500.py` *(nuevo, 25)* | los 10 del criterio de aceptación, la serie, y el no-look-ahead |
| `tests/test_benchmark_ontologia.py` | `TestNoSeHaIntroducidoNingunBenchmark` → `TestElPrimerBenchmarkDeclarado` |
| `tests/test_estudio_resultados.py` | `test_bruto_y_anormal_no_se_confunden` reescrito (+1 test) |

Los diez del encargo:

| # | Test |
|---|---|
| 1 | `test_bm_sp500_es_un_benchmark_valido` |
| 2 | `test_las_tres_acciones_se_asignan_mediante_knowledge` |
| 3 | `test_benchmarked_by_habilita_abnormal_return` |
| 4 | `test_el_calculo_comprueba_pero_no_elige` |
| 5 | `test_la_asignacion_tiene_vigencia` · `test_la_vigencia_la_fija_el_activo_no_el_benchmark` |
| 6 | `test_no_hay_solapamiento_de_asignaciones` |
| 7 | `test_sin_benchmark_el_raw_sigue_calculandose` · `test_el_raw_return_no_cambia_con_ni_sin_benchmark` |
| 8 | `test_el_abnormal_return_usa_el_benchmark_declarado` |
| 9 | `test_calendario_incompatible_falla` |
| 10 | `test_el_benchmark_declarado_no_es_un_nodo_causal` · `test_las_tres_asignaciones_no_anaden_aristas` |

### Dos tests que caducaron

Ambos afirmaban que **no** había benchmark, y estaban puestos para fallar exactamente hoy:

- `TestNoSeHaIntroducidoNingunBenchmark` → reescrito a `TestElPrimerBenchmarkDeclarado`: la propiedad que sigue siendo cierta es que **solo** existe lo autorizado — un benchmark, tres asignaciones, cero `COMPARED_TO`, cero cripto.
- `test_bruto_y_anormal_no_se_confunden` afirmaba `market_adjusted_return_pct is None`. Reescrito a lo que sigue siendo cierto y ahora importa más: si hay ajuste, viaja con la identidad del benchmark; si no lo hay, con su razón. La mitad que caducó se conservó en un test nuevo, sobre un caso donde sí aplica (`con_benchmark=False`).

## 9. QA

```
QA CORE:    PASS
QA PARQUET: PASS
STATUS:     VERIFIED
```

`qa.py` **no se ha tocado**. `data/benchmarks/` queda fuera de su alcance a propósito en esta iteración; tiene su propia validación (`fetch_benchmark.validar_serie()`, sin incidencias sobre las 14.291 sesiones) y un test que la ejecuta sobre la serie real. **Deuda registrada**: conectarla a `qa.py`.

## 10. Qué no se implementó

- **Ningún otro benchmark**: ni `^IXIC`, ni `^NDX`, ni ETF sectoriales, ni CoinDesk 20, ni índice cripto.
- **Ninguna *comparison reference***: cero relaciones `COMPARED_TO`. Nasdaq-100 como referencia contextual queda para la siguiente vertical.
- **Ningún benchmark cripto**, ningún índice construido, y BTC no se usa como benchmark de nada.
- **`HistoricalReactionProfile`**, `reaction_gap`, shrinkage, condicionamiento por régimen, `n_effective`.
- **Scoring, pesos, BUY/SELL**: el resultado del event study no se convierte en señal.
- **`MARKET_MODEL` (α + β)**: solo `DIFERENCIA_SIMPLE`, por D-10.
- **`DimAsset`, `METRIC_FIELDS`, `data/history/`, Power BI**: intactos.
- **`beta` de Alpha Vantage**: sigue sin llegar al contrato.

## 11. Deuda y gaps nuevos

1. **La metodología de S&P DJI no es citable desde este entorno** (403). `point_in_time_capable` se afirma sobre comprobación propia. Mitigación: hash registrado en el §2 para detectar una reformulación futura.
2. **`data/benchmarks/` no está en `qa.py`.** Tiene validación propia y un test, pero no entra en el `STATUS: VERIFIED` global.
3. **El cron no actualiza el benchmark.** `fetch_benchmark.py` se ejecuta a mano. Si el event study se usa con eventos recientes, la serie puede quedarse atrás — y entonces la observación saldrá `SIN_OBSERVACION_BENCHMARK`, que es el fallo correcto: visible, no silencioso.
4. **`serie_hasta` es `null`**, es decir "vigente hasta nuevo aviso". Correcto hoy; habrá que fijarlo si algún día se deja de actualizar.
5. **Solo `MARKET`.** `SECTOR` sigue sin fuente defendible y `ASSET_CLASS` sigue declarado y rechazado.

## 12. Impacto sobre fases anteriores

| Fase | Tocada | Verificación |
|---|---|---|
| P2 Knowledge | +1 entidad, +3 relaciones, +1 fuente | `consulta.py --validar` PASS · 26/51/11 |
| P5A Causal Path | **no** | 2 tests: `bm:sp500` no es nodo y las asignaciones no añaden aristas (D-23 funcionando con un benchmark real) |
| P4, P5B-D, P6, P6.1 | no | suites propias pasan |
| Data Contract | **no** | `qa.py` VERIFIED · `data/history/` sin cambios |

## 13. Criterio de parada

> El S&P 500 está declarado como benchmark formal de mercado para IBM, NVDA y XOM mediante Knowledge, y el event study calcula retornos anormales sin que el benchmark entre en el grafo causal.

**Cumplido**: 52/52 eventos con retorno anormal, `bm:sp500` fuera del grafo causal verificado con dos tests, y `data/history/` sin tocar.

**Alto.** No se avanza al `HistoricalReactionProfile`.
