# Evidence (v1)

Vista **derivada y regenerable** del Data Contract y de `data/news/`. No sustituye a nada, no es fuente de verdad de nada y **ningún motor la consume todavía**. Su único trabajo en v1 es demostrar que se pueden representar observaciones de fuentes distintas sin perder semántica, identidad, temporalidad, procedencia, naturaleza epistemológica ni trazabilidad.

```bash
python3 engine/evidence/construir.py --contar
python3 engine/evidence/construir.py --reversibilidad 2000
python3 engine/evidence/construir.py --reversibilidad-noticias
python3 engine/evidence/construir.py --muestra
python3 engine/evidence/construir.py --materializar     # opcional, a data/evidence/, gitignored
```

## No es un fichero por defecto

507.330 filas de métricas producen ~200 MB de JSON. Evidence es una **función que genera filas**; materializarla es una opción explícita y va a `data/evidence/*.jsonl`, gitignored como `data/current/` y `data/coverage.json`. Un artefacto derivado que se versiona deja de ser derivado.

## Dos hallazgos de la implementación

**`method` no podía con dos trabajos.** La comprobación de reversibilidad falló en las 3.000 primeras filas: `method` estaba guardando a la vez *qué se hizo* («media móvil simple de 20 sesiones») y *dónde está documentado* (`engine/crypto/README.md`, que es lo que el contrato guarda en `calculation_method`). Uno de los dos se perdía y con él la reconstrucción 1:1. Separados en `method` y `method_ref`.

**Tres columnas del contrato se habrían perdido en silencio.** Medido sobre las 507.330 filas: `asset_type` (100%), `confidence_pct` (132 filas), `data_quality_pct` (84). `asset_type` se recupera de DimAsset —que sigue siendo la dimensión, decisión aprobada—, así que **la reconstrucción es Evidence + DimAsset**, y eso se declara en vez de disimularse duplicando la columna en medio millón de filas. Las otras dos viajan como `origin_confidence_pct` / `origin_data_quality_pct`: no es inventar confidence, son valores que la fila de origen ya traía, con un nombre que dice de quién son.

## La colisión de `nature` con Knowledge, y por qué es segura

`engine/knowledge/modelo.py` usa `nature ∈ {STRUCTURAL, ASSERTED}` y **prohíbe** `INFERRED`. Aquí `nature ∈ {MEASURED, DERIVED, INFERRED}` y `INFERRED` **sí** es legítimo. Es el mismo nombre de campo con dos vocabularios distintos: exactamente la forma del defecto de `source_priority` que encontró P0.

Lo que lo hace seguro es que los dos conjuntos son **disjuntos**, así que un valor identifica sin ambigüedad su capa. Eso no es una coincidencia: es una invariante, y `test_evidence` la mantiene. Si alguien añadiera `ASSERTED` aquí o `DERIVED` allí, el test falla antes de que el error llegue a ninguna parte.

La dirección sigue siendo única: una fila de Evidence con `nature=INFERRED` **no puede** convertirse en una relación de Knowledge. Y **ningún adaptador de P3 emite `INFERRED`** — está declarado para P5.

## Procedencia: dos escalas que no se unifican

Cada fila lleva `source_rank` **y** `source_scale`, el nombre de la escala a la que ese rango pertenece: `market_data_priority` (1-2 en uso, autoridad del proveedor) o `journalistic_tier` (1-5, credibilidad del medio). Un `2` de Coinbase y un `2` de Reuters no son el mismo hecho, y P0 ya demostró que compartir columna no los hace comparables. La solución no es fabricar una tercera escala común.

## Naturaleza y trazabilidad

`MEASURED` para lo leído sin transformar; `DERIVED` para lo calculado. `derived_from` **sólo se rellena cuando el destino existe de verdad** — un indicador técnico apunta al `precio` de la misma entidad, fecha y fuente, y si esa fila no está (indicador de una fuente, precio de otra) la referencia no se escribe: una trazabilidad que apunta a algo inexistente es peor que declarar que no se puede trazar, y el método queda documentado igualmente en `method`. Las derivadas cuyo insumo no está en el contrato (el índice CPI de FRED) tienen `derived_from` vacío y el método nombrando la serie.

## Noticias

Dos filas de Evidence por (artículo, entidad): el score (`value_num`) y su etiqueta (`value_text`, con `derived_from` apuntando al score). Dos y no una porque `value_num XOR value_text` es una regla dura y porque la etiqueta es una bucketización que la propia fuente hace del score.

`claim_type` se decide por **regla declarada, no por un clasificador**: distinguir «este medio informa de un hecho» de «este medio opina» exige análisis de contenido, que P3 deliberadamente no hace. El único caso clasificable sin leer el texto es aquel en el que el publicador *es* el actor del hecho (tier 1 de `news/sources.py`, un regulador publicando su propio acto) → `OBSERVATION`. Todo lo demás es `ASSERTION`. Con los datos de hoy las 50 noticias son `ASSERTION`, y eso es información.

`relevance` **no es confidence**: mide cuánto habla el artículo de esta entidad, no cuánto nos fiamos de él. `confidence` no existe como campo en Evidence.

Una entidad que no resuelve **no se crea en silencio**: se devuelve en la lista de no resueltas.

## Lo que P3 no hace

No extrae eventos, no propaga nada, no calcula impacto ni mispricing, no añade dominios ni infraestructura. No toca el Data Contract, `history/`, `incoming/`, `current/`, Power BI, los cinco motores ni `NEWS_FINDINGS`. **Una tesis nunca genera Evidence** — hay un test que lo comprueba leyendo el propio código del adaptador.
