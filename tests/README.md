# Pruebas de humo

Ejecutar antes de tocar un motor existente, y después de añadir uno nuevo:

```
python3 -m unittest discover -s tests -v
```

## Qué comprueban

Que cada motor (`engine/crypto`, `engine/technical`, `engine/macro`, `engine/scoring`) produce, sobre una muestra pequeña de datos reales ya congelados en `fixtures/` (BTC y XRP), una salida con la forma esperada y valores dentro de rango matemáticamente válido (RSI en [0,100], percentiles en [0,100], etc.). No validan si el análisis financiero es "correcto" — eso lo revisamos leyendo los informes — validan que el código no se ha roto.

## Por qué con datos congelados y no en vivo

Para que las pruebas sean rápidas, reproducibles, y no dependan de que CoinGecko/Kraken/FRED estén disponibles ni respeten límites de tasa en el momento de ejecutarlas — el mismo tipo de límite que ya nos bloqueó hoy con GDELT.

## Cuándo actualizar las fixtures

Solo si cambia la forma de los datos que devuelve una fuente (por ejemplo, si CoinGecko añade o quita un campo del endpoint de detalle). No hace falta refrescarlas por el mero paso del tiempo — el objetivo es detectar roturas de código, no tener el precio del día.
