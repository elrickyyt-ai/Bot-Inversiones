"""Nivel CORE de la capa de almacenamiento -- SOLO biblioteca estandar.

Estas pruebas corren en el cron diario, donde PyArrow no esta instalado.
Cubren la resolucion por clave logica (un upsert, no una concatenacion),
la precedencia por retrieved_at (no por la capa fisica donde vive la fila),
el ida y vuelta del CSV de incoming/ y el desdoble value/value_text.

Las que necesitan abrir parquet estan en test_storage_parquet.py.
"""
import datetime
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine", "contract"))
import storage  # noqa: E402

UTC = datetime.timezone.utc


def fila(metric="precio", value=100.0, dia="2024-03-01", ts="2024-03-01T06:00:00Z",
         asset_id="TEST", source="Fuente", domain="tecnico", value_text=None):
    return {
        "asset_id": asset_id, "asset_type": "equity", "domain": domain,
        "metric": metric, "value": value, "value_text": value_text,
        "unit": "USD", "data_as_of": datetime.date.fromisoformat(dia),
        "retrieved_at": datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC),
        "source": source, "source_priority": 2, "confidence_pct": None,
        "data_quality_pct": None, "calculation_method": "test", "source_url": None,
    }


class TestResolucion(unittest.TestCase):
    def test_correccion_no_anade_fila(self):
        """3 correcciones de claves existentes -> el recuento NO sube."""
        base = [fila(metric=f"m{i}", value=float(i)) for i in range(100)]
        correcciones = [fila(metric=f"m{i}", value=999.0, ts="2024-06-01T06:00:00Z")
                        for i in range(3)]
        out = storage.resolve(base + correcciones)
        self.assertEqual(len(out), 100)
        corregidas = [r for r in out if r["value"] == 999.0]
        self.assertEqual(len(corregidas), 3)

    def test_prueba_sintetica_del_plan(self):
        """3 correcciones + 1 alta -> current sube EXACTAMENTE 1 fila.

        Es la comprobacion que el plan de migracion exige de forma explicita:
        obliga a distinguir filas fisicas de estado logico reconstruido.
        """
        base = [fila(metric=f"m{i}", value=float(i)) for i in range(100)]
        r2 = [fila(metric=f"m{i}", value=999.0, ts="2024-06-01T06:00:00Z")
              for i in range(3)]
        r2.append(fila(metric="m_nueva", value=42.0, ts="2024-06-01T06:00:00Z"))

        self.assertEqual(len(base) + len(r2), 104)   # filas fisicas
        self.assertEqual(len(storage.resolve(base + r2)), 101)  # estado logico

    def test_precedencia_por_retrieved_at_no_por_capa(self):
        """El caso que corrigio el plan: una fila 'late' con retrieved_at
        ANTERIOR no puede ganar a una de incoming con retrieved_at posterior."""
        incoming_1 = fila(value=100.0, ts="2026-09-01T06:00:00Z")
        incoming_2 = fila(value=110.0, ts="2026-09-05T06:00:00Z")
        late = fila(value=95.0, ts="2026-09-03T06:00:00Z")

        # el orden en que llegan no debe influir en el resultado
        for orden in ([incoming_1, incoming_2, late], [late, incoming_2, incoming_1],
                      [incoming_2, late, incoming_1]):
            out = storage.resolve(orden)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["value"], 110.0,
                             "debe ganar el retrieved_at mas alto, no la ultima capa")

    def test_late_si_gana_cuando_es_realmente_posterior(self):
        out = storage.resolve([fila(value=110.0, ts="2026-09-05T06:00:00Z"),
                               fila(value=95.0, ts="2026-09-07T06:00:00Z")])
        self.assertEqual(out[0]["value"], 95.0)

    def test_orden_canonico_estable(self):
        filas = [fila(metric="z"), fila(metric="a"), fila(metric="m")]
        self.assertEqual([r["metric"] for r in storage.resolve(filas)], ["a", "m", "z"])


class TestClaveLogica(unittest.TestCase):
    def test_misma_clave_distinta_fuente_son_hechos_distintos(self):
        out = storage.resolve([fila(source="Kraken"), fila(source="Coinbase")])
        self.assertEqual(len(out), 2)

    def test_clave_incluye_los_cinco_campos(self):
        k = storage.logical_key(fila())
        self.assertEqual(k, ("TEST", "tecnico", "precio", "2024-03-01", "Fuente"))


class TestCSV(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_roundtrip_conserva_tipos_y_nulos(self):
        p = os.path.join(self.tmp, "T_2026.csv")
        original = [fila(value=1.5), fila(metric="cat", value=None, value_text="alcista")]
        storage.append_incoming(p, original)
        leidas = storage.read_incoming(p)
        self.assertEqual(len(leidas), 2)
        for o, l in zip(storage.canonical_sort(original), leidas):
            self.assertEqual(o["value"], l["value"])
            self.assertEqual(o["value_text"], l["value_text"])
            self.assertEqual(o["data_as_of"], l["data_as_of"])
            self.assertEqual(o["retrieved_at"], l["retrieved_at"])
            self.assertIsNone(l["confidence_pct"])

    def test_append_no_reescribe_lo_anterior(self):
        p = os.path.join(self.tmp, "T_2026.csv")
        storage.append_incoming(p, [fila(metric="a")])
        with open(p, encoding="utf-8") as f:
            antes = f.read()
        storage.append_incoming(p, [fila(metric="b")])
        with open(p, encoding="utf-8") as f:
            despues = f.read()
        self.assertTrue(despues.startswith(antes),
                        "el append debe conservar intacto el contenido previo")
        self.assertEqual(len(storage.read_incoming(p)), 2)

    def test_sin_fichero_devuelve_vacio(self):
        self.assertEqual(storage.read_incoming(os.path.join(self.tmp, "no.csv")), [])


class TestConversionDesdeJSON(unittest.TestCase):
    def test_desdobla_value_categorico(self):
        r = storage.from_json_row({
            "asset_id": "BTC", "asset_type": "crypto", "domain": "tecnico",
            "metric": "confluencia_sesgo", "value": "confluencia alcista",
            "unit": "categorico", "data_as_of": "2026-09-04",
            "retrieved_at": "2026-09-04T11:17:40Z", "source": "Kraken",
            "source_priority": 2, "confidence_pct": 75, "data_quality_pct": None,
            "calculation_method": "x", "source_url": None})
        self.assertIsNone(r["value"])
        self.assertEqual(r["value_text"], "confluencia alcista")

    def test_numerico_no_toca_value_text(self):
        r = storage.from_json_row({
            "asset_id": "BTC", "asset_type": "crypto", "domain": "tecnico",
            "metric": "precio", "value": 66402.3, "unit": "EUR",
            "data_as_of": "2026-09-04", "retrieved_at": "2026-09-04T11:17:40Z",
            "source": "Kraken", "source_priority": 2, "confidence_pct": None,
            "data_quality_pct": None, "calculation_method": "x", "source_url": None})
        self.assertEqual(r["value"], 66402.3)
        self.assertIsNone(r["value_text"])

    def test_nulos_se_conservan_como_nulos(self):
        r = storage.from_json_row({
            "asset_id": "US", "asset_type": "macro", "domain": "macro",
            "metric": "cpi_yoy_pct", "value": 3.2, "unit": "%",
            "data_as_of": "2026-06-01", "retrieved_at": "2026-09-04T11:58:43Z",
            "source": "FRED", "source_priority": 1, "confidence_pct": None,
            "data_quality_pct": None, "calculation_method": "x", "source_url": None})
        self.assertIsNone(r["confidence_pct"])
        self.assertIsNone(r["data_quality_pct"])
        self.assertIsNone(r["source_url"])



if __name__ == "__main__":
    unittest.main()
