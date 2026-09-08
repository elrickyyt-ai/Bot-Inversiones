# Estado del sistema — punto de entrada

**Actualizado**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Último commit**: `2ee412a`

> **Si eres un agente o una persona que entra por primera vez, lee este documento entero antes que ningún otro.** Está escrito para que no haga falta reconstruir la arquitectura leyendo cientos de commits.

---

## 1. Objetivo

Sistema de inteligencia financiera de apoyo a la decisión de inversión. **No** es un chatbot de bolsa, **no** predice precios y **no** recomienda operaciones. El sistema propone; el usuario ejecuta manualmente. No hay credenciales de trading en ninguna parte.

La propiedad que ordena todo el diseño:

> **El sistema nunca rellena una ausencia de conocimiento con una inferencia que parezca un hecho.** Tiene que poder decir explícitamente *"no existe el dato"*, *"no conozco la relación"* o *"el camino causal está incompleto"*.

Antes de tocar cualquier dato del usuario, `docs/00-protocolo-privacidad.md` es de lectura obligatoria.

---

## 2. Arquitectura actual

```
FUENTES  Kraken · Coinbase · CoinGecko · DefiLlama · FRED · Yahoo · Alpha Vantage · SEC EDGAR
   │
   ▼
DATA CONTRACT      data/incoming/*.csv (año en curso)  +  data/history/** (parquet inmutable)
   │                data/assets/ (DimAsset)  ·  data/news/
   ├──► P6.2a INTEGRIDAD TEMPORAL          los cinco relojes; available_at se DERIVA
   │           available_at ≤ analysis_as_of  ← la invariante que faltaba
   │
   ├──► P1b  Cobertura y frescura          dos ejes, nunca un enum
   │
   ├──► P3   Evidence                      vista derivada y regenerable
   │           │
   │           ├──► P4   Claims → Events
   │           │      └──► P6.2d Episodios   declarados, nunca inferidos
   │           │      └──► P6.2c Event study  earnings → reacción, sin agregar
   │           │             └──► HRP v1  perfil histórico  DESCRIPTIVO, no predictivo
   │           │                    └──► Diagnóstico de cohorte
   │           │                          ¿es INTERPRETABLE?  dependencia · solape
   │           │                             └──► Universo congelado + cobertura
   │           │                                   ¿hay POBLACIÓN?  DECLARADO, no medido
   │           │                                    └──► Autoridad de dato por componente
   │           │                                          SEC manda · AV enriquece · CIK ≠ ticker
   │           │                                     └──► Identidad de instrumento
   │           │                                           A→A · A→B · A→B+C   (transformaciones)
   │           │                                      └──► Cobertura de acciones corporativas
   │           │                                            ¿la ventana cruza una transformación?
   │           │                                       └──► Backfill readiness  (31 activos)
   │           │                                             BACKFILL_READY = false
   │                                                          │
   └──► P2 KNOWLEDGE ◄── Historical Instrument Master v1
          resolve_instrument(identifier, as_of)  ·  ticker ≠ identidad
   │           │
   │           └──► P5D  Data Requirements  ¿existe el dato que el mecanismo pide?
   │
   └──► P2   KNOWLEDGE (a mano, versionado)  entidades · relaciones · conceptos · fuentes
               │      └──► D-21 Benchmark / ComparisonReference
               │             bm:sp500 → IBM · NVDA · XOM   (serie en data/benchmarks/)
               │
               ├──► P5A  Causal Path        recorrido, sin economía
               │      └──► P5B  Mechanism + Direction
               │             └──► P6   Economic Impact   ¿derecho a cuantificar?
               │                    └──► P6.1 Materiality  derivada, nunca almacenada
               │
               └──► P5C  cadena económica real con fuentes externas

CONSUMO (desacoplado, no dicta el motor)   Power BI · Web App
```

**La dirección es única**: cada capa lee la anterior y ninguna escribe hacia atrás. Verificado por hash dentro de la propia suite en P3, P4, P5A, P5B, P6 y P6.1.

---

## 3. Capas cerradas

| Fase | Commit | Qué hace |
|---|---|---|
| Migración | `6c167e6`…`d27f162` | JSON → `history/` (parquet) + `incoming/` (CSV) |
| P1 | `b5bd426` | `fecha_dato` deja de ser la hora de ejecución |
| P1b | `0726049` | Cobertura y frescura como **dos ejes ortogonales** |
| P1 cierre | `bb76054` | La tesis declara su evidencia y su validez |
| P2 | `5f4efa1` | Knowledge Model: entidades, relaciones, conceptos, fuentes |
| P3 | `228b228` | Evidence v1, vista derivada y reversible |
| P4 | `a9ba0c6` | Event & Claim Layer |
| P5A | `b214082` | Causal Path / traversal — **cerrado, no se modifica** |
| P5B | `0c4003f` | Mecanismo y dirección económica |
| P5C | `61dca44` | Primera cadena económica real con fuentes externas |
| P5D | `cfbf38b` | Evidence Gap → Data Requirement |
| P6 | `4f22a88` | Economic Impact: derecho a cuantificar |
| P6.1 | `02c31ad` | Materiality derivada y acotada |
| P6.2a | `f30ffc5` | Integridad temporal: los cinco relojes, `available_at` derivado |
| P6.2b | `f30ffc5` | Look-ahead de 22-31 días corregido en 27 filas |
| P6.2c | `f30ffc5` | Event study mínimo: 52 eventos, `first_tradable_at`, sin agregar |
| P6.2d | `f30ffc5` | Episodios declarados sobre P4: 50 documentos → 43 eventos → 1 episodio |
| D-21 | `2ee412a` | Ontología de benchmark: `benchmark` como entidad, referencia ≠ activo, elegibilidad por familia de medida |
| `bm:sp500` | `da35869` | Primer benchmark real declarado: nivel publicado de `^GSPC`, 14.291 sesiones desde 1970-01-02 |
| HRP v1 | `07f867e` | `HistoricalReactionProfile`: descriptivo, 20 perfiles, ninguno desaparece por falta de datos |
| D-27/29/30/31 | `c44120a` | Ventana de estimación, dependencia y solapamiento: `descriptive` ≠ `predictive`, solape marcado, `n_effective` medido antes de formularse |
| D-32/33/34/35 | `f1b0d38` | Auditoría de población: universo congelado, sesgo de superviviencia de la fuente, `2_60d` = contexto, `independence_model`, reproducibilidad histórica |
| D-36/37/38/39 | `646c72d` | Autoridad de dato por componente: SEC manda, Alpha Vantage enriquece, consenso `UNAVAILABLE`, una escisión no es un split |
| D-40/41/42 | `0fa7bc3` | Identidad histórica de instrumento: el ticker es reasignable, fusión ≠ escisión, cabe en el Knowledge Model |
| D-43/44/45 | `018e520` | Cobertura de acciones corporativas: identidad durante la ventana, el filing manda, cuatro clases de relación |
| D-46/47/48/49 | `e581e22` | Backfill readiness: `false`; el cuello es la identidad del instrumento, no la cobertura |
| D-50/51/52 | `86068de` | Historical Instrument Master v1: aliases fechados, `SUCCEEDED_BY` no causal, validador temporal |

Detalle por fase, con qué se rompe si cae y cómo recuperarla: `informes/2026-09-07_trazabilidad_fases_P0_P61.md`.

---

## 4. Por qué se diseñaron así — la evidencia detrás de las decisiones

> **La validez de una observación histórica depende no solo de que el dato exista y sea *point-in-time*, sino de que la entidad, el instrumento y su continuidad económica puedan identificarse durante la ventana analizada.** (D-43)
>
> Y su corolario de seguridad, descubierto con el caso `MOB`: **un falso positivo de identidad es más peligroso que un dato ausente.**
>
> **Una ausencia con forma de superviviencia no es cobertura parcial** (D-47): un 90% cuyo 10% ausente son exactamente las empresas deslistadas es un sesgo, no una laguna.
>
> Y la raíz común de todo lo anterior: **el sistema no debe deducir semántica por ausencia de una excepción.** Un ticker no es una identidad porque no sepamos que sea otro; una relación no es causal porque no esté en una lista negra.


Estos invariantes no son preferencias de estilo: cada uno nació de un fallo real, medido. `docs/DECISIONES.md` guarda el historial completo, incluidas las decisiones que fueron revisadas.

| Invariante | De dónde salió |
|---|---|
| **Ausencia ≠ evidencia de ausencia** | TVL de BTC (P1b) · `polarity=DENIES` (P2) · sustitución de tres estados (P5B) · `MISSING` ≠ `NOT_APPLICABLE` (P5D) |
| **Un token se comparte si y solo si significa lo mismo** | `source_priority` significaba dos cosas (P0). Dos nombres para una idea es el mismo error: por eso `POINT` no se introdujo junto a `KNOWN` (P6.1) |
| **Dos ejes, no un enum** | cobertura/frescura (P1b) · validez/completitud (P5A) |
| **La fecha del bloque es la del componente más antiguo** | nunca la del más reciente |
| **`UNKNOWN` nunca es permisivo** | es el peor valor en los tres ejes, no uno intermedio |
| **Causalidad ≠ materialidad** | `rel:0046` acredita que TSMC suministra a NVIDIA, no en qué proporción (P6) |
| **"No puedo" ≠ "no sé"** | `NOT_APPLICABLE` no mejora con más datos; `UNKNOWN` sí (P6) |
| **Una regla del código no es un hecho del mundo** | `EXPOSED_TO` degradado a `PROVISIONAL`/`ASSERTED`/`BAJO` (P2) |
| **Lo derivado no se versiona** | `data/current/`, `coverage.json`, `requirements.json`, Evidence, **`available_at`** (D-17) |
| **`STALE` no es un `LOOK_AHEAD` suave** | dos defectos de fechado a la vez y de signo contrario en los mismos fundamentales (D-18) |
| **Un agregado no es conocible hasta su último componente** | lo contrario que la fecha del bloque, y por eso no se contradicen: son dos preguntas |
| **Una referencia de mercado no es un instrumento analizado** | meter índices en `DimAsset` rompe `calendario()` y `esperadas()` de forma medible (D-21) |
| **La ausencia de benchmark limita qué medidas, no si hay análisis** | `RAW_RETURN` es elegible con n=52 mientras `ABNORMAL_RETURN` no lo es, sobre las mismas observaciones (D-22) |
| **Una relación de medida no es un mecanismo económico** | el S&P 500 como referencia de NVIDIA no la conecta con las demás del índice (D-23) |
| **La validez temporal es también de la ventana** | un evento conocible cuya ventana termina después de `as_of` sigue siendo look-ahead (D-26) |
| **Un perfil nunca desaparece: devuelve por qué no puede construirse** | 10 de 20 perfiles no son `VALID` y los 10 dicen su motivo |
| **Un test que se apoya en que algo NO existe caduca** cuando ese algo se documenta | cinco tests reescritos en P5C |

---

## 5. Estado actual, medido

**Suite**: 750 tests · OK — **QA**: `QA CORE: PASS` · `QA PARQUET: PASS` · `STATUS: VERIFIED` (287 particiones, 0 incidencias) — **Knowledge**: PASS (39 entidades · 66 relaciones · 14 fuentes)

```bash
python3 -m unittest discover -s tests
python3 engine/contract/qa.py --require-parquet
python3 engine/knowledge/consulta.py --validar
git status --short data/ knowledge/     # debe salir vacío
```

**Integridad temporal del contrato** (`qa.py`, bloque `INTEGRIDAD TEMPORAL`), sobre 507.330 filas:

| | Filas | |
|---|---:|---|
| `SAFE` | 505.167 | técnico, fundamental cripto, y fundamental de acciones tras la corrección de P6.2b |
| `LOOK_AHEAD` | 2.148 | IPC, HICP y tipo efectivo de la Fed: fecha del periodo, no de publicación. Acotados, **no corregidos** (requieren ALFRED) |
| `STALE` | 15 | las cinco métricas de `DEFECTO_DE_FECHADO` × 3 activos, ya registradas |
| `AMBIGUOUS` | 0 | ninguna métrica sin reloj declarado — una nueva sin declarar **bloquea** |

**Lo que el motor causal produce hoy sobre la cadena real** `NVDA → TSMC → CoWoS`:

```
camino        VERIFIED · COMPLETE          (P5A)
dirección     heredada de P5B, no recalculada
materialidad  BOUNDED ≤19%                 (P6.1)  ← con fuente, sin atribución
magnitud      UNKNOWN                      (P6)
```

**Por qué la magnitud sigue `UNKNOWN`** — cuatro bloqueos, uno resuelto:

| Bloqueo | Estado | Causa |
|---|---|---|
| Materialidad | **`BOUNDED ≤19%`** | resuelto a cota en P6.1 |
| *Fitness* de la variable | `PROXY` | `demand` solo se resuelve con `revenue_growth_yoy_pct` |
| Línea base | **ninguna computable** | ver §6 |
| Coeficiente de transmisión | ninguno | decisión: v1 no estima, ver `docs/DECISIONES.md` |

---

## 6. Deudas abiertas

| Deuda | Dónde está registrada | Por qué sigue abierta |
|---|---|---|
| **Los fundamentales de acciones son un *snapshot*, no una serie** | `informes/2026-09-07_medicion_lineas_base.md` | Medido: las **42** series fundamentales de IBM/NVDA/XOM tienen **exactamente 1 observación**. Ninguna línea base es computable. La ingesta de acciones es manual (Alpha Vantage), nunca automatizada |
| El contrato no admite observaciones sobre entidades que no son activos | `engine/impact/observaciones.py` | `asset_type_of('TSM') → None`. Las 3 filas del 20-F viven aisladas. Misma familia que `capacity_utilization(tech:cowos)` |
| `capacity_utilization(tech:cowos)` | P5D | `MISSING`, sin candidatas ni fuente identificada |
| `adapt_equity()` fecha 5 métricas con la fecha del trimestre | `cadencias.DEFECTO_DE_FECHADO` · `temporal.SEMANTICA_DATA_AS_OF` | Reescribiría filas ya en el contrato. **Clasificado `STALE` en P6.2a**: no falsea un backtest hacia el futuro, al revés que las 9 que sí se corrigieron (D-18) |
| **Sin benchmark formal para cripto** | D-21 · D-24 · D-25 | Resuelto para acciones (`bm:sp500`, nivel publicado). **Sin resolver para cripto**, que es el 60% del contrato: no hay índice PIT gratuito defendible y un índice casero sobre los holdings sería sesgo de selección por construcción |
| **Fecha de publicación de las series macro** | `temporal.RETRASO_PUBLICACION_DECLARADO` | Vive en ALFRED (vintages), no en FRED. 2.148 filas acotadas por cota conservadora, no corregidas |
| **Dirección causal noticia↔precio** | informe de P6.2 §10 | Una noticia puede escribirse *porque* el precio ya se movió. No se representa; no se inventa un campo que no se pueda rellenar |
| **`reportTime` ausente en las fixtures antiguas de equity** | `tests/fixtures/equity/*_earnings.json` | 8 trimestres sin ese campo, así que `momento_publicacion` sale `None`. La ingesta manual debe guardar el payload completo |
| `desempleo_pct` y `spread_10y2y_pct` no llegan al contrato | `thesis.py::_MACRO_CONTEXTO` | Decisión de alcance |
| HBM y sustrato ABF sin fuente | `knowledge/pendiente/nvidia_cadena.json` | Buscados en los dos filings: cero menciones |
| Samsung / SK Hynix / Micron | `knowledge/pendiente/` | **Ya tienen fuente verificada**; fuera del alcance acordado, promovibles en un paso |
| `tech:cowos` se evalúa como insumo de coste, no como restricción de capacidad | informe de P6 | P5B enruta por R5; decisión de no tocar P5B |
| **Solo 8 securities con identidad histórica declarada** | D-50 · `knowledge/entities/securities.json` | Los otros 25 del universo siguen sin mapa. Es curación, no diseño |
| **El grafo causal conecta empresas del mismo mercado** | D-52 | 4 caminos NVDA↔Mobilicom/Walgreens sin arista causal. Aparecieron al declarar identidad correcta |
| **`historical_ticker` al 0% en los 31** | D-46 · `readiness_universo.json` | Ninguna fuente determinista dice qué ticker designaba a un instrumento en una fecha pasada. **Es el cuello de botella del backfill** |
| **Precio ausente justo en los 3 deslistados** | D-47 | DWDP, UTX y WBA. La cobertura que falta tiene forma de sesgo de superviviencia, no de laguna aleatoria |
| **`companyconcept` da falsos negativos** | D-48 | Para KO devuelve 0 donde `companyfacts` da 233. El pipeline futuro debe usar `companyfacts` o comparar ambos |
| **Acciones corporativas `NOT_MEASURED` en 26 de 31 activos** | D-43 · `acciones_corporativas.json` | La tasa de contaminación del universo es **desconocida**, no baja. Es lo que decide si el Instrument Master es mejora o requisito |
| **8 de 12 acciones sin verificar contra la SEC** | D-44 | Clasificadas por indicio de ratio. Marcadas como no verificadas, sin ascender |
| **No hay detector posible de fusiones** | D-44 | No dejan señal en el precio. Un detector sobre la serie encontraría escisiones y perdería fusiones |
| **El traversal causal usa lista negra** | D-45 | 7 de 95 caminos sin arista causal. Pasar a lista blanca tocaría P5A, cerrada |
| **La escisión de Kyndryl no está marcada en IBM** | D-41 · `identidad_instrumento.json` | Serie cargada desde 1970 con un `1046:1000` el 2021-11-04 que es una escisión. IBM es 1/3 de la cohorte; impacto sobre los perfiles **no cuantificado** |
| **XOM tiene dos CIK** | D-40 | El histórico (`0000034088`, `tickers: []`) y el del holding (`0002115436`, desde 2026-07). El pipeline actual no lo sabe |
| **Las fusiones no las declara el proveedor de precios** | D-41 | XOM no marca nada en 1999. Peor que declararlas mal: no hay señal que detectar |
| **`identidad.py` fuera de `qa.py`** | D-24 (mismo patrón) | 30 tests propios; no condiciona el `STATUS: VERIFIED` |
| **Sin puente autoritativo ticker histórico → CIK** | D-36 · `autoridad_datos.json` | `company_tickers.json` es de supervivientes; EDGAR full-text lo recupera con ruido real (44/76 y 68/100). Es el hueco de un Historical Instrument Master |
| **XBRL no llega a los años noventa** | D-37 | UTX desde 2007-12-31, DWDP desde 2015-12-31, mientras el precio llega a 1970 |
| **Rebaseo por escisiones no cuantificado** | D-39 | Medido en un caso (DD). No se sabe en cuántos activos del universo ocurre |
| **Consenso PIT sin fuente** | D-38 | Ninguna fuente gratuita publica el consenso con su fecha de vigencia. `UNAVAILABLE` declarado, nunca inventado |
| **`autoridad.py` fuera de `qa.py`** | D-24 (mismo patrón) | Tiene 26 tests propios; no condiciona el `STATUS: VERIFIED` global |
| **La ingesta de equity no es automatizable** | D-32 · informe de población §11 | El conector MCP no escribe a disco: cada activo exige transcripción manual. Inviable para 300+. Necesita clave en almacén de secretos — decisión del usuario |
| **El proveedor solo conoce supervivientes** | D-32 | `EARNINGS` y `SYMBOL_SEARCH` devuelven vacío para DWDP y UTX. Un universo congelado no es reconstruible con Alpha Vantage, y el sesgo no se ve desde dentro de los datos |
| **22 activos de Universe_v1 `NOT_MEASURED`** | `cobertura_universo_v1.json` | Nunca estimados. Coste de transcripción, no cuota |
| **Los 123 trimestres de IBM sin cuadrar** | `cobertura_universo_v1.json` | 123 frente a los 122 de una serie contigua 1996Q1–2026Q2, que es lo que dieron los otros cinco con ese rango. Comprobación pendiente, no dato bueno |
| **Universe_v1 no tiene mid cap** | D-32 · `universo_v1.json` | Sin composición histórica verificable de un índice mid cap a 2019-01-01; construirla de memoria sería inventarla. Condición de Universe_v2 |
| **Posibles bombas de relojería en tests** | Nota de D-35 | Se arregló la que falló al pasar a 2026-09-08 (fixtures congeladas contra `datetime.now()`); no se han revisado los 627 |
| **La cohorte de eventos tiene 3 activos** | D-31 · `diagnostico_cohorte.py` | `independence_status = LOW`. 52 observaciones de 3 acciones del mismo mercado no son 52 unidades independientes. Los ~356 eventos existen (`EARNINGS` los devuelve en el plan gratuito); la ingesta es manual y no se ha hecho |
| **`n_effective` sin fórmula** | D-31 · cabecera de `engine/events/diagnostico_cohorte.py` | Con 3 activos la correlación intra-cluster es inestable. Se publican los conteos y `independence_status`; un test impide introducir la fórmula sin quitarlo |
| **No existe volatilidad realizada en el contrato** | D-27 revisada · `perfil_reaccion.MEDIDAS_SIN_METODOLOGIA` | La única disponible es una media móvil de 30 sesiones que solapa su propia ventana de estimación. Bloquea 4 perfiles con `INSUFFICIENT_METHODOLOGY` |
| **Sin `ComparisonReference` de sector declarada** | D-21 · D-30 | Elegir peers ahora sería hacerlo *después* de ver los resultados. Bloquea `PEER_RELATIVE_RETURN` (4 perfiles) |
| **`predictive_status` nunca evaluado** | D-29 · `perfil_reaccion.PREDICTIVE_STATUS` | Ninguna comprobación fuera de muestra: ni walk-forward, ni partición temporal, ni otros activos. Corresponde a P8 |
| **`diagnostico_cohorte.py` fuera de `qa.py`** | D-24 (mismo patrón que la serie de benchmark) | Tiene 12 tests propios sobre datos reales, pero no condiciona el `STATUS: VERIFIED` global |
| `consolidate.py` huérfano · `confluencia_sesgo` con dos vocabularios | P0 | Sin impacto funcional |

---

## 7. Próxima decisión

**Medición hecha, diseño pendiente.** `informes/2026-09-07_medicion_lineas_base.md` establece que:

- de las **6** líneas base que declaran los mecanismos, **0** son computables hoy;
- pero **por dos razones distintas**, y eso cambia la prioridad:
  - `CUSTOMER_DEMAND` — la variable existe (por proxy) y lo que falta es **historia**: 1 observación;
  - los otros cinco — **la variable ni siquiera existe**, así que la pregunta de la línea base todavía no se plantea.

La decisión pendiente es de dónde sale la historia de fundamentales de acciones, y está descrita con opciones en ese informe. **No se implementa nada hasta decidirla.**

**Hallazgo de P6.2 que afecta directamente a esa decisión** (2026-09-07, verificado en vivo, 3 llamadas): el endpoint `EARNINGS` de Alpha Vantage **devuelve la serie trimestral completa en el plan gratuito** — IBM 123 trimestres desde 1996-03-31, XOM 122 desde 1996-03-31, NVDA 111 desde 1999-04-30 (su primer trimestre tras la OPV). Cada trimestre trae `fiscalDateEnding`, `reportedDate`, `estimatedEPS`, `reportedEPS`, `surprisePercentage` y `reportTime`. `engine/equity/score.py` la recorta con `earn[:8]`.

Eso **no resuelve** la decisión —`EARNINGS` da EPS y sorpresa, no `roe_pct` ni los márgenes, que vienen de `COMPANY_OVERVIEW` y siguen siendo un snapshot— pero sí cambia el planteamiento: hay al menos una serie fundamental con 30 años de profundidad, point-in-time y sin coste, que hoy se está tirando. Las opciones del informe de líneas base deben reevaluarse con ese dato encima de la mesa.

**Segunda decisión: D-21 — CERRADA, IMPLEMENTADA Y CON SU PRIMER DATO** (`informes/2026-09-07_auditoria_ontologia_benchmark.md` · `…_implementacion_d21_benchmark.md` · `…_declaracion_benchmark_sp500.md`).

> `DimAsset` representa instrumentos analizados; las referencias de mercado no se convierten en activos por conveniencia. La asignación es una **relación de Knowledge**, no una tabla nueva. **La ausencia de benchmark no elimina el análisis de reacción: limita qué medidas pueden llamarse *abnormal return*.**

`bm:sp500` declarado con el **nivel publicado** del índice (D-25), serie en `data/benchmarks/SP500.csv` — fuera del árbol de activos (D-24). Tres asignaciones `BENCHMARKED_BY` / `MARKET`, con la vigencia fijada por el activo (NVDA desde su OPV de 1999-01-22, no desde 1970).

**La cadena completa funciona sobre 52 eventos reales**: `available_at → first_tradable_at → surprise → raw → benchmark → abnormal`, sin look-ahead. Mediana de \|bruto − anormal\| **0,57 pp**, máximo **2,81 pp**, y **3 eventos donde el signo cambia** (IBM 1999-04-21: bruto +1,25%, anormal −1,04%). `ABNORMAL_RETURN` pasa a ser elegible (n=52 ≥ 40).

| Familia | Estado |
|---|---|
| `RAW_RETURN` | utilizable (n=52 ≥ 30) |
| `ABNORMAL_RETURN` | **utilizable** para IBM/NVDA/XOM (n=52 ≥ 40) |
| `PEER_RELATIVE_RETURN` | sin asignación declarada |
| Cripto | sin benchmark formal — y **sin excluir del análisis** |

**Tercera pieza: `HistoricalReactionProfile v1` — CONSTRUIDO** (`informes/2026-09-07_historical_reaction_profile_v1.md`). Descriptivo, no predictivo: ninguna señal, ningún score, ningún `reaction_gap`.

De los **20 perfiles** de la rejilla `event_class × measure_type × horizon`, v1 dio **10 `VALID` y 10 con su motivo**. Que la mitad no fuera válida era el resultado correcto.

**Cuarta pieza: iteración D-27 / independencia / solapamiento — HECHA** (`informes/2026-09-07_d27_dependencia_y_solapamiento.md`, decisiones **D-27 revisada · D-29 · D-30 · D-31**). Metodológica, sobre **los mismos 52 eventos**: no se amplió la cohorte, no se declaró ningún benchmark nuevo, no se tocó `data/` ni `knowledge/`.

El principio que cristaliza: **`COMPUTABLE` ≠ `INTERPRETABLE` ≠ `PREDICTIVO`.** v1 demostró lo primero; esta iteración mide lo segundo; lo tercero no se ha tocado.

**Rejilla vigente** (`as_of` 2026-09-07, política de solape `FLAG`) — **12 `VALID` de 20**:

| Medida | 0_1d | 2_5d | 2_20d | 2_60d |
|---|---|---|---|---|
| `RAW_RETURN` | VALID −0,11 | VALID −0,05 | VALID +0,32 | VALID +2,27 |
| `ABNORMAL_RETURN` | VALID −0,58 | VALID −0,49 | VALID −0,67 | VALID −1,02 |
| `PEER_RELATIVE_RETURN` | `INSUFFICIENT_COMPARABILITY` (×4) | | | |
| `VOLUME_RELATIVE_TO_PRE_EVENT` | VALID **2,04** | VALID **1,26** | VALID **1,06** | VALID **1,01** |
| `VOLATILITY_RELATIVE_TO_PRE_EVENT` | `INSUFFICIENT_METHODOLOGY` (×4) | | | |

**Lo más informativo**, y es descriptivo: a 60 sesiones la mediana **bruta** es +2,27% con `prob+` 0,65, y la **anormal** −1,02% con `prob+` 0,45. Descontar el mercado cambia por completo la lectura de la deriva larga. **No se afirma que la clase prediga nada**: la mediana anormal es ~0 en los cuatro horizontes y el IQR es entre 7 y 16 veces mayor que ella.

**Lo que la iteración midió** (`python3 engine/events/diagnostico_cohorte.py`):

| medición | resultado | consecuencia |
|---|---|---|
| ventana de estimación `[-20,-1]` | **52/52** completas · 0 contaminadas · 0 huecos de volumen | la base pre-evento existe de verdad |
| base del volumen: mediana / media / z-score | media contaminada al alza en el **90%** de las ventanas; z-score hasta **16,92**; la elección **cambia el signo** en 2_60d | **mediana**, medida y no elegida por costumbre |
| volatilidad disponible | media móvil de 30 sesiones que **solapa** su propia ventana de estimación | `INSUFFICIENT_METHODOLOGY`, no `INSUFFICIENT_COMPARABILITY` |
| dependencia | `n_events` 52 · `n_assets` **3** · `independence_status` **LOW** · `cluster` `asset` | el cuello de botella no es `n_events` |
| solapamiento | 0 · 0 · 0 · **3/49** (6,1%) | `FLAG`, no `EXCLUDE` |
| intervalo entre resultados | **63,5 sesiones** (15 intervalos entre 58 y 66) | `2_60d` cubre el **94,5%** del trimestre |
| full vs non-overlapping (2_60d) | ABN −1,02 → −0,88 con n 49→46 | **no discrimina todavía**; ≠ "no hay efecto" |

**Hallazgo que no se buscaba — contaminación estructural ≠ solapamiento técnico**: con solo el 6% de solapamiento formal, `2_60d` parecería limpio; su cobertura del 94,5% del trimestre dice que a 60 sesiones "deriva posterior al evento" y "lo que pasó hasta los resultados siguientes" ya no son distinguibles. **`2_20d`** (cobertura 0,315) es el horizonte largo interpretable; **`2_60d` se publica como contexto de deriva, nunca como medida de reacción**.

**Dos estados, no uno** (D-29): `descriptive_status` y `predictive_status` son campos independientes. **Toda la rejilla vale `predictive_status = NOT_EVALUATED`**, incluidos los 12 descriptivamente válidos — no se ha hecho ninguna comprobación fuera de muestra. Un test recorre `engine/scoring/` y `engine/reasoning/` y exige que **ningún fichero mencione `perfil_reaccion`**: la barrera contra usarlo para decidir es estructural, no documental.

**`n_effective` sigue sin existir, deliberadamente** (D-31): con 3 activos no se puede estimar la correlación intra-cluster. Se publican los conteos y un `independence_status` de tres valores (`HIGH` ≥ 30 activos · `MEDIUM` ≥ 10 · `LOW`) mientras la fórmula no se pueda elegir con evidencia. Un test impide introducirla sin quitarlo.

**Quinta pieza: auditoría de población — HECHA** (`informes/2026-09-07_auditoria_poblacion_historical_events.md`, decisiones **D-32 · D-33 · D-34 · D-35**). Mide si existe una población con la que arreglar `n_assets = 3`. **No es un backfill**: cero eventos cargados en `data/`.

El razonamiento que la motivó: ampliar a ~356 eventos de **los mismos tres activos** daría `n_events = 356` y `n_assets = 3` — más datos y la misma dependencia. **El cuello de botella es transversal, no temporal.**

**Universo congelado** (`engine/events/universo_v1.json`): `universe:v1:djia-2019`, **31 activos · 9 sectores**, `as_of_date = 2019-01-01`. Los 30 del DJIA de esa fecha más NVDA. La regla es ejecutable — un test reconstruye la muestra desde ella. Congelar en el pasado obliga a incluir **DWDP** y **UTX**, que ya no existen, y eso es deliberado.

**El hallazgo que cambia el plan de ampliación:**

> **La fuente solo conoce supervivientes.** `EARNINGS` devuelve `{}` para DWDP y UTX; `SYMBOL_SEARCH` con "DowDuPont" y "United Technologies" devuelve **conjunto vacío**. Un universo congelado en el pasado **no se puede reconstruir** con Alpha Vantage. Los 2 de 31 irrecuperables (**6,5%**) lo son *precisamente porque* tuvieron una acción corporativa — la definición del sesgo de superviviencia. Y no es detectable desde dentro: DWDP no aparece como hueco, aparece como si nunca hubiera existido. **Ampliar a 300 activos pidiéndoselos a este proveedor daría 300 supervivientes.**

**Cobertura medida** (`python3 engine/events/universo.py`), 6 de 31 activos:

| símbolo | trimestres | desde | sin `reportTime` | sin `estimatedEPS` | contigua |
|---|---|---|---|---|---|
| AAPL | 122 | 1996-04-17 | 0 | 8 (todos < 2004) | ✅ |
| CAT | 122 | 1996-04-16 | 0 | 0 | ✅ |
| VZ | 122 | 1996-04-18 | 0 | 0 | ✅ |
| MSFT | 122 | 1996-04-18 | 0 | 0 | ✅ |
| DWDP · UTX | **0** | — | — | — | `TICKER_AUSENTE_DEL_PROVEEDOR` |

**488 trimestres, cero `reportTime` ausentes, las cuatro series trimestralmente contiguas.** La calidad de IBM/NVDA/XOM **es estructural, no accidental** — con la salvedad de que son 4 activos nuevos y no se midió ninguno financiero, de consumo básico ni de salud.

**Segundo hallazgo, operativo**: `reportTime` **no es constante por activo**. MSFT publica post-market como norma y **pre-market en 5 trimestres** repartidos por su serie moderna. Cachear "MSFT = post-market" desplazaría `first_tradable_at` un día en esos cinco y metería la sesión del anuncio dentro de la ventana previa — la misma familia de error que D-27 corrigió para el volumen.

**Reproducibilidad histórica probada** (D-35): `Profile(as_of=T)` sale idéntico aunque el dataset contenga observaciones posteriores a `T` — **cero diferencias sustantivas** en las 20 celdas, en 5 fechas entre 2015 y 2026. Lo único que difiere es la contabilidad de exclusiones, que describe el dataset ofrecido y no el perfil; `CAMPOS_DE_PROCEDENCIA` la nombra y `huella()` hashea el resto.

**Dos campos nuevos por celda, sin recalcular ninguna estadística**: `horizon_class` (`2_60d` → **`LONGER_TERM_CONTEXT`**, D-33 — se sigue publicando, deja de presentarse como reacción) e `independence_model` (`earnings_release` → **`ASSET_CLUSTERED`**, D-34 — declarar la dependencia no es corregirla; `n_effective` sigue sin existir).

**Condición de avance a v2 — NO se cumple, y ese es el resultado correcto:**

```
n_assets_medidos_con_datos       4        n_assets_requerido    30
n_assets_suficiente              False    timestamp_suficiente  True
profundidad_suficiente           True     event_class_coverage  1 (requerido 6)
avanzar_a_v2                     False
```

**Sexta pieza: autoridad de datos históricos — HECHA** (`informes/2026-09-08_auditoria_autoridad_datos_historicos.md`, decisiones **D-36 · D-37 · D-38 · D-39**). Mediciones **en vivo** contra SEC EDGAR, `data.sec.gov` y Yahoo. Cero eventos ingeridos.

**La regla que sobrevive a este backfill (D-36):**

> **La cobertura de un proveedor NO define quién existió en nuestro pasado.** Que una empresa falte en un proveedor es un hecho sobre el **proveedor**, nunca sobre la **empresa**.

Demostrado: los dos activos que Alpha Vantage no conoce están **enteros** en EDGAR — CIK `0001666700` con `DowDuPont Inc.` (2016-03-01 → 2019-05-31), 1009 filings, 131 obs. XBRL; CIK `0000101829` con `UNITED TECHNOLOGIES CORP /DE/` (1994-01-24 → 2020-04-06), 1002 filings, 324 obs. XBRL.

**El sesgo está en tres capas, y no son la misma**: el directorio de Alpha Vantage (sesgado), **`company_tickers.json` de la SEC — también sesgado**, 10.415 empresas sin DWDP ni UTX — y **EDGAR por CIK, no sesgado**. Solo el CIK es inmune.

**Autoridad por componente (D-37):**

| componente | autoridad | estado |
|---|---|---|
| existencia de empresa | SEC — CIK + `formerNames` fechados | `AVAILABLE` |
| **ticker histórico → CIK** | **ninguna autoritativa** | **`AMBIGUOUS`** |
| ocurrencia del evento | SEC — 8-K Item 2.02 | `AVAILABLE` |
| `available_at` | SEC — `acceptanceDateTime` | `AVAILABLE` |
| resultado real | SEC XBRL | `AVAILABLE` |
| expectativa | Alpha Vantage (**ENRICHMENT**) | `AVAILABLE` supervivientes · `UNAVAILABLE` deslistados |
| consenso PIT | ninguna | `UNAVAILABLE` |
| precio | mercado | **`UNAVAILABLE` símbolo histórico · `AMBIGUOUS` sucesor** |
| benchmark | `bm:sp500` | `AVAILABLE` |

**Dos hallazgos que cambian cómo se fecha y se lee un evento:**

1. **`acceptanceDateTime` es un instante, `reportTime` una etiqueta binaria.** Presente en el 100% de los filings, al segundo y en UTC. De un instante se **deriva** pre/intra/post; al revés no. Contraejemplo que la etiqueta no puede representar: el 8-K Item 2.02 de DWDP del **2019-04-18** se aceptó a las `19:38:27Z` = **15:38 ET, intradía**, 22 min antes del cierre.
2. **XBRL es nativamente *vintage*** (`filed` + `accn` en el 100%). El EPS de UTX para `end=2019-12-31` vale **1,32** presentado en 2020 y **6,41** presentado en 2022. Tomar el último valor para un evento de 2019 es **look-ahead puro** — y Alpha Vantage, sin campo de vintage, no permite ni detectarlo.

**Revisión de un supuesto del bloque 4 (D-39)**: Yahoo **codifica las escisiones como splits**. `DD` declara `1487:1000` (Dow) y `4725:10000` (Corteva) en 2019, y reporta `close` **103,61** el 2019-04-18 cuando DowDuPont cotizaba **~53**. Una escisión **no** es un artefacto mecánico. Los **niveles** de la era deslistada no son recuperables; los **retornos** sí, mientras la ventana no cruce la acción corporativa — y Yahoo la declara, así que es detectable. `data/` **no se ha tocado**: afecta a ingestas futuras, no a IBM/NVDA/XOM, que no tuvieron escisiones.

**Un evento se construye sin Alpha Vantage (D-38)**: `filing + available_at + resultado real` son **suficientes** — verificado sobre DWDP y UTX. La falta de consenso da `expectation_status`/`surprise_status` `UNAVAILABLE` y **no borra el evento**; hoy ninguna de las cinco medidas del motor depende de la expectativa.

**Matriz de cobertura** (`python3 engine/events/autoridad.py`): **163 de 248 celdas siguen `NOT_MEASURED`**, ninguna rellenada. `AVAILABLE` 50 · `UNAVAILABLE` 33 · `AMBIGUOUS` 2.

**Decisión recomendada: Camino A, con una condición** — tratar las acciones corporativas como huecos y excluir toda ventana que las cruce. **No se justifica pagar un proveedor**; sí un mapa ticker→CIK curado a mano para 31 activos.

**Séptima pieza: Historical Instrument Master — AUDITADO Y DISEÑADO** (`informes/2026-09-08_auditoria_historical_instrument_master.md`, decisiones **D-40 · D-41 · D-42**). Mediciones en vivo. Cero ingesta, `DimAsset` sin tocar.

**El principio que se convierte en invariante del sistema:**

> Un proveedor que no conoce un instrumento no puede convertirlo en inexistente; y un **ticker sucesor no puede convertirse silenciosamente en el instrumento predecesor**.

**El caso peor no es un 404 (D-40).** `XON`, `DWDP`, `UTX` y `RTN` dan 404 — honesto. Pero **`MOB` devuelve 1011 sesiones desde 2022** y es **Mobilicom Limited**, no Mobil Corporation: el ticker fue **reasignado**. Un resolutor automático de tickers históricos produciría un histórico aparentemente completo y **silenciosamente equivocado**.

**Cuatro capas, y el ticker no es una de las estables:**

```
LEGAL_ENTITY  -> SEC_CIK            1:N en el tiempo (una reorganización crea CIK nuevo)
SEC_CIK       -> MARKET_INSTRUMENT  1:N simultáneo  (RTX declara 'RTX' y 'RTX 30')
MARKET_INSTRUMENT -> TICKER         1:N en el tiempo, con intervalo de validez
TICKER        -> MARKET_INSTRUMENT  N:1 y NO INYECTIVA en el tiempo
```

**El CIK tampoco es eterno, y es actual**: CIK `0002115436` "ExxonMobil Holdings Corp" tiene **29 filings desde 2026-07-01** con un **`8-K12B`** (emisor sucesor); `company_tickers.json` mapea `XOM` a **ese** CIK y el histórico `0000034088` se quedó con **`tickers: []`**. Le está pasando **ahora** a un activo de la cohorte.

**Fusión ≠ escisión (D-41), y la asimetría es peligrosa:**

| transformación | forma | cómo la representa la fuente de precios | PRICE | RETURN | ECONOMIC |
|---|---|---|---|---|---|
| `SPLIT` | A → A | declarada, ratio limpio | ❌ | ✅ | ✅ |
| `SPINOFF` | **A → B + C** | declarada **como split**, ratio extraño | ❌ | ✅ | **❌** |
| `MERGER` | **A → B** | **NO declarada** | ❌ | ✅ | **❌** |
| `TICKER_REUSE` | (otra) → A | **NO declarada**, devuelve otra empresa | ❌ | ❌ | ❌ |

En fusión y escisión **el retorno sobrevive y la economía no**: el ajuste multiplicativo restaura la aritmética y el cociente sigue comparando **dos empresas distintas**.

> **`IBM 2021-11-04 · 1046:1000` es la escisión de Kyndryl**, y `XOM` no declara nada en 1999 pese a la fusión con Mobil. **Dos de los tres activos de la cohorte están afectados**; de los cinco casos auditados **solo NVDA está limpio**. El impacto sobre los perfiles **no está cuantificado**, y no debe suponerse cero.

**Regla de elegibilidad**, ejecutable: no es *"excluir si hay acción corporativa"* sino **si cambia el instrumento económico**. Un split en ventana no invalida; una escisión sí.

**Dónde vive la identidad (D-42)**: **no en `DimAsset`**. El Knowledge Model ya tiene `security`, `organization`, `ISSUED_BY`, `LISTED_ON` y `valid_from`/`valid_to` — **51 relaciones, las 51 con intervalo**. La única extensión mínima es un predicado de **sucesión** `security → security`, que **debe nacer NO CAUSAL** (D-23): una sucesión no es un mecanismo económico. **D-21 preservada.**

**`HISTORICAL_INSTRUMENT_MAPPING = INCOMPLETE`**: `companyfacts` solo sirve `dei` numéricos; `TradingSymbol` es texto y solo está en la portada inline-XBRL **desde ~2020**.

**Octava pieza: cobertura de acciones corporativas — MEDIDA** (`informes/2026-09-08_auditoria_corporate_actions_y_continuidad.md`, decisiones **D-43 · D-44 · D-45**). Ni un perfil recalculado, ni una fila de `data/` tocada.

**La medición sobre los 52 eventos:**

```
  horiz    n_events     clean  con_accion   ambiguous
  0_1d           52        52           0           0
  2_5d           52        52           0           0
  2_20d          52        52           0           0
  2_60d          52        50           2           0
```

> **Cero ambiguos — y ese número no puede leerse solo.** La escisión de Kyndryl (2021-11-04) cae en un **hueco de muestreo** de IBM: sus eventos saltan de 2021-01-22 a 2022-01-25, y el evento real del Q3 2021 (8-K Item 2.02 del 2021-10-20) **no está en la cohorte**. El 0% mide la dispersión del muestreo, no la limpieza de los datos. Un test lo fija para impedir la lectura ingenua.

**Proyección sobre serie contigua**: `2_60d` **1,6% contaminado, 0,5% ambiguo** sobre ~560 eventos teóricos. **Bajo para estos tres activos y no extrapolable** — IBM tuvo 1 escisión en 27 años, DWDP 2 en 3 años y UTX 2 el mismo día. Las acciones de **26 de los 31 activos son `NOT_MEASURED`**: la tasa del universo **no es baja, es desconocida**.

**La clasificación exige el filing (D-44)**: verificada la escisión de Kyndryl con el **8-K del 2021-11-04, `items=2.01`** ("Completion of Acquisition or Disposition of Assets"), en la misma fecha que el factor `1046:1000`. **4 de 12 acciones verificadas contra la SEC**; las otras 8 marcadas como no verificadas.

> **Las fusiones no tienen señal de precio.** XOM declara cinco splits y ninguno en 1999. Es peor que una clasificación errónea: un detector basado en la serie encontrará las escisiones y **se perderá todas las fusiones**.

**Resolución temporal de identidad, verificada (D-43)**:

```
XOM  @ 2019-04-26 -> 0000034088  EXXON MOBIL CORP
XOM  @ 2026-08-15 -> 0002115436  ExxonMobil Holdings Corp
MOB  @ 1995-06-01 -> AMBIGUOUS: ningún intervalo declarado cubre esa fecha
```

**Política propuesta, no implantada**: `FLAG` para lo ajustable, **`EXCLUDE` para `MERGER` y `SPINOFF`**, `AMBIGUOUS` para `UNKNOWN`. `TRUNCATE` evaluado y descartado. Con la cohorte actual **ningún perfil cambiaría de valor** si se implantara hoy.

**Hallazgo colateral (D-45)**: el traversal causal usa **lista negra**. De 95 caminos desde NVDA, **7 (7%) no contienen ninguna arista causal** (`LISTED_ON`, `ISSUED_BY → DOMICILED_IN → DOMICILED_IN`). D-23 cerró el benchmark; `ISSUED_BY`, `LISTED_ON`, `DOMICILED_IN` y `CLASSIFIED_AS` siguen recorriéndose. **`SUCCESSOR_OF` se clasifica `STRUCTURAL` antes de existir** para que no entre por defecto. La corrección de fondo —lista blanca— tocaría P5A y **no se ha hecho**.

**Novena pieza: backfill readiness — MEDIDA sobre los 31** (`informes/2026-09-08_backfill_readiness_historico.md`, decisiones **D-46 · D-47 · D-48 · D-49**). Medición en vivo contra la SEC y la fuente de precios, **sin usar Alpha Vantage para decidir qué activos existen**.

> **`BACKFILL_READY = false`.** **28 de 31** empresas se reconstruyen completas como entidad + evento + resultado + precio + benchmark. **El cuello de botella no es la cobertura: es la identidad del instrumento.**

```
  componente                  AVAIL   UNAV   NOTM   AMBI   coverage
  historical_identity            31      0      0      0     100.0%
  SEC_event                      31      0      0      0     100.0%
  actual_financials              31      0      0      0     100.0%
  successor_mapping              31      0      0      0     100.0%
  benchmark                      31      0      0      0     100.0%
  CIK                            29      0      0      2      93.5%
  price                          28      3      0      0      90.3%
  event_study_eligibility        12      3      0     16      38.7%
  AV_enrichment / expectation     7      2     22      0      22.6%
  historical_ticker               0      0      0     31       0.0%
  corporate_actions               0      3      0     28       0.0%
```

**Escenario C**, con una precisión: la identidad **de entidad** está al 100%; lo que está al 0% es la capa **ticker → instrumento**. **El Instrument Master pasa de mejora futura a requisito previo.**

**El hallazgo que decide (D-47):**

```
fuera del directorio actual : ['DWDP', 'UTX', 'WBA']
sin precio                  : ['DWDP', 'UTX', 'WBA']
¿coinciden?                 : True
```

> Las ausencias de precio son **exactamente** los activos que el directorio ya no lista. Un 90,3% leído como "casi completo" backfillearía 28 supervivientes y perdería justo los 3 casos que hacen la muestra insesgada. Un test **bloquea el backfill solo por esa coincidencia**.

**Y apareció un tercer caso que no estaba en el diseño**: **WBA** no está en `company_tickers.json`; su CIK `0001618921` se recuperó por EDGAR full-text, con 211 obs. de `NetIncomeLoss` y sus 8-K intactos. Con DWDP (escisión) y UTX (fusión) son **tres formas distintas** de dejar de cotizar, las tres invisibles para el directorio.

**Dos correcciones que obligó la medición (D-48)**: medir `actual_financials` solo como `EarningsPerShareDiluted` habría dado **29/31** — KO tiene 4 observaciones y **Visa ninguna**; con `NetIncomeLoss` la cobertura real es **31/31**. Y los dos endpoints de la SEC **se contradicen para KO** (`companyconcept` 0 vs `companyfacts` 233), verificado que **no es sistemático** (IBM y Apple coinciden).

**Lista blanca causal evaluada y NO aplicada (D-49)**: de tres variantes, la única sana —exigir ≥1 arista causal en el camino emitido— elimina **37 de 356 (10,4%)** y **ninguno con contenido causal**. Cumple dos de los tres criterios; falla **regresión cero** (NVDA prof2 27→23, BTC prof2 33→21, con tests que afirman sobre esos conteos). **P5A no se toca**; queda como `P5A hardening` aparte.

**Décima pieza: Historical Instrument Master v1 — IMPLEMENTADO** (`informes/2026-09-08_implementacion_historical_instrument_master_v1.md`, decisiones **D-50 · D-51 · D-52**). Primera iteración que **escribe en `knowledge/`**: 26/51/11 → **39 entidades · 66 relaciones · 14 fuentes**. `data/` intacto.

**El criterio de salida, demostrado:**

```
  ident  as_of        status      security         issuer
  XOM    2019-04-26   VALID       sec:XOM.NYSE     org:exxonmobil
  XOM    2026-08-15   VALID       sec:XOM.NYSE     org:exxonmobil-holdings
  XON    1998-01-01   VALID       sec:XOM.NYSE     org:exxonmobil
  MOB    1995-06-01   UNRESOLVED  -                -
  MOB    2024-01-05   VALID       sec:MOB.NASDAQ   org:mobilicom
  DWDP   2018-11-01   VALID       sec:DWDP.NYSE    org:dupont
  DWDP   2024-01-01   UNRESOLVED  -                -
  UTX    2019-01-23   VALID       sec:UTX.NYSE     org:rtx
  WBA    2019-06-01   VALID       sec:WBA.NASDAQ   org:walgreens
```

Y el punto de control `price_available AND instrument_identity_valid`:

```
  MOB   @ 1995-06-01  precio=True  identidad=UNRESOLVED  elegible=False
  DWDP  @ 2018-11-01  precio=False identidad=VALID       elegible=False
```

> **`MOB` con precio disponible y sin identidad no es elegible.** Es lo que separa esto de un mapa de tickers.

**Sin estructura paralela (D-50)**: `LISTING` se representa con el alias `ticker` + `venue` + vigencia que `aliases` **ya tenía**; `SEC_CIK` es un alias fechado de la organización. **Un solo predicado nuevo**, `SUCCEEDED_BY`, **`STRUCTURAL` y fuera del recorrido causal** (D-23). D-21 intacta, con test.

**Hubo que corregir el propio validador (D-51)**: la comprobación de alias era **global**, así que declarar Mobilicom con el ticker `MOB` habría sido **rechazado** — el supuesto *"ticker = identidad"* estaba incrustado en la validación. Ahora la ambigüedad es **temporal**: un ticker reutilizado es legítimo si las vigencias no se solapan. Y se corrigieron **6 vigencias** que llevaban la fecha de *declaración* en vez de la económica — `rel:0009` (XOM) era directamente incorrecta.

**Efecto colateral medido, y no es menor (D-52):**

```
sec:NVDA.NASDAQ -> ven:NASDAQ -> sec:MOB.NASDAQ -> org:mobilicom
sec:NVDA.NASDAQ -> ven:NASDAQ -> sec:WBA.NASDAQ -> org:walgreens
```

**Declarar identidad correcta creó cuatro caminos causales espurios** entre empresas que solo comparten mercado, **ninguno con arista causal**. Antes NASDAQ era un callejón sin salida. **El coste de la lista negra deja de ser teórico**; queda un test frágil que se romperá cuando se aplique la variante C de D-49. Un test de P5A caducó por esto y se reescribió (§3 del protocolo).

> **Declarar más conocimiento verdadero no solo puede mejorar el grafo.** Con recorrido por lista negra, cada entidad nueva amplía la superficie de caminos espurios.

**Lo siguiente**, por orden de lo que desbloquea:

1. **Decidir el precio histórico de DWDP, UTX y WBA** — es la decisión A/B/C: (A) la fuente existente lo recupera → backfill; (B) existe pero la continuidad económica es ambigua → flag/exclude por horizonte; (C) no recuperable → **solo entonces** tiene sentido estudiar un proveedor de pago.
2. **Mapa de identidad para los 25 activos restantes** del universo — trabajo de curación, no de diseño.
3. **`P5A hardening`** (variante C de D-49), ahora con coste medido.
4. **Clasificar las acciones corporativas de los 31 desde el 8-K** — hoy 5 de 31.
5. **Conectar el punto de control a `poblacion()`**.
6. **Entonces sí**: ampliar población y volver a medir independencia y solape.
7. **Architecture Consolidation** — revisión de P0-P6.1 buscando las invariantes realmente comunes entre PIT, Event, Knowledge, Benchmark, Instrument y Eligibility. Solo ahí tendrá sentido evaluar si `Evidence Eligibility` es una abstracción legítima. **Antes no.**
8. Después: `n_effective` (D-31), más clases de evento, y por último `predictive_status` ≠ `NOT_EVALUATED` (P8).

Roadmap acordado: `P6.2 Quantification unlocks` → `P7 Market Impact` → `P8 Mispricing` → `P9 Thesis` → `P10 Portfolio` → `P11 Outcome/Calibration`. Power BI y Web App consumirán una proyección del motor; no lo dictan.

---

## 8. Cómo se documenta este proyecto

`docs/07-protocolo-de-informes.md` fija qué debe dejar cada fase. En resumen: diseño → informe de implementación → hallazgos → decisiones y desviaciones → deudas → tests/QA → trazabilidad acumulada. **Cuando un descubrimiento cambia una decisión anterior, la historia no se borra**: queda `decisión original → evidencia nueva → revisión → decisión vigente` en `docs/DECISIONES.md`.
