# Historical Instrument Master v1 — implementación

**Fecha**: 2026-09-08 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Base**: `46d3065` · **Commit**: `86068de`
**Alcance**: el mínimo necesario para que un ticker no sea identidad. No amplía el universo, no reconstruye precios de deslistados, no construye un clasificador de acciones corporativas.

**Verificación**:

```
python3 -m unittest discover -s tests            723 → 750 tests · OK
python3 engine/contract/qa.py --require-parquet  QA CORE: PASS · QA PARQUET: PASS · STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   PASS (39 entidades · 66 relaciones · 14 fuentes)
git status --short data/                         vacío
python3 engine/knowledge/instrumentos.py         resolución de los casos obligatorios
```

`knowledge/` **sí cambia** —es el objeto de esta iteración— y pasa de 26/51/11 a **39 entidades · 66 relaciones · 14 fuentes**. `data/` no se ha tocado.

---

## Criterio de salida

> Para una fecha histórica, un ticker solo produce un instrumento si existe una relación temporalmente válida entre ticker, listing/security e issuer. Un ticker reutilizado o sin mapeo histórico se marca ambiguo/no resuelto, **nunca se acepta por el mero hecho de que una fuente de precios devuelva datos**.

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
  IBM    2020-01-01   VALID       sec:IBM.NYSE     org:ibm
  NVDA   2020-01-01   VALID       sec:NVDA.NASDAQ  org:nvidia
```

Y el punto de control:

```
  MOB   @ 1995-06-01  precio=True  identidad=UNRESOLVED  elegible=False
  XOM   @ 2019-04-26  precio=True  identidad=VALID       elegible=True
  DWDP  @ 2018-11-01  precio=False identidad=VALID       elegible=False
  IBM   @ 2020-01-01  precio=True  identidad=VALID       elegible=True
```

**`MOB` con precio disponible y sin identidad no es elegible.** Es la línea que separa este diseño de un mapa de tickers.

## Modelo

Siete capas conceptuales, ninguna nueva en el código:

| capa | dónde vive |
|---|---|
| `LEGAL_ENTITY` | entidad `organization` |
| `SEC_CIK` | **alias fechado** de la organización (`scheme: "sec_cik"`) |
| `SEC_FILING` / `SEC_EVENT` | ya cubiertos por P4 y por la autoridad de D-37; **no se duplican aquí** |
| `SECURITY` | entidad `security` |
| `LISTING` | **alias `ticker` con `venue` + `valid_from`/`valid_to`** sobre el security |
| `TICKER` | el `value` de ese alias — **nunca la identidad** |

**No se introdujo `Listing` como entidad** (§9). El array `aliases` ya llevaba `scheme`, `value`, `venue`, `valid_from`, `valid_to` y `source_id`: eso **es** `Ticker + Exchange + validity`. Un test comprueba que `listing` no está en `TIPOS_ENTIDAD`.

## Entidades

**13 nuevas** (7 organizaciones, 6 securities):

| organización | CIK | estado |
|---|---|---|
| `org:dupont` | `0001666700` | ACTIVE — formerName *DowDuPont Inc.* 2016-03-01→2019-05-31 |
| `org:rtx` | `0000101829` | ACTIVE — dos formerNames encadenados |
| `org:walgreens` | `0001618921` | **INACTIVE** — ausente de `company_tickers.json` |
| `org:exxonmobil-holdings` | `0002115436` | ACTIVE — alias válido **desde 2026-07-01** |
| `org:mobilicom` | — | ACTIVE — **sin relación con Mobil** |
| `org:sec`, `org:yahoo-finance` | — | publishers de las fuentes |

| security | estado | ticker(s) con vigencia |
|---|---|---|
| `sec:XOM.NYSE` *(existente, corregido)* | ACTIVE | `XON` …→1999-11-29 · `XOM` 1999-11-30→… |
| `sec:DWDP.NYSE` | **HISTORICAL** | `DWDP` 2017-09-01→2019-05-31 |
| `sec:DD.NYSE` | ACTIVE | `DD` 2019-06-01→… |
| `sec:UTX.NYSE` | **HISTORICAL** | `UTX` 1994-01-24→2020-04-06 |
| `sec:RTX.NYSE` | ACTIVE | `RTX` 2020-04-07→… |
| `sec:WBA.NASDAQ` | **INACTIVE** | `WBA` 2014-12-31→… |
| `sec:MOB.NASDAQ` | ACTIVE | `MOB` **2022-08-25**→… |

`ESTADOS_ENTIDAD` ya tenía `INACTIVE` y `HISTORICAL`, y el modelo ya decía que *"una entidad no se borra cuando deja de cotizar"*. Esta iteración es la primera que lo usa.

## Relaciones

**15 nuevas**, todas `STRUCTURAL` y con vigencia. Un solo predicado nuevo:

```python
"SUCCEEDED_BY": ({"security"}, {"security"})
PREDICADOS_NO_CAUSALES = frozenset(PREDICADOS_CON_ROL | {"SUCCEEDED_BY"})
```

- `sec:DWDP.NYSE --SUCCEEDED_BY--> sec:DD.NYSE` (2019-06-01)
- `sec:UTX.NYSE --SUCCEEDED_BY--> sec:RTX.NYSE` (2020-04-07)
- **`sec:WBA.NASDAQ` sin sucesor declarado** — no se ha verificado ninguno, y eso **no es un `false`**.
- **`sec:MOB.NASDAQ` sin sucesor**: no es sucesor de Mobil y no hay arista que los una.

**Nace NO CAUSAL** (D-23): que DowDuPont pasara a DuPont no conecta a DuPont con los clientes de Dow. Un test recorre el índice causal y comprueba que ninguna arista es `SUCCEEDED_BY`.

## Temporalidad

**Una corrección al validador era imprescindible.** La comprobación de alias ambiguo era **global**:

```
un mismo (scheme, value) no puede apuntar a dos entidades
```

Eso da por supuesto que **un ticker identifica a una sola entidad en toda la historia** — el supuesto que `MOB` desmiente. Ahora la comprobación es **temporal**, reutilizando `_solapan()` de D-21: un ticker reutilizado es legítimo mientras las vigencias no se solapen; lo que sigue prohibido es que dos entidades lo reclamen **en la misma fecha**. Hay un test para cada mitad.

**Y dos correcciones de vigencia en datos ya declarados**, ambas medidas:

1. **`rel:0009` (XOM `ISSUED_BY`)** decía `valid_from: 2026-09-03` — la fecha en que se declaró, no la vigencia económica. Peor: para esa fecha el ticker **ya había migrado** al holdco. Corregida a **1994-03-04 → 2026-06-30**, con `rel:0052` cubriendo desde 2026-07-01.
2. **`rel:0001/0002` (IBM) y `rel:0005/0006` (NVDA)** tenían el mismo problema. Re-ancladas al **primer filing del CIK en EDGAR** — IBM **1994-03-10**, NVDA **1998-03-06**, XOM **1994-03-04** — medido recorriendo también los ficheros históricos de `submissions`.

El `statement` dice explícitamente qué significa esa fecha: *"es la fecha desde la que hay evidencia directa, no una afirmación de que antes no existiera"*.

## Estados

```
VALID       hay security y issuer vigentes en esa fecha
AMBIGUOUS   hay instrumento pero la resolución no es única o falta el emisor
UNRESOLVED  ningún alias declarado cubre esa fecha
```

**Todo estado distinto de `VALID` lleva motivo**, y hay un test que lo exige: un `UNRESOLVED` sin razón es indistinguible de un fallo del resolutor. Los motivos distinguen *"no existe ese identificador"* de *"existe pero fuera de vigencia"* — que es la diferencia entre un ticker desconocido y un ticker reutilizado.

`resolve_instrument(identifier, as_of)` **lanza `ValueError` si `as_of` es `None`**: para historia no existe la versión sin fecha.

## Casos

**DWDP** — `VALID` en 2018, `UNRESOLVED` en 2024. Identidad completa sin precio.
**UTX** — `VALID` en 2019-01-23, con sucesor `sec:RTX.NYSE`.
**WBA** — `VALID` en 2019 pese a estar ausente del directorio de tickers y sin serie de precios. **Sin sucesor declarado.**
**XOM** — mismo security, **emisor distinto según la fecha**: `org:exxonmobil` (CIK 34088) hasta 2026-06-30 y `org:exxonmobil-holdings` (CIK 2115436) desde 2026-07-01. Y `XON` resuelve en 1998 al mismo security bajo su ticker anterior.
**MOB** — `UNRESOLVED` en 1995 **aunque la fuente de precios devuelva 1011 sesiones**; `VALID` en 2024 como Mobilicom. Es la prueba de seguridad permanente.

## Límites

1. **Solo 8 securities tienen identidad histórica declarada.** Los otros 25 activos del universo siguen sin mapa: `historical_ticker` sigue al **0%** para ellos.
2. **Las anclas de vigencia no son fechas de nacimiento.** «Primer filing en EDGAR» es la evidencia más antigua disponible, no una afirmación sobre lo anterior.
3. **No hay clasificador de acciones corporativas.** `SUCCEEDED_BY` dice *que* hubo sucesión, no *de qué tipo* (§10).
4. **`SEC_FILING` y `SEC_EVENT` no se modelan aquí**: ya viven en P4 y en la autoridad de D-37, y duplicarlos habría creado la estructura paralela que §2 prohíbe.
5. **El precio de DWDP, UTX y WBA sigue sin resolver** — deliberadamente (§11).

## Efecto colateral medido — y no es menor

Declarar identidad legítima **empeoró** la debilidad que D-49 ya había medido:

```
sec:NVDA.NASDAQ -> ven:NASDAQ -> sec:MOB.NASDAQ -> org:mobilicom
sec:NVDA.NASDAQ -> ven:NASDAQ -> sec:WBA.NASDAQ -> org:walgreens
```

**Cuatro caminos nuevos que conectan NVDA con Mobilicom y con Walgreens por el solo hecho de cotizar en el mismo mercado**, y **ninguno contiene una arista causal**. Antes `ven:NASDAQ` era un callejón sin salida porque NVDA era el único security declarado allí; ya no.

No se ha tocado P5A —está prohibido y D-49 dejó demostrado que la lista blanca falla el criterio de regresión cero— pero **el coste de la lista negra ha dejado de ser teórico**. Queda un test frágil a propósito que documenta estos caminos y **se romperá el día que se aplique la variante C**.

**Un test caducó por esto** y se reescribió según §3 del protocolo: `test_el_limite_de_profundidad_se_distingue_de_la_falta_de_conocimiento` exigía que a profundidad 3 apareciera `NO_FURTHER_KNOWLEDGE`, apoyándose en que NASDAQ fuese un callejón sin salida. Se apoyaba en una **ausencia de conocimiento**, no en una propiedad del motor. Reescrito a la propiedad que sigue siendo cierta: los motivos no se confunden y ampliar la profundidad no convierte un `COMPLETE` en incompleto.

## Qué queda pendiente

| pendiente | por qué no está |
|---|---|
| Mapa de identidad para los 25 activos restantes | trabajo de curación, no de diseño |
| Precio de DWDP, UTX, WBA | §11 lo prohíbe; es la decisión A/B/C siguiente |
| Clasificador de acciones corporativas | §10 lo prohíbe; la semántica queda preparada |
| Sucesor de WBA | no verificado; declararlo sin fuente sería inventarlo |
| `P5A hardening` (variante C de D-49) | fuera del alcance, ahora con coste medido |
| Conectar el punto de control a `poblacion()` | sería cambiar el motor de perfiles |

## Tests

**723 → 750** (`Ran 750 tests · OK`). `tests/test_instrument_master.py`, **26 tests**, cubriendo los 10 exigidos:

| # exigido | test |
|---|---|
| 1 ticker no implica identidad | `test_un_ticker_no_implica_identidad` |
| 2 MOB histórico no devuelve Mobilicom | `test_MOB_historico_no_devuelve_Mobilicom` |
| 3 XOM cambia de CIK según fecha | `test_un_ticker_puede_tener_varios_CIK_a_lo_largo_del_tiempo` |
| 4 ticker con varios CIK en el tiempo | `test_el_cik_viaja_como_alias_fechado_no_como_identidad` |
| 5 sucesión es estructural | `test_la_sucesion_es_estructural` |
| 6 sucesión fuera del grafo causal | `test_la_sucesion_no_entra_al_grafo_causal` |
| 7 security válida exige intervalo | `test_una_security_valida_exige_intervalo` |
| 8 ausencia de mapping ≠ falso | `test_la_ausencia_de_mapping_no_se_convierte_en_falso` |
| 9 UNRESOLVED no pasa a VALID | `test_unresolved_no_se_convierte_en_valid` |
| 10 `resolve_instrument` exige `as_of` | `test_resolve_instrument_exige_as_of` |

Y los que protegen el diseño: `test_el_precio_no_basta_para_dar_identidad`, `test_el_validador_permite_reutilizar_un_ticker_sin_solape` con su contraparte `test_el_validador_sigue_prohibiendo_el_solape_real`, `test_no_hay_tipo_de_entidad_listing`, `test_solo_se_anadio_un_predicado` y `test_D21_intacta`.

## QA

```
python3 engine/contract/qa.py --require-parquet   QA CORE: PASS · QA PARQUET: PASS · STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar    PASS · 39 entidades · 66 relaciones · 14 fuentes
git status --short data/                          vacío
```

`data/` intacto. `knowledge/` crece de 26/51/11 a 39/66/14, que es el objeto de esta iteración.

## Qué cambió — ficheros

| fichero | estado | qué |
|---|---|---|
| `engine/knowledge/instrumentos.py` | **nuevo** | `resolve_instrument`, `sucesor_de`, `apto_para_event_study` |
| `engine/knowledge/modelo.py` | modificado | `SUCCEEDED_BY` no causal · ambigüedad de alias **temporal** |
| `knowledge/entities/organizations.json` | modificado | +7 organizaciones, CIK como alias fechado |
| `knowledge/entities/securities.json` | modificado | +6 securities, tickers con vigencia |
| `knowledge/relationships/instrumentos.json` | **nuevo** | 15 relaciones fechadas |
| `knowledge/relationships/identidad.json` | modificado | 6 vigencias re-ancladas a fechas medidas |
| `knowledge/sources/sources.json` | modificado | +3 fuentes |
| `tests/test_instrument_master.py` | **nuevo** | 26 tests |
| `tests/test_caminos.py` | modificado | 1 test caducado reescrito + 1 test nuevo de evidencia |

## Supuestos invalidados

1. **"El modelo necesita una entidad `Listing`."** No: `aliases` ya llevaba `venue` y vigencia.
2. **"El validador es neutral respecto a la identidad."** No: prohibía globalmente que dos entidades compartieran un alias, incrustando *"ticker = identidad"* en la propia validación.
3. **"`valid_from` es la vigencia económica."** En las relaciones existentes era **la fecha de declaración**, y para XOM eso resultaba directamente incorrecto.
4. **"Declarar más conocimiento solo puede mejorar el grafo."** Declarar identidad correcta creó cuatro caminos causales espurios entre empresas que solo comparten mercado.
