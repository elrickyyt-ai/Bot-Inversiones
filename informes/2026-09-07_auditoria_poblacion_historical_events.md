# Auditoría de población del histórico de eventos — ¿hay diversidad transversal suficiente?

**Fecha**: 2026-09-07/08 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Base**: `66b1979` · **Commit**: `f1b0d38`
**Alcance**: medir si existe una población con la que arreglar `n_assets = 3`. **No es un backfill**: no se ha cargado ni un solo evento en `data/`.

**Verificación**:

```
python3 -m unittest discover -s tests            601 → 627 tests · OK
python3 engine/contract/qa.py --require-parquet  QA CORE: PASS · QA PARQUET: PASS · STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   PASS (26 · 51 · 11)
git status --short data/ knowledge/              vacío
python3 engine/events/universo.py                universo, cobertura y condición de avance
```

**Ningún dato nuevo en el contrato.** `data/` y `knowledge/` no se han tocado, verificado con `git status`.

---

## El problema que abre esta auditoría

D-31 dejó el diagnóstico en una línea:

```
n_events = 52   pero   n_assets = 3   →   independence_status = LOW
```

Y con él, la trampa: ampliar a ~356 eventos de **los mismos tres activos** daría `n_events = 356` y `n_assets = 3`. Más datos, la misma dependencia. **El cuello de botella es transversal, no temporal**, así que esta iteración amplía la población antes que la historia.

---

## 1. Universo

**`universe:v1:djia-2019`**, congelado a **`as_of_date = 2019-01-01`**, declarado en `engine/events/universo_v1.json` — un registro curado a mano, como `episodios.json` y `knowledge/` (D-04). Ningún motor lo escribe.

| | |
|---|---|
| activos incluidos | **31** |
| activos excluidos | **6**, cada uno con su motivo |
| sectores | **9** |
| mercado | EE.UU. (NYSE/NASDAQ), un solo calendario |

Reparto sectorial: Tecnología 6 · Financiero 5 · Industrial 4 · Salud 4 · Consumo básico 4 · Consumo discrecional 3 · Energía 2 · Comunicación 2 · Materiales 1.

Los calendarios de resultados están genuinamente escalonados: MSFT cierra ejercicio en junio, AAPL y DIS en septiembre, HD en enero, NKE en mayo, WBA en agosto. No es un universo con 31 activos publicando la misma semana.

**Limitaciones declaradas en el propio fichero, no en una nota al pie:**

1. **Solo gran capitalización.** El usuario pidió incluir *mid cap* y **Universe_v1 no lo tiene**. No dispongo de una composición histórica verificable de un índice mid cap congelada a 2019-01-01 desde una fuente que este proyecto acepte; construirla de memoria sería inventarla y elegir yo las compañías sería una selección. Queda como condición explícita de Universe_v2.
2. **Un solo mercado**, coherente con el único benchmark formal declarado (`bm:sp500`, D-25).
3. La ponderación por precio del DJIA **no interviene**: se usa como *lista de compañías*, no como índice.

## 2. Criterios de selección

> **Los 30 componentes del DJIA tal y como estaba compuesto el 2019-01-01, más los activos de la cohorte de HRP v1 que no estuvieran en ese índice** (solo NVDA: IBM y XOM ya estaban).

**Por qué un índice y no una lista propia.** La pertenencia al índice en una fecha pasada es un hecho público, verificable y **anterior** a cualquier resultado que este proyecto vaya a medir. Una lista elegida por mí sería una selección, y una selección hecha *después* de haber visto reaccionar a IBM/NVDA/XOM sería exactamente el sesgo que esta auditoría existe para evitar.

**Por qué congelado en el pasado.** Tomar la composición de *hoy* excluiría justo a las compañías que peor acabaron — la forma más común del sesgo de superviviencia. Congelar en 2019 obliga a incluir **DWDP** (DowDuPont, escindida en 2019) y **UTX** (United Technologies, fusionada con Raytheon en 2020), que ya no existen. Esa incomodidad es el punto.

**Exclusiones, cada una con su motivo**: GE (salió del DJIA en junio de 2018, *antes* de la congelación — el caso que más tienta a incluir a posteriori, y por eso se deja fuera explícitamente); RTX, DOW y DD (productos de operaciones *posteriores* a la congelación); las 6 cripto de CARTERA_A (`asset_type` distinto y sin benchmark formal, D-21/D-25); TSM (emisor extranjero, presenta 20-F y no 10-Q).

**La regla es ejecutable, no una descripción.** Un test la reproduce: reconstruye la muestra declarada aplicando la regla escrita (recorrido alfabético con paso 3 + los tickers con acción corporativa + la cohorte de v1) y comprueba que coincide exactamente con la lista del fichero.

**La muestra de medición se declaró antes de la primera llamada**, por el mismo motivo.

## 3. Cobertura de Alpha Vantage

```
python3 engine/events/universo.py

=== COBERTURA DE LA FUENTE (muestra declarada) ===
  medidos               6 de 31
  con datos             4
  vacios                2  ['DWDP', 'UTX']
  trimestres totales    488
  sin reportTime        0
  sin estimatedEPS      8
  pre / post market     294 / 194
  series contiguas      4  ['AAPL', 'CAT', 'VZ', 'MSFT']
```

| símbolo | trimestres | desde | hasta | sin `reportTime` | sin `estimatedEPS` | contigua |
|---|---|---|---|---|---|---|
| AAPL | **122** | 1996-04-17 | 2026-07-30 | 0 | 8 | ✅ |
| CAT | **122** | 1996-04-16 | 2026-08-04 | 0 | 0 | ✅ |
| VZ | **122** | 1996-04-18 | 2026-07-24 | 0 | 0 | ✅ |
| MSFT | **122** | 1996-04-18 | 2026-07-29 | 0 | 0 | ✅ |
| DWDP | **0** | — | — | — | — | `TICKER_AUSENTE_DEL_PROVEEDOR` |
| UTX | **0** | — | — | — | — | `TICKER_AUSENTE_DEL_PROVEEDOR` |

**El hallazgo principal de esta auditoría, y no se buscaba:**

> **La fuente solo conoce supervivientes.** `EARNINGS` devuelve `{}` para DWDP y para UTX. `SYMBOL_SEARCH` con "DowDuPont" y con "United Technologies" devuelve **conjunto vacío**: los tickers no están en el directorio de símbolos de Alpha Vantage, no es que falten sus resultados.

La consecuencia es estructural, no un detalle de cobertura: **un universo congelado en el pasado no se puede reconstruir con esta fuente**. Los 2 activos irrecuperables de 31 (**6,5%**) lo son *precisamente porque* tuvieron una acción corporativa — que es la definición del sesgo de superviviencia. Cualquier cohorte construida pidiendo tickers a este proveedor estará sesgada hacia las compañías que sobrevivieron, y el sesgo **no es detectable desde dentro de los datos devueltos**: DWDP no aparece como hueco, aparece como si nunca hubiera existido.

Se registra como dato, no como fila que falta: DWDP y UTX **están** en el registro de cobertura con `quarters_available = 0` y estado propio. Un test lo comprueba.

**Lo que la medición corrigió de mis propias expectativas**: `return_full_data: false` **no reduce la respuesta** — devuelve el histórico completo igualmente. No hay forma de pedir una respuesta compacta.

**Cobertura de la muestra: 6 de 15 declarados.** Los otros 9 y los 16 restantes del universo quedan **`NOT_MEASURED`**, nunca estimados. El motivo **no fue la cuota** (25/día, con margen ese día) sino el coste de transcripción — ver §11.

**Medido en sesión anterior** (2026-09-04, citado, no re-verificado aquí): IBM 123 trimestres desde 1996-03-31 · NVDA 111 desde 1999-04-30 · XOM 122 desde 1996-03-31.

> **Discrepancia registrada, no maquillada**: los **123** de IBM no cuadran con los **122** que daría una serie trimestral contigua 1996Q1–2026Q2, que es lo que dieron los otros cinco activos con ese mismo rango. O IBM tiene un trimestre extra o su serie no es contigua. Queda como comprobación pendiente, no como dato bueno.

## 4. Calidad de timestamps

**`reportTime` está presente en las 488 filas medidas. Cero ausencias.** Es la condición que hace derivable `first_tradable_at` y, con él, todo el event study (D-18).

Pero el reparto revela algo que **invalida un supuesto cómodo**:

| símbolo | pre-market | post-market | patrón |
|---|---|---|---|
| CAT | **122** | 0 | uniforme |
| VZ | **121** | 1 | uniforme con una excepción (2001-04-24) |
| AAPL | 25 | **97** | dos épocas: pre hasta ~2001, post después |
| MSFT | 26 | **96** | **mixto**: bloque pre 1996–2001 **y 5 excepciones pre posteriores** (2009-01-22, 2009-10-23, 2021-07-27, 2022-07-26, 2023-07-25) |

> **`reportTime` no puede asumirse constante por activo.** MSFT publica post-market como norma y pre-market en cinco trimestres repartidos por la serie moderna. Cachear "MSFT = post-market" y aplicarlo a toda su historia desplazaría `first_tradable_at` un día en esos cinco eventos, metiendo la sesión del anuncio dentro de la ventana previa — la misma familia de error que D-27 corrigió para el volumen.

Hay un test que fija esta propiedad sobre MSFT precisamente para que no se reintroduzca el atajo.

**`estimatedEPS`**: ausente en **8** de 488 filas (1,6%), **todas de AAPL y todas anteriores a 2004**. Consecuencia acotada: en esos 8 trimestres la **sorpresa** no es computable; la **reacción** sí. Son dos cosas distintas y el sistema ya las separa. `reportedEPS`: **0 ausencias**.

## 5. Profundidad

**Idéntica y notable en los cuatro medidos: 122 trimestres, desde el primer trimestre de 1996 hasta el segundo de 2026 — algo más de 30 años.** Las cuatro series son **trimestralmente contiguas**: el número de trimestres devueltos coincide exactamente con el que habría entre el más viejo y el más nuevo si no faltase ninguno.

Esa comprobación de contigüidad es la parte que hace la medición verificable en vez de confiada, y se cuenta **en trimestres**, no en días naturales — la rejilla del dato es trimestral, el mismo criterio que llevó a contar los horizontes en sesiones (D-30).

**Respuesta a la pregunta que motivó el bloque**: la calidad de IBM/NVDA/XOM **es estructural, no accidental** — cuatro activos nuevos de cuatro sectores distintos dan exactamente la misma profundidad y la misma completitud de `reportTime`. Con la salvedad honesta de que **n = 4 activos nuevos** es una muestra pequeña para generalizar a 31, y no se ha medido ni un solo activo financiero, de consumo básico ni de salud.

## 6. Distribución de eventos

**No hay eventos nuevos.** La cohorte activa sigue siendo la de HRP v1: 52 observaciones, 3 activos, `events_per_asset` `{IBM: 16, NVDA: 18, XOM: 18}`. Convertir trimestres en eventos exige ingesta en `data/`, que esta iteración tiene explícitamente prohibida.

Lo que la medición **sí** permite proyectar, marcado como proyección y no como dato:

| | medido | proyectado sobre el universo |
|---|---|---|
| activos con datos | 4 medidos + 3 de sesión anterior | ≤ **29** (31 − 2 irrecuperables) |
| trimestres por activo | 122 (4/4 medidos) | ~122 para los de historia larga |
| eventos potenciales | 488 medidos | **~3.400** si los 29 se comportan igual |

La restricción real no será el número de trimestres sino la **serie de precios**: un evento sin ventana de reacción no es una observación. Eso sigue sin medirse.

## 7. Independencia

`independence_status` sigue siendo **`LOW`** y `n_assets` sigue siendo **3**: esta iteración midió población, no la ingirió.

Lo que sí se ha construido es la pieza que D-31 dejó pendiente — **la unidad de dependencia depende de la clase de evento**, y ahora el perfil lo declara:

```python
INDEPENDENCE_MODEL = {"earnings_release": "ASSET_CLUSTERED"}

MODELOS_DE_INDEPENDENCIA = {
    "ASSET_CLUSTERED":      "los eventos del mismo activo no son independientes entre si",
    "EPISODE_CLUSTERED":    "los eventos del mismo episodio no son independientes entre si",
    "EVENT_DATE_CLUSTERED": "los eventos de la misma fecha no son independientes entre activos",
}
```

Tres trimestres de NVDA **son** tres eventos distintos, pero comparten empresa, sector, mercado y régimen: el cluster es el **activo**. Cinco documentos sobre la misma tramitación legislativa comparten el hilo causal: el cluster sería el **episodio** (D-28 explica por qué ese concepto no aplica a un evento programado). Una publicación de IPC afecta a todos los activos el **mismo día**: el cluster sería la **fecha**.

> **Declarar la dependencia no es corregirla.** El perfil dice qué dependencia *reconoce*; `n_effective` **sigue sin existir**, y el test estructural de D-31 sigue vigente: ningún símbolo del módulo contiene `effective`.

Las dos clases que aún no existen (`EPISODE_CLUSTERED`, `EVENT_DATE_CLUSTERED`) se declaran en el vocabulario pero **no se instancian**: no hay ninguna clase de evento que las use todavía, y no se ha inventado ninguna para poder usarlas.

## 8. Overlap

**Sin cambios, porque no hay población nueva**: `overlap_event_count` 0 · 0 · 0 · **3** para `0_1d` / `2_5d` / `2_20d` / `2_60d`; `overlap_rate` máximo **0,061**.

La política sigue siendo **`FLAG`** (D-30): se marca, no se elimina. Volver a medirla sobre una población ampliada es una de las cosas que el backfill desbloquea — y con series trimestrales **contiguas** (§5), la tasa de solape a `2_60d` subirá muy por encima del 6,1% actual, que sale de una cohorte con huecos de muestreo. Ahí §8 de D-30 volverá a ser informativa.

## 9. `2_60d`

Se aplica la decisión, ahora **en el código y no solo en la prosa**:

```python
HORIZON_CLASS = {
    "0_1d":  "IMMEDIATE_REACTION",
    "2_5d":  "SHORT_REACTION",
    "2_20d": "INTERMEDIATE_REACTION",
    "2_60d": "LONGER_TERM_CONTEXT",
}
HORIZONTES_DE_REACCION = ("0_1d", "2_5d", "2_20d")
```

`2_60d` **se sigue publicando y sigue siendo `VALID`** — reclasificarlo no es eliminarlo, y hay un test que lo comprueba. Lo que cambia es que ya no puede presentarse como horizonte de reacción de `earnings_release`: con un intervalo mediano entre resultados de 63,5 sesiones (D-30), una ventana de 60 cubre el **94,5%** del trimestre y mide "lo que pasó hasta el evento siguiente", no "la reacción al evento".

Cada celda de la rejilla declara ahora su `horizon_class`, y `HORIZONTES_DE_REACCION` da a un consumidor la lista de los tres primarios sin tener que conocer la discusión.

## 10. Profile leakage

La propiedad exigida: **`Profile(as_of=T)` debe salir idéntico aunque el dataset contenga observaciones posteriores a `T`.** No basta con filtrar `available_at`.

**Cómo se probó** (no es un test de filtrado, es un test de resultado): se calcula el mismo perfil dos veces, una sobre las 52 observaciones completas y otra sobre un dataset truncado a lo que existía en `T`, y se comparan las 20 celdas.

```
as_of 2015-01-01 · obs  52-> 10 · idénticas  4 · solo-contabilidad 16 · SUSTANTIVAS 0
as_of 2018-06-30 · obs  52-> 12 · idénticas  4 · solo-contabilidad 16 · SUSTANTIVAS 0
as_of 2020-01-01 · obs  52-> 18 · idénticas  4 · solo-contabilidad 16 · SUSTANTIVAS 0
as_of 2023-01-01 · obs  52-> 29 · idénticas  4 · solo-contabilidad 16 · SUSTANTIVAS 0
as_of 2026-09-08 · obs  52-> 52 · idénticas 20 · solo-contabilidad  0 · SUSTANTIVAS 0
```

**Cero diferencias sustantivas en las 20 celdas, en las cinco fechas.** `statistics`, `n_observations`, `status`, `overlap_rate` y el resto son bit a bit iguales.

**Lo que sí difiere, y por qué es correcto que difiera.** Tres campos cambian siempre: `n_excluidas`, `tasa_exclusion` y `exclusiones_por_motivo`. Con 52 observaciones se descartan 34 por PIT; con las 18 de la época **no hay nada que descartar**. Esos campos describen **el dataset que se ofreció**, no el perfil que salió.

En vez de esconder la excepción o de debilitar el test, se separa explícitamente:

```python
CAMPOS_DE_PROCEDENCIA = ("n_excluidas", "tasa_exclusion", "exclusiones_por_motivo")

def huella(perfil):   # sha256 del perfil SIN esos campos
```

`huella()` es lo que tiene que coincidir. Cuatro tests la fijan, incluido uno que comprueba que la huella **sí cambia** cuando cambia el `as_of` — sin él, la huella no estaría midiendo nada.

## 11. Condiciones para ampliar a 300+ activos

**La condición de avance no se cumple, y ese es el resultado correcto de esta auditoría**:

```
=== CONDICION DE AVANCE A v2 ===
  n_assets_medidos_con_datos       4
  n_assets_requerido               30
  n_assets_suficiente              False
  completitud_de_timestamp         1.0
  timestamp_suficiente             True
  profundidad_suficiente           True
  independencia_razonable          False
  event_class_coverage             1
  event_class_requerido            6
  avanzar_a_v2                     False
```

Está escrita como el usuario la formuló — **transversal y de calidad, nunca "si hay más de N eventos, adelante"**. Un test comprueba justamente eso: con `n_assets = 3` no avanza aunque hubiera miles de eventos.

**Los tres bloqueos reales para 300+ activos, en orden de dificultad:**

1. **La ingesta de equity no es automatizable por el camino actual.** El conector MCP **no puede escribir a disco**: cada respuesta de `EARNINGS` (~10k tokens) hay que transcribirla a mano. Ese, y no la cuota, fue el motivo de medir 6 de 15. Para 300 activos es inviable por completo. Lo desbloquearía una clave de API en un almacén de secretos (GitHub Actions), **nunca en el repositorio** — compatible con el protocolo de privacidad, que prohíbe la clave *en el repo*, no su uso. **Es una decisión del usuario y no se ha tomado.**
2. **La cuota**, subordinada a lo anterior: 25 llamadas/día → los 31 activos de Universe_v1 necesitan **2 días**; 300 activos, **12 días**. Con la cuota open-source que Alpha Vantage ofrece a proyectos verificados (mensaje preparado en `informes/2026-09-04_mensaje_alpha_vantage_open_source.md`, **no enviado**) dejaría de ser un límite.
3. **El sesgo de superviviencia es del proveedor, no del universo** (§3). Ampliar a 300 activos *pidiéndoselos a Alpha Vantage* daría 300 supervivientes. Para un universo históricamente honesto haría falta una fuente con tickers retirados — SEC EDGAR los conserva, y ya es una fuente aceptada por este proyecto para presentaciones regulatorias, aunque no da `reportTime`.

**Y una condición que no es de datos**: `event_class_coverage = 1`. El roadmap pide 6-8 clases de evento y solo existe `earnings_release`. Ampliar activos sin ampliar clases daría un perfil muy poblado de una sola clase.

## 12. Qué parte del perfil actual sigue siendo descriptiva

**Toda. Nada de lo medido aquí invalida HRP v1.1**, porque nada de lo medido aquí entró en la cohorte.

| | estado |
|---|---|
| `descriptive_status` | **12 `VALID` de 20**, sin cambios |
| `predictive_status` | **`NOT_EVALUATED` en las 20**, sin excepciones (D-29) |
| alcance de la descripción | sigue siendo **IBM, NVDA y XOM** — tres activos, no "las acciones estadounidenses" |
| `2_60d` | `VALID` y ahora explícitamente `LONGER_TERM_CONTEXT` |

Los perfiles ganan dos campos (`horizon_class`, `independence_model`) que **acotan su lectura sin cambiar ningún número**: ninguna estadística se ha recalculado. Y ganan una garantía nueva que antes no estaba probada: son **reproducibles bit a bit** para cualquier `as_of` pasado (§10).

La barrera de D-29 sigue en pie: ningún módulo de `engine/scoring/` ni `engine/reasoning/` menciona `perfil_reaccion`.

## 13. Tests

**601 → 627** (`Ran 627 tests · OK`).

**Fichero nuevo**: `tests/test_poblacion_universo.py` (**25 tests**)

*Universo congelado* — tamaño y diversidad sectorial; **la selección se reproduce desde su regla escrita** (reconstruye la muestra y la compara con el fichero); el universo incluye activos que dejaron de existir; cada exclusión lleva motivo; la cohorte de v1 está dentro del universo; las dos declaraciones son coherentes entre sí.

*Cobertura* — ningún activo no medido tiene números inventados; **un ticker desaparecido se registra vacío, no ausente**; las series medidas son trimestralmente contiguas; `reportTime` completo; **`reportTime` no es constante por activo** (MSFT); la condición de avance **no** se cumple; la condición es transversal y no de volumen.

*Clase de horizonte* — `2_60d` no es horizonte de reacción; los tres primarios sí lo son; **`2_60d` se sigue publicando** (reclasificar no es eliminar); toda celda declara su clase.

*Modelo de independencia* — `earnings_release` → `ASSET_CLUSTERED`; toda clase declara su modelo; toda celda lo lleva; **declarar la dependencia no es corregirla** (D-31 intacto).

*Profile leakage* — la huella no cambia al añadir observaciones posteriores (4 fechas × 20 celdas); las estadísticas son idénticas, no parecidas; **solo la contabilidad de exclusiones puede diferir**; y la huella **sí** cambia cuando cambia el `as_of`.

**Tests deliberadamente frágiles**, puestos para romperse cuando la arquitectura cambie: `test_la_condicion_de_avance_no_se_cumple_todavia` se rompe el día que la población sea suficiente, que es cuando hay que releer esta auditoría; `test_el_reportTime_no_es_constante_por_activo` se rompe si alguien "limpia" el registro de MSFT.

**Un test caducó, y no por esta iteración.** Al pasar el reloj a 2026-09-08, `test_acciones_con_pe_caducado_pero_tecnico_al_dia_si_publica_confianza` empezó a fallar: las fixtures de acciones están congeladas en **2026-09-02** y el técnico de IBM (`posicion_rango_52s_pct`, `confluencia_sesgo`, ambos **REQUERIDA**) cruzó su umbral de cadencia entre el día 5 y el día 6. Verificado que **no lo causaron los cambios de esta auditoría**: ninguno toca `thesis.py` ni las fixtures, y el fallo se reproduce por la fecha.

Era una **bomba de relojería**: el test comparaba una fixture congelada contra `datetime.now()`, así que tenía garantizado romperse. Arreglarlo relajando el umbral habría sido justo lo contrario de lo que el proyecto exige — el motor estaba haciendo lo correcto.

Arreglo aplicado: `build_thesis(symbol, tvl_chain, as_of=None)` y `build_thesis_equity(symbol, as_of=None)` exponen el reloj que `_evaluar_evidencia()` **ya aceptaba internamente** y que nadie estaba pasando; el test fija `as_of = "2026-09-03"` y pasa a comprobar **la regla** (una métrica `PUBLICADA` caducada no invalida la tesis) en vez de cuántos días llevan las fixtures congeladas. Los otros tres tests del mismo bloque se fijaron igual.

Y se añadió **`test_cuando_caduca_el_tecnico_REQUERIDO_la_tesis_deja_de_ser_valida`** (`as_of = "2026-12-01"`), que fija la otra cara de la regla: cuando lo REQUERIDO caduca, la tesis pasa a `INVALID` y deja de publicar confianza. Existe para impedir que un día se "arregle" un test caducado relajando el umbral.

## 14. QA

```
python3 engine/contract/qa.py --require-parquet
  Particiones abiertas y verificadas: 287 · Incidencias: 0
  QA CORE:    PASS
  QA PARQUET: PASS
  STATUS:     VERIFIED

python3 engine/knowledge/consulta.py --validar
  Knowledge: 26 entidades · 51 relaciones · 3 conceptos · 11 fuentes
  RESULTADO: PASS

git status --short data/ knowledge/
  (vacío)
```

**Sin cambios en datos ni en conocimiento.** El universo y la cobertura viven en `engine/events/`, junto a `episodios.json`, porque son **declaraciones curadas a mano**, no filas del contrato: no llevan `data_as_of`, no se historizan y `qa.py` no las valida. Tienen validación propia (`universo.incoherencias()`) y 25 tests, pero **no condicionan el `STATUS: VERIFIED` global** — la misma deuda que D-24 registró para la serie del benchmark.

---

## Qué cambió — ficheros

| fichero | estado | qué |
|---|---|---|
| `engine/events/universo_v1.json` | **nuevo** | universo congelado: 31 activos, 6 exclusiones, criterio y limitaciones declaradas |
| `engine/events/cobertura_universo_v1.json` | **nuevo** | medición de cobertura por activo; `NOT_MEASURED` explícito |
| `engine/events/_cobertura/*.txt` | **nuevo** | transcripciones (AAPL y CAT completas; VZ, MSFT, DWDP, UTX resumidas) |
| `engine/events/universo.py` | **nuevo** | lectura, comprobación de contigüidad, coherencia entre declaraciones, condición de avance |
| `engine/events/perfil_reaccion.py` | modificado | `HORIZON_CLASS`, `INDEPENDENCE_MODEL`, `CAMPOS_DE_PROCEDENCIA`, `huella()` |
| `tests/test_poblacion_universo.py` | **nuevo** | 25 tests |
| `engine/reasoning/thesis.py` | modificado | `as_of` opcional en los dos constructores de tesis (expone el reloj que `_evaluar_evidencia` ya aceptaba) |
| `tests/test_tesis_evidencia.py` | modificado | 4 tests fijados a fecha + 1 test nuevo — arreglo de una bomba de relojería ajena a esta iteración |

## Supuestos propios invalidados

1. **"La cuota de 25/día es el límite para ampliar la población."** No: el límite es que **el conector MCP no puede escribir a disco**. La cuota se resuelve esperando; la transcripción manual, no.
2. **"Un universo se define eligiendo activos representativos."** Elegirlos yo *es* la selección que había que evitar. La regla tiene que venir de un hecho público anterior a la medición.
3. **"`reportTime` es una propiedad estable de cada compañía."** MSFT lo desmiente con 5 excepciones repartidas por su serie moderna.
4. **"La suite estaba verde, así que el árbol estaba sano."** Estaba verde *ayer*. Un test que compara una fixture congelada contra `datetime.now()` no está verde: está pendiente de romperse en una fecha que nadie ha calculado.
5. **"Congelar el universo en 2019 resuelve el sesgo de superviviencia."** Solo lo resuelve del lado del *diseño*. Del lado de la *fuente* el sesgo persiste y es invisible: los tickers retirados no aparecen como huecos, aparecen como si nunca hubieran existido.
6. **"`return_full_data: false` devolvería una respuesta compacta."** No cambia nada.

## Deuda abierta que deja esta iteración

- **22 activos del universo `NOT_MEASURED`** — `cobertura_universo_v1.json`, con el motivo escrito.
- **Los 123 trimestres de IBM sin cuadrar** con los 122 de una serie contigua — comprobación pendiente, registrada en el propio fichero.
- **Universe_v1 no tiene mid cap** — condición explícita de Universe_v2.
- **La ingesta de equity depende de transcripción manual** — decisión de clave en almacén de secretos, pendiente del usuario.
- **`universo.py` fuera de `qa.py`** — mismo patrón que D-24.
- **`EPISODE_CLUSTERED` y `EVENT_DATE_CLUSTERED` declarados y sin instanciar** — a propósito: no se ha inventado una clase de evento para poder usarlos.
- **Puede haber más tests dependientes del reloj** — se arregló el que falló hoy; no se ha hecho una revisión sistemática de los 627 en busca de otras fixtures congeladas comparadas contra `datetime.now()`.

## Impacto sobre fases anteriores

- **HRP v1.1**: dos campos nuevos por celda; **ninguna estadística recalculada**, verificado porque los 42 tests de `test_perfil_reaccion.py` pasan sin reescritura.
- **P1 cierre (motor de razonamiento)**: `thesis.py` gana un parámetro **opcional** con valor por defecto que preserva el comportamiento exacto (`as_of=None` → `datetime.now()`). Ninguna llamada existente cambia de resultado; el cambio solo hace inyectable un reloj que ya existía dentro.
- **P6.2c/d, P6.1, P6, P5A, D-21, Data Contract**: **no tocados**. `git status --short data/ knowledge/` vacío.
- **`engine/crypto/score.py`**: no tocado; el test de regresión de D-22 sigue pasando.
- **Power BI / Web App / cron**: sin impacto — ni una fila nueva en `data/`.
