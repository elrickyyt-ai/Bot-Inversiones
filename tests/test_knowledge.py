"""Knowledge Model v1 -- P2 (2026-09-06).

Lo que se prueba no es que el JSON esté bien formado. Es que una
relación se puede trazar hasta su fuente, que tiene vigencia temporal
REAL (no un campo decorativo) y que no se puede confundir con una
inferencia del propio sistema.

Criterio de aceptación global: el conjunto válido pasa los trece; el
bloque B de knowledge/pendiente/ falla a propósito, y por eso vive
fuera del directorio que el validador lee.
"""
import copy
import datetime
import json
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "engine", "knowledge"))

import consulta  # noqa: E402
import modelo  # noqa: E402


class TestElConjuntoValido(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()

    def test_valida_sin_incidencias(self):
        self.assertEqual(modelo.validar(self.k), [])

    def test_hay_conocimiento_que_validar(self):
        """Un conjunto vacío también pasaría el validador."""
        self.assertGreater(len(self.k["entities"]), 10)
        self.assertGreater(len(self.k["relationships"]), 10)
        self.assertTrue(self.k["sources"])

    def test_toda_relacion_traza_a_una_fuente_con_localizador(self):
        """Test 1 del diseño: conocer algo y poder citarlo son cosas
        distintas, y sólo la segunda entra aquí."""
        fuentes = {s["source_id"]: s for s in self.k["sources"]}
        for r in self.k["relationships"]:
            self.assertIn(r["source_id"], fuentes, r["relationship_id"])
            self.assertTrue(fuentes[r["source_id"]]["localizador"])
            self.assertTrue(r["statement"], f"{r['relationship_id']} sin statement")

    def test_toda_relacion_tiene_vigencia(self):
        for r in self.k["relationships"]:
            self.assertTrue(r["valid_from"], r["relationship_id"])
            datetime.date.fromisoformat(r["valid_from"])
            if r["valid_to"]:
                self.assertLess(r["valid_from"], r["valid_to"], r["relationship_id"])

    def test_ninguna_relacion_guarda_un_numero(self):
        """Riesgo 2 del diseño: si una cifra necesita vivir en Knowledge,
        el modelo está mal. Knowledge representa estructura; los valores
        observados son del Data Contract."""
        for r in self.k["relationships"]:
            for campo, valor in r.items():
                self.assertNotIsInstance(valor, (int, float),
                                         f"{r['relationship_id']}.{campo} es numérico")

    def test_todo_asset_id_del_contrato_resuelve_a_una_entidad(self):
        """Impide que Knowledge se desincronice del Data Contract en
        silencio."""
        d = os.path.join(RAIZ, "data", "assets")
        for f in sorted(os.listdir(d)):
            aid = f[:-5]
            ents = consulta.resolver(self.k, aid)
            self.assertEqual(len(ents), 1, f"{aid} resuelve a {[e['entity_id'] for e in ents]}")


class TestLaInferenciaNoEntra(unittest.TestCase):
    """Test 2 del diseño. Knowledge representa el mundo que el sistema
    considera conocido; la inferencia es una operación SOBRE ese
    conocimiento y no se persiste junto a él."""

    def test_inferred_no_esta_en_el_vocabulario(self):
        self.assertNotIn("INFERRED", modelo.NATURALEZAS)

    def test_el_validador_rechaza_una_relacion_inferida(self):
        k = modelo.cargar()
        r = copy.deepcopy(k["relationships"][0])
        r["relationship_id"] = "rel:9999"
        r["nature"] = "INFERRED"
        k["relationships"].append(r)
        errores = modelo.validar(k)
        self.assertTrue(any("INFERRED" in e for e in errores), errores)

    def test_ninguna_relacion_del_seed_es_inferida(self):
        for r in modelo.cargar()["relationships"]:
            self.assertIn(r["nature"], modelo.NATURALEZAS)


class TestLaVigenciaEsReal(unittest.TestCase):
    """No basta con que el campo exista: tiene que cambiar lo que el
    sistema responde. El caso es real y sus fechas están medidas sobre
    data/history/crypto/XRP/, no estimadas."""

    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()

    def _xrp_coinbase(self, fecha):
        return [r for r in self.k["relationships"]
                if r["subject"] == "sec:XRP" and r["object"] == "ven:coinbase"
                and modelo.vigente(r, fecha)]

    def test_antes_del_deslistado_si_estaba_listado(self):
        self.assertEqual(len(self._xrp_coinbase(datetime.date(2020, 6, 1))), 1)

    def test_durante_el_deslistado_no_lo_estaba(self):
        """905 días sin ningún punto de Coinbase. Consultar el grafo en
        esa ventana NO debe devolver la relación."""
        self.assertEqual(self._xrp_coinbase(datetime.date(2022, 1, 1)), [])

    def test_tras_la_reanudacion_vuelve_a_estarlo(self):
        self.assertEqual(len(self._xrp_coinbase(datetime.date(2024, 1, 1))), 1)

    def test_la_entidad_no_se_destruye_al_deslistarse(self):
        """La identidad sigue existiendo aunque deje de cotizar en un
        mercado: por eso el estado vive en la relación, no borrando la
        entidad."""
        xrp = [e for e in self.k["entities"] if e["entity_id"] == "sec:XRP"][0]
        self.assertEqual(xrp["status"], "ACTIVE")
        self.assertIn(xrp["status"], modelo.ESTADOS_ENTIDAD)


class TestLaReglaDelCodigoNoEsUnHechoDelMundo(unittest.TestCase):
    """BTC → EXPOSED_TO → US no puede elevarse de "regla que el software
    aplica" a "hecho estructural" sin evidencia externa."""

    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()
        cls.exp = [r for r in cls.k["relationships"] if r["predicate"] == "EXPOSED_TO"]

    def test_toda_exposicion_derivada_del_codigo_es_provisional(self):
        self.assertTrue(self.exp)
        for r in self.exp:
            self.assertEqual(r["status"], "PROVISIONAL", r["relationship_id"])
            self.assertEqual(r["nature"], "ASSERTED", r["relationship_id"])
            self.assertEqual(r["support_level"], "BAJO", r["relationship_id"])

    def test_su_fuente_esta_marcada_como_regla_interna(self):
        fuentes = {s["source_id"]: s for s in self.k["sources"]}
        for r in self.exp:
            self.assertEqual(fuentes[r["source_id"]]["tipo"], "INTERNAL_RULE")

    def test_la_consulta_avisa_de_que_es_provisional(self):
        avisos = consulta._avisos(self.k, self.exp[:1])
        self.assertTrue(avisos)
        self.assertIn("PROVISIONAL", avisos[0])
        self.assertIn("regla del propio motor", avisos[0])


class TestNegarExigeFuente(unittest.TestCase):
    """Test 8 del diseño: una negación sin comprobación es una ausencia
    disfrazada. Las tres ausencias de TVL tenían tres causas distintas y
    el mismo aspecto."""

    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()

    def test_las_negaciones_del_seed_tienen_fuente(self):
        negaciones = [r for r in self.k["relationships"] if r["polarity"] == "DENIES"]
        self.assertTrue(negaciones)
        fuentes = {s["source_id"] for s in self.k["sources"]}
        for r in negaciones:
            self.assertIn(r["source_id"], fuentes)
            self.assertTrue(r["statement"])

    def test_una_negacion_sin_fuente_es_rechazada(self):
        k = modelo.cargar()
        r = copy.deepcopy([x for x in k["relationships"] if x["polarity"] == "DENIES"][0])
        r["relationship_id"] = "rel:9998"
        r["source_id"] = None
        k["relationships"].append(r)
        self.assertTrue(any("sin source_id" in e for e in modelo.validar(k)))

    def test_dot_no_tiene_una_negacion_porque_su_ausencia_si_es_un_hueco(self):
        """BTC y XRP no tienen TVL por naturaleza; DOT lo tiene ausente
        por una incidencia de DefiLlama. No es lo mismo y no se declara
        igual."""
        negados = {r["subject"] for r in self.k["relationships"]
                   if r["polarity"] == "DENIES" and r["object"] == "tech:defi-smart-contracts"}
        self.assertEqual(negados, {"sec:BTC", "sec:XRP"})


class TestCoherenciaEstructural(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()

    def test_sujeto_y_objeto_existen(self):
        ids = {e["entity_id"] for e in self.k["entities"]}
        for r in self.k["relationships"]:
            self.assertIn(r["subject"], ids)
            self.assertIn(r["object"], ids)

    def test_los_tipos_encajan_con_el_predicado(self):
        k = modelo.cargar()
        r = copy.deepcopy(k["relationships"][0])
        r.update({"relationship_id": "rel:9997", "subject": "ven:NYSE",
                  "predicate": "ISSUED_BY", "object": "org:nvidia"})
        k["relationships"].append(r)
        self.assertTrue(any("no admite un sujeto" in e for e in modelo.validar(k)))

    def test_un_alias_no_apunta_a_dos_entidades(self):
        k = modelo.cargar()
        otro = [e for e in k["entities"] if e["entity_id"] == "org:nvidia"][0]
        otro["aliases"] = [{"scheme": "ticker", "value": "NVDA", "venue": "ven:NASDAQ",
                            "valid_from": None, "valid_to": None, "source_id": "src:dimasset-equity"}]
        self.assertTrue(any("alias ambiguo" in e for e in modelo.validar(k)))

    def test_el_concepto_con_varias_implementaciones_declara_comparabilidad(self):
        for c in self.k["concepts"]:
            if len(c.get("implementaciones") or []) > 1:
                self.assertIsNotNone(c.get("comparable_entre_entidades"), c["concept_id"])
                if c["comparable_entre_entidades"] is False:
                    self.assertTrue(c.get("nota_comparabilidad"), c["concept_id"])

    def test_el_concepto_de_percentil_lleva_la_ventana_como_parametro(self):
        """posicion_rango_90d_pct y posicion_rango_52s_pct no son dos
        implementaciones equivalentes: son el mismo operador con
        parámetros distintos, y la diferencia es un factor de 4."""
        c = [x for x in self.k["concepts"] if x["concept_id"] == "percentil_en_ventana"][0]
        ventanas = {i["parametros"]["ventana"] for i in c["implementaciones"]}
        self.assertIn("90d", ventanas)
        self.assertIn("52w", ventanas)
        self.assertFalse(c["comparable_entre_entidades"])


class TestElBloqueBNoValidaAProposito(unittest.TestCase):
    """La cadena de NVIDIA se entrega documentada y fuera del conjunto
    válido. Que el sistema rechace medio seed no es un fallo de la carga
    inicial: es el comportamiento correcto."""

    def test_pendiente_no_se_carga_como_conocimiento(self):
        ids = {r["relationship_id"] for r in modelo.cargar()["relationships"]}
        self.assertNotIn(None, ids)
        candidatas = [x for x in modelo.cargar_pendiente() if x.get("predicate")]
        self.assertTrue(candidatas, "el bloque B debería existir, documentado")

    def test_si_se_intentara_cargar_el_validador_lo_rechazaria(self):
        k = modelo.cargar()
        k["relationships"] += [x for x in modelo.cargar_pendiente() if x.get("predicate")]
        errores = modelo.validar(k)
        self.assertTrue(any("sin source_id" in e for e in errores))

    def test_cada_candidata_declara_el_documento_que_habria_que_citar(self):
        for c in modelo.cargar_pendiente():
            if c.get("predicate"):
                self.assertTrue(c.get("documento_a_citar"), c["subject"])
                self.assertIn("tipo_de_fuente_esperado", c)

    def test_no_hay_camino_desde_nvda_a_una_entidad_no_financiera(self):
        """La consecuencia observable de que el bloque B no esté cargado:
        el sistema demuestra que no conoce el mundo en vez de completarlo."""
        k = modelo.cargar()
        tipos = {e["entity_id"]: e["type"] for e in k["entities"]}
        no_financieras = {e for e, t in tipos.items() if t in consulta.TIPOS_NO_FINANCIEROS}
        alcanzables = set()
        for r in k["relationships"]:
            if r["polarity"] == "AFFIRMS" and r["subject"] == "sec:NVDA.NASDAQ":
                alcanzables.add(r["object"])
        self.assertEqual(alcanzables & no_financieras, set())


if __name__ == "__main__":
    unittest.main()
