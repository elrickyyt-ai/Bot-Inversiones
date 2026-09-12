# P6 · Economic Impact v1

**Fecha**: 2026-09-07 · **Rama**: `claude/bot-inversiones-audit-peh0x2`
**Orden de implementación seguido**: el que fijaste — schema → auditoría de vocabulario → mecanismo/entradas → resolutor determinista → validador → fixtures sintéticas → camino real de P5C → verificar el 100% esperado.

---

## 1. El resultado

```
IMPACTO ECONOMICO — 2026-09-07   (42 tramos sobre 22 caminos)
  magnitud: {'NOT_APPLICABLE': 37, 'UNKNOWN': 5}
```

Ninguna magnitud. **No es un fallo**: es lo que la evidencia y los parámetros declarados permiten afirmar, y cada tramo dice **cuál de las dos cosas** le pasa — que el mecanismo no puede, o que falta el dato.

El tramo real de la cadena de P5C:

```
IMPACTO … rel:0046 : revenue
  mecanismo    CUSTOMER_DEMAND  (CONDITIONALLY_QUANTIFIABLE)
  sobre        revenue de org:tsmc
  direccion    UNKNOWN   (heredada de P5B)
  magnitud     UNKNOWN        materialidad UNKNOWN        horizonte UNKNOWN
  fitness      PROXY          coeficiente  UNKNOWN
  motivos      EVIDENCE_ONLY_BY_PROXY, MATERIALITY_UNKNOWN,
               NO_BASELINE, NO_TRANSMISSION_COEFFICIENT
      · rel:0046 acredita que la relación existe, no en qué proporción:
        falta % de los ingresos del proveedor que vienen de ese cliente.
        Causalidad no es materialidad
      · la variable solo se resuelve con un proxy declarado: P6 puede degradar
        una afirmación cuantitativa a cualitativa, nunca al revés
      · no hay coeficiente declarado: v1 no lo estima — un coeficiente
        estadístico sería salida de un modelo, no evidencia
      · no hay línea base declarada: un cambio sin un "respecto a qué" no es
        una magnitud
```

**Cuatro motivos distintos, nombrados por separado.** Antes de P6 esto era un `UNKNOWN` sin desglosar.

---

## 2. `derecho_a_magnitud()` — el núcleo, y por qué es una función y no una rama

Como dijiste que el objetivo de v1 no es producir números sino demostrar que el sistema **sabe cuándo tendría derecho a producirlos**, hice de eso una función propia y comprobable en vez de una condición enterrada:

```python
derecho_a_magnitud(mecanismo, relationship_id, fitness) -> (bool, [motivos])
```

Cuatro precondiciones, ninguna sustituible por un valor implícito: variable **medida** (no aproximada) · **materialidad** declarada · **coeficiente** de origen declarado · **línea base**.

Hoy devuelve `False` en el 100% de los casos reales. **Un test puebla las tablas de declaración y comprueba que se enciende** — sin eso, "siempre `False`" podría ser un bug en vez de una decisión, y nadie lo sabría.

```
derecho_a_magnitud("CUSTOMER_DEMAND", "rel:0046", "MEASURES")
  hoy                     → False, [MATERIALITY_UNKNOWN, NO_TRANSMISSION_COEFFICIENT, NO_BASELINE]
  con las tablas llenas   → True,  []
  con fitness=PROXY       → False, [EVIDENCE_ONLY_BY_PROXY]     ← ni con todo lo demás
```

El último caso es tu invariante hecho ejecutable: **P6 degrada de cuantitativo a cualitativo, nunca al revés.**

---

## 3. Tres cosas donde me aparté de lo que propusiste, con la medición delante

### 3.1 `magnitude_capability`: `QUANTIFIABLE`, no `SUPPORTED`

Propusiste `SUPPORTED` / `NOT_SUPPORTED` / `CONDITIONALLY_SUPPORTED`. Ejecuté la auditoría de vocabulario (paso 2 de tu orden) contra los 14 vocabularios cerrados del proyecto:

```
SUPPORTED                    COLISIÓN con support(P5B)
NOT_SUPPORTED                libre
CONDITIONALLY_SUPPORTED      libre
QUANTIFIABLE                 libre
NOT_QUANTIFIABLE             libre
CONDITIONALLY_QUANTIFIABLE   libre
```

`SUPPORTED` en P5B es **el respaldo probatorio de una afirmación concreta**; aquí sería **la capacidad de una clase de mecanismo**. Una propiedad de instancia y una de tipo. Bajo la regla que acabas de aceptar —*un token se comparte si y solo si significa lo mismo*— no pueden compartirlo. La familia `QUANTIFIABLE` estaba libre entera y además dice exactamente qué es.

La cara opuesta de la misma regla: **`fitness` sí comparte `MEASURES` y `PROXY` con `catalogo.py`**, porque es una proyección de lo que P5D calcula. Darles otro nombre serían dos nombres para una idea.

### 3.2 Horizonte en días, no en categorías

Dijiste que verificara antes qué se puede reutilizar. Medido:

- P4 tiene `temporal`, pero son **marcas absolutas** (`published_at`, `occurred_at`, `effective_at`, `known_at`), no un horizonte.
- El Thesis Ledger sí tiene una convención: **`horizonte_evaluacion_dias`**, 90 por defecto.

O sea: **no hay vocabulario categórico de horizonte, y sí hay una convención en días.** Así que `horizon` es `{state, dias_min, dias_max}`. Añadir `IMMEDIATE`/`SHORT_TERM`/`MEDIUM_TERM`/`LONG_TERM` habría creado un vocabulario nuevo para algo que el proyecto ya expresa de otra forma.

### 3.3 Tu tabla de mecanismos dice "Dirección: Sí" en los siete — P5B dice otra cosa

En tu tabla los 7 mecanismos producen dirección. En el código de P5B, tres declaran explícitamente que **no**:

```python
"CAPACITY_CONSTRAINT": puede_producir: []      # no produce signo: habilita PRICING_POWER
"LEAD_TIME":           puede_producir: []      # es un desplazamiento temporal, no un signo
"SUBSTITUTION":        puede_producir: ["NEUTRAL"]
```

**No lo he cambiado en ninguno de los dos sitios.** P5B está cerrado y es la autoridad sobre la dirección; P6 la **hereda tal cual** y no vuelve a decidir signos — si lo hiciera habría dos motores opinando sobre lo mismo, y el día que discreparan nadie sabría cuál leer. Hay un test que compara tramo a tramo, no contra el conjunto de valores posibles.

Tu columna de magnitud sí la implementé literalmente, y coincide con la mía en los 7.

---

## 4. Lo que el validador impide, con regla ejecutable

| Regla | Forma ejecutable |
|---|---|
| magnitud sin base de comparación | `KNOWN` exige `value` + `unit` + `baseline`, las tres |
| **cero inventado** | `value == 0` exige `evidence_ids` no vacío |
| **causalidad ≠ materialidad** | `magnitude KNOWN` exige `materiality KNOWN`. **General**, no solo NVDA/TSMC |
| coeficiente estimado | `coefficient_origin == ESTIMATED` **rechazado** en v1, con el mensaje que dice por qué |
| coeficiente sin rastro | `OBSERVED`/`DECLARED` exigen `coefficient_ref` |
| promover cualitativo a cuantitativo | `magnitude KNOWN` con `fitness` `PROXY`/`INSUFFICIENT`/`UNKNOWN` → rechazado |
| confundir "no puedo" con "no sé" | `NOT_QUANTIFIABLE` ⇒ `NOT_APPLICABLE`, **y al revés también** |
| valor implícito | una pieza sin resolver lleva su valor a **null y presente** |
| probabilidad/score/precio/confianza | **rechazo por nombre de campo** |

Sobre el último: no es una lista de estilo. Es la única forma de que "solo un campito de confianza" no entre nunca.

---

## 5. Combinar no es sumar

`combinar()` **no tiene campo `total`, y no existe por diseño**. Devuelve:

```
state       UNKNOWN si algún tramo no resuelve, o si los horizontes difieren
conocido[]  los que sí, identificados
unresolved[] los que no, con su motivo
support     el del PEOR componente (regla de P1b y P5B)
```

Lo que no puede pasar es presentar la suma de los resueltos como si fuera el total — la trampa de *"la media de los que contestaron"*. Cuatro tests lo fijan.

---

## 6. `ESTIMATED` existe en el vocabulario y está prohibido

Recojo tu precisión: no *"los coeficientes no pueden existir"* sino *"P6 v1 no puede emitir uno que no proceda de una relación declarada y verificable"*.

```python
ORIGENES_COEFICIENTE = {OBSERVED, DECLARED, ESTIMATED, UNKNOWN}
ORIGENES_PERMITIDOS_V1 = {OBSERVED, DECLARED, UNKNOWN}
```

Se declara **entero** a propósito: escribirlo es lo que permite **rechazarlo explícitamente**, en vez de que el caso simplemente no exista todavía y aparezca un día sin que nadie lo note. El mensaje del validador dice la razón de fondo: *un coeficiente estimado no es Evidence ni Knowledge, es salida de un modelo, y esa capa no existe.*

---

## 7. Verificación

```bash
python3 -m unittest discover -s tests            # 422 tests · OK   (381 → +41)
python3 engine/contract/qa.py --require-parquet  # STATUS: VERIFIED
python3 engine/knowledge/consulta.py --validar   # PASS
python3 engine/impact/impacto.py org:nvidia --combinar
```

**Nuevos**: `engine/impact/{esquema_impacto,requisitos_magnitud,impacto}.py` + `README.md` · `tests/test_impacto.py`
**Modificados**: ninguno. **P5A, P5B, P5D y Knowledge no se han tocado** — verificado por hash y por un test que comprueba que `valoracion.py` no importa nada de P6.

Los 41 tests en diez bloques: vocabulario · independencia de las cuatro piezas · reglas de magnitud · coeficiente estimado · "no puedo" ≠ "no sé" · campos prohibidos · combinación · camino real de P5C · control positivo del derecho a magnitud · invariantes.

---

## 8. Deuda y siguiente paso

**Deuda registrada**: `capacity_utilization` no aparece como requisito en los tramos `INPUT_COST` de la cadena real porque P5B enruta ese impulso por R5 (coste derivado) y no por la vía de capacidad. Es coherente con P5B y no lo he tocado, pero significa que `tech:cowos` se evalúa hoy como insumo de coste y no como restricción de capacidad — que es el ángulo económicamente interesante. Merece una mirada cuando haya datos.

**Lo que ya no bloquea**: la arquitectura para P7. P6 no importa precio en ninguna forma, y hay un test que comprueba que ningún campo del esquema contiene `precio` ni `price`.

**Lo que sigue bloqueando, por orden de valor**:

1. **Materialidad** — es lo más barato y lo que más desbloquea. `rel:0046` necesita un peso con fuente; hoy `MATERIALIDAD` está vacía y bloquea los tres mecanismos condicionalmente cuantificables a la vez. Requiere decidir si Knowledge gana un campo de peso (cambio de esquema de P2, con su propia decisión).
2. **`capacity_utilization(tech:cowos)`** — `MISSING` desde P5D, sin fuente identificada.
3. **Líneas base** — ninguna declarada. Es una declaración, no un cálculo: *"el valor anterior"* no es una línea base.
