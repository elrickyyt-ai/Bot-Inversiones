"""Economic Knowledge Seed v2 -- P5C (2026-09-07).

La primera cadena economica REAL del proyecto: NVIDIA -> TSMC -> CoWoS.

Lo que hace distinta a esta fase no es el numero de relaciones (tres).
Es de donde vienen. Todo el Knowledge anterior se extrajo del propio
repositorio: tablas del codigo (INTERNAL_RULE), ficheros que este
sistema escribe (DATA_PROVIDER) o mediciones hechas aqui dentro
(OWN_ANALYSIS). Ninguna de esas fuentes es evidencia del mundo: son
evidencia de lo que este software hace. P5C introduce las dos primeras
fuentes EXTERNAS y primarias -- dos documentos regulatorios en EDGAR --
y por eso estos tests miran sobre todo la procedencia.

El resultado economico de la cadena sigue siendo UNKNOWN, y eso no es
un fallo: ahora hay un camino que recorrer, pero sigue sin haber nada
medido sobre el. La diferencia es que el sistema ya puede decir
exactamente que medicion le falta, en vez de no tener ni la pregunta.
"""
import datetime
import json
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "engine", "knowledge"))
sys.path.insert(0, os.path.join(RAIZ, "engine", "causal"))

import caminos  # noqa: E402
import modelo  # noqa: E402
import valoracion  # noqa: E402

HOY = datetime.date(2026, 9, 7)
CADENA = ("rel:0046", "rel:0047", "rel:0048")

# Fragmentos literales de los dos documentos, transcritos a mano al
# leerlos. Si un dia alguien reescribe un `statement` con una parafrasis
# comoda, estos tests lo dicen.
LITERAL_NVDA_TSMC = "We utilize foundries, such as Taiwan Semiconductor Manufacturing Company Limited"
LITERAL_NVDA_COWOS = "We utilize CoWoS technology for semiconductor packaging."
LITERAL_TSMC_COWOS = "CoWoS advanced packaging services"


def _k():
    return modelo.cargar()


class TestLaCadenaEstaDadaDeAlta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k = _k()
        cls.rels = {r["relationship_id"]: r for r in cls.k["relationships"]}

    def test_el_conjunto_sigue_validando(self):
        self.assertEqual(modelo.validar(self.k), [])

    def test_las_tres_relaciones_existen_con_la_forma_esperada(self):
        esperado = {
            "rel:0046": ("org:tsmc", "SUPPLIES", "org:nvidia"),
            "rel:0047": ("org:nvidia", "USES", "tech:cowos"),
            "rel:0048": ("org:tsmc", "USES", "tech:cowos"),
        }
        for rid, (s, p, o) in esperado.items():
            r = self.rels[rid]
            self.assertEqual((r["subject"], r["predicate"], r["object"]), (s, p, o))
            self.assertEqual(r["polarity"], "AFFIRMS")

    def test_son_estructurales_verificadas_y_con_soporte_alto(self):
        """Un documento regulatorio releible es exactamente lo que
        STRUCTURAL significa en este modelo. Si la fuente fuera una nota
        de research, ninguna de las tres podria estar aqui asi."""
        for rid in CADENA:
            r = self.rels[rid]
            self.assertEqual(r["nature"], "STRUCTURAL", rid)
            self.assertEqual(r["status"], "VERIFIED", rid)
            self.assertEqual(r["support_level"], "ALTO", rid)

    def test_cowos_es_una_tecnologia_no_un_producto(self):
        """pendiente/ la habia previsto como prod:cowos. El cambio es
        deliberado y esta razonado en la nota de la entidad."""
        ent = {e["entity_id"]: e for e in self.k["entities"]}
        self.assertEqual(ent["tech:cowos"]["type"], "technology")
        self.assertIn("prod:cowos", ent["tech:cowos"]["nota"])


class TestLaProcedenciaEsExterna(unittest.TestCase):
    """El nucleo de P5C."""

    @classmethod
    def setUpClass(cls):
        cls.k = _k()
        cls.rels = {r["relationship_id"]: r for r in cls.k["relationships"]}
        cls.src = {s["source_id"]: s for s in cls.k["sources"]}

    def test_las_tres_citan_un_filing_de_una_parte_externa(self):
        for rid in CADENA:
            s = self.src[self.rels[rid]["source_id"]]
            self.assertEqual(s["tipo"], "FILING", rid)
            self.assertTrue(s["publisher"], rid)

    def test_ninguna_se_apoya_en_el_propio_codigo_de_este_sistema(self):
        """La distincion que P2 dejo escrita: una regla del software NO
        es un hecho del mundo. Toda la cadena tiene que estar libre de
        INTERNAL_RULE y de OWN_ANALYSIS."""
        for rid in CADENA:
            s = self.src[self.rels[rid]["source_id"]]
            self.assertNotIn(s["tipo"], {"INTERNAL_RULE", "OWN_ANALYSIS"}, rid)

    def test_el_localizador_reabre_el_documento_exacto(self):
        """Una fuente que no se puede volver a abrir no es una fuente.
        No se comprueba por red: se comprueba que el localizador apunta
        a un accession concreto de EDGAR, que es inmutable."""
        for rid in CADENA:
            s = self.src[self.rels[rid]["source_id"]]
            self.assertIn("https://www.sec.gov/Archives/edgar/data/", s["localizador"], rid)
            self.assertTrue(s["accesible"], rid)
            self.assertTrue(s["fecha_publicacion"], rid)

    def test_el_statement_reproduce_el_literal_del_documento(self):
        self.assertIn(LITERAL_NVDA_TSMC, self.rels["rel:0046"]["statement"])
        self.assertIn(LITERAL_NVDA_COWOS, self.rels["rel:0047"]["statement"])
        self.assertIn(LITERAL_TSMC_COWOS, self.rels["rel:0048"]["statement"])

    def test_el_sesgo_de_la_fuente_queda_anotado(self):
        """NVIDIA describiendo su propia cadena es parte interesada, y el
        'such as' del original hace la lista no exhaustiva. Las dos cosas
        se anotan; ninguna invalida la relacion, pero ocultarlas si la
        haria enganosa."""
        s = self.src["src:nvda-10k-fy2026"]
        self.assertIn("parte interesada", s["nota"])
        self.assertIn("no exhaustiv", s["nota"])
        self.assertIn("such as", self.rels["rel:0046"]["statement"])

    def test_la_vigencia_no_se_extrapola(self):
        """valid_from es el primer dia del ejercicio que cubre el
        documento, no 'desde siempre' ni la fecha de consulta. TSMC
        fabrica para NVIDIA desde mucho antes de 2025; ESTA fuente no lo
        acredita, asi que el sistema no lo afirma."""
        for rid, desde in (("rel:0046", "2025-01-27"), ("rel:0047", "2025-01-27"),
                           ("rel:0048", "2025-01-01")):
            r = self.rels[rid]
            self.assertEqual(r["valid_from"], desde, rid)
            self.assertIsNone(r["valid_to"], rid)
            self.assertNotEqual(r["valid_from"], r["last_verified"], rid)


class TestElCaminoSeRecorre(unittest.TestCase):
    """NVDA -> NVIDIA -> TSMC -> CoWoS, con el motor de P5A sin tocar."""

    @classmethod
    def setUpClass(cls):
        cls.k = _k()
        cls.cs = caminos.descubrir("ev4:p5c", "sec:NVDA.NASDAQ", cls.k, HOY, max_depth=3,
                                   tipos_objetivo={"product", "technology", "material"})
        cls.cadena = [c for c in cls.cs
                      if [a["relationship_id"] for a in c["edges"]]
                      == ["rel:0005", "rel:0046", "rel:0048"]]

    def test_la_cadena_pedida_existe_y_esta_completa(self):
        self.assertEqual(len(self.cadena), 1)
        c = self.cadena[0]
        self.assertEqual(c["completeness"], "COMPLETE")
        self.assertEqual(c["edges"][-1]["to"], "tech:cowos")

    def test_es_el_primer_camino_verificado_hasta_una_entidad_no_financiera(self):
        """Antes de P5C, todo camino completo habria sido PROVISIONAL o
        no habria existido: el unico enlace disponible hacia fuera de lo
        financiero era EXPOSED_TO, que procede de una regla del propio
        motor."""
        self.assertEqual(self.cadena[0]["validity"], "VERIFIED")
        preds = {a["predicate"] for a in self.cadena[0]["edges"]}
        self.assertNotIn("EXPOSED_TO", preds)

    def test_el_salto_al_proveedor_se_recorre_en_reverso(self):
        """SUPPLIES esta declarada TSMC -> NVIDIA. Ir de NVIDIA a TSMC es
        recorrerla al reves, y eso se anota; no se duplica la relacion en
        el sentido comodo."""
        arista = self.cadena[0]["edges"][1]
        self.assertEqual(arista["relationship_id"], "rel:0046")
        self.assertEqual(arista["traversal_direction"], "REVERSE")

    def test_ninguna_arista_se_inventa(self):
        ids = {r["relationship_id"] for r in self.k["relationships"]}
        for a in self.cadena[0]["edges"]:
            self.assertIn(a["relationship_id"], ids)


class TestLaCadenaEsUnaPreguntaNoUnaRespuesta(unittest.TestCase):
    """P5B sobre la cadena real: UNKNOWN, y diciendo que falta."""

    @classmethod
    def setUpClass(cls):
        cls.k = _k()
        evento = {"event_id": "ev4:p5c", "primary_entity": "org:nvidia",
                  "action": "demand_change", "direction": "UP"}
        cs = caminos.descubrir(evento["event_id"], "org:nvidia", cls.k, HOY, max_depth=2)
        camino = next(c for c in cs
                      if [a["relationship_id"] for a in c["edges"]] == ["rel:0046", "rel:0048"])
        cls.a = valoracion.valorar(evento, camino, [], cls.k, modelo.vigente, HOY)
        valoracion.validar(cls.a)

    def test_el_resultado_es_unknown(self):
        self.assertEqual(self.a["overall_direction"], "UNKNOWN")
        self.assertEqual(self.a["support"], "UNKNOWN")

    def test_pero_ahora_hay_mecanismos_reconocidos_en_vez_de_nada(self):
        """Antes de P5C todo camino real caia en NO_MECHANISM porque solo
        habia aristas de identidad. Ahora las reglas SI se activan y se
        quedan bloqueadas por falta de medicion, que es un estado
        distinto y mucho mas util."""
        mecs = {t["mechanism"] for t in self.a["segments"]}
        self.assertIn("CUSTOMER_DEMAND", mecs)
        self.assertIn("CAPACITY_CONSTRAINT", mecs)

    def test_dice_exactamente_que_medicion_le_falta(self):
        """El valor real de P5C para la fase siguiente: requires_evidence
        deja de estar vacio y se convierte en la justificacion para abrir
        una fuente de datos nueva -- no al reves."""
        pedido = {v for t in self.a["segments"] for v in t["requires_evidence"]}
        self.assertIn("demand(org:nvidia)", pedido)
        self.assertIn("capacity_utilization(tech:cowos)", pedido)

    def test_no_se_estampa_ningun_signo_sin_evidencia(self):
        for t in self.a["segments"]:
            self.assertEqual(t["economic_direction"], "UNKNOWN", t["mechanism"])
            self.assertEqual(t["evidence_ids"], [])


class TestElLimiteAcordadoSeRespeta(unittest.TestCase):
    """El usuario fijo el alcance: primero NVIDIA -> TSMC -> CoWoS, y
    HBM u otro nodo SOLO cuando la relacion este documentada."""

    @classmethod
    def setUpClass(cls):
        cls.k = _k()
        cls.ids = {e["entity_id"] for e in cls.k["entities"]}

    def test_hbm_y_el_sustrato_siguen_fuera(self):
        self.assertNotIn("prod:hbm", self.ids)
        self.assertNotIn("mat:abf-substrate", self.ids)

    def test_cowos_no_depende_de_nada_todavia(self):
        """El siguiente eslabon (CoWoS -> ?) no esta, y no se rellena."""
        salen = [r for r in self.k["relationships"] if r["subject"] == "tech:cowos"]
        self.assertEqual(salen, [])

    def test_siguen_siendo_candidatas_declaradas_y_no_conocimiento(self):
        pend = [c for c in modelo.cargar_pendiente() if c.get("predicate")]
        objetos = {c["object"] for c in pend}
        self.assertEqual(objetos, {"prod:hbm", "mat:abf-substrate"})
        for c in pend:
            self.assertIsNone(c["source_id"])

    def test_la_busqueda_de_fuente_para_hbm_se_hizo_y_consta(self):
        """No se dejaron sin promover por pereza: se leyeron los dos
        documentos y ninguno las afirma. Esa medicion queda registrada."""
        for c in modelo.cargar_pendiente():
            if c.get("predicate"):
                self.assertIn("SIGUE SIN FUENTE", c["_estado_2026_09_07"])

    def test_los_proveedores_ya_documentados_constan_como_tales(self):
        """Samsung, SK Hynix y Micron aparecen en la MISMA frase del 10-K
        que acredita rel:0046: ya tienen fuente. No se dan de alta porque
        estaban fuera del alcance acordado, no por falta de documento, y
        la diferencia queda escrita para que nadie la confunda."""
        cab = modelo.cargar_pendiente()[0]
        listadas = {c["relacion"] for c in cab["_candidatas_documentadas_pendientes_de_alta"]}
        self.assertIn("org:samsung SUPPLIES org:nvidia", listadas)
        for c in cab["_candidatas_documentadas_pendientes_de_alta"]:
            self.assertEqual(c["fuente"], "src:nvda-10k-fy2026")
            self.assertTrue(c["literal"])


if __name__ == "__main__":
    unittest.main()
