# Estado del sistema — punto de entrada

**Actualizado**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Último commit**: `02c31ad`

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
   ├──► P1b  Cobertura y frescura          dos ejes, nunca un enum
   │
   ├──► P3   Evidence                      vista derivada y regenerable
   │           │
   │           ├──► P4   Claims → Events
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
| **Lo derivado no se versiona** | `data/current/`, `coverage.json`, `requirements.json`, Evidence |
| **Un test que se apoya en que algo NO existe caduca** cuando ese algo se documenta | cinco tests reescritos en P5C |

---

## 5. Estado actual, medido

**Suite**: 447 tests · OK — **QA**: `STATUS: VERIFIED` — **Knowledge**: PASS (25 entidades · 48 relaciones · 10 fuentes)

```bash
python3 -m unittest discover -s tests
python3 engine/contract/qa.py --require-parquet
python3 engine/knowledge/consulta.py --validar
git status --short data/ knowledge/     # debe salir vacío
```

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
| `adapt_equity()` fecha 5 métricas con la fecha del trimestre | `cadencias.DEFECTO_DE_FECHADO` | Reescribiría filas ya en el contrato |
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

Roadmap acordado: `P6.2 Quantification unlocks` → `P7 Market Impact` → `P8 Mispricing` → `P9 Thesis` → `P10 Portfolio` → `P11 Outcome/Calibration`. Power BI y Web App consumirán una proyección del motor; no lo dictan.

---

## 8. Cómo se documenta este proyecto

`docs/07-protocolo-de-informes.md` fija qué debe dejar cada fase. En resumen: diseño → informe de implementación → hallazgos → decisiones y desviaciones → deudas → tests/QA → trazabilidad acumulada. **Cuando un descubrimiento cambia una decisión anterior, la historia no se borra**: queda `decisión original → evidencia nueva → revisión → decisión vigente` en `docs/DECISIONES.md`.
