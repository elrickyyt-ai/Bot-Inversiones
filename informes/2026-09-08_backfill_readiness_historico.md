# Backfill readiness del universo histórico — qué componente impide ampliar con rigor

**Fecha**: 2026-09-08 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Base**: `f6a76d8`
**Pregunta**: de las 31 empresas del universo histórico, ¿cuántas podemos reconstruir *point-in-time* como entidades, eventos, precios e instrumentos, y cuál es el componente que impide ampliar con rigor?

**Verificación**:

```
python3 -m unittest discover -s tests            708 → 723 tests · OK
python3 engine/contract/qa.py --require-parquet  QA CORE: PASS · QA PARQUET: PASS · STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   PASS (26 · 51 · 11)
git status --short data/ knowledge/              vacío
python3 engine/events/readiness.py               cobertura, forma de las ausencias y readiness
```

**Los 31 activos medidos en vivo** el 2026-09-08 contra `data.sec.gov`, `www.sec.gov` y la fuente de precios. **Alpha Vantage no se usó para decidir qué activos existen** (D-36) — y el resultado demuestra por qué no hacía falta.

---

## Respuesta al criterio de parada

> **`BACKFILL_READY = false`.**
>
> **28 de 31** empresas se reconstruyen completas como **entidad + evento + resultado + precio + benchmark**. Las 3 que faltan —**DWDP, UTX, WBA**— son reconstruibles como entidad, evento y resultado, pero **no como precio**.
>
> **El componente que impide ampliar no es la cobertura: es la identidad del instrumento.** `historical_ticker` está al **0%** y `corporate_actions` al **0%**: ninguno tiene fuente determinista.

**Escenario C**, con una precisión importante: la identidad **de entidad** está al 100%. Lo que está al 0% es la capa **ticker → instrumento**. El Instrument Master pasa a ser **requisito previo**, no mejora futura.

## 1. Universo

`universe:v1:djia-2019` — 31 activos congelados a 2019-01-01, semántica *"empresas que deben auditarse"* (D-32/D-40). Los 31 se midieron; ninguno se dio de baja por falta de cobertura.

## 2. Metodología

Un barrido por activo: `submissions` (identidad, `formerNames`, 8-K Item 2.02, `acceptanceDateTime`), `companyconcept`/`companyfacts` (resultado real), y la fuente de precios (serie + factores declarados). Cuatro estados por celda, **`NOT_MEASURED` nunca se rellena como `UNAVAILABLE`**.

**Dos correcciones que la propia medición obligó a hacer:**

1. **El resultado real no vive solo en `EarningsPerShareDiluted`.** KO tiene 4 observaciones de EPS (2008-2009) y Visa **ningún concepto EPS estándar** — solo `BusinessAcquisitionProFormaEarningsPerShareDiluted`. Ambas sí tienen `NetIncomeLoss` (233 y 227). **Medir solo EPS habría dado 29/31 y eliminado silenciosamente a dos.**
2. **Los dos endpoints de la SEC se contradicen para KO.** `companyconcept/NetIncomeLoss` devuelve `{'USD': 0}`; `companyfacts` devuelve **233 observaciones** — mismo CIK, concepto y unidad. Verificado que **no es sistemático**: IBM (123) y Apple (338) coinciden exactamente en ambos. Se usó el valor de `companyfacts`, que es el que tiene los datos.

## 3. Autoridad por componente

Sin cambios respecto a D-37: SEC manda sobre entidad, evento, `available_at` y resultado; Alpha Vantage **enriquece**; el benchmark es `bm:sp500`. Lo que esta auditoría añade es **el número sobre los 31**.

## 4. Cobertura

```
  componente                  AVAIL   UNAV   NOTM   AMBI   coverage
  historical_identity            31      0      0      0     100.0%
  CIK                            29      0      0      2      93.5%
  historical_ticker               0      0      0     31       0.0%
  SEC_event                      31      0      0      0     100.0%
  actual_financials              31      0      0      0     100.0%
  AV_enrichment                   7      2     22      0      22.6%
  expectation                     7      2     22      0      22.6%
  price                          28      3      0      0      90.3%
  corporate_actions               0      3      0     28       0.0%
  successor_mapping              31      0      0      0     100.0%
  benchmark                      31      0      0      0     100.0%
  event_study_eligibility        12      3      0     16      38.7%
```

**Lo que está resuelto**: identidad de entidad, evento, resultado real, sucesión y benchmark — **100% los cinco**. Los 31 activos tienen `acceptanceDateTime` completo y 8-K Item 2.02.

**Lo que no**: el ticker histórico (0%), la clasificación de acciones corporativas (0%) y el precio de los deslistados.

**`AV_enrichment` al 22,6% no es un problema**: 22 `NOT_MEASURED` y 2 `UNAVAILABLE`, y por D-38 su ausencia no elimina ningún evento. Un test comprueba que no entra en el cálculo de readiness.

## 5. Survivorship

**El hallazgo central de esta auditoría**, y no se buscaba:

```
fuera del directorio actual : ['DWDP', 'UTX', 'WBA']
sin precio                  : ['DWDP', 'UTX', 'WBA']
¿coinciden?                 : True
```

> **Las tres ausencias de precio son exactamente los tres activos que el directorio de tickers ya no lista.** La cobertura que falta **no es aleatoria: tiene forma de sesgo de superviviencia.**

Un 90,3% leído como "casi completo" llevaría a backfillear 28 supervivientes y perder precisamente los 3 casos que hacen la muestra insesgada. Hay un test que bloquea el backfill **solo por esa coincidencia**, aunque todos los umbrales se cumplieran.

**Y apareció un caso nuevo que no estaba en el diseño**: **WBA** (Walgreens Boots Alliance) **no está en `company_tickers.json`**. Su CIK `0001618921` se recuperó por EDGAR full-text — 77 de 1123 documentos — con **211 observaciones de `NetIncomeLoss`** y sus 8-K. Es el mismo patrón que DWDP y UTX, **encontrado por el barrido y no elegido por mí**, que es lo que el encargo pedía (§4).

De los tres, dos son escisión/fusión (DWDP, UTX) y uno es **adquisición/salida a privado** (WBA): tres formas distintas de dejar de cotizar, las tres invisibles para el directorio actual.

## 6. Identity

El resolutor distingue los cinco casos exigidos, y `MOB` sigue como test negativo:

```
XOM  @ 2019-04-26 -> 0000034088  EXXON MOBIL CORP
XOM  @ 2026-08-15 -> 0002115436  ExxonMobil Holdings Corp
MOB  @ 1995-06-01 -> AMBIGUOUS: ningún intervalo declarado cubre esa fecha
MOB  @ 2024-01-05 -> Mobilicom Limited
```

**Un ticker actual con datos no demuestra identidad histórica.**

## 7. CIK

**93,5%** — 29 inequívocos y **2 `AMBIGUOUS`**:

- **XOM**: dos CIK (`0000034088` histórico, `0002115436` desde la reorganización del 2026-07-01). Ambos activos: el histórico presentó un 10-Q el 2026-08-03.
- **WBA**: el CIK existe pero se recuperó por **heurística de texto**, no por registro.

## 8. Ticker

**0%.** Los 31 en `AMBIGUOUS`. No hay fuente determinista para saber qué ticker designaba a un instrumento en una fecha pasada (D-40): `companyfacts` solo sirve conceptos numéricos, la portada inline-XBRL solo lleva `dei:TradingSymbol` desde ~2020, y el directorio actual es de supervivientes.

**Es el cuello de botella, y no se resuelve con más cobertura**: se resuelve declarando el mapa a mano para 31 activos.

## 9. Price continuity

`price` al **90,3%**, y el 9,7% que falta es el descrito en §5. Para los 28 con serie, la continuidad **no está garantizada**: `corporate_actions` está al **0% `AVAILABLE`** y **28 en `AMBIGUOUS`**, porque la fuente **señala** los factores y **no los clasifica** (D-44).

`event_study_eligibility` al **38,7%**: 12 activos sin ningún factor no redondo, **16 con al menos uno** —indicio de escisión, nunca prueba— y 3 sin precio.

Los tres tipos de continuidad siguen sin coincidir (D-41): en fusión y escisión el **retorno sobrevive y la economía no**.

## 10. Corporate actions

No se ha construido el Instrument Master. Solo se midió, y **no se extrapoló** la tasa de los 52 eventos al universo: las acciones de 26 de los 31 activos siguen sin clasificar.

Lo medido en la auditoría anterior sobre los 52 eventos, sin cambios: `0_1d` 0 · `2_5d` 0 · `2_20d` 0 · `2_60d` **2 marcadas, 0 ambiguas** — y ese 0% es del **muestreo**, no de la limpieza (D-43).

## 11. Benchmark

**100%.** `bm:sp500` cubre 1970-01-02 → 2026-09-04 y es **estructuralmente inmune**: es un nivel publicado, no una cesta reconstruida (D-25). Es el único componente que no se degrada con el sesgo de superviviencia.

## 12. Event coverage

**100%.** Los 31 tienen 8-K Item 2.02 y `acceptanceDateTime` completo — **incluidos DWDP, UTX y WBA**, que Alpha Vantage no conoce. La población de eventos se construye desde la fuente autoritativa y **no depende del enriquecimiento**.

## 13. Expectation coverage

**22,6%**, y **medido por separado** como se pidió (§8), no como una bandera única:

| componente | cobertura |
|---|---|
| evento histórico (8-K 2.02) | **100%** |
| resultado real (XBRL) | **100%** |
| `estimatedEPS` | 22,6% (7 medidos · 2 `UNAVAILABLE` · 22 `NOT_MEASURED`) |
| `reportTime` | 22,6%, y **derivable de `acceptanceDateTime` al 100%** |

**`event = AVAILABLE` con `expectation = UNAVAILABLE` es un estado real y soportado**: es exactamente el de DWDP y UTX.

## 14. Overlap

Sin cambios (D-30): `overlap_event_count` 0 · 0 · 0 · **3** sobre los 52 eventos; tasa máxima 0,061 a `2_60d`. Volver a medirlo sobre población contigua es una de las cosas que el backfill desbloquea, **no un requisito previo**.

## 15. Causal traversal

Se evaluó el cambio de lista negra a lista blanca **sin tocar P5A**, midiendo sobre caminos reales (`NVDA`, `IBM`, `XOM`, `org:nvidia`, profundidad 3).

**Variante A — lista blanca estricta (solo aristas `CAUSAL`)**: 284 → 102 caminos. **Destruye caminos legítimos**: sin `ISSUED_BY` no se llega del instrumento a la entidad.

**Variante B — `CAUSAL` + `ISSUED_BY` como puente**: 284 → 118. **También destruye legítimos**, y de forma grave:

```
  x84  EXPOSED_TO|EXPOSED_TO|LISTED_ON      <- dos aristas causales, eliminado
  x24  ISSUED_BY|DOMICILED_IN|EXPOSED_TO    <- termina en causal, eliminado
  x3   EXPOSED_TO|DOMICILED_IN|SUPPLIES     <- causal, referencia, causal
```

**Variante C — no restringir el recorrido; exigir que el camino emitido contenga ≥1 arista `CAUSAL`**:

```
origen              actual        C  eliminados
sec:NVDA.NASDAQ         95       88          7
sec:IBM.NYSE            95       86          9
sec:XOM.NYSE            94       86          8
org:nvidia              72       59         13
TOTAL                  356      319         37  (10,4%)

¿Alguno de los eliminados contiene una arista causal?  False
```

**Criterios del encargo:**

| criterio | resultado |
|---|---|
| equivalencia de caminos causales legítimos | ✅ **demostrado** — 0 caminos con arista causal eliminados |
| eliminación de caminos puramente estructurales | ✅ **demostrado** — 37 de 356, todos cadenas de identidad/referencia |
| **regresión cero en los fixtures actuales** | ❌ **NO se cumple** |

Los fixtures **sintéticos** sobreviven al 100% (`T5_ciclo` 4/4, `T6_contradiccion` 1/1, solo usan `SUPPLIES`). Pero los casos sobre el **Knowledge real** pierden caminos —NVDA prof2 **27→23**, BTC prof1 **4→2**, BTC prof2 **33→21**— y `tests/test_caminos.py` afirma sobre esos conteos.

> **Por tanto: no se cambia P5A.** Se documenta la propuesta con su medición. La pérdida de conteos es probablemente *correcta* (son caminos vacíos), pero eso convierte el cambio en una revisión de los tests de una fase cerrada, no en un no-op — y el criterio pedido era regresión cero.

**Recomendación**: hacerlo como refactor propio (`P5A hardening`), **fuera del backfill**, tal y como sugiere el roadmap.

## 16. Readiness

```
BACKFILL_READY: False
universo minimo efectivo: 28 de 31
 - price cubre 90.3%, por debajo de 95%
 - las ausencias de precio coinciden exactamente con los activos deslistados:
   ampliar ahora produciria una cohorte de supervivientes
 - historical_ticker cubre 0.0%: sin fuente determinista, la identidad del
   instrumento no es reconstruible con rigor
 - corporate_actions cubre 0.0%: idem
```

**No se decide con un porcentaje global**, y hay un test que lo fija: el universo mínimo efectivo es **28 de 31 (90,3%)** —alto— y aun así **no está listo**. Si la decisión fuese un umbral, saldría que sí.

## 17. Bloqueos

| bloqueo | naturaleza | cómo se resuelve |
|---|---|---|
| **`historical_ticker` 0%** | estructural | mapa ticker→CIK **curado a mano** para 31 activos, corroborado con `formerNames`. No necesita proveedor |
| **`corporate_actions` 0%** | estructural | clasificar desde el 8-K, activo a activo. **26 de 31 sin medir** |
| **Precio de 3 deslistados** | de fuente | serie del sucesor con mapa explícito, o fuente con deslistados |
| **`CIK` ambiguo en 2** | acotado | intervalos declarados; ya resuelto para XOM |
| **Traversal en lista negra** | de diseño | `P5A hardening`, fuera del backfill |

## 18. Propuesta de siguiente implementación

**El Instrument Master pasa a requisito previo.** Orden recomendado, ninguno ejecutado:

1. **Mapa `ticker histórico → CIK` para los 31**, con intervalos y corroboración por `formerNames`. Es el 0% que bloquea, y es trabajo, no dinero.
2. **Clasificar las acciones corporativas de los 31 desde el 8-K** — hoy 5 de 31.
3. **Resolver el precio de DWDP, UTX y WBA** vía sucesor con mapa explícito. **Sin esto, cualquier ampliación es una cohorte de supervivientes.**
4. **Declarar los 31 en el Knowledge Model** (`security` + `organization` + `ISSUED_BY` fechado, D-42) y añadir `SUCCESSOR_OF` **no causal**.
5. **Entonces sí**, ampliar población y volver a medir independencia y solape.
6. **En paralelo y aparte**: `P5A hardening` con la variante C.

---

## Qué cambió — ficheros

| fichero | estado | qué |
|---|---|---|
| `engine/events/readiness_universo.json` | **nuevo** | medición de los 31 y matriz de cobertura |
| `engine/events/readiness.py` | **nuevo** | cobertura, forma de las ausencias, cuello de botella, `backfill_ready()` |
| `tests/test_backfill_readiness.py` | **nuevo** | 15 tests |

**Sin cambios en `data/`, `knowledge/` ni P5A.**

## Supuestos invalidados

1. **"El resultado real es `EarningsPerShareDiluted`."** KO tiene 4 observaciones y Visa ninguna. Medir solo EPS habría dado 29/31 y eliminado a dos silenciosamente.
2. **"Los endpoints de la SEC son consistentes entre sí."** Para KO, `companyconcept` da 0 y `companyfacts` 233. No es sistemático — IBM y Apple coinciden.
3. **"Los casos de superviviencia son DWDP y UTX."** El barrido encontró un tercero, **WBA**, con una causa distinta (salida a privado).
4. **"Una cobertura del 90% en precios es aceptable."** No cuando el 10% ausente son exactamente los deslistados.
5. **"La lista blanca causal es una mejora obvia."** Las dos variantes intuitivas destruyen 58% de los caminos, incluidos legítimos.

## Deuda abierta

- **`historical_ticker` sin fuente determinista** en los 31.
- **Acciones corporativas sin clasificar en 26 de 31.**
- **Precio de DWDP, UTX y WBA** sin resolver.
- **`companyconcept` da falsos negativos** para al menos un activo; el pipeline futuro debería usar `companyfacts` o comparar ambos.
- **P5A en lista negra**, con la variante C medida y sin aplicar.
- **`readiness.py` fuera de `qa.py`** — mismo patrón que D-24.
