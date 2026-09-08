# Auditoría de autoridad de datos históricos — qué fuente manda sobre cada componente

**Fecha**: 2026-09-08 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Base**: `5702c9b` · **Commit**: `646c72d`
**Alcance**: determinar la fuente autoritativa de cada componente de un *historical earnings event*. **No se implementa ningún pipeline nuevo**, no se ingiere ni un evento, no se amplía de 6/31.

**Verificación**:

```
python3 -m unittest discover -s tests            627 → 654 tests · OK
python3 engine/contract/qa.py --require-parquet  QA CORE: PASS · QA PARQUET: PASS · STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   PASS (26 · 51 · 11)
git status --short data/ knowledge/              vacío
python3 engine/events/autoridad.py               autoridad por componente y matriz de cobertura
```

**Todas las mediciones son en vivo**, contra SEC EDGAR, `data.sec.gov` y Yahoo Finance, ejecutadas hoy. Ninguna cifra procede de memoria.

**Nota de privacidad**: SEC pide declarar un `User-Agent`. Se comprobó que basta uno descriptivo (`Bot-Inversiones research`) — **no hace falta enviar ningún correo ni dato personal**, y no se envió. El `User-Agent` vacío sí se rechaza (403).

---

## La pregunta correcta

No es *"necesitamos más datos"*. Es:

> **¿Qué parte concreta del conocimiento histórico nos falta, y cuál es la fuente de autoridad adecuada para recuperarla sin introducir una nueva forma de look-ahead o de sesgo de superviviencia?**

D-32 demostró que Alpha Vantage devuelve vacío para DWDP y UTX. La tentación es leer eso como *"esas empresas no están en nuestro pasado"*. Esta auditoría demuestra que es exactamente al revés, y deja la regla protegida por tests:

> **La cobertura de un proveedor NO define quién existió en nuestro pasado.** Que una empresa falte en un proveedor es un hecho sobre el **proveedor**, nunca sobre la **empresa**.

## 1. Autoridad por componente

`engine/events/autoridad_datos.json` — declarativo y curado a mano, como `universo_v1.json` y `episodios.json` (D-04). La propuesta del encargo se **verificó pieza a pieza**; dos piezas no sobrevivieron intactas.

| componente | autoridad | estado | ¿coincide con la propuesta? |
|---|---|---|---|
| `company_instrument_existence` | SEC EDGAR (CIK + `formerNames` fechados) | `AVAILABLE` | ✅ |
| `ticker_historico_a_CIK` | **ninguna autoritativa** | **`AMBIGUOUS`** | ⚠️ **pieza que faltaba en la propuesta** |
| `event_occurrence` | SEC EDGAR — 8-K Item 2.02 | `AVAILABLE` | ✅ (precisado: 8-K, no 10-Q) |
| `available_at` | SEC EDGAR — `acceptanceDateTime` | `AVAILABLE` | ✅ |
| `actual_financial_result` | SEC XBRL (`companyconcept`) | `AVAILABLE` | ✅ |
| `expectation_estimatedEPS` | Alpha Vantage (**ENRICHMENT**) | `AVAILABLE` supervivientes · `UNAVAILABLE` deslistados | ✅ |
| `consensus_point_in_time` | ninguna | `UNAVAILABLE` | ✅ |
| `reportTime` pre/post | **SEC derivado** · AV como enriquecimiento | `AVAILABLE` | ⚠️ **mejor que la propuesta** |
| `price` | fuente de mercado | **`UNAVAILABLE` bajo símbolo histórico · `AMBIGUOUS` bajo sucesor** | ⚠️ **la propuesta era optimista** |
| `benchmark` | `bm:sp500` (nivel publicado, D-25) | `AVAILABLE` | ✅ |

## 2. Survivorship

El sesgo aparece en **tres capas distintas**, y confundirlas es lo que lleva a conclusiones equivocadas:

| capa | ¿hay sesgo? | evidencia medida |
|---|---|---|
| **Directorio de tickers de Alpha Vantage** | **Sí, total** | `SYMBOL_SEARCH` devuelve conjunto vacío para DowDuPont y United Technologies |
| **`company_tickers.json` de la SEC** | **Sí, total** | 10.415 empresas; **DWDP y UTX AUSENTES**, solo aparecen RTX y DD |
| **EDGAR por CIK** | **No** | ambos CIKs devuelven el historial íntegro, con nombres anteriores fechados |

> El hallazgo que más importa: **la SEC también tiene sesgo de superviviencia si se entra por ticker.** Su fichero de tickers es de supervivientes igual que el de Alpha Vantage. Lo que **no** tiene sesgo es el **CIK**, que es permanente y arrastra la identidad histórica.

Y de ahí la pieza que faltaba en la propuesta: **entre "un ticker histórico" y "un CIK" no hay puente autoritativo medido**. EDGAR full-text search lo recupera —"DWDP" devuelve CIK `0001666700` en 44 de 76 documentos, "UTX" devuelve `0000101829` en 68 de 100— pero es **búsqueda de texto con ruido real** (Dow, Corteva, fondos que citan el símbolo), no un registro de identificadores. Por eso queda `AMBIGUOUS` y no `AVAILABLE`: es **el hueco exacto de un Historical Instrument Master**.

## 3. DWDP

```
CIK 0001666700 · name (hoy): DuPont de Nemours, Inc. · tickers (hoy): ['DD']
formerNames: 1
   - DowDuPont Inc. | 2016-03-01 -> 2019-05-31
filings recientes: 1009 · acceptanceDateTime no vacíos: 1009 de 1009
```

- **Existencia**: recuperada por completo, con el intervalo de validez del nombre. La estructura es la misma que D-21 dio a la asignación de benchmark: una relación **fechada**, no un atributo.
- **Eventos**: **4 8-K con Item 2.02** en la ventana 2017-09 → 2019-06, ya en la era del ticker retirado (2019-05-02, 2019-04-18, 2019-01-31, 2018-11-01).
- **Resultado real**: **131 observaciones** de `EarningsPerShareDiluted` (2015-12-31 → 2026-06-30), el 100% con `filed` y `accn`.
- **Expectativa**: `UNAVAILABLE`. Alpha Vantage no tiene la compañía.
- **Precio**: Yahoo **404** bajo `DWDP`. Ver §7.

## 4. UTX

```
CIK 0000101829 · name (hoy): RTX Corp · tickers (hoy): ['RTX']
formerNames: 2
   - RAYTHEON TECHNOLOGIES CORP     | 2020-04-07 -> 2023-06-29
   - UNITED TECHNOLOGIES CORP /DE/  | 1994-01-24 -> 2020-04-06
filings recientes: 1002 · acceptanceDateTime no vacíos: 1002 de 1002
```

- **Existencia**: recuperada, con **dos** renombramientos encadenados y sus fechas. Un identificador permanente atraviesa una fusión y dos cambios de nombre.
- **Eventos**: **9 8-K con Item 2.02** hasta 2020-04-06.
- **Resultado real**: **324 observaciones** XBRL (2007-12-31 → 2026-06-30), 100% con `filed` y `accn`.
- **Expectativa**: `UNAVAILABLE`.

## 5. SEC

**Es la autoridad, y por tres razones medidas — no por reputación.**

**(a) `acceptanceDateTime` está en el 100% de los filings**, al segundo y en UTC. Es *estrictamente superior* al `reportTime` de Alpha Vantage: un **instante** del que se **deriva** pre/intra/post comparando con el horario de NYSE. Al revés no se puede — de una etiqueta binaria no se recupera una hora.

Y esa derivación encuentra un caso que la etiqueta binaria **no puede representar**:

| filing | `acceptanceDateTime` | hora ET | clasificación |
|---|---|---|---|
| UTX 8-K 2.02 · 2019-01-23 | `12:10:20Z` | 07:10 | pre-market |
| UTX 8-K 2.02 · 2019-10-22 | `11:01:03Z` | 07:01 | pre-market |
| DWDP 8-K 2.02 · 2019-05-02 | `10:21:38Z` | 06:21 | pre-market |
| **DWDP 8-K 2.02 · 2019-04-18** | **`19:38:27Z`** | **15:38** | **intradía — 22 min antes del cierre** |

> `reportTime` de Alpha Vantage es **binario**. Un anuncio intradía no es ni `pre-market` ni `post-market`, y cualquiera de las dos etiquetas colocaría `first_tradable_at` en el día equivocado.

**(b) XBRL es nativamente *vintage*.** Cada observación lleva `filed` y `accn`, así que "lo que se sabía en T" se reconstruye filtrando `filed <= T`. Y la medición encontró por qué eso no es un lujo:

```
UTX · EarningsPerShareDiluted · end=2019-12-31
   val=1.32  form=10-K  filed=2020-02-06
   val=1.32  form=10-K  filed=2021-02-08
   val=6.41  form=10-K  filed=2022-02-11     <-- reexpresión
```

> **El EPS de 2019 vale 1,32 según lo presentado en 2020 y 6,41 según lo presentado en 2022.** Tomar "el último valor" para un evento de 2019 es **look-ahead puro**: nadie conocía 6,41 en 2019. Alpha Vantage devuelve **un solo valor por trimestre sin campo de vintage** —verificado en el esquema de las respuestas medidas: `fiscalDateEnding`, `reportedDate`, `reportedEPS`, `estimatedEPS`, `surprise`, `surprisePercentage`, `reportTime`— así que **no permite saber si lo que da es lo original o lo reexpresado**.

**(c) El CIK es permanente** y `formerNames` trae intervalos de validez.

**Limitaciones medidas de la SEC**, sin las cuales esto sería propaganda:
- **XBRL no llega tan atrás como el precio**: UTX arranca en 2007-12-31 y DWDP en 2015-12-31 (por ser entidad creada en 2016). El histórico de precios llega a 1970. **XBRL no cubre los años noventa.**
- **`company_tickers.json` es de supervivientes** (§2).
- **Rate limiting real** desde esta IP compartida: `www.sec.gov` devolvió *"Request Rate Threshold Exceeded"* en la primera tanda, y `data.sec.gov` rechaza el `User-Agent` vacío.
- **No tiene consenso ni expectativa.** No es su función.

## 6. Alpha Vantage

Queda definido como **`ENRICHMENT_SOURCE`**, nunca autoridad del universo:

| aporta | calidad temporal | riesgo de superviviencia |
|---|---|---|
| `estimatedEPS`, `reportTime`, `reportedEPS` (secundario) | **MEDIA** — día, etiqueta binaria, **sin vintage** | **ALTO Y DEMOSTRADO** |

Y con una advertencia que la auditoría anterior no había registrado: **`estimatedEPS` no declara de qué momento es la expectativa** ni cuándo se cerró el consenso. Sirve como enriquecimiento; no es una expectativa *point-in-time*.

**La consecuencia operativa, ya protegida por un test**: si una empresa no está en Alpha Vantage, `event existence ≠ false`.

## 7. Price coverage

Aquí es donde **la propuesta inicial era optimista**, y es lo que decide entre Camino A y Camino B.

```
DWDP    -> ERROR HTTPError: HTTP Error 404: Not Found
UTX     -> ERROR HTTPError: HTTP Error 404: Not Found
RTX     ->   930 sesiones · 2017-01-03 .. 2020-09-11
DD      ->   930 sesiones · 2017-01-03 .. 2020-09-11
IBM     ->   930 sesiones · 2017-01-03 .. 2020-09-11
^GSPC   ->   930 sesiones · 2017-01-03 .. 2020-09-11
```

**El símbolo histórico no existe**; el **sucesor** sí cubre la ventana entera. Pero la serie del sucesor **está rebaseada**:

```
DD · alrededor del 8-K de DWDP del 2019-04-18
   2019-04-17 close=104.14   adjclose=90.22
   2019-04-18 close=103.61   adjclose=89.76
   splits declarados por Yahoo en la ventana:
      2019-04-02  ratio 1487:1000    <- escisión de Dow
      2019-06-03  ratio 4725:10000   <- Corteva + contrasplit
```

> **DowDuPont cotizaba en torno a 53 dólares en abril de 2019. Yahoo reporta 103,61.** La diferencia no es un error: Yahoo **codifica las escisiones como splits** y reajusta hacia atrás toda la serie.

**Esto invalida un supuesto documentado del proyecto.** El bloque 4 del backfill decidió usar `close` "porque Yahoo ya ajusta por splits, y un split es un artefacto mecánico, no una variación real de mercado". **Una escisión no es un artefacto mecánico**: la empresa entrega parte de sí misma y la acción pasa a representar otra cosa. Ese supuesto se validó sobre IBM/NVDA/XOM, **ninguno de los cuales tuvo escisiones en la ventana**.

**Pero el daño es acotado, y conviene ser preciso en vez de alarmista:**

- Un event study usa **retornos**, no niveles. Un rebaseo **multiplicativo uniforme se cancela en un cociente**.
- Por tanto los retornos son **correctos** en cualquier ventana que **no atraviese** la acción corporativa, e **incorrectos** solo en las que la cruzan.
- Y Yahoo **declara** esos eventos en la respuesta, así que las ventanas contaminadas son **detectables**, exactamente igual que `_split_contiguous()` ya detecta huecos de calendario.

Ejemplo real: el retorno DD 2019-04-17 → 2019-04-18 es −0,51% y es **válido** (no hay acción corporativa entre esas fechas). En cambio una ventana de estimación de 20 sesiones que terminase el 2019-04-17 **cruzaría** la escisión del 2019-04-02 y estaría contaminada.

Por eso el estado es **`AMBIGUOUS`**, no `AVAILABLE` ni `UNAVAILABLE`: el dato existe y es utilizable **bajo una condición verificable**.

## 8. Benchmark coverage

```
SP500: 14291 sesiones · 1970-01-02 .. 2026-09-04
   2019-01-23 -> PRESENTE      2019-04-18 -> PRESENTE
   2019-05-02 -> PRESENTE      2020-04-06 -> PRESENTE
```

**`AVAILABLE` sin reservas, y estructuralmente inmune al problema.** `bm:sp500` es el **nivel publicado** del índice (D-25), no una cesta reconstruida a partir de constituyentes: no depende de que ninguna empresa siga existiendo. La decisión de D-25 —tomada por otras razones— resulta ser también la que protege del sesgo de superviviencia en el benchmark.

## 9. Event completeness

**Sí: un `earnings_release` se construye sin Alpha Vantage.**

```
SEC filing (8-K Item 2.02)  +  available_at (acceptanceDateTime)  +  actual (XBRL)
```

son suficientes para representar el evento. Verificado para **DWDP y UTX**, es decir, precisamente para las dos compañías que Alpha Vantage no conoce.

Implementado en `autoridad.estado_del_evento()` y protegido por tests:

```
=== EVENTO SIN EXPECTATIVA ===
  event_status             AVAILABLE
  expectation_status       UNAVAILABLE
  surprise_status          UNAVAILABLE
  perfiles_construibles    ['RAW_RETURN', 'ABNORMAL_RETURN',
                            'VOLUME_RELATIVE_TO_PRE_EVENT',
                            'VOLATILITY_RELATIVE_TO_PRE_EVENT',
                            'PEER_RELATIVE_RETURN']
  perfiles_bloqueados      ['SURPRISE_CONDITIONED']
```

## 10. Expectation / consensus gap

**`consensus_point_in_time` = `UNAVAILABLE`.** Ninguna fuente gratuita medida publica el consenso **con la fecha en que ese consenso estaba vigente**. El `estimatedEPS` de Alpha Vantage es una expectativa **sin sello temporal**: no se sabe si es la de la víspera del anuncio o una posterior.

Es la misma familia de problema que D-11 registró con ALFRED para las series macro (el dato existe; su *vintage* no), y se trata igual: **`UNAVAILABLE` declarado, nunca un número inventado**.

**El principio queda ejecutable**: la ausencia de consenso **no invalida el evento**; invalida **únicamente** los perfiles condicionados por sorpresa. Y hoy **ninguna de las cinco medidas del motor depende de la expectativa** — hay un test que lo comprueba, de modo que la rejilla actual sobrevive entera a `consensus = UNAVAILABLE`.

## 11. Universo congelado

`universe:v1:djia-2019` se **mantiene**, con la semántica cambiada como se pidió:

| antes | ahora |
|---|---|
| "activos consultables" | **"empresas que deben auditarse"** |

Registrado en el bloque `semantica` de `universo_v1.json` y fijado por un test. El cambio no es cosmético: bajo la semántica antigua, DWDP y UTX habrían sido **bajas del universo** por no ser consultables. Bajo la nueva son **dos filas con `sec = AVAILABLE` y `expectation = UNAVAILABLE`** — que es la información verdadera.

## 12. Matriz de cobertura

`python3 engine/events/autoridad.py` (filas con alguna celda medida; el resto del universo es `NOT_MEASURED` salvo `benchmark`/`consensus`):

```
asset  sec           event         actual        expectation   consensus     reportTime    price         benchmark
AAPL   NOT_MEASURED  NOT_MEASURED  NOT_MEASURED  AVAILABLE     UNAVAILABLE   AVAILABLE     NOT_MEASURED  AVAILABLE
CAT    NOT_MEASURED  NOT_MEASURED  NOT_MEASURED  AVAILABLE     UNAVAILABLE   AVAILABLE     NOT_MEASURED  AVAILABLE
DWDP   AVAILABLE     AVAILABLE     AVAILABLE     UNAVAILABLE   UNAVAILABLE   AVAILABLE     AMBIGUOUS     AVAILABLE
IBM    NOT_MEASURED  NOT_MEASURED  NOT_MEASURED  AVAILABLE     UNAVAILABLE   AVAILABLE     AVAILABLE     AVAILABLE
MSFT   NOT_MEASURED  NOT_MEASURED  NOT_MEASURED  AVAILABLE     UNAVAILABLE   AVAILABLE     NOT_MEASURED  AVAILABLE
UTX    AVAILABLE     AVAILABLE     AVAILABLE     UNAVAILABLE   UNAVAILABLE   AVAILABLE     AMBIGUOUS     AVAILABLE
VZ     NOT_MEASURED  NOT_MEASURED  NOT_MEASURED  AVAILABLE     UNAVAILABLE   AVAILABLE     NOT_MEASURED  AVAILABLE

conteo: {'AVAILABLE': 50, 'UNAVAILABLE': 33, 'NOT_MEASURED': 163, 'AMBIGUOUS': 2}
```

**163 de 248 celdas siguen `NOT_MEASURED`, y ninguna se ha rellenado.** Un test comprueba que `NOT_MEASURED` domina y otro que `AXP.sec` es `NOT_MEASURED` y **no** `UNAVAILABLE` — el error concreto que esta matriz existe para impedir.

## 13. Limitaciones

1. **SEC medida sobre 2 de 31 activos.** DWDP y UTX se eligieron porque son los casos difíciles ya demostrados. Que EDGAR funcione para ellos **no prueba** que la profundidad XBRL sea homogénea en los 29 restantes.
2. **XBRL no llega a los años noventa** (UTX 2007, DWDP 2015). Los 122 trimestres de precio desde 1996 **no** tienen contrapartida XBRL en toda su extensión.
3. **El puente ticker→CIK no es autoritativo** (§2). Sin resolverlo, un universo histórico se construye a mano.
4. **El rebaseo por escisiones se midió en un caso** (DD). No se ha cuantificado en cuántos activos del universo ocurre.
5. **No se ha verificado que el 8-K Item 2.02 del 2019-04-18 de DWDP sea el anuncio trimestral** y no otra comunicación de resultados; para la conclusión sobre `reportTime` binario da igual, pero no debe leerse como "los resultados del Q1".
6. **Rate limiting de la SEC** desde esta IP: cualquier ingesta masiva tendrá que espaciar peticiones.
7. **No se midió la latencia entre el 8-K y el 10-Q**, que es la que decidiría cuál de los dos es el evento operativo.

## 14. Decisión recomendada

> **Camino A, con una condición.**

Los tres componentes que definen el evento —existencia, `available_at`, resultado real— son **`AVAILABLE` desde la SEC incluso para deslistados**, y el benchmark es `AVAILABLE` sin reservas. La cadena `SEC → eventos históricos → precios → S&P 500 → reacción anormal` es viable, y `surprise = optional` es sostenible porque ninguna medida actual depende de la expectativa.

**La condición** es el precio, que quedó `AMBIGUOUS` y no `AVAILABLE`: hay que **tratar las acciones corporativas como huecos**, igual que `_split_contiguous()` trata los huecos de calendario, y **excluir toda ventana que cruce una**. Yahoo declara los eventos, así que es detectable sin fuente nueva.

**No se justifica todavía pagar un proveedor.** Lo que sí queda justificado, y es distinto, es un **mapa ticker-histórico → CIK curado a mano** para los 31 activos del universo: es el único componente `AMBIGUOUS` estructural, y a esta escala se resuelve con trabajo, no con dinero.

**Orden recomendado, sin ejecutar:**
1. Mapa `ticker histórico → CIK` para los 31, con corroboración vía `formerNames`.
2. Medir profundidad XBRL y 8-K Item 2.02 en los 31 (cierra la limitación 1).
3. Detector de acciones corporativas sobre las series de precio, como extensión de `_split_contiguous()`.
4. Solo entonces, ingesta.

## 15. Qué desbloquea el siguiente backfill

| se desbloquea | por qué |
|---|---|
| **Eventos de compañías deslistadas** | la existencia y el resultado vienen de la SEC, que no las pierde |
| **`available_at` como instante** | `acceptanceDateTime` sustituye a `PROVEEDOR_DIA`; pre/intra/post se **deriva** |
| **Vintage real del resultado** | `filed <= as_of` da lo que se sabía entonces — cierra un look-ahead que Alpha Vantage no permite ni detectar |
| **`RAW_RETURN`, `ABNORMAL_RETURN`, volumen, volatilidad** | ninguna depende de la expectativa |
| **Un universo sin sesgo de superviviencia** | por CIK, no por ticker |

**Sigue bloqueado**: todo perfil condicionado por sorpresa (`consensus = UNAVAILABLE`), los años previos a la cobertura XBRL, y los niveles de precio —no los retornos— de la era deslistada.

---

## Qué cambió — ficheros

Cambio de código **mínimo y deliberado**: solo la fuente declarativa y la invariante que el usuario pidió preservar más allá de este backfill.

| fichero | estado | qué |
|---|---|---|
| `engine/events/autoridad_datos.json` | **nuevo** | autoridad por componente, matriz proveedor × rol × calidad temporal × superviviencia, matriz de cobertura medida |
| `engine/events/autoridad.py` | **nuevo** | estados, roles, `existencia_de_evento()`, `estado_del_evento()`, `matriz_cobertura()`, `incoherencias()` |
| `tests/test_autoridad_datos.py` | **nuevo** | 26 tests |
| `engine/events/universo_v1.json` | modificado | bloque `semantica`: "empresas que deben auditarse" (§11) |
| `tests/test_poblacion_universo.py` | modificado | +1 test que fija esa semántica |

**Sin cambios en `data/` ni en `knowledge/`** (`git status` vacío). Ningún motor existente tocado.

## Supuestos invalidados

1. **"Yahoo `close` solo está ajustado por splits, que son artefactos mecánicos."** (Bloque 4 del backfill.) Yahoo codifica **escisiones** como splits, y una escisión no es un artefacto mecánico. El supuesto se validó sobre tres activos sin escisiones.
2. **"La SEC no tiene sesgo de superviviencia."** Lo tiene, si se entra por ticker: `company_tickers.json` es de supervivientes. Solo el CIK es inmune.
3. **"`reportTime` pre/post describe cuándo se publicó."** Es binario y hay anuncios **intradía** (DWDP 2019-04-18, 15:38 ET).
4. **"El resultado real de un trimestre es un número."** Es una **serie de vintages**: el EPS 2019 de UTX vale 1,32 o 6,41 según cuándo se pregunte.
5. **"SEC EDGAR podría exigir enviar un correo de contacto."** No: un `User-Agent` descriptivo basta.

## Deuda abierta

- **Puente ticker→CIK sin fuente autoritativa** — `autoridad_datos.json`, estado `AMBIGUOUS`.
- **Cobertura SEC medida en 2 de 31** y XBRL sin llegar a los noventa.
- **Rebaseo por escisiones no cuantificado** en el resto del universo.
- **`autoridad.py` fuera de `qa.py`** — mismo patrón que D-24 y que `universo.py`.
- **Consenso PIT sin fuente** — `UNAVAILABLE` declarado.
