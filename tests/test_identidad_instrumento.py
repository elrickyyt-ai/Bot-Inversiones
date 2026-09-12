"""Identidad historica de instrumento (2026-09-08).

El principio que ordena el fichero:

    Un proveedor que no conoce un instrumento no puede convertirlo en
    inexistente; y un ticker sucesor no puede convertirse silenciosamente
    en el instrumento predecesor.
"""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("contract", "events", "knowledge", "technical"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", sub))

import autoridad as au    # noqa: E402
import identidad as idn   # noqa: E402


class TestCapasDeIdentidad(unittest.TestCase):

    def test_el_ticker_no_es_identidad_historica(self):
        d = idn.declaracion()["capas_de_identidad"]["TICKER"]
        self.assertIn("NO_es_identidad", d)
        self.assertIn("MOB", d["prueba"])

    def test_un_cik_puede_tener_varios_instrumentos_a_la_vez(self):
        """Medido: la portada de RTX declara 'RTX' y 'RTX 30'."""
        d = idn.declaracion()["capas_de_identidad"]["MARKET_INSTRUMENT"]
        self.assertIn("RTX 30", d["cardinalidad"])

    def test_el_cik_no_es_eterno(self):
        """Una reorganizacion en holding crea un CIK nuevo (XOM, 2026)."""
        self.assertIn("holding", idn.declaracion()["capas_de_identidad"]["SEC_CIK"]["no_es"])

    def test_el_mapa_ticker_instrumento_no_es_inyectivo_en_el_tiempo(self):
        r = idn.declaracion()["relaciones"]["TICKER -> MARKET_INSTRUMENT"]
        self.assertIn("NO INYECTIVA", r)


class TestTransformaciones(unittest.TestCase):

    def test_la_particion_clave_es_si_cambia_la_exposicion(self):
        self.assertEqual(set(idn.AJUSTABLES), {"SPLIT", "TICKER_CHANGE", "HOLDCO_REORG"})
        self.assertEqual(set(idn.CAMBIAN_INSTRUMENTO), {"MERGER", "SPINOFF"})

    def test_merger_y_spinoff_no_son_la_misma_forma(self):
        t = idn.declaracion()["transformaciones"]
        self.assertEqual(t["MERGER"]["forma"], "A -> B")
        self.assertEqual(t["SPINOFF"]["forma"], "A -> B + C")

    def test_un_ajuste_multiplicativo_no_basta_para_todos(self):
        """El supuesto que esta auditoria existe para acotar."""
        t = idn.declaracion()["transformaciones"]
        self.assertTrue(t["SPLIT"]["ajuste_multiplicativo_basta"])
        self.assertFalse(t["SPINOFF"]["ajuste_multiplicativo_basta"])
        self.assertFalse(t["MERGER"]["ajuste_multiplicativo_basta"])

    def test_el_retorno_puede_sobrevivir_donde_la_economia_no(self):
        """Tras una escision el cociente es correcto y compara dos empresas."""
        c = idn.continuidad_de("SPINOFF")
        self.assertTrue(c[idn.RETURN])
        self.assertFalse(c[idn.ECONOMIC])

    def test_la_reutilizacion_de_ticker_no_conserva_nada(self):
        c = idn.continuidad_de("TICKER_REUSE")
        self.assertFalse(any(c.values()))

    def test_los_tres_tipos_de_continuidad_son_distintos(self):
        self.assertEqual(len(set(idn.TIPOS_CONTINUIDAD)), 3)


class TestElegibilidadEventStudy(unittest.TestCase):

    def test_sin_acciones_es_elegible_y_continuo(self):
        r = idn.elegibilidad_event_study([])
        self.assertTrue(r["eligible"])
        self.assertEqual(r["continuity_class"], idn.CONTINUOUS)

    def test_un_split_en_ventana_NO_invalida_la_observacion(self):
        """La regla no es 'excluir si hay accion corporativa'."""
        r = idn.elegibilidad_event_study([("SPLIT", "estimation")])
        self.assertTrue(r["eligible"])
        self.assertEqual(r["continuity_class"], idn.ADJUSTED)

    def test_una_escision_en_ventana_SI_la_invalida(self):
        r = idn.elegibilidad_event_study([("SPINOFF", "reaction")])
        self.assertFalse(r["eligible"])
        self.assertEqual(r["continuity_class"], idn.AMBIGUOUS)
        self.assertIn("instrumento", r["motivo"])

    def test_una_fusion_en_ventana_tambien(self):
        self.assertFalse(idn.elegibilidad_event_study([("MERGER", "estimation")])["eligible"])

    def test_una_accion_fuera_de_ventana_no_estorba(self):
        r = idn.elegibilidad_event_study([("SPINOFF", None)])
        self.assertTrue(r["eligible"])
        self.assertEqual(r["continuity_class"], idn.CONTINUOUS)

    def test_la_reutilizacion_de_ticker_es_caso_ambiguo_no_ajustable(self):
        r = idn.elegibilidad_event_study([("TICKER_REUSE", "estimation")])
        self.assertFalse(r["eligible"])

    def test_los_cuatro_casos_de_clasificacion_existen(self):
        self.assertEqual(idn.clasificar_accion("SPLIT", False), idn.FUERA_DE_VENTANA)
        self.assertEqual(idn.clasificar_accion("SPLIT", True), idn.AJUSTABLE_EN_VENTANA)
        self.assertEqual(idn.clasificar_accion("SPINOFF", True), idn.CAMBIA_INSTRUMENTO_EN_VENTANA)
        self.assertEqual(idn.clasificar_accion("DELISTING", True), idn.CASO_AMBIGUO)


class TestCasosMinimos(unittest.TestCase):

    def test_estan_los_cinco(self):
        self.assertEqual(set(idn.casos()), {"DWDP", "UTX", "IBM", "NVDA", "XOM"})

    def test_ibm_tiene_una_escision_pese_a_estar_en_la_cohorte(self):
        """Kyndryl 2021-11-04, declarada por Yahoo como split 1046:1000."""
        tipos = [t["tipo"] for t in idn.casos()["IBM"]["transformaciones"]]
        self.assertIn("SPINOFF", tipos)

    def test_nvda_es_el_unico_sin_cambio_de_instrumento(self):
        for c, esperado in (("NVDA", False), ("IBM", True), ("XOM", True),
                            ("DWDP", True), ("UTX", True)):
            tipos = {t["tipo"] for t in idn.casos()[c]["transformaciones"]}
            self.assertEqual(bool(tipos & set(idn.CAMBIAN_INSTRUMENTO)), esperado, c)

    def test_xom_tiene_dos_cik_distintos(self):
        """La reorganizacion de 2026 parte el mapa ticker->CIK."""
        c = idn.casos()["XOM"]
        self.assertNotEqual(c["cik_historico"], c["cik_actual_del_ticker"])

    def test_el_mapeo_historico_esta_declarado_incompleto(self):
        self.assertEqual(idn.mapping_status(), "INCOMPLETE")
        self.assertTrue(idn.declaracion()["_hueco_exacto"].strip())


class TestNoConfundirSucesorConPredecesor(unittest.TestCase):
    """El punto 7 del encargo, convertido en invariante."""

    def test_la_ausencia_en_el_directorio_no_es_inexistencia(self):
        """Reutiliza la regla fundacional de D-36."""
        self.assertTrue(au.existencia_de_evento(presente_en_autoridad=True,
                                                presente_en_enriquecimiento=False))

    def test_el_precio_del_sucesor_no_se_declara_disponible_para_el_predecesor(self):
        """DD y RTX cubren la ventana, pero rebaseados: AMBIGUOUS, no AVAILABLE."""
        _, mat = idn.matriz_casos()
        for c in ("DWDP", "UTX"):
            self.assertEqual(mat[c]["price"], "AMBIGUOUS", c)
            self.assertNotEqual(mat[c]["price"], "AVAILABLE", c)

    def test_el_ticker_historico_no_se_declara_resuelto(self):
        _, mat = idn.matriz_casos()
        self.assertEqual(mat["DWDP"]["historical_ticker"], "AMBIGUOUS")
        self.assertEqual(mat["XOM"]["historical_ticker"], "AMBIGUOUS")


class TestMatrizYDeclaracion(unittest.TestCase):

    def test_solo_los_cuatro_estados(self):
        cols, mat = idn.matriz_casos()
        for c, fila in mat.items():
            for k in cols:
                self.assertIn(fila[k], au.ESTADOS, f"{c}/{k}")

    def test_lo_no_medido_no_se_convierte_en_unavailable(self):
        _, mat = idn.matriz_casos()
        self.assertEqual(mat["IBM"]["event"], au.NOT_MEASURED)
        self.assertNotEqual(mat["IBM"]["event"], au.UNAVAILABLE)

    def test_solo_nvda_es_elegible_a_nivel_de_activo(self):
        _, mat = idn.matriz_casos()
        elegibles = [c for c in mat if mat[c]["event_study_eligible"] == au.AVAILABLE]
        self.assertEqual(elegibles, ["NVDA"])

    def test_la_declaracion_es_coherente(self):
        self.assertEqual(idn.incoherencias(), [])

    def test_todo_caso_declara_continuidad_conocida(self):
        for nombre, c in idn.casos().items():
            self.assertIn(c["continuidad"].split()[0], idn.CLASES_CONTINUIDAD, nombre)


if __name__ == "__main__":
    unittest.main(verbosity=2)
