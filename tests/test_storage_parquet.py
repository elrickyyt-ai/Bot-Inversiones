"""Nivel PARQUET de la capa de almacenamiento -- EXIGE PyArrow.

Abren particiones de history/ y materializan current/, asi que no pueden
correr en el cron diario. Si PyArrow no esta disponible se SALTAN de forma
EXPLICITA: un skip visible en la salida, nunca un PASS silencioso. "No se
pudo verificar" no es "verificado correctamente".
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

HAY_PYARROW = storage.hay_pyarrow()
RAZON_SKIP = ("PyArrow no disponible: el contenido de los parquet NO se ha verificado")

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


@unittest.skipUnless(HAY_PYARROW, RAZON_SKIP)
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


@unittest.skipUnless(HAY_PYARROW, RAZON_SKIP)
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



if __name__ == "__main__":
    unittest.main()
