# Bot-Inversiones

Sistema de inteligencia financiera para apoyo a decisiones de inversión (no un chatbot de bolsa). Ver `docs/00-arquitectura-conceptual.md` para la arquitectura conceptual del proyecto (Fase 0) y las fases de desarrollo acordadas.

## Punto de entrada obligatorio

**Antes de trabajar en nada, lee `contexto/ESTADO_VIGENTE.md`.** Es la superficie de
estado vigente: qué es cierto hoy, dónde vive cada verdad, qué decisiones están
activas, qué invariantes no pueden violarse y cómo llegar al registro histórico.
Es pequeña y está sometida a un presupuesto verificado en CI.

**Referencia y valida; nunca duplica como verdad.** Si un dato tiene fuente canónica
en el código, la superficie apunta a ella y el validador detecta cualquier
divergencia: `python3 contexto/validar.py`.

El registro histórico —`docs/ESTADO.md`, `docs/DECISIONES.md`, `informes/` y el
estado de este fichero previo a F1— no se carga de entrada: se recupera bajo
demanda desde los punteros de la superficie. Su integridad se comprueba con
`python3 contexto/integridad.py` y `python3 contexto/extraccion.py`.

## Protocolo obligatorio de privacidad

**Antes de tratar cualquier dato del usuario (identidad, cartera, holdings, plataformas, credenciales), lee y aplica `docs/00-protocolo-privacidad.md` en su totalidad.** Es un requisito permanente para todo el trabajo en este proyecto, no solo una referencia opcional. En resumen:

- Pseudonimizar por defecto: usar `CARTERA_A`, `CUENTA_01`, etc. en vez de identidad real cuando sea posible.
- Nunca solicitar ni almacenar contraseñas, claves API, seed phrases, tokens o credenciales de ningún tipo.
- Separar siempre identidad, información financiera y credenciales.
- Minimizar: pedir solo el dato estrictamente necesario; usar rangos en vez de cifras exactas cuando baste.
- Antes de enviar cualquier dato del usuario a un servicio externo, evaluar necesidad y minimizar lo transmitido.

