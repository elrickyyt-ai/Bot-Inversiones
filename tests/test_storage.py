"""Pruebas de la capa de almacenamiento history / incoming / current.

Cubren lo que el plan de migracion exige demostrar, no lo que es facil de
probar: que la resolucion es un upsert por clave logica y no una
concatenacion, que la precedencia la decide retrieved_at y no la capa
fisica donde vive la fila, y que current es reproducible funcionalmente.
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


class TestParquetYManifiesto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = (storage.HISTORY_DIR, storage.INCOMING_DIR, storage.CURRENT_DIR)
        storage.HISTORY_DIR = os.path.join(self.tmp, "history")
        storage.INCOMING_DIR = os.path.join(self.tmp, "incoming")
        storage.CURRENT_DIR = os.path.join(self.tmp, "current")

    def tearDown(self):
        storage.HISTORY_DIR, storage.INCOMING_DIR, storage.CURRENT_DIR = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_manifiesto_registra_hash_filas_y_rango(self):
        filas = [fila(metric=f"m{i}", dia=f"2024-03-{i+1:02d}") for i in range(5)]
        storage.write_partition("equity", "TEST", 2024, filas)
        man = storage.read_manifest("equity", "TEST")
        self.assertEqual(len(man["particiones"]), 1)
        e = man["particiones"][0]
        self.assertEqual(e["fichero"], "2024.parquet")
        self.assertEqual(e["revision"], 1)
        self.assertEqual(e["filas"], 5)
        self.assertEqual(e["data_as_of_min"], "2024-03-01")
        self.assertEqual(e["data_as_of_max"], "2024-03-05")
        self.assertEqual(len(e["sha256"]), 64)

    def test_hash_del_manifiesto_detecta_cambio(self):
        storage.write_partition("equity", "TEST", 2024, [fila()])
        man = storage.read_manifest("equity", "TEST")
        p = os.path.join(storage.history_dir("equity", "TEST"), "2024.parquet")
        self.assertEqual(storage.sha256_file(p), man["particiones"][0]["sha256"])
        storage.write_parquet([fila(value=777.0)], p)   # alguien reescribe la particion
        self.assertNotEqual(storage.sha256_file(p), man["particiones"][0]["sha256"])

    def test_revision_usa_nombre_distinto_y_conserva_la_original(self):
        storage.write_partition("equity", "TEST", 2024, [fila(value=1.0)])
        storage.write_partition("equity", "TEST", 2024,
                                [fila(value=2.0, ts="2024-06-01T06:00:00Z")], revision=2)
        d = storage.history_dir("equity", "TEST")
        self.assertTrue(os.path.exists(os.path.join(d, "2024.parquet")))
        self.assertTrue(os.path.exists(os.path.join(d, "2024_r2.parquet")))
        man = storage.read_manifest("equity", "TEST")
        self.assertEqual([e["revision"] for e in man["particiones"]], [1, 2])
        # r1 sigue diciendo lo que decia: la inmutabilidad fisica se conserva
        r1 = storage.read_parquet(os.path.join(d, "2024.parquet"))
        self.assertEqual(r1[0]["value"], 1.0)

    def test_history_resuelto_da_una_fila_por_clave(self):
        storage.write_partition("equity", "TEST", 2024, [fila(value=1.0)])
        storage.write_partition("equity", "TEST", 2024,
                                [fila(value=2.0, ts="2024-06-01T06:00:00Z")], revision=2)
        crudas = storage.read_history("equity", "TEST")
        self.assertEqual(len(crudas), 2)
        resueltas = storage.resolve(crudas)
        self.assertEqual(len(resueltas), 1)
        self.assertEqual(resueltas[0]["value"], 2.0)


class TestCurrent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = (storage.HISTORY_DIR, storage.INCOMING_DIR, storage.CURRENT_DIR)
        storage.HISTORY_DIR = os.path.join(self.tmp, "history")
        storage.INCOMING_DIR = os.path.join(self.tmp, "incoming")
        storage.CURRENT_DIR = os.path.join(self.tmp, "current")

    def tearDown(self):
        storage.HISTORY_DIR, storage.INCOMING_DIR, storage.CURRENT_DIR = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_combina_history_e_incoming(self):
        storage.write_partition("equity", "TEST", 2024, [fila(metric="a", dia="2024-05-01")])
        storage.append_incoming(storage.incoming_path("TEST", 2026),
                                [fila(metric="b", dia="2026-05-01", ts="2026-05-01T06:00:00Z")])
        self.assertEqual(storage.materialize("equity", "TEST"), 2)

    def test_reproducibilidad_funcional_no_binaria(self):
        """Mismos inputs -> mismas claves, valores, nulos, schema y orden.
        NO se exige identidad de bytes: otra version de PyArrow podria
        comprimir distinto sin que eso sea un fallo."""
        storage.write_partition("equity", "TEST", 2024,
                                [fila(metric=f"m{i}", value=float(i)) for i in range(20)])
        storage.materialize("equity", "TEST")
        p = os.path.join(storage.CURRENT_DIR, "TEST.parquet")
        primera = storage.read_parquet(p)
        storage.materialize("equity", "TEST")
        segunda = storage.read_parquet(p)
        self.assertEqual([storage.logical_key(r) for r in primera],
                         [storage.logical_key(r) for r in segunda])
        self.assertEqual([r["value"] for r in primera], [r["value"] for r in segunda])
        self.assertEqual([r["value_text"] for r in primera], [r["value_text"] for r in segunda])
        self.assertEqual(sorted(primera[0].keys()), sorted(storage.COLUMNS))

    def test_una_clave_logica_exactamente_una_fila(self):
        storage.write_partition("equity", "TEST", 2024, [fila(value=1.0)])
        storage.append_incoming(
            storage.incoming_path("TEST", 2026),
            [fila(value=2.0, ts="2026-01-01T06:00:00Z")])   # misma clave logica
        n = storage.materialize("equity", "TEST")
        self.assertEqual(n, 1)
        filas = storage.read_parquet(os.path.join(storage.CURRENT_DIR, "TEST.parquet"))
        self.assertEqual(filas[0]["value"], 2.0)

    def test_activo_solo_en_incoming_es_visible(self):
        """Un activo dado de alta a mitad de anio no tiene ninguna particion
        cerrada todavia. Resolver su asset_type solo por la carpeta de
        history/ lo dejaba invisible para qa.py y para la materializacion
        -- detectado por el test de privacidad de qa durante la migracion."""
        storage.append_incoming(storage.incoming_path("NUEVO", 2026),
                                [fila(asset_id="NUEVO", ts="2026-03-01T06:00:00Z")])
        self.assertEqual(storage.asset_type_of("NUEVO"), "equity")
        self.assertEqual(len(storage.read_asset("NUEVO")), 1)

    def test_no_deja_fichero_temporal(self):
        storage.write_partition("equity", "TEST", 2024, [fila()])
        storage.materialize("equity", "TEST")
        restos = [f for f in os.listdir(storage.CURRENT_DIR) if f.startswith(".")]
        self.assertEqual(restos, [], "el temporal debe renombrarse, no quedarse")


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
