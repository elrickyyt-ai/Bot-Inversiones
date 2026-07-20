# Protocolo de Privacidad, Confidencialidad y Protección de Datos del Proyecto

## Naturaleza de este documento

Este documento **no es un contrato ni tiene valor legal vinculante frente a terceros**. Quien lo redacta y lo aplica es un asistente de IA (Claude, operado por Anthropic dentro de Claude Code), no una parte con capacidad jurídica para suscribir acuerdos. Ningún contenido de este documento modifica, sustituye ni tiene precedencia sobre:

- los Términos de Servicio y la Política de Privacidad de Anthropic,
- las prácticas reales de almacenamiento, retención o procesamiento de datos de la plataforma sobre la que se ejecuta esta sesión,
- ninguna obligación legal, fiscal o regulatoria aplicable al USUARIO.

Este documento es, en cambio, un **protocolo operativo interno del proyecto**: el conjunto de reglas que este asistente se compromete a seguir de forma consistente en todo el trabajo de diseño, análisis, código y documentación que genere para este proyecto, a partir de su adopción. Se guarda en el repositorio y se referencia desde `CLAUDE.md` para que cualquier sesión futura de Claude Code que trabaje en este proyecto lo cargue automáticamente como contexto y lo respete.

Si en algún momento se necesita que estas garantías tengan fuerza legal real (frente a un proveedor, un colaborador, o como política interna exigible), este texto puede servir de base, pero debe ser revisado y formalizado por un profesional del derecho.

**Fecha de adopción:** 2026-07-20
**Ámbito:** todo el trabajo realizado en el repositorio `Bot-Inversiones` y en las conversaciones asociadas a este proyecto.

---

## 1. Principio general de confidencialidad

Toda información proporcionada por el USUARIO durante este proyecto se trata como **confidencial, privada, de acceso restringido y no destinada a divulgación**. Esto incluye, entre otros: identidad, nombre y apellidos, documentos de identidad, direcciones, teléfonos, correos electrónicos, datos bancarios, datos financieros, patrimonio, ingresos, inversiones, posiciones financieras, carteras, transacciones, datos fiscales, situación tributaria, información empresarial o profesional, claves de API, tokens, contraseñas, credenciales, identificadores de cuentas, direcciones de wallets, datos de brokers, estrategias de inversión, algoritmos propios, código propietario, modelos cuantitativos, bases de datos y documentación privada.

Se aplica en todo momento el **principio de minimización de datos**: usar únicamente la información estrictamente necesaria para completar la tarea solicitada.

## 2. Limitación de uso

La información proporcionada se usa exclusivamente para responder a las solicitudes del USUARIO dentro de este proyecto. No se utiliza para: construir perfiles personales innecesarios, inferir identidad más allá de lo necesario, deducir información sensible no proporcionada expresamente, relacionar datos con información externa para identificar al USUARIO, enriquecer perfiles comerciales o publicitarios, ni divulgar información personal cuando no sea estrictamente necesario.

Cuando una tarea pueda realizarse sin la identidad real del USUARIO, se usan datos anonimizados o pseudonimizados.

## 3. Pseudonimización por defecto

Siempre que sea posible, la información identificativa se sustituye por referencias abstractas: `USUARIO`, `EMPRESA_A`, `CUENTA_01`, `CARTERA_A`, `[API_KEY]`, `[DIRECCIÓN OMITIDA]`, `[IDENTIFICADOR FISCAL OMITIDO]`. No se reproduce innecesariamente información sensible ya proporcionada.

## 4. Protección contra exposición accidental

Antes de generar cualquier respuesta con información personal, financiera, fiscal, jurídica o empresarial, se evalúa si es realmente necesaria:

- Si no es necesaria → **se omite**.
- Si es parcialmente necesaria → **se anonimiza**.
- Si es imprescindible → **se muestra solo el mínimo necesario**.

Nunca se incluyen deliberadamente credenciales, contraseñas, secretos, claves privadas o tokens completos en código, logs, ejemplos, documentación, mensajes de error, bases de datos de prueba, archivos de configuración, repositorios o prompts enviados a otros modelos. Se usan siempre variables de entorno, gestores de secretos o marcadores seguros.

## 5. Prohibición de exposición a terceros desde el flujo de trabajo

No se envía, copia, publica, transmite ni incorpora deliberadamente información confidencial del USUARIO a servicios externos, APIs externas, motores de búsqueda, bases de datos públicas, repositorios públicos, herramientas de terceros, sistemas de analítica ni herramientas de logging o debugging — salvo que el USUARIO solicite expresamente una acción que lo requiera, y siempre informándole antes de qué datos concretos son necesarios y por qué. Cuando una integración externa sea necesaria, se usa la mínima información posible, y nunca la identidad real cuando un identificador pseudónimo sea suficiente.

## 6. Protección específica para el sistema de inversiones

El sistema se diseña bajo **Privacy by Design**. Se tratan como especialmente sensibles: capital disponible, patrimonio, ingresos, cartera, posiciones, precios de entrada, órdenes, movimientos bancarios, información de brokers, historial financiero, declaraciones fiscales, estrategia de inversión personal, perfil de riesgo individual, y claves/credenciales de APIs financieras o brokers.

La arquitectura separa **datos de identidad** de **datos financieros**: siempre que sea técnicamente posible, ningún registro financiero contendrá directamente nombre, dirección, documento de identidad u otro identificador personal del USUARIO — se usan identificadores internos aleatorios.

## 7. Segregación de datos

Se mantienen separadas tres categorías: **IDENTIDAD** (lo estrictamente necesario para identificar al titular), **INFORMACIÓN FINANCIERA** (cartera, operaciones, análisis, estrategias, datos económicos) y **CREDENCIALES** (contraseñas, tokens, claves de API). Una vulneración de una categoría no debe permitir automáticamente acceder a las otras.

## 8. Seguridad de credenciales

Nunca se recomienda almacenar contraseñas en texto plano, claves de API directamente en código, secretos dentro de GitHub, tokens dentro de prompts, ni claves privadas sin protección adecuada. Se prioriza: gestores de secretos, variables de entorno, cifrado, control de acceso, principio de mínimo privilegio y rotación de credenciales. En cualquier ejemplo de código se usa `API_KEY = "[YOUR_API_KEY]"`, nunca una credencial real.

## 9. Información fiscal y jurídica

Ninguna inferencia sobre la situación fiscal, jurídica, tributaria, patrimonial o societaria del USUARIO se presenta como un hecho salvo que haya sido proporcionada expresamente. En escenarios legales o fiscales se diferencia siempre entre: hechos proporcionados, supuestos, interpretación, posibles consecuencias e información que requiere verificación profesional. No se realizan afirmaciones categóricas sobre obligaciones legales o fiscales sin identificar circunstancias y jurisdicción aplicables.

## 10. Prevención de registros engañosos

No se redacta ningún documento que presente como ocurrido un hecho que no lo sea, ni se atribuyen al USUARIO operaciones, ingresos, gastos, declaraciones, contratos o decisiones inexistentes. Los ejemplos o simulaciones se identifican siempre como `SIMULACIÓN`, `EJEMPLO` o `ESCENARIO HIPOTÉTICO`.

## 11. Datos de terceros

La información privada de terceros recibe el mismo nivel de protección: no se divulgan innecesariamente nombres, teléfonos, correos, documentos, información financiera o conversaciones privadas de terceros. Se usan pseudónimos cuando sea posible.

## 12. Derecho a la minimización

Antes de solicitar información sensible se evalúa si es realmente necesaria para la tarea. Si no lo es, no se solicita. Si basta una aproximación, se solicita un rango (p. ej., "¿en qué rango aproximado está el capital destinado a inversión?" en vez del importe exacto de una cuenta bancaria).

## 13. Datos especialmente sensibles que nunca se solicitan ni deben incorporarse

Contraseñas, claves privadas, frases semilla (*seed phrases*), códigos de recuperación, códigos 2FA, PIN, CVV, claves bancarias y copias completas de documentos de identidad cuando no sean necesarias. **Nunca se solicita la seed phrase o clave privada de una wallet.** Si el USUARIO intenta proporcionar información no necesaria para la tarea, se le advierte antes de incorporarla.

## 14. Servicios y APIs externas

Antes de recomendar que datos personales o financieros se transmitan a una API, servicio cloud o proveedor externo, se analiza: qué información recibe, para qué la necesita, cuánto tiempo puede conservarla, si puede usarse para entrenamiento, dónde se almacena, qué terceros pueden intervenir, qué controles de privacidad ofrece, y si existe una alternativa que requiera menos datos. Se aplica siempre minimización de datos.

## 15. Logging y telemetría

Los sistemas de logging que se diseñen deben excluir o enmascarar credenciales, claves, datos bancarios, documentos identificativos e información financiera personal innecesaria, con filtros automáticos de redacción cuando sea posible.

## 16. Retención de datos del sistema

Ningún dato se almacena indefinidamente por defecto. Para cada categoría de datos del sistema se define: finalidad, ubicación, acceso, retención, eliminación y backup. Antes de diseñar una base de datos que almacene información personal, se justifica por qué esa información necesita almacenarse.

## 17. Acceso y permisos

Todo el sistema se diseña bajo el principio de **mínimo privilegio**: cada componente accede únicamente a la información estrictamente necesaria para su función (p. ej., el motor de noticias no necesita credenciales bancarias; el motor técnico no necesita conocer la identidad del USUARIO; el motor de análisis con LLM no debe recibir claves privadas).

## 18. Prohibición de perfilado innecesario

No se construyen perfiles adicionales sobre el USUARIO que no sean necesarios para las funciones solicitadas. Se evita especialmente inferir innecesariamente: patrimonio total, identidad política, información médica, relaciones personales, localización precisa o hábitos privados.

## 19. Control sobre las respuestas

Ante cualquier respuesta que pueda exponer información sensible, se sigue este orden de prioridad: (1) omitir, (2) anonimizar, (3) generalizar, (4) usar rangos, (5) mostrar el dato exacto solo cuando sea estrictamente necesario.

## 20. Límites de este protocolo

Este protocolo regula cómo se trata la información **dentro de las respuestas, análisis, código y arquitectura generados para este proyecto**. No modifica las políticas del proveedor de la plataforma, sus términos contractuales, sus sistemas internos de almacenamiento, sus obligaciones legales ni sus prácticas de retención o seguridad. Cuando una garantía de privacidad dependa de la plataforma, configuración de cuenta, contrato o proveedor externo utilizado, se indicará expresamente. No se debe transmitir al USUARIO una falsa sensación de confidencialidad o protección legal.

## 21. Alerta de privacidad

Si en el curso del proyecto el USUARIO está a punto de incorporar información que pueda generar un riesgo significativo de robo de identidad, fraude, acceso financiero indebido, exposición fiscal o jurídica, pérdida patrimonial o vulneración de secretos, se le advertirá claramente y se propondrá una forma alternativa de alcanzar el mismo objetivo minimizando la información expuesta.

## 22. Principio final

Para toda decisión de arquitectura, programación y tratamiento de información de este proyecto:

**Recopilar menos. Almacenar menos. Compartir menos. Dar menos acceso. Conservar menos tiempo. Anonimizar siempre que sea posible. Nunca sacrificar privacidad sin una necesidad técnica justificada.**

---

## Aplicación práctica inmediata a este proyecto

A partir de la adopción de este protocolo:

- Los **holdings reales** (acciones, ETFs, índices, criptomonedas) que el USUARIO aporte se almacenarán bajo un **identificador pseudónimo de cartera** (p. ej. `CARTERA_A`), nunca junto al nombre real, correo o cualquier dato identificativo del USUARIO.
- **Nunca se solicitarán ni almacenarán** contraseñas, claves API, seed phrases, tokens de acceso a brokers/exchanges o credenciales de ningún tipo. Cuando el sistema necesite conectarse a una API real (fase posterior), se documentará el uso de variables de entorno o gestor de secretos, nunca credenciales en el repositorio.
- El **nombre de la plataforma/bróker/exchange** usado por posición se trata como dato financiero operativo (necesario para el análisis de riesgo de concentración de contraparte), no como dato identificativo — se mantiene separado de cualquier dato de identidad personal.
- Cuando se investiguen plataformas alternativas (Tarea pendiente de este proyecto), esa investigación se hará sobre las categorías/plataformas mencionadas, sin transmitir a servicios externos ni cifras de cartera ni identidad del USUARIO.
