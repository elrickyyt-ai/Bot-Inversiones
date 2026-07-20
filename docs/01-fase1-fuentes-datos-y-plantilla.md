# Fase 1 — Fuentes de datos del MVP y plantilla de informe

Resultado de explorar y **verificar en vivo** (no solo documentar de oídas) qué fuentes gratuitas son accesibles para el MVP, probando cada una antes de recomendarla.

## 1. Fuentes verificadas

| Fuente | Cubre | Coste | Verificación | Limitación importante |
|---|---|---|---|---|
| **SEC EDGAR** (`data.sec.gov`, API XBRL) | Fundamentales de empresas que reportan a la SEC (IBM, NVIDIA, ExxonMobil) | Gratis, sin clave | ✅ Probado: 227 puntos trimestrales de Revenue de IBM, con fecha de `filed` y `accn` por dato | Solo empresas que reportan a la SEC — no cubre emisores no estadounidenses |
| **Yahoo Finance** (`query1.finance.yahoo.com/v8/finance/chart`) | Precio histórico diario de acciones e índices | Gratis, sin clave | ✅ Probado: histórico de IBM desde 1962, y del índice S&P 500 (`^GSPC`) | Endpoint no documentado oficialmente por Yahoo (puede cambiar sin aviso); el módulo de fundamentales (`quoteSummary`) SÍ exige autenticación y no es accesible así — por eso los fundamentales vienen de SEC EDGAR, no de aquí |
| **CoinGecko + Kraken** (públicas) | Precio cripto | Gratis, sin clave | ✅ Ya validado en el análisis retrospectivo de `CARTERA_A` | CoinGecko limita a 365 días de histórico en el plan gratuito; Kraken a ~720 velas diarias. Para el MVP (datos hacia adelante, no retrospectiva) esto no es un problema |
| Factsheet/KIID del proveedor del fondo (Fidelity/Vanguard/iShares, PDF público) | TER, objetivo, índice de referencia oficial de cada fondo de `CARTERA_A` | Gratis | No probado en este paso (descarga puntual, no API) | Sin API — actualización manual/periódica, no automatizable de forma sencilla |
| App de MyInvestor (pantallazo manual) | NAV/valor diario y ganancia de los 9 fondos de `CARTERA_A` | Gratis | Ya usado (tu pantallazo original) | Sin API pública conocida para estas clases de fondos — entrada manual en el MVP |

**Descartadas en la exploración de esta fase** (por quedar bloqueadas o requerir pago desde este entorno, igual que ya ocurrió con el histórico cripto): Financial Modeling Prep (clave de pago obligatoria), stooq (bloquea con un reto JavaScript no resoluble sin navegador), CoinCap (bloqueada por política de red de este entorno).

## 2. Asignación de fuente por dominio (Fase 0 → dato concreto)

**Bloque B — acciones individuales (IBM, NVIDIA, ExxonMobil):**
- Fundamental & Quality Domain → SEC EDGAR (Revenue, Net Income, EPS, márgenes, deuda — todos con fecha de filing real, evitando el look-ahead bias que señalamos en el Paso 1 de la Fase 0).
- Market Behavior Domain (técnico) → Yahoo Finance (precio diario, para SMA/RSI/MACD/ATR).
- Valuation Domain → calculado internamente combinando precio (Yahoo) y fundamentales (SEC) — no se delega a un tercero, evita depender de la metodología de cálculo de otro proveedor.
- Risk Domain → volatilidad/drawdown/beta calculados sobre el histórico de precio de Yahoo, comparado contra `^GSPC` como referencia de mercado.

**Bloque A — fondos indexados de `CARTERA_A`:**
- Valor/rendimiento actual → app de MyInvestor (manual, como ya hiciste).
- Benchmark de referencia → el índice correspondiente vía Yahoo (`^GSPC` para el fondo S&P 500, etc.), para medir tracking aproximado.
- Categoría/coste/objetivo oficial → factsheet KIID del proveedor.

## 3. Plantilla de informe — dos variantes

La plantilla del Paso 18 (Fase 0) se divide en dos, porque un fondo diversificado y una acción individual no comparten las mismas secciones con sentido.

### Variante 1 — Acción individual (Bloque B)

```
ACTIVO
Ticker / Precio / Fecha / Capitalización / Sector

RESUMEN EJECUTIVO

FUNDAMENTALES (SEC EDGAR)          Score · Confidence · Data Quality
VALORACIÓN (calculado)             Score · Confidence · Data Quality
ANÁLISIS TÉCNICO (Yahoo Finance)   Score · Confidence · Data Quality
RIESGO (volatilidad/beta/drawdown) Score · Confidence · Data Quality

[MACRO, SENTIMIENTO, CATALIZADORES: no disponibles en el MVP — marcados como "DATOS INSUFICIENTES"]

BULL CASE / BASE CASE / BEAR CASE
FACTORES QUE INVALIDARÍAN LA TESIS
DATOS QUE FALTAN
NIVEL DE CONFIANZA DEL ANÁLISIS
```

### Variante 2 — Fondo/ETF (Bloque A)

```
FONDO
Nombre / Clase / ISIN si disponible / Plataforma / Fecha

RESUMEN EJECUTIVO

CATEGORÍA (RV/RF, geografía, cobertura de divisa)
COSTE (TER) frente a alternativas de la misma categoría
TRACKING frente a su índice de referencia (Yahoo, aproximado)
ENCAJE MACRO (¿favorece o perjudica el régimen macro actual a esta categoría?)
RIESGO (volatilidad de la categoría, no de una empresa)

BULL CASE / BASE CASE / BEAR CASE (de la categoría, no de un emisor)
DATOS QUE FALTAN
NIVEL DE CONFIANZA DEL ANÁLISIS
```

## 4. Pendiente explícito

Ambas plantillas dejan huecos marcados como "DATOS INSUFICIENTES" en Macro, Sentimiento y Catalizadores — así se diseñó a propósito en el Paso 6 de la Fase 0: el MVP demuestra el bucle completo con lo mínimo, no simula disciplinas que aún no existen.
