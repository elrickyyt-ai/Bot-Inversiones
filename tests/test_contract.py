"""Pruebas del Data Contract (engine/contract/) -- Fase de visualizacion,
ver docs/03-arquitectura-visualizacion-y-acceso.md.

Usa las mismas fixtures congeladas que tests/test_engines.py, con el
mismo cuidado de no depender de red ni de las carpetas _data reales.
"""
import datetime
import json
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

    def _news_row(self, **overrides):
        row = {
            "news_id": "abc123", "asset_id": "XRP", "asset_type": "crypto",
            "data_as_of": "2026-09-02T21:31:05Z", "retrieved_at": "2026-09-03T12:00:00Z",
            "source": "Decrypt.co", "source_domain": "decrypt.co", "source_priority": 3,
            "headline": "titular", "summary": "resumen", "url": "https://decrypt.co/x",
            "sentiment": 0.19, "sentiment_label": "Somewhat-Bullish", "relevance": 0.68,
            "persona_influyente": None,
        }
        row.update(overrides)
        return row

    def test_news_row_valida_ok(self):
        self.assertTrue(schema.validate_news_row(self._news_row()))

    def test_rechaza_relevance_fuera_de_rango(self):
        with self.assertRaises(schema.ContractError):
            schema.validate_news_row(self._news_row(relevance=1.5))

    def test_news_row_rechaza_hint_de_cartera_privada(self):
        with self.assertRaises(schema.ContractError):
            schema.validate_news_row(self._news_row(summary="ver CARTERA_A_posicion.csv"))


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

    def test_adapt_technical_incluye_sma_atr_y_volatilidad(self):
        """Paso 3 (2026-09-03): ampliar technical con SMA/ATR/volatilidad,
        que engine/technical/score.py ya calculaba pero el adaptador
        todavia no extraia."""
        rows = self.mod.adapt_technical("BTC")
        for row in rows:
            schema.validate_metric_row(row)
        metrics = {r["metric"] for r in rows}
        for expected in ("sma20", "sma50", "sma100", "sma200", "atr14",
                          "atr14_pct_precio", "volatilidad_hist_30d_anualizada_pct"):
            self.assertIn(expected, metrics)

    def test_adapt_technical_incluye_volumen(self):
        """Bloque 3 (2026-09-04): volumen es uno de los campos pedidos
        explicitamente para el historico, anadido tambien a "hoy" para
        que no diverjan."""
        rows = self.mod.adapt_technical("BTC")
        by_metric = {r["metric"]: r for r in rows}
        self.assertIn("volumen", by_metric)
        self.assertEqual(by_metric["volumen"]["unit"], "unidades")
        self.assertGreater(by_metric["volumen"]["value"], 0)

    def test_adapt_technical_backfill_vacio_sin_fichero(self):
        """Un activo sin {ID}_ohlc_backfill.json debe devolver [] en vez
        de fallar, mismo patron que adapt_news()."""
        self.assertEqual(self.mod.adapt_technical_backfill("ZZZ"), [])

    def test_adapt_technical_backfill_excluye_fechas_ya_en_el_data_contract(self):
        """Corregido 2026-09-04 (hueco de proceso detectado en Power BI):
        adapt_technical_backfill() ya no excluye por una frontera fija
        (la cache rotativa de Kraken, que no reflejaba lo que el Data
        Contract tenia escrito de verdad) -- ahora excluye cualquier
        fecha que YA este en data/metrics/{symbol}.json, sin importar en
        que posicion caiga. Fixture: tests/fixtures/technical/
        BTC_ohlc_backfill.json (30 velas, 2024-06-30 -> 2024-07-29).
        Simulamos un Data Contract existente con dos fechas YA cubiertas
        en mitad del rango (no en un extremo) -- exactamente el patron
        de bug real: el cron solo escribe "hoy" cada vez que corre, deja
        huecos internos, no una frontera limpia."""
        import shutil
        import tempfile
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmpdir, ignore_errors=True)
        os.makedirs(os.path.join(tmpdir, "metrics"))
        ya_cubiertas = ["2024-07-10", "2024-07-20"]
        existing_rows = [
            {"asset_id": "BTC", "asset_type": "crypto", "domain": "tecnico", "metric": "precio",
             "value": 1.0, "unit": "EUR", "data_as_of": f, "retrieved_at": "2026-09-04T00:00:00Z",
             "source": "Kraken", "source_priority": 2, "confidence_pct": None, "data_quality_pct": None,
             "calculation_method": None, "source_url": None}
            for f in ya_cubiertas
        ]
        with open(os.path.join(tmpdir, "metrics", "BTC.json"), "w") as f:
            json.dump(existing_rows, f)

        original_dir = self.mod.DATA_CONTRACT_DIR
        self.mod.DATA_CONTRACT_DIR = tmpdir
        self.addCleanup(setattr, self.mod, "DATA_CONTRACT_DIR", original_dir)

        rows = self.mod.adapt_technical_backfill("BTC")
        self.assertGreater(len(rows), 0)
        for row in rows:
            schema.validate_metric_row(row)
            self.assertEqual(row["source"], "Coinbase")
        fechas = {r["data_as_of"] for r in rows if r["metric"] == "precio"}
        self.assertEqual(len(fechas), 28, "30 velas de la fixture menos las 2 ya cubiertas por Kraken")
        for f in ya_cubiertas:
            self.assertNotIn(f, fechas, "una fecha ya cubierta por Kraken no debe reescribirse desde Coinbase")
        metrics = {r["metric"] for r in rows}
        self.assertIn("precio", metrics)
        self.assertIn("volumen", metrics)
        self.assertIn("sma20", metrics, "30 velas alcanzan para sma20 (necesita 20)")
        self.assertNotIn("sma50", metrics, "30 velas no alcanzan para sma50 (necesita 50), no debe inventarse")
        self.assertNotIn("sma200", metrics)

    def test_adapt_asset_crypto_tiene_currency_documentada(self):
        row = self.mod.adapt_asset_crypto("BTC")
        schema.validate_asset_row(row)
        self.assertEqual(row["currency"], "EUR")
        self.assertEqual(row["name"], "Bitcoin")
        self.assertIsNone(row["country"], "BTC no tiene country_origin en CoinGecko, no debe inventarse")

    def test_adapt_asset_equity_todos_los_campos_de_la_fuente(self):
        row = self.mod.adapt_asset_equity("IBM")
        schema.validate_asset_row(row)
        self.assertEqual(row["currency"], "USD")
        self.assertEqual(row["exchange"], "NYSE")
        self.assertEqual(row["country"], "USA")

    def test_adapt_asset_macro_no_deja_huerfano_el_asset_id(self):
        row = self.mod.adapt_asset_macro("US")
        schema.validate_asset_row(row)
        self.assertEqual(row["asset_id"], "US")

    def test_adapt_macro_filas_validas(self):
        rows = self.mod.adapt_macro()
        self.assertTrue(len(rows) > 0)
        for row in rows:
            schema.validate_metric_row(row)

    def test_adapt_macro_data_as_of_es_la_fecha_real_no_la_de_ejecucion(self):
        """2026-09-04: mismo bug que se corrigio para BTC/XRP el mismo
        dia -- data_as_of debia ser la fecha real del ultimo dato de
        FRED, no datetime.now(). Con datetime.now() esta prueba habria
        sido indetectable (fixture fija, 'hoy' cambia cada dia)."""
        rows = self.mod.adapt_macro()
        by_metric = {r["metric"]: r for r in rows}
        self.assertEqual(by_metric["cpi_yoy_pct"]["data_as_of"], "2026-06-01")
        self.assertEqual(by_metric["fed_funds_pct"]["data_as_of"], "2026-06-01")
        self.assertEqual(by_metric["hicp_yoy_pct"]["data_as_of"], "2026-06-01")
        self.assertEqual(by_metric["ecb_deposit_rate_pct"]["data_as_of"], "2026-07-22")

    def test_adapt_macro_backfill_filas_validas_y_con_fechas_distintas(self):
        """Backfill (2026-09-04): a diferencia de adapt_macro() (solo
        'hoy', misma fecha en todas las filas), el backfill debe traer
        muchas fechas distintas -- es la razon de ser del backfill."""
        rows = self.mod.adapt_macro_backfill()
        self.assertGreater(len(rows), 1000, "FRED ya tiene decadas de historia descargada")
        for row in rows:
            schema.validate_metric_row(row)
        fechas = {r["data_as_of"] for r in rows}
        self.assertGreater(len(fechas), 100, "el backfill debe cubrir muchas fechas distintas, no solo 'hoy'")
        # cada activo declarado es US o EA, nunca uno inventado
        self.assertEqual({r["asset_id"] for r in rows}, {"US", "EA"})

    def test_adapt_crypto_backfill_vacio_sin_cadena_tvl(self):
        self.assertEqual(self.mod.adapt_crypto_backfill("BTC", None), [])
        self.assertEqual(self.mod.adapt_crypto_backfill("XRP", None), [])

    def test_adapt_crypto_backfill_filas_validas_y_con_fechas_distintas(self):
        """Bloque 2 (2026-09-04): igual que adapt_macro_backfill(), a
        diferencia de adapt_crypto() (solo 'hoy') el backfill debe traer
        varias fechas distintas -- tests/fixtures/crypto/ETH_tvl.json
        tiene 15 puntos diarios fijos."""
        rows = self.mod.adapt_crypto_backfill("ETH", "Ethereum")
        self.assertEqual(len(rows), 6, "9 primeros puntos sin ventana de 365d suficiente")
        for row in rows:
            schema.validate_metric_row(row)
            self.assertEqual(row["asset_id"], "ETH")
            self.assertEqual(row["metric"], "tvl_percentile_365d")
            self.assertEqual(row["source"], "DefiLlama")
        fechas = {r["data_as_of"] for r in rows}
        self.assertEqual(len(fechas), 6, "cada fila debe tener una fecha real distinta")

    def test_adapt_equity_distingue_data_as_of_de_retrieved_at(self):
        rows = self.mod.adapt_equity("IBM")
        for row in rows:
            schema.validate_metric_row(row)
        precio_row = next(r for r in rows if r["metric"] == "precio")
        pe_row = next(r for r in rows if r["metric"] == "pe_ratio")
        # el precio y el ratio fundamental vienen de fechas distintas -- la
        # razon de ser de separar data_as_of de retrieved_at (docs/03)
        self.assertNotEqual(precio_row["data_as_of"], pe_row["data_as_of"])

    def test_adapt_equity_incluye_eps_margenes_sorpresa_y_analistas(self):
        """Paso 3 (2026-09-03): ampliar equity con metricas que el motor ya
        calculaba pero el adaptador todavia no extraia."""
        rows = self.mod.adapt_equity("IBM")
        for row in rows:
            schema.validate_metric_row(row)
        by_metric = {r["metric"]: r for r in rows}
        self.assertIn("eps", by_metric)
        self.assertEqual(by_metric["eps"]["unit"], "USD")
        self.assertIn("profit_margin_pct", by_metric)
        self.assertIn("operating_margin_pct", by_metric)
        self.assertIn("earnings_beats_8q", by_metric)
        self.assertIn("earnings_misses_8q", by_metric)
        self.assertIn("analyst_target_price", by_metric)
        # todas las metricas nuevas comparten fundamental_as_of con pe_ratio,
        # no con el precio -- vienen del mismo overview, no de la cotizacion
        self.assertEqual(by_metric["eps"]["data_as_of"], by_metric["pe_ratio"]["data_as_of"])

    def test_adapt_news_filas_validas_una_por_articulo(self):
        """Paso 4 (2026-09-03): fixture congelada de 3 articulos reales de
        NEWS_SENTIMENT (Alpha Vantage) para XRP -- cada uno con su propio
        sentiment/relevance especifico de XRP, no un promedio agregado."""
        rows = self.mod.adapt_news("XRP", "crypto")
        self.assertEqual(len(rows), 3)
        for row in rows:
            schema.validate_news_row(row)
            self.assertEqual(row["asset_id"], "XRP")
        # cada articulo conserva su propia fila -- no se colapsan en un
        # unico sentimiento medio, tal como pidio el usuario
        news_ids = {r["news_id"] for r in rows}
        self.assertEqual(len(news_ids), 3)

    def test_adapt_news_sin_data_devuelve_lista_vacia(self):
        """Un activo sin _data/{ID}_news_sentiment.json todavia consultado
        (cuota de Alpha Vantage) no debe hacer fallar build.py."""
        rows = self.mod.adapt_news("ETH", "crypto")
        self.assertEqual(rows, [])

    def test_adapt_news_no_inventa_persona_influyente(self):
        rows = self.mod.adapt_news("XRP", "crypto")
        for row in rows:
            if row["persona_influyente"] is not None:
                self.fail("ningun autor de la fixture esta en personas_influyentes.json")

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


class TestBuildHistorizacion(unittest.TestCase):
    """engine/contract/build.py debe ser append-only e idempotente --
    ejecutarlo dos veces con el mismo data_as_of no debe duplicar filas."""

    def setUp(self):
        import shutil
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.build = _import_contract_module("build")
        self.build.DATA_DIR = self.tmpdir

    def _metric_row(self, data_as_of):
        return {
            "asset_id": "BTC", "asset_type": "crypto", "domain": "tecnico",
            "metric": "precio", "value": 100.0, "unit": "EUR",
            "data_as_of": data_as_of, "retrieved_at": "2026-09-03T10:00:00Z",
            "source": "Kraken", "source_priority": 2,
            "confidence_pct": None, "data_quality_pct": None,
            "calculation_method": None, "source_url": None,
        }

    def _thesis_row(self, data_as_of):
        return {
            "thesis_id": f"BTC_{data_as_of}_x", "asset_id": "BTC", "thesis_type": "crypto",
            "bull_case": "b", "base_case": "b", "bear_case": "b",
            "contradictions": [], "convergences": [], "divergences": [],
            "invalidation_factors": [], "confidence_pct": 80,
            "data_as_of": data_as_of, "retrieved_at": "2026-09-03T10:00:00Z",
        }

    def test_misma_ejecucion_dos_veces_no_duplica_metricas(self):
        row = self._metric_row("2026-09-01")
        total1, added1, skipped1 = self.build._write_metric_rows("BTC", [row])
        total2, added2, skipped2 = self.build._write_metric_rows("BTC", [row])
        self.assertEqual((total1, added1, skipped1), (1, 1, 0))
        self.assertEqual((total2, added2, skipped2), (1, 0, 1))

    def test_dia_distinto_si_se_acumula(self):
        self.build._write_metric_rows("BTC", [self._metric_row("2026-09-01")])
        total, added, skipped = self.build._write_metric_rows("BTC", [self._metric_row("2026-09-02")])
        self.assertEqual((total, added, skipped), (2, 1, 0))

    def test_thesis_no_duplica_mismo_data_as_of(self):
        t1_total, t1_added = self.build._write_thesis_row("BTC", self._thesis_row("2026-09-01"))
        t2_total, t2_added = self.build._write_thesis_row("BTC", self._thesis_row("2026-09-01"))
        self.assertEqual((t1_total, t1_added), (1, 1))
        self.assertEqual((t2_total, t2_added), (1, 0))

    def test_thesis_formato_antiguo_objeto_unico_se_migra_sin_perderse(self):
        import json
        path = os.path.join(self.tmpdir, "thesis", "BTC.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as f:
            json.dump(self._thesis_row("2026-08-01"), f)  # formato antiguo: objeto, no lista
        total, added = self.build._write_thesis_row("BTC", self._thesis_row("2026-09-01"))
        self.assertEqual((total, added), (2, 1), "la tesis antigua no debe perderse al migrar a formato historico")

    def _news_row(self, news_id):
        return {
            "news_id": news_id, "asset_id": "XRP", "asset_type": "crypto",
            "data_as_of": "2026-09-02T21:31:05Z", "retrieved_at": "2026-09-03T10:00:00Z",
            "source": "Decrypt.co", "source_domain": "decrypt.co", "source_priority": 3,
            "headline": "titular", "summary": "resumen", "url": f"https://decrypt.co/{news_id}",
            "sentiment": 0.19, "sentiment_label": "Somewhat-Bullish", "relevance": 0.68,
            "persona_influyente": None,
        }

    def test_misma_ejecucion_dos_veces_no_duplica_noticias(self):
        row = self._news_row("abc123")
        total1, added1, skipped1 = self.build._write_news_rows("XRP", [row])
        total2, added2, skipped2 = self.build._write_news_rows("XRP", [row])
        self.assertEqual((total1, added1, skipped1), (1, 1, 0))
        self.assertEqual((total2, added2, skipped2), (1, 0, 1))

    def test_articulo_nuevo_se_acumula(self):
        self.build._write_news_rows("XRP", [self._news_row("abc123")])
        total, added, skipped = self.build._write_news_rows("XRP", [self._news_row("def456")])
        self.assertEqual((total, added, skipped), (2, 1, 0))

    def test_sin_noticias_y_sin_fichero_previo_no_escribe_nada(self):
        total, added, skipped = self.build._write_news_rows("BTC", [])
        self.assertEqual((total, added, skipped), (0, 0, 0))
        self.assertFalse(os.path.exists(os.path.join(self.tmpdir, "news", "BTC.json")))

    def _asset_row(self, currency="EUR"):
        return {
            "asset_id": "BTC", "asset_type": "crypto", "name": "Bitcoin",
            "sector": "Cripto", "industry": None, "country": None,
            "currency": currency, "exchange": None, "active": True,
            "retrieved_at": "2026-09-03T10:00:00Z", "source": "CoinGecko",
        }

    def test_asset_row_no_reescribe_si_solo_cambia_retrieved_at(self):
        """Automatizacion GitHub Actions (2026-09-03): una segunda pasada
        sin cambios reales no debe tocar el fichero -- si no, un cron
        diario generaria un commit cada dia solo por el timestamp."""
        import json
        import time
        path = os.path.join(self.tmpdir, "assets", "BTC.json")
        self.build._write_asset_row("BTC", self._asset_row())
        primera_escritura = os.path.getmtime(path)
        time.sleep(0.01)
        otro_retrieved_at = dict(self._asset_row(), retrieved_at="2026-09-04T10:00:00Z")
        self.build._write_asset_row("BTC", otro_retrieved_at)
        segunda_escritura = os.path.getmtime(path)
        self.assertEqual(primera_escritura, segunda_escritura, "no debio reescribir el fichero")
        with open(path) as f:
            contenido = json.load(f)
        self.assertEqual(contenido["retrieved_at"], "2026-09-03T10:00:00Z", "conserva el retrieved_at original")

    def test_asset_row_si_reescribe_si_cambia_algo_real(self):
        import json
        self.build._write_asset_row("BTC", self._asset_row(currency="EUR"))
        self.build._write_asset_row("BTC", self._asset_row(currency="USD"))
        with open(os.path.join(self.tmpdir, "assets", "BTC.json")) as f:
            contenido = json.load(f)
        self.assertEqual(contenido["currency"], "USD")


class TestDetectTechnicalGaps(unittest.TestCase):
    """engine/contract/backfill.py::detect_technical_gaps() -- el lado de
    diagnostico/reporte de la correccion de 2026-09-04 (hueco de proceso
    detectado en Power BI)."""

    def setUp(self):
        import shutil
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        os.makedirs(os.path.join(self.tmpdir, "metrics"))
        self.backfill = _import_contract_module("backfill")
        self.backfill.DATA_DIR = self.tmpdir

    def _write_precio_dates(self, symbol, fechas):
        rows = [
            {"asset_id": symbol, "asset_type": "crypto", "domain": "tecnico", "metric": "precio",
             "value": 1.0, "unit": "EUR", "data_as_of": f, "retrieved_at": "2026-09-04T00:00:00Z",
             "source": "Kraken", "source_priority": 2, "confidence_pct": None, "data_quality_pct": None,
             "calculation_method": None, "source_url": None}
            for f in fechas
        ]
        with open(os.path.join(self.tmpdir, "metrics", f"{symbol}.json"), "w") as f:
            json.dump(rows, f)

    def test_sin_fichero_no_da_huecos(self):
        self.assertEqual(self.backfill.detect_technical_gaps("BTC"), [])

    def test_fechas_consecutivas_sin_huecos(self):
        self._write_precio_dates("BTC", ["2026-01-01", "2026-01-02", "2026-01-03"])
        self.assertEqual(self.backfill.detect_technical_gaps("BTC"), [])

    def test_detecta_un_hueco_interno(self):
        """El patron real del bug: dos fechas 'sueltas' con un hueco
        grande en medio -- no una frontera limpia en un extremo."""
        self._write_precio_dates("BTC", ["2024-07-29", "2026-07-20", "2026-09-04"])
        gaps = self.backfill.detect_technical_gaps("BTC")
        self.assertEqual(gaps, [
            ("2024-07-29", "2026-07-20", 721),
            ("2026-07-20", "2026-09-04", 46),
        ])

    def test_ignora_otras_metricas_y_dominios(self):
        """Solo debe mirar domain=tecnico, metric=precio -- otras filas
        (sma20, o de otro dominio) no deben contarse como fechas de la
        serie de precio."""
        rows = [
            {"asset_id": "BTC", "asset_type": "crypto", "domain": "tecnico", "metric": "precio",
             "value": 1.0, "unit": "EUR", "data_as_of": "2026-01-01", "retrieved_at": "2026-09-04T00:00:00Z",
             "source": "Kraken", "source_priority": 2, "confidence_pct": None, "data_quality_pct": None,
             "calculation_method": None, "source_url": None},
            {"asset_id": "BTC", "asset_type": "crypto", "domain": "tecnico", "metric": "sma20",
             "value": 1.0, "unit": "EUR", "data_as_of": "2026-06-01", "retrieved_at": "2026-09-04T00:00:00Z",
             "source": "Kraken", "source_priority": 2, "confidence_pct": None, "data_quality_pct": None,
             "calculation_method": None, "source_url": None},
            {"asset_id": "BTC", "asset_type": "crypto", "domain": "fundamental", "metric": "precio",
             "value": 1.0, "unit": "EUR", "data_as_of": "2026-03-01", "retrieved_at": "2026-09-04T00:00:00Z",
             "source": "CoinGecko", "source_priority": 2, "confidence_pct": None, "data_quality_pct": None,
             "calculation_method": None, "source_url": None},
        ]
        with open(os.path.join(self.tmpdir, "metrics", "BTC.json"), "w") as f:
            json.dump(rows, f)
        # solo hay UNA fecha de domain=tecnico+metric=precio -- sin pares, sin huecos que detectar
        self.assertEqual(self.backfill.detect_technical_gaps("BTC"), [])


if __name__ == "__main__":
    unittest.main()
