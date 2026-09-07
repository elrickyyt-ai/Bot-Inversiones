# `engine/impact/` — Economic Impact v1 (P6)

> El objetivo de v1 **no es producir números**. Es demostrar que el sistema sabe exactamente **cuándo tendría derecho a producirlos y cuándo no**.

```
CausalAssessment (P5B) + DataRequirement (P5D) → EconomicImpact
```

## Qué es un `EconomicImpact`

Una **afirmación condicionada**:

> dado el evento E, el mecanismo M y la evidencia disponible, la variable V de la entidad X va en dirección D, en el horizonte H, con la magnitud que se pueda sostener.

No dice *"NVIDIA tendrá +X%"*. Un impacto con `magnitude UNKNOWN` **no es un fallo**: es el resultado correcto de la información disponible.

## Las cuatro piezas son independientes

`direction` · `magnitude` · `materiality` · `horizon` tienen **su propio estado**, porque pueden estar en estados distintos a la vez. La magnitud **no es obligatoria**.

Cada pieza vale `KNOWN` | `UNKNOWN` | `NOT_APPLICABLE`, y la distinción entre las dos últimas es el corazón de la capa:

| | significa | ¿mejora con más datos? |
|---|---|---|
| `NOT_APPLICABLE` | el mecanismo no produce esta pieza, por su naturaleza | **no** |
| `UNKNOWN` | podría conocerse, hoy no se conoce | **sí** |

## Los tres ficheros

| Fichero | Qué es |
|---|---|
| `esquema_impacto.py` | vocabularios + validador. Las reglas viven aquí, no en la disciplina |
| `requisitos_magnitud.py` | **declaración a mano**: capacidad de magnitud y entradas mínimas por mecanismo. `COEFICIENTES`, `MATERIALIDAD` y `LINEAS_BASE` están **vacías** en v1 |
| `impacto.py` | resolutor determinista + CLI. **No contiene ninguna fórmula** |

## `derecho_a_magnitud()` — el núcleo

Cuatro precondiciones, ninguna sustituible por un valor implícito:

1. la variable observada **medida**, no aproximada (`fitness == MEASURES`)
2. **materialidad** declarada — *causalidad no es materialidad*
3. **coeficiente de transmisión** de origen declarado
4. **línea base** contra la que medir el cambio

Hoy devuelve `False` en el 100% de los casos reales. Un test puebla las tablas y comprueba que **se enciende** — sin eso, "siempre `False`" podría ser un bug en vez de una decisión.

## Lo que P6 nunca emite

`probability` · `score` · `price_target` · `confidence` · `recommendation` · `expected_return`

El validador **rechaza cualquier campo con esos nombres**. No es estilo: es la única forma de que no reaparezcan por la puerta de atrás.

Y no es impacto de mercado: **P6 = "qué cambia económicamente"**, **P7 = "qué debería pasar en el precio"**. `precio` es la métrica mejor cubierta del contrato, o sea el atajo más fácil de tomar.

## El coeficiente estimado no existe en v1

`ORIGENES_COEFICIENTE = {OBSERVED, DECLARED, ESTIMATED, UNKNOWN}` se declara **entero**, y `ESTIMATED` está **prohibido por el validador**. Escribirlo completo es lo que permite rechazarlo explícitamente, en vez de que el caso simplemente no exista y aparezca un día sin que nadie lo note.

Un coeficiente estimado estadísticamente **no será Evidence ni Knowledge**: será salida de un modelo, y esa capa (con ventana de entrenamiento, validación fuera de muestra, estabilidad, sensibilidad al régimen) no existe.

## Combinar ≠ sumar

`combinar()` **no tiene campo `total`**, y no existe por diseño. Devuelve `conocido[]` + `unresolved[]`, el soporte del **peor** componente, y `UNKNOWN` si algún tramo no resuelve o si los horizontes difieren.

## Uso

```bash
python3 engine/impact/impacto.py org:nvidia
python3 engine/impact/impacto.py org:nvidia --combinar
```

## Estado hoy

42 tramos sobre 22 caminos: **37 `NOT_APPLICABLE`** (aristas de identidad y mecanismos no cuantificables) y **5 `UNKNOWN`**. Ninguna magnitud, y cada tramo dice si es porque el mecanismo no puede o porque falta el dato.
