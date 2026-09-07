# Trazabilidad de las fases P0 → P5B

**Fecha**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Último commit**: `0c4003f`

Este informe existe para una situación concreta: **que una fase falle en el futuro y haya que recuperar su estado**. Da, por cada fase, el commit exacto, los ficheros que la componen, los tests que la cubren, el comando que la verifica por separado y qué se rompe si cae.

No sustituye a los README de cada módulo (que explican *por qué* está hecho así). Este documento responde a *dónde está* y *cómo se comprueba*.

---

## Verificación completa en tres comandos

```bash
python3 -m unittest discover -s tests           # 329 tests, debe dar OK
python3 engine/contract/qa.py --require-parquet # debe dar STATUS: VERIFIED
git status --short data/ knowledge/             # debe salir vacío
```

Si los tres pasan, las once fases están sanas. Si falla alguno, la tabla de abajo dice qué fase mirar.

---

## Mapa de fases

| Fase | Commit | Qué hace | Verificación aislada |
|---|---|---|---|
| **Migración** | `6c167e6` → `d27f162` | JSON → `history/` (parquet) + `incoming/` (CSV) | `python3 -m unittest tests.test_storage_core tests.test_storage_parquet` |
| **P1** | `b5bd426` | `fecha_dato` deja de ser la hora de ejecución | `python3 -m unittest tests.test_engines.TestIntegridadTemporalDeLosMotores` |
| **P1b** | `0726049` | Cobertura y frescura como dos ejes | `python3 engine/contract/cobertura.py` |
| **P1 cierre** | `bb76054` | La tesis declara su evidencia y su validez | `python3 -m unittest tests.test_tesis_evidencia` |
| **P2** | `5f4efa1` | Knowledge Model v1 (la capa 0 de la Fase 0) | `python3 engine/knowledge/consulta.py --validar` |
| **P3** | `228b228` | Evidence v1, vista derivada | `python3 engine/evidence/construir.py --reversibilidad 2000` |
| **P4** | `a9ba0c6` | Event & Claim Layer v1 | `python3 engine/events/consolidar.py --noticias` |
| **P5A** | `b214082` | Causal Path / traversal | `python3 engine/causal/caminos.py sec:NVDA.NASDAQ` |
| **P5B** | `0c4003f` | Mecanismo y dirección económica | `python3 engine/causal/valoracion.py sec:NVDA.NASDAQ` |

---

## Detalle por fase

### Migración de almacenamiento — `6c167e6`, `3a1b087`, `8619f73`, `f0e0e35`, `7637e8a`, `05449b0`, `d27f162`

**Ficheros**: `engine/contract/storage.py` · `migrar.py` · `verificar_migracion.py` · `compactar.py` · `materializar.py` · `qa.py` · `build.py` · `data/history/**` · `data/incoming/*.csv`

**Estado**: 507.330 filas, 0 duplicados de clave lógica. `history/` son particiones anuales inmutables con manifiesto (SHA-256 + filas + rango + revisión). `incoming/` es el año en curso en CSV, escrito por el cron sin PyArrow.

**Si falla**: es la base de todo. Un fallo de hash en el manifiesto significa que una partición cerrada cambió — `qa.py` lo detecta antes que ninguna otra cosa. La recuperación es `git checkout` de la partición, **no** regenerarla.

**Recuperación**: `git checkout <commit> -- data/history/` restaura las particiones. `engine/contract/verificar_migracion.py` reejecuta las 8 comprobaciones de equivalencia.

---

### P1 · Integridad temporal — `b5bd426`

**Ficheros**: `engine/macro/score.py` (líneas 121, 172 del original) · `engine/equity/score.py` (línea 80) · `tests/test_engines.py`

**Qué cambió**: `fecha_dato` era `datetime.now()` en los dos motores. Ahora hay `fechas_dato` por métrica y `fecha_dato` es la del componente **más antiguo**.

**Tests clave**: `TestIntegridadTemporalDeLosMotores` — guardia transversal sobre los cinco motores que compara contra la fecha de hoy. **Se vuelve más exigente con el tiempo**, y falla si alguien reintroduce `now()` en cualquier motor, incluido uno nuevo.

**Si falla**: `test_las_fixtures_siguen_congeladas_en_el_pasado` falla si alguien regenera las fixtures con datos del día — entonces el test anterior deja de discriminar. Es el único falso positivo posible y está cubierto.

---

### P1b · Cobertura y frescura — `0726049`

**Ficheros**: `engine/contract/cadencias.py` (declaración) · `cobertura.py` (evaluación) · `qa.py` (bloque informativo) · `build.py` · `tests/test_cobertura.py`

**Invariante**: `cadencias.py` **declara**, no mide. Lo no declarado queda `UNKNOWN`, que no es permisivo. La cadencia es `(unidad, n)` con unidad `sesion` o `dia`.

**Artefacto derivado**: `data/coverage.json`, gitignored, recalculado en cada `build.py`.

**Si falla**: el bloque de `qa.py` es informativo y **nunca** hace fallar el QA. Un fallo aquí no bloquea el cron por diseño.

---

### P1 cierre · Evidencia de la tesis — `bb76054`

**Ficheros**: `engine/reasoning/thesis.py` (`EVIDENCIA_CRYPTO`, `EVIDENCIA_EQUITY`) · `engine/contract/schema.py` · `adapters.py` · `cadencias.py` · `docs/04-modelo-power-bi.md` · `tests/test_tesis_evidencia.py`

**Regla**: sólo la evidencia `REQUERIDA` invalida. `PUBLICADA` y `CONTEXTO` generan advertencia. Si la validez no es `VALID`, `confidence_pct` es `None` — y `schema.py` **rechaza** la combinación contraria.

**Si falla**: una tesis con `evidence_validity` distinto de `VALID` y `confidence_pct` no nulo hace fallar `validate_thesis_row`. Eso pararía `build.py`, que es el comportamiento buscado.

---

### P2 · Knowledge Model — `5f4efa1`

**Ficheros**: `engine/knowledge/modelo.py` · `consulta.py` · `knowledge/entities/*.json` (23) · `relationships/*.json` (45) · `concepts/concepts.json` (3) · `sources/sources.json` (8) · `knowledge/pendiente/nvidia_cadena.json` · `tests/test_knowledge.py`

**Cuatro reglas del validador**: fuente resoluble · `nature` no admite `INFERRED` · toda relación tiene vigencia · negar exige fuente igual que afirmar.

**`knowledge/` SÍ se versiona** (a diferencia de `data/current/` y `data/coverage.json`): son ~50 filas mantenidas a mano y su historial de cambios *es* información.

**Si falla**: `python3 engine/knowledge/consulta.py --validar` da `FAIL` con la lista de incidencias. `modelo.py` no tiene ninguna función de escritura, así que una corrupción sólo puede venir de una edición manual o de un merge.

---

### P3 · Evidence — `228b228`

**Ficheros**: `engine/evidence/esquema.py` · `adaptadores.py` · `construir.py` · `tests/test_evidence.py`

**No es un fichero por defecto**: es un generador. 507.430 filas (507.330 métricas 1:1 + 100 noticias). `--materializar` escribe `data/evidence/*.jsonl`, gitignored.

**Reversibilidad**: `original → Evidence → reconstrucción` con 0 diferencias sobre las 15 columnas. La reconstrucción es **Evidence + DimAsset** (`asset_type` es atributo estático del activo).

**Si falla**: `construir.py --reversibilidad 2000` da `FAIL` con las diferencias campo a campo. Ese comando es el diagnóstico.

---

### P4 · Event & Claim — `a9ba0c6`

**Ficheros**: `engine/events/esquema_evento.py` · `extractores.py` · `consolidar.py` · `tests/fixtures/eventos/casos.json` · `tests/test_events.py`

**Medido**: noticias 100 Evidence → 50 claims → 43 eventos. Técnico XRP: 3.628 → 219 → 219, con 67 `CONFIRMED`.

**Nota de nombres**: el módulo se llama `esquema_evento.py` y **no** `esquema.py` porque chocaba con `engine/evidence/esquema.py`. Hay una guardia en `tests/test_events.py::test_los_nombres_de_modulo_de_engine_son_unicos` que falla si vuelve a aparecer un duplicado. **Tercera vez que esta colisión rompió tests de otra capa**; la guardia es la mitigación.

---

### P5A · Causal Path — `b214082`

**Ficheros**: `engine/causal/caminos.py` · `tests/fixtures/caminos/casos.json` · `tests/test_caminos.py`

**Cerrado y no se modifica.** Hay un test en P5B (`test_p5a_no_se_ha_tocado`) que comprueba que `caminos.py` no importa nada de P5B.

**Medido**: profundidad 1/2/3 → 4/25/89 caminos desde NVDA. Vigencia real: XRP↔Coinbase inalcanzable a 2022-01-01, alcanzable a 2024-01-01.

---

### P5B · Mecanismo y dirección económica — `0c4003f`

**Ficheros**: `engine/causal/mecanismos.py` · `valoracion.py` · `tests/fixtures/valoracion/casos.json` · `tests/test_valoracion.py`

**Resultado real hoy**: los 25 caminos desde NVDA dan `UNKNOWN`. Tres motivos medidos, y hay un test por cada uno que fallará el día que dejen de ser ciertos:
- `test_no_existe_ninguna_relacion_economica_afirmativa` — cero `SUPPLIES`/`USES`/`SUBSTITUTES` afirmativas
- `test_ninguna_variable_de_mecanismo_existe_en_evidence_v1` — cero métricas de demanda, capacidad, coste de insumo, inventario o plazo
- `test_las_aristas_de_identidad_no_transmiten_nada` — las cuatro verificadas son de identidad

**Esos tres tests son deliberadamente frágiles**: están puestos para romperse cuando el conocimiento crezca. Si fallan, no hay que arreglarlos: hay que actualizarlos y comprobar que P5B empieza a producir algo distinto de `UNKNOWN`.

---

## Dependencias entre fases

```
Data Contract (migración)
    │
    ├─→ P1  integridad temporal   (motores → contrato)
    ├─→ P1b cobertura/frescura    (lee incoming/, opcionalmente history/)
    │        └─→ P1 cierre        (thesis.py usa cadencias.py)
    ├─→ P3  Evidence              (lee el contrato + P2 para entidades)
    │        └─→ P4  Event        (lee Evidence)
    └─→ P2  Knowledge  ───────────┴─→ P5A Path  ─→ P5B Assessment
```

**La dirección es única**: cada capa lee la anterior y **ninguna escribe hacia atrás**. Está comprobado por hash dentro de la propia suite en P3, P4, P5A y P5B.

---

## Invariantes transversales del proyecto

Reglas que han aparecido más de una vez y que conviene no volver a romper:

1. **Ausencia ≠ evidencia de ausencia.** Tres apariciones: `NO_APLICA` en P1b (TVL de BTC), `polarity=DENIES` en P2, y la comprobación de sustitución de tres estados en P5B.
2. **Nunca reutilizar un vocabulario para conceptos distintos.** Tres apariciones: `source_priority` (P0), `nature` en Knowledge vs Evidence (P3), y las tres direcciones (P5B) — resuelto usando `DIVERGENT` en vez de `MIXED`. Los conjuntos deben ser **disjuntos** y hay tests que lo mantienen.
3. **Dos ejes, no un enum.** Cobertura y frescura (P1b), validez y completitud (P5A).
4. **La fecha del bloque es la del componente más antiguo**, nunca la del más reciente.
5. **Nombres de módulo únicos en `engine/`** salvo `score.py` y `fetch_data.py`, que se repiten a propósito. Guardia en `tests/test_events.py`.
6. **Un test no debe inspeccionar la prosa.** Dos veces escribí tests que buscaban palabras en comentarios y encontraban justo la documentación que explica que esa cosa no existe. Se comprueban esquemas y comportamiento.

---

## Deudas registradas y no corregidas

| Deuda | Dónde está registrada | Por qué no se corrigió |
|---|---|---|
| `adapt_equity()` escribe `pe_ratio`, `peg_ratio` y las tres `analyst_*` con la fecha del trimestre | `cadencias.py::DEFECTO_DE_FECHADO` + test que impide taparlo | Reescribiría filas ya en el contrato; tarea posterior a P2 |
| `desempleo_pct` y `spread_10y2y_pct` se descargan de FRED y no llegan al contrato | `thesis.py::_MACRO_CONTEXTO` + `cadencias.py` | Decisión de alcance; la pendiente 10a-2a es la serie macro más fresca (2 días) |
| `CLAUDE.md` describe `data/metrics/*.json`, que ya no existe | acordado dejarlo | Documentación desfasada, sin impacto funcional |
| `consolidate.py` huérfano | — | No lo consume nadie |
| `confluencia_sesgo` emite dos vocabularios distintos para cripto y acciones | P0 | Excluido de la migración a propósito |
| Seed B de NVIDIA sin fuente | `knowledge/pendiente/nvidia_cadena.json` | Entrará por el procedimiento de alta de P2, no antes |

---

## Cómo recuperar una fase concreta

```bash
# Ver qué tocó una fase
git show --stat <commit>

# Recuperar sólo sus ficheros de código, sin tocar el resto
git checkout <commit> -- engine/<modulo>/ tests/test_<modulo>.py

# Comprobar que la fase vuelve a estar sana
python3 -m unittest tests.test_<modulo>
python3 -m unittest discover -s tests   # y que no rompió nada más
```

**Nunca** recuperar `data/history/` regenerándolo: son particiones inmutables con manifiesto y la recuperación correcta es `git checkout`, no una nueva escritura.
