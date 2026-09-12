# D-27, independencia y solapamiento — iteración metodológica previa a ampliar la cohorte

**Fecha**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Base**: `07f867e` · **Commit**: `c44120a`
**Alcance**: metodología sobre los **mismos 52 eventos** de IBM/NVDA/XOM. No se ha ampliado la cohorte, no se ha declarado ningún benchmark nuevo, no se ha añadido ningún activo.

**Verificación**:

```
python3 -m unittest discover -s tests            587 → 601 tests · OK
python3 engine/contract/qa.py --require-parquet  QA CORE: PASS · QA PARQUET: PASS · STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   PASS (26 entidades · 51 relaciones · 11 fuentes)
git status --short data/ knowledge/              vacío
python3 engine/events/diagnostico_cohorte.py     el diagnóstico completo
python3 engine/events/perfil_reaccion.py         la rejilla de 20 perfiles
```

**Ningún dato nuevo**: no se ha descargado ni escrito nada en `data/` ni en `knowledge/`. Toda la evidencia de este informe sale del contrato ya versionado.

---

## Lo que esta iteración perseguía

El `HistoricalReactionProfile v1` produjo 10 perfiles `VALID`. La pregunta que abre este informe no es si esos números se pueden **calcular** —está demostrado que sí— sino si se pueden **leer**:

> `COMPUTABLE` ≠ `INTERPRETABLE` ≠ `PREDICTIVO`

v1 cerró lo primero. Este informe mide lo segundo. Lo tercero —walk-forward, fuera de muestra— **no se toca aquí**, y el código lo dice explícitamente en vez de dejarlo implícito.

---

## 1. Definición de `estimation_window`

**`estimation_window` = las 20 sesiones bursátiles `[-20, -1]` inmediatamente anteriores a `first_tradable_at` (s1), sin incluir s1.**

Tres precisiones que la hacen verificable:

- **En sesiones, no en días naturales.** Es la unidad en la que ya se miden los horizontes. Contar en días daría un número que no se puede contrastar con la ventana de reacción.
- **Excluye s1.** s1 *es* la sesión del evento: incluirla mete el pico dentro de su propia base. Ese fue exactamente el defecto que D-27 registró.
- **Respeta `_split_contiguous()`.** Una ventana que cruzase un hueco real de calendario (deslistado, cierre de mercado) mezclaría dos regímenes de liquidez distintos.

La distinción frente a `reaction_window` queda ahora en el propio objeto de perfil, como dos campos separados:

| campo | qué es | cuándo es `null` |
|---|---|---|
| `estimation_window` | base **anterior** al evento contra la que se normaliza | medidas que no necesitan base (`RETURN`, `RELATIVE_TO_BENCHMARK`, `RELATIVE_TO_PEER`) |
| `reaction_window` | el horizonte que se está midiendo | nunca |

**El intervalo `[-20,-1]` NO se ha adoptado como constante global.** `_pct_in_window()` en `engine/crypto/score.py` sigue con su ventana de 365 días y **no se ha tocado** — su `10` es el mínimo razonable para un percentil en ventana móvil, no un parámetro de event study. `LARGO_VENTANA_ESTIMACION = 20` vive en `engine/events/estudio_resultados.py` y solo lo usa el event study.

### Medición de disponibilidad — la ventana existe de verdad

```
python3 engine/events/diagnostico_cohorte.py

=== VENTANA DE ESTIMACION ===
  largo                          20
  con_ventana_completa           52
  sin_ventana_completa           0
  contaminadas_por_otro_evento   0
  con_huecos_de_volumen          0
```

**52 de 52.** Ningún evento se queda sin base, ninguna ventana de estimación contiene otro evento de resultados del mismo activo, y ninguna tiene huecos de volumen. Es el mejor resultado posible y conviene decir por qué era esperable: 20 sesiones son un tercio del intervalo entre trimestres (§6), así que la ventana previa cae de lleno en el periodo tranquilo.

---

## 2. Métricas afectadas por la distinción

| medida | familia semántica | ¿necesita `estimation_window`? | estado en v1.1 |
|---|---|---|---|
| `RAW_RETURN` | `RETURN` | no | `VALID` ×4 |
| `ABNORMAL_RETURN` | `RELATIVE_TO_BENCHMARK` | no (la base es el benchmark) | `VALID` ×4 |
| `PEER_RELATIVE_RETURN` | `RELATIVE_TO_PEER` | no | `INSUFFICIENT_COMPARABILITY` ×4 |
| `VOLUME_RELATIVE_TO_PRE_EVENT` | `RELATIVE_TO_PRE_EVENT` | **sí** | `VALID` ×4 |
| `VOLATILITY_RELATIVE_TO_PRE_EVENT` | `RELATIVE_TO_PRE_EVENT` | **sí** | `INSUFFICIENT_METHODOLOGY` ×4 |

La regla queda comprobada por un test: **solo las medidas de la familia `RELATIVE_TO_PRE_EVENT` declaran `estimation_window`; el resto lo tiene a `null`.** Un retorno no necesita base pre-evento porque ya es una diferencia; un nivel sí.

Consecuencia directa: el **neutro** de una medida depende de su familia, no de una convención global.

```python
NEUTRO_POR_FAMILIA = {"RETURN": 0.0, "RELATIVE_TO_BENCHMARK": 0.0,
                      "RELATIVE_TO_PEER": 0.0, "RELATIVE_TO_PRE_EVENT": 1.0}
```

En v1 `prob_positive` valía **1,00** para las medidas de cociente, porque comparaba un ratio contra 0. Un cociente de 0,4 es una **caída** de volumen y se estaba contando como positiva. Corregido y con test propio.

---

## 3. Propuesta de volumen — la base es la **mediana**, y se midió (revisión de D-27)

El usuario pidió explícitamente no elegir entre media, mediana y z-score de forma arbitraria. Se midieron las tres sobre los 52 eventos:

```
horiz   n    ratio/MEDIANA        ratio/MEDIA          z-score            media>mediana
0_1d    52   med 2.04  max 7.95   med 1.98  max 7.36   med 4.05  max 16.92   47/52
2_5d    51   med 1.26  max 2.93   med 1.15  max 2.64   med 0.59  max  4.94   46/51
2_20d   51   med 1.06  max 2.50   med 1.00  max 2.13   med 0.00  max  3.01   46/51
2_60d   49   med 1.02  max 2.28   med 0.94  max 1.94   med -0.19 max  2.53   44/49
```

**Tres hallazgos, en orden de importancia:**

1. **La media está contaminada al alza en el 90% de las ventanas** (47/52, 46/51, 46/51, 44/49). El volumen diario tiene una distribución con cola derecha pesada: un único día de pánico dentro de las 20 sesiones previas arrastra la media y **no** la mediana. En los 4 horizontes, 44-47 de los eventos dan un ratio **menor** usando la media — es decir, la media esconde sistemáticamente el pico del evento.
2. **El z-score es inutilizable como medida publicable.** Máximo **16,92** en `0_1d`. Un z de 17 no es una anomalía estadística interpretable: es la prueba de que la desviación típica de una ventana de 20 sesiones de volumen no es una escala estable. Además, un z-score depende de la forma de la distribución de la base, que aquí es asimétrica por construcción.
3. **La elección de base cambia el signo de la conclusión en 2_60d**: mediana → 1,02 (volumen ligeramente por encima); media → 0,94 (volumen *por debajo*). Es el mejor argumento de que esto no podía elegirse por costumbre.

**Decisión**: `VOLUME_RELATIVE_TO_PRE_EVENT` = `mediana(ventana de reacción) / mediana(estimation_window [-20,-1])`. Mediana en el numerador y en el denominador, por el mismo motivo en los dos sitios.

**Resultado, ya interpretable:**

| horizonte | mediana del cociente | `prob > 1` | IQR |
|---|---|---|---|
| `0_1d` | **2,04** | 0,981 | 1,78 |
| `2_5d` | **1,26** | 0,824 | 0,59 |
| `2_20d` | **1,06** | 0,627 | 0,28 |
| `2_60d` | **1,01** | 0,531 | 0,24 |

Se lee de forma natural y monótona: el día del evento se negocia **el doble** de lo normal, y la anomalía se disuelve hacia 1 en dos meses. Compárese con v1, donde la misma cohorte daba mediana **−43,5%** a 2_5d y `prob_positive` **0,08** — un número correcto con una lectura natural equivocada.

**Se descartó**: publicar las tres bases y dejar la elección al consumidor. Multiplica por tres la rejilla y traslada al lector una decisión metodológica que este informe puede tomar con evidencia.

---

## 4. Propuesta de volatilidad — `INSUFFICIENT_METHODOLOGY` (revisión de D-27)

Se aplicó el **mismo razonamiento** que al volumen, y dio un resultado distinto. Esto importa: si la respuesta hubiera sido automáticamente la misma, el razonamiento no estaría haciendo nada.

**Disponibilidad** (no es el problema): 47 de 52 eventos tienen `volatilidad_hist_30d_anualizada_pct` completa en su ventana de estimación.

**El problema es de definición.** La única volatilidad que existe en el contrato es una **media móvil de 30 sesiones**. Por tanto:

- el valor en la sesión del evento **ya contiene las 20 sesiones de la ventana de estimación**;
- el cociente `volatilidad(reacción) / volatilidad(estimación)` compara **dos ventanas solapadas**, con 20 de sus 30 sesiones en común;
- el cociente estaría comprimido hacia 1 por construcción, y esa compresión se leería como "el evento no cambia la volatilidad".

Sería el mismo error de D-27 en otra forma: un número computable cuya lectura natural es falsa.

**Decisión**: `status = INSUFFICIENT_METHODOLOGY` en los cuatro horizontes, con el motivo escrito en el código (`MEDIDAS_SIN_METODOLOGIA`), no solo en este informe.

**Lo que lo desbloquearía**: volatilidad **realizada** calculada sobre la ventana de reacción —desviación típica de los retornos diarios de esas sesiones concretas— que es una métrica nueva del contrato, no una transformación de la existente. Queda registrada como deuda, no como imposibilidad.

---

## 5. Dependencia — D-31

```
=== DEPENDENCIA ===
  n_observations             52
  n_events                   52
  n_assets                   3
  n_independent_assets       3
  n_episodes                 NOT_APPLICABLE
  events_per_asset           {'IBM': 16, 'NVDA': 18, 'XOM': 18}
  events_per_asset_median    18
  events_per_episode         NOT_APPLICABLE
  independence_status        LOW
  cluster_recomendado        asset
```

**El cuello de botella no es `n_events`, es `n_assets`.** Los mínimos declarados de D-22 (30, 40, 50, 60) se cumplen con holgura sobre `n=52`, y aun así la cohorte tiene **tres** unidades transversales. Los 16 trimestres de IBM comparten empresa, sector, mercado y régimen macro; no son 16 observaciones independientes de "cómo reacciona una acción a sus resultados".

Esto no invalida los perfiles: los hace **descriptivos de estos tres activos**, que es exactamente lo que v1 dice ser.

**`independence_status`** — tres valores con umbrales declarados sobre el número de **activos**, no de eventos:

| estado | umbral | esta cohorte |
|---|---|---|
| `HIGH` | ≥ 30 activos | |
| `MEDIUM` | ≥ 10 activos | |
| `LOW` | < 10 activos | ✅ **3** |

**`cluster_recomendado = "asset"`**, con la razón registrada en el código: los eventos de un mismo activo comparten empresa, sector, mercado y régimen, *y además se suceden en el tiempo*. El episodio **no aplica** a un evento programado (D-28), así que clusterizar por episodio no separaría nada en esta cohorte — daría exactamente los mismos grupos que no clusterizar.

**No se ha inventado ninguna fórmula de `n_effective`.** Un test lo comprueba: el módulo no define ningún símbolo que contenga `effective`. Ver §10.

---

## 6. Eventos por activo e intervalo entre eventos

`events_per_asset`: IBM **16**, NVDA **18**, XOM **18** — mediana **18**.

Intervalos entre eventos sucesivos del mismo activo, **medidos en sesiones bursátiles**:

```
IBM  [2196, 380, 1324, 1006, 65, 251, 253, 254, 252, 250, 254, 184, 66, 58, 62]
NVDA [945, 314, 884, 195, 311, 259, 248, 189, 65, 64, 62, 124, 190, 64, 185, 65, 126]
XOM  [3217, 376, 754, 502, 129, 58, 256, 63, 379, 187, 316, 59, 190, 189, 61, 63, 62]
```

Los intervalos grandes (250, 380, 3217…) son **huecos de muestreo de la cohorte**, no trimestres largos: los 52 eventos no son una serie trimestral contigua, sino la selección que las fixtures capturaron. El diagnóstico filtra por `< 150` sesiones para quedarse con lo que de verdad son trimestres consecutivos:

- **18 intervalos** por debajo de 150 sesiones, mediana **63,5**;
- de ellos, **15 caen entre 58 y 66 sesiones** — trimestres consecutivos reales;
- los otros 3 (124, 126, 129) son saltos de **dos** trimestres, coherentes con el doble de 63.

**Un trimestre son ~63 sesiones, no ~91 días naturales.** Medirlo en días habría dado un número incomparable con la ventana, que se cuenta en sesiones. Hay un test explícito sobre esto.

---

## 7. Solapamiento — D-30

```
  horiz    ventana  solapan    tasa  interv.med  cobertura
  0_1d           1        0     0.0        63.5      0.016
  2_5d           5        0     0.0        63.5      0.079
  2_20d         20        0     0.0        63.5      0.315
  2_60d         60        3   0.061        63.5      0.945
```

- `overlap_event_count`: **0 · 0 · 0 · 3**
- `overlap_rate`: **0,0 · 0,0 · 0,0 · 0,061**

**El hallazgo que no se buscaba está en la última columna.** `cobertura_del_intervalo` = ventana / intervalo mediano, y es una medida **distinta** del solapamiento técnico:

> A `2_60d`, solo **3 de 49** ventanas alcanzan literalmente al evento siguiente — pero la ventana cubre el **94,5%** del trimestre.

Es decir: aunque el solapamiento formal sea del 6%, a 60 sesiones "la deriva posterior a los resultados del Q3" y "lo que le pasó a la acción hasta los resultados del Q4" han dejado de ser cosas distinguibles. Un solapamiento del 6% podría leerse como "prácticamente limpio"; la cobertura del 94,5% dice que no lo es. Por eso se publican las dos.

A `2_20d` la cobertura es **0,315** — un tercio del trimestre. Es el horizonte largo más defendible de los disponibles.

---

## 8. `full_sample` frente a `non_overlapping_sample`

Se publican **las dos**, en el mismo objeto de perfil (`statistics` y `statistics_non_overlapping`). **No se ha eliminado ningún evento.**

```
=== FULL vs NON-OVERLAPPING ===
  RAW_RETURN         2_20d  no comparable: no hay ningun evento solapado que quitar
  RAW_RETURN         2_60d  n 49->46 mediana +2.27 -> +2.25 (delta -0.020) · prob 0.65 -> 0.65
  ABNORMAL_RETURN    2_20d  no comparable: no hay ningun evento solapado que quitar
  ABNORMAL_RETURN    2_60d  n 49->46 mediana -1.02 -> -0.88 (delta +0.140) · prob 0.45 -> 0.46
```

**El test todavía no es informativo, y hay que decirlo así.** Las diferencias son pequeñas (−0,02 y +0,14 puntos porcentuales), pero eso **no** demuestra que el solapamiento sea inocuo: solo **3 eventos** se quitan de 49. Con 3 observaciones fuera de una muestra de 49, una mediana que apenas se mueve es el resultado esperado tanto si el solapamiento contamina como si no.

Afirmar "el solapamiento no afecta" con esta evidencia sería el mismo error que el usuario ya corrigió con las dos observaciones de NVDA. Lo que se puede afirmar es: **con esta cohorte, la comparación no discrimina.** Volverá a ser informativa cuando la cohorte tenga series trimestrales contiguas y la tasa de solapamiento a 2_60d suba de 6% a lo que corresponda.

En `2_20d` la comparación devuelve **`comparable: False`** con motivo `"no hay ningun evento solapado que quitar"`, en vez de duplicar una estadística idéntica y aparentar una validación que no ocurrió.

---

## 9. Efecto sobre `2_20d` y `2_60d`

Ambos horizontes se **conservan**, con lecturas distintas:

| | `2_20d` | `2_60d` |
|---|---|---|
| solapamiento técnico | 0 / 51 | 3 / 49 (6,1%) |
| cobertura del trimestre | 0,315 | **0,945** |
| `n` (PIT completo) | 51 | 49 |
| IQR de `ABNORMAL_RETURN` | 9,04 | **16,52** |
| lectura | deriva posterior al evento | **deriva ≈ trimestre entero** |

`2_60d` no se elimina: es computable, tiene muestra suficiente y su `overlap_rate` está publicado. Pero **no puede leerse como "reacción al evento"**. A 60 sesiones se está midiendo casi todo lo que le pasó a la acción entre unos resultados y los siguientes, incluyendo información que nada tiene que ver con el evento. La dispersión lo confirma: el IQR casi se duplica de 2_20d a 2_60d mientras la mediana apenas se mueve — señal de ruido añadido, no de señal añadida.

**Recomendación registrada**: `2_20d` es el horizonte largo interpretable de esta rejilla. `2_60d` se publica como contexto de deriva, nunca como medida de reacción. No se ha convertido en una regla de código porque afecta a la lectura, no al cálculo.

---

## 10. Metodología de `n_effective` — pendiente, y por qué (D-31)

**No se ha definido.** El usuario pidió medir antes de formular, y la medición dice que aún falta información para elegir la fórmula:

1. **La unidad de cluster está decidida (`asset`) pero no probada.** Con 3 activos no se puede comprobar empíricamente que el clustering por activo capture la dependencia — cualquier estimación de correlación intra-cluster sobre 3 grupos es inestable.
2. **La dependencia temporal dentro de un activo no está medida.** Los trimestres de IBM se suceden; falta saber si la reacción a unos resultados está correlacionada con la del trimestre anterior. Con 16 observaciones por activo, esa autocorrelación no se estima con precisión.
3. **La dependencia transversal en fecha común no existe en esta cohorte.** Las fechas de resultados de IBM, NVDA y XOM no coinciden. En una cohorte de 356 eventos sí habrá solapamientos de calendario entre activos, y eso es una fuente de dependencia **distinta** de las dos anteriores.

Mientras tanto se publica `independence_status` de tres valores, `n_independent_assets`, `events_per_asset` y `cluster_recomendado` — los conteos con los que después se podrá elegir una fórmula, en vez de una fórmula elegida de cualquier manera.

**Se descartó explícitamente**: `n_effective = n_assets` (descarta toda la información temporal), `n_effective = n / (1 + (m−1)ρ)` con un ρ supuesto (el supuesto sería el resultado), y el bootstrap por activo (correcto como *método*, pero no valida el número de clusters que lo hace fiable — 3 son pocos).

---

## 11. `DESCRIPTIVE_STATUS` — D-29

**El perfil `VALID` de v1 no se ha eliminado.** Se ha desdoblado el estado en dos campos independientes:

```python
"descriptive_status": "VALID",          # ¿se puede describir lo observado?
"predictive_status": "NOT_EVALUATED",   # ¿tiene validez fuera de muestra?
```

`descriptive_status` responde a: *¿hay muestra suficiente, PIT válido, benchmark compatible y metodología definida para **describir** lo que ocurrió?* Toma los 7 valores ya existentes (`VALID`, `INSUFFICIENT_SAMPLE`, `NO_BENCHMARK`, `INSUFFICIENT_COMPARABILITY`, `PIT_INVALID`, `UNSTABLE`, `INSUFFICIENT_METHODOLOGY`).

El campo `status` se mantiene como alias de `descriptive_status` para no romper a los consumidores de v1.

**Rejilla vigente** (`as_of = 2026-09-07`, política de solape `FLAG`):

| medida | `0_1d` | `2_5d` | `2_20d` | `2_60d` |
|---|---|---|---|---|
| `RAW_RETURN` | VALID −0,11 | VALID −0,05 | VALID +0,32 | VALID +2,27 |
| `ABNORMAL_RETURN` | VALID −0,58 | VALID −0,49 | VALID −0,67 | VALID −1,02 |
| `PEER_RELATIVE_RETURN` | INSUFF_COMPARABILITY | ″ | ″ | ″ |
| `VOLUME_RELATIVE_TO_PRE_EVENT` | VALID 2,04 | VALID 1,26 | VALID 1,06 | VALID 1,01 |
| `VOLATILITY_RELATIVE_TO_PRE_EVENT` | INSUFF_METHODOLOGY | ″ | ″ | ″ |

**12 `VALID` de 20** (v1: 10 de 20). Las dos ganadas son las de volumen en los horizontes de deriva, que ahora tienen una base defendible. Los 8 restantes siguen diciendo por qué no pueden construirse.

---

## 12. `PREDICTIVE_STATUS` — D-29

```python
PREDICTIVE_STATUS = {
    "NOT_EVALUATED": "no se ha hecho ninguna comprobacion fuera de muestra",
    "VALID":         "...",
    "INVALID":       "...",
}
```

**Para toda la rejilla de v1.1: `PREDICTIVE_STATUS = NOT_EVALUATED`.** Sin excepciones, incluidos los 12 perfiles `VALID`.

`NOT_EVALUATED` **no** significa "probablemente sirve". Significa que **no se ha hecho ninguna comprobación fuera de muestra**: ni walk-forward, ni partición temporal, ni prueba en activos distintos de los tres que produjeron el perfil. Es la misma distinción que el proyecto ya usa entre `UNKNOWN` y `NOT_APPLICABLE`: aquí *sí* mejoraría con más trabajo, y ese trabajo no se ha hecho.

**El perfil no se usa para scoring.** Un test lo comprueba de forma estructural, recorriendo los ficheros: ningún módulo de `engine/scoring/` ni `engine/reasoning/` menciona `perfil_reaccion`. Un segundo test recorre las 20 celdas de la rejilla y exige `NOT_EVALUATED` en todas. La distinción entre los dos estados existe precisamente para que un perfil `VALID` no se cuele en una decisión por parecerse a una señal.

---

## 13. Qué queda bloqueado

| bloqueado | por qué | qué lo desbloquea |
|---|---|---|
| `PEER_RELATIVE_RETURN` | no hay grupo de comparación declarado; seleccionar peers ahora sería hacerlo *después* de ver los resultados | declarar una `ComparisonReference` de sector **antes** de mirar, con criterio escrito (D-21) |
| `VOLATILITY_RELATIVE_TO_PRE_EVENT` | la volatilidad del contrato es media móvil de 30 sesiones y solapa la ventana de estimación | volatilidad **realizada** sobre la ventana de reacción — métrica nueva |
| `n_effective` | 3 activos no permiten estimar la correlación intra-cluster | cohorte con ≥10 activos, idealmente ≥30 |
| `PREDICTIVE_STATUS ≠ NOT_EVALUATED` | no hay validación fuera de muestra de ningún tipo | walk-forward con partición temporal — P8 (Backtesting) |
| lectura de `2_60d` como reacción | cubre el 94,5% del intervalo entre eventos | nada; es una propiedad del calendario trimestral, no una carencia de datos |
| cripto en esta rejilla | no hay benchmark de mercado PIT gratuito defendible (medido en D-21) | un proveedor de índice cripto con nivel publicado |
| `independence_status ≥ MEDIUM` | 3 activos | ampliar la cohorte a ≥10 activos |

Los dos últimos casos de la tabla son de naturaleza distinta al resto y conviene no confundirlos: la lectura de `2_60d` **no mejora con más datos** (es estructural), mientras que todos los demás sí.

---

## 14. Tests

**587 → 601** (`Ran 601 tests · OK`). Antes de esta iteración, v1 dejó la suite en 587.

**Fichero nuevo**: `tests/test_diagnostico_cohorte.py` (**12 tests**)

- `test_el_cuello_de_botella_es_el_numero_de_activos_no_el_de_eventos` — 52 observaciones, 3 activos, `LOW`.
- `test_un_evento_programado_no_tiene_episodio` — `NOT_APPLICABLE`, ni `0` ni `UNKNOWN` (D-28).
- `test_se_clusteriza_por_activo_y_la_razon_esta_escrita`
- `test_la_ventana_de_estimacion_esta_disponible_y_limpia` — 52/52, 0 contaminadas, 0 huecos.
- `test_el_solapamiento_solo_aparece_en_el_horizonte_largo` — 0/0/0/3.
- `test_la_contaminacion_estructural_no_es_el_solapamiento` — 2_20d no solapa con nadie y cubre un tercio del trimestre.
- `test_el_intervalo_se_mide_en_sesiones_no_en_dias` — entre 55 y 70, no ~91.
- `test_comparar_muestras_no_elimina_nada_de_forma_permanente` — D-30.
- `test_sin_eventos_solapados_la_comparacion_dice_que_no_es_comparable`
- `test_el_modulo_no_publica_ninguna_formula_de_n_effective` — estructural.
- `test_el_estado_de_independencia_tiene_tres_valores_declarados`
- `test_el_informe_cubre_los_cuatro_horizontes`

**Tests añadidos a `tests/test_perfil_reaccion.py`** (10):

- `test_descriptivo_y_predictivo_son_estados_distintos`
- `test_toda_medida_declara_su_semantica`
- `test_solo_las_medidas_relativas_al_pre_evento_declaran_ventana`
- `test_el_neutro_de_un_cociente_es_uno_no_cero`
- `test_el_volumen_se_mide_contra_la_ventana_de_estimacion`
- `test_la_volatilidad_disponible_no_tiene_metodologia`
- `test_el_solape_se_marca_y_no_se_elimina`
- `test_la_politica_EXCLUDE_sigue_disponible`
- `test_ningun_motor_de_decision_importa_el_perfil` — barrera estructural de §12
- `test_toda_la_rejilla_declara_no_evaluado_prediccionalmente`

**Tests caducados y reescritos** (§3 del protocolo de informes — un test que se apoya en que algo no existe caduca cuando ese algo se documenta):

| test de v1 | por qué caducó | test vigente |
|---|---|---|
| `test_el_solape_excluye_las_observaciones_contaminadas` | D-30 cambió la política por defecto de `EXCLUDE` a `FLAG` | `test_el_solape_se_marca_y_no_se_elimina` |
| `test_una_medida_de_nivel_solo_se_publica_en_0_1d` | la base pre-evento hace publicable el volumen en los 4 horizontes | `test_el_volumen_se_mide_contra_la_ventana_de_estimacion` |

**Regresión sobre lo que no debía cambiar**: `tests/test_estudio_resultados.py::test_el_umbral_10_de_pct_in_window_no_se_ha_vuelto_global` (ya existente desde D-22) comprueba que `engine/crypto/score.py::_pct_in_window()` conserva su mínimo de 10 puntos — el `[-20,-1]` de este informe **no** se ha propagado a ninguna otra parte del sistema. Los 23 tests de `test_estudio_resultados.py` siguen pasando sin reescritura.

---

## 15. QA

```
python3 engine/contract/qa.py --require-parquet
  ...
  QA CORE:    PASS
  QA PARQUET: PASS
  STATUS:     VERIFIED
  Particiones abiertas y verificadas: 287 · Incidencias: 0

python3 engine/knowledge/consulta.py --validar
  Knowledge: 26 entidades · 51 relaciones · 3 conceptos · 11 fuentes
  RESULTADO: PASS

git status --short data/ knowledge/
  (vacío)
```

**Sin cambios en datos.** Esta iteración es exclusivamente metodológica: toca `engine/events/` y `tests/`, y nada más. Los bloques informativos de `qa.py` (cobertura y frescura) siguen igual que en v1 — 19 `AVAILABLE` · 1 `PARTIAL`, con `DOT.fundamental` sin `tvl_percentile_365d` por la incidencia de DefiLlama ya conocida.

---

## Qué cambió — ficheros

| fichero | estado | qué |
|---|---|---|
| `engine/events/diagnostico_cohorte.py` | **nuevo** | dependencia, ventana de estimación, solapamiento, contaminación estructural, full vs non-overlapping |
| `engine/events/perfil_reaccion.py` | modificado | `descriptive_status`/`predictive_status`, `estimation_window`/`reaction_window`, `NEUTRO_POR_FAMILIA`, `VOLUME_RELATIVE_TO_PRE_EVENT`, `MEDIDAS_SIN_METODOLOGIA`, política `FLAG` |
| `engine/events/estudio_resultados.py` | modificado | `ventana_estimacion()`, `marcar_solapamientos()`, `LARGO_VENTANA_ESTIMACION`, volumen contra base pre-evento |
| `tests/test_diagnostico_cohorte.py` | **nuevo** | 12 tests |
| `tests/test_perfil_reaccion.py` | modificado | +10 tests, 2 reescritos |

---

## Supuestos propios invalidados en esta iteración

1. **"El solapamiento técnico mide la contaminación."** No. A `2_60d` el solapamiento es del 6% y la cobertura del intervalo del 94,5%. Hicieron falta las dos medidas; con una sola se habría concluido que `2_60d` está limpio.
2. **"Si la muestra completa y la no solapada dan casi lo mismo, el solapamiento no afecta."** No con 3 eventos de diferencia sobre 49. La comparación **no discrimina** todavía, que no es lo mismo que no encontrar efecto.
3. **"La media es una base razonable para el volumen."** Medido: contaminada al alza en el 90% de las ventanas, y en `2_60d` cambia el signo de la conclusión.
4. **"Volumen y volatilidad son el mismo problema y admiten la misma solución."** El razonamiento fue el mismo y el resultado distinto: el volumen tiene serie diaria cruda, la volatilidad solo una media móvil que solapa su propia base.

---

## Deuda abierta que deja esta iteración

- **`n_effective` sin fórmula** — registrado en la cabecera de `diagnostico_cohorte.py`, con test estructural que impide introducirla sin quitar el test.
- **Volatilidad realizada** no existe en el contrato — `MEDIDAS_SIN_METODOLOGIA` en `perfil_reaccion.py`.
- **`diagnostico_cohorte.py` no entra en `qa.py`** — igual que la serie de benchmark (D-24). Tiene tests propios sobre datos reales, pero no condiciona el `STATUS: VERIFIED` global.
- **La cohorte de 52 eventos no es una serie trimestral contigua** — los intervalos de 250-3217 sesiones son huecos de muestreo. Al ampliar a ~356 eventos, la tasa de solapamiento a `2_60d` subirá y §8 volverá a ser informativa.

---

## Impacto sobre fases anteriores

- **P6.2c (event study)**: `estudio_resultados.py` gana la ventana de estimación y el marcado de solape. Ningún cálculo previo cambia de valor — verificado porque los 23 tests de `test_estudio_resultados.py` siguen pasando sin reescritura.
- **P6.2d, P6.1, P6, P5A, Data Contract**: **no tocados**. `git status --short data/ knowledge/` vacío.
- **`engine/crypto/score.py`**: **no tocado**, con test de regresión explícito.
- **Power BI / Web App / cron**: sin impacto. No hay ficheros nuevos en `data/`; la rejilla de perfiles sigue sin publicarse en el contrato.

---

## Decisiones registradas

| decisión | qué fija |
|---|---|
| **D-27 · revisión** | la base de una medida de nivel es la ventana `[-20,-1]`, con **mediana** medida frente a media y z-score; la volatilidad disponible no admite metodología |
| **D-29** | `descriptive_status` ≠ `predictive_status`; toda la rejilla es `NOT_EVALUATED`; barrera estructural contra su uso en scoring |
| **D-30** | el solapamiento se **marca** (`FLAG`), no elimina eventos; contaminación estructural ≠ solapamiento técnico |
| **D-31** | `n_effective` se mide antes de formularse: conteos e `independence_status`, ninguna fórmula |

Todas en `docs/DECISIONES.md`, con la cadena completa *decisión original → evidencia nueva → revisión → decisión vigente* intacta.

