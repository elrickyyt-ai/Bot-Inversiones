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
import datetime
import json
import os
import shutil
import sys
import tempfile
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
        "equity": os.path.join(ROOT, "engine", "equity", "_data"),
        "news": os.path.join(ROOT, "engine", "news", "_data"),
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

    def test_fecha_dato_es_la_de_coingecko_no_la_de_ejecucion(self):
        """2026-09-03: fecha_dato debia ser detail['last_updated'], no
        datetime.now() -- con datetime.now() esta prueba habria sido
        indetectable (la fixture es fija, "hoy" cambia cada dia que se
        ejecuta el test), que es precisamente como paso desapercibido el
        bug real de BTC/XRP desactualizados en CoinGecko."""
        r = self.mod.score_asset("BTC", None)
        self.assertEqual(r["fecha_dato"], "2026-07-20", "fecha_dato debe venir de detail['last_updated'], fijo en la fixture")


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

    def test_fecha_dato_es_la_de_la_ultima_vela_no_la_de_ejecucion(self):
        """2026-09-03: fecha_dato debia ser la fecha real de la ultima
        vela de Kraken (ohlc[-1][0]), no datetime.now() -- con
        datetime.now() esta prueba habria sido indetectable (la fixture
        es fija, "hoy" cambia cada dia que se ejecuta el test), que es
        precisamente como paso desapercibido el bug real de BTC/XRP
        desactualizados ~45 dias."""
        r = self.mod.score_asset("BTC")
        self.assertEqual(r["fecha_dato"], "2026-07-20", "fecha_dato debe venir de la ultima vela real de la fixture, no de hoy")

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

    def test_historical_series_us_misma_formula_que_yoy_actual(self):
        """Backfill (2026-09-04): historical_series_us() debe dar, para
        la fecha mas reciente, el mismo cpi_yoy_pct que score_us() -- es
        la misma formula aplicada a toda la historia, no una nueva."""
        actual = self.mod.score_us()["cpi_yoy_pct"]
        historico = self.mod.historical_series_us()
        cpi_rows = [(f, v) for m, f, v in historico if m == "cpi_yoy_pct"]
        self.assertEqual(cpi_rows[-1][1], actual, "el ultimo punto del historico debe coincidir con el dato 'de hoy'")

    def test_historical_series_us_empieza_un_anio_despues_del_origen(self):
        """La fixture us_cpi.json empieza en 1947-01-01 -- el primer YoY
        real solo puede calcularse a partir de 1948-01-01 (necesita un
        punto de ~12 meses antes dentro de la propia serie)."""
        historico = self.mod.historical_series_us()
        cpi_rows = [(f, v) for m, f, v in historico if m == "cpi_yoy_pct"]
        self.assertEqual(cpi_rows[0][0], "1948-01-01")

    def test_historical_series_no_incluye_regimen_ni_señales(self):
        """El backfill historico es solo dato -- ninguna sintesis de
        'hoy' (regimen_estimado, señales, confidence) debe colarse ahi,
        eso no tiene sentido por fecha pasada."""
        historico = self.mod.historical_series_us() + self.mod.historical_series_ea()
        metricas = {m for m, _, _ in historico}
        self.assertEqual(metricas, {"cpi_yoy_pct", "fed_funds_pct", "hicp_yoy_pct", "ecb_deposit_rate_pct"})


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

    def test_xom_detecta_contradiccion_crecimiento_anual_vs_ultimo_trimestre(self):
        t = self.mod.build_thesis_equity("XOM")
        self.assertTrue(len(t["contradicciones"]) >= 1, "XOM debe detectar la contradicción entre BPA YoY fuerte y el fallo del último trimestre")

    def test_thesis_equity_declara_los_tres_escenarios(self):
        t = self.mod.build_thesis_equity("IBM")
        for campo in ("bull_case", "base_case", "bear_case", "factores_que_invalidarian_la_tesis"):
            self.assertTrue(t[campo], f"falta {campo} en la tesis de acciones")


class TestEquityFundamentalsEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _materialize_fixtures()
        cls.mod = _import("equity", "score")

    def test_ibm_schema_y_rangos(self):
        r = self.mod.score_asset("IBM")
        self.assertEqual(r["activo"], "IBM")
        self.assertTrue(0 <= r["posicion_rango_52s_pct"] <= 100)
        self.assertTrue(0 <= r["data_quality_pct"] <= 100)
        self.assertTrue(r["confluencia"]["sesgo"])

    def test_xom_detecta_el_fallo_del_ultimo_trimestre(self):
        r = self.mod.score_asset("XOM")
        self.assertEqual(r["sorpresa_resultados"]["ultima_sorpresa_pct"], -4.3478)
        self.assertFalse(r["confluencia"]["detalle"]["ultima_sorpresa_positiva"])

    def test_beats_mas_misses_no_supera_8_trimestres(self):
        r = self.mod.score_asset("IBM")
        total = r["sorpresa_resultados"]["ultimos_8_trimestres_beats"] + r["sorpresa_resultados"]["ultimos_8_trimestres_misses"]
        self.assertLessEqual(total, 8)


class TestThesisLedger(unittest.TestCase):
    """Importante: usa un directorio temporal para el ledger, nunca el
    real -- estas pruebas no deben ensuciar el historial de tesis de
    verdad con entradas de test."""

    @classmethod
    def setUpClass(cls):
        _materialize_fixtures()
        cls.mod = _import("reasoning", "ledger")

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.mod.LEDGER_DIR = self.tmpdir

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_registrar_tesis_crea_entrada_con_umbral(self):
        entrada = self.mod.record_thesis("BTC", None)
        self.assertEqual(entrada["activo"], "BTC")
        self.assertIsNone(entrada["evaluacion"], "una tesis recién registrada no debe traer evaluación todavía")
        self.assertIsNotNone(entrada["umbral_movimiento_significativo_pct"])

    def test_no_evalua_antes_de_tiempo(self):
        self.mod.record_thesis("BTC", None)
        evaluadas = self.mod.evaluate_pending("BTC", precio_actual=999999)
        self.assertEqual(evaluadas, [], "no debe evaluar una entrada de hoy mismo, el horizonte es de 90 días")

    def test_evalua_correctamente_pasado_el_horizonte(self):
        entrada = self.mod.record_thesis("BTC", None)
        precio_inicial = entrada["precio_en_el_momento"]
        futuro = datetime.date.today() + datetime.timedelta(days=200)
        # Movimiento muy por encima de cualquier umbral de volatilidad razonable
        evaluadas = self.mod.evaluate_pending("BTC", precio_actual=precio_inicial * 3, hoy=futuro)
        self.assertEqual(len(evaluadas), 1)
        self.assertEqual(evaluadas[0]["evaluacion"]["veredicto"], "bull_case")


if __name__ == "__main__":
    unittest.main()
