# `engine/requirements/` — Evidence Gap → Data Requirement (P5D)

> P5B dice **qué** le falta. P5D dice **si existe, dónde y con qué calidad**.

Cierra el bucle que P5C dejó abierto:

```
EVENT → CAUSAL PATH → ECONOMIC MECHANISM → REQUIRED EVIDENCE
                                              ↓  [P5D]
                                        AVAILABLE EVIDENCE → (P6 IMPACT)
```

## El problema que resuelve

P5B ya producía lo más valioso que tiene el motor causal:

```python
requires_evidence = ["demand(org:nvidia)", "capacity_utilization(tech:cowos)"]
```

…pero como cadenas de texto dentro de un tramo. P5D las parsea, las **deduplica** (el mismo requisito aparece en decenas de caminos) y las resuelve contra el contrato real.

## Los tres ficheros

| Fichero | Qué es |
|---|---|
| `esquema_requisito.py` | vocabularios cerrados + validador del `DataRequirement` |
| `catalogo.py` | **declaración a mano**, hermano de `contract/cadencias.py`: qué métrica observa qué variable |
| `resolver.py` | resolución + CLI. No descarga nada, no declara equivalencias |

## Las tres reglas que el validador hace cumplir

1. **Una métrica no es la variable hasta que alguien lo declara.** `revenue` no se convierte en `demand` porque ambos suban. Toda candidata lleva `relation` (`MEASURES` | `PROXY`) y una `justification`; todo `PROXY` lleva además su `confounder`, o el validador la rechaza.
2. **Solo-proxy no llega a `AVAILABLE`.** Como máximo `PARTIAL`. Es la misma regla que P5B aplica a un signo que depende de un supuesto no verificado.
3. **`NOT_APPLICABLE` exige declaración.** La ausencia de dato es `MISSING`. Degradarla a "no aplica" convertiría un hueco en una respuesta.

## Vocabulario: se importa, no se copia

Los cinco estados de disponibilidad y los cuatro de frescura vienen de `contract/cadencias.py`, no de una copia local. Es la misma pregunta ("¿existe el dato?") sobre un sujeto distinto — un requisito de mecanismo en vez de un par activo × dominio. Los dos ejes comparten **solo** `UNKNOWN`, y a propósito: significa lo mismo en ambos ("no había declaración con la que comparar").

## Uso

```bash
python3 engine/requirements/resolver.py org:nvidia            # desde una entidad
python3 engine/requirements/resolver.py --requisito "price(sec:BTC)"
python3 engine/requirements/resolver.py org:nvidia --json     # data/requirements.json
```

`data/requirements.json` es **derivado y no se versiona**: depende de `coverage.json` (que tampoco) y envejece solo con la frescura.

## Estado hoy

| Requisito | Disponibilidad | Por qué |
|---|---|---|
| `demand(org:nvidia)` | `PARTIAL` · `FRESH` | solo `revenue_growth_yoy_pct`, declarado **proxy** con su confusor |
| `capacity_utilization(tech:cowos)` | `MISSING` | ninguna fuente de este sistema publica utilización de capacidad de encapsulado |

El segundo es **el cuello de botella real hacia P6**: no es el algoritmo de impacto, es que ese dato no lo tiene nadie aquí.
