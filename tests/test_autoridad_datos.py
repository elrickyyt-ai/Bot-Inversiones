"""Autoridad de dato por componente (2026-09-08).

Una sola invariante ordena todo el fichero, y es la que debe sobrevivir a
este backfill: LA COBERTURA DE UN PROVEEDOR NO DEFINE QUIEN EXISTIO EN
NUESTRO PASADO.
"""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("contract", "events", "knowledge", "technical"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", sub))

import autoridad as au        # noqa: E402
import universo as uni        # noqa: E402
import perfil_reaccion as pr  # noqa: E402


class TestReglaFundacional(unittest.TestCase):

    def test_la_ausencia_en_un_enriquecedor_no_niega_la_existencia(self):
        """El caso DWDP/UTX, convertido en invariante ejecutable."""
        self.assertTrue(au.existencia_de_evento(presente_en_autoridad=True,
                                                presente_en_enriquecimiento=False))

    def test_solo_la_autoridad_puede_afirmar_la_no_existencia(self):
        self.assertFalse(au.existencia_de_evento(presente_en_autoridad=False,
                                                 presente_en_enriquecimiento=False))

    def test_alpha_vantage_no_es_autoridad_del_universo(self):
        self.assertFalse(au.es_autoridad_de_universo("Alpha Vantage"))
        self.assertIn(au.ENRICHMENT, au.proveedores()["Alpha Vantage"]["roles"])

    def test_la_sec_si_lo_es(self):
        self.assertTrue(au.es_autoridad_de_universo("SEC EDGAR / XBRL"))

    def test_la_regla_esta_escrita_en_la_declaracion(self):
        texto = au.declaracion()["regla_fundacional"]
        self.assertIn("PROVEEDOR", texto)
        self.assertIn("DWDP", texto)
        self.assertIn("UTX", texto)


class TestEstadosDeCobertura(unittest.TestCase):

    def test_hay_exactamente_cuatro_y_son_distintos(self):
        self.assertEqual(len(au.ESTADOS), 4)
        self.assertEqual(len(set(au.ESTADOS)), 4)

    def test_unavailable_y_not_measured_no_son_lo_mismo(self):
        """'lo miramos y no esta' != 'no lo hemos mirado'."""
        self.assertNotEqual(au.UNAVAILABLE, au.NOT_MEASURED)
        d = au.declaracion()["estados_de_cobertura"]
        self.assertIn("AUSENTE", d[au.UNAVAILABLE].upper())
        self.assertIn("NO SE HA COMPROBADO", d[au.NOT_MEASURED].upper())

    def test_ambiguous_no_es_available(self):
        """Recuperable por una heurística no es lo mismo que disponible."""
        self.assertNotEqual(au.AMBIGUOUS, au.AVAILABLE)
        self.assertEqual(au.componentes()["ticker_historico_a_CIK"]["estado"], au.AMBIGUOUS)


class TestCompletitudDelEvento(unittest.TestCase):

    def test_filing_mas_available_at_mas_actual_bastan(self):
        r = au.estado_del_evento(True, True, True, tiene_expectativa=False)
        self.assertEqual(r["event_status"], au.AVAILABLE)

    def test_la_falta_de_expectativa_no_elimina_el_evento(self):
        """Produce UNAVAILABLE en expectativa y sorpresa, no borra el hecho."""
        r = au.estado_del_evento(True, True, True, tiene_expectativa=False)
        self.assertEqual(r["event_status"], au.AVAILABLE)
        self.assertEqual(r["expectation_status"], au.UNAVAILABLE)
        self.assertEqual(r["surprise_status"], au.UNAVAILABLE)

    def test_sin_expectativa_siguen_construyendose_los_perfiles_no_condicionados(self):
        r = au.estado_del_evento(True, True, True, tiene_expectativa=False)
        for m in ("RAW_RETURN", "ABNORMAL_RETURN", "VOLUME_RELATIVE_TO_PRE_EVENT"):
            self.assertIn(m, r["perfiles_construibles"])
        self.assertIn("SURPRISE_CONDITIONED", r["perfiles_bloqueados"])

    def test_sin_resultado_el_evento_no_esta_completo(self):
        r = au.estado_del_evento(True, True, False, tiene_expectativa=True)
        self.assertEqual(r["event_status"], au.UNAVAILABLE)
        self.assertEqual(r["perfiles_construibles"], [])

    def test_los_perfiles_sin_expectativa_existen_de_verdad_en_el_motor(self):
        """Impide que la lista se desincronice de las medidas reales."""
        reales = set(pr.MEDIDAS)
        for m in au.PERFILES_SIN_EXPECTATIVA:
            self.assertIn(m, reales, m)

    def test_ninguna_medida_actual_depende_de_la_sorpresa(self):
        """Por eso la rejilla de hoy sobrevive a consensus UNAVAILABLE."""
        self.assertFalse(set(pr.MEDIDAS) & set(au.PERFILES_CON_EXPECTATIVA))


class TestMatrizDeCobertura(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.simbolos = sorted(uni.simbolos())
        cls.mat = au.matriz_cobertura(cls.simbolos)

    def test_cubre_el_universo_entero(self):
        self.assertEqual(set(self.mat), set(self.simbolos))

    def test_todo_valor_es_uno_de_los_cuatro_estados(self):
        for s, fila in self.mat.items():
            for col, v in fila.items():
                self.assertIn(v, au.ESTADOS, f"{s}/{col}")

    def test_lo_no_medido_es_not_measured_y_no_unavailable(self):
        """El error que esta matriz existe para impedir."""
        self.assertEqual(self.mat["AXP"]["sec"], au.NOT_MEASURED)
        self.assertNotEqual(self.mat["AXP"]["sec"], au.UNAVAILABLE)

    def test_los_deslistados_tienen_SEC_disponible_y_alpha_vantage_no(self):
        """La demostracion de la regla fundacional, activo a activo."""
        for s in ("DWDP", "UTX"):
            self.assertEqual(self.mat[s]["sec"], au.AVAILABLE, s)
            self.assertEqual(self.mat[s]["event"], au.AVAILABLE, s)
            self.assertEqual(self.mat[s]["actual"], au.AVAILABLE, s)
            self.assertEqual(self.mat[s]["expectation"], au.UNAVAILABLE, s)

    def test_el_precio_de_los_deslistados_es_ambiguo_no_disponible(self):
        """Existe bajo el sucesor pero rebaseado: no es AVAILABLE."""
        for s in ("DWDP", "UTX"):
            self.assertEqual(self.mat[s]["price"], au.AMBIGUOUS, s)

    def test_el_benchmark_esta_disponible_para_todos(self):
        """Un nivel publicado no depende de que el activo exista (D-25)."""
        for s in self.simbolos:
            self.assertEqual(self.mat[s]["benchmark"], au.AVAILABLE, s)

    def test_el_consenso_no_esta_disponible_para_ninguno(self):
        for s in self.simbolos:
            self.assertEqual(self.mat[s]["consensus"], au.UNAVAILABLE, s)

    def test_la_mayoria_del_universo_sigue_sin_medirse(self):
        """El exito de esta auditoria no es llenar la matriz."""
        r = au.resumen_matriz(self.simbolos)
        self.assertGreater(r[au.NOT_MEASURED], r[au.AVAILABLE])


class TestDeclaracion(unittest.TestCase):

    def test_todo_componente_declara_autoridad_estado_y_evidencia(self):
        for nombre, c in au.componentes().items():
            self.assertTrue(c["autoridad"].strip(), nombre)
            self.assertTrue(c["estado"].strip(), nombre)
            self.assertTrue(c["verificado"].strip(), nombre)

    def test_todo_proveedor_declara_su_riesgo_de_superviviencia(self):
        for nombre, p in au.proveedores().items():
            self.assertTrue(p["survivorship_risk"].strip(), nombre)
            self.assertTrue(p["calidad_temporal"].strip(), nombre)

    def test_el_consenso_pit_esta_declarado_como_no_disponible(self):
        self.assertEqual(au.componentes()["consensus_point_in_time"]["estado"], au.UNAVAILABLE)

    def test_la_declaracion_es_coherente(self):
        self.assertEqual(au.incoherencias(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
