# Estado del sistema — punto de entrada

**Actualizado**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Último commit**: `P6.2a-d`

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
   │           │
   │           └──► P5D  Data Requirements  ¿existe el dato que el mecanismo pide?
   │
   └──► P2   KNOWLEDGE (a mano, versionado)  entidades · relaciones · conceptos · fuentes
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
| P6.2a | *(este commit)* | Integridad temporal: los cinco relojes, `available_at` derivado |
| P6.2b | *(este commit)* | Look-ahead de 22-31 días corregido en 27 filas |
| P6.2c | *(este commit)* | Event study mínimo: 52 eventos, `first_tradable_at`, sin agregar |
| P6.2d | *(este commit)* | Episodios declarados sobre P4: 50 documentos → 43 eventos → 1 episodio |

Detalle por fase, con qué se rompe si cae y cómo recuperarla: `informes/2026-09-07_trazabilidad_fases_P0_P61.md`.

---

## 4. Por qué se diseñaron así — la evidencia detrás de las decisiones

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
| **Un test que se apoya en que algo NO existe caduca** cuando ese algo se documenta | cinco tests reescritos en P5C |

---

## 5. Estado actual, medido

**Suite**: 491 tests · OK — **QA**: `STATUS: VERIFIED` — **Knowledge**: PASS (25 entidades · 48 relaciones · 10 fuentes)

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
| **Sin benchmark en el contrato** | D-21 · informe de P6.2 §12 | Bloquea el retorno anormal y con él cualquier agregación. Recomendación `DimBenchmark`; **sin resolver para cripto**, que es el 60% del contrato |
| **Fecha de publicación de las series macro** | `temporal.RETRASO_PUBLICACION_DECLARADO` | Vive en ALFRED (vintages), no en FRED. 2.148 filas acotadas por cota conservadora, no corregidas |
| **Dirección causal noticia↔precio** | informe de P6.2 §10 | Una noticia puede escribirse *porque* el precio ya se movió. No se representa; no se inventa un campo que no se pueda rellenar |
| **`reportTime` ausente en las fixtures antiguas de equity** | `tests/fixtures/equity/*_earnings.json` | 8 trimestres sin ese campo, así que `momento_publicacion` sale `None`. La ingesta manual debe guardar el payload completo |
| `desempleo_pct` y `spread_10y2y_pct` no llegan al contrato | `thesis.py::_MACRO_CONTEXTO` | Decisión de alcance |
| HBM y sustrato ABF sin fuente | `knowledge/pendiente/nvidia_cadena.json` | Buscados en los dos filings: cero menciones |
| Samsung / SK Hynix / Micron | `knowledge/pendiente/` | **Ya tienen fuente verificada**; fuera del alcance acordado, promovibles en un paso |
| `tech:cowos` se evalúa como insumo de coste, no como restricción de capacidad | informe de P6 | P5B enruta por R5; decisión de no tocar P5B |
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

**Segunda decisión abierta, nueva**: dónde vive el benchmark (D-21). Bloquea el retorno anormal y, con él, cualquier agregación de reacciones. Recomendación razonada en `informes/2026-09-07_integridad_temporal_y_event_study_mvp.md` §12, **sin resolver para cripto**.

Roadmap acordado: `P6.2 Quantification unlocks` → `P7 Market Impact` → `P8 Mispricing` → `P9 Thesis` → `P10 Portfolio` → `P11 Outcome/Calibration`. Power BI y Web App consumirán una proyección del motor; no lo dictan.

---

## 8. Cómo se documenta este proyecto

`docs/07-protocolo-de-informes.md` fija qué debe dejar cada fase. En resumen: diseño → informe de implementación → hallazgos → decisiones y desviaciones → deudas → tests/QA → trazabilidad acumulada. **Cuando un descubrimiento cambia una decisión anterior, la historia no se borra**: queda `decisión original → evidencia nueva → revisión → decisión vigente` en `docs/DECISIONES.md`.
