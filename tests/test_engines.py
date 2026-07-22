"""Pruebas de humo para los motores construidos hasta ahora.

Objetivo: detectar cuanto antes si un cambio en un motor rompe su
contrato de datos (las claves que espera el consolidador o un futuro
motor de razonamiento) o produce valores fuera de rango sensato. No
sustituye una validacion financiera del contenido -- es una red de
seguridad tecnica, barata, sin dependencias externas (unittest de la
libreria estandar) y sin llamadas de red: usa una copia pequena de
datos reales ya descargados (tests/fixtures/), asi que no depende de
que las APIs externas esten disponibles ni respeten limites de tasa.

Ejecutar antes de tocar cualquier motor existente, y despues de anadir
uno nuevo:

    python3 -m unittest discover -s tests -v
"""
import json
import os
import shutil
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _materialize_fixtures():
    """Copia las fixtures a la carpeta _data de cada motor (gitignored),
    para que los motores lean exactamente lo que leerian en producción,
    sin tocar su código."""
    mapping = {
        "crypto": os.path.join(ROOT, "engine", "crypto", "_data"),
        "technical": os.path.join(ROOT, "engine", "technical", "_data"),
        "macro": os.path.join(ROOT, "engine", "macro", "_data"),
    }
    for name, dest in mapping.items():
        os.makedirs(dest, exist_ok=True)
        src = os.path.join(FIXTURES, name)
        for fname in os.listdir(src):
            shutil.copy(os.path.join(src, fname), os.path.join(dest, fname))


def _import(subdir, modname):
    path = os.path.join(ROOT, "engine", subdir)
    sys.path.insert(0, path)
    try:
        if modname in sys.modules:
            del sys.modules[modname]
        return __import__(modname)
    finally:
        sys.path.remove(path)


class TestCryptoFundamentalsEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _materialize_fixtures()
        cls.mod = _import("crypto", "score")

    def test_btc_schema_y_rangos(self):
        r = self.mod.score_asset("BTC", None)
        claves_esperadas = {
            "activo", "fecha_dato", "supply_pct_of_max", "fdv_mcap_ratio",
            "market_cap_percentile_365d", "tvl_usd_actual", "tvl_percentile_365d",
            "dev_commits_4_semanas", "dev_stars", "dev_forks",
            "posible_incidencia_datos", "data_quality_pct",
        }
        self.assertEqual(claves_esperadas, set(r.keys()))
        self.assertEqual(r["activo"], "BTC")
        self.assertIsNone(r["tvl_percentile_365d"], "BTC no tiene TVL, no debe inventarse un valor")
        self.assertTrue(0 <= r["data_quality_pct"] <= 100)
        if r["market_cap_percentile_365d"] is not None:
            self.assertTrue(0 <= r["market_cap_percentile_365d"] <= 100)

    def test_xrp_sin_tvl_no_marca_incidencia_falsa(self):
        r = self.mod.score_asset("XRP", None)
        self.assertFalse(r["posible_incidencia_datos"], "XRP sin TVL por diseño no debe marcarse como incidencia de datos")


class TestTechnicalEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _materialize_fixtures()
        cls.mod = _import("technical", "score")

    def test_btc_schema_y_rangos(self):
        r = self.mod.score_asset("BTC")
        self.assertEqual(r["activo"], "BTC")
        self.assertGreater(r["precio"], 0)
        if r["rsi14"] is not None:
            self.assertTrue(0 <= r["rsi14"] <= 100, "RSI fuera de su rango matemático [0,100]")
        self.assertIn("sesgo", r["confluencia"])
        self.assertIn("confidence_pct", r["confluencia"])
        self.assertTrue(0 <= r["confluencia"]["confidence_pct"] <= 100)

    def test_confluencia_nunca_mas_de_4_señales(self):
        r = self.mod.score_asset("XRP")
        alcistas = sum(1 for v in r["confluencia"]["detalle"].values() if v is True)
        self.assertLessEqual(alcistas, 4)


class TestMacroEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _materialize_fixtures()
        cls.mod = _import("macro", "score")

    def test_us_regimen_no_vacio(self):
        r = self.mod.score_us()
        self.assertTrue(r["regimen_estimado"])
        self.assertIsInstance(r["cpi_yoy_pct"], float)

    def test_ea_regimen_no_vacio(self):
        r = self.mod.score_ea()
        self.assertTrue(r["regimen_estimado"])
        self.assertIn("gap", r, "el gap de desempleo/curva de la Eurozona debe seguir declarado")


class TestScoringConsolidado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _materialize_fixtures()
        cls.mod = _import("scoring", "consolidate")

    def test_scorecard_btc_no_inventa_dominios_no_disponibles(self):
        sc = self.mod.build_scorecard("BTC", None)
        self.assertFalse(sc["dominios"]["noticias_sentimiento"]["disponible"])
        self.assertEqual(sc["cobertura_dominios"], "3/4")

    def test_scorecard_xrp_cobertura_completa(self):
        sc = self.mod.build_scorecard("XRP", None)
        self.assertTrue(sc["dominios"]["noticias_sentimiento"]["disponible"])
        self.assertEqual(sc["cobertura_dominios"], "4/4")


class TestMotorDeRazonamiento(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _materialize_fixtures()
        cls.mod = _import("reasoning", "thesis")

    def test_dot_hereda_confianza_reducida_por_incidencia_de_datos(self):
        t = self.mod.build_thesis("BTC", None)
        # BTC no tiene incidencia -> confidence no debe ir penalizado a 45
        self.assertNotEqual(t["confidence_pct"], 45)

    def test_xrp_propaga_la_contradiccion_de_noticias(self):
        t = self.mod.build_thesis("XRP", None)
        self.assertTrue(len(t["contradicciones"]) >= 1, "XRP debe heredar la contradicción ya detectada en Fase 4")

    def test_tesis_siempre_declara_los_tres_escenarios(self):
        t = self.mod.build_thesis("BTC", None)
        for campo in ("bull_case", "base_case", "bear_case", "factores_que_invalidarian_la_tesis"):
            self.assertTrue(t[campo], f"falta {campo} en la tesis")


if __name__ == "__main__":
    unittest.main()
