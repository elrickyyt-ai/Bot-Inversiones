# Arquitectura objetivo

**Qué sistema se está construyendo y cómo se relacionan sus componentes.**

Este documento **no dice qué existe hoy**. Eso vive en `docs/ESTADO.md` §2
(«Arquitectura actual»), es su autoridad y aquí no se duplica: duplicarlo
convertiría este fichero en una segunda copia del estado del código, que es
exactamente el fallo que hace que un documento de arquitectura sea ficción a
los tres meses.

El reparto es:

| Dónde | Qué responde |
|---|---|
| `docs/ESTADO.md` §2 | **qué existe** actualmente, con su evidencia medida |
| este documento | **qué sistema se construye** y cómo encajan sus piezas |
| `contrato.json::arquitectura_objetivo` | estados **declarados** y sus anclas |
| `validar.py::estado_arquitectura()` | estado **efectivo**, calculado del código |

Ver el estado real: `python3 contexto/validar.py`

---

## 0. System Operating Model

Este proyecto tiene **dos dimensiones de arquitectura superpuestas**, y
confundirlas es un error que ya se ha cometido una vez:

| Dimensión | Qué responde | Cómo se representa |
|---|---|---|
| **A · Arquitectura de producto/decisión** | *qué produce el sistema* | los componentes de `contrato.json::arquitectura_objetivo`, con estado y ancla |
| **B · System Operating Model** | *cómo decide el sistema qué trabajo hacer, qué cargar y qué flujo seguir* | **solo este flujo conceptual**, sin componentes, sin estados y sin maquinaria |

```
   PROJECT
      │
      ▼
    TASK
      │
      ▼
   COMPLEXITY GATE            ¿cuánto trabajo pide esto de verdad?
      │
      ▼
   CONTEXT / RESOURCE         qué contexto y qué fuentes hacen falta,
   RESOLUTION                 y ninguna más
      │
      ▼
   WORKFLOW
      │
      ├──► RESEARCH
      ├──► ANALYSIS
      └──► VERIFICATION
```

**B NO está en el registro de componentes, y es deliberado.** No recibe
`IMPLEMENTED`, `PARTIAL`, `PLANNED` ni `NOT_AUTHORIZED`: es un modelo
operativo, no una capacidad de producto, y darle estados lo convertiría en
una hoja de ruta de implementación que nadie ha autorizado.

Lo que sigue prohibido es la **maquinaria**, no el concepto: sin Task Router,
sin agentes ni subagentes, sin skills, sin hooks, sin framework de
orquestación. B describe cómo se trabaja; no manda construir nada que lo
ejecute.

F1 y S0 son, de hecho, las primeras piezas reales de B: el presupuesto de
`contexto:L0`, el cierre efectivo y el alcance por bloque **son** resolución
de contexto y recursos, hecha a mano y verificada en CI.

---

## La regla que sostiene este documento

```
"está en la arquitectura"   !=   "está implementado"
```

Se impide por mecanismo, no por disciplina. De los cuatro estados, **solo uno
se deriva**:

| Estado | Naturaleza | Regla que lo comprueba |
|---|---|---|
| `IMPLEMENTED` | **DERIVADO** del ancla de código | declararlo sin ancla resoluble falla |
| `PARTIAL` | declarativo | existe en código pero no como objeto contratado; exige ancla |
| `PLANNED` | declarativo | arquitectura objetivo, sin implementación; exige ancla nula |
| `NOT_AUTHORIZED` | declarativo | capacidad deliberadamente fuera de las autorizadas; exige ancla nula |

Los tres declarativos **no pueden calcularse**: la ausencia de código no dice
si algo está planificado o prohibido. Y la comprobación va en los dos
sentidos, que es lo que la hace útil: si aparece código bajo un componente
declarado `PLANNED`, el validador lo detecta en vez de dejar que la
declaración envejezca en silencio.

### `NOT_AUTHORIZED` no significa «todavía no implementado»

Es la distinción más importante de este vocabulario, y no es sinónimo de D-01.

- **D-01** — *el sistema propone, el usuario ejecuta* — es una decisión de
  producto sobre **quién actúa**.
- **`NOT_AUTHORIZED`** es un estado de **capacidad**: esta pieza no está entre
  las autorizadas en el estado actual del sistema.

Están relacionados —D-01 es la razón por la que `EXECUTION_GATE` y
`BROKER_ORDER` lo están— pero no son la misma cosa: una capacidad podría
dejar de estar autorizada por motivos ajenos a D-01, y D-01 seguiría siendo
cierto aunque existiese una ejecución autorizada y supervisada.

`INVESTMENT_PROPOSAL` es `PLANNED`, no `NOT_AUTHORIZED`: se va a construir.
`BROKER_ORDER` es `NOT_AUTHORIZED`: hoy no se va a construir.

---

## Granularidad: 29 componentes no son 29 capacidades nuevas

El registro descompone la arquitectura objetivo en **29 componentes**. Ese
número es una **descomposición normativa** de este documento, elegida para que
cada pieza tenga un ancla comprobable — **no una afirmación de que se hayan
añadido capacidades** respecto de esquemas anteriores.

Los diseños previos contaban con otra granularidad: la cadena conceptual de
origen enumeraba 26 eslabones, y `docs/00-arquitectura-conceptual.md` (Fase 0)
describía 10 capas. Los tres describen el mismo sistema con cortes distintos.
Si dentro de seis meses aparece «arquitectura v1 = 26 / v2 = 29», la respuesta
es que **cambió el corte, no el alcance**.

Cambiar el número exige decirlo aquí. Añadir una capacidad exige una decisión
registrada en `docs/DECISIONES.md`, que es otra cosa.

Los `id` son cadenas estables (`DATA`, `EVIDENCE`, `INVESTMENT_PROPOSAL`…) y
son la clave por la que el validador resuelve cada ancla: renombrarlos rompe
la trazabilidad, así que no se renombran por estética.

---

## La cadena

La mitad superior está construida. **La mitad inferior es objetivo, no
implementación** — el estado real de cada pieza lo da el validador, no este
dibujo.

```
   DATA ──► EVIDENCE ──► EVENT/CLAIM ──► KNOWLEDGE ──► CAUSAL PATH
                                                            │
                                          CAUSAL ASSESSMENT ◄┘
                                                 │
                              ECONOMIC IMPACT ──► MATERIALITY
                                                       │
                 TECHNICAL ASSESSMENT ──┐              │
                                        ├──────────────┴──► THESIS
               FUNDAMENTAL ASSESSMENT ──┘                     │
   ═══════════════════════════════════════════════════════════│═══════
   ↑ implementado                            objetivo ↓       │
                                                              ▼
                                                  INVESTMENT PROPOSAL
                                                              │
                                                       RISK ASSESSMENT
                                                              │
                                                  INDEPENDENT VERIFY
                                                              │
                                            ┌─────────────────┴────┐
                                            ▼                      ▼
                                     HUMAN APPROVAL        AUTONOMY POLICY
                                            └──────────┬───────────┘
                                                       ▼
                                                EXECUTION GATE   ⛔
                                                       │
                                                  BROKER/ORDER   ⛔
                                                       │
                                                    OUTCOME
                                                       │
                                                LEARNING ENGINE
                                                       │
                                             CANDIDATE IMPROVEMENT
                                                       │
                                            ┌──────────┴──────────┐
                                            ▼                     ▼
                                        BACKTEST              RISK TEST
                                            └──────────┬──────────┘
                                                       ▼
                                                      OOS
                                                       │
                                                    SHADOW
                                                       │
                                              HUMAN/POLICY GATE
                                                       │
                                               POLICY REGISTRY
                                                       │
                                                 NEW VERSION

   RUN = trazabilidad transversal de extremo a extremo
   ⛔  = NOT_AUTHORIZED
```

### La frontera económica del sistema

```
   THESIS               interpreta y EXPLICA una oportunidad
      │
      ▼                 ←── aquí el sistema deja de analizar
   INVESTMENT PROPOSAL  transforma la tesis en una DECISIÓN CANDIDATA
      │
      ▼
   EXECUTION + FEEDBACK
```

Todo P1-P6.2 no fue «construir más analytics»: es el núcleo que hace que esa
decisión candidata sea auditable en vez de una recomendación arbitraria.

### `INVESTMENT PROPOSAL` es el puente, no una capa más

```
hasta THESIS          el sistema EXPLICA
desde PROPOSAL        el sistema DECIDE
```

Es capa propia porque **una misma tesis puede dar `BUY`, `WAIT` o
`NO_ACTION`** según valoración, riesgo, exposición, horizonte y condiciones de
entrada. Convertir una tesis directamente en una orden borraría esa
distinción, y con ella la posibilidad de medir si la *decisión* —no la
explicación— generó rendimiento.

Todo el núcleo epistemológico existente es lo que hace que una Proposal pueda
decir *«esta decisión no apareció de la nada»* y reconstruir su cadena causal.
Ese es el activo técnico del sistema, no el veredicto.

---

## Tres bucles, no una cadena lineal

```
   DECISIÓN     EVIDENCE → CAUSAL → THESIS → PROPOSAL → RISK → VERIFY → APPROVAL
   EJECUCIÓN    EXECUTION GATE → BROKER/ORDER → OUTCOME
   APRENDIZAJE  OUTCOME → LEARNING → CANDIDATE → BACKTEST/RISK TEST
                       → OOS → SHADOW → POLICY GATE → POLICY REGISTRY → NEW VERSION
                                                               │
                       └───────────────────────────────────────┘
                              la política nueva gobierna la decisión siguiente
```

Están separados a propósito. El sistema se realimenta, y la realimentación
tiene una regla dura:

> **`learning` nunca modifica una política activa de forma directa.**
> Un cambio aprendido recorre `candidate → validación → OOS → shadow →
> aprobación → versión nueva`.

**Y el bucle de aprendizaje NO existe todavía.** `BACKTEST` está `PARTIAL`
porque hay *event study* y `HistoricalReactionProfile v1` sobre 52 eventos
reales, descriptivos — **eso no es backtesting de política**. El ciclo
`candidate → backtest → risk test → OOS → shadow → promotion` no está
construido en ninguna de sus etapas. Que exista análisis histórico no debe
leerse como que exista validación de políticas: son cosas distintas y el
`PARTIAL` solo cubre la primera.

Y `RUN` no es decoración: es la infraestructura epistemológica de la propia
decisión. **Cada RUN conserva la `policy_version` exacta** con la que se
tomó, para que una decisión histórica no pueda reinterpretarse bajo una
política posterior.

---

## Autonomía — `autonomia:L0..L4`

```
autonomia:L0   READ
autonomia:L1   ANALYZE
autonomia:L2   PROPOSE
autonomia:L3   HUMAN-APPROVED EXECUTION     ← techo inicial
autonomia:L4   BOUNDED AUTONOMY             ← no se contempla en este estado
```

Con **`deny by default`**: la política de autonomía está por encima del
agente, y lo no autorizado no se ejecuta.

**El namespace es obligatorio.** `L0` es un token con dos significados en este
proyecto:

| Namespace | Qué es | Estado |
|---|---|---|
| `contexto:L0` | nivel de **carga de contexto** obligatoria | implementado: `contrato.json::L0`, `presupuesto_L0`, `l0-budget/v1`, `l0-closure/v1`, la suite y el CI |
| `autonomia:L0..L4` | escalera de **autonomía** | no implementada: 0 ocurrencias en el árbol |

No son dos usos con igual derecho: uno está implementado en seis sitios y el
otro es intención. Por eso **no se renombra el mecanismo implementado** para
acomodar al ausente. La coincidencia léxica queda registrada como deuda
(`DC-5`), sin resolver.

---

## Qué está deliberadamente prohibido

- Sin credenciales de trading en ninguna parte del sistema (**D-01**).
- `learning` → política activa, nunca directo.
- Un LLM no decide un mecanismo económico: las reglas causales son
  deterministas, explícitas y versionadas.
- `Mispricing` no existe todavía: exige magnitud económica real y no puede
  calcularse sobre `UNKNOWN`.
- No calibrar pesos con `n=0` predicciones evaluadas.
- **Sin Task Router, agentes, subagentes, skills, hooks ni framework de
  orquestación.** Lo prohibido es la maquinaria, no el concepto: el System
  Operating Model del §0 se conserva como flujo —define cómo trabaja el
  sistema— y precisamente por eso no aparece en el registro de componentes ni
  recibe estados. Convertir `TASK` o `WORKFLOW` en componentes con estado
  habría sido introducir una hoja de ruta de orquestación por la puerta de
  atrás.

---

## Producto frente a infraestructura de desarrollo

Dos ejes distintos que conviene no confundir:

| | Qué gobierna | Dónde |
|---|---|---|
| `P0…P11` | **roadmap de producto** | `docs/ESTADO.md`, `informes/…trazabilidad_fases_P0_P61.md` |
| `F1 / S0 / PC-1` | **alcance de escritura** por bloque | `contrato.json::bloques` |
| `Fase 0…10` | esquema histórico, **citado por D-01 vigente** | `docs/00-arquitectura-conceptual.md` |

`P7` dice *qué se construye*; `S0` dice *qué puede escribirse ahora*. Los tres
vocabularios se conservan y ninguno se renombra. **La relación de `PC-1` con
`P7…P11` no está declarada**: es deuda `DD-4`, no una omisión silenciosa.

**F1 y S0 no son el producto financiero.** Son lo que permite que el producto
siga evolucionando sin perder su arquitectura, sus decisiones ni su historia.

---

## De dónde viene esto

| Dónde | Qué |
|---|---|
| `docs/00-arquitectura-conceptual.md` | Fase 0, capas 0-9. **Histórico**: la arquitectura real ya no lo sigue, y no se reescribe |
| `docs/ESTADO.md` | arquitectura actual y su evidencia medida |
| `informes/…trazabilidad_fases_P0_P61.md` | fase → commit → comando de verificación |
| `docs/DECISIONES.md` | D-01…D-53 |
