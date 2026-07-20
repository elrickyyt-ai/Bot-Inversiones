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
- Fase 1 (definición de MVP, holdings, watchlist): en curso.
