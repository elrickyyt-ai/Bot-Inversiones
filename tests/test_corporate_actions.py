"""Cobertura de acciones corporativas y continuidad economica (2026-09-08).

Dos invariantes de seguridad, y la segunda es la mas fuerte que ha
aparecido en el proyecto:

    1. La validez de una observacion historica depende tambien de que la
       entidad, el instrumento y su continuidad economica puedan
       identificarse DURANTE la ventana analizada.
    2. Un FALSO POSITIVO DE IDENTIDAD es mas peligroso que un dato ausente.
"""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("contract", "events", "knowledge", "technical", "causal"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", sub))

import cobertura_acciones as ca   # noqa: E402
import identidad as idn           # noqa: E402
import perfil_reaccion as pr      # noqa: E402


class TestRegistroDeAcciones(unittest.TestCase):

    def test_todo_tipo_declarado_es_conocido(self):
        d = ca.registro()
        for a in d["acciones"]:
            self.assertIn(a["tipo"], d["tipos"], a["fecha"])

    def test_la_clasificacion_no_se_deduce_del_factor_de_precio(self):
        """Un ratio no redondo es indicio, nunca prueba (D-41)."""
        self.assertIn("NUNCA prueba", ca.registro()["_regla_de_clasificacion"])
        for a in ca.registro()["acciones"]:
            self.assertTrue(a["clasificacion_basada_en"].strip(), a["fecha"])
            self.assertIn("verificado_contra_sec", a)

    def test_la_escision_de_kyndryl_esta_verificada_contra_la_sec(self):
        """Es el caso que afecta a la cohorte: no puede quedar en indicio."""
        k = [a for a in ca.acciones_de("IBM") if a["fecha"] == "2021-11-04"]
        self.assertEqual(len(k), 1)
        self.assertEqual(k[0]["tipo"], "SPINOFF")
        self.assertTrue(k[0]["verificado_contra_sec"])
        self.assertIn("2.01", k[0]["clasificacion_basada_en"])

    def test_la_fusion_de_xom_no_tiene_senal_de_precio(self):
        """Las fusiones no las declara la fuente de precios."""
        m = [a for a in ca.acciones_de("XOM") if a["tipo"] == "MERGER"][0]
        self.assertIn("NINGUNA", m["senal_de_precio"])
        self.assertTrue(m["verificado_contra_sec"])

    def test_el_ticker_reutilizado_es_UNKNOWN_y_no_SUCCESSION(self):
        """Clasificarlo como sucesion seria el falso positivo de identidad."""
        m = [a for a in ca.acciones_de("MOB")][0]
        self.assertEqual(m["tipo"], "UNKNOWN")
        self.assertIn("por_que_UNKNOWN", m)


class TestParticionDeContinuidad(unittest.TestCase):

    def test_split_no_cambia_el_instrumento_y_escision_si(self):
        self.assertIn("SPLIT", ca.NO_CAMBIAN_INSTRUMENTO)
        self.assertIn("SPINOFF", ca.CAMBIAN_INSTRUMENTO)
        self.assertIn("MERGER", ca.CAMBIAN_INSTRUMENTO)

    def test_la_politica_propuesta_cubre_todos_los_tipos(self):
        for t in ca.registro()["tipos"]:
            self.assertIn(t, ca.POLITICA_PROPUESTA, t)

    def test_lo_que_cambia_el_instrumento_se_propone_EXCLUDE(self):
        for t in ca.CAMBIAN_INSTRUMENTO:
            self.assertEqual(ca.POLITICA_PROPUESTA[t], "EXCLUDE", t)

    def test_lo_ajustable_se_propone_FLAG_no_EXCLUDE(self):
        """Excluir todo split tiraria observaciones validas."""
        self.assertEqual(ca.POLITICA_PROPUESTA["SPLIT"], "FLAG")

    def test_lo_sin_clasificar_se_propone_AMBIGUOUS(self):
        self.assertEqual(ca.POLITICA_PROPUESTA["UNKNOWN"], "AMBIGUOUS")


class TestMedicionSobreLosEventosReales(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.det = ca.medir()
        cls.res = ca.resumen(cls.det)

    def test_mide_los_52_eventos_en_los_cuatro_horizontes(self):
        for h in pr.HORIZONTES:
            self.assertEqual(self.res[h]["n_events"], 52, h)

    def test_los_conteos_cuadran(self):
        for h, c in self.res.items():
            self.assertEqual(c["n_events_clean"] + c["n_events_with_corporate_action"],
                             c["n_events"], h)
            self.assertLessEqual(c["n_events_ambiguous"], c["n_events_with_corporate_action"])

    def test_la_contaminacion_crece_con_el_horizonte(self):
        """Una ventana mas larga atrapa mas acciones. Si esto se invierte,
        hay un error de ventanas."""
        con = [self.res[h]["n_events_with_corporate_action"] for h in pr.HORIZONTES]
        self.assertEqual(con, sorted(con))

    def test_ningun_evento_actual_es_ambiguo_y_eso_es_del_MUESTREO(self):
        """La escision de Kyndryl (2021-11-04) cae en el hueco de muestreo
        de IBM (2021-01-22 -> 2022-01-25). El 0% NO significa que la cohorte
        este limpia: significa que la cohorte no es contigua."""
        self.assertEqual(self.res["2_60d"]["n_events_ambiguous"], 0)
        fechas = sorted(o["first_tradable_at"] for o in pr.observaciones_v1()
                        if o["asset_id"] == "IBM" and o["first_tradable_at"])
        self.assertNotIn("2021-10-20", fechas)
        anterior = [f for f in fechas if f < "2021-11-04"][-1]
        posterior = [f for f in fechas if f > "2021-11-04"][0]
        self.assertEqual((anterior, posterior), ("2021-01-22", "2022-01-25"))


class TestResolucionTemporalDeIdentidad(unittest.TestCase):
    """El caso MOB, como test permanente."""

    def test_un_ticker_actual_no_demuestra_identidad_historica(self):
        cik, motivo = idn.resolver_identidad("MOB", "1995-06-01")
        self.assertIsNone(cik)
        self.assertIn("AMBIGUOUS", motivo)

    def test_el_mismo_ticker_si_resuelve_en_su_propio_intervalo(self):
        cik, ent = idn.resolver_identidad("MOB", "2024-01-05")
        self.assertEqual(ent, "Mobilicom Limited")

    def test_xom_resuelve_a_cik_distinto_segun_la_fecha(self):
        """La reorganizacion de 2026 no puede dejar el historico apuntando
        al CIK nuevo."""
        antiguo, _ = idn.resolver_identidad("XOM", "2019-04-26")
        nuevo, _ = idn.resolver_identidad("XOM", "2026-08-15")
        self.assertEqual(antiguo, "0000034088")
        self.assertEqual(nuevo, "0002115436")
        self.assertNotEqual(antiguo, nuevo)

    def test_un_ticker_sin_intervalo_declarado_no_se_adivina(self):
        cik, motivo = idn.resolver_identidad("IBM", "2020-01-01")
        self.assertIsNone(cik)
        self.assertIn("AMBIGUOUS", motivo)

    def test_la_regla_de_seguridad_esta_escrita(self):
        r = idn.declaracion()["resolucion_temporal"]["_regla"]
        self.assertIn("falso positivo", r.lower())


class TestSemanticaDeRelacion(unittest.TestCase):

    def test_las_cuatro_clases_estan_declaradas(self):
        clases = idn.declaracion()["semantica_de_relacion"]["clases"]
        self.assertEqual(set(clases), {"CAUSAL", "STRUCTURAL", "MEASUREMENT", "REFERENCE"})

    def test_ningun_predicado_de_identidad_se_declara_causal(self):
        preds = idn.declaracion()["semantica_de_relacion"]["predicados"]
        for p in ("ISSUED_BY", "LISTED_ON", "BENCHMARKED_BY", "COMPARED_TO", "SUCCESSOR_OF"):
            self.assertNotEqual(preds[p], "CAUSAL", p)

    def test_successor_of_se_clasifica_antes_de_existir(self):
        """Para que no entre al traversal por defecto el dia que se anada."""
        import modelo as m
        self.assertNotIn("SUCCESSOR_OF", m.PREDICADOS)
        self.assertEqual(idn.declaracion()["semantica_de_relacion"]["predicados"]["SUCCESSOR_OF"],
                         "STRUCTURAL")

    def test_el_traversal_usa_lista_negra_y_queda_registrado(self):
        """Hoy se recorre TODO menos dos predicados: un predicado nuevo
        entra al motor causal por defecto. Este test documenta el riesgo."""
        import modelo as m
        recorridos = set(m.PREDICADOS) - set(m.PREDICADOS_NO_CAUSALES)
        self.assertIn("ISSUED_BY", recorridos)
        self.assertIn("LISTED_ON", recorridos)

    def test_la_medicion_de_caminos_vacios_esta_registrada(self):
        med = idn.declaracion()["semantica_de_relacion"]["medicion"]
        self.assertEqual(med["caminos_totales"], 95)
        self.assertEqual(med["sin_ninguna_arista_causal"], 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
