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

    def test_historical_tvl_percentile_vacio_sin_cadena_tvl(self):
        self.assertEqual(self.mod.historical_tvl_percentile("BTC", None), [])
        self.assertEqual(self.mod.historical_tvl_percentile("XRP", None), [])

    def test_historical_tvl_percentile_misma_formula_que_pct_in_window(self):
        """tests/fixtures/crypto/ETH_tvl.json: 15 puntos diarios fijos,
        pensados para que la ventana movil de 365 dias sea valida a partir
        del 10o punto (indice 9, _pct_in_window exige >=10 valores) --
        valores calculados a mano y verificados contra la formula ya
        existente en _pct_in_window, ninguna metodologia nueva."""
        out = self.mod.historical_tvl_percentile("ETH", "Ethereum")
        self.assertEqual(len(out), 6, "9 primeros puntos sin ventana suficiente, quedan 15-9=6")
        esperado = [
            ("2023-11-23", 87.5),
            ("2023-11-24", 25.0),
            ("2023-11-25", 100.0),
            ("2023-11-26", 90.0),
            ("2023-11-27", 10.0),
            ("2023-11-28", 100.0),
        ]
        self.assertEqual(out, esperado)


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

    def test_score_asset_incluye_volumen(self):
        """Bloque 3 (2026-09-04): volumen anadido a score_asset() para
        que el backfill (que si lo necesita, es uno de los campos
        pedidos explicitamente) no introduzca un campo que "hoy" no
        tiene -- misma fuente (ohlc[-1]['volume']), ya descargada, sin
        llamada nueva."""
        r = self.mod.score_asset("BTC")
        self.assertGreater(r["volumen"], 0)

    def test_historical_series_btc_fixture_conteo_y_esquema(self):
        """tests/fixtures/technical/BTC_ohlc.json: 721 velas reales de
        Kraken, sin huecos -- historical_series() debe devolver una fila
        por vela, con las mismas claves para todas las fechas (algunas
        con valor None hasta acumular suficiente ventana, nunca una clave
        ausente)."""
        path = os.path.join(ROOT, "engine", "technical", "_data", "BTC_ohlc.json")
        out = self.mod.historical_series("BTC", path)
        self.assertEqual(len(out), 721)
        self.assertEqual(out[0]["fecha_dato"], "2024-07-30")
        self.assertEqual(out[-1]["fecha_dato"], "2026-07-20")
        claves_esperadas = {
            "fecha_dato", "precio", "volumen", "sma20", "sma50", "sma100", "sma200",
            "rsi14", "atr14", "atr14_pct_precio", "volatilidad_hist_30d_anualizada_pct",
        }
        for r in out:
            self.assertEqual(claves_esperadas, set(r.keys()))
        # con 721 velas hay de sobra para sma200 en las ultimas filas
        self.assertIsNotNone(out[-1]["sma200"])
        # las primeras 199 no pueden tenerlo (ventana insuficiente, honesto)
        self.assertIsNone(out[0]["sma200"])

    def test_historical_series_respeta_huecos_no_mezcla_ventanas(self):
        """2026-09-04: un hueco real en la serie (encontrado en el
        backfill real de XRP -- Coinbase deslisto XRP en EEUU entre
        2021-01 y 2023-07 por el litigio con la SEC, ~905 dias) no debe
        producir una SMA/RSI/ATR que mezcle precios de antes y despues
        del hueco. Fixture sintetica: 25 velas seguidas, hueco de 5 dias,
        25 velas mas a un nivel de precio totalmente distinto -- si el
        codigo mezclara ventanas, sma20 en la primera vela del segundo
        tramo no seria None (tendria de sobra con las 19 ultimas del
        primer tramo)."""
        base = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        rows = []
        for i in range(25):
            t = int((base + datetime.timedelta(days=i)).timestamp())
            c = 100.0 + i
            rows.append([t, c, c, c, c, 0, 1.0, 0])
        gap_start = base + datetime.timedelta(days=25 + 5)  # 5 dias de hueco
        for i in range(25):
            t = int((gap_start + datetime.timedelta(days=i)).timestamp())
            c = 100000.0 + i  # nivel de precio totalmente distinto, no confundible
            rows.append([t, c, c, c, c, 0, 1.0, 0])

        tmp_path = os.path.join(tempfile.gettempdir(), "test_gap_ohlc.json")
        with open(tmp_path, "w") as f:
            json.dump(rows, f)
        try:
            segments = self.mod._split_contiguous(self.mod._load_ohlc("GAP", path=tmp_path))
            self.assertEqual([len(s) for s in segments], [25, 25])

            out = self.mod.historical_series("GAP", tmp_path)
            self.assertEqual(len(out), 50)
            primera_del_segundo_tramo = out[25]
            self.assertIsNone(primera_del_segundo_tramo["sma20"],
                               "el segundo tramo debe empezar su propia ventana, no heredar la del primero")
            self.assertEqual(primera_del_segundo_tramo["precio"], 100000.0)

            ultima = out[-1]  # vela #20 (indice 19) del segundo tramo -> sma20 ya valida
            self.assertIsNotNone(ultima["sma20"])
            # media de las 20 ultimas del SEGUNDO tramo unicamente (100005..100024)
            self.assertAlmostEqual(ultima["sma20"], sum(range(100005, 100025)) / 20, places=3)
        finally:
            os.remove(tmp_path)

    def test_historical_volatility_series_misma_formula_que_historical_volatility(self):
        ind = _import("technical", "indicators")
        closes = [100.0 + (i % 7) * 3.1 for i in range(80)]  # serie no trivial, deterministica
        serie = ind.historical_volatility_series(closes, 30)
        self.assertEqual(len(serie), len(closes))
        for i in range(len(closes)):
            esperado = ind.historical_volatility(closes[:i + 1], 30)
            self.assertEqual(serie[i], esperado)

    def _write_ohlc(self, dates_closes):
        """dates_closes: lista de (date, close) -- vela plana (open=high=low=close),
        volumen fijo. Devuelve la ruta del fichero temporal (forma cruda Kraken)."""
        rows = [[int(datetime.datetime.combine(d, datetime.time(), tzinfo=datetime.timezone.utc).timestamp()),
                 c, c, c, c, 0, 1.0, 0] for d, c in dates_closes]
        path = os.path.join(tempfile.gettempdir(), "test_calendar_ohlc.json")
        with open(path, "w") as f:
            json.dump(rows, f)
        return path

    def test_equity_viernes_a_lunes_no_rompe_el_tramo(self):
        """Bloque 4 (2026-09-04): _split_contiguous(asset_type='equity')
        no debe tratar un fin de semana normal como hueco."""
        d = datetime.date
        # 2026-07-10 (viernes) -> 2026-07-13 (lunes), sin festivo de por medio
        fechas = [d(2026, 7, 10), d(2026, 7, 13), d(2026, 7, 14)]
        path = self._write_ohlc([(f, 100.0 + i) for i, f in enumerate(fechas)])
        ohlc = self.mod._load_ohlc("TEST", path)
        segmentos = self.mod._split_contiguous(ohlc, asset_type="equity")
        self.assertEqual(len(segmentos), 1, "viernes->lunes no debe romper el tramo para acciones")
        self.assertEqual(len(segmentos[0]), 3)

    def test_equity_festivo_bursatil_no_rompe_el_tramo(self):
        """2026-07-03 es el 4 de julio observado (cae en sábado, NYSE lo
        observa el viernes anterior) -- jueves 07-02 -> lunes 07-06 no
        debe romper el tramo (festivo + fin de semana, cero sesiones
        esperadas de por medio)."""
        d = datetime.date
        fechas = [d(2026, 7, 1), d(2026, 7, 2), d(2026, 7, 6), d(2026, 7, 7)]
        path = self._write_ohlc([(f, 100.0 + i) for i, f in enumerate(fechas)])
        ohlc = self.mod._load_ohlc("TEST", path)
        segmentos = self.mod._split_contiguous(ohlc, asset_type="equity")
        self.assertEqual(len(segmentos), 1, "festivo bursátil (4 de julio observado) no debe romper el tramo")
        self.assertEqual(len(segmentos[0]), 4)

    def test_equity_sesion_realmente_ausente_rompe_el_tramo(self):
        """Mismo rango que el test anterior, pero quitando 2026-07-08
        (miércoles, sesión normal sin motivo de ausencia) -- eso SÍ debe
        detectarse como hueco real, no ocultarse."""
        d = datetime.date
        fechas = [d(2026, 7, 6), d(2026, 7, 7), d(2026, 7, 9), d(2026, 7, 10)]  # falta el 07-08
        path = self._write_ohlc([(f, 100.0 + i) for i, f in enumerate(fechas)])
        ohlc = self.mod._load_ohlc("TEST", path)
        segmentos = self.mod._split_contiguous(ohlc, asset_type="equity")
        self.assertEqual(len(segmentos), 2, "una sesión de trading realmente ausente debe partir el tramo")
        self.assertEqual([len(s) for s in segmentos], [2, 2])

    def test_crypto_mantiene_su_comportamiento_actual_con_fin_de_semana(self):
        """Diferencia clave con equity: para cripto, un fin de semana
        SÍ es un hueco real (cotiza 24/7) -- asset_type='crypto' (por
        defecto) no debe adoptar la tolerancia de calendario bursátil."""
        d = datetime.date
        fechas = [d(2026, 7, 10), d(2026, 7, 13)]  # viernes -> lunes, faltan sábado y domingo
        path = self._write_ohlc([(f, 100.0 + i) for i, f in enumerate(fechas)])
        ohlc = self.mod._load_ohlc("TEST", path)
        segmentos = self.mod._split_contiguous(ohlc)  # asset_type por defecto
        self.assertEqual(len(segmentos), 2, "para cripto, sábado/domingo ausentes siguen siendo un hueco real")

    def test_indicadores_cripto_sin_cambios_tras_anadir_asset_type(self):
        """Regresión explícita: historical_series() sobre la fixture real
        de BTC (721 velas, sin huecos) debe dar EXACTAMENTE los mismos
        resultados con o sin pasar asset_type -- el parámetro nuevo no
        debe alterar el comportamiento por defecto de cripto."""
        path = os.path.join(ROOT, "engine", "technical", "_data", "BTC_ohlc.json")
        con_defecto = self.mod.historical_series("BTC", path)
        explicito = self.mod.historical_series("BTC", path, asset_type="crypto")
        self.assertEqual(con_defecto, explicito)
        self.assertEqual(len(con_defecto), 721)

    def test_equity_split_no_produce_caida_artificial(self):
        """Bloque 4 (2026-09-04): datos REALES de Yahoo Finance para NVDA
        alrededor de su split 10:1 del 2024-06-10 (jueves 06-06/viernes
        06-07 antes, lunes 06-10 despues -- fin de semana entre medio).
        Verificado en vivo que Yahoo ya devuelve 'close' ajustado
        retroactivamente por el split -- esta prueba fija esos valores
        reales como regresion: si algun dia el codigo empezara a usar el
        precio sin ajustar (o 'adjclose', que ademas mezcla dividendos),
        esta prueba detectaria la discontinuidad."""
        rows = [
            [1717594200, 118.37100219726562, 122.4489974975586, 117.46800231933594, 122.44000244140625, 0, 528402000, 0],
            [1717680600, 124.0479965209961, 125.58699798583984, 118.31999969482422, 120.99800109863281, 0, 664696000, 0],
            [1717767000, 119.7699966430664, 121.69200134277344, 118.02200317382812, 120.88800048828125, 0, 412386000, 0],
            [1718026200, 120.37000274658203, 123.0999984741211, 117.01000213623047, 121.79000091552734, 0, 313434100, 0],
            [1718112600, 121.7699966430664, 122.87000274658203, 118.73999786376953, 120.91000366210938, 0, 222551200, 0],
            [1718199000, 123.05999755859375, 126.87999725341797, 122.56999969482422, 125.19999694824219, 0, 299595000, 0],
        ]
        path = os.path.join(tempfile.gettempdir(), "test_nvda_split.json")
        with open(path, "w") as f:
            json.dump(rows, f)
        try:
            ohlc = self.mod._load_ohlc("NVDA", path)
            segmentos = self.mod._split_contiguous(ohlc, asset_type="equity")
            self.assertEqual(len(segmentos), 1, "viernes 06-07 -> lunes 06-10 (dia del split) no debe romper el tramo")

            out = self.mod.historical_series("NVDA", path, asset_type="equity")
            self.assertEqual(len(out), 6)
            precios = [r["precio"] for r in out]
            for i in range(1, len(precios)):
                variacion_pct = abs(precios[i] - precios[i - 1]) / precios[i - 1] * 100
                self.assertLess(variacion_pct, 15,
                                 f"variacion diaria de {variacion_pct:.1f}% en {out[i]['fecha_dato']} -- "
                                 "un split sin ajustar produciria aqui una caida de ~90%")
            # el precio del dia del split (2024-06-10) es del mismo orden de magnitud que el dia anterior
            fecha_a_precio = {r["fecha_dato"]: r["precio"] for r in out}
            self.assertAlmostEqual(fecha_a_precio["2024-06-10"], fecha_a_precio["2024-06-07"], delta=10)
        finally:
            os.remove(path)


class TestTradingCalendar(unittest.TestCase):
    """engine/technical/trading_calendar.py -- pruebas unitarias
    directas sobre el calculo de festivos NYSE y sesiones esperadas,
    sin pasar por score.py."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _import("technical", "trading_calendar")

    def test_festivos_nyse_2026_conocidos(self):
        """Festivos verificados a mano contra el calendario NYSE real de
        2026: Ano Nuevo, MLK, Presidents Day, Viernes Santo (Pascua
        2026 = 5 de abril), Memorial Day, Juneteenth, 4 de julio
        (observado el viernes 3, cae en sabado), Labor Day, Accion de
        Gracias, Navidad -- 10 festivos, ninguno inventado."""
        d = datetime.date
        esperados = {
            d(2026, 1, 1), d(2026, 1, 19), d(2026, 2, 16), d(2026, 4, 3),
            d(2026, 5, 25), d(2026, 6, 19), d(2026, 7, 3), d(2026, 9, 7),
            d(2026, 11, 26), d(2026, 12, 25),
        }
        self.assertEqual(self.mod.us_market_holidays(2026), esperados)

    def test_juneteenth_no_es_festivo_antes_de_2022(self):
        self.assertNotIn(datetime.date(2021, 6, 18), self.mod.us_market_holidays(2021))

    def test_viernes_a_lunes_normal_cero_sesiones_esperadas(self):
        self.assertEqual(
            self.mod.sessions_skipped_between(datetime.date(2026, 7, 10), datetime.date(2026, 7, 13), "equity"), 0)

    def test_festivo_mas_fin_de_semana_cero_sesiones_esperadas(self):
        """4 de julio 2026 observado el viernes 3 -- jueves 07-02 a
        lunes 07-06 no debe contar ninguna sesion esperada de por
        medio."""
        self.assertEqual(
            self.mod.sessions_skipped_between(datetime.date(2026, 7, 2), datetime.date(2026, 7, 6), "equity"), 0)

    def test_sesion_normal_ausente_cuenta_como_hueco(self):
        self.assertEqual(
            self.mod.sessions_skipped_between(datetime.date(2026, 7, 6), datetime.date(2026, 7, 8), "equity"), 1)

    def test_cripto_cualquier_dia_ausente_cuenta_como_hueco(self):
        """Para cripto (24/7), un fin de semana SI cuenta como sesion
        esperada ausente -- no hay tolerancia de calendario bursatil."""
        self.assertEqual(
            self.mod.sessions_skipped_between(datetime.date(2026, 7, 3), datetime.date(2026, 7, 4), "crypto"), 0)
        self.assertEqual(
            self.mod.sessions_skipped_between(datetime.date(2026, 7, 3), datetime.date(2026, 7, 5), "crypto"), 1)


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
