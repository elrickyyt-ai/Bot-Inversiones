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

## Materialidad (P6.1) — se deriva, no se almacena

```
Evidence (de entidad)  +  Knowledge (la relación)  →  Materiality (derivada)
```

`materialidad.py` mantiene los cuatro pasos separados a propósito:

```
OBSERVATION → APPLICABILITY CHECK (entidad · relación · vigencia) → DERIVATION → status
```

Si la aplicabilidad estuviera mezclada con la búsqueda, una observación **válida pero inaplicable** acabaría indistinguible de un hueco de datos, y el sistema mandaría a buscar una fuente que ya tiene. De ahí dos motivos y no uno:

| motivo | significa |
|---|---|
| `NO_SUPPORTING_EVIDENCE` | no hay observación: hace falta una fuente |
| `EVIDENCE_EXISTS_BUT_NOT_APPLICABLE` | la hay y es válida, pero no alcanza a esta contraparte o periodo |

**No hay fichero de materialidades ni función de escritura**: si se guardara, en dos meses nadie sabría si el 19% es lo que dijo el 20-F o lo que dedujo el sistema.

### El caso real

```
MATERIALIDAD mat:SUPPLIER_REVENUE_EXPOSURE:org:tsmc:org:nvidia
  ESTADO     BOUNDED  <= 19.0%
  observado  org:tsmc · 2025 · aplicada via rel:0046
      · cota, no atribución: la fuente dice que el mayor cliente de org:tsmc
        representa 19.0%, sin nombrarlo. Que org:nvidia sea ese cliente NO se afirma
      · 2 observaciones descartadas por no ser aplicables, no por ser peores
```

El 20-F publica **tres** cotas (25% 2023 · 22% 2024 · 19% 2025) y `rel:0046` solo está atestiguada desde 2025-01-27, así que **solo la de 2025 aplica** — no por ser menor ni más reciente, sino por ser la única cuyo periodo intersecta con la vigencia de la relación.

### `BOUNDED` y `POINT`

`BOUNDED` se añade a `ESTADOS_PIEZA` y lo comparten magnitud y materialidad. **`POINT` no se introduce**: `KNOWN` ya significa eso, y añadirlo serían dos nombres para una idea.

Una cota solo se emite si es **estricta** (`< 100%`) y procede de una observación. Un tope aritmético no es una cota: parece información sin serlo.

## Uso

```bash
python3 engine/impact/impacto.py org:nvidia
python3 engine/impact/impacto.py org:nvidia --combinar
```

## Estado hoy

42 tramos sobre 22 caminos: **37 `NOT_APPLICABLE`** (aristas de identidad y mecanismos no cuantificables) y **5 `UNKNOWN`**. Ninguna magnitud, y cada tramo dice si es porque el mecanismo no puede o porque falta el dato.
