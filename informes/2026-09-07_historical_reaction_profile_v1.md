# HistoricalReactionProfile v1 — descriptivo, no predictivo

**Fecha**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Base**: `da35869`
**Alcance de v1**: una sola familia homogénea — renta variable estadounidense, eventos corporativos, benchmark S&P 500, datos de cierre. Macro y cripto quedan fuera por decisión explícita.

**Verificación**:

```
python3 -m unittest discover -s tests            547 → 581 tests · OK
python3 engine/contract/qa.py --require-parquet  STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   PASS (26 · 51 · 11)
git status --short data/ knowledge/              vacío
python3 engine/events/perfil_reaccion.py [as_of] la rejilla completa
```

**Ningún dato nuevo**: no se ha descargado ni escrito nada en `data/` ni en `knowledge/`.

---

## La propiedad que ordena el módulo

> Un perfil **nunca desaparece** por falta de datos: devuelve el motivo por el que no puede construirse.

Es el mismo principio que ya sostienen P6.1 (materialidad `UNKNOWN` frente a `NOT_APPLICABLE`), `temporal.py` (`DESCONOCIDO` no es permisivo) y D-21 (`UNAVAILABLE` no se sustituye). Aquí queda cristalizado: de los **20 perfiles** de la rejilla, **10 son `VALID` y 10 no**, y los diez que no lo son dicen exactamente por qué.

## 1. Población

Partida: **52 observaciones** del Event Study MVP (IBM 16 · NVDA 18 · XOM 18), sobre las fixtures congeladas de Alpha Vantage `EARNINGS`.

Pipeline de selección, aplicado **en este orden** y con la **primera** razón por la que cada observación sale:

```
52 observaciones
   ↓  PIT: available_at <= as_of
   ↓  PIT: la ventana del horizonte termina <= as_of
   ↓  CLASE: event_class en la taxonomía
   ↓  TIMING: existe primera sesión negociable
   ↓  SOLAPE: la ventana no alcanza al evento siguiente del mismo activo
   ↓  BENCHMARK: elegible (solo ABNORMAL_RETURN)
   ↓  OBSERVACIÓN: la medida tiene valor en esas dos sesiones
cohorte
```

El orden importa: un evento excluido por PIT no se vuelve a evaluar por benchmark. Se registra la razón que de verdad lo saca.

**Un test comprueba que `incluidas + excluidas == población de partida` en las 20 celdas**: nada se descarta en silencio.

## 2. Taxonomía

**Una sola clase**: `earnings_release`.

Es la única que hoy se identifica de forma robusta: tiene fecha de publicación, franja horaria, expectativa y sorpresa, todo del mismo payload. Los eventos de P4 sobre noticias son `ASSERTS_SENTIMENT` —la postura declarada por un medio, no un hecho económico— y el propio P4 lo dice en sus `unknowns`. **No se ha ampliado la taxonomía para aumentar `n`.**

Dimensiones: `event_class × measure_type × horizon`. **No** se han añadido sector, capitalización, régimen, deciles de sorpresa ni buckets de timing: con 52 observaciones y 3 activos, cualquiera de ellas produciría cohortes de `n` ridículo.

## 3. Filtros de elegibilidad

| Filtro | Regla | Origen |
|---|---|---|
| PIT del evento | `available_at ≤ as_of` | P6.2a |
| **PIT de la ventana** | la sesión final del horizonte `≤ as_of` | **nuevo, §10** |
| Clase | `event_class` en la taxonomía declarada | v1 |
| Timing | `first_tradable_at` existe (`reportTime` conocido) | P6.2c |
| Solape | la ventana no alcanza al evento siguiente del mismo activo | P6.2c, ahora **por horizonte** |
| Benchmark | las cuatro condiciones de D-21 | D-21 |
| Observación | la medida existe en las dos sesiones, sin sustituir por la más cercana | v1 |

## 4. Exclusiones

Tasa de exclusión por celda, reportada **aunque el perfil sea válido**:

| Medida | Horizonte | Incluidas | Excluidas | Tasa | Motivo dominante |
|---|---|---:|---:|---:|---|
| RAW_RETURN | 0_1d · 2_5d | 52 | 0 | 0,0% | — |
| RAW_RETURN | 2_20d | 51 | 1 | 1,9% | serie sin sesiones suficientes |
| RAW_RETURN | 2_60d | 46 | 6 | 11,5% | **3 solape** + 3 serie insuficiente |
| ABNORMAL_RETURN | igual que RAW | 52→46 | 0→6 | 0→11,5% | idénticas |
| PEER_RELATIVE_RETURN | todos | 0 | 52 | **100%** | sin comparable declarado |
| VOLUME_CHANGE | 0_1d | 52 | 0 | 0,0% | — |
| VOLATILITY_CHANGE | 0_1d | 50 | 2 | 3,8% | sin volatilidad en esas sesiones |

Las 2 exclusiones de volatilidad son reales y explicables: la volatilidad histórica de 30 días no existe en las primeras sesiones de cada tramo contiguo de la serie.

## 5. Conteos de independencia

Los cinco se conservan por separado **aunque coincidan** — que coincidan es información, no ruido:

| | ABNORMAL 0_1d | ABNORMAL 2_60d |
|---|---:|---:|
| `n_observations` | 52 | 46 |
| `n_events` | 52 | 46 |
| `n_independent_events` | 52 | 46 |
| `n_episodes` | **`NOT_APPLICABLE`** | **`NOT_APPLICABLE`** |
| `n_independent_episodes` | **`NOT_APPLICABLE`** | **`NOT_APPLICABLE`** |
| `n_activos` | 3 | 3 |

**Por qué los episodios son `NOT_APPLICABLE` y no `UNKNOWN`**: el episodio es una construcción de la capa de noticias —varios documentos sobre el mismo hecho—, y una publicación de resultados no procede de documentos agrupables. Ningún dato adicional le daría un `episode_id`. El proyecto ya distingue las dos cosas desde P6: *"`NOT_APPLICABLE` no mejora con más datos; `UNKNOWN` sí"*.

`n_events == n_independent_events` **por construcción**: el filtro de solape ya sacó los que se pisan con otro evento del mismo activo dentro del horizonte. Se reportan los dos porque en una cohorte futura con episodios declarados dejarán de coincidir.

### Una limitación de la cohorte que hay que decir

Las 52 observaciones son un **subconjunto deliberadamente disperso** de los ~356 eventos reales. Medida la separación entre eventos consecutivos del fixture para IBM: 2.196, 380, 1.324, 1.006, 65, 251, 253, 254, 252, 250, 254, 184, 66, 58, 62 sesiones.

Con trimestres **consecutivos** la separación real es de ~58-66 sesiones, así que **el horizonte 2_60d está justo en el límite** de lo que permite un evento trimestral: a veces solapa y a veces no. La tasa de solape del 11,5% medida aquí **no es representativa** de lo que daría la serie completa, donde sería mucho mayor. El perfil a 2_60d es frágil por construcción del calendario corporativo, no por nuestros datos.

## 6. Horizontes

```
0_1d    s0 → s1        reacción inmediata (s0 = sesión previa, s1 = primera NEGOCIABLE)
2_5d    s1 → s1+4      deriva posterior
2_20d   s1 → s1+19
2_60d   s1 → s1+59
```

Todos en **sesiones reales de la serie del activo**, nunca en días naturales — el proyecto ya rechazó esa aproximación al construir `trading_calendar.py`.

Los tres de deriva arrancan en `s1` y no en `s0` a propósito: arrancar en `s0` incluiría la reacción inmediata y no serían deriva, serían la misma medida con más ruido.

**La ventana no se acorta nunca para que quepa**: un horizonte de 60 sesiones medido sobre 12 no es ese horizonte. Si la serie no llega, la observación sale con `SERIE_SIN_SESIONES_SUFICIENTES_PARA_EL_HORIZONTE`.

**Sin intradía**, como se pidió.

## 7. Estadísticas

Nunca solo la media. La mediana va primero: con muestras pequeñas y colas gruesas la media sola engaña.

| Medida | Horiz. | n | mediana | media | p10 | p25 | p75 | p90 | prob+ | IQR |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| RAW | 0_1d | 52 | −0,11 | 0,64 | −7,62 | −2,78 | 4,52 | 8,71 | 0,50 | 7,30 |
| RAW | 2_5d | 52 | −0,05 | 0,51 | −4,03 | −2,39 | 2,41 | 5,65 | 0,50 | 4,80 |
| RAW | 2_20d | 51 | 0,32 | 0,41 | −9,85 | −4,54 | 4,53 | 11,13 | 0,51 | 9,07 |
| RAW | 2_60d | 46 | **2,25** | 4,33 | −8,94 | −4,61 | 9,63 | 20,22 | **0,65** | 14,24 |
| **ABN** | 0_1d | 52 | −0,58 | 0,51 | −6,78 | −2,40 | 4,31 | 8,22 | 0,42 | 6,71 |
| **ABN** | 2_5d | 52 | −0,49 | 0,24 | −5,20 | −2,56 | 2,25 | 5,31 | 0,48 | 4,81 |
| **ABN** | 2_20d | 51 | −0,67 | −0,15 | −9,53 | −6,13 | 2,91 | 9,42 | 0,45 | 9,04 |
| **ABN** | 2_60d | 46 | **−0,88** | 2,27 | −11,77 | −6,31 | 8,89 | 18,05 | **0,46** | 15,20 |
| VOLUME | 0_1d | 52 | 51,52 | 65,26 | −4,48 | 22,59 | 93,60 | 127,01 | 0,86 | 71,01 |
| VOLATILITY | 0_1d | 50 | 5,47 | 16,92 | −0,66 | 0,24 | 18,52 | 54,23 | 0,80 | 18,28 |

### Lo que estos números dicen, y lo que NO dicen

**La comparación más informativa es RAW frente a ABNORMAL a 60 sesiones**: mediana **+2,25% bruta** frente a **−0,88% anormal**, y `prob_positive` **0,65 frente a 0,46**. Descontar el mercado cambia por completo la lectura de la derida larga — es exactamente lo que un benchmark existe para hacer, medido sobre datos propios.

**Lo que NO se afirma**: que `earnings_release` "prediga" rentabilidad, en ningún signo. Estos son **10 perfiles descriptivos sobre 52 observaciones de 3 activos**. La mediana anormal es prácticamente cero en los cuatro horizontes y la dispersión es entre 7 y 15 veces mayor que ella (IQR 6,71 frente a mediana −0,58 a 0_1d). Un IQR quince veces la mediana describe una distribución centrada en nada con colas anchas, no un patrón.

Volumen y volatilidad a 0_1d sí muestran el comportamiento esperado —el volumen mediano se multiplica por 1,5 el día del evento (`prob+` 0,86) y la volatilidad sube en el 80% de los casos—, y eso es una **verificación de que la ventana está bien puesta**, no un hallazgo.

## 8. Estados de perfil

De los 20: **10 `VALID`, 10 `INSUFFICIENT_COMPARABILITY`**.

| Estado | Celdas | Por qué |
|---|---:|---|
| `VALID` | 10 | RAW×4, ABN×4, VOLUME 0_1d, VOLATILITY 0_1d |
| `INSUFFICIENT_COMPARABILITY` | 4 | `PEER_RELATIVE_RETURN`: no hay ninguna *comparison reference* declarada |
| `INSUFFICIENT_COMPARABILITY` | 6 | medidas de **nivel** en horizontes de deriva, §11 |
| `INSUFFICIENT_SAMPLE` | — | aparece con `as_of` histórico (§10) |
| `NO_BENCHMARK` | — | aparece sin benchmark declarado (probado) |
| `PIT_INVALID` | — | aparece con `as_of` anterior a todos los eventos (probado) |
| `UNSTABLE` | — | **no evaluable** con esta muestra, §11 |

**`INSUFFICIENT_SAMPLE` no significa "no hay nada"**, significa "no me fío todavía": el perfil sigue reportando su distribución completa. Es la diferencia entre callar y decir con cuánta evidencia se habla.

## 9. Benchmark

Todo perfil de `ABNORMAL_RETURN` conserva:

```
benchmark_id                    bm:sp500
benchmark_methodology_version   yahoo-^GSPC-close-1d/v1
metodo_ajuste                   DIFERENCIA_SIMPLE
```

**Y se niega a construirse sin ellos.** Si la cohorte mezclara dos benchmarks o dos versiones de metodología, el estado es `INSUFFICIENT_COMPARABILITY` con la razón *"sería irreproducible"* — hay un test que lo fuerza inyectando un `benchmark_id` distinto en una observación.

Es la misma exigencia que la auditoría de D-21 planteó al encontrar `beta` de Alpha Vantage: una magnitud ajustada por mercado cuyo mercado se desconoce es irreproducible.

## 10. Point-in-time

Todo perfil lleva `as_of_date` y `methodology_version`, y solo usa eventos con `available_at ≤ as_of`.

**Reproducibilidad histórica, medida**:

| `as_of` | n | Estado |
|---|---:|---|
| 2026-09-07 | 52 | `VALID` |
| 2020-01-01 | 18 | `INSUFFICIENT_SAMPLE` |
| 2010-01-01 | 5 | `INSUFFICIENT_SAMPLE` |
| 1990-01-01 | 0 | `PIT_INVALID` |

### Un look-ahead encontrado en mi propia implementación

La primera versión filtraba por `available_at ≤ as_of` **y nada más**. Eso deja pasar un caso: un evento **conocible** en `as_of` cuya ventana de 60 sesiones **termina después** de `as_of`. Un perfil fechado en 2020-01-25 no puede saber cómo acabó una ventana que aún no había terminado.

Corregido con un filtro adicional —`ventana[1] ≤ as_of`, motivo `PIT: la ventana del horizonte termina despues de as_of`— y un test que lo fuerza con `as_of = 2020-01-25` en el horizonte 2_60d.

Es la misma familia de error que P6.2a corrigió en el contrato, aquí en la dimensión del horizonte: la validez temporal no es solo del dato de entrada, también de la ventana de medida.

## 11. Limitaciones

**1. Las medidas de nivel no tienen ventana base.** Para un retorno, acumular desde `s1` mide la deriva. Para volumen o volatilidad, `s1` **es la sesión del pico**, así que "variación de `s1` a `s1+20`" no mide volumen anormal: mide la vuelta a la normalidad después del pico. Medido antes de aplicar la regla: mediana **−43,5%** a 2_5d con `prob_positive` **0,08** — un número que se leería al revés.

Una medida de nivel necesita una **ventana base anterior al evento**, y esa es una decisión metodológica no tomada. Hasta que se tome, esos seis perfiles salen `INSUFFICIENT_COMPARABILITY` con su motivo. `0_1d` sí es limpio para ellas: compara la sesión del evento con la anterior.

**2. `UNSTABLE` no es evaluable con esta muestra.** La comprobación es *split-half* por fecha: si las dos mitades temporales no coinciden en el signo de la mediana, la cohorte no se describe bien con un número. Solo se evalúa con al menos **2× el mínimo declarado** — partir una muestra que apenas llega al mínimo daría dos mitades sin significado. Con `ABNORMAL_RETURN` haría falta n≥80 y hay 52. El perfil lo dice explícitamente en vez de afirmar estabilidad.

**3. Tres activos.** `n_activos = 3` en todos los perfiles. La cohorte no es una muestra del mercado: es IBM, NVDA y XOM.

**4. El subconjunto no es representativo del solape** (§5).

**5. `n_effective` no existe.** Con 3 activos, 52 observaciones **no** son 52 unidades independientes de información: hay correlación transversal entre acciones del mismo mercado en la misma fecha. Corregirlo exige un `n_effective`, que el encargo excluye de esta iteración. **Los `n` reportados son de eventos, no de información independiente**, y hay que leerlos así.

## 12. Resultados nulos e insuficientes

Se reportan igual que los válidos, con sus conteos:

| Celda | n | Estado | Razón |
|---|---:|---|---|
| `PEER_RELATIVE_RETURN` × 4 | 0 | `INSUFFICIENT_COMPARABILITY` | no hay ninguna *comparison reference* declarada para estos activos |
| `VOLUME_CHANGE` 2_5d/2_20d/2_60d | 0 | `INSUFFICIENT_COMPARABILITY` | medida de nivel sin ventana base |
| `VOLATILITY_CHANGE` 2_5d/2_20d/2_60d | 0 | `INSUFFICIENT_COMPARABILITY` | ídem |
| Todas con `as_of=1990-01-01` | 0 | `PIT_INVALID` | ningún evento era conocible |
| `ABNORMAL_*` sin benchmark | 0 | `NO_BENCHMARK` | probado con `con_benchmark=False` |

**Que la mitad de la rejilla no sea `VALID` es el resultado correcto**, no un fallo: el criterio de parada era que el sistema pudiera demostrar con qué evidencia habla, no que produjera muchos perfiles.

## 13. Tests

**547 → 581** (+34). `OK`.

`tests/test_perfil_reaccion.py` (nuevo, 34 tests) cubre:

- la rejilla completa: 20 celdas, ninguna desaparece, todas con estado del vocabulario
- `incluidas + excluidas == población` en las 20 celdas; toda exclusión con motivo
- PIT: `as_of` histórico reduce la población; ningún evento incluido era desconocido; **la ventana que termina después de `as_of` se excluye**; `PIT_INVALID`
- estados: `NO_BENCHMARK` sin benchmark, `RAW_RETURN` **sigue siendo `VALID`** sin él, medidas de nivel, `INSUFFICIENT_SAMPLE` reportando distribución
- benchmark: identidad exigida; mezclar dos lo hace irreproducible
- estadísticos sobre un vector conocido; nunca solo la media; vector vacío no inventa
- **validación manual contra el MVP**: mediana, media, mín y máx del perfil coinciden con el cálculo directo sobre `raw_return_1s_pct` y `market_adjusted_return_pct`, y tres eventos concretos coinciden uno a uno
- ningún perfil contiene campos de señal, score, peso ni `reaction_gap`

## 14. QA

```
QA CORE:    PASS
QA PARQUET: PASS
STATUS:     VERIFIED
```

`qa.py` no se ha tocado. El perfil es una **vista derivada**: no escribe nada en `data/` ni en `knowledge/`, y se recalcula desde las observaciones. Es coherente con el invariante del proyecto *"lo derivado no se versiona"*.

## 15. Qué NO se implementó

- **shrinkage**, `n_effective`, `reaction_gap`, *confidence* predictiva, score, pesos, BUY/SELL, optimización.
- **Régimen** como dimensión, y ninguna otra dimensión adicional (sector, capitalización, deciles de sorpresa, buckets de timing).
- **Macro y cripto**: v1 valida una sola familia homogénea. Cripto tendrá `RAW / PEER_RELATIVE / VOLUME / VOLATILITY` sin benchmark formal; macro tendrá otra estructura (una sorpresa → varios activos).
- **Nuevos benchmarks o índices**, ninguna *comparison reference*, ningún dato descargado.
- **Narrative, LLM, GDELT**.
- **Intradía**.
- **Ventana base para medidas de nivel** — es la decisión concreta que desbloquearía 6 de los 10 perfiles no válidos.

---

## Criterio de parada

> "Este perfil está construido con N observaciones, M eventos independientes y K episodios, usando únicamente información disponible *as-of*, esta metodología, este benchmark y este horizonte."

Ejemplo real, reproducible con `python3 engine/events/perfil_reaccion.py 2026-09-07`:

```
event_class    earnings_release
measure_type   ABNORMAL_RETURN
horizon        0_1d
as_of_date     2026-09-07
methodology    historical_reaction_profile/v1
benchmark      bm:sp500 · yahoo-^GSPC-close-1d/v1 · DIFERENCIA_SIMPLE
n_observations 52   n_events 52   n_independent_events 52
n_episodes     NOT_APPLICABLE     n_activos 3
excluidas      0 (tasa 0,0%)
mediana −0,58  media 0,51  p25 −2,40  p75 4,31  prob+ 0,42  IQR 6,71
estabilidad    no evaluable (harían falta 80 observaciones)
status         VALID
```

**Cumplido.** No se avanza a régimen ni a `reaction_gap`.
