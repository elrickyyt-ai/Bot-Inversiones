# Auditoría del Historical Instrument Master — quién era la entidad y qué instrumento cotizaba

**Fecha**: 2026-09-08 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Base**: `12683b3`
**Alcance**: auditar y **diseñar** el mínimo necesario para estudiar empresas que cambiaron de ticker, de nombre, se fusionaron, se escindieron o dejaron de cotizar. **No se implementa el pipeline**, no se ingiere nada, no se amplía la cohorte.

**Verificación**:

```
python3 -m unittest discover -s tests            654 → 684 tests · OK
python3 engine/contract/qa.py --require-parquet  QA CORE: PASS · QA PARQUET: PASS · STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   PASS (26 · 51 · 11)
git status --short data/ knowledge/              vacío
python3 engine/events/identidad.py               modelo, casos, elegibilidad y matriz
```

Todas las mediciones son **en vivo** contra `data.sec.gov`, `www.sec.gov/Archives` y Yahoo, ejecutadas hoy.

---

## Respuesta al criterio de parada (§12)

> *"Para una empresa histórica, ¿quién era la entidad, qué instrumento cotizaba, con qué identificador, durante qué intervalo, y podemos reconstruir de forma reproducible su precio y sus eventos sin confundir un sucesor con el instrumento original?"*

**Parcialmente, y el reparto es asimétrico:**

| pregunta | respuesta |
|---|---|
| ¿quién era la entidad? | **SÍ** — CIK + `formerNames` con intervalos |
| ¿durante qué intervalo? | **SÍ** para la entidad |
| ¿qué instrumento cotizaba? | **SÍ desde ~2020**, **NO antes** |
| ¿con qué identificador (ticker)? | **NO de forma determinista para el pasado** |
| ¿reconstruir sus eventos? | **SÍ** (8-K Item 2.02 + `acceptanceDateTime` + XBRL) |
| ¿reconstruir su precio? | **Solo retornos, y solo fuera de acciones corporativas** |
| ¿sin confundir sucesor con original? | **SÍ, pero solo si el mapa es explícito** — automáticamente **NO** |

**`HISTORICAL_INSTRUMENT_MAPPING = INCOMPLETE`**, declarado en el fichero y fijado por un test.

## 1. Modelo de identidad

Cuatro capas, declaradas en `engine/events/identidad_instrumento.json`:

| capa | qué es | estabilidad |
|---|---|---|
| `LEGAL_ENTITY` | la persona jurídica; puede cambiar de nombre sin dejar de ser la misma | alta |
| `SEC_CIK` | identificador que la SEC asigna a un **filer** | **la más alta medida — pero no eterna** |
| `MARKET_INSTRUMENT` | el valor concreto que cotiza | media |
| `TICKER` | etiqueta de un instrumento en un mercado **en un momento** | **ninguna: no es identidad** |

```
LEGAL_ENTITY  -> SEC_CIK            1:N en el tiempo (una reorganización crea CIK nuevo)
SEC_CIK       -> MARKET_INSTRUMENT  1:N simultáneo (acciones y varias emisiones de deuda)
MARKET_INSTRUMENT -> TICKER         1:N en el tiempo, con intervalo de validez
TICKER        -> MARKET_INSTRUMENT  N:1 y NO INYECTIVA en el tiempo
```

Esa última línea es la que rompe todo lo demás, y no es teórica (§3).

## 2. CIK

**Es el ancla, y aguanta mucho más de lo que cabría esperar**: sobrevive a renombramientos y a fusiones. CIK `0000101829` atraviesa United Technologies → Raytheon Technologies → RTX sin cambiar.

**Pero no es eterno**, y el contraejemplo es reciente y está en la cohorte de producción:

```
CIK 0002115436 · ExxonMobil Holdings Corp · tickers ['XOM']
   29 filings · 2026-07-01 .. 2026-08-28 · formas: S-8 POS 23, 8-K 3, 10-Q 1, POSASR 1, 8-K12B 1

CIK 0000034088 · EXXON MOBIL CORP · tickers []
   1000 filings · 2019-12-18 .. 2026-08-07
```

> En **julio de 2026** —hace dos meses— ExxonMobil hizo una **reorganización en holding**. El `8-K12B` es la forma de registro de **emisor sucesor**. El ticker `XOM` migró al CIK nuevo, y el CIK histórico se quedó con **`tickers: []`**.

Resolver hoy `XOM → CIK` devuelve `2115436`, con 29 filings desde julio. Los 122 trimestres de historia viven bajo `0000034088`. **No es una curiosidad de los años noventa: le está pasando ahora a un activo que ya está en `data/`.**

## 3. Ticker

**El ticker no es identidad, y la prueba no es un 404 sino algo peor:**

```
XON    -> HTTP Error 404: Not Found        (Exxon antes de 1999)
DWDP   -> HTTP Error 404: Not Found
UTX    -> HTTP Error 404: Not Found
RTN    -> HTTP Error 404: Not Found        (Raytheon antes de la fusión)
MOB    -> OK  1011 sesiones · 2022-08-25 .. 2026-09-04
```

`MOB` devuelve datos. Y no es Mobil Corporation, absorbida en 1999:

```
MOB  {'longName': 'Mobilicom Limited', 'exchangeName': 'NCM',
      'instrumentType': 'EQUITY', 'firstTradeDate': 1661434200}
```

> **Un ticker retirado puede reasignarse a otra empresa.** Resolver un ticker histórico contra el proveedor actual no falla ruidosamente: **devuelve los datos de otra compañía**. Un 404 es honesto; `MOB` es una respuesta silenciosamente equivocada.

Ese es el argumento más fuerte del principio del §17: no basta con no confundir un **sucesor** con el predecesor — hay que no confundir un **desconocido** con él.

**Y el cambio de ticker es invisible en el precio**: la serie de `XOM` arranca en 1962 (`firstTradeDate: -252322200`) y cubre toda la era en que la empresa cotizaba como `XON`. Yahoo ha **reetiquetado retroactivamente** la historia de Exxon bajo el símbolo nuevo, sin marca alguna.

## 4. Instrumento

**Un CIK puede tener varios instrumentos a la vez**, y está medido. La portada del 10-Q de 2020-10-27 declara:

```
dei:EntityRegistrantName -> ['RAYTHEON TECHNOLOGIES CORPORATION']
dei:TradingSymbol        -> ['RTX', 'RTX 30']
dei:Security12bTitle     -> ['Common Stock ($1 par value)', '2.150% Notes due 2030']
dei:SecurityExchangeName -> ['New York Stock Exchange', 'New York Stock Exchange']
dei:EntityCentralIndexKey-> ['0000101829']
```

Dos instrumentos, un CIK. **El event study observa un `MARKET_INSTRUMENT`, no una `LEGAL_ENTITY`** — y hoy el proyecto los confunde, porque `DimAsset` indexa por símbolo.

**Cuándo es demostrable el instrumento negociado**, medido filing a filing:

| filing | `dei:TradingSymbol` |
|---|---|
| UTX 10-Q · 2019-04-26 | **AUSENTE** (ninguna etiqueta de portada) |
| UTX 10-Q · 2019-07-26 | **AUSENTE** (`EntityRegistrantName` y `EntityCentralIndexKey` sí, `TradingSymbol` no) |
| UTX 10-Q · 2020-10-27 | **`RTX`, `RTX 30`** |

**La frontera está en ~2019-2020**, con la entrada en vigor del XBRL de portada. Antes de eso, el ticker **no está** en el filing de forma estructurada.

**Y la heurística evidente falla.** El nombre del documento principal parece codificar el ticker:

```
2020-10-27  utx-20200930.htm
2021-10-26  rtx-20210930.htm
```

Pero el fichero de **octubre de 2020** se llama `utx-…` **cuando el ticker ya era RTX desde abril de 2020** — y su propia portada declara `TradingSymbol = RTX`. **El nombre del fichero está obsoleto respecto a su contenido.** Cualquier pipeline que dedujese el ticker del nombre del documento se equivocaría en ese trimestre.

## 5. Sucesores

`formerNames` da la cadena de identidad legal con intervalos:

| caso | cadena medida |
|---|---|
| **DWDP** | `DowDuPont Inc.` (2016-03-01 → 2019-05-31) → `DuPont de Nemours, Inc.` |
| **UTX** | `UNITED TECHNOLOGIES CORP /DE/` (1994-01-24 → 2020-04-06) → `RAYTHEON TECHNOLOGIES CORP` (2020-04-07 → 2023-06-29) → `RTX Corp` |
| **XOM** | `EXXON CORP` (1994-05-11 → 1999-11-30) → `EXXON MOBIL CORP` |
| **NVDA** | `NVIDIA CORP/CA` (1998-05-07 → 2002-06-04) → `NVIDIA CORP` (renombramiento cosmético) |
| **IBM** | sin `formerNames` |

**Pero sucesión de nombre ≠ sucesión de instrumento.** El caso de UTX lo demuestra: el 2020-04-03 ocurren **dos cosas distintas el mismo día** —las escisiones de Otis y Carrier, y la fusión con Raytheon— y `formerNames` solo registra el renombramiento. La transformación económica no está en ese campo.

## 6. Corporate actions

Historia completa de "splits" declarados por la fuente de precios:

```
XOM   5:  1976-07-26 2:1 · 1981-06-12 2:1 · 1987-09-15 2:1 · 1997-04-14 2:1 · 2001-07-19 2:1
IBM   5:  1973-05-29 5:4 · 1979-06-01 4:1 · 1997-05-28 2:1 · 1999-05-27 2:1 · 2021-11-04 1046:1000
NVDA  6:  2000-06-27 2:1 · 2001-09-12 2:1 · 2006-04-07 2:1 · 2007-09-11 3:2 · 2021-07-20 4:1 · 2024-06-10 10:1
DD    8:  ... · 2019-04-02 1487:1000 · 2019-06-03 4725:10000 · 2025-11-03 239:100 · 2026-06-24 1:3
RTX   6:  ... · 2020-04-03 15890:10000
```

**Dos patrones, y la fuente no los distingue:**

- **Ratios limpios** (2:1, 4:1, 3:2, 10:1, 5:4) → splits reales.
- **Ratios extraños** (`1487:1000`, `4725:10000`, `15890:10000`, `1046:1000`) → **escisiones disfrazadas de split**.

> **`IBM 2021-11-04 · 1046:1000` es la escisión de Kyndryl.** IBM está **ya en la cohorte de producción**, con serie de precio backfilleada desde 1970. Cualquier ventana de event study que cruce el 2021-11-04 compara IBM-con-Kyndryl contra IBM-sin-Kyndryl.

**Y el otro lado es peor: las fusiones no dejan rastro.** XOM declara cinco splits y **ninguno en 1999**, el año de la fusión con Mobil. La serie es continua, sin marca, a través de una operación que duplicó la empresa.

```
SPLIT / TICKER_CHANGE / HOLDCO_REORG →  declarado o irrelevante
SPINOFF                              →  declarado, pero MAL CLASIFICADO (como split)
MERGER                               →  NO DECLARADO
TICKER_REUSE                         →  NO DECLARADO, y devuelve otra empresa
```

**La clasificación no puede venir del proveedor de precios.** Éste da una *señal detectable* (un ratio raro), no una *clasificación*. La clasificación autoritativa está en el 8-K de la operación.

## 7. DWDP

| | |
|---|---|
| CIK | `0001666700` — `AVAILABLE` |
| entidad | `DowDuPont Inc.` 2016-03-01 → 2019-05-31 |
| eventos | 4 8-K Item 2.02 en la era del ticker retirado |
| resultado real | 131 obs. XBRL, 100% con `filed` |
| precio bajo `DWDP` | **`UNAVAILABLE`** (404) |
| precio bajo `DD` | **`AMBIGUOUS`** — rebaseado por dos escisiones |
| instrumento demostrable | **NO** — las portadas de 2019 no llevan `dei:TradingSymbol` |
| continuidad | **`AMBIGUOUS`** |

## 8. UTX

| | |
|---|---|
| CIK | `0000101829` — `AVAILABLE` |
| entidad | dos renombramientos encadenados con fechas |
| eventos | 9 8-K Item 2.02 hasta 2020-04-06 |
| resultado real | 324 obs. XBRL, 100% con `filed` |
| precio bajo `UTX` | **`UNAVAILABLE`** (404) |
| precio bajo `RTX` | **`AMBIGUOUS`** |
| instrumento demostrable | **SÍ, pero solo desde 2020** (`RTX`, `RTX 30`) |
| continuidad | **`AMBIGUOUS`** |

**El caso más instructivo**: el 2020-04-03 concurren una **escisión doble** (Otis, Carrier) y una **fusión** (Raytheon). Yahoo declara **un solo split** `15890:10000` por las escisiones y **nada** por la fusión. Una sola cifra para dos transformaciones económicas opuestas.

## 9. Precio

**Lo recuperable y lo no recuperable, separado:**

| | DWDP | UTX | IBM | NVDA | XOM |
|---|---|---|---|---|---|
| serie bajo ticker histórico | ❌ 404 | ❌ 404 | ✅ | ✅ | ✅ (bajo `XOM`; `XON` da 404) |
| serie bajo sucesor | ✅ rebaseada | ✅ rebaseada | — | — | — |
| nivel comparable con la época | ❌ | ❌ | ⚠️ tras 2021-11-04 | ✅ | ⚠️ |
| retornos válidos fuera de acciones | ✅ | ✅ | ✅ | ✅ | ✅ |

Recordatorio de la medición de D-39: `DD` reporta `close` **103,61** el 2019-04-18 cuando DowDuPont cotizaba **~53**.

## 10. Continuidad

**Tres preguntas distintas, no una** — y son decrecientes en fuerza:

```
PRICE_LEVEL_CONTINUITY        el NIVEL es comparable entre dos fechas
RETURN_CONTINUITY             el COCIENTE es un retorno económicamente válido
ECONOMIC_INSTRUMENT_CONTINUITY el instrumento representa la MISMA exposición
```

| transformación | forma | PRICE | RETURN | ECONOMIC |
|---|---|---|---|---|
| `SPLIT` | A → A | ❌ | ✅ | ✅ |
| `TICKER_CHANGE` | A → A | ❌ | ✅ | ✅ |
| `HOLDCO_REORG` | A → A' (CIK nuevo) | ❌ | ✅ | ✅ |
| `MERGER` | **A → B** | ❌ | ✅ | **❌** |
| `SPINOFF` | **A → B + C** | ❌ | ✅ | **❌** |
| `DELISTING` | A → (nada) | ❌ | ❌ | ❌ |
| `TICKER_REUSE` | (otra) → A | ❌ | ❌ | ❌ |

> **La fila que importa**: en `MERGER` y `SPINOFF` el **retorno sobrevive y la economía no**. Un ajuste multiplicativo restaura la aritmética del cociente, y el cociente sigue comparando **dos empresas distintas**. Por eso "un ajuste multiplicativo es suficiente" es falso, y por eso hacen falta las tres preguntas separadas.

Clases declaradas: `CONTINUOUS`, `CORPORATE_ACTION_ADJUSTED`, `SUCCESSOR_MAPPING`, `AMBIGUOUS`, `DISCONTINUOUS`.

**De los cinco casos, solo NVDA es `CORPORATE_ACTION_ADJUSTED`** — el único sin escisión ni fusión.

## 11. Fuente autoritativa

| relación | fuente | estado |
|---|---|---|
| `CIK ↔ historical company` | SEC `submissions` (`formerNames` con intervalo) | **`AVAILABLE`** |
| `CIK ↔ ticker` | **ninguna determinista para el pasado** | **`AMBIGUOUS`** |
| `ticker ↔ instrument` | portada inline-XBRL (`dei:TradingSymbol`) | `AVAILABLE` **desde ~2020** · `UNAVAILABLE` antes |
| `instrument ↔ successor` | `8-K12B`, 8-K Item 2.01, `formerNames` | `AMBIGUOUS` — hay que leer filings, no hay campo estructurado |
| `instrument ↔ corporate action` | Yahoo declara splits | `AMBIGUOUS` — no clasifica, y no declara fusiones |

**Se rechazó explícitamente EDGAR full-text como autoridad**, tal y como se pidió. Encuentra coincidencias (`DWDP` → CIK correcto en 44 de 76 documentos) pero es **búsqueda de texto con ruido real**, y "el CIK más frecuente" no es un criterio de identidad.

**Y se comprobó la alternativa estructurada, que tampoco sirve**: `companyfacts` solo expone conceptos `dei` **numéricos** —`EntityCommonStockSharesOutstanding` y `EntityPublicFloat`—. `TradingSymbol` es texto y **no está en la API**; hay que descargar y parsear el documento.

## 12. Huecos

**`HISTORICAL_INSTRUMENT_MAPPING = INCOMPLETE`.** El hueco exacto:

> **No existe fuente gratuita determinista que devuelva, dado un ticker y una fecha pasada, qué instrumento designaba.**

Lo recuperable, en orden decreciente de solidez:
1. **Identidad legal por CIK** — completa, con intervalos.
2. **Ticker del instrumento desde ~2020** — leyendo la portada inline-XBRL (no la API).
3. **Antes de 2020** — solo heurísticas: búsqueda de texto (con ruido) o el nombre del fichero (**medido obsoleto**: `utx-20200930.htm` con `TradingSymbol = RTX`).

Huecos adicionales medidos: la **clasificación** de la acción corporativa no está en el proveedor de precios; las **fusiones** no se declaran; el CIK **cambia** en reorganizaciones (XOM 2026); y `company_tickers.json` apunta al CIK **actual**, que puede no ser el histórico.

## 13. Impacto en event study

**La regla no es "excluir si hay acción corporativa"** — eso tiraría observaciones válidas. Es **si cambia el instrumento económico**. Cuatro casos, implementados en `identidad.elegibilidad_event_study()`:

```
sin acciones               eligible=True    CONTINUOUS
split en estimación        eligible=True    CORPORATE_ACTION_ADJUSTED
escisión en reacción       eligible=False   AMBIGUOUS
fusión fuera de ventana    eligible=True    CONTINUOUS
reutilización de ticker    eligible=False   AMBIGUOUS
```

Un split dentro de la ventana **no invalida nada**: el ajuste se cancela en el cociente. Una escisión sí, aunque el cociente sea aritméticamente correcto, porque compara dos empresas distintas.

**Impacto concreto sobre la cohorte actual**: IBM tiene una escisión el **2021-11-04**. Los eventos de IBM cuyas ventanas crucen esa fecha dejan de ser elegibles bajo esta regla. **No se ha aplicado** —sería implementar el pipeline— pero queda medido y con test.

## 14. Impacto en historical profile

**Ninguno inmediato: no se ha recalculado ni un perfil.** Lo que cambia es qué se sabe de ellos:

- `descriptive_status` y `predictive_status` **siguen igual** (12 `VALID` de 20, `NOT_EVALUATED` en las 20).
- Aparece una **fuente de exclusión nueva y no contabilizada**: acciones corporativas que cambian el instrumento. Hoy `poblacion()` no la conoce.
- Los perfiles de **IBM** están construidos sobre una serie con una escisión sin marcar. Con `n_assets = 3`, IBM es **un tercio** de la cohorte.
- **NVDA es el único de los cinco limpio.**

Esto **no invalida** HRP v1.1 —que es descriptivo y así se declara— pero acota su lectura: la mediana de `ABNORMAL_RETURN` a 2_60d incluye ventanas que pueden cruzar la escisión de Kyndryl. **No se ha cuantificado cuántas**, y no debe suponerse que son cero.

## 15. Propuesta de implementación futura

**No hace falta tocar `DimAsset`, ni crear una tabla de tickers.** El Knowledge Model **ya tiene** lo que falta, y está medido:

```
tipos de entidad : security, organization, venue, benchmark, sector, ...
predicados       : ISSUED_BY (security -> organization), LISTED_ON (security -> venue)
campos relación  : valid_from, valid_to, role, status, source_id, ...
uso real         : 51 relaciones, LAS 51 con intervalo de validez
```

El mapeo es directo:

| capa del modelo | representación propuesta |
|---|---|
| `LEGAL_ENTITY` | entidad `organization` existente |
| `SEC_CIK` | identificador de la `organization` |
| `MARKET_INSTRUMENT` | entidad `security` existente |
| `TICKER` | **atributo fechado del `security`**, nunca su identidad |
| `CIK ↔ instrumento` | `ISSUED_BY` con `valid_from`/`valid_to` — **ya existe y ya se usa** |

**La única extensión mínima**: un predicado de sucesión `security → security` que lleve en `nature` la transformación (`MERGER`, `SPINOFF`, `HOLDCO_REORG`…). Es lo que hoy no se puede expresar.

**Y debe nacer `NO CAUSAL`.** El modelo ya tiene `PREDICADOS_NO_CAUSALES = {BENCHMARKED_BY, COMPARED_TO}` por D-23. Una sucesión de instrumento **no es un mecanismo económico**: que DowDuPont se convirtiera en DuPont no conecta causalmente a DuPont con los clientes de Dow. Sin esa marca, el motor causal recorrería la arista y produciría caminos inexistentes — exactamente el fallo que D-23 corrigió para benchmark.

**D-21 queda preservada**: `benchmark` sigue siendo un tipo de entidad aparte y `ROLES_NO_ACTIVOS` intacto. Nada de esto convierte un índice en instrumento analizado.

**Orden recomendado** (ninguno ejecutado):
1. Declarar los 5 casos como entidades `security` + `organization` con `ISSUED_BY` fechado.
2. Añadir el predicado de sucesión, no causal, con test de regresión sobre `caminos.indice()`.
3. Detector de acciones corporativas sobre las series de precio (señal), con clasificación **declarada a mano** desde el 8-K (autoridad).
4. Conectar `elegibilidad_event_study()` a `poblacion()`.
5. Solo entonces, ingesta.

## 16. Qué no debe automatizarse todavía

| no automatizar | por qué |
|---|---|
| **Resolver ticker → CIK** | `MOB` devuelve Mobilicom. Un resolutor automático produce datos de otra empresa **sin fallar** |
| **Clasificar la acción corporativa por el ratio** | "1046:1000 parece escisión" es una heurística. La autoridad es el 8-K |
| **Sustituir el predecesor por el sucesor** | `DD` no es `DWDP`. El mapa debe ser explícito y revisado |
| **Deducir el ticker del nombre del fichero** | medido obsoleto: `utx-20200930.htm` declara `RTX` |
| **Dar de baja lo que el proveedor no conoce** | D-36 |
| **Reconstruir niveles de precio pre-escisión** | solo los retornos sobreviven, y solo fuera de la acción |

Lo que **sí** puede automatizarse ya: descarga por CIK, `acceptanceDateTime`, XBRL con `filed`, y la **detección** (no clasificación) de acciones corporativas.

---

## Qué cambió — ficheros

Cambio de código mínimo: la fuente declarativa y la invariante del principio.

| fichero | estado | qué |
|---|---|---|
| `engine/events/identidad_instrumento.json` | **nuevo** | 4 capas, 7 transformaciones, 3 tipos de continuidad, 5 casos, fuentes evaluadas, matriz |
| `engine/events/identidad.py` | **nuevo** | `continuidad_de()`, `clasificar_accion()`, `elegibilidad_event_study()`, `matriz_casos()`, `incoherencias()` |
| `tests/test_identidad_instrumento.py` | **nuevo** | 30 tests |

**Sin cambios en `data/` ni `knowledge/`.** `DimAsset` **no se ha tocado**, como se pidió.

## Supuestos invalidados

1. **"Un ticker retirado simplemente no devuelve datos."** `MOB` devuelve 1011 sesiones de **Mobilicom Limited**.
2. **"El CIK es permanente."** Una reorganización en holding crea uno nuevo — XOM, hace dos meses.
3. **"`formerNames` captura la sucesión."** Captura el **nombre**. El 2020-04-03 de UTX son una escisión doble y una fusión, y `formerNames` solo ve el renombramiento.
4. **"El nombre del documento codifica el ticker."** `utx-20200930.htm` declara `TradingSymbol = RTX`.
5. **"Las escisiones son el problema; los splits son inocuos."** Cierto — pero **las fusiones no se declaran en absoluto**, y eso es peor que declararlas mal.
6. **"Esto afecta a empresas raras."** Afecta a **IBM** (Kyndryl, 2021) y a **XOM** (holdco, 2026), dos de los tres activos de la cohorte.

## Deuda abierta

- **`HISTORICAL_INSTRUMENT_MAPPING = INCOMPLETE`** — sin fuente determinista pre-2020.
- **La escisión de Kyndryl no está marcada** en la serie de IBM ya cargada; impacto sobre los perfiles **no cuantificado**.
- **XOM tiene dos CIK** y el pipeline actual no lo sabe.
- **Fusiones sin declarar** por el proveedor de precios.
- **`identidad.py` fuera de `qa.py`** — mismo patrón que D-24, `universo.py` y `autoridad.py`.
- **Solo 5 casos auditados**; el resto del universo, `NOT_MEASURED`.
