"""Causal Path / Graph Traversal v1 -- P5A (2026-09-07).

    EVENT + KNOWLEDGE -> CAUSAL PATH

T1, T2, T3, T4 y T7 corren sobre el Knowledge REAL del seed A. T5 (ciclo)
y T6 (contradicción) usan fixtures sintéticas declaradas: el Knowledge
real no contiene ningún ciclo, y sus dos únicas relaciones DENIES no
tienen contraparte afirmativa, así que no hay contradicción que detectar.
Fabricarlas en knowledge/ sería contaminar conocimiento verificado.
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
import modelo  # noqa: E402

HOY = datetime.date(2026, 9, 7)
FIXTURES = json.load(open(os.path.join(RAIZ, "tests", "fixtures", "caminos", "casos.json"),
                          encoding="utf-8"))


def _k():
    return modelo.cargar()


class TestUnoRecorridoReal(unittest.TestCase):
    """T1: NVDA → ISSUED_BY → NVIDIA → DOMICILED_IN → US."""

    @classmethod
    def setUpClass(cls):
        cls.k = _k()
        cls.cs = caminos.descubrir("ev4:t1", "sec:NVDA.NASDAQ", cls.k, HOY, max_depth=2)

    def _t1(self):
        return [c for c in self.cs
                if [a["predicate"] for a in c["edges"]] == ["ISSUED_BY", "DOMICILED_IN"]]

    def test_el_camino_existe_y_es_verificado(self):
        t1 = self._t1()
        self.assertEqual(len(t1), 1)
        c = t1[0]
        self.assertEqual([n["entity_id"] for n in c["nodes"]],
                         ["sec:NVDA.NASDAQ", "org:nvidia", "reg:US"])
        self.assertEqual(c["validity"], "VERIFIED")
        self.assertEqual(c["depth"], 2)
        self.assertEqual(c["direction_status"], "FORWARD")

    def test_todos_los_caminos_validan(self):
        for c in self.cs:
            caminos.validar(c, self.k)

    def test_las_aristas_referencian_no_copian(self):
        """La relación sigue siendo la única fuente de verdad: si la
        proyección divergiera, el camino tendría vida propia."""
        por_id = {r["relationship_id"]: r for r in self.k["relationships"]}
        for c in self.cs:
            for a in c["edges"]:
                r = por_id[a["relationship_id"]]
                for campo in ("predicate", "source_id", "status", "support_level", "nature"):
                    self.assertEqual(a[campo], r[campo])

    def test_toda_arista_traza_hasta_una_fuente_resoluble(self):
        fuentes = {s["source_id"] for s in self.k["sources"]}
        for c in self.cs:
            for a in c["edges"]:
                self.assertIn(a["source_id"], fuentes)
            self.assertTrue(set(c["source_refs"]) <= fuentes)

    def test_las_diez_preguntas_se_responden(self):
        texto = caminos.explicar(self._t1()[0], self.k)
        for n in range(1, 11):
            self.assertIn(f"{n:2d}." if n > 9 else f" {n}.", texto)
        self.assertIn("no es signo económico", texto)

    def test_el_path_id_es_reproducible(self):
        otra = caminos.descubrir("ev4:t1", "sec:NVDA.NASDAQ", self.k, HOY, max_depth=2)
        self.assertEqual([c["path_id"] for c in self.cs], [c["path_id"] for c in otra])
        self.assertIn("rel:", self._t1()[0]["path_id"])

    def test_una_entidad_no_declarada_no_se_crea(self):
        # El ejemplo original era org:tsmc. Dejo de servir en P5C, cuando
        # TSMC entro al Knowledge con su fuente: un test que se apoya en
        # que algo NO existe caduca en cuanto ese algo se documenta, y eso
        # es exactamente lo que tiene que pasar. Se sustituye por un
        # identificador que no va a existir nunca.
        with self.assertRaises(caminos.PathError):
            caminos.descubrir("ev4:x", "org:esta-organizacion-no-esta-declarada",
                              self.k, HOY)


class TestDosRelacionProvisional(unittest.TestCase):
    """T2: BTC → EXPOSED_TO → US se marca PROVISIONAL y conserva su origen."""

    @classmethod
    def setUpClass(cls):
        cls.k = _k()
        cls.cs = [c for c in caminos.descubrir("ev4:t2", "sec:BTC", cls.k, HOY, max_depth=1)
                  if c["edges"][0]["predicate"] == "EXPOSED_TO"]

    def test_el_camino_hereda_la_provisionalidad(self):
        self.assertTrue(self.cs)
        for c in self.cs:
            self.assertEqual(c["validity"], "PROVISIONAL")
            self.assertEqual(c["edges"][0]["status"], "PROVISIONAL")

    def test_conserva_el_origen_internal_rule(self):
        fuentes = {s["source_id"]: s for s in self.k["sources"]}
        for c in self.cs:
            self.assertEqual(c["source_refs"], ["src:thesis-macro-uniforme"])
            self.assertEqual(fuentes["src:thesis-macro-uniforme"]["tipo"], "INTERNAL_RULE")

    def test_lo_declara_en_unknowns(self):
        for c in self.cs:
            self.assertTrue(any("PROVISIONAL" in u for u in c["unknowns"]))

    def test_una_provisional_contamina_todo_el_camino(self):
        """Un camino con una arista verificada y otra provisional no es
        verificado a medias: es provisional."""
        largos = [c for c in caminos.descubrir("ev4:t2b", "sec:NVDA.NASDAQ", self.k, HOY, max_depth=2)
                  if any(a["status"] == "PROVISIONAL" for a in c["edges"]) and c["depth"] == 2]
        self.assertTrue(largos)
        for c in largos:
            self.assertEqual(c["validity"], "PROVISIONAL")


class TestTresVigencia(unittest.TestCase):
    """T3: el camino cambia con la fecha, sin que cambie el Knowledge."""

    @classmethod
    def setUpClass(cls):
        cls.k = _k()

    def _alcanza_coinbase(self, fecha):
        cs = caminos.descubrir("ev4:t3", "sec:XRP", self.k, fecha, max_depth=1)
        return any(a["to"] == "ven:coinbase" for c in cs for a in c["edges"])

    def test_en_2022_no_estaba_listado(self):
        self.assertFalse(self._alcanza_coinbase(datetime.date(2022, 1, 1)))

    def test_en_2024_si(self):
        self.assertTrue(self._alcanza_coinbase(datetime.date(2024, 1, 1)))

    def test_en_2020_tambien(self):
        self.assertTrue(self._alcanza_coinbase(datetime.date(2020, 6, 1)))

    def test_la_fecha_viaja_en_el_camino(self):
        cs = caminos.descubrir("ev4:t3", "sec:XRP", self.k, datetime.date(2024, 1, 1), max_depth=1)
        for c in cs:
            self.assertEqual(c["as_of"], "2024-01-01")


class TestCuatroCaminoIncompleto(unittest.TestCase):
    """T4: NVDA hacia una entidad no financiera. Nunca se infiere el eslabón.

    Escrito en P5A, cuando NINGÚN camino llegaba. En P5C llegan cuatro,
    porque se dieron de alta org:tsmc y tech:cowos con sus filings. Lo
    que se prueba aquí no cambia — no inventar eslabones, y decir dónde
    se interrumpe el que no llega — pero se separa en dos poblaciones,
    porque afirmar hoy "ninguno llega" sería falso y afirmarlo para
    siempre habría convertido una ausencia medida en un dogma.
    """

    @classmethod
    def setUpClass(cls):
        cls.k = _k()
        cls.cs = caminos.descubrir("ev4:t4", "sec:NVDA.NASDAQ", cls.k, HOY, max_depth=3,
                                   tipos_objetivo={"product", "technology", "material"})
        cls.incompletos = [c for c in cls.cs if c["completeness"] == "PATH_INCOMPLETE"]
        cls.completos = [c for c in cls.cs if c["completeness"] == "COMPLETE"]

    def test_la_mayoria_de_caminos_sigue_sin_llegar(self):
        self.assertTrue(self.incompletos)

    def test_cada_camino_dice_donde_se_interrumpe(self):
        for c in self.incompletos:
            self.assertTrue(c["incomplete_at"])
            self.assertIn(c["incomplete_reason"], caminos.MOTIVOS_INCOMPLETO)
            self.assertTrue(any("camino incompleto en" in u for u in c["unknowns"]))

    def test_el_que_llega_llega_por_conocimiento_documentado(self):
        """No basta con que exista un camino completo: cada arista suya
        tiene que resolver a una relación con fuente."""
        self.assertTrue(self.completos)
        por_id = {r["relationship_id"]: r for r in self.k["relationships"]}
        fuentes = {s["source_id"] for s in self.k["sources"]}
        for c in self.completos:
            for a in c["edges"]:
                r = por_id[a["relationship_id"]]
                self.assertIn(r["source_id"], fuentes)

    def test_no_se_inventa_ninguna_relacion(self):
        por_id = {r["relationship_id"] for r in self.k["relationships"]}
        for c in self.cs:
            for a in c["edges"]:
                self.assertIn(a["relationship_id"], por_id)

    def test_una_entidad_solo_negada_sigue_sin_alcanzarse(self):
        """tech:defi-smart-contracts existe, pero sus únicas relaciones
        son DENIES y una negación no se recorre. Es el caso que P5C NO
        cambia: documentar CoWoS no documenta esto."""
        rels = [r for r in self.k["relationships"] if r["object"] == "tech:defi-smart-contracts"]
        self.assertTrue(rels)
        self.assertEqual({r["polarity"] for r in rels}, {"DENIES"})
        self.assertFalse(any(a["to"] == "tech:defi-smart-contracts"
                             for c in self.cs for a in c["edges"]))

    def test_una_negacion_no_es_un_camino(self):
        cs = caminos.descubrir("ev4:t4b", "sec:BTC", self.k, HOY, max_depth=2)
        self.assertFalse(any(a["to"] == "tech:defi-smart-contracts" for c in cs for a in c["edges"]))


class TestCincoCiclo(unittest.TestCase):
    """T5: A → B → C → A termina sin duplicar infinitamente."""

    def test_el_traversal_termina(self):
        cs = caminos.descubrir("ev:t5", "org:a", FIXTURES["T5_ciclo"], HOY, max_depth=6)
        self.assertTrue(cs)
        self.assertLessEqual(max(c["depth"] for c in cs), 2)

    def test_ningun_camino_repite_una_entidad(self):
        cs = caminos.descubrir("ev:t5", "org:a", FIXTURES["T5_ciclo"], HOY, max_depth=6)
        for c in cs:
            ids = [n["entity_id"] for n in c["nodes"]]
            self.assertEqual(len(ids), len(set(ids)), c["path_id"])

    def test_una_profundidad_mayor_no_produce_mas_ciclos(self):
        a = caminos.descubrir("ev:t5", "org:a", FIXTURES["T5_ciclo"], HOY, max_depth=3)
        b = caminos.descubrir("ev:t5", "org:a", FIXTURES["T5_ciclo"], HOY, max_depth=20)
        self.assertEqual(len(a), len(b))


class TestSeisContradiccion(unittest.TestCase):
    """T6: AFFIRMS y DENIES sobre el mismo triple. No se resuelve sola."""

    @classmethod
    def setUpClass(cls):
        cls.cs = caminos.descubrir("ev:t6", "org:a", FIXTURES["T6_contradiccion"], HOY, max_depth=1)

    def test_el_camino_queda_contestado(self):
        self.assertTrue(self.cs)
        for c in self.cs:
            self.assertEqual(c["validity"], "CONTESTED")

    def test_registra_que_relacion_niega_a_cual(self):
        c = self.cs[0]
        self.assertEqual(len(c["contradictions"]), 1)
        self.assertEqual(c["contradictions"][0]["relationship_id"], "rel:fx12")
        self.assertEqual(c["contradictions"][0]["contradice"], "rel:fx11")

    def test_no_se_resuelve_automaticamente(self):
        for c in self.cs:
            self.assertTrue(any("no resuelve la contradiccion" in u for u in c["unknowns"]))

    def test_la_negacion_no_se_recorre_como_arista(self):
        for c in self.cs:
            self.assertNotIn("rel:fx12", [a["relationship_id"] for a in c["edges"]])


class TestSieteProfundidad(unittest.TestCase):
    """T7: la profundidad es un límite técnico, no una alteración del Knowledge."""

    @classmethod
    def setUpClass(cls):
        cls.k = _k()

    def test_mas_profundidad_encuentra_mas_caminos(self):
        n = [len(caminos.descubrir("ev4:t7", "sec:NVDA.NASDAQ", self.k, HOY, max_depth=d))
             for d in (1, 2, 3)]
        self.assertEqual(n, sorted(n))
        self.assertLess(n[0], n[2])

    def test_los_caminos_cortos_son_los_mismos_a_cualquier_profundidad(self):
        """Aumentar la profundidad añade caminos; no cambia los que ya
        había. Si los cambiara, la profundidad estaría alterando el
        conocimiento en vez de limitar la búsqueda."""
        d1 = {c["path_id"] for c in caminos.descubrir("ev4:t7", "sec:NVDA.NASDAQ", self.k, HOY, max_depth=1)}
        d3 = {c["path_id"] for c in caminos.descubrir("ev4:t7", "sec:NVDA.NASDAQ", self.k, HOY, max_depth=3)}
        self.assertTrue(d1 <= d3)

    def test_el_limite_de_profundidad_se_distingue_de_la_falta_de_conocimiento(self):
        cs = caminos.descubrir("ev4:t7", "sec:NVDA.NASDAQ", self.k, HOY, max_depth=1,
                               tipos_objetivo={"product", "technology", "material"})
        self.assertEqual({c["incomplete_reason"] for c in cs}, {"DEPTH_LIMIT"})
        hondo = caminos.descubrir("ev4:t7", "sec:NVDA.NASDAQ", self.k, HOY, max_depth=3,
                                  tipos_objetivo={"product", "technology", "material"})
        self.assertIn("NO_FURTHER_KNOWLEDGE", {c["incomplete_reason"] for c in hondo})


class TestInvariancia(unittest.TestCase):
    """P5A es una transformación derivada: no puede modificar nada."""

    def _huella(self, *subdirs):
        h = hashlib.sha256()
        for sub in subdirs:
            for raiz, _, fs in sorted(os.walk(os.path.join(RAIZ, sub))):
                if "__pycache__" in raiz:
                    continue
                for f in sorted(fs):
                    if f.endswith((".json", ".csv")):
                        h.update(open(os.path.join(raiz, f), "rb").read())
        return h.hexdigest()

    def test_recorrer_no_modifica_knowledge_ni_data(self):
        antes = self._huella("knowledge", "data/incoming", "data/news", "data/assets", "data/thesis")
        k = _k()
        caminos.descubrir("ev4:inv", "sec:NVDA.NASDAQ", k, HOY, max_depth=3)
        caminos.descubrir("ev4:inv", "sec:BTC", k, HOY, max_depth=2)
        self.assertEqual(antes, self._huella("knowledge", "data/incoming", "data/news",
                                             "data/assets", "data/thesis"))

    def test_el_modulo_no_abre_ningun_fichero_para_escribir(self):
        src = open(os.path.join(RAIZ, "engine", "causal", "caminos.py"), encoding="utf-8").read()
        codigo = "\n".join(l for l in src.splitlines()
                           if not l.strip().startswith("#") and '"""' not in l)
        for escritura in ("open(", "json.dump", "os.replace", "shutil."):
            self.assertNotIn(escritura, codigo)

    def test_el_esquema_no_tiene_ningun_campo_economico(self):
        """P5A sólo descubre estructura. La comprobación es sobre el
        ESQUEMA, no sobre el texto del módulo: un test que buscara
        palabras en los comentarios fallaría precisamente por la
        documentación que explica que esos campos no existen."""
        prohibidos = {"economic_direction", "probability", "probabilidad", "sign",
                      "exposure_score", "transmission_score", "bottleneck_score",
                      "impact_score", "mispricing", "opportunity_score", "magnitude",
                      "weight", "peso"}
        self.assertEqual(caminos.CAMPOS_CAMINO & prohibidos, set())
        self.assertEqual(caminos.CAMPOS_ARISTA & prohibidos, set())

    def test_ningun_camino_emitido_lleva_un_valor_economico(self):
        k = _k()
        for origen in ("sec:NVDA.NASDAQ", "sec:BTC", "reg:US"):
            for c in caminos.descubrir("ev4:eco", origen, k, HOY, max_depth=2):
                self.assertEqual(set(c), caminos.CAMPOS_CAMINO)
                for a in c["edges"]:
                    self.assertEqual(set(a), caminos.CAMPOS_ARISTA)
                    # support_level es respaldo del CONOCIMIENTO (P2), no
                    # un peso de transmisión: es ordinal y no operable.
                    self.assertIn(a["support_level"], {"ALTO", "MEDIO", "BAJO"})

    def test_direccion_estructural_no_es_signo_economico(self):
        k = _k()
        cs = caminos.descubrir("ev4:dir", "reg:US", k, HOY, max_depth=1)
        self.assertTrue(cs)
        for c in cs:
            self.assertIn(c["direction_status"], caminos.DIRECCIONES)
            for a in c["edges"]:
                self.assertIn(a["traversal_direction"], ("FORWARD", "REVERSE"))
        self.assertTrue(any(a["traversal_direction"] == "REVERSE" for c in cs for a in c["edges"]),
                        "hace falta al menos un recorrido inverso para que la distinción importe")
        for c in cs:
            self.assertTrue(any("no dice si el efecto sube o baja" in u for u in c["unknowns"]))


if __name__ == "__main__":
    unittest.main()
