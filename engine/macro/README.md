# Macro Engine (v1)

Motor de régimen macro — Fase 5, dominio **transversal** de la Fase 0: no compite con los demás motores, los contextualiza (no todos los activos reaccionan igual al mismo entorno macro).

## Uso

```
python3 engine/macro/fetch_data.py   # descarga a engine/macro/_data/ (no versionado)
python3 engine/macro/score.py        # clasifica régimen EE.UU. y Eurozona, imprime JSON
```

## Fuente de datos

FRED (Banco de la Reserva Federal de St. Louis), endpoint público de descarga CSV (`fredgraph.csv`) — **sin clave de API**, pese a que el API REST formal de FRED sí la exige. FRED agrega también series internacionales (inflación de la Eurozona, tipo del BCE), así que una sola fuente cubre ambas regiones en esta v1.

## Metodología

Igual que el motor técnico: **confluencia de señales, nunca un indicador aislado**, con la regla exacta documentada en el código (no es una caja negra):

- **EE.UU.**: inflación (CPI interanual) vs. objetivo del 2%, dirección de los tipos de la Fed, tendencia del desempleo, y si la curva 10 años-2 años está invertida (señal clásica de recesión). Con las cuatro señales se clasifica el régimen.
- **Eurozona**: inflación (HICP interanual) y dirección del tipo de depósito del BCE comparando ahora vs. hace 3 meses vs. hace 12 meses, para detectar pivotes de política monetaria.

## Gap explícito de esta v1

Sin serie de desempleo ni de curva de tipos de la Eurozona actualizada y gratuita — por eso el régimen de la Eurozona tiene menor confidence (60%) que el de EE.UU. (100%, las 4 señales tienen dato).

## Nota importante sobre esta v1 en general

Un hallazgo interesante de construir este motor: en la sesión anterior de este mismo proyecto se citó (vía búsqueda web) que "el CPI aumentó 4,2% interanual en mayo de 2026, el mayor incremento desde 2023" — al verificarlo ahora contra la fuente primaria (FRED, serie oficial de EE.UU.), el dato real de EE.UU. es **3,46% interanual en junio de 2026**, no 4,2%. Lo más probable es que aquella cifra se refiriera a otro país o índice, no a EE.UU. — se corrige aquí explícitamente en vez de dejar la discrepancia sin resolver, tal como exige el protocolo del proyecto (verificar contra fuente primaria antes de dar un dato por bueno).
