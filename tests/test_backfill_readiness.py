"""Preparacion para ampliar la poblacion historica (2026-09-08).

La invariante que ordena el fichero: una cobertura alta NO es suficiente si
lo que falta son justamente los activos que dejaron de cotizar. El sistema
no debe deducir semantica por ausencia de una excepcion.
"""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("contract", "events", "knowledge", "technical"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", sub))

import autoridad as au      # noqa: E402
import readiness as rd      # noqa: E402
import universo as uni      # noqa: E402


class TestMatriz(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cols, cls.mat = rd.matriz()

    def test_cubre_el_universo_congelado_entero(self):
        self.assertEqual(set(self.mat), set(uni.simbolos()))
        self.assertEqual(len(self.mat), 31)

    def test_solo_los_cuatro_estados(self):
        for s, fila in self.mat.items():
            for c in self.cols:
                self.assertIn(fila[c], rd.ESTADOS, f"{s}/{c}")
        self.assertEqual(set(rd.ESTADOS), set(au.ESTADOS))

    def test_los_deslistados_siguen_en_la_matriz(self):
        """No se caen del universo por no tener precio (D-36)."""
        for s in ("DWDP", "UTX", "WBA"):
            self.assertIn(s, self.mat)
            self.assertEqual(self.mat[s]["historical_identity"], rd.AVAILABLE, s)
            self.assertEqual(self.mat[s]["SEC_event"], rd.AVAILABLE, s)
            self.assertEqual(self.mat[s]["price"], rd.UNAVAILABLE, s)

    def test_wba_aparecio_en_la_medicion_no_en_el_diseno(self):
        """No se eligio como caso: el barrido lo encontro ausente del
        directorio de tickers, igual que DWDP y UTX."""
        med = rd.declaracion()["medicion_por_activo"]["WBA"]
        self.assertFalse(med["en_directorio_actual"])
        self.assertIn("full-text", med["cik_origen"])
        self.assertGreater(med["n_filings"], 0)

    def test_alpha_vantage_no_decide_que_activos_existen(self):
        """Su cobertura es 22,6% y aun asi los 31 tienen identidad."""
        cob = rd.cobertura()
        self.assertLess(cob["AV_enrichment"]["coverage_rate"], 0.5)
        self.assertEqual(cob["historical_identity"]["coverage_rate"], 1.0)


class TestCobertura(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cob = rd.cobertura()

    def test_los_conteos_suman_el_universo(self):
        for c, v in self.cob.items():
            self.assertEqual(v["n_available"] + v["n_unavailable"]
                             + v["n_not_measured"] + v["n_ambiguous"], 31, c)

    def test_entidad_evento_resultado_y_benchmark_estan_completos(self):
        for c in ("historical_identity", "SEC_event", "actual_financials",
                  "successor_mapping", "benchmark"):
            self.assertEqual(self.cob[c]["coverage_rate"], 1.0, c)

    def test_el_ticker_historico_no_tiene_ninguna_fuente_determinista(self):
        """0% AVAILABLE y 31 AMBIGUOUS: es el cuello de botella real."""
        self.assertEqual(self.cob["historical_ticker"]["coverage_rate"], 0.0)
        self.assertEqual(self.cob["historical_ticker"]["n_ambiguous"], 31)

    def test_not_measured_no_se_confunde_con_unavailable(self):
        """AV: 22 no medidos y 2 medidos-y-ausentes. Son cosas distintas."""
        av = self.cob["AV_enrichment"]
        self.assertEqual(av["n_not_measured"], 22)
        self.assertEqual(av["n_unavailable"], 2)


class TestFormaDeLasAusencias(unittest.TestCase):
    """El test que impide leer un 90% como 'casi completo'."""

    def test_las_ausencias_de_precio_son_exactamente_los_deslistados(self):
        s = rd.ausencias_con_forma_de_superviviencia()
        self.assertEqual(s["fuera_del_directorio_actual"], s["sin_precio"])
        self.assertTrue(s["coinciden"])
        self.assertEqual(s["sin_precio"], ["DWDP", "UTX", "WBA"])

    def test_esa_coincidencia_bloquea_el_backfill_por_si_sola(self):
        r = rd.backfill_ready()
        self.assertFalse(r["BACKFILL_READY"])
        self.assertTrue(any("superviviente" in x for x in r["razones"]))


class TestReadiness(unittest.TestCase):

    def test_no_esta_listo_y_las_razones_estan_escritas(self):
        r = rd.backfill_ready()
        self.assertFalse(r["BACKFILL_READY"])
        self.assertGreaterEqual(len(r["razones"]), 3)

    def test_no_se_decide_con_un_porcentaje_global(self):
        """El universo minimo efectivo es 28 de 31 -- alto -- y aun asi no
        esta listo. Si la decision fuese un porcentaje, saldria que si."""
        r = rd.backfill_ready()
        self.assertEqual(r["universo_minimo_efectivo"], 28)
        self.assertGreater(r["universo_minimo_efectivo"] / r["n_universo"], 0.9)
        self.assertFalse(r["BACKFILL_READY"])

    def test_la_expectativa_no_es_bloqueante(self):
        """D-38: su ausencia no elimina el evento."""
        self.assertNotIn("expectation", rd.COMPONENTES_BLOQUEANTES)
        self.assertNotIn("AV_enrichment", rd.COMPONENTES_BLOQUEANTES)
        r = rd.backfill_ready()
        self.assertFalse(any("expectation" in x for x in r["razones"]))

    def test_el_cuello_de_botella_es_la_identidad_del_instrumento(self):
        cb = {x["componente"] for x in rd.cuello_de_botella()}
        self.assertIn("historical_ticker", cb)
        self.assertIn("corporate_actions", cb)
        for c in ("historical_identity", "SEC_event", "actual_financials", "benchmark"):
            self.assertNotIn(c, cb, c)


if __name__ == "__main__":
    unittest.main(verbosity=2)
