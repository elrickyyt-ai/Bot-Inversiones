"""Economic Causal Mechanism & Direction v1 -- P5B (2026-09-07).

    Event + CausalPath + Evidence -> CausalAssessment

Los casos sintéticos usan EXCLUSIVAMENTE predicados del vocabulario
cerrado de P2. No usan CONSUMES ni PRODUCES, y tampoco los mapean a
USES/SUPPLIES, porque no son equivalentes: USES puede ser tecnología o
infraestructura mientras CONSUMES implica flujo, y SUPPLIES es
organización→organización mientras PRODUCES es organización→producto.

El test real usa un Event de P4 y un camino de P5A sobre el Knowledge
real, y su resultado es UNKNOWN. Eso no es un fallo: es lo que hay.
"""
import datetime
import hashlib
import json
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "engine", "causal"))
sys.path.insert(0, os.path.join(RAIZ, "engine", "knowledge"))

import caminos  # noqa: E402
import mecanismos  # noqa: E402
import modelo  # noqa: E402
import valoracion  # noqa: E402

HOY = datetime.date(2026, 9, 7)
FX = json.load(open(os.path.join(RAIZ, "tests", "fixtures", "valoracion", "casos.json"),
                    encoding="utf-8"))


def _valorar(nombre, rel_id):
    """Ejecuta la tubería completa: P5A descubre el camino, P5B lo valora.
    El camino se elige por la relación que debe contener, no por su
    longitud: así el test dice exactamente qué está probando."""
    c = FX[nombre]
    cs = caminos.descubrir(c["event"]["event_id"], c["origen"], c["knowledge"],
                           HOY, c["profundidad"])
    camino = next(x for x in cs
                  if rel_id in [a["relationship_id"] for a in x["edges"]])
    a = valoracion.valorar(c["event"], camino, c["evidence"], c["knowledge"],
                           modelo.vigente, HOY)
    valoracion.validar(a)
    return a


def _tramo(a, variable):
    return next(t for t in a["segments"] if t["affected_variable"] == variable)


class TestVocabularioYSeparacion(unittest.TestCase):
    def test_las_tres_direcciones_son_disjuntas(self):
        """Tercera aparición del patrón de source_priority. polarity,
        traversal_direction y economic_direction son conceptos distintos:
        si compartieran un valor volverían a confundirse."""
        polarity = set(modelo.POLARIDADES)
        traversal = set(caminos.DIRECCIONES)
        economica = set(mecanismos.DIRECCIONES_CAMINO)
        self.assertTrue(polarity.isdisjoint(traversal))
        self.assertTrue(polarity.isdisjoint(economica))
        self.assertTrue(traversal.isdisjoint(economica),
                        "MIXED no puede estar en las dos: por eso el resumen económico "
                        "usa DIVERGENT")
        self.assertIn("MIXED", traversal)
        self.assertIn("DIVERGENT", economica)

    def test_no_se_usan_consumes_ni_produces(self):
        """No están en el vocabulario de P2 y NO se mapean a los que sí
        están, porque no son equivalentes."""
        for caso in FX.values():
            if not isinstance(caso, dict) or "knowledge" not in caso:
                continue
            preds = {r["predicate"] for r in caso["knowledge"]["relationships"]}
            self.assertEqual(preds & {"CONSUMES", "PRODUCES"}, set())
            self.assertTrue(preds <= set(modelo.PREDICADOS), preds)

    def test_el_vocabulario_de_mecanismos_es_pequeno(self):
        self.assertEqual(len(mecanismos.MECANISMOS), 7)
        for nombre, m in mecanismos.MECANISMOS.items():
            self.assertTrue(m["relacion"], nombre)
            self.assertTrue(m["bloqueo"], nombre)
            self.assertIsInstance(m["necesita"], list)

    def test_ninguna_variable_de_mecanismo_existe_en_evidence_v1(self):
        """El motivo por el que el test real dará UNKNOWN. Si algún día
        deja de ser cierto, este test lo dirá."""
        sys.path.insert(0, os.path.join(RAIZ, "engine", "evidence"))
        import adaptadores
        metricas = {e["metric"] for e in adaptadores.evidencia_de_metricas(["US"], limite=3000)}
        self.assertEqual(metricas & set(mecanismos.VARIABLES_MECANISMO), set())


class TestUnoCadena(unittest.TestCase):
    """T1: demanda del cliente sube y se propaga al proveedor."""

    @classmethod
    def setUpClass(cls):
        cls.a = _valorar("T1_cadena", "rel:v03")

    def test_el_ingreso_del_proveedor_sube_con_soporte_completo(self):
        t = _tramo(self.a, "revenue")
        self.assertEqual((t["economic_direction"], t["support"]), ("POSITIVE", "SUPPORTED"))
        self.assertEqual(t["rule_id"], "R3")
        self.assertTrue(t["evidence_ids"])

    def test_cada_tramo_declara_la_regla_que_lo_produjo(self):
        for t in self.a["segments"]:
            self.assertTrue(t["rule_id"])
        self.assertEqual(self.a["rule_version"], mecanismos.RULE_VERSION)


class TestDosCoste(unittest.TestCase):
    """T2: el coste sube directamente; el margen sólo bajo supuesto."""

    @classmethod
    def setUpClass(cls):
        cls.a = _valorar("T2_coste", "rel:v10")

    def test_el_coste_sube_con_soporte_completo(self):
        t = _tramo(self.a, "cost")
        self.assertEqual((t["economic_direction"], t["support"]), ("POSITIVE", "SUPPORTED"))
        self.assertEqual(t["assumptions"], [])

    def test_el_margen_baja_pero_solo_bajo_un_supuesto_declarado(self):
        """El signo del margen NO es una consecuencia mecánica del coste:
        depende de si la empresa puede repercutirlo."""
        t = _tramo(self.a, "margin")
        self.assertEqual((t["economic_direction"], t["support"]), ("NEGATIVE", "PARTIAL"))
        self.assertTrue(t["assumptions"])
        self.assertIn("repercutir", t["assumptions"][0])

    def test_el_resumen_no_confunde_coste_con_divergencia(self):
        """Coste arriba y margen abajo son la MISMA historia. Sumar
        signos de variables distintas daría DIVERGENT por error."""
        self.assertEqual(self.a["overall_direction"], "NEGATIVE")

    def test_un_signo_con_supuesto_nunca_puede_estar_supported(self):
        malo = dict(self.a)
        malo["segments"] = [dict(_tramo(self.a, "margin"), support="SUPPORTED")]
        with self.assertRaises(valoracion.AssessmentError):
            valoracion.validar(malo)


class TestTresSustitucionYAusencia(unittest.TestCase):
    """La corrección más importante de P5B: ausencia ≠ evidencia de ausencia."""

    def test_sin_fila_substitutes_el_poder_de_precio_es_solo_parcial(self):
        """Que Knowledge no contenga X SUBSTITUTES Y significa que NO
        CONOCEMOS un sustituto, no que no exista."""
        t = _tramo(_valorar("T1_cadena", "rel:v03"), "pricing_power")
        self.assertEqual((t["economic_direction"], t["support"]), ("POSITIVE", "PARTIAL"))
        self.assertTrue(t["assumptions"])
        self.assertTrue(any("no es evidencia de ausencia" in u for u in t["unknowns"]))

    def test_con_ausencia_verificada_si_hay_soporte_completo(self):
        """Una relación DENIES SUBSTITUTES es una comprobación, no un
        hueco: sólo ella permite afirmar el poder de precio."""
        t = _tramo(_valorar("T1b_ausencia_verificada", "rel:v03"), "pricing_power")
        self.assertEqual((t["economic_direction"], t["support"]), ("POSITIVE", "SUPPORTED"))
        self.assertEqual(t["assumptions"], [])

    def test_con_sustituto_afirmado_no_se_puede_inferir(self):
        t = _tramo(_valorar("T3_sustitucion", "rel:v03"), "pricing_power")
        self.assertEqual((t["economic_direction"], t["support"]), ("UNKNOWN", "UNKNOWN"))
        self.assertEqual(t["mechanism"], "SUBSTITUTION")

    def test_la_sustitucion_bloquea_un_mecanismo_no_el_camino_entero(self):
        con = _valorar("T3_sustitucion", "rel:v03")
        sin = _valorar("T1_cadena", "rel:v03")
        self.assertEqual(_tramo(con, "revenue")["economic_direction"],
                         _tramo(sin, "revenue")["economic_direction"])
        self.assertEqual(_tramo(con, "cost")["economic_direction"],
                         _tramo(sin, "cost")["economic_direction"])

    def test_los_tres_estados_de_sustitucion_son_distintos(self):
        estados = {
            _tramo(_valorar(n, "rel:v03"), "pricing_power")["support"]
            for n in ("T1_cadena", "T1b_ausencia_verificada", "T3_sustitucion")}
        self.assertEqual(estados, {"PARTIAL", "SUPPORTED", "UNKNOWN"})


class TestCuatroCambioDeSigno(unittest.TestCase):
    """T4: un camino puede cambiar de signo entre tramos."""

    @classmethod
    def setUpClass(cls):
        cls.a = _valorar("T1_cadena", "rel:v03")

    def test_hay_tramos_de_los_dos_signos(self):
        signos = {t["economic_direction"] for t in self.a["segments"]}
        self.assertIn("POSITIVE", signos)
        self.assertIn("NEGATIVE", signos)

    def test_el_resumen_es_divergente_y_no_un_signo_unico(self):
        self.assertEqual(self.a["overall_direction"], "DIVERGENT")

    def test_divergent_no_colisiona_con_mixed_de_p5a(self):
        self.assertNotIn("DIVERGENT", caminos.DIRECCIONES)
        self.assertNotIn("MIXED", mecanismos.DIRECCIONES_CAMINO)


class TestCincoSinEvidencia(unittest.TestCase):
    """T5: la relación estructural existe, la variable no."""

    @classmethod
    def setUpClass(cls):
        cls.a = _valorar("T5_sin_evidencia", "rel:v10")

    def test_la_direccion_es_desconocida(self):
        self.assertEqual(self.a["overall_direction"], "UNKNOWN")
        self.assertEqual(self.a["support"], "UNKNOWN")

    def test_dice_exactamente_que_evidencia_falta(self):
        t = self.a["segments"][0]
        self.assertEqual(t["economic_direction"], "UNKNOWN")
        self.assertTrue(t["requires_evidence"])
        self.assertIn("price(mat:x)", t["requires_evidence"])
        self.assertEqual(t["evidence_ids"], [])

    def test_una_relacion_estructural_no_basta(self):
        """A USES X demuestra el vínculo. No demuestra el signo."""
        c = FX["T5_sin_evidencia"]
        self.assertTrue(c["knowledge"]["relationships"])
        self.assertEqual(c["evidence"], [])
        self.assertTrue(any("no hay Evidence" in u for u in self.a["unknowns"]))

    def test_unknown_no_significa_neutral(self):
        self.assertNotEqual(self.a["overall_direction"], "NEUTRAL")


class TestSeisEventoSinImpulso(unittest.TestCase):
    def test_una_opinion_publicada_no_mueve_ninguna_variable(self):
        a = _valorar("T6_evento_sin_impulso", "rel:v03")
        self.assertEqual(a["overall_direction"], "UNKNOWN")
        self.assertTrue(any("no mueve ninguna variable" in u for u in a["unknowns"]))
        self.assertIsNone(mecanismos.IMPULSO_POR_ACCION["sentiment_assertion"])


class TestReal(unittest.TestCase):
    """Un Event real de P4 y un camino real de P5A sobre el Knowledge real.
    El resultado es UNKNOWN, y el valor del test está en que diga por qué."""

    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()
        evento = {"event_id": "ev4:sec:NVDA.NASDAQ:price_change:2026-09-04:UP:10+",
                  "primary_entity": "sec:NVDA.NASDAQ", "action": "price_change",
                  "direction": "UP"}
        cs = caminos.descubrir(evento["event_id"], "sec:NVDA.NASDAQ", cls.k, HOY, max_depth=2)
        cls.camino = next(c for c in cs
                          if [a["predicate"] for a in c["edges"]] == ["ISSUED_BY", "DOMICILED_IN"])
        cls.a = valoracion.valorar(evento, cls.camino, [], cls.k, modelo.vigente, HOY)

    def test_valida(self):
        self.assertTrue(valoracion.validar(self.a))

    def test_las_aristas_de_identidad_no_transmiten_nada(self):
        for t in self.a["segments"]:
            self.assertEqual(t["mechanism"], mecanismos.NO_MECHANISM)
            self.assertEqual(t["economic_direction"], "UNKNOWN")
            self.assertEqual(t["rule_id"], "R0")

    def test_el_resultado_es_unknown_y_dice_por_que(self):
        self.assertEqual(self.a["overall_direction"], "UNKNOWN")
        self.assertEqual(self.a["support"], "UNKNOWN")
        self.assertTrue(any("identidad" in u or "clasificacion" in u for u in self.a["unknowns"]))

    def test_ninguna_variable_de_mecanismo_esta_medida(self):
        """El motivo de fondo, medido sobre el Knowledge y la Evidence
        reales. En P5B eran DOS motivos a la vez: no había ninguna
        relación económica afirmativa Y no había ninguna variable medida.
        P5C resolvió el primero (rel:0046/0047/0048, con filings). El
        segundo sigue en pie, y es el que de verdad bloquea: aunque ahora
        hay cadena que recorrer, no hay nada que observar sobre ella."""
        economicos = {"SUPPLIES", "USES", "SUBSTITUTES"}
        afirmativas = [r for r in self.k["relationships"]
                       if r["predicate"] in economicos and r["polarity"] == "AFFIRMS"]
        self.assertTrue(afirmativas, "P5C dio de alta la primera cadena económica real")

        sys.path.insert(0, os.path.join(RAIZ, "engine", "evidence"))
        import adaptadores
        medidas = {e["metric"] for e in adaptadores.evidencia_de_metricas(["NVDA"], limite=3000)}
        self.assertEqual(medidas & set(mecanismos.VARIABLES_MECANISMO), set())


class TestInvariantes(unittest.TestCase):
    def _huella(self, *subdirs):
        h = hashlib.sha256()
        for sub in subdirs:
            for raiz, _, fs in sorted(os.walk(os.path.join(RAIZ, sub))):
                if "__pycache__" in raiz:
                    continue
                for f in sorted(fs):
                    if f.endswith((".json", ".csv", ".py")):
                        with open(os.path.join(raiz, f), "rb") as fh:
                            h.update(fh.read())
        return h.hexdigest()

    def test_valorar_no_modifica_nada(self):
        antes = self._huella("knowledge", "engine/evidence", "engine/events",
                             "engine/causal", "data/incoming", "data/news")
        _valorar("T1_cadena", "rel:v03")
        modelo.cargar()
        self.assertEqual(antes, self._huella("knowledge", "engine/evidence", "engine/events",
                                             "engine/causal", "data/incoming", "data/news"))

    def test_p5a_no_se_ha_tocado(self):
        """P5A queda cerrado y aprobado."""
        src = open(os.path.join(RAIZ, "engine", "causal", "caminos.py"), encoding="utf-8").read()
        self.assertNotIn("mecanismos", src)
        self.assertNotIn("valoracion", src)

    def test_ningun_modulo_de_p5b_escribe_en_disco(self):
        for f in ("mecanismos.py", "valoracion.py"):
            src = open(os.path.join(RAIZ, "engine", "causal", f), encoding="utf-8").read()
            codigo = "\n".join(l for l in src.splitlines()
                               if not l.strip().startswith("#") and '"""' not in l)
            for escritura in ("open(", "json.dump", "os.replace", "shutil."):
                self.assertNotIn(escritura, codigo, f)

    def test_p5b_no_emite_ningun_numero(self):
        """Ni magnitud, ni peso, ni probabilidad, ni confidence. Se
        comprueba sobre el esquema y sobre lo emitido, no sobre la prosa."""
        prohibidos = {"probability", "impact_score", "exposure", "transmission",
                      "confidence", "weight", "magnitude", "score"}
        self.assertEqual(valoracion.CAMPOS_ASSESSMENT & prohibidos, set())
        self.assertEqual(valoracion.CAMPOS_TRAMO & prohibidos, set())
        a = _valorar("T1_cadena", "rel:v03")
        for t in a["segments"]:
            for v in t.values():
                self.assertNotIsInstance(v, float)

    def test_el_assessment_referencia_evidencia_no_la_copia(self):
        a = _valorar("T1_cadena", "rel:v03")
        ids = {e["evidence_id"] for e in FX["T1_cadena"]["evidence"]}
        self.assertTrue(set(a["evidence_ids"]) <= ids)
        for t in a["segments"]:
            self.assertTrue(set(t["evidence_ids"]) <= ids)


if __name__ == "__main__":
    unittest.main()
