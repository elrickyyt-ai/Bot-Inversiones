"""Diagnostico de dependencia y solapamiento -- D-27/D-29/D-30 (2026-09-07).

La propiedad que ordena estos tests: el diagnostico **mide** si una cohorte
es interpretable; no la arregla ni la reduce. Por eso ninguna funcion de
aqui elimina observaciones, y por eso `n_effective` todavia no existe.
"""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("contract", "events", "knowledge", "technical"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", sub))

import diagnostico_cohorte as dc   # noqa: E402
import estudio_resultados as er    # noqa: E402
import perfil_reaccion as pr       # noqa: E402

HOY = "2026-09-07"


class TestCohorteReal(unittest.TestCase):
    """Sobre los 52 eventos reales de IBM/NVDA/XOM."""

    @classmethod
    def setUpClass(cls):
        cls.obs = pr.observaciones_v1()
        cls.series = {s: er.series_del_activo(s) for s in pr.SIMBOLOS_V1}

    def test_el_cuello_de_botella_es_el_numero_de_activos_no_el_de_eventos(self):
        """52 eventos de 3 tickers no son 52 unidades independientes."""
        d = dc.dependencia(self.obs)
        self.assertEqual(d["n_observations"], 52)
        self.assertEqual(d["n_assets"], 3)
        self.assertEqual(d["n_independent_assets"], 3)
        self.assertEqual(d["independence_status"], "LOW")

    def test_un_evento_programado_no_tiene_episodio(self):
        """D-28: NOT_APPLICABLE, no 0 ni UNKNOWN."""
        d = dc.dependencia(self.obs)
        self.assertEqual(d["n_episodes"], pr.NO_APLICA)
        self.assertEqual(d["events_per_episode"], pr.NO_APLICA)

    def test_se_clusteriza_por_activo_y_la_razon_esta_escrita(self):
        d = dc.dependencia(self.obs)
        self.assertEqual(d["cluster_recomendado"], "asset")
        self.assertIn("episodio", d["razon_cluster"])

    def test_la_ventana_de_estimacion_esta_disponible_y_limpia(self):
        """[-20,-1] existe para los 52 y ningun otro evento cae dentro."""
        v = dc.ventana_estimacion_diagnostico(self.obs, self.series)
        self.assertEqual(v["largo"], 20)
        self.assertEqual(v["con_ventana_completa"], 52)
        self.assertEqual(v["sin_ventana_completa"], 0)
        self.assertEqual(v["contaminadas_por_otro_evento"], 0)
        self.assertEqual(v["con_huecos_de_volumen"], 0)

    def test_el_solapamiento_solo_aparece_en_el_horizonte_largo(self):
        tasas = {h: dc.solapamiento(self.obs, h) for h in pr.HORIZONTES}
        for h in ("0_1d", "2_5d", "2_20d"):
            self.assertEqual(tasas[h]["overlap_event_count"], 0, h)
        self.assertEqual(tasas["2_60d"]["overlap_event_count"], 3)
        self.assertGreater(tasas["2_60d"]["overlap_rate"], 0)

    def test_la_contaminacion_estructural_no_es_el_solapamiento(self):
        """2_20d no solapa con nadie y aun asi ocupa un tercio del trimestre."""
        c20 = dc.contaminacion_estructural(self.obs, self.series, "2_20d")
        c60 = dc.contaminacion_estructural(self.obs, self.series, "2_60d")
        self.assertEqual(dc.solapamiento(self.obs, "2_20d")["overlap_event_count"], 0)
        self.assertGreater(c20["cobertura_del_intervalo"], 0.2)
        # 60 sesiones cubren casi todo el intervalo entre resultados.
        self.assertGreater(c60["cobertura_del_intervalo"], 0.9)
        self.assertLess(c60["cobertura_del_intervalo"], 1.0)

    def test_el_intervalo_se_mide_en_sesiones_no_en_dias(self):
        """Un trimestre son ~63 sesiones, no ~91 dias: es la unidad del horizonte."""
        c = dc.contaminacion_estructural(self.obs, self.series, "2_60d")
        self.assertGreater(c["intervalo_mediano_entre_eventos"], 55)
        self.assertLess(c["intervalo_mediano_entre_eventos"], 70)

    def test_comparar_muestras_no_elimina_nada_de_forma_permanente(self):
        """D-30: la muestra limpia se publica AL LADO de la completa."""
        c = dc.comparar_muestras(self.obs, "ABNORMAL_RETURN", "2_60d", HOY)
        self.assertTrue(c["comparable"])
        self.assertGreater(c["n_full"], c["n_limpia"])
        p = pr.perfil(self.obs, "earnings_release", "ABNORMAL_RETURN", "2_60d", HOY)
        self.assertEqual(p["n_observations"], c["n_full"])
        self.assertIsNotNone(p["statistics"])
        self.assertIsNotNone(p["statistics_non_overlapping"])

    def test_sin_eventos_solapados_la_comparacion_dice_que_no_es_comparable(self):
        """No inventa una muestra limpia identica a la completa."""
        c = dc.comparar_muestras(self.obs, "RAW_RETURN", "2_20d", HOY)
        self.assertFalse(c["comparable"])
        self.assertIn("solapado", c["motivo"])


class TestNoSeHaDefinidoNEffective(unittest.TestCase):
    """El usuario pidio MEDIR la dependencia antes de formularla."""

    def test_el_modulo_no_publica_ninguna_formula_de_n_effective(self):
        self.assertFalse([n for n in dir(dc) if "effective" in n.lower()])
        src = open(os.path.join(RAIZ, "engine", "events", "diagnostico_cohorte.py"),
                   encoding="utf-8").read()
        self.assertIn("NO define `n_effective`", src)

    def test_el_estado_de_independencia_tiene_tres_valores_declarados(self):
        self.assertGreater(dc.MIN_ACTIVOS_ALTO, dc.MIN_ACTIVOS_MEDIO)
        base = pr.observaciones_v1()[:1]

        def con_activos(n):
            return [dict(base[0], asset_id=f"A{i}") for i in range(n)]

        self.assertEqual(dc.dependencia(con_activos(dc.MIN_ACTIVOS_ALTO))
                         ["independence_status"], "HIGH")
        self.assertEqual(dc.dependencia(con_activos(dc.MIN_ACTIVOS_MEDIO))
                         ["independence_status"], "MEDIUM")
        self.assertEqual(dc.dependencia(con_activos(dc.MIN_ACTIVOS_MEDIO - 1))
                         ["independence_status"], "LOW")


class TestInformeCompleto(unittest.TestCase):

    def test_el_informe_cubre_los_cuatro_horizontes(self):
        d = dc.informe(HOY)
        self.assertEqual(len(d["solapamiento"]), len(pr.HORIZONTES))
        self.assertEqual(len(d["contaminacion"]), len(pr.HORIZONTES))
        self.assertEqual(d["as_of"], HOY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
