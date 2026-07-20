# Cartera — datos financieros pseudonimizados

Esta carpeta contiene los datos de holdings reales usados como semilla de la Fase 1 del proyecto, tratados conforme a `docs/00-protocolo-privacidad.md`.

- **Identificador de cartera:** `CARTERA_A`. No se guarda en ningún archivo de esta carpeta el nombre, correo ni ningún otro identificador personal del titular.
- **Titularidad:** los datos de las cuentas de Binance y Kraken pertenecen a un tercero que ha dado su consentimiento para que se traten en este sistema como si el usuario del proyecto fuera el titular.
- **Minimización aplicada:** los ficheros originales exportados (User ID de Binance, txid/refid de Kraken, historial operación por operación con comisiones) **no se han conservado**. Solo se guarda el resultado ya limpio: fecha, operación, activo, cantidad, contravalor y plataforma.

## Archivos

| Archivo | Contenido |
|---|---|
| `CARTERA_A_operaciones_cripto.csv` | 105 operaciones de compra/venta cripto reconstruidas, sin identificadores de cuenta ni de transacción. |
| `CARTERA_A_eventos_no_trade_cripto.csv` | Depósitos, retiradas, conversiones fiat↔stablecoin, airdrops y migraciones de token (p. ej. EOS→A/Vaulta). |
| `CARTERA_A_posicion_neta_cripto.csv` | Resumen de la posición actual estimada por activo. |
| `CARTERA_A_fondos_indexados.csv` | Holdings de fondos indexados en MyInvestor (valor actual, ganancia y coste estimado). |
| `CARTERA_A_analisis_retrospectivo_cripto.md` | Informe de comportamiento: para cada operación cripto con datos de precio verificables, contexto técnico (posición dentro del rango de 90 días, evolución posterior); para el periodo 2021-2022, contexto general de mercado explícitamente marcado como no verificado. |

## Nunca en esta carpeta

Conforme al protocolo de privacidad del proyecto: contraseñas, claves API, seed phrases, códigos 2FA, ni ningún identificador de cuenta de las plataformas.
