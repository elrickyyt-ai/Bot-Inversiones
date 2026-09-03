# Modelo de datos para Power BI (Fases B-G, sin código de interfaz)

**Fecha:** 2026-09-03 · **Precede a:** `docs/03-arquitectura-visualizacion-y-acceso.md` (arquitectura general) · **Basado en:** el diagnóstico real de `engine/contract/qa.py`, no en suposiciones — ver `informes/2026-09-03_data_qa_v1.md`.

## Hallazgo que condiciona todo lo demás — actualización 2026-09-03 (resuelto)

**Este hallazgo ya está resuelto.** `engine/contract/build.py` ahora es append-only e idempotente (ver `engine/contract/README.md`, sección "Historización"). Las medidas de variación (Change %, 1D/7D/30D) siguen sin tener sentido *hoy* porque solo hay un día de historial acumulado, pero ya no están bloqueadas por diseño — se poblarán solas a medida que `build.py` se ejecute en días sucesivos. Se deja el análisis original abajo tal cual se escribió, porque documenta correctamente el problema y su causa.

**Texto original (contexto):** `data/metrics/{TICKER}.json` guardaba solo el último snapshot, no una serie histórica. Cada vez que se ejecutaba `engine/contract/build.py`, el fichero de cada activo se sobrescribía con los datos del momento — no se acumulaba como sí hacía el Thesis Ledger (`engine/reasoning/ledger/*.jsonl`, que es append-only). Esto significaba que no existía ningún historial en el Data Contract, y por tanto ninguna medida de variación era construible.

## Fase B — Fact/Dim tables

### FactMetrics
Igual que pediste, mapea casi 1:1 con el Data Contract ya construido:
`asset_id, asset_type, domain, data_as_of, retrieved_at, metric, value, unit, source, confidence_pct, data_quality_pct`.

### FactThesis — una modificación respecto a tu propuesta
`contradictions`, `convergences`, `divergences` e `invalidation_factors` son **listas**, no valores únicos — en `data/thesis/*.json` son arrays. Meterlas tal cual en una celda de Power BI impide contar "cuántas contradicciones se detectaron este mes" o filtrar por tipo de hallazgo, que es justo lo que la página "Thesis Performance" (ya prevista en `docs/03`) necesita. Propongo una tabla adicional:

**FactThesisFindings**: `thesis_id, asset_id, asset_type, data_as_of, finding_type (contradiction|convergence|divergence|invalidation), text`

Con `asset_id`/`data_as_of` copiados directamente (no solo enlazados vía `thesis_id`), para que se relacione con `DimAsset`/`DimDate` como cualquier otra tabla de hechos, sin depender de una relación fact-a-fact (mala práctica en Power BI, la evito desde el diseño).

**FactThesis** (simplificada, sin las 4 listas): `thesis_id, asset_id, thesis_type, data_as_of, retrieved_at, confidence_pct, bull_case, base_case, bear_case`.

### DimAsset — gap real encontrado
`name`, `sector`, `country` que pediste **no existen todavía en ningún fichero de `data/`** — los adaptadores solo generan filas de métrica y de tesis, nunca atributos estáticos del activo. Los datos brutos sí los tienen (`engine/equity/_data/*_overview.json` trae `Name`/`Sector`/`Country` de Alpha Vantage; CoinGecko trae el nombre de cada cripto) — haría falta un tercer tipo de adaptador (`adapt_asset_attributes()`) que hoy no existe. Lo marco como pendiente, no lo invento.

**Propuesta añadida, no pedida pero necesaria**: `DimAsset` debería llevar un campo **`currency`** (`EUR` para cripto vía Kraken, `USD` para acciones vía Alpha Vantage) — es la resolución estructural correcta al hallazgo de la Fase A (`precio` con dos unidades distintas), mejor que solo advertir en cada medida.

```
DimAsset: asset_id, asset_type, name, sector, country, currency
DimDate:  Date, Year, Month, Quarter, DayOfWeek (calendario estándar)
DimSource: source, source_priority
DimMetric: metric, domain, expected_unit, display_label
```

**¿Son suficientes estas dimensiones?** Con la adición de `currency` en `DimAsset` y la separación de `FactThesisFindings`, sí, para lo que existe en `data/` hoy. No son suficientes para lo que pides en la Fase E que hoy no existe (ver gaps abajo) — pero eso es un problema de cobertura de datos, no de dimensiones.

## Fase C — Power Query (Get Data → Folder)

1. **Get Data → Folder**, apuntando a `data/metrics/` — Power BI lista todos los `.json` de la carpeta con su ruta.
2. **Combine & Transform**: al combinar, Power Query pide una función de transformación de ejemplo (usa el primer fichero) — como cada `.json` es un **array** de filas, la transformación debe usar `Json.Document` seguido de `Table.FromRecords`, no `Record.ToTable` (eso es para un objeto único, válido en cambio para `data/thesis/*.json`, que son objetos sueltos, no arrays).
3. **Filtro de archivos**: excluir `_macro.json` de la carga de `data/metrics/` si se va a tratar como una fuente separada (recomendado: macro no tiene `asset_id` de un activo de mercado, mézclalo aparte o con un `asset_type = "macro"` explícito, que ya lo tiene).
4. **Expandir la columna JSON** a columnas: `asset_id, asset_type, domain, metric, value, unit, data_as_of, retrieved_at, source, source_priority, confidence_pct, data_quality_pct, calculation_method, source_url`.
5. **Tipos de datos**: `data_as_of` → `Date` (no `DateTime`, es un día, no un instante); `retrieved_at` → `DateTimeZone` (trae hora y es UTC); `value` → cuidado, es texto en algunas filas (`confluencia_sesgo` es categórico) y numérico en otras — **no fuerces un tipo único a `value`**, es la razón por la que el contrato separa `value` de `unit`; dejar `value` como texto en Power Query y convertir a número solo donde el `metric` lo requiera es más seguro que forzar `Decimal` a toda la columna (fallaría en las filas categóricas). `confidence_pct`/`data_quality_pct` → `Whole Number` (ya vienen validados en 0-100 por `schema.py`).
6. **Eliminar columnas innecesarias**: la columna de ruta/nombre de archivo que añade el Folder Connector (`Source.Name`, `Folder Path`) una vez confirmado que `asset_id` ya identifica el origen.
7. **Tratamiento de nulos**: **no reemplazar nulos por 0** en `confidence_pct`/`data_quality_pct`/`value` — un nulo aquí significa "el motor no calculó esto para este activo" (ej. `tvl_percentile_365d` en BTC, que no tiene TVL por diseño, no por error), y convertirlo en 0 lo confundiría con un dato real de valor cero. Dejar como `null`/blank, Power BI y DAX lo manejan bien de forma nativa.
8. **Columnas calculadas que sí valen la pena en Power Query** (no en DAX, porque son de limpieza de fuente, no de análisis): una columna `value_numeric` (intento de conversión a número, con error capturado → null si no aplica) separada de `value_text` (la original) — así DAX no tiene que decidir tipo fila a fila.
9. **`data/thesis/`**: carpeta separada, mismo patrón de Folder Connector, pero cada archivo es un objeto único → usar `Record.ToTable` o directamente `Table.FromRecords({Json.Document(...)})`.

## Fase D — Modelo estrella

```
DimAsset ──┬── FactMetrics ──── DimSource
           │        │
           │        └────────── DimMetric
           │
           ├── FactThesis
           │
           └── FactThesisFindings

DimDate ───┼── FactMetrics
           ├── FactThesis
           └── FactThesisFindings
```

- Todas las relaciones son **uno a muchos**, dirección de filtro **única** (de la dimensión hacia el hecho) — sin bidireccional, para evitar ambigüedad tal como pediste.
- Claves: `DimAsset[asset_id]`, `DimDate[Date]`, `DimSource[source]`, `DimMetric[metric]`.
- **Ninguna relación fact-a-fact** (ver la razón en `FactThesisFindings` arriba) — es la fuente más común de relaciones ambiguas en Power BI y la evito desde el diseño, no parcheándola después.

## Fase E — Medidas DAX (solo las que hoy son construibles)

### Genéricas
```dax
Asset Count = DISTINCTCOUNT(FactMetrics[asset_id])
Metric Count = DISTINCTCOUNT(FactMetrics[metric])
Thesis Count = DISTINCTCOUNT(FactThesis[thesis_id])
Latest Confidence = AVERAGE(FactMetrics[confidence_pct])
Latest Data Quality = AVERAGE(FactMetrics[data_quality_pct])
```
`Latest Value` = con un solo snapshot por activo, hoy es simplemente el valor almacenado — se deja preparada para cuando haya historial:
```dax
Latest Value =
CALCULATE(SELECTEDVALUE(FactMetrics[value_numeric]), FactMetrics[data_as_of] = MAX(FactMetrics[data_as_of]))
```

**`Previous Value`, `Change`, `Change %`: BLOQUEADAS.** No hay una fecha anterior que comparar — ver el hallazgo del principio del documento. No las escribo hasta que `build.py` conserve historial.

### Precio
```dax
Precio Actual = CALCULATE([Latest Value], FactMetrics[metric] = "precio")
```
Segmentado siempre por `DimAsset[currency]` en la visualización (nunca sumar `Precio Actual` de un cripto y una acción en la misma tarjeta) — la resolución del hallazgo de la Fase A.
**Variación 1D/7D/30D: BLOQUEADAS**, misma razón que `Change %`.

### Fundamentals — solo lo que existe
```dax
Crecimiento Ingresos YoY = CALCULATE([Latest Value], FactMetrics[metric] = "revenue_growth_yoy_pct")
ROE = CALCULATE([Latest Value], FactMetrics[metric] = "roe_pct")
```
`Revenue` (importe absoluto), `EPS`, `FCF`, márgenes: **no existen en `data/` hoy.** `EPS` y los márgenes sí los calcula `engine/equity/score.py` pero el adaptador actual no los extrajo; `FCF` no lo calcula ningún motor todavía. No propongo medidas para ninguno de los tres.

### Technical — solo lo que existe
```dax
RSI Actual = CALCULATE([Latest Value], FactMetrics[metric] = "rsi14")
```
`SMA`, `ATR`, `Volatility`: los calcula `engine/technical/score.py` pero el adaptador no los extrajo — **no existen en `data/`**, no propongo medidas.

### News — nada construible
**Cero métricas de noticias existen en el Data Contract.** No hay adaptador de `engine/news/` todavía (el motor de noticias en sí existe y funciona, pero nunca se conectó al Data Contract). No propongo ninguna medida de "número de noticias", "sentimiento medio" ni "noticias positivas/negativas" — sería inventarlas sobre datos que no están.

## Fase F — página Data Quality (diseño conceptual)

Recomiendo que esta página **reproduzca las comprobaciones de `qa.py` dentro del propio Power BI** (como medidas DAX sobre `FactMetrics`, no solo como un informe externo), para que la validación viva donde se consume el dato:

```
┌─────────────────────────────────────────────────────────┐
│ DATA QUALITY                                              │
├─────────────────────────────────────────────────────────┤
│ Fuentes activas: 5   ·   Activos: 9   ·   Filas: 70        │
│ Última actualización: [MAX(retrieved_at)]                   │
├─────────────────────────────────────────────────────────┤
│ CONFIDENCE / DATA QUALITY MEDIO POR DOMINIO (tabla)         │
│ COBERTURA: activo × métrica esperada (matriz, huecos visibles)│
│ INCIDENCIA AUTOMÁTICA: "Metric Unit Consistency Check"       │
│   -- DISTINCTCOUNT(unit) por metric, alerta si > 1           │
│   (habría detectado 'precio' EUR/USD el primer día)          │
│ FRESHNESS: días desde retrieved_at, por activo                │
└─────────────────────────────────────────────────────────┘
```

La medida de incidencia automática es nueva respecto a lo que pediste, pero es la versión DAX de exactamente lo que `qa.py` ya hace en Python — tiene sentido que ambas existan (una para desarrollo/CI, otra para consulta dentro del propio informe).

## Fase G — páginas del dashboard principal (solo lista, sin diseñar — como pediste)

Market Overview · Asset Research · Fundamentals · Technical · Macro · News & Sentiment · Thesis — mismas 7 que ya estaban esbozadas con más detalle en `docs/03-arquitectura-visualizacion-y-acceso.md` §9. **News & Sentiment no tendrá contenido real hasta que exista el adaptador de noticias** — la página puede diseñarse, pero no poblarse. No se construye ninguna todavía.

## Resumen de lo que quedó pendiente de autorización — estado 2026-09-03

1. ~~Historizar `build.py` (append en vez de overwrite)~~ — **hecho.**
2. Adaptador de atributos estáticos de activo (`name`, `sector`, `country`, `currency`) para `DimAsset` — autorizado, en curso.
3. Ampliar `adapt_equity`/`adapt_technical` para incluir EPS, márgenes, SMA, ATR, volatilidad — autorizado, en curso.
4. Adaptador de `engine/news/` al Data Contract — autorizado, en curso.
