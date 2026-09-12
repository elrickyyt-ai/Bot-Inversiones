"""Primer benchmark real declarado: S&P 500 -- D-21 (2026-09-07).

Los diez tests que el usuario fijo como criterio de aceptacion, sobre la
declaracion real en `knowledge/` y la serie real en `data/benchmarks/`.
"""
import datetime
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("knowledge", "contract", "events", "technical", "causal"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", sub))

import modelo                     # noqa: E402
import fetch_benchmark            # noqa: E402
import estudio_resultados as er   # noqa: E402
import caminos                    # noqa: E402

FIXTURES = os.path.join(RAIZ, "tests", "fixtures", "eventos_resultados")
SIMBOLOS = ("IBM", "NVDA", "XOM")


from _parquet import requiere_parquet  # noqa: E402


def _path(sym):
    return os.path.join(FIXTURES, f"{sym}_earnings.json")


class TestElBenchmarkDeclarado(unittest.TestCase):
    """Tests 1 y 5."""

    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()
        cls.bm = next(e for e in cls.k["entities"] if e["entity_id"] == "bm:sp500")

    def test_bm_sp500_es_un_benchmark_valido(self):
        self.assertEqual(modelo.validar(self.k), [])
        self.assertEqual(self.bm["type"], "benchmark")
        b = self.bm["benchmark"]
        self.assertEqual(b["composition_source"], "PUBLISHED_LEVEL")
        self.assertTrue(b["point_in_time_capable"])
        self.assertEqual(b["calendar"], "equity")
        self.assertEqual(b["serie_desde"], "1970-01-02")
        self.assertTrue(b["methodology_version"])

    def test_no_es_un_activo_y_no_esta_en_dimasset(self):
        """La razon de ser de D-21: una referencia de mercado no se
        convierte en instrumento analizado por conveniencia."""
        self.assertIsNone(self.bm["asset_id"])
        self.assertFalse(os.path.exists(os.path.join(RAIZ, "data", "assets", "SP500.json")))
        self.assertFalse(os.path.isdir(os.path.join(RAIZ, "data", "history", "benchmark")))
        self.assertFalse(os.path.exists(os.path.join(RAIZ, "data", "incoming", "SP500_2026.csv")))

    def test_se_usa_el_nivel_publicado_y_no_un_etf(self):
        """Un ETF meteria comision, tracking error y acciones corporativas
        propias dentro del benchmark metodologico."""
        self.assertEqual(self.bm["benchmark"]["composition_source"], "PUBLISHED_LEVEL")
        # el alias apunta al INDICE, no a un ETF que lo replique
        tickers = {a["value"] for a in self.bm["aliases"]}
        self.assertEqual(tickers, {"^GSPC"})
        self.assertNotIn("SPY", tickers)
        # y la serie almacenada viene de ese ticker
        filas = fetch_benchmark.leer("SP500")
        self.assertEqual({f["source"] for f in filas}, {"Yahoo Finance"})

    def test_la_asignacion_tiene_vigencia(self):
        for r in self.k["relationships"]:
            if r.get("predicate") == "BENCHMARKED_BY":
                self.assertTrue(r["valid_from"])
                self.assertIn("valid_to", r)
                self.assertTrue(r["source_id"])
                self.assertTrue(r["verification_method"])

    def test_la_vigencia_la_fija_el_activo_no_el_benchmark(self):
        """NVDA cotiza desde 1999-01-22 y el S&P 500 desde 1970: la
        asignacion no puede empezar antes de que exista el activo."""
        por_sujeto = {r["subject"]: r for r in self.k["relationships"]
                      if r.get("predicate") == "BENCHMARKED_BY"}
        self.assertEqual(por_sujeto["sec:NVDA.NASDAQ"]["valid_from"], "1999-01-22")
        self.assertEqual(por_sujeto["sec:IBM.NYSE"]["valid_from"], "1970-01-02")
        for r in por_sujeto.values():
            self.assertGreaterEqual(r["valid_from"], self.bm["benchmark"]["serie_desde"])


class TestSerieDelBenchmark(unittest.TestCase):

    def test_la_serie_almacenada_es_valida(self):
        self.assertEqual(fetch_benchmark.validar_serie("SP500"), [])

    def test_cubre_el_periodo_declarado(self):
        fechas, _ = fetch_benchmark.serie("SP500")
        k = modelo.cargar()
        bm = next(e for e in k["entities"] if e["entity_id"] == "bm:sp500")
        self.assertEqual(fechas[0], bm["benchmark"]["serie_desde"])
        self.assertGreater(len(fechas), 14000)

    def test_no_tiene_sesiones_en_fin_de_semana(self):
        """Calendario `equity`, y por eso no puede medir un cripto."""
        fechas, _ = fetch_benchmark.serie("SP500")
        fds = [f for f in fechas if datetime.date.fromisoformat(f).weekday() >= 5]
        self.assertEqual(fds, [])


class TestAsignacionYElegibilidad(unittest.TestCase):
    """Tests 2, 3 y 4."""

    def test_las_tres_acciones_se_asignan_mediante_knowledge(self):
        for sym in SIMBOLOS:
            asig, ent = er.asignacion_de(sym)
            self.assertIsNotNone(asig, sym)
            self.assertEqual(ent["entity_id"], "bm:sp500")
            self.assertEqual(asig["role"], "MARKET")
            self.assertEqual(asig["predicate"], "BENCHMARKED_BY")

    def test_benchmarked_by_habilita_abnormal_return(self):
        for sym in SIMBOLOS:
            asig, ent = er.asignacion_de(sym)
            ok, motivo = er.benchmark_elegible("2024-01-25", "equity", asig, ent)
            self.assertTrue(ok, f"{sym}: {motivo}")

    def test_el_calculo_comprueba_pero_no_elige(self):
        """`asignacion_de` BUSCA la declarada; si hubiera dos vigentes,
        levanta en vez de quedarse con una."""
        import inspect
        fuente = inspect.getsource(er.asignacion_de)
        self.assertIn("EstudioError", fuente)
        for prohibido in ("max(", "min(", "sorted(candidatas", "best", "mejor"):
            self.assertNotIn(prohibido, fuente)

    def test_ningun_activo_cripto_tiene_asignacion(self):
        for sym in ("BTC", "ETH", "XRP"):
            asig, ent = er.asignacion_de(sym)
            self.assertIsNone(asig, sym)
            self.assertIsNone(ent, sym)

    # --- 6 ---
    def test_no_hay_solapamiento_de_asignaciones(self):
        k = modelo.cargar()
        por_clave = {}
        for r in k["relationships"]:
            if r.get("predicate") == "BENCHMARKED_BY":
                por_clave.setdefault((r["subject"], r["role"]), []).append(r)
        for rels in por_clave.values():
            self.assertEqual(len(rels), 1)
        self.assertEqual(modelo.validar(k), [])

    # --- 9 ---
    def test_calendario_incompatible_falla(self):
        """El S&P 500 no puede medir un cripto: 28,5% de las sesiones de
        BTC caen en dias sin mercado bursatil."""
        asig, ent = er.asignacion_de("IBM")
        ok, motivo = er.benchmark_elegible("2024-01-25", "crypto", asig, ent)
        self.assertFalse(ok)
        self.assertEqual(motivo, er.CALENDARIO_INCOMPATIBLE)


@requiere_parquet
class TestEventStudyConBenchmark(unittest.TestCase):
    """Tests 7 y 8, y la comprobacion de que no hay look-ahead."""

    @classmethod
    def setUpClass(cls):
        cls.con = {s: er.estudiar(s, _path(s)) for s in SIMBOLOS}
        cls.sin = {s: er.estudiar(s, _path(s), con_benchmark=False) for s in SIMBOLOS}
        cls.todas_con = [o for v in cls.con.values() for o in v]
        cls.todas_sin = [o for v in cls.sin.values() for o in v]

    # --- 7 ---
    def test_el_raw_return_no_cambia_con_ni_sin_benchmark(self):
        """El benchmark aporta una medida nueva; no altera la que habia."""
        for sym in SIMBOLOS:
            for a, b in zip(self.con[sym], self.sin[sym]):
                self.assertEqual(a["raw_return_1s_pct"], b["raw_return_1s_pct"])
                self.assertEqual(a["first_tradable_at"], b["first_tradable_at"])

    def test_sin_benchmark_el_raw_sigue_calculandose(self):
        medibles = [o for o in self.todas_sin if o["raw_return_1s_pct"] is not None]
        self.assertEqual(len(medibles), 52)
        self.assertTrue(all(o["market_adjusted_return_pct"] is None for o in self.todas_sin))

    # --- 8 ---
    def test_el_abnormal_return_usa_el_benchmark_declarado(self):
        con_ajuste = [o for o in self.todas_con if o["market_adjusted_return_pct"] is not None]
        self.assertEqual(len(con_ajuste), 52)
        for o in con_ajuste:
            self.assertEqual(o["benchmark_id"], "bm:sp500")
            self.assertEqual(o["metodo_ajuste"], er.DIFERENCIA_SIMPLE)
            self.assertEqual(o["benchmark_methodology_version"], "yahoo-^GSPC-close-1d/v1")
            self.assertIsNone(o["razon_sin_ajuste"])

    def test_el_ajuste_es_exactamente_la_diferencia(self):
        for o in self.todas_con:
            if o["market_adjusted_return_pct"] is None:
                continue
            esperado = o["raw_return_1s_pct"] - o["benchmark_return_1s_pct"]
            self.assertAlmostEqual(o["market_adjusted_return_pct"], esperado, places=1)

    def test_bruto_y_anormal_se_conservan_por_separado(self):
        for o in self.todas_con:
            self.assertIn("raw_return_1s_pct", o)
            self.assertIn("market_adjusted_return_pct", o)
            self.assertIn("benchmark_return_1s_pct", o)

    def test_sin_look_ahead_el_benchmark_se_mide_en_las_mismas_sesiones(self):
        """La condicion que hace valido todo lo demas: el retorno del
        benchmark se mide entre la sesion PREVIA y la primera negociable,
        las mismas dos del activo. Ninguna es posterior."""
        _bf, bpx = fetch_benchmark.serie("SP500")
        for o in self.todas_con:
            if o["market_adjusted_return_pct"] is None:
                continue
            self.assertLess(o["sesion_previa"], o["first_tradable_at"])
            self.assertGreaterEqual(o["first_tradable_at"], o["available_at"])
            self.assertIn(o["sesion_previa"], bpx)
            self.assertIn(o["first_tradable_at"], bpx)
            b0, b1 = bpx[o["sesion_previa"]], bpx[o["first_tradable_at"]]
            self.assertAlmostEqual(o["benchmark_return_1s_pct"],
                                   (b1 - b0) / b0 * 100, places=1)

    def test_el_ajuste_cambia_el_signo_en_algunos_casos(self):
        """La razon de ser del benchmark: hay eventos cuyo retorno bruto
        es positivo y cuyo retorno anormal es negativo."""
        flips = [o for o in self.todas_con
                 if o["market_adjusted_return_pct"] is not None
                 and o["raw_return_1s_pct"] * o["market_adjusted_return_pct"] < 0]
        self.assertGreaterEqual(len(flips), 3)

    def test_abnormal_return_pasa_a_ser_elegible(self):
        calculadas = {"RAW_RETURN", "ABNORMAL_RETURN"}
        ok, informe = er.elegibilidad(self.todas_con, "ABNORMAL_RETURN",
                                      medidas_disponibles=calculadas)
        self.assertTrue(ok)
        self.assertEqual(informe["motivo"], "SUFICIENTE")
        self.assertGreaterEqual(informe["sin_solapamiento"],
                                informe["minimo_declarado"])

    def test_no_se_ha_calculado_ningun_perfil_historico(self):
        """El encargo se detiene antes del HistoricalReactionProfile."""
        for o in self.todas_con:
            for prohibido in ("mediana", "median", "profile", "percentil", "reaction_gap"):
                self.assertNotIn(prohibido, o)


class TestNoEntraEnElGrafoCausal(unittest.TestCase):
    """Test 10, ahora con un benchmark REAL declarado."""

    def test_el_benchmark_declarado_no_es_un_nodo_causal(self):
        k = modelo.cargar()
        salidas, _neg = caminos.indice(k, datetime.date(2026, 9, 7))
        self.assertNotIn("bm:sp500", salidas)
        for vecinos in salidas.values():
            self.assertNotIn("bm:sp500", [v[0] for v in vecinos])

    def test_las_tres_asignaciones_no_anaden_aristas(self):
        k = modelo.cargar()
        sin_asig = dict(k)
        sin_asig["relationships"] = [r for r in k["relationships"]
                                     if r.get("predicate") != "BENCHMARKED_BY"]
        con, _ = caminos.indice(k, datetime.date(2026, 9, 7))
        sin, _ = caminos.indice(sin_asig, datetime.date(2026, 9, 7))
        self.assertEqual(sorted(con), sorted(sin))


if __name__ == "__main__":
    unittest.main()
