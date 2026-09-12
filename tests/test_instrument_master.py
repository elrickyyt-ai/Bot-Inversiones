"""Historical Instrument Master v1 (2026-09-08).

El criterio de salida, como invariante ejecutable:

    Para una fecha historica, un ticker solo produce un instrumento si
    existe una relacion temporalmente valida entre ticker, listing/security
    e issuer. Un ticker reutilizado o sin mapeo historico se marca ambiguo
    o no resuelto, NUNCA se acepta por el mero hecho de que una fuente de
    precios devuelva datos.
"""
import datetime
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("contract", "events", "knowledge", "causal"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", sub))

import caminos            # noqa: E402
import instrumentos as im  # noqa: E402
import modelo             # noqa: E402


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()


class TestTickerNoEsIdentidad(Base):

    def test_resolve_instrument_exige_as_of(self):
        """No existe resolve_instrument(identifier) para historia."""
        with self.assertRaises(ValueError):
            im.resolve_instrument("XOM", None, self.k)

    def test_un_ticker_no_implica_identidad(self):
        """El mismo simbolo da instrumentos distintos en fechas distintas."""
        a = im.resolve_instrument("MOB", "2024-01-05", self.k)
        b = im.resolve_instrument("MOB", "1995-06-01", self.k)
        self.assertEqual(a["identity_status"], im.VALID)
        self.assertEqual(b["identity_status"], im.UNRESOLVED)
        self.assertNotEqual(a["security"], b["security"])

    def test_un_ticker_puede_tener_varios_CIK_a_lo_largo_del_tiempo(self):
        antes = im.resolve_instrument("XOM", "2019-04-26", self.k)
        despues = im.resolve_instrument("XOM", "2026-08-15", self.k)
        self.assertEqual(antes["issuer"], "org:exxonmobil")
        self.assertEqual(despues["issuer"], "org:exxonmobil-holdings")
        self.assertEqual(antes["security"], despues["security"])

    def test_el_cik_viaja_como_alias_fechado_no_como_identidad(self):
        orgs = {e["entity_id"]: e for e in self.k["entities"]
                if e.get("type") == "organization"}
        viejo = [a for a in orgs["org:exxonmobil"]["aliases"] if a["scheme"] == "sec_cik"]
        nuevo = [a for a in orgs["org:exxonmobil-holdings"]["aliases"] if a["scheme"] == "sec_cik"]
        self.assertEqual(viejo[0]["value"], "0000034088")
        self.assertEqual(nuevo[0]["value"], "0002115436")
        self.assertEqual(nuevo[0]["valid_from"], "2026-07-01")


class TestMOBPruebaDeSeguridad(Base):
    """El ticker reutilizado, como test permanente."""

    def test_MOB_historico_no_devuelve_Mobilicom(self):
        r = im.resolve_instrument("MOB", "1995-06-01", self.k)
        self.assertEqual(r["identity_status"], im.UNRESOLVED)
        self.assertIsNone(r["security"])
        self.assertIsNone(r["issuer"])

    def test_el_precio_no_basta_para_dar_identidad(self):
        """Aunque la fuente devuelva 1011 sesiones, no hay identidad en 1995."""
        c = im.apto_para_event_study("MOB", "1995-06-01", price_available=True, k=self.k)
        self.assertTrue(c["price_available"])
        self.assertFalse(c["instrument_identity_valid"])
        self.assertFalse(c["elegible"])

    def test_mobilicom_no_es_sucesor_de_nada(self):
        self.assertIsNone(im.sucesor_de("sec:MOB.NASDAQ", "2026-09-08", self.k))
        for r in self.k["relationships"]:
            if r["predicate"] == "SUCCEEDED_BY":
                self.assertNotIn("MOB", r["object"])


class TestSucesion(Base):

    def test_la_sucesion_es_estructural(self):
        rels = [r for r in self.k["relationships"] if r["predicate"] == "SUCCEEDED_BY"]
        self.assertTrue(rels)
        for r in rels:
            self.assertEqual(r["nature"], "STRUCTURAL")

    def test_la_sucesion_no_entra_al_grafo_causal(self):
        """D-23: una sucesion de instrumento no es un mecanismo economico."""
        self.assertIn("SUCCEEDED_BY", modelo.PREDICADOS_NO_CAUSALES)
        salidas, _ = caminos.indice(self.k, datetime.date(2026, 9, 8))
        for origen, aristas in salidas.items():
            for _destino, rel, _dir in aristas:
                self.assertNotEqual(rel["predicate"], "SUCCEEDED_BY", origen)

    def test_los_sucesores_declarados_son_los_medidos(self):
        self.assertEqual(im.sucesor_de("sec:DWDP.NYSE", "2026-09-08", self.k), "sec:DD.NYSE")
        self.assertEqual(im.sucesor_de("sec:UTX.NYSE", "2026-09-08", self.k), "sec:RTX.NYSE")

    def test_la_ausencia_de_mapping_no_se_convierte_en_falso(self):
        """WBA no tiene sucesor declarado: eso es 'no verificado', no 'no existe'."""
        self.assertIsNone(im.sucesor_de("sec:WBA.NASDAQ", "2026-09-08", self.k))
        wba = [e for e in self.k["entities"] if e["entity_id"] == "sec:WBA.NASDAQ"][0]
        self.assertIn("no se ha verificado", wba["nota"])


class TestVigenciaTemporal(Base):

    def test_una_security_valida_exige_intervalo(self):
        for e in self.k["entities"]:
            if e.get("type") != "security":
                continue
            for al in e.get("aliases") or []:
                if al["scheme"] == "ticker":
                    self.assertIn("valid_from", al, e["entity_id"])
                    self.assertIn("valid_to", al, e["entity_id"])

    def test_fuera_de_vigencia_no_resuelve(self):
        """DWDP existio hasta 2019; en 2024 su ticker ya no designa nada."""
        r = im.resolve_instrument("DWDP", "2024-01-01", self.k)
        self.assertEqual(r["identity_status"], im.UNRESOLVED)

    def test_dentro_de_vigencia_si_resuelve(self):
        r = im.resolve_instrument("DWDP", "2018-11-01", self.k)
        self.assertEqual(r["identity_status"], im.VALID)
        self.assertEqual(r["security"], "sec:DWDP.NYSE")

    def test_el_validador_permite_reutilizar_un_ticker_sin_solape(self):
        """Antes prohibia globalmente que dos entidades compartieran alias;
        eso daba por supuesto que un ticker identifica a una sola entidad en
        toda la historia -- el supuesto que MOB desmiente."""
        self.assertEqual(modelo.validar(self.k), [])

    def test_el_validador_sigue_prohibiendo_el_solape_real(self):
        import copy
        k2 = copy.deepcopy(self.k)
        for e in k2["entities"]:
            if e["entity_id"] == "sec:IBM.NYSE":
                e["aliases"].append({"scheme": "ticker", "value": "NVDA", "venue": "ven:NASDAQ",
                                     "valid_from": "2020-01-01", "valid_to": None,
                                     "source_id": "src:sec-submissions"})
        fallos = modelo.validar(k2)
        self.assertTrue(any("alias ambiguo" in f for f in fallos), fallos)


class TestEstados(Base):

    def test_los_tres_estados_existen_y_son_distintos(self):
        self.assertEqual(len(set(im.ESTADOS)), 3)
        self.assertEqual(set(im.ESTADOS), {"VALID", "AMBIGUOUS", "UNRESOLVED"})

    def test_unresolved_no_se_convierte_en_valid(self):
        r = im.resolve_instrument("NO-EXISTE-ESTE-TICKER", "2020-01-01", self.k)
        self.assertEqual(r["identity_status"], im.UNRESOLVED)
        self.assertIsNone(r["security"])
        self.assertTrue(r["motivo"])

    def test_todo_estado_no_valido_lleva_motivo(self):
        for ident, f in (("MOB", "1995-06-01"), ("DWDP", "2024-01-01"), ("ZZZZ", "2020-01-01")):
            r = im.resolve_instrument(ident, f, self.k)
            if r["identity_status"] != im.VALID:
                self.assertTrue(r.get("motivo"), f"{ident}@{f}")

    def test_ambiguous_no_se_convierte_en_unavailable(self):
        """Son estados distintos y el punto de control los distingue."""
        c = im.apto_para_event_study("MOB", "1995-06-01", price_available=True, k=self.k)
        self.assertEqual(c["identity_status"], im.UNRESOLVED)
        self.assertIn("price_available", c)
        self.assertTrue(c["price_available"])


class TestCasosObligatorios(Base):

    def test_los_nueve_casos_del_encargo(self):
        esperado = {
            ("DWDP", "2018-11-01"): (im.VALID, "sec:DWDP.NYSE"),
            ("UTX",  "2019-01-23"): (im.VALID, "sec:UTX.NYSE"),
            ("WBA",  "2019-06-01"): (im.VALID, "sec:WBA.NASDAQ"),
            ("XOM",  "2019-04-26"): (im.VALID, "sec:XOM.NYSE"),
            ("XOM",  "2026-08-15"): (im.VALID, "sec:XOM.NYSE"),
            ("MOB",  "1995-06-01"): (im.UNRESOLVED, None),
            ("IBM",  "2020-01-01"): (im.VALID, "sec:IBM.NYSE"),
            ("NVDA", "2020-01-01"): (im.VALID, "sec:NVDA.NASDAQ"),
        }
        for (ident, f), (st, sec) in esperado.items():
            r = im.resolve_instrument(ident, f, self.k)
            self.assertEqual(r["identity_status"], st, f"{ident}@{f}")
            self.assertEqual(r["security"], sec, f"{ident}@{f}")

    def test_XOM_2019_y_2026_dan_emisores_distintos(self):
        a = im.resolve_instrument("XOM", "2019-04-26", self.k)["issuer"]
        b = im.resolve_instrument("XOM", "2026-08-15", self.k)["issuer"]
        self.assertNotEqual(a, b)

    def test_los_deslistados_conservan_identidad_sin_precio(self):
        """D-36: no tener serie no los borra del modelo."""
        for ident, f in (("DWDP", "2018-11-01"), ("UTX", "2019-01-23"), ("WBA", "2019-06-01")):
            r = im.resolve_instrument(ident, f, self.k)
            self.assertEqual(r["identity_status"], im.VALID, ident)
            c = im.apto_para_event_study(ident, f, price_available=False, k=self.k)
            self.assertTrue(c["instrument_identity_valid"], ident)
            self.assertFalse(c["elegible"], ident)


class TestNoSeCreoEstructuraParalela(Base):

    def test_no_hay_tipo_de_entidad_listing(self):
        """El listing se representa con aliases fechados sobre el security."""
        self.assertNotIn("listing", modelo.TIPOS_ENTIDAD)
        xom = [e for e in self.k["entities"] if e["entity_id"] == "sec:XOM.NYSE"][0]
        tickers = [a for a in xom["aliases"] if a["scheme"] == "ticker"]
        self.assertEqual({a["value"] for a in tickers}, {"XON", "XOM"})
        for a in tickers:
            self.assertEqual(a["venue"], "ven:NYSE")

    def test_solo_se_anadio_un_predicado(self):
        nuevos = set(modelo.PREDICADOS) - {
            "ISSUED_BY", "LISTED_ON", "DOMICILED_IN", "CLASSIFIED_AS", "EXPOSED_TO",
            "SUPPLIES", "USES", "DEPENDS_ON", "SUBSTITUTES", "BENCHMARKED_BY", "COMPARED_TO"}
        self.assertEqual(nuevos, {"SUCCEEDED_BY"})

    def test_D21_intacta(self):
        self.assertIn("benchmark", modelo.TIPOS_ENTIDAD)
        self.assertEqual(modelo.PREDICADOS["BENCHMARKED_BY"], ({"security"}, {"benchmark"}))
        self.assertIn("BENCHMARKED_BY", modelo.PREDICADOS_NO_CAUSALES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
