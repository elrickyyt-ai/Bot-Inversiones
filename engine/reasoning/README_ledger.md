# Thesis Ledger (v1)

Fase 0, punto 21: memoria histórica. Registra cada tesis generada (`engine/reasoning/thesis.py`) junto con el precio del momento, para poder comprobar más adelante si acertó — el mismo mecanismo que `personas_influyentes.json` aplica a divulgadores externos, aplicado ahora al propio sistema.

## Uso

```
python3 engine/reasoning/ledger.py   # registra la tesis de hoy para los 6 activos
```

Cada entrada se añade a `engine/reasoning/ledger/{ACTIVO}.jsonl` (JSON Lines, una tesis por línea). **A diferencia de `_data/`, esto SÍ se versiona en git** — es nuestro propio historial de análisis, no datos de mercado en bruto que se puedan volver a descargar.

## Cómo se evalúa una tesis pasada

```python
from ledger import evaluate_pending
evaluate_pending("BTC", precio_actual=<precio de hoy>)
```

Solo completa el campo `evaluacion` de las entradas cuyo horizonte (90 días por defecto) ya se cumplió — nunca evalúa antes de tiempo, ni inventa un veredicto.

### El umbral no es arbitrario

"¿Se cumplió el bull case, el bear case, o ninguno?" necesita un criterio objetivo. En vez de un porcentaje fijo igual para todos los activos, se usa la **volatilidad histórica anualizada** que ya calcula el motor técnico (distinta por activo — ADA es mucho más volátil que BTC) escalada al horizonte de evaluación con la regla estándar de escala por raíz del tiempo:

```
umbral_pct = volatilidad_anualizada_pct × √(horizonte_días / 365)
```

Si la variación real de precio supera ese umbral al alza → `bull_case`. Si lo supera a la baja → `bear_case`. Si se queda dentro → `base_case`. Es una regla simple y documentada, no un juicio subjetivo de "pareció que acertó".

## Qué falta para que esto cierre el círculo

- Un recordatorio real a 90 días vista para ejecutar `evaluate_pending` (hoy no hay ningún proceso automático que lo dispare).
- Agregación: una vez haya varias tesis evaluadas, calcular la tasa de acierto del propio sistema por dominio (¿acierta más cuando fundamental y técnico convergen que cuando divergen?) — la pregunta que en el fondo motivó construir todo esto.
