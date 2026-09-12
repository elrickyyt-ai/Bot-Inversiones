# Estado vigente

Superficie de estado vigente del sistema. **Pequeña y acotada**: es contexto de
carga obligatoria y está sometida a un presupuesto verificado en CI.

**Referencia y valida; nunca duplica como verdad.** Si un dato tiene fuente
canónica en el código, aquí aparece la referencia y el validador comprueba que
no ha divergido. Si no la tiene, se declara como afirmación humana con fecha,
autoría y evidencia — y entonces el test verifica **trazabilidad, no veracidad**.

Validar: `python3 contexto/validar.py` · `python3 contexto/integridad.py` ·
`python3 contexto/extraccion.py`

## CURRENT STATE

Bot-Inversiones es un sistema de inteligencia financiera de apoyo a la decisión.
**No predice precios y no recomienda operaciones**: propone; el usuario ejecuta.

El motor causal está construido y cerrado de extremo a extremo — recorrido,
mecanismo, impacto y materialidad. Su cuello de botella **no es capacidad sino
insumo**: faltan observables económicos y relaciones económicas afirmativas, no
reglas. Las capas de assessment técnico y fundamental existen como cálculo pero
todavía **no como objetos contratados**, y por eso la tesis que llega al
consumidor no consume el motor causal.

Lo que es cierto hoy, con su procedencia:

| Afirmación | Valor | Fecha | Evidencia |
|---|---|---|---|
| ¿Está P5B implementado? | sí — engine/causal/valoracion.py, reglas R0-R5, 32 tests | 2026-09-12 | `commit:0c4003f` |
| ¿Está aplicada la variante C de D-49 sobre P5A? | sí — D-53, path_semantics y caminos_causales() | 2026-09-12 | `commit:ff7a4da` |
| ¿En qué punto está F1? | T1, T5 y los slices de T2/T4/T6 cerrados; T7-T10 pendientes | 2026-09-12 | `commit:8c38056` |
| ¿Está el universo histórico listo para backfill? | no — BACKFILL_READY=false, el cuello es la identidad de instrumento | 2026-09-12 | `file:informes/2026-09-08_backfill_readiness_historico.md` |

**Hacia dónde va**: la arquitectura objetivo vive en
`contexto/ARQUITECTURA_OBJETIVO.md`; el estado efectivo de cada componente lo
calcula `contexto/validar.py::estado_arquitectura()` desde su ancla de código.
Qué existe HOY es `docs/ESTADO.md` §2, y no se duplica en ninguno de los dos.

Cualquier cifra viva —número de entidades, relaciones, filas de evidencia,
estado de QA, número de tests— **no se copia aquí**: se obtiene ejecutando
`engine/knowledge/consulta.py --validar`, `engine/contract/qa.py --require-parquet`
y la suite. Copiarlas sería convertir esta superficie en una segunda fuente.

## CANONICAL REFERENCES

Dónde vive cada verdad. Aquí va la **referencia**, nunca el valor.

| Pregunta | Clase | Fuente canónica |
|---|---|---|
| ¿Qué predicados son no causales? | `CODE-ANCHORED` | `engine/knowledge/modelo.py::PREDICADOS_NO_CAUSALES` |
| ¿Qué clase semántica tiene cada predicado? | `CODE-ANCHORED` | `engine/knowledge/modelo.py::SEMANTICA_PREDICADO` |
| ¿Qué versión de reglas causales está vigente? | `CODE-ANCHORED` | `engine/causal/mecanismos.py::RULE_VERSION` |
| ¿Qué direcciones económicas admite un camino? | `CODE-ANCHORED` | `engine/causal/mecanismos.py::DIRECCIONES_CAMINO` |
| ¿Qué niveles de soporte existen? | `CODE-ANCHORED` | `engine/causal/mecanismos.py::SOPORTES` |
| ¿Qué variables observa un mecanismo? | `CODE-ANCHORED` | `engine/causal/mecanismos.py::VARIABLES_MECANISMO` |
| ¿Qué semánticas puede tener un camino causal? | `CODE-ANCHORED` | `engine/causal/caminos.py::SEMANTICAS_CAMINO` |
| ¿Qué campos tiene un CausalAssessment? | `CODE-ANCHORED` | `engine/causal/valoracion.py::CAMPOS_ASSESSMENT` |
| ¿Qué estados admite el manifiesto histórico? | `CODE-ANCHORED` | `contexto/integridad.py::ESTADOS` |
| ¿Cuántas relaciones económicas afirmativas existen? | `AMBIGUOUS` | `engine/knowledge/modelo.py::PREDICADOS_CAUSALES` **y** `engine/causal/mecanismos.py::SIN_MECANISMO` |

`relaciones_economicas_afirmativas` es **`AMBIGUOUS`** y no se resuelve: la palabra *causal*
significa dos cosas distintas en dos capas y ambas son deliberadas. El validador
comprueba que las dos fuentes **siguen discrepando**; si convergieran, la entrada
caducaría y habría que reclasificarla, no darla por resuelta.

Una pregunta sin entrada en el registro responde `UNDECLARED` — **nunca** un
valor por defecto.

## ACTIVE DECISIONS

Marcadas como vigentes por `vigencia-decisiones/v1` (58 de 58). El texto,
la evidencia y la cadena de revisiones viven en `docs/DECISIONES.md`.

D-01 · D-02 · D-03 · D-04 · D-05 · D-06 · D-07 · D-08 · D-09 · D-10 · D-11 · D-12 · D-13 · D-14 · D-15 · D-16 · D-17 · D-18 · D-19 · D-20 · D-21 · D-22 · D-23 · D-24 · D-25 · D-26 · D-27 · D-28 · D-29 · D-30 · D-31 · D-32 · D-33 · D-34 · D-35 · D-36 · D-37 · D-38 · D-39 · D-40 · D-41 · D-42 · D-43 · D-44 · D-45 · D-46 · D-47 · D-48 · D-49 · D-50 · D-51 · D-52 · D-53 · D-54 · D-55 · D-56 · D-57 · D-58

**Límite declarado, y es importante**: `docs/DECISIONES.md` **no distingue
vigente de superada de forma legible por máquina**. El protocolo prohíbe borrar
historia y las revisiones se añaden dentro de la misma entrada, así que las 58
salen marcadas. Esa distinción es deuda abierta; no se inventa aquí.

## INVARIANTS

Lo que no puede violarse, en ninguna capa:

- **El sistema nunca rellena una ausencia con una inferencia que parezca un
  hecho.** Tiene que poder decir *no existe el dato*, *no conozco la relación*,
  *el camino está incompleto*.
- **`UNKNOWN` ≠ `NEUTRAL`.** Desconocer un efecto no es afirmar que no lo hay.
- **`UNDECLARED` ≠ valor por defecto.** Ni `None` interpretable como cero, ni
  cadena vacía.
- **Ausencia ≠ cero.** Una cobertura que falta no es una cobertura de cero.
- **Proxy ≠ medición.** Un observable declarado como proxy arrastra su confusor
  y degrada el soporte; nunca asciende a medición por conveniencia.
- **Integridad point-in-time.** `available_at` se deriva, no se almacena, y
  `available_at ≤ analysis_as_of`.
- **El ticker no es identidad histórica.** Es reasignable; la identidad se
  resuelve por fecha.
- **Las reglas causales son deterministas, explícitas y versionadas.** Un LLM no
  decide un mecanismo económico.
- **No duplicar como verdad una fuente canónica.** Se referencia y se valida.
- **La historia no se borra.** Una decisión revisada conserva su cadena entera.
- **El sistema propone; el usuario ejecuta.** Sin credenciales de trading.
- **Privacidad**: obligatoria antes de tratar cualquier dato del usuario. El
  enunciado resumido está en `CLAUDE.md`; el texto íntegro, en
  `docs/00-protocolo-privacidad.md`. No se repite aquí: repetirlo sería
  duplicar dentro del propio contexto obligatorio.

## HISTORICAL POINTERS

El registro histórico **no se carga de entrada**. Se recupera bajo demanda.

| Dónde | Qué responde |
|---|---|
| `docs/ESTADO.md` | La narrativa completa: por qué cada capa se diseñó así, con la evidencia medida |
| `docs/DECISIONES.md` | Cada decisión, su evidencia y su cadena de revisiones |
| `informes/` | Qué se midió, qué se descartó y qué supuestos quedaron invalidados en cada fase |
| `contexto/historico/claude_md_estado_previo_a_F1.md` | El estado que `CLAUDE.md` declaraba antes de F1, íntegro |
| `docs/07-protocolo-de-informes.md` | Qué debe dejar cada fase |
| `git log -S` | Cuándo cambió una constante concreta |

Integridad del histórico: `python3 contexto/integridad.py` (manifiesto principal,
`docs/` + `informes/`) y `python3 contexto/extraccion.py` (mecanismo separado
para la extracción de `CLAUDE.md`).
