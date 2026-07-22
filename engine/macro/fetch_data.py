"""Ingesta de datos para el motor macro (Fase 5).

Fuente: FRED (Federal Reserve Bank of St. Louis), endpoint publico de
descarga CSV (fredgraph.csv) -- no exige clave de API pese a que el
portal principal de FRED si la pide para su API REST formal. FRED
tambien agrega series internacionales (ej. inflacion de la Eurozona,
tipo de la facilidad de deposito del BCE), por eso basta una unica
fuente para EE.UU. y la Eurozona en esta v1.
"""
import csv
import io
import json
import os
import urllib.request

OUT_DIR = os.path.join(os.path.dirname(__file__), "_data")

SERIES = {
    "us_cpi": "CPIAUCSL",                 # indice CPI EE.UU. (para YoY)
    "us_fedfunds": "FEDFUNDS",             # tipo de referencia Fed
    "us_unemployment": "UNRATE",           # tasa de paro EE.UU.
    "us_10y": "DGS10",
    "us_2y": "DGS2",
    "us_10y2y_spread": "T10Y2Y",           # curva de tipos EE.UU.
    "ea_hicp": "CP0000EZ19M086NEST",       # indice HICP Eurozona (para YoY)
    "ea_ecb_rate": "ECBDFR",               # tipo facilidad de deposito BCE
}


def _get_csv(series_id):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "bot-inversiones-research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8")
    rows = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2 or not row[0] or not row[1] or row[1] in (".", "value", ""):
            continue
        try:
            rows.append([row[0], float(row[1])])
        except ValueError:
            continue
    return rows


def fetch_all():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, series_id in SERIES.items():
        rows = _get_csv(series_id)
        json.dump(rows, open(f"{OUT_DIR}/{name}.json", "w"))
        print(f"{name} ({series_id}): {len(rows)} puntos, último {rows[-1] if rows else None}")


if __name__ == "__main__":
    fetch_all()
