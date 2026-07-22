# Bot-Inversiones

Sistema de inteligencia financiera para apoyo a decisiones de inversión (no un chatbot de bolsa). Ver `docs/00-arquitectura-conceptual.md` para la arquitectura conceptual del proyecto (Fase 0) y las fases de desarrollo acordadas.

## Protocolo obligatorio de privacidad

**Antes de tratar cualquier dato del usuario (identidad, cartera, holdings, plataformas, credenciales), lee y aplica `docs/00-protocolo-privacidad.md` en su totalidad.** Es un requisito permanente para todo el trabajo en este proyecto, no solo una referencia opcional. En resumen:

- Pseudonimizar por defecto: usar `CARTERA_A`, `CUENTA_01`, etc. en vez de identidad real cuando sea posible.
- Nunca solicitar ni almacenar contraseñas, claves API, seed phrases, tokens o credenciales de ningún tipo.
- Separar siempre identidad, información financiera y credenciales.
- Minimizar: pedir solo el dato estrictamente necesario; usar rangos en vez de cifras exactas cuando baste.
- Antes de enviar cualquier dato del usuario a un servicio externo, evaluar necesidad y minimizar lo transmitido.

## Estado del proyecto

- Fase 0 (arquitectura conceptual): completada — `docs/00-arquitectura-conceptual.md`.
- Fase 1 (definición de MVP, holdings, watchlist, fuentes de datos): completada — ver `cartera/` (holdings pseudonimizados de `CARTERA_A` y watchlist) y `docs/01-fase1-fuentes-datos-y-plantilla.md` / `docs/02-fase1-gaps-y-roadmap-fuentes.md`. Pendiente para más adelante (no ahora): investigar plataformas alternativas a Binance/Kraken/MyInvestor.
- Fase 2 (Fundamental Engine): en curso. Orden acordado: cripto primero (motor de tokenomics/on-chain, `engine/crypto/`, ya con primera versión funcionando para BTC/ETH/ADA/SOL/DOT/XRP — ver `informes/2026-07-20_cripto_fundamentales_v1.md`), acciones (IBM/NVIDIA/ExxonMobil, motor SEC EDGAR + Yahoo Finance) después.
- Fase 3 (Motor Técnico): v1 funcionando para BTC/ETH/ADA/SOL/DOT/XRP — `engine/technical/`, ver `informes/2026-07-22_cripto_tecnico_v1.md`. Principio de diseño: confluencia de indicadores, nunca señales aisladas.
- Fase 5 (Motor Macro): v1 funcionando para EE.UU. y Eurozona (FRED) — `engine/macro/`, ver `informes/2026-07-22_macro_y_sintesis_v1.md`. Régimen: EE.UU. "expansión con inflación pegajosa", Eurozona "pivote hawkish reciente del BCE". Contextualiza (no reemplaza) los hallazgos de fundamentales y técnico.
- Fase 4 (Noticias/sentimiento): pendiente, siguiente motor a construir.
- Decisión de ejecución (aplica a toda fase de automatización futura, Fase 10): el sistema únicamente propone: el usuario ejecuta manualmente. Sin credenciales de trading en el sistema por ahora.
- Mapa de ruta visual del proyecto (artefacto publicado, redesplegar si se pide una versión actualizada): https://claude.ai/code/artifact/270c9640-d4f7-47d3-a090-240203a5dc23 (fuente: scratchpad de la sesión que lo creó, no versionada en el repo).
