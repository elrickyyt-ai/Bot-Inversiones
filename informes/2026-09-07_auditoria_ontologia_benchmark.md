# Auditoría de ontología: qué es un benchmark en una arquitectura multi-activo

**Fecha**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2` · **Base**: `e158fad`
**Naturaleza**: auditoría. **No se ha implementado nada** — ni benchmarks, ni índices, ni cambios en `DimAsset`, Power BI, scoring, Historical Reaction Profiles, `reaction_gap`, pesos ni BUY/SELL. Cero ficheros de código modificados.

**Mediciones en vivo hechas para esta auditoría** (ninguna consume cuota de Alpha Vantage):

```
CoinGecko /global                        200 · solo valor ACTUAL, sin serie
CoinGecko /global/market_cap_chart       401 Unauthorized (requiere clave de pago)
Yahoo ^GSPC   14.291 velas  1970-01-02 → 2026-09-04
Yahoo ^IXIC   14.013 velas  1971-02-05 → 2026-09-04
Yahoo ^NDX    10.312 velas  1985-10-01 → 2026-09-04
Yahoo XLK      6.968 velas  1998-12-22 → 2026-09-04
Yahoo XLE      6.968 velas  1998-12-22 → 2026-09-04
Yahoo SOXX     6.324 velas  2001-07-13 → 2026-09-04
```

---

## 1. Qué es un Asset

Lo que ya dice el repositorio, no una definición nueva:

- `engine/knowledge/modelo.py::TIPOS_ENTIDAD` — `security` = *"instrumento negociable (lo que hoy es un asset_id)"*.
- `schema.ASSET_FIELDS` = `asset_id, asset_type, name, sector, industry, country, currency, exchange, active, retrieved_at, source`. Son atributos **de un instrumento**: dónde cotiza, en qué divisa, de qué sector, de qué país.

> **Asset = instrumento negociable cuyo comportamiento el sistema analiza.**

Los 11 de hoy: 6 cripto, 3 acciones, 2 regiones macro. Las dos macro (`US`, `EA`) ya son una excepción admitida —no son instrumentos— y se aceptó porque tienen serie propia, cadencia declarada y dominio propio. Es un precedente, y conviene mirarlo con cuidado: se admitió una excepción, no se abrió la puerta a cualquiera.

## 2. Qué es un Benchmark

> **Benchmark = referencia metodológica versionada contra la que se calcula un retorno anormal.**

La diferencia con un Asset no es de grado. Un benchmark no se analiza: se usa para **descontar** de la reacción de un activo la parte que no le es propia. Y tiene una propiedad que ningún campo de `ASSET_FIELDS` expresa: una **metodología** con versión y vigencia.

El sistema ya guarda un número derivado de un benchmark **sin haberlo declarado nunca**: `engine/equity/score.py:150` extrae `beta` del `COMPANY_OVERVIEW` de Alpha Vantage. Beta es, por definición, una magnitud relativa a un índice — y aquí ni se sabe cuál, ni con qué ventana, ni con qué frecuencia. **No llega al Data Contract** (verificado: `grep beta engine/contract/*.py` → 0 resultados), así que hoy no contamina nada. Pero es el ejemplo exacto de lo que esta ontología existe para impedir: un número ajustado por mercado cuyo mercado es desconocido.

## 3. Qué es una Comparison Reference

La distinción que propone el usuario es correcta, y hay una razón formal para sostenerla:

> **Comparison Reference = referencia descriptiva para contextualizar, que NO entra en el cálculo de un retorno anormal.**

Si BTC fuese el benchmark de BTC, su retorno anormal sería **cero por construcción**. No es un caso raro: es lo que pasaría al usar el líder de una clase como benchmark de la propia clase. Y sin embargo *"BTC −8%, ETH −5%, token −20%"* es información útil.

Un mismo objeto puede ser las dos cosas para activos distintos: BTC puede ser Comparison Reference de ETH y no ser benchmark de nadie. Lo que no puede es serlo del mismo activo.

Es el mismo invariante que el proyecto ya aplica cuatro veces: **un token se comparte si y solo si significa lo mismo** (P0 con `source_priority`, D-11 con `SUPPORTED`, D-13 con `POINT`, y P6.2a con `data_as_of`). Llamar `benchmark` a las dos cosas sería la quinta.

## 4. Qué `BenchmarkRole` hacen falta

Un rol no se justifica por ser concebible, sino por responder a una pregunta distinta **y** ser construible con evidencia:

| Rol | Pregunta | ¿Construible hoy? |
|---|---|---|
| `MARKET` | ¿cuánto se movió todo el mercado? | **Sí** en equity (^GSPC desde 1970). **No** en cripto (§8) |
| `SECTOR` | ¿qué parte fue del sector? | Solo vía ETF sectorial; **no** con constituyentes propios (§7) |
| `ASSET_CLASS` | ¿qué hizo la clase de activo? | Coincide con `MARKET` mientras haya una sola clase por activo. **No se introduce**: sería un token duplicado hasta que exista un caso que los separe |
| `PEER` | ¿qué hizo un comparable? | Sí, pero **no es benchmark** — es Comparison Reference (§3) |
| `FACTOR` | ¿qué parte explican factores? | **No.** Requiere una capa de modelo (ventana de entrenamiento, validación fuera de muestra) que **D-10 ya declaró inexistente** |

**Propuesta**: `MARKET` y `SECTOR` como roles de benchmark; `PEER` como rol de Comparison Reference. `ASSET_CLASS` y `FACTOR` **no se introducen todavía** — declarar cinco roles y poder poblar uno sería inventar vocabulario, el error que D-13 evitó al no introducir `POINT`.

## 5. Cómo se asigna un benchmark a un activo

**Hallazgo que simplifica la propuesta**: la asignación **ya es expresable con la capa que existe**. Una relación de Knowledge (P2) tiene hoy exactamente esta forma:

```json
{"relationship_id": "rel:0026", "subject": "sec:BTC", "predicate": "EXPOSED_TO",
 "object": "reg:US", "polarity": "AFFIRMS", "nature": "ASSERTED",
 "status": "PROVISIONAL", "support_level": "BAJO", "source_id": "src:...",
 "statement": "...", "valid_from": "2026-07-22", "valid_to": null,
 "last_verified": "2026-09-06", "verification_method": "..."}
```

`subject` · `object` · `valid_from` · `valid_to` · `source_id` · `nature` · `status` — es una `AssetBenchmarkAssignment` completa, con vigencia y procedencia, en un formato ya validado, ya versionado en git y ya cubierto por `consulta.py --validar`.

Y trae de regalo dos invariantes que una tabla nueva tendría que reinventar:

- **D-04**: ningún motor escribe conocimiento. Una asignación de benchmark **no puede** fijarla el código que calcula el retorno — que es exactamente la defensa contra el *selection bias* del §11.
- **D-09**: la vigencia no se extrapola. `valid_from` es el primer día que la fuente acredita, no "desde siempre".

**Propuesta**: la asignación es una **relación de Knowledge con un predicado nuevo**, no una tabla paralela. Requiere un tipo de entidad nuevo (§14) y una entrada en `PREDICADOS`, que restringe qué pares (sujeto, objeto) son legales — hoy impide "un mercado emitido por un material" y ahí impediría "una acción con benchmark en un sector".

## 6. Cómo cambia la asignación con el tiempo

Con `valid_from` / `valid_to`, igual que cualquier otra relación. Tres casos reales que lo exigen:

1. **NVDA cambia de perfil.** En 1999 era una empresa de tarjetas gráficas de pequeña capitalización; hoy es una de las mayores del índice. El benchmark sectorial defendible no tiene por qué ser el mismo en los dos extremos.
2. **XLK no existe antes de 1998-12-22** (verificado). Cualquier asignación sectorial vía ETF tiene un `valid_from` duro, y los 6.968 días previos de IBM/XOM no tienen benchmark sectorial. No es un fallo: es un `valid_from`.
3. **Una revisión de metodología no es un cambio de benchmark.** Si S&P cambia cómo calcula el índice, el `benchmark_id` sigue siendo el mismo y lo que cambia es `methodology_version`. Confundirlos haría irreproducible cualquier cálculo pasado.

## 7. Equity

**`MARKET`: construible y sin fricción.** ^GSPC cubre 1970-01-02 → 2026-09-04, **exactamente el mismo tramo que IBM y XOM ya tienen en el contrato**, y por la misma fuente (Yahoo Finance) y el mismo camino que el backfill del bloque 4 ya usa. No hace falta una fuente nueva.

**`SECTOR`: el hallazgo incómodo.** El sistema **no puede construir un benchmark sectorial con lo suyo**:

- `knowledge/entities/sectors.json` tiene **dos** sectores, `sect:technology` y `sect:energy`, y ambos con `source_id: src:dimasset-equity` — es decir, **derivados del propio `DimAsset`**, no de una clasificación externa.
- Los constituyentes serían **2 acciones** para tecnología (IBM, NVDA) y **1** para energía (XOM).

Un "benchmark sectorial" de una acción es aritméticamente indistinguible de esa acción. La única vía defendible es un ETF sectorial externo (XLK 1998-12-22, XLE 1998-12-22, SOXX 2001-07-13) — **y un ETF no es un índice**: tiene comisión, tracking error y su propia historia de composición. Meterlo en la misma tabla que ^GSPC sin distinguirlo repetiría el error de token compartido.

**Sobre `^NDX` frente a `^GSPC` para NVDA**: son dos preguntas distintas (mercado amplio vs. grandes tecnológicas), y por eso el modelo debe admitir **varias asignaciones simultáneas con rol distinto**. Lo que no debe admitir es elegir entre ellas después de ver el resultado (§11).

## 8. Crypto — el caso que decide la ontología

**Obligatorio**, porque el 60% del contrato es cripto. Medido, no supuesto:

| Candidato | Verificado | Veredicto |
|---|---|---|
| CoinGecko `/global` | 200, **solo valor actual** | No sirve: sin serie histórica no hay event study |
| CoinGecko `/global/market_cap_chart` | **401 Unauthorized** | Requiere clave de pago. Rompería el patrón "sin clave" de todas las fuentes del proyecto |
| Índice construido con los 6 cripto del contrato | — | **Rechazado**, ver abajo |
| BTC como benchmark de cripto | — | **Rechazado**: circular para BTC (AR ≡ 0) y no es un índice |
| DefiLlama | ya en uso | Da TVL, no capitalización. No es un índice de mercado |
| Coinbase / Kraken | ya en uso | No publican índice |

**Por qué se rechaza el índice casero, y es el argumento más fuerte de esta auditoría**: los 6 cripto de `DimAsset` **son los holdings actuales de `CARTERA_A`**. Un índice construido con ellos estaría seleccionado *ex post* por lo que el usuario tiene hoy — sesgo de supervivencia y de selección **por construcción**. Sería exactamente el look-ahead que P6.2a acaba de eliminar del contrato, reintroducido por la puerta de atrás y con apariencia de metodología.

> **Conclusión: para cripto, `MARKET` = `UNAVAILABLE`.** No es una carencia que haya que tapar. Es el resultado correcto.

Lo que sí es defendible para cripto es Comparison Reference: BTC y ETH como referencias descriptivas (`PEER` / `LEADER`), **sin** que de ahí salga ningún retorno anormal.

**Consecuencia que hay que aceptar antes de decidir**: con esta ontología, los eventos de cripto **no tendrán retorno anormal** hasta que aparezca una fuente de índice PIT y gratuita. Y como la suficiencia de muestra ya bloquea toda agregación sin retorno anormal (P6.2c), **el Historical Reaction Profile nacerá cubriendo solo acciones**. Es una limitación real del sistema, no del diseño, y es mejor tenerla escrita que descubrirla dentro de tres fases.

## 9. Qué ocurre cuando no existe benchmark

`UNAVAILABLE`, propagado como ausencia, con el precedente ya establecido en el propio event study: `market_adjusted_return_pct = None` con `razon_sin_ajuste = SIN_BENCHMARK_EN_EL_CONTRATO`.

Tres reglas:

1. **No se sustituye en silencio** por otra referencia.
2. **Tampoco se sustituye en voz alta** por un *peer*. Un `PEER` es Comparison Reference y **no puede ascender a benchmark** porque falte el bueno — es la razón formal de separar los dos conceptos (§3).
3. **`UNAVAILABLE` no es permisivo**, igual que `UNKNOWN` en `cadencias.py` y `DESCONOCIDO` en `temporal.py`. Un activo sin benchmark no participa en una agregación que requiera retorno anormal.

## 10. Cómo evitamos look-ahead

El riesgo que plantea el usuario —usar la composición actual de un índice para reconstruir su pasado— **tiene una salida limpia, y conviene verla antes de diseñar campos para el problema difícil**:

> Si se usa el **nivel publicado** del índice, la composición es irrelevante.

El valor de ^GSPC el 2018-11-16 es el que S&P publicó ese día y **no se restata**. No hay que saber qué empresas lo componían: el nivel ya lo incorpora. El problema de composición aparece **solo** en benchmarks que construyamos nosotros — y esos, por el §8, no se van a construir.

Eso reduce los campos PIT a los que de verdad hacen falta en `DimBenchmark`:

| Campo | Para qué |
|---|---|
| `methodology_version` | un cambio de metodología del proveedor no puede pasar inadvertido |
| `valid_from` / `valid_to` | XLK no existe antes de 1998-12-22 |
| `composition_source` | `PUBLISHED_LEVEL` · `ETF_NAV` · `CONSTRUCTED` |
| `point_in_time_capable` | ¿el proveedor restata la serie hacia atrás? |

Y una comprobación que el proyecto ya sabe hacer, del §10 del informe de P6.2: **un `close` de Yahoo cambia con los splits pero no con los dividendos**. Para un índice no hay splits; para un **ETF sí puede haberlos**, así que un benchmark vía ETF necesita la misma cautela con `close` frente a `adjclose` que ya se documentó para acciones.

**Ausencia declarada**: los índices no tienen problema de *survivorship* en su nivel publicado, pero **sí lo tienen los ETF** cuando cambian de índice de referencia. No se resuelve aquí; se registra.

## 11. Cómo evitamos benchmark selection bias

El escenario que hay que impedir —probar cinco benchmarks y quedarse con el que da el AR más extremo— **ya está estructuralmente bloqueado si la asignación vive en Knowledge**:

- **D-04**: el motor no escribe conocimiento. El código que calcula el retorno **no puede** crear ni modificar la asignación. No es disciplina: es que `modelo.py` no tiene funciones de escritura, a propósito.
- **D-09**: `valid_from` es la fecha que la fuente acredita. Una asignación creada hoy no puede fingir que regía en 2018.
- El registro está **versionado en git**: cambiar un benchmark deja un commit con fecha, autor y diff.

Encima de eso, una `BenchmarkPolicy` declarada por `(asset_type, rol)` — como `cadencias.CADENCIAS` declara la cadencia por `(domain, metric)` — hace que la elección sea una propiedad **del tipo de activo**, no de la observación. Un activo no elige su benchmark: lo hereda de su clase.

**Y una regla que conviene escribir explícitamente**: el número de asignaciones por `(activo, rol, periodo)` es **exactamente uno**. Varios roles simultáneos, sí; dos candidatos para el mismo rol y el mismo periodo, no — ahí es donde entraría la elección *ex post*.

## 12. Impacto sobre el Event Study

`estudio_resultados.py` emite hoy 17 campos por observación, con dos ya preparados para esto: `market_adjusted_return_pct` (None) y `razon_sin_ajuste`.

La propuesta del usuario de **no guardar un único `abnormal_return`** es correcta, y hay que añadirle algo: **cada retorno ajustado debe viajar con la identidad del benchmark que lo produjo**. Un `market_adjusted_return` sin saber contra qué es irreproducible — es el problema de `beta` del §2, otra vez.

Forma mínima (**no implementada**):

```
raw_return_1s_pct              ya existe
ajustes: [ {rol, benchmark_id, methodology_version, valor_pct, metodo} ]
```

Con `metodo` declarado —`DIFERENCIA_SIMPLE` (r_activo − r_benchmark) frente a `MARKET_MODEL` (α+βr, que exige ventana de estimación)— porque **son cosas distintas y D-10 ya prohíbe estimar coeficientes en v1**. En v1 solo cabe `DIFERENCIA_SIMPLE`: es la única que no requiere la capa de modelo que no existe.

Efecto sobre lo ya construido: `suficiencia_de_muestra()` deja de bloquear por `SIN_RETORNO_ANORMAL` **solo para los activos con benchmark**, y pasa a bloquear por muestra insuficiente. Con 3 acciones y ~356 eventos verificados, el mínimo declarado de 30 se supera; el condicionado de 50 probablemente no. Cripto seguirá bloqueado, por el §8.

## 13. Impacto sobre Power BI

Medido sobre `docs/04-modelo-power-bi.md`. **Aquí es donde la opción A se rompe de forma verificable**, y no por estética:

```python
>>> cadencias.calendario("tecnico", "precio", "index")   → 'crypto'
>>> cadencias.esperadas("X", "index", "tecnico")         → None
```

- `calendario()` devuelve `"equity" if asset_type == "equity" else "crypto"`. Un índice con `asset_type="index"` recibiría el calendario **24/7**: cada fin de semana contaría como sesión perdida y la frescura saldría rota todos los lunes.
- `esperadas()` devuelve `None` → **`PARTIAL` no es calculable** → `UNKNOWN`, que el propio proyecto declara **el peor valor** del eje de frescura, no un intermedio.
- `Asset Count = DISTINCTCOUNT(FactMetrics[asset_id])` pasaría de 11 a 12 **en silencio**. Y `Latest Confidence`, `Latest Data Quality` y `Precio Actual` (segmentado por `currency`, donde el índice caería en el cubo USD junto a las acciones) incluirían la referencia entre lo analizado.

Con la opción B, `FactMetrics` **no cambia de esquema** y `DimAsset` sigue con 11 filas. La serie del benchmark necesita destino propio: o una tabla de hechos separada (`FactBenchmark`), o un `asset_id` en `FactMetrics` que no esté en `DimAsset` —lo que rompería la integridad referencial del modelo estrella—. **Recomendación: tabla propia.** Es una relación más en Power BI y ninguna medida existente cambia de valor.

## 14. Propuesta de D-21

La formulación del criterio de salida es correcta en lo esencial. **Dos modificaciones, ambas por evidencia del repositorio**:

**(a) `AssetBenchmarkAssignment` no debe ser una entidad nueva.** La capa Knowledge (§5) ya tiene la forma exacta —sujeto, objeto, vigencia, fuente, verificación— y aporta D-04 y D-09 sin escribir una línea. Crear una tabla paralela duplicaría un mecanismo probado y, peor, la sacaría del alcance de `consulta.py --validar`.

**(b) `DimBenchmark` no es una población homogénea.** Contiene índices (no negociables, nivel publicado, sin splits) y ETF (negociables, con comisión, tracking error y splits). Necesita `composition_source` para distinguirlos, y **`CONSTRUCTED` debe declararse y ser rechazado por el validador** — exactamente el patrón de **D-10** con `ESTIMATED`: se nombra para que el día que alguien lo intente salte, en vez de aparecer sin que nadie lo note.

Formulación propuesta:

> **`DimAsset` representa instrumentos analizados. `DimBenchmark` representa referencias metodológicas versionadas, distinguiendo si su serie es un nivel publicado o el NAV de un instrumento negociable, y rechazando las construidas por el propio sistema. La asignación activo→referencia es una relación de Knowledge con rol y vigencia, no una tabla nueva, y por tanto ningún motor puede escribirla. Un `(activo, rol, periodo)` admite exactamente una asignación. La ausencia de benchmark se propaga como `UNAVAILABLE` y no se sustituye por otra referencia, ni en silencio ni ascendiendo un `PEER`.**

## 15. Alternativas descartadas

| Alternativa | Por qué se descarta |
|---|---|
| **Índices dentro de `DimAsset`** | Rompe `calendario()` y `esperadas()` de forma verificable (§13); mezcla lo analizado con lo que mide; `Asset Count` cambia en silencio |
| **`AssetBenchmarkAssignment` como tabla nueva** | Knowledge ya lo expresa con vigencia y procedencia, y aporta D-04/D-09 gratis (§5) |
| **Índice cripto construido con los 6 activos del contrato** | Son los holdings actuales de `CARTERA_A`: selección *ex post* y sesgo de supervivencia por construcción (§8) |
| **BTC como benchmark de cripto** | AR ≡ 0 para BTC; y un constituyente no es un índice (§3) |
| **CoinGecko de pago para el índice cripto** | Rompe el patrón "sin clave" de todas las fuentes del proyecto; misma razón por la que se descartó CryptoCompare en el bloque 3 |
| **Rol `FACTOR` en v1** | Exige una capa de modelo que D-10 declaró inexistente |
| **Rol `ASSET_CLASS` en v1** | Coincide con `MARKET` mientras cada activo tenga una sola clase: dos nombres para una idea (D-13) |
| **`MARKET_MODEL` (α+β) en v1** | Estimar β es estimar un coeficiente, prohibido por D-10 |
| **Un solo campo `abnormal_return`** | Irreproducible sin la identidad del benchmark: el problema de `beta` (§2) |
| **Benchmark sectorial con constituyentes propios** | 2 acciones en tecnología, 1 en energía (§7) |

## 16. Qué NO debe implementarse todavía

- Ningún benchmark, índice ni ETF ingerido.
- Ningún cambio en `DimAsset`, `ASSET_FIELDS`, `METRIC_FIELDS` ni el modelo de Power BI.
- Ningún `BenchmarkRole`, predicado ni tipo de entidad añadido a `modelo.py`.
- Ningún campo nuevo en la observación de reacción.
- `HistoricalReactionProfile`, `reaction_gap`, condicionamiento por régimen, `n_effective`, shrinkage: **nada**. El usuario ya fijó que `reaction_gap` exige antes muestra suficiente, comparables, benchmark congelado, régimen y walk-forward.
- `beta` **no** se conecta al Data Contract mientras su benchmark siga sin declararse.

---

## Sobre `Evidence Eligibility` (§8 del planteamiento del usuario)

La observación es correcta y ya tiene tres instancias en el código, no dos:

| Regla | Dónde vive hoy |
|---|---|
| No usar una línea base sin historia suficiente | D-16 · `informes/2026-09-07_medicion_lineas_base.md` |
| No usar un perfil histórico sin muestra suficiente | `estudio_resultados.MINIMOS_DECLARADOS` (D-20) |
| No usar un dato sin validez temporal | `temporal.usable_en()` (D-17) |
| No usar una comparación sin referencia válida | *no existe todavía* — es lo que D-21 crearía |

**Recomendación deliberada: no abstraerlo todavía.** El proyecto ya tiene un precedente de haber acertado esperando —`_pct_in_window()` existió mucho antes de que P6.2c lo generalizara, y generalizarlo con su `10` como umbral global habría sido un error (D-20)—. Con tres instancias y una cuarta sin construir, una abstracción prematura fijaría la forma equivocada. **La cuarta instancia (D-21) es justamente la que dirá si las cuatro comparten estructura o solo se parecen.** Después de D-21, con las cuatro delante, es el momento de decidirlo.

---

## Qué falta saber antes de cerrar D-21

Tres cosas que esta auditoría **no** puede responder sola:

1. **¿Se acepta que cripto quede sin retorno anormal?** Es el 60% del contrato y la consecuencia directa del §8. Con la alternativa siendo un índice casero sesgado, la respuesta recomendada es sí — pero es una decisión del usuario, no técnica.
2. **¿ETF sectorial, o ningún benchmark sectorial en v1?** Un ETF introduce comisión, tracking error y splits en algo que se usa como referencia limpia. La alternativa es tener solo `MARKET` en v1, que es más pobre y más honesto.
3. **¿`^GSPC` o `^IXIC`/`^NDX` como `MARKET` de las acciones?** Los tres cubren el periodo. La decisión debe tomarse por criterio declarado y **antes** de mirar ningún resultado (§11), o el sesgo de selección entra por ahí.

**Alto.** Según lo acordado, la implementación de D-21 no empieza hasta que esta ontología esté validada.
