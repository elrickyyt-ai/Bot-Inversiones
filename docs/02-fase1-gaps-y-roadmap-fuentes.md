# Fase 1 — Qué falta si se consiguen mejores fuentes de datos

Cierre de la Fase 1: para cada hueco de datos identificado, qué pasos concretos se activarían si en el futuro se resuelve el acceso a la fuente. No es trabajo pendiente del MVP — es la referencia para cuando decidas invertir en una fuente mejor.

## 1. Histórico cripto 2021-2023 (retrospectiva de `CARTERA_A`)

**Hueco:** sin datos de precio verificados antes de ago-2024 (ver `cartera/CARTERA_A_analisis_retrospectivo_cripto.md`, secciones marcadas 🟡).

**Si se consigue una fuente** (API de pago tipo CryptoCompare/Kaiko/Nomics, o un CSV que tú mismo exportes de un sitio al que tengas acceso):
1. Guardar el histórico bajo la misma disciplina de minimización ya aplicada (sin claves ni identificadores en el repo).
2. Volver a ejecutar el mismo script de análisis ya construido (`analyze.py`, en el scratchpad de esta sesión) apuntando a la nueva fuente — no hace falta rehacer nada, solo sustituir el origen de precios.
3. Sustituir en el informe las secciones 🟡 (contexto general) por 🟢 (dato verificado) con las cifras reales.

## 2. NAV/TER/tracking de los 9 fondos de MyInvestor (Bloque A)

**Hueco:** sin API pública — entrada manual vía pantallazo.

**Si se consigue una fuente** (API de un agregador tipo Morningstar/Kepler, o scraping autorizado del factsheet KIID del proveedor):
1. Construir un conector ligero que traiga NAV diario + TER + índice de referencia oficial por fondo.
2. Automatizar lo que hoy es manual: el `Data Quality Score` de esos 9 fondos subiría (hoy es más bajo precisamente por depender de una captura manual puntual).
3. Calcular tracking difference real frente al índice (hoy solo se aproxima comparando contra `^GSPC` vía Yahoo).

## 3. Fundamentales de empresas no estadounidenses

**Hueco:** SEC EDGAR solo cubre emisores que reportan a la SEC — válido para IBM/NVIDIA/ExxonMobil, no serviría si en el futuro añades una acción europea o asiática.

**Si se consigue una fuente** (API de pago tipo Refinitiv/FactSet, o acceso a los reguladores locales — Companies House en Reino Unido, ESMA/CNMV en la UE):
1. Extender la capa de Data Acquisition para que el conector de fundamentales dependa del país del emisor, no de una única fuente fija.
2. Ampliar el Instrument Master Data para guardar la jurisdicción reguladora de cada activo.

## 4. Datos intradía / tiempo real

**Hueco:** todas las fuentes actuales (Yahoo, SEC, CoinGecko/Kraken) dan datos diarios o retrasados — suficiente para el MVP (análisis de medio plazo), no para trading de corto plazo.

**Si en el futuro hace falta** (cuando el horizonte de la tesis lo justifique, no antes): evaluar una fuente de pago específica en ese momento — no se recomienda adelantarlo ahora, ver Paso 5 de la Fase 0 (exclusiones deliberadas).

---

## Mensaje para pedir consejo a terceros sobre fuentes de datos

Texto listo para preguntar en un foro, a un colega o en una comunidad, sin ningún dato personal ni de cartera — solo la necesidad técnica:

> Estoy montando un proyecto personal de análisis de inversiones (Python, presupuesto ajustado). Ya tengo resuelto con fuentes gratuitas: fundamentales de empresas USA vía SEC EDGAR (API oficial) y precio histórico de acciones/índices vía Yahoo Finance. Me faltan dos cosas:
> 1. Una forma barata (o gratuita) de conseguir histórico de precio diario de criptomonedas de varios años (no solo BTC/ETH, también altcoins de menor capitalización), ya que las APIs públicas gratuitas que he probado (CoinGecko, Kraken) solo dan entre 1 y 2 años de histórico en su plan gratuito.
> 2. Una forma de conseguir NAV, TER y el índice de referencia oficial de fondos indexados UCITS europeos (tipo Fidelity/Vanguard/iShares "Acc" share classes) sin ticker de bolsa — no encuentro una API gratuita para esto, solo el factsheet en PDF del proveedor.
>
> ¿Alguna fuente gratuita o de bajo coste que recomendéis para estos dos casos?

Puedes usarlo tal cual — no contiene ninguna referencia a tu cartera, activos concretos ni identidad.
