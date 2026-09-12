# F1 — Contexto durable y cierre documental (T10)

**Fecha**: 2026-09-12 · **Bloque**: F1 · **Rango**: `6316bcd..f784b85`

> Este informe se redacta el **2026-09-12** como materialización documental de
> **T10**. **No existió antes de esta fecha.** T10 se ejecutó como auditoría
> *read-only* en la sesión `session_0179q4dtcnyvFaxR1bGhHf7h` sin dejar
> artefacto en el repositorio; este documento lo registra a posteriori,
> distinguiendo en todo momento qué está demostrado por Git y qué solo por
> aquella conversación.

Nada de lo que sigue se fecha hacia atrás. Donde una afirmación depende de una
conversación y no del repositorio, se dice.

---

## A · Qué estaba planificado

El plan de tickets **sí es evidencia de repositorio**: el cuerpo de `6316bcd`
lo enumera literalmente.

> «AUTORIZADO Y ENTREGADO: T1 completo + T2-SLICE + T4-SLICE + T6-SLICE.
> **NO entra: T2/T4/T6 completos, T3, T5, T7, T8, T9, T10.**»

| Ticket | Qué | Commit |
|---|---|---|
| T1 | Integridad del contenido histórico | `6316bcd` |
| T2 · T3 · T4 · T6 | Contrato, L0 por cierre efectivo, superficie S1, validador de las tres clases | `97bd1e1` (slices en `6316bcd`) |
| T5 | Extracción D-PRD-1 de `CLAUDE.md` | `8c38056` |
| T7 | Índice de alcanzabilidad del contexto (S6) | `30022c9` |
| T8 | Batería negativa e invariantes | `032c9e5` |
| T9 | CI de pull request | `f784b85` |
| **T10** | **auditoría final read-only** | **sin commit** |

**`CONVERSATION_ONLY`**: la *definición* de T10 como auditoría final read-only.
Git lo nombra como ticket del plan, pero **ninguna fuente del repositorio dice
qué era**. Se registra aquí como afirmación del usuario, no como hecho de Git.

---

## B · Qué fue realmente implementado

Todo con ancla en el árbol y en los cuerpos de commit.

| Requisito | Ticket | Fichero | Bytes |
|---|---|---|---|
| S1 superficie de estado vigente | T4 | `contexto/ESTADO_VIGENTE.md` | 7.265 |
| S2 contrato de contexto | T2 | `contexto/contrato.json` | 12.834 |
| S3 registro de STATE QUERY | T2 | `contrato.json::state_queries` | 14 consultas |
| S4 validador | T6 | `contexto/validar.py` | 19.646 |
| S5 presupuesto L0 | T3 | `l0_efectivo()` + `medir_l0()` | 2.305 tok |
| S6 índice de alcanzabilidad | T7 | `contexto/grafo.py` | 9.348 |
| S7 integridad histórica | T1 | `contexto/integridad.py` | 6.979 |
| S8 batería negativa | T8 | `tests/test_invariantes_f1.py` | 23 mutaciones |
| S9 CI de PR | T9 | `.github/workflows/verificar-contexto.yml` | 2.332 |
| D-PRD-1 extracción | T5 | `contexto/historico/claude_md_…md` | 23.333 |

**165 tests en 7 ficheros**, y la cadena de crecimiento de la suite consta en
los siete cuerpos de commit: `777 → 814 → 824 → 845 → 879 → 905 → 919 → 942`.
La diferencia, 942 − 777 = **165**, cuadra con el conteo por fichero.

---

## C · Qué fue reverificado, y cuándo

Reejecutado sobre `f784b85` el **2026-09-12 a las 13:44:43Z**. Los 11 tamaños
de fichero coinciden **al byte** con los declarados en la conversación.

```
python3 -m unittest discover -s tests          Ran 942 tests — OK
python3 contexto/validar.py                    PASS   L0 2.305 / 12.000
                                                      14 consultas: 9 / 1 / 4
python3 contexto/integridad.py                 PASS   PRESERVED=43 MOVED=0
                                                      ADDED=0 LOST=0 ALTERED=0
python3 contexto/extraccion.py                 PASS   ancla ff2003f9… coincide
python3 contexto/grafo.py                      PASS   27 nodos · 36 aristas
python3 engine/knowledge/consulta.py --validar PASS
python3 engine/contract/qa.py --require-parquet CORE PASS · PARQUET PASS
```

Comprobado además, y no solo el total del grafo sino **su forma**:

```
MANDATORY_READ 1 · POINTS 15 · VALIDATES 6 · REFERENCE 12 (+2 desde REGENERABLE)
REGENERABLE → HISTORICAL = 0
```

`consultar("pregunta_que_no_existe")` → `('UNDECLARED', None)`: estado
explícito, **no un valor por defecto**.

Y el invariante 12 de F1, verificado por la vía que de verdad lo demuestra —
`git diff 3b008f0..f784b85` — : **0 ficheros** en `engine/`, `data/`,
`knowledge/`, `docs/` e `informes/`.

Una nota de entorno que importa para reproducir esto: la suite **requiere
`pyarrow`**. Sin él son 43 errores de importación, no un defecto del código.
Ver §E.

---

## D · Qué no quedó persistido entonces

Dicho como hecho, sin justificarlo.

- **T10 no dejó artefacto.** Ni commit, ni informe, ni entrada de contrato.
- **Su definición no está en el repositorio.** Solo el nombre del ticket.
- **D-54 y D-55 nunca se registraron** en `docs/DECISIONES.md`, que se quedó
  en D-53 (`ff7a4da`, 2026-09-11). El PRD las exigía.
- **`docs/ESTADO.md` no recibió una sola línea de F1**: 0 ocurrencias de «F1»
  en sus 52.756 bytes. Su último commit es `3b008f0`, el inmediatamente
  anterior al arranque de F1.
- **No había informe de F1** en `informes/`, que `docs/07-protocolo-de-informes.md`
  §1 exige al cerrar una fase.
- **La verificación en contexto fresco** (punto 10 de T10) se ejecutó según la
  conversación y **no quedó registrada**.
- **El PRD de F1 no está en el repositorio.** La matriz S1–S9 de §B lo
  reconstruye desde los cuerpos de commit y el árbol.

Hay una razón estructural detrás de varios de estos puntos, y conviene
dejarla escrita porque no es negligencia: `docs/ESTADO.md` y
`docs/DECISIONES.md` **están fijados por hash** en `contexto/manifiesto.json`,
y `ALTERED` no admite excepción por diseño —*«LOST y ALTERED no tienen flag de
excepcion y no deben tenerlo nunca»*—. Además `integridad.py::main()` invoca
`verificar()` sin `adiciones` y no expone forma de declararlas, así que un
fichero nuevo en `informes/` se clasificaba **`LOST`** → FAIL. **F1 construyó
un mecanismo que hacía inejecutable su propio protocolo de cierre.**

El procedimiento que lo resuelve queda declarado en D-56: el cambio en
`docs/` o `informes/` viaja **en el mismo commit** que la regeneración de
`contexto/manifiesto.json`, y la guarda de alcance lo exige (veredicto
`PROTEGIDO_GLOBAL`, condicional). La taxonomía `ADDED` frente a `LOST` sigue
siendo deuda (DF-2).

---

## E · Contradicciones descubiertas

Seis, con su cadena `material → fuente canónica → estado actual`. Ninguna se
corrige en silencio.

### E1 · «F1 = CLOSED» era falso

```
material    "F1 = CLOSED · Todos los requisitos satisfechos"
canónica    contrato.json::alcance_bloque.vigente = true
            contrato.json::open_debt[3]  "apagarlo es requisito para PC-1"
            contrato.json::state_queries[f1_estado]  "T7-T10 pendientes"
            docs/ESTADO.md  0 ocurrencias de "F1"
            docs/DECISIONES.md  última D-53
            informes/  sin informe de F1
actual      F1 NO estaba cerrada en el repositorio
```

Y el material **se contradecía consigo mismo**: su propia sección de deudas
documentaba que D-54/D-55 no se registraron, que no había informe y que el
texto de cierre era inexacto — y aun así concluía `CLOSED`.

### E2 · El mecanismo que produjo ese veredicto

```
material    D-55: "Implementación: no registrado · Evidencia: ninguna
                   · Estado: SATISFECHO_CON_DEUDA"
canónica    DECISIONES.md: D-55 no existe
actual      un requisito con evidencia NULA no es "satisfecho con deuda":
            es NO SATISFECHO
```

Error de categoría, y es el que hizo posible el `CLOSED`: si
`SATISFECHO_CON_DEUDA` admite evidencia vacía, la etiqueta no discrimina nada.
Contradice el invariante del propio proyecto: `UNKNOWN` ≠ `NEUTRAL`, ausencia
≠ cero.

### E3 · `engine/ = 119` no es reproducible

```
material    "engine/ 119 -> 119 SIN CAMBIOS"
canónica    worktree sin __pycache__: 118 · rastreados por git: 95
actual      la cifra 119 no se reproduce con ningún criterio
```

La **sustancia sí se sostiene**, y por mejor vía: `git diff` da 0 ficheros
tocados. El número se midió sobre `engine/*/_data/`, que es efímero y
gitignored. Un invariante no debe medirse sobre una superficie no
reproducible.

### E4 · `alcance_pr.py exit=0` estaba sobre-leído

```
material    §G "contexto/alcance_pr.py ... exit=0"
canónica    cierto, pero evaluaba HEAD~1..HEAD = 4 ficheros
actual      sobre el diff de integración real: 406 de 490 FUERA_DE_ALCANCE
```

No era falso: no decía lo que parecía decir. Corregido en S0.1 — el rango
pasa a ser el del bloque (`desde~1..hasta`), y la salida **declara** qué ha
medido.

### E5 · `como_se_cierra` instruía lo que el propio material declaraba incorrecto

```
material    DF-1: "la transición correcta es sustitución, no apagado"
canónica    alcance_bloque.como_se_cierra = "poner vigente=false ..."
actual      resuelto en S0.1: el interruptor desaparece
```

### E6 · DF-6, que el material no detectó

```
canónica    verificar-contexto.yml declara "SIN DEPENDENCIAS" y ejecuta
            la suite completa
actual      11 ficheros de test importan pyarrow vía storage.py; solo
            test_storage_parquet.py está protegido con skipUnless
            → en un runner limpio: 43 ERRORES
```

**El gate de PR construido en T9 fallaría hoy.** Pasa localmente porque
`pyarrow` está instalado. Ningún PR lo reveló porque **el repositorio no ha
tenido ni un pull request**. Es un defecto en un entregable de F1 y por eso
**bloquea su cierre** (§F). Se corrige en S0.2.

---

## F · Estado actual de F1

**`OPEN`**, por veredicto calculado — no por afirmación.

```
python3 -c "import validar; print(validar.veredicto_cierre('F1'))"
```

| # | Obligación | Estado | Evidencia |
|---|---|---|---|
| 1 | entregables | ✅ | 10 declarados, todos resuelven |
| 2 | tests | ✅ | `python3 -m unittest discover -s tests` |
| 3 | validadores | ✅ | 6 autoridades declaradas y resolubles |
| 4 | alcance | ✅ | `desde=6316bcd`, sucesor activo `S0` |
| 5 | **deudas bloqueantes** | ❌ | **DF-6 abierta** |
| 6 | última verificación | ✅ | `f784b85`, 2026-09-12T13:44:43Z |
| 7 | commit | ✅ | `f784b85` resoluble y ancestro de HEAD |

**F1 está técnicamente completada y documentalmente registrada, pero no
cerrada.** Y esa es la respuesta correcta: no se puede declarar `CLOSED` un
bloque cuyo propio gate de PR no pasa en un runner limpio. Cuando S0.2
resuelva DF-6, el veredicto se recalcula solo.

Que el mecanismo devuelva `OPEN` aquí es la prueba de que no es decorativo.
Un `CLOSED` firmado a mano es exactamente lo que ocurrió en septiembre y lo
que este contrato existe para impedir.

### Deudas que siguen abiertas

| ID | Qué | Bloquea |
|---|---|---|
| D-2 | duplicación como verdad: detección heurística, no estructural | — |
| D-A | `DECISIONES.md` no distingue vigente de superada | — |
| X-1 | `EXPOSED_TO` es `AMBIGUOUS` y no se resuelve | — |
| DF-2 | un fichero nuevo no declarado se etiqueta `LOST`, no `ADDED` | — |
| **DF-6** | el gate de PR falla sin `pyarrow` | **F1** |
| DF-7 | `clasificacion-nodos/v2`: `docs/` es `HISTORICAL` para el mecanismo | — |
| DC-5 | colisión de namespace `L0` (contexto ↔ autonomía) | — |
| DD-4 | `PC-1` sin encaje declarado en `P7…P11` | — |

---

## G · Qué cambió en S0 hasta aquí

| Commit | Qué |
|---|---|
| `aadb269` | **DF-1**: `alcance_bloque.vigente` → `bloque_activo` + `bloques[*].escritura`, cuatro veredictos, denegación por defecto, protección global derivada del manifiesto |
| `27a3b16` | `BLOQUE = desde + hasta`; `CLAUDE.md` en la escritura legítima de F1; autoridad de la extracción |
| `cdeab6a` | Arquitectura **objetivo** persistida: 29 componentes, `IMPLEMENTED` derivado del ancla |
| `986b502` | System Operating Model recuperado como dimensión propia, sin componentes ni maquinaria |

**Diez tests caducaron y se reescribieron** (`docs/07` §3), no se borraron: se
apoyaban en que `engine/`, `data/` y `knowledge/` estuviesen prohibidos
*siempre* — la formulación del interruptor. Uno **invierte** su propiedad:
antes exigía que el interruptor existiese; ahora, que no exista.

## H · Implicaciones para los consumidores

Ninguna. `engine/`, `data/`, `knowledge/`, el Data Contract, el cron diario,
Power BI y la Web App **no se han tocado** en ningún commit de S0. `docs/` e
`informes/` solo reciben este informe, las decisiones D-54+ y la
actualización de `ESTADO.md`, con el manifiesto regenerado en el mismo commit.

## I · Qué viene después

`S0.2` DF-6 → `S0.3` contexto durable → `S0.5` las 754 filas → integración
por PR → cierre calculado de F1 → declaración de `PC-1`.

El destino del producto está persistido en
`contexto/ARQUITECTURA_OBJETIVO.md`: la frontera económica del sistema está en
`THESIS → INVESTMENT PROPOSAL`, donde deja de explicar y empieza a decidir.
F1 y S0 no son ese producto: son lo que permite llegar a él sin volver a
perder la arquitectura, las decisiones ni la historia.
