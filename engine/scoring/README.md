# Scoring Consolidado (v1)

Fase 6. Reúne, por activo, lo que cada motor construido hasta ahora (`engine/crypto`, `engine/technical`, `engine/macro`, y el informe manual de `engine/news`) ya calculó — sin fusionarlo en un único número.

## Uso

```
python3 engine/scoring/consolidate.py
```

Requiere que ya existan los datos descargados de `engine/crypto/_data/`, `engine/technical/_data/` y `engine/macro/_data/` (ejecutar los `fetch_data.py` de cada motor primero si no existen).

## Por qué no hay un "score único 0-10" todavía

La Fase 0 fue explícita: una suma ponderada simple de dominios distintos oculta contradicciones en vez de mostrarlas (ver el propio ejemplo de la Fase 0: fundamentales excelentes + valoración cara + insiders vendiendo no debe promediarse a un "6"). Ese trabajo de detectar convergencia/divergencia es la Fase 7 (Motor de Razonamiento), todavía no construida. Este motor de scoring se limita a lo que la Fase 0 pidió para la Fase 6: normalización, comparación y — cuando un dominio no tiene dato de un activo — decirlo explícitamente en vez de inventar un valor.

## Qué propaga cada dominio

- **Fundamental (tokenomics)**: percentiles de 365 días y Data Quality del motor cripto — incluida cualquier advertencia de incidencia de datos (ver DOT en el informe v1).
- **Técnico**: sesgo de confluencia y su propio confidence (basado en cuántas de las 4 señales tenían dato).
- **Macro**: contexto regional (no específico del activo — se adjunta igual a todos).
- **Noticias/sentimiento**: solo cuando existe informe para ese activo; si no, se marca `disponible: false`.
