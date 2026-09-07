"""Observaciones de base para materialidad -- P6.1 (2026-09-07).

ESTO NO ES UN FICHERO DE DECLARACION, a diferencia de `cadencias.py`,
`catalogo.py` y `requisitos_magnitud.py`. Aqui no hay reglas: hay
OBSERVACIONES fechadas, con fuente citable y periodo. Una observacion no
es una declaracion, y la diferencia importa.

POR QUE ESTAN AQUI Y NO EN EL CONTRATO
--------------------------------------
El diseno de P6.1 concluyo que estas filas son de UNA entidad y por
tanto caben en el contrato sin tocar METRIC_FIELDS. Al ir a escribirlas
aparecio el limite real, medido:

    storage.asset_type_of("TSM") -> None
    data/assets/ -> ADA BTC DOT EA ETH IBM NVDA SOL US XOM XRP

El contrato guarda observaciones sobre ACTIVOS, y TSMC es una ENTIDAD que
no es un activo de esta watchlist. Meterla exigiria inventar un activo
TSM sin serie de precios, sin dominio y sin cadencia, solo para colgar
una fila: ensuciaria DimAsset, cobertura y frescura a cambio de nada.

Es la misma familia de hueco que `capacity_utilization(tech:cowos)`: el
sistema sabe observar activos, y todavia no entidades que no coticen en
su watchlist. DEUDA REGISTRADA, no disimulada -- cuando el contrato
admita observaciones de entidad (o TSMC entre como activo), estas filas
se mueven y este fichero desaparece.

Lo que NO se hizo: guardarlas en knowledge/ (una observacion fechada no
es una relacion estructural) ni inventar el activo.
"""

# Cada fila es literal del documento citado. `periodo` es el ejercicio
# que cubre la cifra, no la fecha de publicacion: la cota se aplica al
# periodo observado, y de ahi sale la comprobacion de vigencia.
OBSERVACIONES = [
    {
        "observation_id": "obs:tsmc:largest_customer:2025",
        "basis": "SUPPLIER_REVENUE_EXPOSURE",
        "subject": "org:tsmc",
        "metric": "largest_customer_revenue_share",
        "upper_bound": 19.0,
        "unit": "%",
        "periodo": ("2025-01-01", "2025-12-31"),
        "source_id": "src:tsmc-20f-fy2025",
        "literal": "Our largest customer in 2023, 2024 and 2025 accounted for 25%, 22% "
                   "and 19% of our net revenue in the respective year.",
    },
    {
        "observation_id": "obs:tsmc:largest_customer:2024",
        "basis": "SUPPLIER_REVENUE_EXPOSURE",
        "subject": "org:tsmc",
        "metric": "largest_customer_revenue_share",
        "upper_bound": 22.0,
        "unit": "%",
        "periodo": ("2024-01-01", "2024-12-31"),
        "source_id": "src:tsmc-20f-fy2025",
        "literal": "(misma frase, ejercicio 2024)",
    },
    {
        "observation_id": "obs:tsmc:largest_customer:2023",
        "basis": "SUPPLIER_REVENUE_EXPOSURE",
        "subject": "org:tsmc",
        "metric": "largest_customer_revenue_share",
        "upper_bound": 25.0,
        "unit": "%",
        "periodo": ("2023-01-01", "2023-12-31"),
        "source_id": "src:tsmc-20f-fy2025",
        "literal": "(misma frase, ejercicio 2023)",
    },
]


def de(basis, subject):
    """Observaciones de esa base sobre ese sujeto. Sin ordenar por fecha
    ni por valor: elegir la ultima o la mayor seria decidir antes de
    comprobar si son aplicables, que es justo lo que P6.1 no hace."""
    return [o for o in OBSERVACIONES if o["basis"] == basis and o["subject"] == subject]
