"""Event & Claim Layer v1 -- P4 (2026-09-07).

    SOURCE → EVIDENCE → CLAIM → EVENT CANDIDATE → EVENT

Los tests 1 y 2 corren sobre datos REALES del proyecto. Los tests 3 a 7
usan fixtures SINTÉTICAS declaradas, porque el corpus real no contiene
ninguno de esos casos: medido, 0 titulares idénticos, 1 solo par con
solapamiento léxico ≥0.5 y del mismo medio, ninguna fuente de tier 1 y
ningún par anuncio/entrada-en-vigor. Fabricarlos dentro de data/news/
sería contaminar datos reales.
"""
import json
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "engine", "events"))

import consolidar  # noqa: E402
import esquema_evento as esquema  # noqa: E402
import extractores  # noqa: E402

FIXTURES = json.load(open(os.path.join(RAIZ, "tests", "fixtures", "eventos", "casos.json"),
                          encoding="utf-8"))


def _caso(nombre):
    c = FIXTURES[nombre]
    return c["claims"], c["evidence"]


def _evento_unico(nombre):
    claims, evs = _caso(nombre)
    eventos = consolidar.consolidar(claims, evs)
    assert len(eventos) == 1, f"{nombre}: {len(eventos)} eventos, se esperaba 1"
    return eventos[0]


class TestEsquema(unittest.TestCase):
    def test_una_claim_sin_evidencia_es_rechazada(self):
        c = dict(_caso("T3_duplicacion")[0][0], evidence_ids=[])
        with self.assertRaises(esquema.EventError):
            esquema.validar_claim(c)

    def test_un_evento_sin_unknowns_es_rechazado(self):
        """La pregunta 12 es obligatoria: un evento tiene que poder
        declarar lo que no sabe."""
        e = dict(_evento_unico("T3_duplicacion"))
        del e["unknowns"]
        with self.assertRaises(esquema.EventError):
            esquema.validar_evento(e)

    def test_magnitud_sin_unidad_es_rechazada(self):
        e = dict(_evento_unico("T3_duplicacion"), unit=None)
        with self.assertRaises(esquema.EventError):
            esquema.validar_evento(e)

    def test_solo_geopolitical_admite_subtipo(self):
        """THREAT/ACTION no son estados universales."""
        e = dict(_evento_unico("T3_duplicacion"), event_subtype="THREAT")
        with self.assertRaises(esquema.EventError):
            esquema.validar_evento(e)
        ok = dict(e, event_type="GEOPOLITICAL", event_subtype="THREAT")
        self.assertTrue(esquema.validar_evento(ok))

    def test_effective_at_no_puede_ser_anterior_a_occurred_at(self):
        e = _evento_unico("T5_evento_futuro")
        malo = dict(e, temporal=dict(e["temporal"], effective_at="2026-01-01"))
        with self.assertRaises(esquema.EventError):
            esquema.validar_evento(malo)


class TestUnoXRPReal(unittest.TestCase):
    """Test 1: las 50 noticias reales, extremo a extremo."""

    @classmethod
    def setUpClass(cls):
        cls.claims, cls.evs, cls.sin_claim = consolidar.pipeline_noticias()
        cls.eventos = consolidar.consolidar(cls.claims, cls.evs)

    def test_medidas_de_la_tuberia(self):
        self.assertEqual(len(self.evs), 100)          # 50 artículos x 2 filas
        self.assertEqual(len(self.claims), 50)        # 1 claim por artículo
        self.assertLess(len(self.eventos), len(self.claims),
                        "si no se consolida nada, la deduplicación no está haciendo su trabajo")
        self.assertEqual({e["primary_entity"] for e in self.eventos}, {"sec:XRP"})

    def test_todo_valida(self):
        for c in self.claims:
            esquema.validar_claim(c)
        cpid = {c["claim_id"]: c for c in self.claims}
        for e in self.eventos:
            esquema.validar_evento(e, cpid)

    def test_los_estados_dependen_del_soporte(self):
        for e in self.eventos:
            if e["status"] == "CORROBORATED":
                self.assertGreaterEqual(e["independent_support_count"], 2)
            if e["status"] == "CANDIDATE":
                self.assertEqual(e["independent_support_count"], 1)

    def test_ninguna_noticia_se_confirma_sola(self):
        """Todas las fuentes del corpus son tier 3: ninguna es primaria,
        así que ningún evento de noticias puede salir CONFIRMED."""
        for e in self.eventos:
            self.assertFalse(e["primary_support"])
            self.assertNotEqual(e["status"], "CONFIRMED")

    def test_se_mide_lo_que_no_se_ha_sabido_extraer(self):
        """Las 100 evidencias producen claims de sentimiento y nada más.
        Lo que el titular describe queda sin extraer, y eso se declara."""
        self.assertEqual(self.sin_claim, [])
        for e in self.eventos:
            self.assertTrue(any("no se ha interpretado" in u for u in e["unknowns"]))

    def test_las_doce_preguntas_se_responden(self):
        cpid = {c["claim_id"]: c for c in self.claims}
        epid = {e["evidence_id"]: e for e in self.evs}
        texto = consolidar.explicar(self.eventos[0], cpid, epid)
        for n in range(1, 13):
            self.assertIn(f"{n:2d}." if n > 9 else f" {n}.", texto)
        self.assertIn("Lo que NO sabemos", texto)


class TestDosCuantitativoReal(unittest.TestCase):
    """Test 2: eventos observables respaldados por Evidence MEASURED."""

    @classmethod
    def setUpClass(cls):
        cls.claims, cls.evs = consolidar.pipeline_tecnico("XRP")
        cls.eventos = consolidar.consolidar(cls.claims, cls.evs)

    def test_hay_eventos_de_precio_confirmados(self):
        precio = [e for e in self.eventos if e["action"] == "price_change"]
        self.assertTrue(precio)
        for e in precio:
            self.assertTrue(e["primary_support"])
            self.assertEqual(e["status"], "CONFIRMED")
            self.assertIn(e["direction"], {"UP", "DOWN"})
            self.assertIsNotNone(e["magnitude"])
            self.assertEqual(e["unit"], "%")

    def test_estan_respaldados_por_evidencia_medida(self):
        epid = {e["evidence_id"]: e for e in self.evs}
        precio = [e for e in self.eventos if e["action"] == "price_change"][0]
        cpid = {c["claim_id"]: c for c in self.claims}
        for cid in precio["claim_ids"]:
            for eid in cpid[cid]["evidence_ids"]:
                self.assertEqual(epid[eid]["nature"], "MEASURED")

    def test_un_indicador_derivado_no_confiere_soporte_primario(self):
        vol = [e for e in self.eventos if e["action"] == "volatility_spike"]
        self.assertTrue(vol)
        for e in vol:
            self.assertFalse(e["primary_support"])
            self.assertEqual(e["status"], "CANDIDATE")
            self.assertIn("decisiones de modelo", e["status_reason"])

    def test_un_hueco_de_serie_no_es_un_movimiento_de_mercado(self):
        """XRP tiene 905 días sin datos por el deslistado de Coinbase. Un
        salto entre los dos extremos del hueco no es una variación de
        precio: el extractor sólo compara sesiones consecutivas."""
        cpid = {c["claim_id"]: c for c in self.claims}
        epid = {e["evidence_id"]: e for e in self.evs}
        import datetime
        for c in self.claims:
            if c["predicate"] != "MOVED_PRICE":
                continue
            fechas = sorted(datetime.date.fromisoformat(epid[i]["occurred_at"])
                            for i in c["evidence_ids"])
            self.assertEqual((fechas[1] - fechas[0]).days, 1, c["claim_id"])


class TestTresDuplicacion(unittest.TestCase):
    """Test 3: N Evidence → 1 Event, sin usar similitud textual."""

    def test_tres_medios_distintos_producen_un_solo_evento(self):
        e = _evento_unico("T3_duplicacion")
        self.assertEqual(e["evidence_count"], 3)
        self.assertEqual(e["independent_support_count"], 3)
        self.assertEqual(e["status"], "CORROBORATED")

    def test_tres_articulos_del_mismo_medio_no_son_tres_fuentes(self):
        """El caso que impide leer 'más artículos' como 'más confirmado'."""
        e = _evento_unico("T3b_mismo_medio")
        self.assertEqual(e["evidence_count"], 3)
        self.assertEqual(e["independent_support_count"], 1)
        self.assertEqual(e["status"], "CANDIDATE")

    def test_la_identidad_no_es_similitud_textual(self):
        """La clave son entidad, tipo, acción, fecha y magnitud. Ningún
        campo de texto libre entra en ella."""
        claims, evs = _caso("T3_duplicacion")
        clave = consolidar.identity_key(claims[0])
        self.assertEqual(len(clave), 5)
        self.assertEqual(clave[0], "sec:XRP")
        self.assertEqual(clave[2], "price_change")

    def test_el_mismo_hecho_en_dias_distintos_son_dos_eventos(self):
        claims, evs = _caso("T3_duplicacion")
        otro = dict(claims[0], claim_id="cl:t3:z",
                    temporal_ref=dict(claims[0]["temporal_ref"], occurred_at="2026-08-02"))
        self.assertEqual(len(consolidar.consolidar(claims + [otro], evs)), 2)

    def test_magnitudes_muy_distintas_no_se_confunden(self):
        claims, evs = _caso("T3_duplicacion")
        otro = dict(claims[0], claim_id="cl:t3:y", object_value=40.0)
        self.assertEqual(len(consolidar.consolidar(claims + [otro], evs)), 2)


class TestCuatroContradiccion(unittest.TestCase):
    """Test 4."""

    def test_una_negacion_deja_el_evento_disputado(self):
        e = _evento_unico("T4_contradiccion")
        self.assertEqual(e["status"], "CONTESTED")
        self.assertEqual(e["contradictory_support"], 1)

    def test_no_se_resuelve_por_mayoria(self):
        """Dos afirman y uno niega: sigue disputado. Añadir un cuarto
        que afirme tampoco lo resuelve."""
        claims, evs = _caso("T4_contradiccion")
        extra = dict(claims[0], claim_id="cl:t4:d")
        e = consolidar.consolidar(claims + [extra], evs)[0]
        self.assertEqual(e["status"], "CONTESTED")
        self.assertIn("no se resuelve por mayoria", e["status_reason"])

    def test_una_fuente_primaria_si_resuelve(self):
        claims, evs = _caso("T4_contradiccion")
        primaria = dict(evs[0], evidence_id="ev:fx:t4:p", source="SEC", source_rank=1)
        cl = dict(claims[0], claim_id="cl:t4:p", evidence_ids=["ev:fx:t4:p"])
        e = consolidar.consolidar(claims + [cl], evs + [primaria])[0]
        self.assertIn(e["status"], {"REJECTED", "CONFIRMED"})
        self.assertNotEqual(e["status"], "CONTESTED")


class TestCincoEventoFuturo(unittest.TestCase):
    """Test 5: un anuncio sobre una acción futura no es la acción."""

    def test_los_tres_momentos_quedan_separados(self):
        e = _evento_unico("T5_evento_futuro")
        t = e["temporal"]
        self.assertEqual(t["published_at"], "2026-09-10")
        self.assertEqual(t["occurred_at"], "2026-09-10")
        self.assertEqual(t["effective_at"], "2026-10-01")
        self.assertEqual(t["known_at"], "2026-09-10")

    def test_occurred_at_es_el_anuncio_no_la_aplicacion(self):
        e = _evento_unico("T5_evento_futuro")
        self.assertLess(e["temporal"]["occurred_at"], e["temporal"]["effective_at"])
        self.assertTrue(esquema.validar_evento(e))

    def test_sin_effective_at_se_declara_como_desconocido(self):
        e = _evento_unico("T3_duplicacion")
        self.assertIsNone(e["temporal"].get("effective_at"))
        self.assertTrue(any("entrada en vigor" in u for u in e["unknowns"]))


class TestSeisFuentePrimariaUnica(unittest.TestCase):
    """Test 6: una sola fuente primaria puede confirmar."""

    def test_una_fuente_primaria_confirma_sin_una_segunda(self):
        e = _evento_unico("T6_fuente_primaria_unica")
        self.assertEqual(e["independent_support_count"], 1)
        self.assertTrue(e["primary_support"])
        self.assertEqual(e["status"], "CONFIRMED")
        self.assertIn("no necesita una segunda fuente", e["status_reason"])

    def test_una_secundaria_unica_no_confirma(self):
        e = _evento_unico("T3b_mismo_medio")
        self.assertEqual(e["independent_support_count"], 1)
        self.assertEqual(e["status"], "CANDIDATE")


class TestSieteRevision(unittest.TestCase):
    def test_una_magnitud_corregida_despues_es_una_revision(self):
        e = _evento_unico("T7_revision")
        self.assertEqual(e["status"], "REVISED")


class TestLimitesArquitectonicos(unittest.TestCase):
    """Lo que P4 no hace y no puede hacer."""

    def test_p4_no_escribe_en_knowledge(self):
        import hashlib
        d = os.path.join(RAIZ, "knowledge")
        def huella():
            h = hashlib.sha256()
            for raiz, _, fs in sorted(os.walk(d)):
                for f in sorted(fs):
                    if f.endswith(".json"):
                        h.update(open(os.path.join(raiz, f), "rb").read())
            return h.hexdigest()
        antes = huella()
        claims, evs, _ = consolidar.pipeline_noticias()
        consolidar.consolidar(claims, evs)
        self.assertEqual(antes, huella())

    def test_ningun_modulo_de_p4_abre_un_fichero_para_escribir(self):
        """No basta con que hoy no escriba: no debe existir la capacidad."""
        for f in ("esquema_evento.py", "extractores.py", "consolidar.py"):
            src = open(os.path.join(RAIZ, "engine", "events", f), encoding="utf-8").read()
            codigo = "\n".join(l for l in src.splitlines()
                               if not l.strip().startswith("#") and '"""' not in l)
            for escritura in ('open(', 'json.dump', 'os.replace', 'shutil.'):
                self.assertNotIn(escritura, codigo, f"{f}: {escritura}")

    def test_los_nombres_de_modulo_de_engine_son_unicos(self):
        """Guardia estructural: `modelo` y `esquema` ya colisionaron dos
        veces entre paquetes de engine/, y la segunda rompió nueve tests
        de otra capa sin tocarla. Como los motores se importan por ruta y
        no como paquetes, dos ficheros con el mismo nombre base compiten
        por la misma entrada de sys.modules."""
        import collections
        vistos = collections.defaultdict(list)
        raiz = os.path.join(RAIZ, "engine")
        for d, _, ficheros in os.walk(raiz):
            if "_data" in d or "__pycache__" in d:
                continue
            for f in ficheros:
                if f.endswith(".py"):
                    vistos[f].append(os.path.relpath(os.path.join(d, f), raiz))
        repetidos = {k: v for k, v in vistos.items() if len(v) > 1}
        # score.py y fetch_data.py se repiten a propósito, uno por motor, y
        # adapters.py los importa borrándolos de sys.modules justo por eso.
        esperados = {"score.py", "fetch_data.py", "__init__.py"}
        self.assertEqual({k for k in repetidos} - esperados, set(),
                         f"nombres de módulo duplicados: {repetidos}")

    def test_p4_no_modifica_el_data_contract(self):
        import hashlib
        d = os.path.join(RAIZ, "data")
        def huella():
            h = hashlib.sha256()
            for sub in ("incoming", "news", "assets", "thesis"):
                p = os.path.join(d, sub)
                for f in sorted(os.listdir(p)):
                    h.update(open(os.path.join(p, f), "rb").read())
            return h.hexdigest()
        antes = huella()
        consolidar.pipeline_noticias()
        self.assertEqual(antes, huella())

    def test_no_hay_propagacion_causal_ni_impacto(self):
        for f in ("esquema_evento.py", "extractores.py", "consolidar.py"):
            src = open(os.path.join(RAIZ, "engine", "events", f), encoding="utf-8").read().lower()
            for prohibido in ("def propagar", "def impacto", "market_impact",
                              "mispricing", "opportunity_score"):
                self.assertNotIn(prohibido, src, f)

    def test_los_extractores_son_reglas_declaradas_no_analisis_de_texto(self):
        """Cada claim dice qué regla la produjo, y esa regla es
        reejecutable."""
        claims, _, _ = consolidar.pipeline_noticias()
        metodos = {c["extraction_method"] for c in claims}
        self.assertEqual(metodos, {extractores.METODO_SENTIMIENTO})
        self.assertIn("/v1", extractores.METODO_SENTIMIENTO)

    def test_ningun_extractor_de_v1_emite_announces_action(self):
        """Está en el vocabulario para poder representar un anuncio con
        efecto posterior, no porque P4 sepa extraerlo de un texto."""
        noticias, _, _ = consolidar.pipeline_noticias()
        tecnicas, _ = consolidar.pipeline_tecnico("XRP")
        self.assertNotIn("ANNOUNCES_ACTION",
                         {c["predicate"] for c in noticias + tecnicas})

    def test_una_assertion_de_evidence_no_se_vuelve_un_hecho(self):
        """Las 50 noticias son ASSERTION en Evidence; sus claims dicen que
        un medio afirma una postura, no que la postura sea cierta."""
        claims, evs, _ = consolidar.pipeline_noticias()
        self.assertEqual({e["claim_type"] for e in evs}, {"ASSERTION"})
        for c in claims:
            self.assertEqual(c["predicate"], "ASSERTS_SENTIMENT")
        self.assertIn("NO dice que la entidad sea alcista",
                      esquema.PREDICADOS["ASSERTS_SENTIMENT"])


if __name__ == "__main__":
    unittest.main()
