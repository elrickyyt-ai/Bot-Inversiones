# Fase 0 — Arquitectura conceptual del sistema de inteligencia financiera

Este documento es el resultado del **PASO 1 al PASO 6** solicitados: análisis crítico de la propuesta original, arquitectura conceptual definitiva, mapa de módulos, separación MVP/Intermedio/Avanzado, exclusiones deliberadas y definición del primer producto funcional.

Todavía no hay tecnologías, APIs ni infraestructura cloud elegidas. Eso es intencional.

---

## PASO 1 — Análisis crítico de la propuesta original

La visión es coherente y ambiciosa, y el principio de "nunca una sola métrica decide" es correcto. Pero antes de construir nada hay que señalar problemas reales, porque varios de ellos, si no se corrigen ahora, se conviertirán en deuda estructural.

### 1.1 Carencias

- **No existe un "objeto central" del sistema.** Hay 12 motores y 12 scores, pero ninguna entidad que los una a lo largo del tiempo. Falta un concepto de **Tesis de Inversión** como entidad versionada (con fecha, supuestos, scores de entrada, conclusión y fecha de revisión), que es justo lo que el punto 21 (memoria histórica) necesita para funcionar. Sin esta entidad, "guardar lo que dijo el sistema" no tiene dónde anclarse.
- **No hay identidad de instrumentos (master data).** Splits, cambios de ticker, ADRs, doble cotización, delistados... si no se resuelve la identidad del activo de forma centralizada, cada motor puede referirse "al mismo" activo con datos distintos y el sistema fallará en silencio.
- **Falta un bucle de calibración explícito.** El backtesting (punto 22) y la memoria histórica (punto 21) generan evidencia sobre qué funciona, pero no hay ningún módulo que use esa evidencia para **ajustar pesos o desconfiar de un motor concreto**. Sin eso, el sistema nunca aprende, solo registra.
- **No se define el horizonte temporal de cada análisis.** Momentum, opciones y volumen intradía son señales de corto plazo; DCF y moat son de largo plazo. Mezclarlos sin declarar "¿para qué horizonte es esta tesis?" produce contradicciones falsas (no reales) entre motores.
- **No hay modelo de coste/frecuencia.** Analizar 12 disciplinas con LLMs para todo un universo de activos, todos los días, no es viable económicamente. Falta decidir qué se analiza a diario, qué semanalmente y qué solo bajo demanda.
- **Cartera y personalización llegan demasiado tarde en el discurso (puntos 29-30) pero son las que convierten "análisis de un activo" en "ayuda a MI decisión".** Aunque su implementación completa sea tardía, el diseño debe contemplarlas desde el principio como una capa, no como un anexo.

### 1.2 Redundancias

- **Fundamental / Valuation / Growth / Business Quality Score** se solapan: crecimiento es una lectura temporal de los propios fundamentales, y calidad de negocio comparte variables (márgenes, ROIC) con fundamentales. No hace falta fusionarlos en la presentación, pero sí en el pipeline de datos que los alimenta.
- **Technical / Momentum / Volume Score**: en la práctica profesional, momentum y volumen son subconjuntos del análisis técnico. Tratarlos como tres motores independientes triplica el pipeline de precios sin necesidad.
- **News Intelligence / Influential People / Sentiment**: los tres hacen lo mismo a nivel de infraestructura (ingerir texto, puntuar credibilidad de la fuente, extraer sentimiento/relevancia/sorpresa, vincular a un activo). La diferencia real está solo en **quién es la fuente** (medio vs. persona) y **qué peso se le da**. Deberían compartir una única infraestructura NLP con un "credibility/influence weighting" configurable, no ser tres motores separados.

### 1.3 Conceptos mal planteados

- **Escala 0-10 para todos los scores.** El propio planteamiento duda de ella, con razón: comparar un "Sentiment Score: 7.4" con un "Fundamental Score: 7.4" sugiere que son magnitudes equivalentes, y no lo son. Una escala absoluta sin definición operacional es **falsa precisión** disfrazada de rigor. (Se resuelve en el Paso 2.)
- **Fórmulas "conceptuales" como producto de factores** (`Impact Score = Relevancia × Sorpresa × Credibilidad × Alcance × Persistencia`, `Statement Impact = Influencia × Relevancia × Sorpresa × Credibilidad × Alcance`). Multiplicar cinco números subjetivos entre 0 y 1 (o 0 y 10) no es una fórmula causal validada, es una heurística de **ranking**. Hay que tratarla como tal explícitamente (sirve para ordenar noticias por prioridad, no para "calcular" un impacto real en precio) para no generar una falsa sensación de modelo cuantitativo.
- **DCF como pilar del Valuation Engine.** Para empresas sin beneficios estables, de alto crecimiento o cíclicas, un DCF es extremadamente sensible a supuestos y aporta poca información marginal sobre los múltiplos comparables. Debe presentarse con una fiabilidad declarada según el tipo de negocio, no como output central homogéneo para cualquier activo.
- **Sistema multiagente de 8+ agentes + Critic Agent para cada activo, cada día.** Es coherente como diseño de razonamiento, pero como está planteado (ejecutarlo para todo lo que se analiza) es inviable en coste y en latencia, y muy difícil de depurar cuando algo falla (¿qué agente introdujo el error?). Es una capacidad de fase avanzada, activada bajo demanda, no un motor de ejecución continua.
- **Derivatives Engine con Gamma Exposure y Unusual Options Activity** en el diseño temprano. Son señales de altísimo ruido incluso con datos de pago de calidad institucional; en fase inicial, con datos limitados, aportarían más ruido que señal.

### 1.4 Riesgos metodológicos

- **Look-ahead bias no solo en el backtesting, también en el uso diario.** Los fundamentales "as reported hoy" no son los que un inversor tenía disponibles en su momento (restatements, revisiones). Si el sistema no guarda datos **point-in-time**, cualquier revisión histórica de una tesis estará contaminada.
- **El LLM puede racionalizar relación causa-efecto que no existe** entre una noticia y un movimiento de precio (correlación temporal ≠ causalidad). Hay que diseñar los prompts para que el sistema declare explícitamente "el precio se movió X, la noticia fue Y, no hay evidencia de causalidad confirmada" salvo que sea evidente (ej. profit warning).
- **Comparar predicción del sistema vs. resultado real sin controlar por el régimen de mercado** (punto 21) puede atribuir al sistema aciertos que en realidad son del mercado alcista general. Hace falta comparar contra un benchmark, no en términos absolutos.
- **El Critic Agent, si comparte modelo y contexto con el agente que generó la tesis, hereda su sesgo** (cámara de eco). Debe diseñarse con acceso a evidencia que el agente principal no priorizó, o con un prompt estructuralmente adversarial, no solo "revisa esto".

### 1.5 Problemas de datos

- Las fuentes gratuitas típicas (yfinance, Alpha Vantage free, Financial Modeling Prep free, etc.) tienen: retraso de 15-20 min o EOD, límites de peticiones bajos, huecos e inconsistencias, e histórico limitado. El diseño debe **asumir esto desde el día 1**, no descubrirlo después.
- Datos de calidad institucional (point-in-time fundamentals, order book, opciones con profundidad) son caros (Bloomberg, FactSet, S&P Capital IQ, OPRA). No son razonables para un proyecto personal en fase inicial.
- **13F institucional tiene hasta 45 días de retraso**; el "Institutional Flow Engine" nunca será tiempo real por diseño regulatorio, no por limitación técnica. Hay que comunicarlo como una propiedad estructural del dato, no como un defecto a corregir.

### 1.6 Costes ocultos

- Procesar miles de noticias/día con un LLM sin un filtro barato previo (embeddings + reglas de relevancia) dispara el coste de tokens rápidamente.
- Guardar series intradía + embeddings de todas las noticias para muchos activos crece en almacenamiento incluso dentro de free tiers.
- Tener simultáneamente SQL + NoSQL + Time-series DB + Vector DB + Object Storage desde el MVP (punto 20) es sobreingeniería: más superficies que mantener, más coste fijo, sin beneficio temprano.

### 1.7 Dificultades técnicas

- Sincronización de timestamps y zonas horarias entre mercados y fuentes (pre-market, after-hours, distintos husos) es una fuente de errores subestimada.
- Un motor de razonamiento que "detecte contradicciones" entre 12 señales es, en la práctica, ingeniería de prompts + reglas híbridas difícil de validar; hay riesgo real de que dé la ilusión de razonamiento estructurado sin que realmente lo sea. Debe construirse de forma incremental y testeable, no como una caja negra de LLM.

---

## PASO 2 — Arquitectura conceptual definitiva

Manteniendo el flujo original (Datos → Análisis → Interpretación → Tesis → Riesgo → Escenarios → Decisión), se reorganiza para resolver las carencias anteriores, **sin elegir tecnología todavía**:

```
0. INSTRUMENT MASTER DATA
   (identidad única de cada activo: ticker, nombre, clase de activo,
    mercado, moneda, corporate actions, mapeo entre fuentes)
        │
1. DATA ACQUISITION LAYER
   (conectores agrupados por naturaleza del dato, no por disciplina:
    Precios/Mercado · Fundamentales · Texto y Eventos · Macro · Flujos · Derivados[fase posterior])
        │
2. EVIDENCE LAYER (almacenamiento crudo, inmutable, con procedencia)
   Cada dato entra con: fuente, timestamp de publicación, timestamp de ingestión,
   nivel de credibilidad de la fuente, versión "as of" (point-in-time)
        │
3. DOMINIOS ANALÍTICOS (consolidación de los 12 motores originales en dominios)
   ┌───────────────────────────┬─────────────────────────────────────────┐
   │ Fundamental & Quality      │ estados financieros, ratios, valoración,  │
   │ Domain                     │ moat, management, crecimiento             │
   │ Market Behavior Domain     │ técnico, volumen/microestructura,         │
   │                            │ derivados (cuando existan)                │
   │ Macro & Regime Domain      │ ciclo económico, tipos, inflación,        │
   │                            │ liquidez, commodities                     │
   │ Narrative & Sentiment      │ noticias, personas influyentes,           │
   │ Domain                     │ sentimiento (una sola infraestructura NLP)│
   │ Flow & Ownership Domain    │ insiders, institucionales, ETF flows      │
   │ Catalyst Domain            │ eventos futuros con probabilidad/impacto  │
   └───────────────────────────┴─────────────────────────────────────────┘
   El Risk Domain es transversal: no "compite" con los demás, los audita a todos.
        │
4. SCORING & NORMALIZATION LAYER
   Metodología explícita y versionada (ver Paso 2.1). Cada score lleva siempre:
   valor, método usado, confianza, calidad del dato, fecha, versión de metodología.
        │
5. REASONING & SYNTHESIS LAYER
   Motor central + función crítica: detecta convergencia / divergencia /
   contradicción entre dominios, y construye la TESIS DE INVERSIÓN (entidad versionada)
        │
6. THESIS LEDGER (memoria histórica)
   Registro inmutable de cada tesis emitida, con sus supuestos y su score de confianza,
   para comparación futura contra el resultado real
        │
7. PERSONALIZATION & PORTFOLIO LAYER
   Traduce la tesis (que es objetiva) en relevancia para EL USUARIO
   (tamaño de posición sugerido, encaje en cartera, alertas relevantes)
   — nunca modifica los hechos ni los scores, solo la priorización
        │
8. PRESENTATION LAYER
   Informe estructurado (Paso 18), alertas, API, dashboard
        │
9. FEEDBACK & CALIBRATION LOOP
   Compara Thesis Ledger vs. resultados reales → ajusta pesos de scoring,
   detecta qué dominios predicen mejor en qué régimen macro, qué fuentes son fiables
   (retroalimenta a las capas 3 y 4)
```

La diferencia clave frente al planteamiento original: **la capa 0 (identidad), la capa 6 (tesis como entidad) y la capa 9 (calibración)** no existían explícitamente antes, y son las que convierten un conjunto de motores en un sistema que aprende y es auditable.

### 2.1 Metodología de scoring (respuesta directa al punto 16)

Recomendación: **no usar una escala absoluta 0-10 con significado fijo**. En su lugar:

- Cada score se calcula como una **posición relativa (percentil o z-score)** dentro de un universo de comparación explícito y declarado (histórico propio del activo, sector, mercado). Ejemplo: "Margen operativo en percentil 78 frente a su sector en los últimos 5 años".
- El percentil se **mapea a una escala 0-10 solo para presentación** (UX), nunca como magnitud comparable entre disciplinas distintas.
- Cada score se publica siempre como una tripleta: **Score + Confidence Score + Data Quality Score**, tal como pedía el punto 16, pero con definición operacional:
  - *Data Quality Score* = función de completitud, antigüedad y número de fuentes independientes que corroboran el dato.
  - *Confidence Score* = función de la dispersión del propio cálculo (ej. cuánto cambia el score si se excluye la fuente menos fiable) y del tamaño de muestra histórica disponible.
- La metodología de cálculo se **versiona** (v1, v2...). Un score de hace 6 meses solo es comparable con uno actual si comparte versión de metodología; si no, el sistema debe advertirlo explícitamente en vez de comparar cosas distintas silenciosamente.

Esto evita la falsa precisión sin renunciar a la comparabilidad que el usuario pedía.

---

## PASO 3 — Mapa de módulos y relaciones

| Módulo | Consume de | Produce para | Tipo |
|---|---|---|---|
| Instrument Master Data | Fuentes de referencia (listados, corporate actions) | Todos los módulos | Fundacional |
| Data Acquisition (Precios) | Fuentes de mercado | Evidence Layer, Market Behavior Domain | Ingesta |
| Data Acquisition (Fundamentales) | Filings, proveedores fundamentales | Evidence Layer, Fundamental Domain | Ingesta |
| Data Acquisition (Texto/Eventos) | Noticias, comunicados, transcripciones | Evidence Layer, Narrative Domain | Ingesta |
| Data Acquisition (Macro) | Bancos centrales, estadísticas oficiales | Evidence Layer, Macro Domain | Ingesta |
| Data Acquisition (Flujos) | Filings regulatorios (13F, Form 4), ETF providers | Evidence Layer, Flow Domain | Ingesta (fase posterior) |
| Evidence Layer | Todas las ingestas | Todos los dominios analíticos | Almacenamiento con procedencia |
| Fundamental & Quality Domain | Evidence Layer (fundamentales) | Scoring Layer, Reasoning Layer | Analítico |
| Market Behavior Domain | Evidence Layer (precios/volumen) | Scoring Layer, Reasoning Layer | Analítico |
| Macro & Regime Domain | Evidence Layer (macro) | Scoring Layer, todos los dominios (como contexto) | Analítico transversal |
| Narrative & Sentiment Domain | Evidence Layer (texto) | Scoring Layer, Catalyst Domain, Reasoning Layer | Analítico |
| Flow & Ownership Domain | Evidence Layer (flujos) | Scoring Layer, Reasoning Layer | Analítico |
| Catalyst Domain | Narrative Domain, calendario corporativo | Reasoning Layer, Alert System | Analítico |
| Risk Domain | Todos los dominios + Market Behavior | Reasoning Layer, Portfolio Layer | Auditor transversal |
| Scoring & Normalization | Todos los dominios analíticos | Reasoning Layer, Thesis Ledger | Normalización |
| Reasoning & Synthesis (+ Critic) | Scoring Layer, Risk Domain | Thesis Ledger, Presentation Layer | Núcleo de decisión |
| Thesis Ledger | Reasoning Layer | Feedback Loop, Presentation Layer | Memoria |
| Personalization & Portfolio | Thesis Ledger, perfil del usuario | Presentation Layer, Alert System | Capa de usuario |
| Feedback & Calibration | Thesis Ledger + resultados reales de mercado | Scoring Layer, Reasoning Layer (pesos) | Aprendizaje |
| Presentation Layer | Reasoning Layer, Personalization | Usuario | Salida |
| Alert System | Catalyst, Narrative, Risk, Flow domains | Usuario | Salida |

Relación transversal importante: **Risk Domain y Macro & Regime Domain no son "un motor más"**: alimentan y contextualizan a todos los demás en lugar de competir con ellos en pie de igualdad dentro del Reasoning Layer.

---

## PASO 4 — MVP / Versión intermedia / Versión avanzada

### MVP
- **Universo**: watchlist pequeña y manual (10-30 tickers), solo acciones, ETFs e índices.
- **Módulos activos**: Instrument Master Data (mínimo), Data Acquisition de precios EOD + fundamentales trimestrales (1-2 fuentes), Fundamental & Quality Domain (versión básica: ratios + comparación con histórico propio, sin DCF), Market Behavior Domain (tendencia + medias + RSI/MACD/ATR), Risk Domain básico (volatilidad, drawdown, beta).
- **Scoring**: metodología de percentiles ya definida desde el inicio (no rehacerla después), pero limitada a comparación contra histórico propio (todavía sin comparables sectoriales completos).
- **Reasoning**: sin LLM multiagente; reglas explícitas y transparentes que señalan divergencias obvias (ej. "valoración en percentil alto + momentum negativo").
- **Salida**: informe estructurado (plantilla del punto 18) generado bajo demanda para un ticker, con secciones no disponibles marcadas explícitamente como "DATOS INSUFICIENTES" en vez de omitirse.
- **Memoria**: Thesis Ledger simple (guardar cada informe generado) para poder comparar más adelante.

### Versión intermedia
- Se añaden: Narrative & Sentiment Domain (pipeline NLP único), Macro & Regime Domain, comparación sectorial/competidores en valoración, DCF con escenarios (con fiabilidad declarada según tipo de negocio), Flow & Ownership Domain (insiders/institucional, asumiendo el retraso estructural).
- Se activa el Feedback Loop básico: comparación de tesis pasadas (30/90/180 días) vs. resultado real, contra benchmark.
- Se introducen 2-3 agentes especializados (no 8) con una pasada crítica ligera, usada bajo demanda, no en modo batch continuo.
- Alertas para un conjunto reducido y priorizado de eventos (resultados, cambios fundamentales relevantes, noticias de alto impacto).
- Ampliación de universo (posible entrada de criptomonedas como primera clase de activo adicional).

### Versión avanzada
- Sistema multiagente completo con Critic Agent adversarial, Catalyst Engine con calendario y probabilidades, Derivatives Engine (cuando el activo lo soporte y los datos sean asequibles).
- Portfolio Layer completo: concentración, correlación, stress testing, escenarios macro aplicados a cartera real.
- Backtesting formal con walk-forward analysis y control de sesgos (look-ahead, survivorship, overfitting).
- Personalización rica (perfil completo del punto 29) y soporte multi-activo completo (bonos, divisas, materias primas, opciones, futuros).
- Feedback loop automático ajustando pesos de scoring por régimen macro y por fiabilidad histórica de cada dominio/fuente.

---

## PASO 5 — Qué NO incluir inicialmente, y por qué

- **Derivatives Engine (opciones, gamma exposure, unusual activity)**: datos de calidad son caros y de difícil acceso para un proyecto personal; la relación señal/ruido es baja incluso con buenos datos.
- **Sistema multiagente completo (8+ agentes) en modo de ejecución continua**: coste y latencia altos, y muy difícil de depurar cuando el resultado final es incorrecto (no se sabe qué agente lo causó). Se introduce de forma incremental y bajo demanda.
- **DCF/valoración intrínseca sofisticada desde el inicio**: alta sensibilidad a supuestos; antes hace falta una base de comparación sectorial sólida para que el DCF aporte algo más que los múltiplos simples.
- **Flow & Ownership Engine (insiders/institucional)**: el retraso estructural de los datos (hasta 45 días en 13F) hace que aporte poco valor mientras el núcleo del sistema todavía no es fiable; mejor priorizarlo cuando el resto ya funcione.
- **Portfolio stress-testing y escenarios macro sobre cartera real**: requiere que el análisis de activo individual ya sea confiable, y requiere tener realmente una cartera modelada; introducirlo antes es construir sobre una base no validada.
- **Order book / microestructura en tiempo real**: caro, y solo relevante si el horizonte de la tesis es de corto plazo, lo cual no está definido como objetivo principal del proyecto.
- **Backtesting/optimización automática de pesos**: si se activa antes de tener una metodología de scoring estable, el riesgo de sobreajustar (overfitting) a un histórico corto es alto.
- **Universo multi-activo amplio (bonos, divisas, materias primas, futuros) desde el inicio**: cada clase de activo tiene su propio modelo de datos y proveedores; ampliar antes de validar el núcleo en acciones/ETFs multiplica la complejidad de integración sin necesidad.
- **Cuestionario de personalización extenso**: dos o tres parámetros (horizonte, tolerancia al riesgo) bastan al principio; invertir en una UX de onboarding rica antes de tener un núcleo analítico fiable es prematuro.

---

## PASO 6 — Primer producto funcional

**Generador de informe individual (Fundamentals + Técnico + Riesgo) para una watchlist reducida de acciones/ETFs.**

El usuario selecciona un ticker de una lista corta y predefinida. El sistema:

1. Resuelve su identidad en el Instrument Master Data (mínimo viable).
2. Descarga precios EOD históricos y fundamentales trimestrales de 1-2 fuentes.
3. Calcula el conjunto definido de ratios/indicadores fundamentales y técnicos, siempre comparados contra el histórico propio del activo (todavía sin comparables sectoriales completos).
4. Calcula un Risk Score básico (volatilidad, drawdown, beta).
5. Aplica la metodología de scoring por percentiles definida en el Paso 2.1, con Confidence y Data Quality explícitos.
6. Genera el informe con la plantilla del punto 18, marcando explícitamente como "DATOS INSUFICIENTES" cualquier sección para la que aún no exista motor (sentimiento, macro, catalizadores, flujos).
7. Guarda el informe en el Thesis Ledger con fecha, para poder compararlo más adelante con lo que realmente ocurrió con el precio.

Este primer producto no usa LLM multiagente ni fuentes de pago. Su objetivo no es ser completo, sino **demostrar que el bucle completo Datos → Análisis → Interpretación → Tesis → Memoria funciona de extremo a extremo, de forma barata y auditable**, antes de añadir ninguna disciplina más.

---

## Siguiente paso

Con esta arquitectura conceptual acordada, la Fase 1 (definición de producto/MVP en detalle: alcance exacto del informe, fuentes de datos concretas para el MVP, modelo de datos mínimo) sería el siguiente bloque de trabajo, tal como propone la metodología de desarrollo del punto 32 — todavía sin elegir tecnologías ni infraestructura cloud.
