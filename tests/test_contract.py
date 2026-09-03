"""Pruebas del Data Contract (engine/contract/) -- Fase de visualizacion,
ver docs/03-arquitectura-visualizacion-y-acceso.md.

Usa las mismas fixtures congeladas que tests/test_engines.py, con el
mismo cuidado de no depender de red ni de las carpetas _data reales.
"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine", "contract"))

from test_engines import _materialize_fixtures, ROOT as ENGINES_ROOT  # noqa: E402

import schema  # noqa: E402


def _import_contract_module(modname):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine", "contract")
    sys.path.insert(0, path)
    try:
        if modname in sys.modules:
            del sys.modules[modname]
        return __import__(modname)
    finally:
        sys.path.remove(path)


class TestSchema(unittest.TestCase):
    def test_metric_row_valida_ok(self):
        row = {
            "asset_id": "BTC", "asset_type": "crypto", "domain": "tecnico",
            "metric": "precio", "value": 100.0, "unit": "EUR",
            "data_as_of": "2026-09-01", "retrieved_at": "2026-09-01T10:00:00Z",
            "source": "Kraken", "source_priority": 2,
            "confidence_pct": None, "data_quality_pct": None,
            "calculation_method": None, "source_url": None,
        }
        self.assertTrue(schema.validate_metric_row(row))

    def test_rechaza_data_as_of_futuro(self):
        row = {
            "asset_id": "BTC", "asset_type": "crypto", "domain": "tecnico",
            "metric": "precio", "value": 100.0, "unit": "EUR",
            "data_as_of": "2026-12-01", "retrieved_at": "2026-09-01T10:00:00Z",
            "source": "Kraken", "source_priority": 2,
        }
        with self.assertRaises(schema.ContractError):
            schema.validate_metric_row(row)

    def test_rechaza_campo_no_reconocido(self):
        row = {
            "asset_id": "BTC", "asset_type": "crypto", "domain": "tecnico",
            "metric": "precio", "value": 100.0, "unit": "EUR",
            "data_as_of": "2026-09-01", "retrieved_at": "2026-09-01T10:00:00Z",
            "source": "Kraken", "source_priority": 2,
            "cantidad_neta": 5,  # nunca deberia poder colarse un campo de cartera
        }
        with self.assertRaises(schema.ContractError):
            schema.validate_metric_row(row)

    def test_rechaza_hint_de_cartera_privada(self):
        row = {
            "asset_id": "BTC", "asset_type": "crypto", "domain": "tecnico",
            "metric": "precio", "value": 100.0, "unit": "EUR",
            "data_as_of": "2026-09-01", "retrieved_at": "2026-09-01T10:00:00Z",
            "source": "Kraken", "source_priority": 2,
            "source_url": "ver CARTERA_A_posicion_neta_cripto.csv",
        }
        with self.assertRaises(schema.ContractError):
            schema.validate_metric_row(row)


class TestAdapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _materialize_fixtures()
        cls.mod = _import_contract_module("adapters")

    def test_adapt_crypto_filas_validas(self):
        rows = self.mod.adapt_crypto("BTC", None)
        self.assertTrue(len(rows) > 0)
        for row in rows:
            schema.validate_metric_row(row)
            self.assertEqual(row["asset_id"], "BTC")

    def test_adapt_technical_filas_validas(self):
        rows = self.mod.adapt_technical("BTC")
        self.assertTrue(len(rows) > 0)
        for row in rows:
            schema.validate_metric_row(row)

    def test_adapt_macro_filas_validas(self):
        rows = self.mod.adapt_macro()
        self.assertTrue(len(rows) > 0)
        for row in rows:
            schema.validate_metric_row(row)

    def test_adapt_equity_distingue_data_as_of_de_retrieved_at(self):
        rows = self.mod.adapt_equity("IBM")
        for row in rows:
            schema.validate_metric_row(row)
        precio_row = next(r for r in rows if r["metric"] == "precio")
        pe_row = next(r for r in rows if r["metric"] == "pe_ratio")
        # el precio y el ratio fundamental vienen de fechas distintas -- la
        # razon de ser de separar data_as_of de retrieved_at (docs/03)
        self.assertNotEqual(precio_row["data_as_of"], pe_row["data_as_of"])

    def test_adapt_thesis_no_incluye_cantidades_de_cartera(self):
        sys.path.insert(0, os.path.join(ENGINES_ROOT, "engine", "reasoning"))
        try:
            if "thesis" in sys.modules:
                del sys.modules["thesis"]
            thesis_mod = __import__("thesis")
        finally:
            sys.path.remove(os.path.join(ENGINES_ROOT, "engine", "reasoning"))
        thesis = thesis_mod.build_thesis("BTC", None)
        row = self.mod.adapt_thesis(thesis, "crypto")
        schema.validate_thesis_row(row)
        serialized = str(row)
        for hint in schema.FORBIDDEN_SOURCE_HINTS:
            self.assertNotIn(hint, serialized)


class TestQA(unittest.TestCase):
    """Usa un DATA_DIR temporal con datos fabricados a mano -- nunca el
    data/ real, para que la prueba sea determinista y no dependa de si
    build.py se ha ejecutado antes."""

    def setUp(self):
        import shutil
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmpdir, "metrics"))
        os.makedirs(os.path.join(self.tmpdir, "thesis"))
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)

    def _write(self, subdir, fname, content):
        import json
        with open(os.path.join(self.tmpdir, subdir, fname), "w") as f:
            json.dump(content, f)

    def test_diagnostico_limpio_da_pass(self):
        self._write("metrics", "BTC.json", [{
            "asset_id": "BTC", "asset_type": "crypto", "domain": "tecnico",
            "metric": "precio", "value": 100.0, "unit": "EUR",
            "data_as_of": "2026-09-01", "retrieved_at": "2026-09-01T10:00:00Z",
            "source": "Kraken", "source_priority": 2,
            "confidence_pct": 80, "data_quality_pct": 90,
            "calculation_method": None, "source_url": None,
        }])
        qa = _import_contract_module("qa")
        qa.DATA_DIR = self.tmpdir
        report, ok = qa.run_qa()
        self.assertTrue(ok)
        self.assertIn("PASS", report)

    def test_diagnostico_detecta_incidencia_de_privacidad(self):
        self._write("metrics", "BTC.json", [{
            "asset_id": "BTC", "asset_type": "crypto", "domain": "tecnico",
            "metric": "precio", "value": 100.0, "unit": "EUR",
            "data_as_of": "2026-09-01", "retrieved_at": "2026-09-01T10:00:00Z",
            "source": "Kraken", "source_priority": 2,
            "confidence_pct": 80, "data_quality_pct": 90,
            "calculation_method": None, "source_url": "ver CARTERA_A_posicion_neta_cripto.csv",
        }])
        qa = _import_contract_module("qa")
        qa.DATA_DIR = self.tmpdir
        report, ok = qa.run_qa()
        self.assertFalse(ok, "una fila con hint de cartera privada debe hacer fallar el diagnóstico")


if __name__ == "__main__":
    unittest.main()
