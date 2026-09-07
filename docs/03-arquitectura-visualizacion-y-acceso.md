# Arquitectura de visualización y acceso — planificación (sin código)

> **Estado (2026-09-07)**: **especificación de consumo, no contrato arquitectónico.** Escrito cuando el backend era `JSON → Data Contract → UI`. Sigue vigente en la división de funciones y en la regla de que Web App y Power BI son **consumidores, no la lógica analítica**. Han quedado obsoletos `data/*.json` y las métricas como único nivel analítico: el motor ha crecido con Knowledge, Evidence, Events, Causal Path, Assessment e Impact. Ver `docs/06-diseno-p61-materialidad.md` §7. **No se rediseña hasta que el modelo del motor esté consolidado.**


**Fecha:** 2026-09-03 (revisión 2) · **Origen:** propuesta detallada aportada por el usuario (arquitectura híbrida Web App + Power BI), revisada, verificada y ajustada aquí antes de construir nada. No es una de las 10 fases originales de la Fase 0 — es una capa transversal nueva: cómo se **consulta** todo lo que los motores ya producen, sin depender de leer el repositorio de GitHub directamente.

**Revisión 2 (misma fecha):** el usuario aportó una segunda revisión externa con tres correcciones — verificadas todas antes de aplicarlas: (1) Cloudflare recomienda ahora Workers en vez de Pages para proyectos nuevos, Pages en modo mantenimiento; (2) Alpha Vantage sí ofrece peticiones ilimitadas para proyectos open-source/educativos verificados, pero el proceso de verificación no está documentado públicamente — acción pendiente del usuario, no asumida; (3) un dato dentro del bundle de una Web App estática no es equivalente a un dato en backend, aunque el acceso a la página esté protegido por Cloudflare Access. Las tres se incorporan abajo.

## 0. Cómo he tratado la propuesta original

La propuesta que trajiste es sólida y la sigo en la mayor parte de sus decisiones. Antes de adoptarla verifiqué sus tres cifras de coste clave (no venían de esta sesión, así que no las di por buenas sin más):

| Afirmación | Verificado | Fuente |
|---|---|---|
| Cloudflare Pages: 500 builds/mes gratis | ✅ Correcto | [temps.sh](https://temps.sh/blog/cloudflare-pages-free-tier-limits-2026) |
| Supabase free: pausa tras 1 semana de inactividad | ✅ Correcto — además, **máximo 2 proyectos activos** en el plan gratis (no mencionado en la propuesta original) | [supabase.com/docs](https://supabase.com/docs/guides/platform/free-project-pausing) |
| Vercel Hobby: prohíbe uso comercial | ✅ Correcto, pero **matiz importante**: un proyecto personal, no monetizado, sin pagar a nadie por construirlo, no encaja en su propia definición de "comercial" — Vercel Hobby probablemente sería técnicamente válido aquí. Cloudflare Workers sigue siendo la elección más limpia porque evita esa ambigüedad y además es la plataforma que Cloudflare recomienda hoy para proyectos nuevos, no porque Vercel esté prohibido para este caso concreto | [vercel.com/docs/plans/hobby](https://vercel.com/docs/plans/hobby) |

Encontré además un **hueco de privacidad que la propuesta no cubría**: Cloudflare Pages/Workers, por defecto, publica el sitio en una URL **pública** — no hay "privado por defecto" como sí tienen los Artifacts de Claude. Para un proyecto que va a mostrar tu watchlist y tesis, eso no es aceptable tal cual. La solución (también gratis, verificada) es **Cloudflare Access**: hasta 50 usuarios autenticados a 0€, más que suficiente para uso individual — pones el sitio detrás de un login antes de que sea consultable. Lo incorporo como pieza obligatoria, no opcional. ([zerotrustcost.com](https://zerotrustcost.com/cloudflare-zero-trust-pricing))

### Ajustes propios sobre la propuesta (incluye la revisión 2 del usuario, ya verificada)

1. **No metería FastAPI en el MVP.** Los motores ya escriben JSON a disco. Un sitio estático (React/Vite) puede leer esos JSON directamente en tiempo de build — sin servidor, sin proceso corriendo, sin nada que mantener vivo. FastAPI se añade en **v1**, cuando de verdad haga falta algo dinámico (editar la watchlist desde la web, consultas ad hoc) — no antes. Es la misma disciplina de "no construir lo que no hace falta todavía" que hemos aplicado en todo el proyecto.
2. **La automatización de Alpha Vantage/Bigdata.com no se resuelve con hosting.** Es el problema real que ya documenté en `engine/equity/README.md` y `engine/news/README.md`: el conector MCP solo es invocable desde una sesión de Claude, no desde un cron job. Hay tres caminos: (a) mantenerlo manual; (b) clave propia de Alpha Vantage como *secret* de GitHub Actions; o (c) **verificado ahora**: Alpha Vantage ofrece explícitamente "unlimited API requests for verified open-source or educational projects" en su propia página de soporte — este repositorio es público, así que probablemente calificaría, pero **el proceso de verificación no está documentado públicamente**, hay que escribir a `support@alphavantage.co` y preguntar. Acción pendiente del usuario, no la doy por concedida. Mientras tanto, **CoinGecko, Kraken, FRED y DefiLlama ya son 100% automatizables hoy mismo con GitHub Actions**, gratis, sin ningún cambio de cuenta. ([alphavantage.co/support](https://www.alphavantage.co/support/))
3. **Hosting: Cloudflare Workers, no Cloudflare Pages** (corrección de la revisión 2 del usuario, verificada). Cloudflare lo dice sin rodeos en su propia documentación: *"Now that Workers supports both serving static assets and server-side rendering, you should start with Workers"* — Pages sigue soportado pero está en modo mantenimiento, toda la inversión nueva va a Workers. Para nuestro caso concreto es además **mejor en el plan gratis**: servir assets estáticos es gratis e ilimitado en Workers (hasta 20.000 assets por versión), sin el límite de 500 builds/mes que sí tiene Pages — y si en v1 hace falta algo dinámico, ya estamos en la plataforma correcta sin migrar. Cloudflare Access se aplica igual sobre Workers. Todas las referencias a "Cloudflare Pages" en este documento pasan a ser "Cloudflare Workers (modo assets estáticos)". ([developers.cloudflare.com/workers](https://developers.cloudflare.com/workers/platform/pricing/))
4. **Un dato en el bundle de una Web App estática no es un dato en backend**, aunque la página esté detrás de Cloudflare Access (corrección de la revisión 2 del usuario, y tiene razón). Cloudflare Access protege la ruta, pero si algún día se filtra un asset por una URL de vista previa (`*.workers.dev`) sin la misma política aplicada, o si Access se desconfigura, cualquier cosa que esté en el bundle queda expuesta. Por eso, regla explícita para el Data Contract y los adaptadores (§5): **la Web App solo puede recibir datos pseudonimizados de investigación (tickers, métricas de mercado, tesis) — nunca credenciales, nunca cantidades ni importes reales de `cartera/`**. Esa separación ya la aplicamos de facto con Airtable; aquí se convierte en regla de diseño explícita del propio adaptador, no solo de buena voluntad.

---

## 1. Evaluación del estado actual

- 6 motores en Python puro (sin dependencias externas más allá de la librería estándar), cada uno con su propio `score.py` que devuelve un diccionario con una forma razonablemente consistente ya hoy: `activo`, `fecha_dato`/`fecha`, métricas propias del dominio, `data_quality_pct`/`confidence_pct`.
- Un motor de razonamiento (`engine/reasoning/thesis.py`) que ya produce Bull/Base/Bear case, contradicciones y factores de invalidación — el contenido más "presentable" que tenemos.
- Un Thesis Ledger (`engine/reasoning/ledger.py`) con memoria histórica en JSONL, versionado en git.
- 19 pruebas de humo (`tests/`).
- Una watchlist viva en Airtable (9 activos) y un mapa de fases en un Artifact — ninguno de los dos pensado para navegar el contenido analítico en detalle, solo para el estado del proyecto y el seguimiento de posiciones.
- **Lo que falta para una interfaz real**: los informes de cada motor son ahora mismo *prosa en Markdown* (`informes/*.md`), no datos estructurados reutilizables por una UI. Ese es el trabajo real antes de wireframes: un **Data Contract** y una capa que traduzca la salida de cada `score.py` a ese contrato.

## 2. Web App vs. Power BI — reparto de responsabilidades

| | Web App | Power BI |
|---|---|---|
| Uso diario / consulta rápida | ✅ | ❌ (fricción de abrir el .pbix) |
| Insights, contradicciones, tesis narrativa | ✅ | ❌ (Power BI no narra bien texto largo) |
| Exploración libre, cruces ad hoc, series largas | ❌ (no reinventar un BI) | ✅ |
| Backtesting, análisis de correlación | ❌ | ✅ (DAX, matrices, drill-through) |
| Evolución histórica de la cartera | Vista resumen | Análisis profundo |
| Alertas / "qué ha cambiado hoy" | ✅ | ❌ |

No se duplica funcionalidad: la Web App es la puerta de entrada diaria y narrativa; Power BI es el laboratorio cuantitativo cuando quieras profundizar. Coincido en esto con la propuesta original punto por punto.

## 3. Comparativa tecnológica y de costes (verificada)

| Capa | Opción elegida | Precio | Límite gratis | Qué pasa al superarlo | ¿Tarjeta? | Riesgo de coste inesperado |
|---|---|---|---|---|---|---|
| Frontend | React + Vite | 0€ (open source) | — | — | No | Ninguno |
| Hosting | **Cloudflare Workers (modo assets estáticos)** | 0€ | Assets estáticos: gratis e ilimitados, 20.000 assets/versión. 100.000 peticiones/día solo cuenta para invocaciones dinámicas (irrelevante en MVP) | Se bloquean peticiones dinámicas extra (no aplica a servir el sitio) | No para el plan free | Bajo |
| Acceso privado | Cloudflare Access | 0€ | 50 usuarios autenticados | Se bloquea el login del usuario 51 (no aplica a un proyecto de 1 persona) | No | Ninguno |
| Backend (v1, no MVP) | FastAPI en Cloudflare Workers | 0€ en el rango de uso personal | 100.000 peticiones/día, 10ms CPU/petición | Se bloquean peticiones extra | No | Bajo |
| Datos (MVP) | JSON/Parquet en el propio repo | 0€ | Límite de tamaño de repo de GitHub (varios GB) | — | No | Ninguno |
| Datos (v1+) | Supabase | 0€ | 500MB BD, 5GB egress, **2 proyectos activos**, pausa tras 1 semana sin uso | Proyecto se pausa (no se borra), hay que "despertarlo" | Sí, para verificar cuenta aunque el plan sea gratis | Bajo si se vigila el egress |
| Automatización | GitHub Actions | 0€ | 2.000 min/mes (repos privados) | Se bloquean workflows hasta el mes siguiente | No | Bajo, un motor de este tamaño consume minutos de sobra |
| BI | Power BI Desktop + My Workspace | 0€ | Solo para ti, no para compartir con otros | Necesitarías Pro (~10€/usuario/mes) o Premium para compartir | No para Desktop | Ninguno mientras sea solo para ti |

**Orden de prioridad de coste, tal como pediste**: 0€ (Cloudflare Workers + Access + GitHub Actions + ficheros) → 0€ con matices (Supabase, cuando haga falta) → nada de Vercel Pro ni Power BI Pro mientras el proyecto sea solo tuyo.

## 4. Arquitectura de datos

```
Fuentes (Alpha Vantage, FRED, CoinGecko, DefiLlama, Kraken, NEWS_SENTIMENT)
        │
        ▼
Ingesta (fetch_data.py automatizable vía GitHub Actions | Alpha Vantage/Bigdata.com manual hasta decidir el punto 2 de arriba)
        │
        ▼
Motores Python existentes (engine/crypto, engine/technical, engine/macro, engine/equity, engine/news, engine/scoring, engine/reasoning)
        │
        ▼
NUEVO: capa de normalización → Data Contract (ver §5) → data/*.json versionado en git
        │
        ├──────────────► Power BI Desktop (lee los JSON/Parquet directamente, sin API)
        │
        ▼
Web App estática (React/Vite, lee los mismos JSON en build-time)
        │
        ▼
Cloudflare Workers, modo assets estáticos + Cloudflare Access (privado)
```

Nota: en el MVP, Power BI y la Web App leen **el mismo árbol de ficheros**, no una API — es la forma más barata y más simple de garantizar que ambos muestran lo mismo sin duplicar lógica.

## 5. Data Contract

Partiendo de lo que ya propusiste, y ajustado a lo que nuestros motores **ya emiten hoy** (para que la migración sea barata, no un rediseño):

### Nivel métrica (una fila por observación)

```
asset_id            # "BTC", "NVDA" -- ya es el campo "activo" en todos los motores
asset_type          # "crypto" | "equity"
domain              # "fundamental" | "tecnico" | "macro" | "noticias"
metric              # "pe_ratio", "rsi14", "market_cap_percentile_365d"...
value                # el valor numérico o texto
unit                 # "%", "USD", "ratio", "categorico"
data_as_of           # NUEVO (revisión 2 del usuario) -- fecha a la que corresponde el dato
retrieved_at          # NUEVO (revisión 2 del usuario) -- cuándo se descargó, con hora (ISO 8601 UTC)
source               # "Alpha Vantage", "CoinGecko", "FRED"...
source_priority       # NUEVO (revisión 2 del usuario) -- 1 = fuente primaria/oficial (FRED),
                       # 2 = agregador de mercado establecido (Alpha Vantage, CoinGecko, Kraken,
                       # DefiLlama, NEWS_SENTIMENT). Distinto de la jerarquía de credibilidad de
                       # noticias (engine/news/sources.py, esa es para periodismo, esta es para
                       # fuentes de datos de mercado) -- ambas conviven, no se fusionan.
confidence_pct       # ya existe en tecnico/reasoning, falta añadirlo a crypto/macro
data_quality_pct     # ya existe en crypto/equity, falta añadirlo a tecnico/macro
calculation_method   # referencia al README del motor (ya documentado, falta enlazarlo)
source_url           # cuando aplica (ej. informe de origen)
```

**Por qué `data_as_of` y `retrieved_at` por separado** (razón que dio el usuario en la revisión 2, y es correcta): un P/E "a fecha de hoy" descargado hoy no es lo mismo que el mismo P/E descargado la semana que viene pero que sigue correspondiendo al cierre trimestral de hace un mes. Sin esta distinción, un futuro backtesting (Fase 8) podría usar sin darse cuenta un dato que en la fecha simulada todavía no existía — *look-ahead bias*, el mismo riesgo que la Fase 0 ya advirtió sobre el propio backtesting.

### Nivel tesis (uno por tesis generada)

```
thesis_id            # ya existe como "id" en el Ledger
asset_id
thesis_type          # "crypto" | "equity"
bull_case / base_case / bear_case      # ya existen tal cual en thesis.py
contradictions / convergences / divergences   # ya existen tal cual
invalidation_factors # ya existe como "factores_que_invalidarian_la_tesis"
confidence_pct
data_as_of            # NUEVO -- misma razón que arriba
retrieved_at           # NUEVO
```

**Conclusión de la comprobación que pediste antes de diseñar la UI**: el modelo **es suficiente**, porque ya está casi implícito en lo que los motores devuelven — el trabajo real no es inventar un esquema nuevo, es escribir un adaptador delgado por motor que traduzca su `score_asset()` a estas dos formas y lo escriba en `data/`. Eso sí conviene hacerlo **antes** de la UI, tal como pedías, para no tener que rehacer la interfaz cada vez que un motor cambie de forma.

**Regla de clasificación de datos** (revisión 2 del usuario, incorporada como regla de diseño del adaptador, no solo como nota): estos dos niveles del contrato solo pueden contener datos de mercado y de análisis — nunca campos derivados de `cartera/` (cantidades, importes, flujo de caja). Un adaptador que en el futuro quisiera cruzar con `CARTERA_A` real tendría que vivir fuera de este contrato, en la capa de Power BI/almacenamiento privado, nunca en lo que acaba en el bundle de la Web App.

## 6. Sitemap

```
/                       Dashboard
/watchlist              Lista completa (equivalente web de la tabla Airtable)
/asset/{ticker}         Asset Research (tabs: Overview, Fundamental, Valuation,
                         Technical, Volume, Sentiment, News, Macro, Thesis, History)
/insights                Divergencias, contradicciones, cambios recientes
/thesis-ledger            Historial de tesis + resultado cuando se evalúan
/news                     Noticias + sentimiento + personas influyentes
/macro                    Régimen EE.UU./Eurozona
/about                    Metodología, fuentes, limitaciones -- transparencia del sistema
```

## 7. User flows (los dos que más importan)

**Flujo diario ("¿qué ha cambiado?")**: entra en `/` → ve Market Regime + Key Insights → si algo llama la atención (ej. "XOM: contradicción") → clic → aterriza en `/asset/XOM#thesis` con el detalle completo y las fuentes.

**Flujo de investigación de un activo nuevo**: `/watchlist` → añade ticker (siempre que ya exista un motor que lo soporte) → `/asset/{ticker}` tab Overview → navega por tabs según lo que necesite, sin recargar la sensación de "página distinta por cada motor".

## 8. Wireframes textuales

### Dashboard

```
┌─────────────────────────────────────────────────────────┐
│ BOT-INVERSIONES              [Buscar activo...]   ⚠ 3   │
├─────────────────────────────────────────────────────────┤
│ RÉGIMEN DE MERCADO                                       │
│  EE.UU.: Expansión con inflación pegajosa                │
│  Eurozona: Pivote hawkish reciente del BCE                │
├─────────────────────────────────────────────────────────┤
│ INSIGHTS DE HOY                                           │
│  ⚠ XOM   — Contradicción: BPA +112,8% vs. último trim. -4,3%│
│  ↕ BTC/ETH — Divergencia fundamental débil / técnico alcista│
│  ● DOT   — Confidence reducido (45%), incidencia de datos  │
├─────────────────────────────────────────────────────────┤
│ WATCHLIST                                                 │
│  Ticker  Fundamental  Técnico    Estado   Última tesis     │
│  BTC     percentil 11%  3/4 alcista  Comprado  ver tesis →  │
│  NVDA    PEG 0,57       alcista      Vigilando ver tesis →  │
│  ...                                                       │
└─────────────────────────────────────────────────────────┘
```

*Nota deliberada:* nada de "score global 87/100" — cada columna es la métrica real del motor correspondiente, no un número inventado que las mezcle.

### Asset Research (`/asset/XOM`)

```
┌─────────────────────────────────────────────────────────┐
│ XOM — Exxon Mobil Corp                    $164,15  -0,24%│
│ [Overview][Fundamental][Valoración][Técnico][Noticias]    │
│ [Macro][Tesis][Histórico]                                  │
├─────────────────────────────────────────────────────────┤
│ TAB: Tesis                                                 │
│                                                             │
│ ⚠ CONTRADICCIÓN DETECTADA (regla automática, no manual)    │
│  Crecimiento BPA interanual: +112,8%                        │
│  Última sorpresa de resultados: -4,35% (falló el consenso)  │
│  → La cifra anual puede estar dominada por una base de      │
│    comparación baja, no por el momento actual.               │
│                                                             │
│  BULL CASE   / BASE CASE   / BEAR CASE   (texto completo)   │
│  Factores que invalidarían esta tesis: [lista]               │
│  Confidence: 75%   ·   Fuente: engine/equity + Alpha Vantage │
└─────────────────────────────────────────────────────────┘
```

### Insights (`/insights`)

```
┌─────────────────────────────────────────────────────────┐
│ INSIGHTS                          Filtrar: [Todos ▾]      │
├─────────────────────────────────────────────────────────┤
│ ⚠ CONTRADICCIÓN · XOM · hoy                                │
│ ↕ DIVERGENCIA · BTC · hoy                                  │
│ ↕ DIVERGENCIA · ETH · hoy                                  │
│ ↓ CONFIDENCE REDUCIDO · DOT · incidencia de datos, 22-jul   │
│ ⚠ CONTRADICCIÓN (noticias) · XRP · regulatorio pendiente    │
└─────────────────────────────────────────────────────────┘
```

### Thesis Ledger (`/thesis-ledger`)

```
┌─────────────────────────────────────────────────────────┐
│ THESIS LEDGER                                              │
├─────────────────────────────────────────────────────────┤
│ BTC · registrada 02-sep-2026 · precio 66.402,30 €           │
│  Umbral de movimiento significativo: ±20,3% (90 días)        │
│  Evaluación: pendiente (vence 01-dic-2026)                    │
├─────────────────────────────────────────────────────────┤
│ [Cuando se evalúe:]                                          │
│  Variación real: +XX% · Veredicto: bull_case / base_case /   │
│  bear_case · ¿Coincidió con la lectura del sistema?           │
└─────────────────────────────────────────────────────────┘
```

## 9. Diseño de Power BI (10 páginas, igual que propusiste, con una adaptación)

1. Market Overview · 2. Asset Comparison · 3. Fundamentals · 4. Valuation · 5. Technical · 6. Macro · 7. News & Sentiment · 8. Thesis Performance (agregados del Ledger: tasa de acierto por dominio, por tipo de convergencia/divergencia — la pregunta que motivó construir el Ledger) · 9. Portfolio (cruzando con `cartera/`, pseudonimizado, **nunca cantidades reales expuestas si el .pbix se comparte alguna vez**) · 10. Backtesting (cuando exista la Fase 8).

## 10. Propuesta de stack mínimo (MVP)

```
GitHub (ya existe)
Python (ya existe, motores)
GitHub Actions (nuevo, gratis) — automatiza CoinGecko/Kraken/FRED/DefiLlama
React + Vite (nuevo)
Cloudflare Workers, modo assets estáticos + Cloudflare Access (nuevo, gratis, privado)
Power BI Desktop (ya lo sabes usar)
```

Sin FastAPI, sin Supabase, sin backend corriendo en ningún sitio — todo estático, todo gratis, todo privado.

## 11. Roadmap

**MVP** — capa de normalización (Data Contract) + Web App estática de solo lectura (Dashboard, Asset Research, Insights, Thesis Ledger) detrás de Cloudflare Access + GitHub Actions automatizando las 4 fuentes que ya no requieren conector MCP + Power BI Desktop conectado a los mismos ficheros.

**v1** — decisión sobre Alpha Vantage/Bigdata.com (clave propia vs. manual) + FastAPI si de verdad hace falta interacción (editar watchlist desde la web) + extender el Thesis Ledger a acciones (necesita serie de precios diaria para acciones, pendiente desde antes) + página `/news` completa con personas influyentes.

**v2** — Fase 8 (backtesting) integrada en Power BI · Fase 9 (gestión de cartera) · posible Supabase si el volumen de datos ya no es cómodo en ficheros.

## 12. Qué NO construir todavía

- Backend/API (FastAPI) — esperar a v1.
- Supabase o cualquier base de datos — los ficheros aguantan de sobra en el MVP.
- Automatización de Alpha Vantage/Bigdata.com — depende de una decisión tuya pendiente (clave propia o no).
- Cualquier forma de autenticación multiusuario más allá de Cloudflare Access (no hay "usuarios" plural en este proyecto).
- Power BI Service / Pro — mientras el consumo sea solo tuyo, Desktop + My Workspace basta.

## 13. Riesgos técnicos y económicos

- **Egress de Supabase** cuando se introduzca (v2): vigilar el consumo si hay iteración rápida de datos; 5GB gratis es generoso pero no infinito.
- **Cloudflare Access mal configurado** podría dejar el sitio accesible sin login por error de configuración — verificar explícitamente antes de subir cualquier dato real.
- **Alpha Vantage 25 llamadas/día**: si se automatiza con clave propia, un workflow programado mal calibrado puede agotar la cuota sin que te des cuenta hasta que falle silenciosamente — necesita alerta, no solo cron.
- **Divergencia entre Web App y Power BI** si en algún momento dejan de leer exactamente el mismo Data Contract — el riesgo que el Data Contract está pensado para evitar, pero exige disciplina de mantenerlo actualizado en cada motor nuevo.
- **Ninguno de los pasos de este MVP tiene coste recurrente** si se sigue el stack de §10 — el primer euro real solo aparece si se necesita Supabase con más de 500MB, o Power BI Pro para compartir con alguien más.

## 14. Recomendación final para el MVP

Data Contract → adaptadores por motor → GitHub Actions automatizando las fuentes libres → Web App estática de solo lectura en Cloudflare Workers + Access → Power BI Desktop sobre los mismos ficheros. Sin backend, sin base de datos, sin coste. Cuando esto esté en pie y lo hayas usado un tiempo real, decidimos si v1 hace falta de verdad o si el MVP ya cubre el 80% de para qué lo querías.

## 15. Orden de construcción acordado (revisión 2 del usuario)

1. Data Contract + adaptadores por motor.
2. `data/` normalizado y consistente.
3. Tests para ese contrato.
4. Power BI conectado al mismo dataset.
5. Web App.

**Aprobado conceptualmente por el usuario el 2026-09-03, con las tres correcciones de arriba ya incorporadas.** Alcance autorizado para empezar a programar: **únicamente los pasos 1-3** (Data Contract, adaptadores, tests) — sin tocar todavía la interfaz ni Power BI. Ver `engine/contract/` para la implementación.
