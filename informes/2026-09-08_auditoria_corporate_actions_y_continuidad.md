# Auditoría de cobertura de Corporate Actions y continuidad económica

**Fecha**: 2026-09-08 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Base**: `1dad962` · **Commit**: `018e520`
**Pregunta**: ¿cuántos eventos de nuestro universo tienen dentro de sus ventanas una transformación que pueda romper la continuidad económica del instrumento?

**Verificación**:

```
python3 -m unittest discover -s tests            684 → 708 tests · OK
python3 engine/contract/qa.py --require-parquet  QA CORE: PASS · QA PARQUET: PASS · STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   PASS (26 · 51 · 11)
git status --short data/ knowledge/              vacío
python3 engine/events/cobertura_acciones.py      la medición completa
```

**Ni un perfil recalculado, ni una fila de `data/` tocada.**

---

## La respuesta, y por qué no se puede leer sola

```
=== COBERTURA DE ACCIONES CORPORATIVAS · 52 eventos ===
  horiz    n_events     clean  con_accion   ambiguous
  0_1d           52        52           0           0  (0.0%)
  2_5d           52        52           0           0  (0.0%)
  2_20d          52        52           0           0  (0.0%)
  2_60d          52        50           2           0  (0.0%)
```

**Cero eventos ambiguos.** Y ese número **no significa que la cohorte esté limpia**:

> La escisión de Kyndryl (**2021-11-04**) cae exactamente en un **hueco de muestreo** de IBM: sus eventos saltan de **2021-01-22** a **2022-01-25**. El evento real de resultados del Q3 2021 —el 8-K Item 2.02 del **2021-10-20**, que aparece en los filings de IBM— **no está en la cohorte**.

El 0% mide la **dispersión del muestreo**, no la limpieza de los datos. Un test fija justamente esto para que nadie lea el número al revés.

## 1. Casos

| caso | tipo dominante | verificado contra SEC | en la cohorte |
|---|---|---|---|
| **IBM / Kyndryl** | `SPINOFF` 2021-11-04 | **sí** — 8-K con Item 2.01 | sí (3 activos) |
| **XOM / Mobil** | `MERGER` 1999-11-30 | **sí** — `formerNames` | sí |
| **XOM / reorg 2026** | `REORGANIZATION` 2026-07-01 | **sí** — `8-K12B` + `25-NSE` | sí |
| **DWDP** | `SPINOFF` ×2 (2019) | no — indicio de ratio | no |
| **UTX** | `SPINOFF` + `MERGER` (2020-04-03) | parcial — `formerNames` para la fusión | no |
| **MOB** | `UNKNOWN` — reutilización de ticker | no aplica | no |
| **NVDA** (control) | solo `SPLIT` | no — ratios redondos | sí |

**12 acciones declaradas, 4 verificadas contra la SEC.** Las 8 restantes se marcan explícitamente como **no verificadas** y no se ascienden.

## 2. Fuentes

**La clasificación no puede venir del proveedor de precios.** El factor es una **señal**; la autoridad es el filing.

Verificación de la escisión que importa:

```
8-K  2021-11-04  items=2.01,7.01,9.01  acc=0001558370-21-014643
```

**Item 2.01 = "Completion of Acquisition or Disposition of Assets"**, en la **misma fecha** que el factor `1046:1000` de Yahoo. La clasificación de IBM/Kyndryl deja de ser un indicio.

Y en la misma ventana aparece el evento de resultados:

```
8-K  2021-10-20  items=2.02,7.01,9.01
```

## 3. Ticker reuse

```
MOB  @ 1995-06-01 -> AMBIGUOUS: ningún intervalo declarado cubre esa fecha
MOB  @ 2024-01-05 -> Mobilicom Limited
```

**El caso queda como test permanente.** Un ticker que existe hoy **no demuestra identidad histórica sin una relación temporal válida**. `resolver_identidad()` exige fecha y devuelve `AMBIGUOUS` —nunca el candidato más probable— cuando ningún intervalo la cubre.

Se clasificó como **`UNKNOWN`, no `SUCCESSION`**: no es una transformación *del* instrumento histórico, es *otro* instrumento reutilizando la etiqueta. Llamarlo sucesión sería exactamente el falso positivo que el registro existe para impedir.

## 4. CIK migration

**Verificado que la resolución depende del intervalo temporal** (§7 del encargo):

```
XOM  @ 2019-04-26 -> 0000034088  EXXON MOBIL CORP
XOM  @ 2026-08-15 -> 0002115436  ExxonMobil Holdings Corp
XON  @ 1998-01-01 -> 0000034088  EXXON CORP
```

Base documental: `8-K12B` del **2026-07-01** (aceptación `16:36:49Z`, items 1.01, 2.01, 2.03, 3.03, 5.02, 5.03, 9.01) bajo el CIK nuevo, y un **`25-NSE`** (retirada de cotización) el 2026-07-02 bajo el antiguo. **Los dos CIK siguen activos**: el histórico presentó un 10-Q el 2026-08-03.

> Sin resolución por fecha, `XOM` histórico apuntaría al CIK nuevo —29 filings desde julio— y el sistema perdería los 1000 del CIK antiguo. Un test lo fija.

## 5. Mergers

**No dejan rastro en el precio.** XOM declara cinco splits y **ninguno en 1999**, el año de la fusión con Mobil. La única evidencia es la transición de `formerNames`: `EXXON CORP` termina el **1999-11-30**.

Es **peor que una clasificación errónea**: en la escisión hay un factor raro que *se puede detectar*; en la fusión **no hay nada que detectar**. Cualquier detector basado en la serie de precios encontrará las escisiones y **se perderá todas las fusiones**.

## 6. Spin-offs

Se declaran, pero **mal clasificadas** — como splits, con ratios no redondos:

| activo | fecha | factor declarado | qué era |
|---|---|---|---|
| IBM | 2021-11-04 | `1046:1000` | escisión de Kyndryl |
| DD (ex-DWDP) | 2019-04-02 | `1487:1000` | escisión de Dow |
| DD (ex-DWDP) | 2019-06-03 | `4725:10000` | Corteva + contrasplit |
| RTX (ex-UTX) | 2020-04-03 | `15890:10000` | Otis y Carrier |

El caso de **UTX** es el más instructivo: el 2020-04-03 concurren una **escisión doble** y una **fusión**, y la fuente declara **un solo factor**. Dos transformaciones económicas opuestas comprimidas en un número.

## 7. Reorganizaciones

`REORGANIZATION` se clasifica como **no cambia el instrumento económico**: en un holdco reorg el accionista conserva la misma exposición. Lo que rompe es el **mapa ticker → CIK**, no el precio.

Por eso el evento de XOM del 2026-05-01 sale **`MARCADA`** y no `AMBIGUA`: la reorganización del 2026-07-01 cae en su ventana 2_60d, y es una discontinuidad **de identidad**, no de continuidad económica. Son cosas distintas y la clasificación lo refleja.

## 8. Continuidad

Los tres tipos **no coinciden**, y ésa es la razón de separarlos:

| tipo de acción | `PRICE_CONTINUITY` | `RETURN_CONTINUITY` | `ECONOMIC_INSTRUMENT_CONTINUITY` |
|---|---|---|---|
| `SPLIT` · `TICKER_CHANGE` · `REORGANIZATION` | ❌ | ✅ | ✅ |
| **`MERGER` · `SPINOFF`** | ❌ | ✅ | **❌** |
| `TICKER_REUSE` · `UNKNOWN` | ❌ | ❌ | ❌ |

**La fila del medio es todo el problema**: tras una escisión el cociente entre dos precios ajustados es **aritméticamente correcto** y compara **dos empresas distintas**. Un ajuste multiplicativo restaura el retorno y **no** restaura la economía.

## 9. Impacto en event study

```
=== EVENTOS AFECTADOS ===
  IBM   1999-04-21  ->  2_60d: MARCADA (SPLIT)
  XOM   2026-05-01  ->  2_60d: MARCADA (REORGANIZATION)
```

**Ninguno ambiguo, los dos ajustables.** La regla aplicada no es *"excluir si hay acción corporativa"* —eso habría tirado estos dos, que son válidos— sino **si cambia el instrumento económico**.

**Proyección sobre una serie trimestral contigua** (método declarado: un evento queda contaminado si la acción cae en `[s1−20, s1+W]`, franja de `20+W+1` fechas de evento, con eventos cada ~63,5 sesiones — D-30):

| horizonte | contaminados | ambiguos | % contaminado | % ambiguo |
|---|---|---|---|---|
| `0_1d` | 2,4 | 0,7 | 0,4% | 0,1% |
| `2_5d` | 2,9 | 0,8 | 0,5% | 0,1% |
| `2_20d` | 4,5 | 1,3 | 0,8% | 0,2% |
| `2_60d` | **8,9** | **2,6** | **1,6%** | **0,5%** |

sobre ~560 eventos teóricos de los tres activos.

**La contaminación es baja *para estos tres activos*, y eso no se puede extrapolar.** IBM tuvo 1 escisión en 27 años; **DWDP tuvo 2 en 3 años y UTX 2 el mismo día**. La varianza entre compañías es enorme, y las acciones corporativas de **26 de los 31 activos del universo son `NOT_MEASURED`**. La tasa real del universo **no es baja: es desconocida**.

## 10. Impacto en historical profiles

**No se ha recalculado ninguna estadística.** Lo que cambia es lo que se sabe:

- `descriptive_status` y `predictive_status` **sin cambios** (12 `VALID` de 20, `NOT_EVALUATED` en las 20).
- Aparece una fuente de exclusión que `poblacion()` **no conoce**: acciones que cambian el instrumento.
- Con la cohorte actual el efecto sería **2 observaciones marcadas de 52** y **ninguna excluida** — si la política se implantara hoy, **ningún perfil cambiaría de valor**.
- Eso vale **solo** para esta cohorte dispersa. En la cohorte contigua de ~356 eventos habría exclusiones reales.

## 11. Matriz por horizonte

Por activo (`limpia / marcada / ambigua`):

| activo | `0_1d` | `2_5d` | `2_20d` | `2_60d` |
|---|---|---|---|---|
| IBM | 16 / 0 / 0 | 16 / 0 / 0 | 16 / 0 / 0 | **15 / 1 / 0** |
| NVDA | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 |
| XOM | 18 / 0 / 0 | 18 / 0 / 0 | 18 / 0 / 0 | **17 / 1 / 0** |

**NVDA queda limpio en los cuatro horizontes** — es el control, y se comporta como tal. La contaminación **crece monótonamente con el horizonte**, con un test que lo comprueba: si se invirtiera, habría un error de ventanas.

## 12. Política propuesta

**Propuesta, no implantada.** Por tipo de acción:

| tipo | política | justificación |
|---|---|---|
| `SPLIT` · `TICKER_CHANGE` · `NAME_CHANGE` | **`FLAG`** | el ajuste se cancela en el cociente; excluir tiraría observaciones válidas |
| `REORGANIZATION` · `SUCCESSION` | **`FLAG`** | rompe la identidad, no la exposición económica |
| **`MERGER` · `SPINOFF`** | **`EXCLUDE`** | `RETURN` sobrevive y `ECONOMIC` no: el número saldría y compararía dos empresas |
| `UNKNOWN` | **`AMBIGUOUS`** | no se sabe qué pasó; un falso positivo es peor que una ausencia |

Por medida, la propuesta **no es uniforme**:

- **`RAW_RETURN`** y **`ABNORMAL_RETURN`**: `EXCLUDE` ante cambio de instrumento. El benchmark no arregla nada — descontar el S&P 500 de un retorno que compara dos empresas distintas sigue comparando dos empresas distintas.
- **`PEER_RELATIVE_RETURN`**: `EXCLUDE`, y además **el peer también** puede tener su propia acción corporativa. Hoy está bloqueada por otra razón (`INSUFFICIENT_COMPARABILITY`), así que no urge.
- **`VOLUME_RELATIVE_TO_PRE_EVENT`**: `AMBIGUOUS` y no `EXCLUDE`. Una escisión cambia el número de acciones en circulación, así que el cociente de volúmenes compara dos bases distintas — pero el efecto **no se ha medido** y no debe suponerse.

**`TRUNCATE`** se evaluó y **se descarta como opción general**: acortar la ventana hasta la acción cambia la longitud del horizonte, y comparar un `2_60d` truncado a 11 sesiones con otro completo mezcla dos medidas distintas. Solo tendría sentido con un horizonte declarado variable, que no existe.

## 13. Tests necesarios

**24 nuevos** en `tests/test_corporate_actions.py` (684 → 708).

*Registro* — todo tipo declarado es conocido; **la clasificación no se deduce del factor de precio**; la escisión de Kyndryl está verificada contra el 8-K Item 2.01; la fusión de XOM no tiene señal de precio; **el ticker reutilizado es `UNKNOWN` y no `SUCCESSION`**.

*Partición* — split no cambia el instrumento y escisión sí; la política cubre todos los tipos; lo que cambia el instrumento se propone `EXCLUDE`; **lo ajustable se propone `FLAG`, no `EXCLUDE`**.

*Medición* — los 52 eventos en los cuatro horizontes; los conteos cuadran; **la contaminación crece con el horizonte**; y el test que impide la lectura ingenua: **`test_ningun_evento_actual_es_ambiguo_y_eso_es_del_MUESTREO`**, que comprueba que 2021-10-20 **no** está en la cohorte y que el hueco de IBM va de 2021-01-22 a 2022-01-25.

*Resolución temporal* — **un ticker actual no demuestra identidad histórica** (`MOB` @ 1995 → `AMBIGUOUS`); el mismo ticker sí resuelve en su intervalo; **XOM resuelve a CIK distinto según la fecha**; un ticker sin intervalo declarado **no se adivina**.

*Semántica de relación* — las cuatro clases; ningún predicado de identidad se declara `CAUSAL`; **`SUCCESSOR_OF` se clasifica antes de existir**; y el que documenta el riesgo vigente: el traversal usa **lista negra**.

## 14. Qué NO se implementó

| no hecho | por qué |
|---|---|
| Corregir perfiles históricos | prohibido, y con la cohorte actual ninguno cambiaría de valor |
| Backfill | prohibido |
| Instrument Master completo | prohibido |
| Política de exclusión en `poblacion()` | es propuesta; implantarla es cambiar el motor |
| Campos `n_identity_valid`, `n_price_continuous`, `n_corporate_action_clean` | **evaluados y no añadidos**: hoy serían `52 / 52 / 50` y no preservan ninguna invariante que los tests no cubran ya. Serán necesarios cuando la política se implante |
| Nuevos benchmarks, scoring, P6/P6.1 | prohibido |
| `SUCCESSOR_OF` en el modelo | D-42; solo se ha **clasificado por anticipado** |

---

## Hallazgo colateral: el traversal causal usa lista negra

Medido sobre `sec:NVDA.NASDAQ`, profundidad 3, a fecha 2026-09-08:

```
caminos totales                            95
con al menos una arista CAUSAL             88 (93%)
SIN ninguna arista causal                   7 (7%)

cadenas vacías observadas:
   LISTED_ON
   ISSUED_BY
   ISSUED_BY -> DOMICILED_IN
   ISSUED_BY -> DOMICILED_IN -> DOMICILED_IN
   ISSUED_BY -> CLASSIFIED_AS
   ISSUED_BY -> CLASSIFIED_AS -> CLASSIFIED_AS
```

`PREDICADOS_NO_CAUSALES` contiene **solo** `BENCHMARKED_BY` y `COMPARED_TO` (D-23). Todo lo demás **se recorre por defecto**, incluidos `ISSUED_BY`, `LISTED_ON`, `DOMICILED_IN` y `CLASSIFIED_AS`.

**`ISSUED_BY` como puente es legítimo** —`ISSUED_BY → SUPPLIES` sí transmite—, pero terminar en el país o el sector no aporta nada. **7 caminos de 95 no contienen ninguna arista causal.**

**El riesgo real es futuro**: con una lista negra, `SUCCESSOR_OF` entraría al motor causal **por defecto** el día que se añada. Por eso queda clasificado como `STRUCTURAL` **antes de existir**, con un test que lo fija. La corrección de fondo —pasar a lista blanca de predicados `CAUSAL`— **no se ha hecho**: cambiaría P5A, que está cerrada, y no es el alcance de esta auditoría.

## Qué cambió — ficheros

| fichero | estado | qué |
|---|---|---|
| `engine/events/acciones_corporativas.json` | **nuevo** | 12 acciones declaradas, con base de clasificación y si está verificada |
| `engine/events/cobertura_acciones.py` | **nuevo** | medición sobre ventanas reales, resumen por horizonte y por activo |
| `engine/events/identidad_instrumento.json` | modificado | `resolucion_temporal` (intervalos XOM/XON/MOB) y `semantica_de_relacion` |
| `engine/events/identidad.py` | modificado | `resolver_identidad(ticker, fecha)` |
| `tests/test_corporate_actions.py` | **nuevo** | 24 tests |

**Sin cambios en `data/` ni `knowledge/`.**

## Supuestos invalidados

1. **"Si el 0% de los eventos está contaminado, la cohorte está limpia."** El 0% mide el **muestreo**: Kyndryl cae en un hueco de IBM.
2. **"Un detector sobre la serie de precios encontraría las acciones corporativas."** Encontraría las escisiones y **se perdería todas las fusiones**.
3. **"Las tres continuidades van juntas."** En fusión y escisión el retorno sobrevive y la economía no.
4. **"D-23 dejó el traversal causal a salvo."** Lo dejó a salvo del **benchmark**. `ISSUED_BY`, `LISTED_ON`, `DOMICILED_IN` y `CLASSIFIED_AS` **siguen recorriéndose**, y producen 7 caminos vacíos de 95.

## Deuda abierta

- **Acciones corporativas `NOT_MEASURED` en 26 de 31 activos** — la tasa del universo es desconocida, no baja.
- **8 de 12 acciones sin verificar contra la SEC** — clasificadas por indicio de ratio.
- **Ningún detector de fusiones** — no hay señal en el precio.
- **El traversal causal es lista negra** — corregirlo tocaría P5A, cerrada.
- **Efecto de una escisión sobre `VOLUME_RELATIVE_TO_PRE_EVENT`** no medido.
- **`cobertura_acciones.py` fuera de `qa.py`** — mismo patrón que D-24.
