# CARTERA_A — Análisis retrospectivo de operaciones cripto

**Identificador de cartera pseudónimo:** `CARTERA_A` (titular real no identificado en este documento, conforme a `docs/00-protocolo-privacidad.md`).
**Plataformas:** Binance, Kraken.
**Operaciones analizadas:** 105 compras/ventas de cripto entre 2021-03 y 2025-11, reconstruidas a partir de los ledgers exportados, sin conservar User ID de Binance ni txid/refid de Kraken (ver `cartera/CARTERA_A_operaciones_cripto.csv`).

## Metodología y limitación de datos importante

Para dar contexto técnico a cada operación (¿se compró cerca de un máximo o de un mínimo relativo? ¿cómo evolucionó el precio después?) se han obtenido series de precio diario en EUR de dos fuentes públicas verificables:

- **CoinGecko** (API pública): últimos 365 días desde hoy.
- **Kraken** (API pública, OHLC diario): últimos ~720 días desde hoy.

Combinadas, estas fuentes cubren de forma **verificada y con cifras reales** el periodo aproximado **agosto 2024 → julio 2026**. Para operaciones anteriores a esa fecha (la mayor parte de 2021 y 2022), las fuentes públicas gratuitas accesibles desde este entorno no ofrecen histórico verificable, y **CoinGecko** limita explícitamente su API pública gratuita a 365 días de histórico, mientras que fuentes alternativas (Binance, CoinCap, Yahoo Finance, CryptoCompare) resultaron bloqueadas o exigen clave de pago desde este entorno.

Por tanto, este informe distingue explícitamente dos tipos de contenido, tal como exige el protocolo del proyecto (no inventar datos ausentes):

- 🟢 **DATO VERIFICADO**: precio real obtenido de API, con fecha de la fuente.
- 🟡 **CONTEXTO GENERAL DE MERCADO**: conocimiento general y ampliamente documentado sobre la evolución del mercado cripto en esas fechas (ciclos conocidos, eventos públicos notorios), **sin cifra de precio verificada**. No debe tratarse como un dato exacto.

---

## 1. XRP — el activo con más operaciones (41 movimientos), con datos verificados

Es el activo mejor cubierto por datos reales (34 de sus 41 operaciones caen dentro de la ventana verificada, desde nov-2024).

**Patrón detectado (🟢 verificado):**

- **Nov 2024 – ene 2025**: las ventas se ejecutaron sistemáticamente cerca de máximos locales de 90 días (percentil 87–100% del rango) — por ejemplo, venta del 2024-11-30 a ~1,84€ (percentil 100%), venta del 2025-01-16 a ~3,15€ (percentil 100%). Esto es un patrón de **buen timing relativo de salida**: no se vendió en pánico ni en mínimos.
- **Feb 2025 en adelante**: el patrón de compra cambia notablemente — la mayoría de las compras se ejecutan en el percentil **bajo** del rango de 90 días (0–36%): 2025-03-09 (percentil 0%), 2025-04-03 (percentil 1%), 2025-11-04 (percentil 0% en dos operaciones). Es decir, **se compró sistemáticamente en caídas relativas, no en euforia** — también es una señal de disciplina, no de comportamiento impulsivo.
- **Sin embargo**, el dato más relevante para la tesis global: **todas** las compras realizadas entre nov-2024 y nov-2025 muestran una variación negativa de entre **-44% y -69%** entre el precio de entrada y el precio más reciente disponible (jul-2026). Esto no es un problema de timing relativo (que fue razonablemente disciplinado), sino de **régimen de mercado**: XRP entró en una tendencia bajista sostenida y prolongada desde los niveles de esa ventana, y ninguna de las compras posteriores ha compensado esa caída de fondo hasta la fecha del dato más reciente.

**Conclusión sobre XRP:** el comportamiento táctico (comprar en mínimos relativos de 90 días, vender en máximos relativos) fue correcto y disciplinado. El problema no fue *cómo* se operó dentro de las tendencias, sino la ausencia de un criterio para diferenciar "está barato dentro de su rango reciente" de "está en una tendencia bajista de fondo que puede continuar" — exactamente la distinción que en la Fase 0 del sistema corresponde al **Market Behavior Domain** (tendencia de medio plazo) frente a un simple oscilador de rango.

---

## 2. ETH, BTC, SOL, ADA, ARB (2024–2025, con datos verificados parciales)

| Activo | Operación | Fecha | Precio (🟢) | Posición en rango 90d | Cambio hasta hoy |
|---|---|---|---|---|---|
| ETH | SELL | 2024-12-16 | 3.782€ | 99,7% (máximo local) | -56,0% |
| ETH | BUY | 2024-12-19 (x2) | 3.297€ | 70,5% | -49,6% |
| ETH | BUY | 2025-09-25 | 3.324€ | 62,4% | -50,0% |
| ETH | BUY | 2025-10-10 / 10-14 | 3.340–3.556€ | 52–55% | -50 a -53% |
| BTC | BUY | 2025-08-25 | 94.850€ | 41,2% | -39,6% |
| BTC | BUY | 2025-10-10 / 10-14 | 97.570–98.380€ | 36–42% | -41 a -42% |
| SOL | SELL | 2024-12-06 | 224,1€ | 83,0% (cerca de máximo) | -69,7% |
| ADA | SELL | 2024-11-30 (x2) | 1,019€ | 100% (máximo local) | -85,8% |
| ARB | BUY | 2024-12-19 | 0,7527€ | 47,0% (neutral) | -89,5% |

Mismo patrón que XRP: las decisiones tácticas dentro del rango de corto plazo no fueron descabelladas (ADA y ETH se vendieron cerca de máximos locales), pero **todas** las posiciones abiertas en este periodo muestran una caída de fondo muy significativa hasta el dato más reciente — ARB es el caso más extremo (-89,5%). Esto refuerza la misma conclusión: el sistema que estamos construyendo necesita, además del oscilador de rango de 90 días, una **lectura de régimen/tendencia de medio-largo plazo** (justo el Market Behavior Domain + Macro & Regime Domain de la Fase 0) para no comprar/mantener activos que técnicamente "parecen baratos" dentro de una caída estructural más amplia.

---

## 3. Periodo 2021–2022: sin datos verificados, solo contexto general 🟡

39 operaciones (SHIB, DOGE, TRX, XLM, DOT, EOS, y las primeras de ETH/ADA/XRP/SOL/ALGO) caen fuera de la ventana de datos verificable con las fuentes accesibles desde este entorno. Lo que sigue es **contexto general de mercado conocido públicamente**, no una serie de precios verificada — se marca explícitamente para no hacer pasar una estimación por un hecho:

- 🟡 Las compras de **DOGE** (15–22 abril 2021) coinciden con la fase de mayor especulación pública sobre esa moneda en 2021 (impulsada por menciones públicas repetidas y expectativa de una aparición en televisión estadounidense a inicios de mayo de 2021). Las ventas (1 y 8 de mayo de 2021) se ejecutaron muy cerca de las fechas en que, según es ampliamente conocido, el precio alcanzó de forma abrupta un máximo y después corrigió con fuerza — es decir, el *timing* narrativo de esas ventas concretas parece haber sido razonablemente bueno, aunque no podemos confirmarlo con una cifra exacta.
- 🟡 La compra de **SHIB** (12 de mayo de 2021) también se sitúa en ese mismo periodo de euforia por criptomonedas "meme". La venta (6 de octubre de 2021) se ejecutó *antes* de un repunte de precio de ese activo ampliamente documentado a finales de octubre de 2021 — es posible que la venta se realizara semanas antes del máximo, pero de nuevo, sin cifra verificada no se puede cuantificar cuánta revalorización se dejó sobre la mesa.
- 🟡 Las operaciones de **DOT, TRX, XLM, EOS** en marzo-mayo de 2021 y noviembre de 2021 fueron en su mayoría ciclos cortos de compra-venta (mismo día o pocos días), dentro de lo que se conoce como el primer gran ciclo alcista cripto de 2021, que alcanzó máximos generalizados a comienzos de noviembre de 2021 y fue seguido por un mercado bajista prolongado durante 2022 (incluyendo eventos públicos y muy documentados como el colapso de Terra/Luna en mayo de 2022 y de FTX en noviembre de 2022).
- 🟡 Las compras de ETH, ADA, XRP, SOL y ALGO en enero-febrero de 2022 se sitúan ya dentro de ese mercado bajista de 2022, que fue generalizado y prolongado durante todo el año.

**No se puede, con la información disponible en este entorno, decir con precisión si cada operación individual de este periodo fue una buena o mala decisión de timing.** Si se quiere análisis cuantitativo verificado también de este tramo, la vía sería aportar un histórico de precios propio (por ejemplo, exportado de TradingView o de un proveedor de pago), o repetir este análisis desde un entorno con acceso a una API de pago con histórico completo.

---

## 4. Síntesis de comportamiento observado (toda la muestra)

1. **La ejecución táctica de corto plazo (comprar relativamente barato, vender relativamente caro dentro de rangos de 90 días) es, en la parte verificada de los datos, consistentemente razonable.** No se observa el patrón clásico de comprar en la euforia de máximos históricos y vender en pánico en mínimos históricos.
2. **El punto débil identificado no es el timing táctico, sino la ausencia de un criterio de tendencia/régimen de fondo.** Comprar "barato dentro del rango reciente" un activo que está en una tendencia bajista estructural más amplia sigue produciendo pérdidas, como muestran de forma verificada XRP, ETH, BTC, SOL, ADA y ARB en el tramo 2024-2025.
3. **Alta fragmentación en muchas operaciones pequeñas sobre el mismo activo** (especialmente XRP, con compras/ventas repetidas de importes de 50-300€), lo que sugiere una operativa más cercana al trading de corto plazo que a la inversión de convicción — vale la pena que confirmes si esa es la intención real, porque cambia qué tipo de análisis (técnico de corto plazo vs. fundamental/tesis de largo plazo) es más relevante para este activo.
4. **Recomendación para el sistema que estamos construyendo:** cuando se active el Market Behavior Domain (Fase posterior), debería incorporar desde el principio, además de un oscilador de rango como el usado aquí, una métrica de tendencia de medio plazo (p. ej. posición del precio respecto a una media móvil de 100-200 días) — es precisamente la señal que, de haber estado disponible, habría diferenciado "barato en el rango reciente" de "barato dentro de una tendencia bajista de fondo" en los casos de ARB, ADA y SOL anteriores.

---

## Fuentes de datos utilizadas

- CoinGecko API pública (`/coins/{id}/market_chart`, `vs_currency=eur`, `days=365`), consultada 2026-07-20.
- Kraken API pública (`/0/public/OHLC`, `interval=1440`), consultada 2026-07-20.
- Para el periodo 2021-2022: conocimiento general documentado públicamente sobre ciclos de mercado cripto, sin verificación numérica — señalado explícitamente en cada punto.
