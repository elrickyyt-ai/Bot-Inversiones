# Trazabilidad de las fases P0 → P6.1

**Fecha**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Último commit**: `02c31ad`

Este informe existe para una situación concreta: **que una fase falle en el futuro y haya que recuperar su estado**. Da, por cada fase, el commit exacto, los ficheros que la componen, los tests que la cubren, el comando que la verifica por separado y qué se rompe si cae.

No sustituye a los README de cada módulo (que explican *por qué* está hecho así). Este documento responde a *dónde está* y *cómo se comprueba*.

---

## Verificación completa en tres comandos

```bash
python3 -m unittest discover -s tests           # 708 tests, debe dar OK
python3 engine/contract/qa.py --require-parquet # debe dar STATUS: VERIFIED
git status --short data/ knowledge/             # debe salir vacío
```

Si los tres pasan, las veintidós fases están sanas. Si falla alguno, la tabla de abajo dice qué fase mirar.

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
| **P5C** | `61dca44` | Primera cadena económica real, con fuentes externas | `python3 -m unittest tests.test_cadena_suministro` |
| **P5D** | `cfbf38b` | Evidence Gap → Data Requirement | `python3 engine/requirements/resolver.py org:nvidia` |
| **P6** | `4f22a88` | Economic Impact v1 | `python3 engine/impact/impacto.py org:nvidia` |
| **P6.1** | `02c31ad` | Materiality derivada | `python3 -m unittest tests.test_materialidad` |
| **P6.2a** | `f30ffc5` | Integridad temporal: los cinco relojes | `python3 -m unittest tests.test_temporal` |
| **P6.2b** | `f30ffc5` | Look-ahead corregido en la familia `earnings_*` | `python3 engine/contract/qa.py` → bloque `INTEGRIDAD TEMPORAL` |
| **P6.2c** | `f30ffc5` | Event study mínimo sobre resultados | `python3 engine/events/estudio_resultados.py` |
| **P6.2d** | `f30ffc5` | Episodios declarados sobre P4 | `python3 -m unittest tests.test_episodios` |
| **D-21** | `2ee412a` | Ontología de benchmark y elegibilidad por familia | `python3 -m unittest tests.test_benchmark_ontologia` |
| **D-21 (datos)** | `22ef8aa` | `bm:sp500` declarado y consumido por el event study | `python3 -m unittest tests.test_benchmark_sp500` |
| **HRP v1** | `f4156fe` | Perfiles históricos descriptivos, 20 celdas con estado | `python3 engine/events/perfil_reaccion.py` |
| **HRP v1.1** | `c44120a` | Ventana de estimación, dependencia y solapamiento: `descriptive` ≠ `predictive` | `python3 engine/events/diagnostico_cohorte.py` |
| **Población** | `f1b0d38` | Universo congelado, cobertura de fuente y reproducibilidad histórica | `python3 engine/events/universo.py` |
| **Autoridad** | `646c72d` | Qué fuente manda sobre cada componente del evento | `python3 engine/events/autoridad.py` |
| **Identidad** | `0fa7bc3` | Identidad histórica de instrumento y transformaciones | `python3 engine/events/identidad.py` |
| **Corporate actions** | `PENDIENTE` | Contaminación de ventanas por transformaciones de instrumento | `python3 engine/events/cobertura_acciones.py` |

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

---

### HRP v1.1 · Diagnóstico de cohorte — D-27 revisada · D-29 · D-30 · D-31

**Ficheros**: `engine/events/diagnostico_cohorte.py` (nuevo) · `engine/events/perfil_reaccion.py` · `engine/events/estudio_resultados.py` · `tests/test_diagnostico_cohorte.py` (nuevo, 12 tests) · `tests/test_perfil_reaccion.py` (+10)

**Qué añade sobre HRP v1**: no calcula perfiles nuevos; mide si los que hay son **interpretables**.

- `estimation_window` `[-20,-1]` separada de `reaction_window`, con la disponibilidad medida: **52/52** completas, 0 contaminadas, 0 huecos de volumen.
- Base del volumen elegida **por medición**, no por costumbre: la media está contaminada al alza en el **90%** de las ventanas y el z-score llega a **16,92** → mediana. `VOLUME_RELATIVE_TO_PRE_EVENT` **2,04 → 1,26 → 1,06 → 1,01**.
- Volatilidad: mismo razonamiento, resultado distinto → `INSUFFICIENT_METHODOLOGY` (media móvil de 30 sesiones que solapa su propia base).
- `descriptive_status` ≠ `predictive_status`; toda la rejilla `NOT_EVALUATED`.
- Solape **marcado** (`FLAG`), no eliminado: 0 · 0 · 0 · **3/49**, con `statistics_non_overlapping` publicada al lado.
- **Hallazgo**: contaminación estructural ≠ solapamiento técnico. `2_60d` solapa el 6% y cubre el **94,5%** del trimestre (intervalo mediano **63,5 sesiones**).

**Tests deliberadamente frágiles**, puestos para romperse cuando la arquitectura cambie:
- `test_el_modulo_no_publica_ninguna_formula_de_n_effective` — se rompe el día que se introduzca `n_effective`, que es cuando hay que releer D-31.
- `test_ningun_motor_de_decision_importa_el_perfil` — se rompe el día que un scorer consuma el perfil, que es cuando hay que releer D-29.
- `test_el_umbral_10_de_pct_in_window_no_se_ha_vuelto_global` (de D-22) — se rompe si el `[-20,-1]` se propaga a `engine/crypto/score.py`.

**Qué se rompe si cae**: nada aguas abajo — ningún consumidor lee el perfil, por diseño. Lo que se pierde es la capacidad de decir **por qué** un perfil no es interpretable, y con ella la barrera contra usarlo como señal.

**Informe**: `informes/2026-09-07_d27_dependencia_y_solapamiento.md`.

---

### Población · Universo congelado y cobertura — D-32 · D-33 · D-34 · D-35

**Ficheros**: `engine/events/universo_v1.json` · `cobertura_universo_v1.json` · `_cobertura/*.txt` · `universo.py` (todos nuevos) · `perfil_reaccion.py` · `tests/test_poblacion_universo.py` (nuevo, 25 tests)

**Qué añade**: no ingiere nada. Mide si existe población para arreglar `n_assets = 3`.

- `universe:v1:djia-2019`, **31 activos · 9 sectores**, congelado a 2019-01-01, con 6 exclusiones motivadas.
- Cobertura de 6 activos: **488 trimestres**, 4 series contiguas de 122, **0 `reportTime` ausentes**, 8 `estimatedEPS` ausentes (AAPL, pre-2004).
- **Hallazgo**: la fuente **solo conoce supervivientes** — DWDP y UTX devuelven vacío y no están en el directorio de símbolos.
- **Hallazgo operativo**: `reportTime` **no es constante por activo** (MSFT mezcla pre y post).
- `horizon_class` (`2_60d` = `LONGER_TERM_CONTEXT`) e `independence_model` (`ASSET_CLUSTERED`) en cada celda, **sin recalcular ninguna estadística**.
- **Reproducibilidad histórica**: 0 diferencias sustantivas en 20 celdas × 5 fechas; `CAMPOS_DE_PROCEDENCIA` + `huella()`.

**Tests deliberadamente frágiles**:
- `test_la_condicion_de_avance_no_se_cumple_todavia` — se rompe cuando la población sea suficiente, que es cuando hay que releer esta auditoría.
- `test_el_reportTime_no_es_constante_por_activo` — se rompe si alguien "limpia" el registro de MSFT.
- `test_cuando_caduca_el_tecnico_REQUERIDO_la_tesis_deja_de_ser_valida` — impide "arreglar" un test caducado relajando el umbral de cadencia.

**Bomba de relojería encontrada y desactivada**: `test_acciones_con_pe_caducado…` comparaba fixtures congeladas en 2026-09-02 contra `datetime.now()` y falló al pasar a 2026-09-08. `build_thesis`/`build_thesis_equity` aceptan ahora `as_of` opcional (el reloj que `_evaluar_evidencia` ya recibía). **No revisado si quedan más.**

**Qué se rompe si cae**: nada aguas abajo — el universo no alimenta ningún motor todavía. Se pierde la trazabilidad de por qué la cohorte es la que es.

**Informe**: `informes/2026-09-07_auditoria_poblacion_historical_events.md`.

---

### Autoridad · Qué fuente manda sobre cada componente — D-36 · D-37 · D-38 · D-39

**Ficheros**: `engine/events/autoridad_datos.json` · `autoridad.py` (nuevos) · `tests/test_autoridad_datos.py` (nuevo, 26 tests) · `universo_v1.json` (bloque `semantica`)

**Qué añade**: no ingiere nada. Determina la autoridad de cada componente de un earnings event, medido **en vivo** contra SEC EDGAR y Yahoo.

- **Regla fundacional (D-36)**: la cobertura de un proveedor no define quién existió. DWDP y UTX, ausentes en Alpha Vantage, están enteros en EDGAR (1009 y 1002 filings; 131 y 324 obs. XBRL).
- **El sesgo está en tres capas**: directorio de AV, `company_tickers.json` de la SEC (**también sesgado**) y EDGAR por CIK (**inmune**).
- **`acceptanceDateTime`** en el 100% de los filings: un instante, no una etiqueta. Contraejemplo intradía: DWDP 2019-04-18, 15:38 ET.
- **XBRL nativamente vintage**: UTX EPS 2019 = 1,32 (filed 2020) vs 6,41 (filed 2022).
- **Yahoo codifica escisiones como splits** (D-39): revisa un supuesto del bloque 4.
- **Matriz de cobertura**: 163 de 248 celdas `NOT_MEASURED`, ninguna rellenada.

**Tests deliberadamente frágiles**:
- `test_alpha_vantage_no_es_autoridad_del_universo` — se rompe si alguien promueve AV a `AUTHORITATIVE_SOURCE`.
- `test_lo_no_medido_es_not_measured_y_no_unavailable` — impide el colapso de estados que la matriz existe para evitar.
- `test_ninguna_medida_actual_depende_de_la_sorpresa` — se rompe el día que se añada un perfil condicionado por sorpresa, que es cuando hay que releer D-38.
- `test_el_universo_lista_empresas_a_auditar_no_activos_consultables` — impide que la cobertura vuelva a decidir la pertenencia.

**Qué se rompe si cae**: nada aguas abajo — es declarativo y ningún motor lo consume todavía. Se pierde la regla que impide que un proveedor decida quién existió en nuestro pasado.

**Informe**: `informes/2026-09-08_auditoria_autoridad_datos_historicos.md`.

---

### Identidad · Historical Instrument Master — D-40 · D-41 · D-42

**Ficheros**: `engine/events/identidad_instrumento.json` · `identidad.py` (nuevos) · `tests/test_identidad_instrumento.py` (nuevo, 30 tests)

**Qué añade**: no ingiere nada y no toca `DimAsset`. Modela **transformaciones de instrumento**, que es lo que una tabla de tickers no puede representar.

- **4 capas**: `LEGAL_ENTITY` · `SEC_CIK` · `MARKET_INSTRUMENT` · `TICKER`. El ticker no es identidad.
- **El caso peor no es un 404**: `MOB` devuelve 1011 sesiones de **Mobilicom Limited**, no de Mobil.
- **El CIK no es eterno**: XOM tiene dos (`0000034088` histórico con `tickers: []`, `0002115436` desde 2026-07 con `8-K12B`).
- **3 tipos de continuidad**: en `MERGER` y `SPINOFF` el retorno sobrevive y la economía no.
- **`IBM 2021-11-04 1046:1000`** es la escisión de Kyndryl, en un activo de la cohorte.
- **Regla de elegibilidad**: no "hay acción corporativa" sino "cambia el instrumento económico".

**Tests deliberadamente frágiles**:
- `test_solo_nvda_es_elegible_a_nivel_de_activo` — se rompe cuando se marquen las acciones corporativas, que es cuando hay que releer D-41.
- `test_el_precio_del_sucesor_no_se_declara_disponible_para_el_predecesor` — impide que `AMBIGUOUS` se ascienda a `AVAILABLE`.
- `test_un_split_en_ventana_NO_invalida_la_observacion` — impide la sobrecorrección de excluir toda acción corporativa.
- `test_el_mapeo_historico_esta_declarado_incompleto` — se rompe el día que exista fuente determinista.

**Qué se rompe si cae**: nada aguas abajo — declarativo, sin consumidores. Se pierde la invariante que impide confundir un sucesor con el instrumento original.

**Informe**: `informes/2026-09-08_auditoria_historical_instrument_master.md`.

---

### Corporate actions · Cobertura y continuidad — D-43 · D-44 · D-45

**Ficheros**: `engine/events/acciones_corporativas.json` · `cobertura_acciones.py` (nuevos) · `identidad_instrumento.json` · `identidad.py` · `tests/test_corporate_actions.py` (nuevo, 24 tests)

**Qué añade**: mide, no corrige. Cuántos eventos llevan en sus ventanas una transformación que rompa la continuidad económica.

- **52 eventos**: `2_60d` da **2 marcadas, 0 ambiguas**; los otros tres horizontes, limpios.
- **El 0% es del muestreo**: Kyndryl (2021-11-04) cae en el hueco de IBM (2021-01-22 → 2022-01-25).
- **Proyección contigua**: 1,6% contaminado y 0,5% ambiguo a `2_60d`. No extrapolable: 26 de 31 activos `NOT_MEASURED`.
- **Kyndryl verificada** contra el 8-K `items=2.01` del 2021-11-04.
- **Las fusiones no tienen señal de precio** (XOM 1999).
- **Resolución temporal**: `XOM` da CIK distinto según la fecha; `MOB @ 1995` da `AMBIGUOUS`.
- **7 de 95 caminos causales sin arista causal** (D-45).

**Tests deliberadamente frágiles**:
- `test_ningun_evento_actual_es_ambiguo_y_eso_es_del_MUESTREO` — impide leer el 0% como "cohorte limpia"; se rompe cuando la cohorte se haga contigua, que es cuando hay que releer D-43.
- `test_un_ticker_actual_no_demuestra_identidad_historica` — el caso `MOB`, permanente.
- `test_successor_of_se_clasifica_antes_de_existir` — se rompe el día que se añada al modelo sin declararlo no causal.
- `test_la_contaminacion_crece_con_el_horizonte` — si se invierte, hay un error de ventanas.

**Qué se rompe si cae**: nada aguas abajo — declarativo y sin consumidores. Se pierde la invariante de que una observación exige identidad y continuidad durante su ventana.

**Informe**: `informes/2026-09-08_auditoria_corporate_actions_y_continuidad.md`.

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
        └─ P5C amplía SUS DATOS (no su código): fuentes externas
                                              └─→ P5D Requirement (lee P1b + P5B)
                                                    └─→ P6 Impact (lee P5B + P5D)
                                                          └─→ P6.1 Materiality (deriva de Evidence + Knowledge)
```

### P5C · Economic Knowledge Seed v2 — cadena `NVIDIA → TSMC → CoWoS`

**Ficheros**: `knowledge/relationships/cadena_suministro.json` (nuevo) · `knowledge/entities/{organizations,technologies}.json` · `knowledge/sources/sources.json` · `knowledge/pendiente/nvidia_cadena.json` · `tests/test_cadena_suministro.py` (nuevo)

**Qué añade**: `rel:0046` (`org:tsmc SUPPLIES org:nvidia`), `rel:0047` (`org:nvidia USES tech:cowos`) y `rel:0048` (`org:tsmc USES tech:cowos`), más las entidades `org:tsmc` y `tech:cowos` y las **dos primeras fuentes externas del proyecto**: el 10-K FY2026 de NVIDIA y el 20-F FY2025 de TSMC, ambos en EDGAR.

**Por qué importa**: hasta aquí, las 45 relaciones de Knowledge procedían del propio repositorio (`INTERNAL_RULE`, `DATA_PROVIDER`, `OWN_ANALYSIS`) — evidencia de lo que el software hace, no del mundo. P5C es la primera vez que el sistema afirma algo sobre el mundo citando un documento que cualquiera puede reabrir.

**Ningún módulo del motor se tocó.** P5A recorre la cadena y P5B la valora con el código que ya tenían.

**Efecto observable**: primer camino `VERIFIED` + `COMPLETE` hasta una entidad no financiera (`rel:0005>rel:0046>rel:0048`), y `requires_evidence` deja de estar vacío: `demand(org:nvidia)` y `capacity_utilization(tech:cowos)`.

**Si falla**: no rompe ninguna capa inferior — Knowledge se lee, no se escribe desde ningún motor. `python3 engine/knowledge/consulta.py --validar` localiza el problema; borrar `knowledge/relationships/cadena_suministro.json` devuelve el sistema al estado de P5B.

**Informe**: `informes/2026-09-07_p5c_cadena_economica_real.md`.

---

### P5D · Evidence Gap → Data Requirement

**Ficheros**: `engine/requirements/{esquema_requisito,catalogo,resolver}.py` + `README.md` (nuevos) · `engine/contract/cadencias.py` (declara `ESTADOS_COBERTURA`) · `tests/test_requisitos.py` (nuevo) · `.gitignore`

**Qué hace**: convierte el `requires_evidence` de P5B en `DataRequirement` resueltos contra el contrato real, con los cinco estados de disponibilidad de P1b (importados, no copiados) y los cuatro de frescura.

**Las tres reglas del validador**: (1) una métrica no es la variable hasta que se declara con justificación — todo `PROXY` exige además su confusor; (2) solo-proxy nunca llega a `AVAILABLE`, techo `PARTIAL`; (3) `NOT_APPLICABLE` exige declaración, la falta de dato es `MISSING`.

**Resultado sobre la cadena de P5C**: `demand(org:nvidia)` = `PARTIAL`/`FRESH` (solo proxy declarado); `capacity_utilization(tech:cowos)` = `MISSING`, bloqueando 6 tramos. Ése es el cuello de botella real hacia P6.

**Fallo real que atrapó su propio diseño**: la candidata de `price` se declaró sobre el dominio `"technical"` cuando el contrato lo llama `"tecnico"`. No fallaba: devolvía `MISSING`, presentando una errata del catálogo como un hueco de datos. Guardia permanente en `test_toda_candidata_apunta_a_una_metrica_que_el_contrato_emite`.

**Si falla**: no rompe nada por debajo — solo lee. `engine/requirements/resolver.py --requisito "price(sec:BTC)"` es el diagnóstico más corto: si eso no da `AVAILABLE`, el problema está en `catalogo.py` o en `data/`, no en el resolutor.

**Informe**: `informes/2026-09-07_p5d_requisitos_de_evidencia.md`.

---

### P6 · Economic Impact v1

**Ficheros**: `engine/impact/{esquema_impacto,requisitos_magnitud,impacto}.py` + `README.md` (nuevos) · `tests/test_impacto.py` (nuevo). **Ningún fichero modificado**.

**Qué hace**: `CausalAssessment` (P5B) + `DataRequirement` (P5D) → `EconomicImpact`. Las cuatro piezas —dirección, magnitud, materialidad, horizonte— tienen **su propio estado**, porque pueden estar en estados distintos a la vez: la magnitud **no es obligatoria**.

**El núcleo**: `derecho_a_magnitud()`. v1 **no produce números y no contiene ninguna fórmula**; lo que entrega es la comprobación de si el sistema *tendría derecho* a producirlos, con cuatro precondiciones (variable medida · materialidad · coeficiente de origen declarado · línea base). Hoy `False` en el 100% de los casos reales; un test puebla las tablas y comprueba que **se enciende**, para que "siempre False" no pueda ser un bug disfrazado de decisión.

**Reglas ejecutables**: `value == 0` exige `evidence_ids` · `magnitude KNOWN` exige `materiality KNOWN` (causalidad ≠ materialidad, general) · `coefficient_origin == ESTIMATED` **rechazado en v1** · `fitness` `PROXY` nunca se promueve a cuantitativo · `NOT_QUANTIFIABLE` ⇒ `NOT_APPLICABLE` y al revés · rechazo por nombre de `probability`/`score`/`price_target`/`confidence`/`recommendation`.

**Combinar ≠ sumar**: `combinar()` **no tiene campo `total`**, por diseño. Devuelve `conocido[]` + `unresolved[]`, soporte del peor componente, `UNKNOWN` si algo no resuelve o si los horizontes difieren.

**Resultado real**: 42 tramos sobre 22 caminos → 37 `NOT_APPLICABLE` + 5 `UNKNOWN`. Ninguna magnitud, y cada tramo dice si es porque el mecanismo no puede o porque falta el dato.

**Si falla**: no rompe nada por debajo, solo lee. `python3 engine/impact/impacto.py org:nvidia` es el diagnóstico; si aparece cualquier magnitud con valor, el fallo está en `requisitos_magnitud.py` (alguna tabla de declaración dejó de estar vacía sin querer).

**Informe**: `informes/2026-09-07_p6_impacto_economico_v1.md` · **Diseño previo**: `docs/05-diseno-p6-impacto-economico.md`.

---

### P6.1 · Materiality derivada

**Ficheros**: `engine/impact/{esquema_materialidad,observaciones,materialidad}.py` (nuevos) · `tests/test_materialidad.py` (nuevo) · `esquema_impacto.py`, `requisitos_magnitud.py`, `impacto.py` (modificados).

**Qué hace**: `Evidence` (de entidad) + `Knowledge` (la relación) → `Materiality` (derivada, nunca almacenada). Cuatro pasos separados: `OBSERVATION → APPLICABILITY CHECK (entidad · relación · vigencia) → DERIVATION → status`.

**Resultado real**: `TSMC ← NVIDIA` = `BOUNDED ≤19%`, vía `rel:0046`, citando el 20-F **sin atribuir el 19% a NVIDIA**. En P6, la materialidad del tramo real pasa de `UNKNOWN` a `BOUNDED` y `MATERIALITY_UNKNOWN` se sustituye por `MATERIALITY_ONLY_BOUNDED`.

**El test central**: el 20-F da 25% (2023), 22% (2024), 19% (2025) y `rel:0046` solo está atestiguada desde 2025-01-27. Como el 19% es a la vez la menor y la más reciente, hay una fixture que invierte el caso (relación válida solo en 2023) donde la aplicable pasa a ser la **mayor y más antigua** — demostrando que la selección es por intersección temporal, no por `min`/`max`/`latest`.

**Dos motivos que no se colapsan**: `NO_SUPPORTING_EVIDENCE` (hace falta una fuente) frente a `EVIDENCE_EXISTS_BUT_NOT_APPLICABLE` (la hay y no alcanza). Los dos dan `UNKNOWN`; no son el mismo `UNKNOWN`.

**`POINT` no se introdujo**: `KNOWN` ya significa eso. Magnitud y materialidad comparten `ESTADOS_PIEZA`, ahora con `BOUNDED`.

**Si falla**: solo lee. `python3 -m unittest tests.test_materialidad` es el diagnóstico; si `TSMC ← NVIDIA` deja de dar `BOUNDED ≤19%`, mirar `observaciones.py` y la vigencia de `rel:0046`.

**Informe**: `informes/2026-09-07_p61_materialidad_v1.md`.

---

**La dirección es única**: cada capa lee la anterior y **ninguna escribe hacia atrás**. Está comprobado por hash dentro de la propia suite en P3, P4, P5A y P5B.

---

## Invariantes transversales del proyecto

Reglas que han aparecido más de una vez y que conviene no volver a romper:

1. **Ausencia ≠ evidencia de ausencia.** Cuatro apariciones, y desde P5D con un bloque de tests único (`TestInvariantesEpistemicos`) que las rompe juntas si alguien afloja una:
   - `NO RELATION` ≠ `RELATION DENIES` — P2 (`polarity=DENIES` exige fuente)
   - `NO EVIDENCE` ≠ `EVIDENCE OF NO EFFECT` — P5B (`UNKNOWN` ≠ `NEUTRAL`)
   - `NO SOURCE` ≠ `SOURCE SAYS IT DOES NOT EXIST` — P5D (`MISSING` ≠ `NOT_APPLICABLE`)
   - `NO_APLICA` en P1b (TVL de BTC), el caso original
   Y una cuarta que las une: **`UNKNOWN` nunca es permisivo** en ninguno de los tres ejes.
   P6 añade dos más: **`causalidad ≠ materialidad`** (Knowledge acredita que la relación existe, no en qué proporción) y **"no puedo" ≠ "no sé"** (`NOT_APPLICABLE` no mejora con más datos; `UNKNOWN` sí).
2. **Reutilizar un vocabulario cuando el concepto ES el mismo, nunca cuando difiere.** Las dos caras: P5D **importa** los cinco estados de cobertura de P1b en vez de copiarlos (misma pregunta, otro sujeto), y comparte `UNKNOWN` entre disponibilidad y frescura porque significa lo mismo — pero **solo** `UNKNOWN`, fijado por test. La cara opuesta: Tres apariciones: `source_priority` (P0), `nature` en Knowledge vs Evidence (P3), y las tres direcciones (P5B) — resuelto usando `DIVERGENT` en vez de `MIXED`. Los conjuntos deben ser **disjuntos** y hay tests que lo mantienen.
3. **Dos ejes, no un enum.** Cobertura y frescura (P1b), validez y completitud (P5A).
4. **La fecha del bloque es la del componente más antiguo**, nunca la del más reciente.
5. **Nombres de módulo únicos en `engine/`** salvo `score.py` y `fetch_data.py`, que se repiten a propósito. Guardia en `tests/test_events.py`.
6. **Un test que se apoya en que algo NO existe caduca cuando ese algo se documenta**, y eso es lo correcto. En P5C hubo que reescribir cinco tests de P2/P5A/P5B que afirmaban ausencias hoy superadas. La forma de escribirlos es separar la ausencia medida ("ninguno llega") de la propiedad permanente ("lo que llega, llega por conocimiento con fuente").
7. **Un test no debe inspeccionar la prosa.** Dos veces escribí tests que buscaban palabras en comentarios y encontraban justo la documentación que explica que esa cosa no existe. Se comprueban esquemas y comportamiento.

---

## Roadmap acordado (2026-09-07)

```
P0 · P1 · P1b · P2 · P3 · P4 · P5A · P5B · P5C · P5D · P6      ✅ cerradas
P6.1  Materiality              ✅ implementada
P6.2  Quantification unlocks
P7    Market Impact
P8    Mispricing
P9    Thesis integration
P10   Portfolio
P11   Outcome / Calibration
────────────────────────────────────────────────────────────────
CONSUMPTION   Power BI + Web App
```

**Power BI y la Web App quedan desacoplados del motor.** `docs/03` y `docs/04` pasan a ser **especificación de consumo, no contrato arquitectónico**: siguen siendo válidos en la división de funciones y en la regla de que ambos son consumidores, pero `FactMetrics` ya no representa el sistema y ningún motor se diseña pensando primero en él. Cuando llegue el momento, ambos consumirán una **proyección** del estado del motor.

---

## Deudas registradas y no corregidas

| Deuda | Dónde está registrada | Por qué no se corrigió |
|---|---|---|
| `adapt_equity()` escribe `pe_ratio`, `peg_ratio` y las tres `analyst_*` con la fecha del trimestre | `cadencias.py::DEFECTO_DE_FECHADO` + test que impide taparlo | Reescribiría filas ya en el contrato; tarea posterior a P2 |
| `desempleo_pct` y `spread_10y2y_pct` se descargan de FRED y no llegan al contrato | `thesis.py::_MACRO_CONTEXTO` + `cadencias.py` | Decisión de alcance; la pendiente 10a-2a es la serie macro más fresca (2 días) |
| `CLAUDE.md` describe `data/metrics/*.json`, que ya no existe | acordado dejarlo | Documentación desfasada, sin impacto funcional |
| `consolidate.py` huérfano | — | No lo consume nadie |
| `confluencia_sesgo` emite dos vocabularios distintos para cripto y acciones | P0 | Excluido de la migración a propósito |
| Seed B de NVIDIA: HBM y sustrato ABF | `knowledge/pendiente/nvidia_cadena.json` | **Buscados en P5C** en los dos filings primarios: cero menciones. Siguen sin fuente |
| Samsung, SK Hynix y Micron como proveedores de NVIDIA | `knowledge/pendiente/nvidia_cadena.json::_candidatas_documentadas_pendientes_de_alta` | **Ya tienen fuente verificada** (misma frase del 10-K que `rel:0046`). Fuera del alcance acordado de P5C, promovibles en un paso |
| `rel:0046` no documenta la **materialidad** de la relación de suministro | informe de P5C | El 10-K no dice qué fracción de wafers fabrica TSMC. Toda medida de impacto que lo necesite tendrá que decir que no lo sabe |
| `demand(org:nvidia)` sale `FRESH` con un dato de hace 5 semanas | informe de P5D | Correcto por cadencia (trimestral), pero la frescura dice que el dato está al día para su cadencia, no que sirva para el mecanismo. P6 debe mirarlo dos veces |
| Las 5 variables de mecanismo no tienen `concept_id` | `catalogo.CONCEPTO_DE_VARIABLE` + test | Ausencia medida, no hueco: declarar un concepto vacío sería peor que no declararlo |
| `MATERIALIDAD`, `COEFICIENTES` y `LINEAS_BASE` vacías | `requisitos_magnitud.py` + test | Decisión de P6 v1, no olvido. **Resuelto en el diseño de P6.1**: la materialidad se **deriva**, no se almacena; la evidencia es de entidad y cabe en el contrato sin tocar `METRIC_FIELDS` ni Knowledge |
| ~~Cuatro significados comparten el nombre `materialidad`~~ | — | **Cerrada en P6.1**: `BASIS_POR_MECANISMO` tipa la base y el extremo sujeto de cada mecanismo |
| El contrato no admite observaciones sobre entidades que no son activos | `engine/impact/observaciones.py` (cabecera) | Medido en P6.1: `asset_type_of('TSM') → None`. Las 3 filas del 20-F viven ahí, marcadas como observaciones y no declaraciones. Misma familia que `capacity_utilization(tech:cowos)` |
| `tech:cowos` se evalúa como insumo de coste, no como restricción de capacidad | informe de P6 | P5B enruta ese impulso por R5 y no por la vía de capacidad. Coherente con P5B, no tocado; el ángulo de capacidad es el económicamente interesante |
| 2.148 filas macro con `data_as_of` = fecha del periodo, no de publicación | `temporal.SEMANTICA_DATA_AS_OF` + bloque de QA | IPC, HICP y tipo efectivo de la Fed. La fecha real vive en ALFRED (vintages), que este sistema no usa. Acotadas por cota conservadora y visibles en cada QA; **no corregidas**, porque corregirlas sin la fuente sería inventar precisión |
| Las 15 filas del grupo B siguen fechadas con el trimestre | `cadencias.DEFECTO_DE_FECHADO` | `STALE`, no `LOOK_AHEAD` (D-18). No se re-fecharon: por decisión explícita del usuario y porque no falsean ningún backtest hacia el futuro |
| No hay benchmark en el contrato | D-21 | Sin él no hay retorno anormal, y sin retorno anormal la suficiencia de muestra bloquea toda agregación de reacciones. **Sin resolver para cripto** |
| La dirección causal noticia↔precio no se representa | informe de P6.2 §10 | Una noticia puede escribirse *porque* el precio ya se movió. No se inventa un campo que no se pueda rellenar |
| Un solo episodio declarado | `engine/events/episodios.json` | El mecanismo existe y está probado con 5 documentos reales; poblarlo es trabajo de curación con fuente, no de código |
| ~~Ningún benchmark declarado~~ | — | **Cerrada**: `bm:sp500` declarado el 2026-09-07 con las tres asignaciones. Los dos tests que vigilaban el vacío fallaron como estaba previsto y se reescribieron a "solo existe lo autorizado" |
| La metodología de S&P DJI no es citable | `src:yahoo-gspc` (nota) | `spglobal.com` responde 403, misma situación que D-07. `point_in_time_capable` se afirma sobre comprobación propia; hash de la serie registrado para detectar una reformulación |
| `data/benchmarks/` fuera de `qa.py` | D-24 | Tiene validación propia y un test sobre la serie real, pero no entra en el `STATUS: VERIFIED` global |
| El cron no actualiza el benchmark | `fetch_benchmark.py` | Se ejecuta a mano. Si la serie se queda atrás, la observación sale `SIN_OBSERVACION_BENCHMARK` — visible, no silencioso |
| Sin ventana base para medidas de nivel | D-27 · `perfil_reaccion.MEDIDAS_DE_NIVEL` | Bloquea 6 de los 20 perfiles. Es una decisión metodológica, no un problema de datos |
| No existe `n_effective` | informe de HRP v1 §11 | 52 observaciones de 3 acciones del mismo mercado no son 52 unidades independientes de información. Los `n` reportados son de eventos |
| La cohorte son 52 de ~356 eventos reales | fixtures de `eventos_resultados/` | Subconjunto disperso: la tasa de solape medida (11,5% a 2_60d) no es representativa de la serie completa |
| `ASSET_CLASS` declarado y rechazado | `modelo.ROLES_NO_ACTIVOS` | Su definición no está cerrada: para una acción `MARKET` y `ASSET_CLASS` difieren, para un cripto coinciden. Reactivarlo cuesta una línea |

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
