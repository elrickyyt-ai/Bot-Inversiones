# Crypto Fundamentals Engine (v1)

Motor de "fundamentales" para criptomonedas — deliberadamente **distinto** del Fundamental Engine de acciones (`docs/01-fase1-fuentes-datos-y-plantilla.md`), porque no existe un equivalente cripto de Revenue/EPS/EBITDA. En su lugar usa **tokenomics** y **actividad on-chain/desarrollo**.

## Uso

```
python3 engine/crypto/fetch_data.py   # descarga a engine/crypto/_data/ (no versionado, ver .gitignore)
python3 engine/crypto/score.py        # calcula métricas y las imprime en JSON
```

## Métricas v1 y de dónde salen

| Métrica | Fuente | Con serie histórica real (percentil) |
|---|---|---|
| % de supply circulante sobre el máximo/total | CoinGecko (snapshot) | No — valor puntual |
| FDV / Market Cap (dilución pendiente) | CoinGecko (snapshot) | No — valor puntual |
| Market Cap, percentil 365d | CoinGecko (`market_chart`, histórico real) | Sí |
| TVL, percentil 365d (solo ETH/SOL/ADA/DOT) | DefiLlama (histórico real) | Sí |
| Actividad de desarrollo (commits 4 semanas, stars, forks) | CoinGecko (snapshot) | No — valor puntual |

**Por qué BTC y XRP no tienen TVL:** no son plataformas de contratos inteligentes con un ecosistema DeFi nativo comparable — forzar un TVL ahí sería inventar una métrica que no aplica, así que se marca explícitamente como no aplicable en vez de mostrar un cero engañoso.

**`posible_incidencia_datos`:** cuando CoinGecko/DefiLlama devuelven actividad de desarrollo o TVL en cero de forma sospechosa (visto en DOT en la primera ejecución — probablemente un mapeo incorrecto del repositorio de GitHub o de la chain en la fuente, no que Polkadot no tenga desarrollo real), el motor lo señala y reduce el Data Quality en vez de presentarlo como un hecho.

## Explícitamente fuera de v1 (gap, no fantaseado)

- Direcciones activas / nº de transacciones on-chain.
- Ratio de staking (% de supply en staking) — relevante para ETH, ADA, SOL, DOT.
- Concentración de holders (distribución de la oferta).

Si se encuentra una fuente gratuita fiable para alguna de estas, se añade como columna nueva sin rehacer el resto del motor.

## Metodología de scoring

Percentil dentro del histórico propio del activo (no hay todavía universo de peers cripto — ver `docs/02-fase1-gaps-y-roadmap-fuentes.md`). Data Quality con techo de 80% por fuente única, reducido a 45% cuando se detecta una posible incidencia de datos.
