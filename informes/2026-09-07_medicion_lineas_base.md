# Medición · Líneas base — qué necesita cada mecanismo y qué existe

**Fecha**: 2026-09-07 · **Tipo**: medición de solo lectura, previa al diseño de P6.2
**Encargo**: determinar qué tipo de línea base necesita cada mecanismo y **cuáles existen realmente**, antes de decidir dónde almacenarlas o cómo cuantificarlas.

---

## 1. Qué se midió

Tres consultas, reproducibles:

```python
# 1 · qué línea base declara necesitar cada mecanismo
RM.ENTRADAS[*]["linea_base"]

# 2 · qué métrica del contrato resuelve la variable observada
catalogo.OBSERVABLES

# 3 · cuánta historia tiene cada serie, sobre los 11 activos
storage.all_layers(tipo, asset) → fechas distintas por (dominio, métrica)
```

---

## 2. Resultado 1 · Las seis líneas base declaradas

| Mecanismo | Línea base que necesita |
|---|---|
| `CUSTOMER_DEMAND` | demanda normal del cliente |
| `INPUT_COST` | precio normal del insumo |
| `CAPACITY_CONSTRAINT` | utilización normal del recurso |
| `PRICING_POWER` | utilización normal del recurso |
| `SUPPLY_SHORTAGE` | inventario normal |
| `LEAD_TIME` | plazo normal |

Las seis son **niveles normales**, no valores anteriores. Esa distinción resulta ser decisiva: un valor anterior se saca de una serie de dos puntos; un nivel normal necesita una distribución.

---

## 3. Resultado 2 · Profundidad real por dominio

```
  fundamental   63 series · con UNA sola fecha:  42 · con >1:  21
                distribución (fechas:series): {1: 42, 2: 18, 1698: 1, 1989: 1, 3127: 1}

  macro          4 series · con UNA sola fecha:   0 · con >1:   4
                distribución: {343: 1, 864: 1, 941: 1, 10065: 1}

  tecnico      108 series · con UNA sola fecha:   6 · con >1: 102
                distribución: {1: 6, 2: 12, 1446: 1, 1646: 1, 1707: 1, 1708: 1, …}
```

**Técnico y macro están completos.** El backfill hizo su trabajo: 10.065 fechas en una serie macro, más de 1.700 en varias técnicas.

**Fundamental, no.** Y el desglose es tajante:

```
fundamental — series con más de 2 fechas:
   ETH   tvl_percentile_365d    3127
   SOL   tvl_percentile_365d    1989
   ADA   tvl_percentile_365d    1698
```

Las **tres** únicas series fundamentales con profundidad son percentiles de TVL de cripto, del backfill de DefiLlama. De acciones, **ninguna**:

```
IBM / NVDA / XOM — las 14 métricas fundamentales de cada uno:  1 observación
```

**42 de 42 series con exactamente una observación.** No es una carencia parcial: **el dominio fundamental de acciones es un *snapshot*, no una serie.**

**Causa, ya documentada**: la ingesta de acciones es manual vía el conector MCP de Alpha Vantage y nunca se automatizó. Hay una única captura, del 2026-09-03.

---

## 4. El hallazgo: hay dos gaps distintos, no uno

De las 6 líneas base, **0 son computables**. Pero por razones distintas, y eso cambia la prioridad:

| Mecanismo | Variable observada | Estado de la variable | Estado de la línea base |
|---|---|---|---|
| `CUSTOMER_DEMAND` | `demand` | **existe** (proxy `revenue_growth_yoy_pct`) | **1 observación** → imposible |
| `INPUT_COST` | `price` (del insumo) | `MISSING` — `tech:cowos` no tiene datos | la pregunta no se plantea |
| `CAPACITY_CONSTRAINT` | `capacity_utilization` | `MISSING` en todo el sistema | idem |
| `PRICING_POWER` | `capacity_utilization` | `MISSING` | idem |
| `SUPPLY_SHORTAGE` | `inventory` | `MISSING` | idem |
| `LEAD_TIME` | `lead_time` | `MISSING` | idem |

> **Un gap de variable y un gap de línea base son gaps distintos, y solo uno de los seis mecanismos ha llegado al segundo.**

Cinco están bloqueados **un paso antes**: no tiene sentido diseñar cómo se declara una línea base de inventario cuando no hay ninguna medida de inventario. Trabajar en líneas base "en general" sería construir para cinco casos que no existen.

**El único mecanismo donde la línea base es el cuello de botella real es `CUSTOMER_DEMAND`** — y es justamente el de la cadena `NVDA → TSMC`.

---

## 5. Segundo hallazgo: una línea base sobre una tasa no es lo mismo que sobre un nivel

`demand(org:nvidia)` se resuelve con `revenue_growth_yoy_pct`, que **ya es una variación**: lleva dentro una comparación contra el año anterior.

Eso plantea una pregunta que el diseño de P6 no había visto:

```
¿la línea base de `demand` es "el ingreso normal"  →  y entonces el proxy ya la incorpora
                                                       mal, porque compara contra UN año concreto,
   o "el crecimiento normal"                       →  y entonces hace falta una distribución
                                                       de crecimientos, que es otra cosa?
```

Con una sola observación las dos son imposibles, así que la pregunta no bloquea hoy. Pero **cambia qué habría que pedir**: no "historia de ingresos", sino **historia de la métrica que efectivamente resuelve la variable**, que no es lo mismo.

---

## 6. Qué se descartó, y por qué

| Descartado | Razón |
|---|---|
| Diseñar un vocabulario de tipos de línea base ahora | cinco de seis mecanismos no han llegado a esa pregunta; sería construir para casos inexistentes |
| Usar "el valor anterior" como línea base | los seis mecanismos piden un **nivel normal**, no un valor previo. Con 2 observaciones se puede restar; no se puede saber qué es normal |
| Derivar la línea base de las 18 series con 2 fechas | dos puntos son un cambio, no una distribución. Además esos dos puntos son dos ejecuciones del cron, no dos periodos económicos |
| Tratar el *snapshot* de acciones como serie de longitud 1 | una media de un elemento es el elemento: parecería una línea base sin serlo. Mismo error que la cota trivial de P6.1 |

---

## 7. Supuestos invalidados

**El diseño de P6 daba por hecho que las líneas base eran un problema de declaración** — *"una línea base es una declaración, no un cálculo: 'el valor anterior' no es una línea base"* (informe de P6, §8).

Eso **sigue siendo cierto para el criterio**, pero era incompleto: aunque se declarara el criterio *"media de 8 trimestres"*, **no habría datos para aplicarlo**. El problema no es solo dónde se declara: es que la serie no existe. La deuda estaba mal caracterizada.

---

## 8. Gaps nuevos que aparecen

1. **El dominio fundamental de acciones no es una serie.** Afecta a mucho más que P6.2: el Thesis Ledger para acciones, cualquier comparación temporal de márgenes o EPS, y la página de *Asset Research* de Power BI.
2. **La línea base tiene que ser de la métrica que resuelve la variable**, no de la magnitud conceptual. Si mañana `demand` se resolviera con otra métrica, la línea base cambiaría con ella.
3. **Las 18 series con exactamente 2 fechas** son un artefacto del cron, no periodos económicos. Merecen mirarse antes de que alguien las tome por historia.

---

## 9. La decisión que queda abierta

**¿De dónde sale la historia de fundamentales de acciones?** Cuatro opciones, con lo que cuesta cada una:

| Opción | Qué da | Coste / riesgo |
|---|---|---|
| **Alpha Vantage, endpoints trimestrales** (`INCOME_STATEMENT`, `EARNINGS`) | historia real de ingresos y beneficios, varios años | 25 llamadas/día y **manual**: el mismo patrón que dejó 1 observación. Habría que automatizarlo primero |
| **Acumular el *snapshot* actual** | historia a partir de hoy | no sirve para P6.2: tardaría años en dar una distribución |
| **Yahoo Finance**, como en el backfill de precio | ya validado en este proyecto para acciones | hay que comprobar si publica fundamentales trimestrales históricos; **no medido todavía** |
| **No desbloquear `CUSTOMER_DEMAND` y pasar a otro mecanismo** | cero coste | los otros cinco están bloqueados un paso antes, así que no hay a dónde pasar |

**Mi recomendación**: antes de elegir, **medir si Yahoo o Alpha Vantage publican de verdad la serie trimestral** que haría falta — exactamente el mismo paso que se dio antes del bloque 4 del backfill, cuando se comprobó en vivo que `outputsize=full` estaba bloqueado y eso cambió la fuente elegida. Es una medición corta y evita diseñar sobre un supuesto.

**No se implementa nada hasta decidirlo.**

---

## 10. Estado

**No se ha tocado código.** Medición de solo lectura.

```
suite     447 tests · OK        (sin cambios)
qa.py     STATUS: VERIFIED
knowledge PASS
```

**Impacto sobre fases anteriores**: ninguno funcional. Recaracteriza la deuda de líneas base registrada en P6 (§7 de este informe) y añade una deuda nueva y mayor: el dominio fundamental de acciones.

**Implicaciones para los consumidores**: la página *Asset Research* de Power BI muestra fundamentales de acciones como si fueran comparables en el tiempo. Con una observación por serie, cualquier gráfico temporal de esas métricas es un punto. No se cambia nada ahora — Power BI está desacoplado — pero queda registrado.
