# Data Contract (v1)

Capa de visualización — ver `docs/03-arquitectura-visualizacion-y-acceso.md` para la planificación general y `docs/04-modelo-power-bi.md` para el modelo de datos de Power BI (Fases B-G). Esta pieza cubre los pasos 1-2 del orden acordado con el usuario el 2026-09-03 (historización + DimAsset) más los pasos 1-3 originales (Data Contract, adaptadores, tests) y la Fase A de diagnóstico (`qa.py`) — **la Web App y Power BI todavía no se han construido**, quedan para cuando se autorice explícitamente.

## Diagnóstico (`qa.py`)

```
python3 engine/contract/qa.py
```

Lee `data/`, valida cada fila contra el contrato y produce un informe legible (no JSON crudo), con PASS/FAIL en cinco bloques: esquema, privacidad, temporal (`data_as_of` vs. `retrieved_at`), fuentes, y DimAsset. Ejecutarlo después de cada `build.py` para saber si el sistema funciona sin inspeccionar los ficheros a mano — ver `informes/2026-09-03_data_qa_v1.md` para la primera ejecución real, que encontró un hallazgo genuino (precio en EUR para cripto vs. USD para acciones) y un defecto real en `schema.py` (rango de `confidence_pct`/`data_quality_pct` sin validar, ya corregido). El hallazgo del EUR/USD quedó resuelto con DimAsset (ver más abajo): la comprobación de unidades incompatibles en `qa.py` ahora compara por `(metric, asset_type)` en vez de solo `metric` — una unidad distinta entre asset_types distintos es esperada y queda explicada por `DimAsset.currency`, no es una incidencia.

## Qué hace

`schema.py` define tres formas de fila (métrica, tesis, y DimAsset) que va a consumir tanto la futura Web App como Power BI, sin lógica duplicada entre ambas. `adapters.py` traduce la salida de cada motor existente (`engine/crypto`, `engine/technical`, `engine/macro`, `engine/equity`, `engine/reasoning`) a esas formas, **sin modificar los motores originales**. `build.py` orquesta todos los adaptadores, valida cada fila contra el contrato antes de escribirla, y genera `data/metrics/{TICKER}.json`, `data/thesis/{TICKER}.json` y `data/assets/{TICKER}.json` en la raíz del repo.

## Uso

```
python3 engine/contract/build.py
```

Requiere que ya existan los datos descargados de cada motor (`_data/` de crypto/technical/macro/equity) — ejecutar sus `fetch_data.py` primero si no existen.

## Historización (desde 2026-09-03) — append-only, idempotente

`data/metrics/{ID}.json` y `data/thesis/{ID}.json` ya **no se sobrescriben** en cada ejecución de `build.py` — son un histórico que crece con el tiempo. Ejecutar `build.py` varias veces el mismo día (o el mismo minuto) no duplica filas.

**Clave lógica de idempotencia para métricas**: `(asset_id, domain, metric, data_as_of, source)` — **nunca** `retrieved_at`, porque dos ejecuciones el mismo día tendrían un `retrieved_at` distinto (la hora exacta) pero deben considerarse la misma observación si `data_as_of` coincide.

**Clave lógica de idempotencia para tesis**: `(asset_id, data_as_of)` — como máximo una tesis registrada por activo y fecha de dato.

**Semántica exacta**: si ya existe una fila con esa clave, la fila nueva se descarta (no se sobrescribe el valor existente). Esto significa que la primera captura de un `data_as_of` concreto es la que queda — una revisión posterior del mismo dato histórico (poco común, pero posible en filings) no se reflejaría automáticamente. Se documenta como decisión explícita, no como limitación oculta.

**Macro ya no escribe un fichero `_macro.json` especial** — EE.UU. y Eurozona pasan a tratarse como activos propios (`US.json`, `EA.json`), con el mismo tratamiento historizado que cripto y acciones.

**Migración del formato de tesis**: antes de historizar, `data/thesis/{ID}.json` era un objeto único (la última tesis). Ahora es una lista de objetos. `build.py` migra automáticamente el formato antiguo la primera vez que se ejecuta, sin perder la tesis que ya hubiera.

## DimAsset (`data/assets/{ID}.json`) — atributos estáticos, no historizados

A diferencia de métricas y tesis, `data/assets/{ID}.json` **se sobrescribe** en cada `build.py` (un objeto, no una lista) — nombre, sector, país, divisa no cambian día a día, así que no aporta valor guardar un histórico. Campos: `asset_id`, `asset_type`, `name`, `sector`, `industry`, `country`, `currency`, `exchange`, `active`, `retrieved_at`, `source`.

**Procedencia de cada campo, documentada por tipo de activo** (en el docstring de cada función `adapt_asset_*` de `adapters.py`, no solo aquí):
- **Acciones** (`adapt_asset_equity`): todos los campos extraídos literalmente de `COMPANY_OVERVIEW` de Alpha Vantage (`Name`, `Sector`, `Industry`, `Country`, `Currency`, `Exchange`) — ninguno asignado por el sistema.
- **Cripto** (`adapt_asset_crypto`): `name` viene de CoinGecko. `sector="Cripto"` es una etiqueta **asignada** por este sistema (CoinGecko no tiene un equivalente limpio de "sector" para criptomonedas). `currency="EUR"` es la divisa del **sistema** (todo el motor cripto cotiza vía Kraken en EUR), no una propiedad inherente del activo — esto es precisamente lo que resuelve la ambigüedad EUR/USD que `qa.py` detectó. `country` solo se rellena si CoinGecko trae `country_origin`; si viene vacío se deja `None`, nunca se inventa "Global".
- **Macro** (`adapt_asset_macro`): pseudo-activos para EE.UU. (`US`, `currency="USD"`) y Eurozona (`EA`, `currency="EUR"`) — nombres y divisas fijados por definición de la región, `source="FRED"`.

**Por qué resuelve el hallazgo EUR/USD de `qa.py`**: antes, una fila con `metric="precio"` no dejaba claro en qué divisa estaba sin ir a mirar el motor de origen. Ahora, unir cualquier fila de métrica con `data/assets/{asset_id}.json` por `asset_id` da la divisa real de forma explícita — es la relación que en el modelo de Power BI (`docs/04-modelo-power-bi.md`) corresponde a la tabla `DimAsset`.

## `data_as_of` vs. `retrieved_at`

La razón de separarlos (a petición explícita del usuario, y es correcta): un ratio fundamental de una acción corresponde al último trimestre reportado, no al momento en que se descarga. Ejemplo real de XOM en esta misma sesión: `precio` con `data_as_of=2026-09-02` (fecha de la cotización) y `pe_ratio` con `data_as_of=2026-06-30` (fecha del último trimestre) — ambos con el mismo `retrieved_at` (cuándo se ejecutó `build.py`). Sin esta distinción, un futuro backtesting (Fase 8) podría usar sin darse cuenta un dato que en la fecha simulada todavía no existía.

## Gap conocido: macro

`adapt_macro()` usa la fecha de descarga como `data_as_of` en vez de la fecha real del último dato publicado (ej. el mes exacto del CPI) — `engine/macro/score.py` no expone todavía esa fecha en su valor de retorno. Corregirlo es un cambio pequeño pero está fuera del alcance acordado para esta pieza (solo Data Contract + adaptadores, sin tocar los motores). Documentado también en el código.

## Regla de privacidad (aplicada en el propio validador, no solo en la documentación)

`schema.py` rechaza cualquier fila que contenga un campo no reconocido por el contrato, o que mencione literalmente `cartera_A`, `cantidad_neta` o `flujo_caja` en cualquier valor — para que un adaptador futuro no pueda colar por error un dato de `cartera/` en lo que acabará en el bundle de la Web App. Ver `docs/03-arquitectura-visualizacion-y-acceso.md` para la razón completa (un dato en el bundle de una app estática no es equivalente a un dato en backend, aunque el acceso esté protegido).

## Fuentes de datos vs. fuentes de noticias

`SOURCE_PRIORITY` en `schema.py` es una jerarquía **distinta** de la que ya existe en `engine/news/sources.py` — esa es para credibilidad periodística (Reuters vs. un blog), esta es para fiabilidad de fuentes de datos de mercado (FRED como fuente primaria vs. agregadores como Alpha Vantage/CoinGecko). Ambas conviven, no se fusionan.
