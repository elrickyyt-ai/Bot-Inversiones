# Event & Claim Layer (v1)

```
SOURCE → EVIDENCE → CLAIM → EVENT CANDIDATE → EVENT
```

Responde *«¿qué afirmaciones y acontecimientos podemos reconstruir a partir de la evidencia disponible?»*. **No** responde «¿qué impacto económico tendrá?» — eso es Assessment, y P4 no lo toca.

```bash
python3 engine/events/consolidar.py --noticias --explicar 3
python3 engine/events/consolidar.py --tecnico XRP --explicar 1
```

## Lo primero: P4 no interpreta texto

Los extractores son **reglas declaradas y auditables**, no análisis de lenguaje. Cada claim lleva el nombre y la versión del extractor que la produjo (`sentiment_assertion/v1`, `price_change_threshold/v1(umbral=10.0%)`) y esa regla se puede volver a ejecutar.

Un titular como *«Ripple Is Bringing Agentic AI Payments to the XRP Blockchain»* contiene un acontecimiento que este sistema **no sabe extraer**. Lo correcto es no extraerlo, en vez de fabricar una tripleta plausible. Esa incapacidad no se esconde: aparece en los `unknowns` de todos los eventos de noticias — *«el contenido del titular no se ha interpretado: P4 extrae la postura declarada por el medio, no el acontecimiento que el texto describe»*.

Por eso el predicado es `ASSERTS_SENTIMENT` y no `IS_BULLISH`: la claim dice que **ese medio afirma** una postura, no que la postura sea cierta. Es lo que impide que una `ASSERTION` de Evidence se convierta en un hecho.

## Identidad y deduplicación

```
identity_key = (entidad principal, tipo de evento, acción, fecha a su granularidad, magnitud bucketizada)
```

**Ningún campo de texto libre entra en la clave.** La similitud textual no es criterio de identidad. Dos titulares distintos sobre el mismo movimiento del mismo activo el mismo día son un evento con dos evidencias; dos titulares casi idénticos sobre días distintos son dos eventos.

## Soporte: cuatro números que no se colapsan en uno

| campo | qué mide |
|---|---|
| `evidence_count` | cuántas evidencias lo sostienen |
| `independent_support_count` | cuántas **fuentes** distintas (no artículos) |
| `primary_support` | hay medición propia o fuente primaria |
| `contradictory_support` | cuántas claims lo niegan |

Tres artículos del mismo medio son 3 evidencias y **1 fuente** — el caso que impide leer «más artículos» como «más confirmado».

**Límite conocido y declarado**: si tres medios *distintos* reproducen el mismo teletipo de agencia, este sistema los cuenta como tres fuentes independientes, porque la cadena de sindicación no es observable con los campos que hay. No se disimula: va en los `unknowns` de todo evento sostenido sólo por prensa.

## Estados: por naturaleza y procedencia, no por recuento

| estado | condición |
|---|---|
| `CONFIRMED` | soporte primario (medición del propio contrato o tier 1), sin contradicción — **una sola fuente basta** |
| `CORROBORATED` | ≥2 fuentes independientes secundarias, sin contradicción |
| `CANDIDATE` | una sola fuente secundaria, o un indicador derivado de nuestra propia serie |
| `CONTESTED` | hay una negación y ninguna primaria la resuelve — **no se resuelve por mayoría** |
| `REJECTED` | una fuente primaria lo desmiente |
| `REVISED` | evidencia posterior cambió su magnitud |

Un indicador `DERIVED` de nuestra propia serie (la volatilidad de 30 días) **no** confiere soporte primario: su umbral y su ventana son decisiones de modelo. El `status_reason` lo dice con esas palabras, en vez de hablar de «un solo medio» donde no hay ninguno.

## Cuatro relojes, ninguno inventado

`published_at`, `occurred_at`, `effective_at`, `known_at`. Un anuncio sobre una acción futura **no** se representa como si la acción hubiese ocurrido: `occurred_at` es cuándo se anunció y `effective_at` cuándo aplica. El validador rechaza un `effective_at` anterior al `occurred_at`.

## Medido sobre datos reales

| | |
|---|---|
| Noticias XRP | 100 Evidence → **50 claims** → **43 eventos** · 4 `CORROBORATED`, 39 `CANDIDATE` |
| Técnico XRP | 3.628 Evidence → 219 claims → 219 eventos · **67 `CONFIRMED`** (price_change, MEASURED), 152 `CANDIDATE` (volatilidad) |

Ningún evento de noticias sale `CONFIRMED`: las cinco fuentes del corpus son tier 3 y ninguna es primaria.

## Fixtures sintéticas, y por qué

El corpus real **no contiene** los casos 3 a 7. Medido: 0 titulares idénticos, 1 solo par con solapamiento léxico ≥0.5 y del mismo medio, ninguna fuente de tier 1, ningún par anuncio/entrada-en-vigor. Fabricar esos casos dentro de `data/news/` sería contaminar datos reales, así que viven en `tests/fixtures/eventos/casos.json` declarados como sintéticos.

`ANNOUNCES_ACTION` sigue el mismo patrón que `INFERRED` en Evidence: está en el vocabulario porque el modelo **tiene** que poder representar un anuncio con efecto posterior, pero **ningún extractor de v1 lo produce** y hay un test que lo comprueba.

## Regla arquitectónica

Un Event puede **consumir** Knowledge para resolver entidades y **jamás** escribirlo. Ni un evento ni una inferencia modifican una relación estructural: eso exige `nueva fuente → verificación → actualización controlada`. Los tres módulos de P4 no tienen ninguna llamada de escritura a fichero, y hay un test que lo verifica sobre el código además de comprobar por hash que `knowledge/` y `data/` no cambian.

---

## Episodios (P6.2d, 2026-09-07)

La tercera unidad, sobre las dos que esta capa ya tenía:

```
DOCUMENTO   una pieza concreta        → Evidence, con su source_ref
EVENTO      un hecho identificable    → Event, deduplicado por identity_key
EPISODIO    una secuencia en curso    → episodios.json + episodios.py
```

P4 ya evitaba el doble conteo por **redundancia** (`evidence_count` vs `independent_support_count`). No evitaba el doble conteo por **continuidad**: cinco piezas sobre momentos distintos del mismo hilo son cinco eventos legítimos y **un solo asunto abierto**.

```bash
python3 engine/events/episodios.py     # valida el registro declarado
```

Sobre los datos reales de XRP: **50 documentos → 100 evidencias → 43 eventos → 5 eventos en 1 episodio**.

**Un episodio se declara, nunca se infiere** (D-19). Agrupar por parecido de texto es justo lo que esta capa se prohibió en su regla de identidad. La pertenencia se ancla al `news_id` del Data Contract (estable), no al `event_id` (derivado, se regenera). El estado `OPEN`/`RESOLVED` importa: en julio de 2026 el sistema trató la aprobación en comité de la CLARITY Act como catalizador resuelto y hubo que corregirlo a mano cuando el Senado aplazó la votación.

`episode_id = None` significa *"no se ha declarado que pertenezca a ningún episodio"*, **no** *"es un hecho aislado"*.

## Event study mínimo (P6.2c)

```bash
python3 engine/events/estudio_resultados.py
```

Responde, de extremo a extremo: *¿qué información estaba disponible, qué sorpresa implicaba, cuándo pudo negociarse por primera vez y cómo reaccionó el activo?*

Emite **observaciones individuales**. No agrega, no calcula medianas, no produce señales y no afirma causalidad — `suficiencia_de_muestra()` bloquea la agregación y explica por qué (hoy: `SIN_BENCHMARK_EN_EL_CONTRATO`).

Lo que hace visible el `reportTime` de Alpha Vantage: **`pre-market` se negocia la misma sesión, `post-market` la siguiente**. XOM publica casi siempre pre-market; IBM y NVDA post-market. Sin ese campo, 28 de los 52 eventos de la muestra se medirían en una sesión en la que la noticia todavía no existía. Si falta, `first_tradable_at` es `None`: no se elige una franja por defecto.
