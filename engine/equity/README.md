# Equity Fundamentals Engine (v1)

Fase 2, Bloque B — el motor de acciones que había quedado pendiente. Cubre IBM, NVIDIA (NVDA) y ExxonMobil (XOM), las tres acciones de prueba del watchlist original (Fase 1).

## Diferencia importante con los demás motores del proyecto

Los otros motores (`engine/crypto`, `engine/technical`, `engine/macro`) tienen un `fetch_data.py` ejecutable de forma independiente porque llaman a APIs públicas sin autenticación. Este motor usa el **conector MCP de Alpha Vantage** conectado a la cuenta del usuario en esta sesión de Claude — no expone una clave de API que un script externo pueda usar, y **no se guarda ninguna clave en el repositorio** (protocolo de privacidad: nunca almacenar credenciales).

En la práctica, esto significa que la descarga de datos es un paso manual dentro de la sesión (llamadas a `GLOBAL_QUOTE`, `COMPANY_OVERVIEW`, `EARNINGS` por cada ticker), y `score.py` calcula sobre lo que ya esté guardado en `_data/` (no versionado, igual que los demás).

## Uso

```
python3 engine/equity/score.py
```

## Gestión de cuota (Alpha Vantage gratuito: 25 llamadas/día, ~1/seg)

9 llamadas para 3 tickers (quote + overview + earnings cada uno) agotan más de un tercio de la cuota diaria gratuita. Lanzarlas en paralelo dispara el límite de ráfaga — hay que espaciarlas. Si se amplía el watchlist de acciones más adelante, vale la pena revisar si el plan de pago compensa.

## Metodología

Igual disciplina que el resto: valores puntuales (P/E, márgenes, ROE, crecimiento) se reportan como referencia, no como percentil inventado — Alpha Vantage no da una serie histórica de fundamentales en el plan usado. La única métrica con posición relativa real es el **rango de 52 semanas** (dato directo de Alpha Vantage). La confluencia técnica combina precio vs. SMA50/SMA200 y si el último resultado trimestral batió o falló el consenso — mismo principio de "nunca una señal aislada" que `engine/technical`.

## Explícitamente fuera de v1

- Sin balance/cash flow detallado (Debt/Equity, Net Debt/EBITDA, FCF) — quedan para una siguiente iteración si Alpha Vantage los da sin consumir demasiada cuota.
- Sin comparativa sectorial entre las tres (sectores demasiado distintos: tecnología/servicios, semiconductores, energía — comparar sus múltiplos directamente sería engañoso sin normalizar por sector).
