# Protocolo de informes y trazabilidad

**Vigente desde**: 2026-09-07 · **Aplica a**: toda fase y subfase a partir de P6.2.

Este protocolo existe por una razón concreta: **que un chat nuevo o un agente distinto no tenga que reconstruir la arquitectura leyendo cientos de commits.** Un commit dice *qué* cambió; no dice qué se midió antes, qué se descartó, ni qué supuesto quedó invalidado por el camino. Eso se pierde si no se escribe, y es justo lo que más cuesta reconstruir.

---

## 1. Qué deja cada fase

| Artefacto | Dónde | Cuándo |
|---|---|---|
| **Diseño** | `docs/NN-diseno-<fase>.md` | antes de escribir código, y se espera revisión |
| **Informe de implementación** | `informes/AAAA-MM-DD_<fase>.md` | al cerrar la fase |
| **Decisiones y revisiones** | `docs/DECISIONES.md` | cada vez que se decide o se revisa algo |
| **Estado acumulado** | `docs/ESTADO.md` | se actualiza en cada fase |
| **Trazabilidad por fase** | `informes/…_trazabilidad_…md` | se actualiza en cada fase |

Una fase pequeña puede fundir diseño e informe en un documento. **Ninguna puede saltarse `DECISIONES.md` ni `ESTADO.md`.**

---

## 2. Qué registra un informe, obligatoriamente

1. **Qué se midió** — con el comando o la consulta, y el resultado literal. Medir antes de diseñar es la disciplina central del proyecto; el informe tiene que dejar la medición reproducible.
2. **Qué cambió** — ficheros, con qué es nuevo y qué se modificó.
3. **Qué se descubrió** — hallazgos que no se buscaban. Suelen ser lo más valioso.
4. **Qué se descartó y por qué** — la opción no tomada, con su razón. Sin esto, dentro de seis meses alguien la reevalúa desde cero.
5. **Qué supuestos quedaron invalidados** — incluidos los propios. Si el diseño decía A y la implementación demostró B, se dice.
6. **Qué gaps nuevos aparecieron** — un gap descubierto y no registrado es un gap perdido.
7. **Desviaciones del diseño** — qué se hizo distinto y con qué justificación.
8. **Deuda abierta** — técnica y epistemológica, con dónde queda registrada en el código.
9. **Commits relevantes**.
10. **Tests y QA** — número antes y después, y el resultado de `qa.py`.
11. **Impacto sobre fases anteriores** — qué se tocó, qué no, y cómo se verificó que no se tocó.
12. **Implicaciones para los consumidores** — Power BI, Web App, cron.

---

## 3. La historia no se borra

Cuando una medición cambia una decisión anterior, **no se reescribe el pasado**. En `docs/DECISIONES.md` queda la cadena completa:

```
decisión original  →  evidencia nueva  →  revisión  →  decisión vigente
```

Esto importa especialmente ahora que el sistema empieza a adquirir conocimiento económico real: una decisión revisada con evidencia es información sobre el dominio, no un error que convenga esconder. Borrarla haría que la misma discusión se repitiera.

Lo mismo aplica a los tests: **un test que se apoya en que algo no existe caduca cuando ese algo se documenta**, y eso es correcto. Se reescribe a la propiedad que sigue siendo cierta, y el informe dice cuál era y por qué cambió.

---

## 4. Reglas de escritura

- **La medición, literal.** Nada de *"hay pocos datos"*: `NVDA/fundamental/revenue_growth_yoy_pct → 1 fila`.
- **Lo que no se hizo, también.** Una fase que decide no construir algo tiene que decir qué y por qué.
- **Los defectos propios se registran igual que los heredados**, y con el mismo detalle.
- **Ningún informe afirma que algo funciona sin haberlo ejecutado.** Si no se comprobó, se dice que no se comprobó.
- **Los números llevan su fuente**: comando, fichero o documento citable.

---

## 5. El punto de entrada

`docs/ESTADO.md` es el documento que lee primero quien entra. Su estructura es fija:

```
OBJETIVO → ARQUITECTURA ACTUAL → CAPAS CERRADAS → POR QUÉ SE DISEÑARON ASÍ
        → ESTADO ACTUAL (medido) → DEUDAS → PRÓXIMA DECISIÓN
```

Si `ESTADO.md` no basta para entender dónde está el proyecto y cuál es la siguiente decisión, el protocolo no se está cumpliendo.
