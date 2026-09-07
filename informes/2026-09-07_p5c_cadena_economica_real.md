# P5C · Economic Knowledge Seed v2 — la primera cadena económica real

**Fecha**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2`
**Alcance acordado**: `NVIDIA → TSMC → CoWoS`, una relación cada vez, con su fuente. HBM y cualquier otro nodo **solo** cuando la relación esté documentada.

---

## 1. Qué cambia de verdad

No son tres relaciones más. Es **de dónde vienen**.

Todo el Knowledge anterior (45 relaciones, P2) se extrajo del propio repositorio:

| Origen | Tipo de fuente | Qué es en realidad |
|---|---|---|
| `KRAKEN_PAIR`, `COINBASE_PAIR`, `ASSETS` | `INTERNAL_RULE` | una tabla del código de este sistema |
| `data/assets/*.json` | `DATA_PROVIDER` | un fichero que este sistema escribe |
| hueco de XRP, tabla `NO_APLICA` | `OWN_ANALYSIS` | una medición hecha aquí dentro |

Ninguna de las tres es evidencia del mundo: son evidencia de **lo que este software hace**. P2 ya lo dejó escrito al degradar `EXPOSED_TO` a `ASSERTED`/`PROVISIONAL`/`BAJO`: *una regla del código no es un hecho estructural del mundo*.

P5C introduce las **dos primeras fuentes externas y primarias** del proyecto, y con ellas el primer camino causal `VERIFIED` que sale de lo financiero.

---

## 2. Las fuentes

| `source_id` | Tipo | Documento | Publicado | Localizador |
|---|---|---|---|---|
| `src:nvda-10k-fy2026` | `FILING` | NVIDIA, Form 10-K del ejercicio cerrado el 25-01-2026 | 2026-02-25 | [EDGAR `nvda-20260125.htm`](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm) — Item 1 Business, epígrafe *Manufacturing* |
| `src:tsmc-20f-fy2025` | `FILING` | TSMC, Form 20-F del ejercicio cerrado el 31-12-2025 | 2026-04-16 | [EDGAR `tsm-20251231.htm`](https://www.sec.gov/Archives/edgar/data/1046179/000162828026025362/tsm-20251231.htm) — Item 4.B Business Overview, plataforma HPC |

**Decisión de fuente para TSMC.** `pendiente/` preveía *"comunicación técnica de TSMC sobre su plataforma de encapsulado avanzado"*, es decir la página comercial `tsmc.com/.../cowos`, como `COMPANY_STATEMENT`. Se descartó y se usó el 20-F en su lugar. Razones, en orden:

1. La página web **no tiene fecha estable** y su contenido puede cambiar sin dejar rastro. `modelo.validar()` exige un localizador que permita **reabrir** el documento; una URL cuyo contenido muta no lo permite.
2. Está detrás de protección anti-bot (`curl` recibe `Just a moment... Enable JavaScript`), de modo que ni siquiera se puede verificar de forma reproducible desde este entorno.
3. El 20-F **dice lo mismo**, es un `FILING` en vez de un `COMPANY_STATEMENT`, y su URL en EDGAR es inmutable.

Es el mismo criterio con el que en la Fase 4 se descartó Google News RSS y en el bloque 3 del backfill se eligió Coinbase sobre Binance: se prefiere la fuente que se puede releer y citar, no la más cómoda.

---

## 3. Las tres relaciones

### `rel:0046` — `org:tsmc SUPPLIES org:nvidia`

> "We utilize foundries, such as **Taiwan Semiconductor Manufacturing Company Limited, or TSMC**, and Samsung Electronics Co., Ltd., or Samsung, to produce our semiconductor wafers."
> — NVIDIA 10-K FY2026, Item 1 Business, *Manufacturing*

`STRUCTURAL` · `VERIFIED` · `ALTO` · vigente desde `2025-01-27`.

**Dos sesgos anotados en la propia fuente, no escondidos**:
- Es la **parte interesada** describiendo su propia cadena de suministro. NVIDIA no tiene incentivo para nombrar en falso a un proveedor, pero eso hay que decirlo, no asumirlo.
- El **"such as" es del original**: la lista es explícitamente **no exhaustiva**. Que TSMC esté nombrada es un hecho; que sean los únicos, no se afirma.

### `rel:0047` — `org:nvidia USES tech:cowos`

> "**We utilize CoWoS technology for semiconductor packaging.**"
> — mismo documento, mismo epígrafe

`STRUCTURAL` · `VERIFIED` · `ALTO` · vigente desde `2025-01-27`.

**Esta relación no estaba prevista en `pendiente/`.** Aparece porque la fuente la dice literalmente, no porque se fuera buscando. La frase no dice *quién ejecuta* el encapsulado — eso lo acredita `rel:0048`, no ésta.

### `rel:0048` — `org:tsmc USES tech:cowos`

> "We also offer multiple TSMC 3DFabric® advanced silicon stacking and packaging solutions, such as TSMC-SoIC® manufacturing services and **CoWoS® advanced packaging services**"
> — TSMC 20-F FY2025, Item 4.B, plataforma HPC

`STRUCTURAL` · `VERIFIED` · `ALTO` · vigente desde `2025-01-01`. El mismo 20-F lista `CoWoS` entre las marcas registradas de TSMC.

Se lee *"offer … services"* como `USES` (TSMC ejecuta el proceso), no como una venta de producto. **La palabra exacta de la fuente queda en el `statement`** para que quien lea pueda discrepar de la lectura sin tener que volver al documento.

---

## 4. Dos decisiones que se apartan de lo previsto

### 4.1 `tech:cowos`, no `prod:cowos`

`pendiente/` la había anotado como producto. Se tipó como **tecnología**, aplicando la definición del propio modelo:

- `product`: *"bien o servicio concreto, con capacidad y precio"*
- `technology`: *"proceso o capacidad que se emplea, no se compra"*

NVIDIA no compra "un CoWoS": compra encapsulado hecho **con** CoWoS. Y su propio 10-K dice *"CoWoS **technology**"*.

**El contraargumento es real y queda anotado en la entidad, no escondido**: TSMC lo vende como *"CoWoS advanced packaging **services**"*, y un servicio sí tiene capacidad y precio — de hecho **la capacidad CoWoS es justo la variable económica interesante**. Si en P6 hace falta tratar esa capacidad como magnitud, será un `concept`, no un cambio de tipo de esta entidad. Ningún predicado se pierde por la elección: `USES`, `EXPOSED_TO` y `SUBSTITUTES` admiten los dos tipos.

### 4.2 La vigencia no se extrapola

`valid_from` es el **primer día del ejercicio que cubre el documento citado**, no "desde siempre" ni la fecha de consulta:

| Relación | `valid_from` | Por qué |
|---|---|---|
| `rel:0046`, `rel:0047` | `2025-01-27` | el ejercicio fiscal anterior de NVIDIA cerró el 2025-01-26 |
| `rel:0048` | `2025-01-01` | el 20-F cubre el año natural 2025 |

TSMC fabrica para NVIDIA desde mucho antes de 2025. **Esta fuente no lo acredita, así que el sistema no lo afirma.** Un test lo fija (`test_la_vigencia_no_se_extrapola`).

---

## 5. El camino, recorrido

Con el motor de P5A **sin tocar** (`caminos.py` sigue cerrado y verificado por hash en la suite):

```
cp:…:rel:0005>rel:0046>rel:0048   VERIFIED · COMPLETE · depth 3
    sec:NVDA.NASDAQ  -ISSUED_BY->  org:nvidia   (FORWARD, rel:0005)
    org:nvidia       -SUPPLIES->   org:tsmc     (REVERSE, rel:0046)
    org:tsmc         -USES->       tech:cowos   (FORWARD, rel:0048)
```

Es el **primer camino `VERIFIED` y `COMPLETE` del proyecto hasta una entidad no financiera**. Antes de P5C, el único enlace que salía de lo financiero era `EXPOSED_TO`, que procede de una regla del propio motor: cualquier camino completo habría sido `PROVISIONAL`.

El salto al proveedor se recorre en **`REVERSE`**: `SUPPLIES` está declarada `TSMC → NVIDIA` y se recorre al revés, y eso se anota. No se duplica la relación en el sentido cómodo.

---

## 6. El resultado económico: `UNKNOWN`, y por qué eso es el éxito

P5B sobre la cadena real, con un impulso de demanda al alza sobre NVIDIA:

```
  org:nvidia → org:tsmc   [rel:0046]
      mecanismo   CUSTOMER_DEMAND · R3
      efecto      revenue = UNKNOWN
      necesita    demand(org:nvidia)
  org:tsmc → tech:cowos   [rel:0048]
      mecanismo   INPUT_COST · R5           efecto  cost = UNKNOWN
      mecanismo   CAPACITY_CONSTRAINT · R4  efecto  pricing_power = UNKNOWN
      necesita    capacity_utilization(tech:cowos)

  DIRECCIÓN GLOBAL  UNKNOWN
  SOPORTE           UNKNOWN
```

En P5B el `UNKNOWN` tenía **dos** causas a la vez: no había ninguna relación económica afirmativa **y** no había ninguna variable de mecanismo medida. **P5C resuelve la primera.** La segunda sigue en pie, y es la que de verdad bloquea.

La diferencia no es cosmética. Antes, todo camino real caía en `NO_MECHANISM` porque solo había aristas de identidad: el sistema no tenía ni la pregunta. Ahora las reglas **sí se activan** y se quedan bloqueadas por falta de medición, que es un estado distinto y mucho más útil:

> **`requires_evidence` deja de estar vacío.** `demand(org:nvidia)` y `capacity_utilization(tech:cowos)` son ahora la **justificación documentada** para abrir una fuente de datos nueva — no al revés. Ése era el mecanismo que se acordó: la necesidad de evidencia se demuestra, no se presupone.

---

## 7. El límite acordado se respeta — y qué se encontró al respetarlo

**HBM y el sustrato ABF siguen fuera**, y no por pereza: se buscaron explícitamente en los dos documentos primarios. **Cero menciones de "HBM" y cero de "ABF"/"Ajinomoto" en ambos filings.** El 10-K solo dice *"memory"*. La búsqueda queda registrada en el propio `pendiente/` (`_estado_2026_09_07`) y fijada por un test.

**Hallazgo que sí apareció**: la **misma frase** del 10-K que acredita `rel:0046` nombra a Samsung como fundición, y a SK Hynix, Micron y Samsung como proveedores de memoria.

> "We utilize foundries, such as … TSMC, **and Samsung Electronics Co., Ltd., or Samsung**, to produce our semiconductor wafers. **We purchase memory from SK Hynix Inc., Micron Technology, Inc., and Samsung.**"

Esas tres relaciones **ya no son candidatas sin fuente**: tienen fuente primaria identificada y verificada. **No se dan de alta porque el alcance acordado era la cadena NVIDIA → TSMC → CoWoS, no porque falte documentación** — y la diferencia queda escrita en `pendiente/` (`_candidatas_documentadas_pendientes_de_alta`) para que nadie la confunda con una ausencia de evidencia. Son promovibles en un paso, sin buscar nada nuevo.

**Por qué importa `org:samsung SUPPLIES org:nvidia` en particular**: es el único **sustituto documentado** de TSMC como fundición. La corrección central de P5B fue que *ausencia de fila `SUBSTITUTES` ≠ ausencia de sustituto*, con un chequeo de tres estados. Mientras Samsung no esté dado de alta, el sistema no puede distinguir "no se sabe si hay alternativa" de "la hay". Es la primera candidata a promover.

---

## 8. Tests

`tests/test_cadena_suministro.py` — **23 tests nuevos** en cinco bloques:

| Bloque | Qué fija |
|---|---|
| `TestLaCadenaEstaDadaDeAlta` | forma, naturaleza, estado y soporte de las tres; `tech:cowos` es tecnología |
| `TestLaProcedenciaEsExterna` | **el núcleo**: `FILING` de parte externa, sin `INTERNAL_RULE` ni `OWN_ANALYSIS`, localizador EDGAR, literal transcrito, sesgo anotado, vigencia sin extrapolar |
| `TestElCaminoSeRecorre` | la cadena existe, es `COMPLETE`, es `VERIFIED`, el salto al proveedor es `REVERSE`, ninguna arista se inventa |
| `TestLaCadenaEsUnaPreguntaNoUnaRespuesta` | `UNKNOWN`, pero con mecanismos activos y `requires_evidence` poblado |
| `TestElLimiteAcordadoSeRespeta` | HBM/ABF fuera, `tech:cowos` sin salidas, búsqueda de fuente registrada, candidatas documentadas listadas |

### Cuatro tests anteriores hubo que reescribirlos, y es lo correcto

Codificaban **el estado del mundo antes de P5C**, no una propiedad permanente:

| Test | Decía | Ahora dice |
|---|---|---|
| `test_una_entidad_no_declarada_no_se_crea` (P5A) | usaba `org:tsmc` como ejemplo de entidad inexistente | usa un identificador que no existirá nunca |
| `test_ningun_camino_llega` (P5A/T4) | ningún camino alcanza una entidad no financiera | se separa en dos poblaciones: los incompletos siguen diciendo dónde se cortan; el que llega, llega **por conocimiento con fuente** |
| `test_la_unica_entidad_no_financiera_solo_tiene_negaciones` (P5A/T4) | `tech:defi-smart-contracts` era la única | sigue siendo el caso que P5C **no** cambia: documentar CoWoS no documenta esto |
| `test_no_existe_ninguna_relacion_economica_afirmativa` (P5B) | cero relaciones económicas afirmativas | ahora las hay; **lo que bloquea es que ninguna variable de mecanismo esté medida** |
| `test_no_hay_camino_desde_nvda_a_una_entidad_no_financiera` (P2) | nada no financiero es alcanzable | **lo no documentado** no se alcanza: HBM y ABF no aparecen en ninguna relación |

Un test que se apoya en que algo **no** existe caduca en cuanto ese algo se documenta — y eso es exactamente lo que tiene que pasar. Afirmar hoy "ninguno llega", y dejarlo afirmado para siempre, habría convertido una ausencia medida en un dogma.

---

## 9. Verificación

```bash
python3 -m unittest discover -s tests            # 354 tests · OK   (329 → +25)
python3 engine/knowledge/consulta.py --validar   # 25 entidades · 48 relaciones · 10 fuentes · PASS
python3 engine/contract/qa.py --require-parquet  # STATUS: VERIFIED
python3 engine/causal/caminos.py sec:NVDA.NASDAQ --hasta-no-financiera --profundidad 4
```

Ficheros tocados: `knowledge/entities/{organizations,technologies}.json` · `knowledge/sources/sources.json` · `knowledge/relationships/cadena_suministro.json` (nuevo) · `knowledge/pendiente/nvidia_cadena.json` · `tests/test_cadena_suministro.py` (nuevo) · `tests/{test_caminos,test_valoracion,test_knowledge}.py`.

**Ningún módulo del motor se ha modificado.** P5A y P5B recorren y valoran la cadena nueva con el código que ya tenían: era justo lo que había que comprobar.

---

## 10. Lo siguiente

En el orden en que se hace más barato y menos arriesgado:

1. **Promover Samsung / SK Hynix / Micron** — fuente ya verificada, un paso. Desbloquea el chequeo de sustitución de P5B, que hoy no puede distinguir "no se sabe" de "hay alternativa".
2. **`CoWoS → ?`** — sigue sin fuente primaria. No se promueve nada hasta tenerla.
3. **P6 · Economic Impact** — ahora con `requires_evidence` poblado, que es lo que justifica abrir una fuente de datos nueva.

**Deuda registrada, no resuelta**: `rel:0046` documenta la relación de suministro, pero no su **materialidad** — el 10-K no dice qué fracción de los wafers de NVIDIA fabrica TSMC. Cualquier medida de impacto que lo requiera tendrá que decir que no lo sabe.
