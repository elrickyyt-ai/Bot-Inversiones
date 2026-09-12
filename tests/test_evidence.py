"""Evidence v1 -- P3 (2026-09-06).

Las doce demostraciones exigidas, más las que hacen falta para que
"Evidence es derivada y aditiva" sea una propiedad comprobada y no una
promesa: que no toca el Data Contract, que no escribe en Knowledge y que
una tesis nunca produce Evidence.

Los tests pesados corren sobre US (1.805 filas, el activo más pequeño con
métricas medidas y derivadas) en vez de sobre las 507.330: la semántica
es la misma y la suite sigue tardando segundos.
"""
import datetime
import hashlib
import json
import os
import re
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "engine", "evidence"))

import adaptadores  # noqa: E402
import construir  # noqa: E402
import esquema  # noqa: E402

ACTIVO = "US"


from _parquet import requiere_parquet  # noqa: E402


def _evidencia(asset_id=ACTIVO):
    return list(adaptadores.evidencia_de_metricas([asset_id]))


@requiere_parquet
class TestReversibilidad(unittest.TestCase):
    """(1) original → Evidence → reconstrucción inequívoca."""

    def test_reconstruccion_campo_a_campo_sin_diferencias(self):
        revisadas, difs = construir.verificar_reversibilidad(2000)
        self.assertGreater(revisadas, 1000)
        self.assertEqual(difs, [], difs[:5])

    def test_la_reconstruccion_cubre_todas_las_columnas_del_contrato(self):
        """Que no haya diferencias no vale si se comparan tres columnas."""
        st = adaptadores._mod("contract", "storage")
        idx = adaptadores.indice_entidades()
        fila = next(iter(st.resolve(st.read_incoming_rows(ACTIVO))))
        ev = adaptadores.adaptar_metrica(fila, idx[ACTIVO])
        volvio = adaptadores.reconstruir_metrica(ev, st.asset_type_of(ACTIVO))
        self.assertEqual(set(volvio), set(st.COLUMNS))

    def test_el_id_es_determinista(self):
        """Evidence es regenerable: si el id cambiara entre ejecuciones,
        derived_from apuntaría a filas que ya no existen."""
        a, b = _evidencia(), _evidencia()
        self.assertEqual([x["evidence_id"] for x in a], [x["evidence_id"] for x in b])


@requiere_parquet
class TestConservacionDeTiposYValores(unittest.TestCase):
    """(2) y (3)."""

    @classmethod
    def setUpClass(cls):
        cls.ev = _evidencia()

    def test_los_tipos_se_conservan(self):
        for e in self.ev:
            if e["value_num"] is not None:
                self.assertIsInstance(e["value_num"], (int, float))
                self.assertNotIsInstance(e["value_num"], bool)
            if e["value_text"] is not None:
                self.assertIsInstance(e["value_text"], str)
            self.assertIsInstance(e["derived_from"], list)
            self.assertIsInstance(e["source_rank"], int)

    def test_value_num_xor_value_text(self):
        for e in self.ev:
            tiene = (e["value_num"] is not None, e["value_text"] is not None)
            self.assertIn(tiene, [(True, False), (False, True)], e["evidence_id"])

    def test_el_validador_rechaza_los_dos_a_la_vez(self):
        e = dict(self.ev[0], value_num=1.0, value_text="x")
        with self.assertRaises(esquema.EvidenceError):
            esquema.validar_fila(e)

    def test_el_validador_rechaza_una_fila_sin_valor(self):
        e = dict(self.ev[0], value_num=None, value_text=None)
        with self.assertRaises(esquema.EvidenceError):
            esquema.validar_fila(e)


@requiere_parquet
class TestTemporalidad(unittest.TestCase):
    """(4) y (5)."""

    @classmethod
    def setUpClass(cls):
        cls.ev = _evidencia()

    def test_known_at_nunca_es_anterior_a_occurred_at(self):
        for e in self.ev:
            self.assertLessEqual(e["occurred_at"][:10], e["known_at"][:10], e["evidence_id"])

    def test_el_validador_rechaza_saber_algo_antes_de_que_ocurra(self):
        e = dict(self.ev[0], occurred_at="2030-01-01", known_at="2026-09-06T00:00:00+00:00")
        with self.assertRaises(esquema.EvidenceError):
            esquema.validar_fila(e)

    def test_las_marcas_de_tiempo_vienen_de_la_fila_de_origen(self):
        """No hay fabricación: se comparan contra la fila del contrato."""
        st = adaptadores._mod("contract", "storage")
        idx = adaptadores.indice_entidades()
        for fila in list(st.resolve(st.read_incoming_rows(ACTIVO)))[:50]:
            e = adaptadores.adaptar_metrica(fila, idx[ACTIVO])
            self.assertEqual(e["occurred_at"], fila["data_as_of"].isoformat())
            self.assertEqual(e["known_at"], fila["retrieved_at"].isoformat())

    def test_los_adaptadores_no_llaman_a_now(self):
        """El defecto que P1 tuvo que corregir tres veces en tres motores
        distintos. Aquí se impide por construcción."""
        for fichero in ("adaptadores.py", "esquema.py"):
            src = open(os.path.join(RAIZ, "engine", "evidence", fichero), encoding="utf-8").read()
            codigo = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
            self.assertNotIn("now()", codigo, fichero)
            self.assertNotIn("today()", codigo, fichero)


@requiere_parquet
class TestProcedencia(unittest.TestCase):
    """(6) y (8)."""

    @classmethod
    def setUpClass(cls):
        cls.metricas = _evidencia()
        cls.noticias, cls.sin_resolver = adaptadores.evidencia_de_noticias()

    def test_toda_fila_declara_su_escala_de_procedencia(self):
        for e in self.metricas + self.noticias:
            self.assertIn(e["source_scale"], esquema.SOURCE_SCALES, e["evidence_id"])
            self.assertIsNotNone(e["source_rank"])

    def test_las_dos_escalas_no_se_unifican(self):
        """P0 demostró que source_priority significa cosas distintas
        según el dominio. Evidence conserva el rango Y el nombre de la
        escala, en vez de fabricar una tercera escala común."""
        self.assertEqual({e["source_scale"] for e in self.metricas}, {"market_data_priority"})
        self.assertEqual({e["source_scale"] for e in self.noticias}, {"journalistic_tier"})

    def test_relevance_solo_existe_en_noticias_y_no_es_confidence(self):
        for e in self.metricas:
            self.assertIsNone(e["relevance"], e["evidence_id"])
        self.assertTrue(any(e["relevance"] is not None for e in self.noticias))
        self.assertNotIn("confidence", esquema.CAMPOS)
        self.assertNotIn("confidence_pct", esquema.CAMPOS)

    def test_los_dos_unicos_numeros_de_calidad_son_del_origen(self):
        """No se inventa confidence: lo que viaja son los valores que la
        fila de origen ya traía, con nombre que lo dice."""
        self.assertIn("origin_confidence_pct", esquema.CAMPOS)
        self.assertIn("origin_data_quality_pct", esquema.CAMPOS)
        st = adaptadores._mod("contract", "storage")
        idx = adaptadores.indice_entidades()
        for fila in list(st.resolve(st.read_incoming_rows(ACTIVO)))[:50]:
            e = adaptadores.adaptar_metrica(fila, idx[ACTIVO])
            self.assertEqual(e["origin_confidence_pct"], fila.get("confidence_pct"))
            self.assertEqual(e["origin_data_quality_pct"], fila.get("data_quality_pct"))


@requiere_parquet
class TestDerivacion(unittest.TestCase):
    """(7)."""

    @classmethod
    def setUpClass(cls):
        cls.ev = _evidencia("IBM")

    def test_derived_from_resuelve_siempre(self):
        ids = {e["evidence_id"] for e in self.ev}
        for e in self.ev:
            for origen in e["derived_from"]:
                self.assertIn(origen, ids, f"{e['evidence_id']} apunta a {origen}")

    def test_hay_derivaciones_de_verdad(self):
        """Una lista vacía también 'resuelve': el test anterior no prueba
        nada si nadie deriva de nadie."""
        self.assertTrue([e for e in self.ev if e["derived_from"]])

    def test_lo_medido_no_deriva_de_nada(self):
        for e in self.ev:
            if e["nature"] == "MEASURED":
                self.assertEqual(e["derived_from"], [], e["evidence_id"])

    def test_el_validador_rechaza_medido_con_derivacion(self):
        e = dict(self.ev[0], nature="MEASURED", derived_from=["ev:met:x"])
        with self.assertRaises(esquema.EvidenceError):
            esquema.validar_fila(e)

    def test_method_y_method_ref_son_cosas_distintas(self):
        """La comprobación de reversibilidad demostró que un solo campo
        no puede con las dos: qué se hizo y dónde está documentado."""
        derivadas = [e for e in self.ev if e["nature"] == "DERIVED" and e["method"]]
        self.assertTrue(derivadas)
        e = derivadas[0]
        self.assertNotEqual(e["method"], e["method_ref"])


class TestNoticias(unittest.TestCase):
    """(9) y la resolución de entidades."""

    @classmethod
    def setUpClass(cls):
        cls.ev, cls.sin_resolver = adaptadores.evidencia_de_noticias()

    def test_una_noticia_no_se_convierte_en_event(self):
        """P3 no hace extracción de eventos. Una noticia produce
        observaciones sobre una entidad, no un suceso con actores y
        magnitud."""
        for e in self.ev:
            self.assertIn(e["claim_type"], {"OBSERVATION", "ASSERTION"})
            self.assertNotIn("event", e["evidence_id"])
            self.assertEqual(e["domain"], "noticias")
        src = open(os.path.join(RAIZ, "engine", "evidence", "adaptadores.py"), encoding="utf-8").read()
        self.assertNotIn("def extraer_evento", src)

    def test_se_conserva_el_contenido_del_articulo(self):
        for e in self.ev:
            self.assertTrue(e["headline"])
            self.assertIsNotNone(e["summary"])
            self.assertTrue(e["source_ref"])

    def test_la_entidad_de_una_noticia_es_mencionada_no_medida(self):
        for e in self.ev:
            self.assertEqual(e["entity_role"], "MENTIONED")

    def test_una_entidad_no_resoluble_se_registra_y_no_se_crea(self):
        for caso in self.sin_resolver:
            self.assertIn("asset_id", caso)
            self.assertIn("motivo", caso)
        antes = {x["entity_id"] for x in adaptadores._mod("knowledge", "modelo").cargar()["entities"]}
        adaptadores.evidencia_de_noticias()
        despues = {x["entity_id"] for x in adaptadores._mod("knowledge", "modelo").cargar()["entities"]}
        self.assertEqual(antes, despues)

    def test_la_etiqueta_deriva_del_score(self):
        etiquetas = [e for e in self.ev if e["metric"] == "news_sentiment_label"]
        scores = {e["evidence_id"] for e in self.ev if e["metric"] == "news_sentiment"}
        self.assertTrue(etiquetas)
        for e in etiquetas:
            self.assertEqual(len(e["derived_from"]), 1)
            self.assertIn(e["derived_from"][0], scores)


@requiere_parquet
class TestFronteras(unittest.TestCase):
    """(10) y (11): lo que Evidence NO hace."""

    def test_una_tesis_nunca_genera_evidence(self):
        src = open(os.path.join(RAIZ, "engine", "evidence", "adaptadores.py"), encoding="utf-8").read()
        self.assertNotIn("thesis", src.lower())
        self.assertNotIn("data/thesis", src)
        for e in _evidencia() + adaptadores.evidencia_de_noticias()[0]:
            self.assertNotIn(e["domain"], {"tesis", "thesis"})

    def test_generar_evidence_no_modifica_knowledge(self):
        d = os.path.join(RAIZ, "knowledge")
        def huella():
            h = hashlib.sha256()
            for raiz, _, ficheros in sorted(os.walk(d)):
                for f in sorted(ficheros):
                    if f.endswith(".json"):
                        h.update(open(os.path.join(raiz, f), "rb").read())
            return h.hexdigest()
        antes = huella()
        list(adaptadores.evidencia_de_metricas([ACTIVO]))
        adaptadores.evidencia_de_noticias()
        self.assertEqual(antes, huella())

    def test_generar_evidence_no_modifica_el_data_contract(self):
        d = os.path.join(RAIZ, "data")
        def huella():
            h = hashlib.sha256()
            for sub in ("incoming", "news", "assets", "thesis"):
                p = os.path.join(d, sub)
                for f in sorted(os.listdir(p)):
                    h.update(open(os.path.join(p, f), "rb").read())
            return h.hexdigest()
        antes = huella()
        list(adaptadores.evidencia_de_metricas([ACTIVO]))
        adaptadores.evidencia_de_noticias()
        self.assertEqual(antes, huella())

    def test_evidence_no_tiene_funciones_de_escritura_sobre_sus_fuentes(self):
        src = open(os.path.join(RAIZ, "engine", "evidence", "adaptadores.py"), encoding="utf-8").read()
        self.assertNotIn("open(", src.replace('open(p, encoding="utf-8")', ""))

    def test_los_vocabularios_de_nature_siguen_siendo_disjuntos(self):
        """Evidence y Knowledge comparten el NOMBRE del campo `nature`
        con vocabularios distintos. Es seguro sólo mientras sean
        disjuntos: entonces un valor identifica sin ambigüedad su capa.
        Si alguien añadiera ASSERTED aquí o DERIVED allí, este test falla
        antes de que el error llegue a ninguna parte."""
        kn = adaptadores._mod("knowledge", "modelo")
        self.assertTrue(set(esquema.NATURES).isdisjoint(set(kn.NATURALEZAS)))
        self.assertIn("INFERRED", esquema.NATURES)
        self.assertEqual(kn.NATURALEZA_PROHIBIDA, "INFERRED")

    def test_ningun_adaptador_de_p3_emite_inferred(self):
        """INFERRED está en el vocabulario para P5. Ningún adaptador de
        P3 lo produce: P3 no infiere nada."""
        todas = _evidencia() + adaptadores.evidencia_de_noticias()[0]
        self.assertNotIn("INFERRED", {e["nature"] for e in todas})


@requiere_parquet
class TestConceptosYCobertura(unittest.TestCase):
    """(12) y el puente con P2."""

    @classmethod
    def setUpClass(cls):
        cls.kn = adaptadores._mod("knowledge", "modelo").cargar()

    def test_todo_concept_id_existe_en_knowledge(self):
        declarados = {c["concept_id"] for c in self.kn["concepts"]}
        for metric, concepto in adaptadores.CONCEPTO_DE_METRICA.items():
            self.assertIn(concepto, declarados, metric)

    def test_los_dos_casos_documentados_estan_mapeados(self):
        m = adaptadores.CONCEPTO_DE_METRICA
        self.assertEqual(m["cpi_yoy_pct"], "inflation_yoy")
        self.assertEqual(m["hicp_yoy_pct"], "inflation_yoy")
        self.assertEqual(m["fed_funds_pct"], "policy_rate")
        self.assertEqual(m["ecb_deposit_rate_pct"], "policy_rate")

    def test_la_no_comparabilidad_de_policy_rate_se_respeta(self):
        """Mapear dos métricas al mismo concepto NO las vuelve
        comparables: el concepto lo declara y Evidence no lo contradice."""
        c = [x for x in self.kn["concepts"] if x["concept_id"] == "policy_rate"][0]
        self.assertFalse(c["comparable_entre_entidades"])
        self.assertTrue(c["nota_comparabilidad"])
        inf = [x for x in self.kn["concepts"] if x["concept_id"] == "inflation_yoy"][0]
        self.assertTrue(inf["comparable_entre_entidades"])

    def test_toda_entidad_de_evidence_existe_en_knowledge(self):
        ids = {e["entity_id"] for e in self.kn["entities"]}
        for e in _evidencia() + adaptadores.evidencia_de_noticias()[0]:
            self.assertIn(e["entity_id"], ids)

    def test_la_cobertura_es_medible(self):
        ev = _evidencia()
        st = adaptadores._mod("contract", "storage")
        origen = len(st.resolve(st.all_layers(st.asset_type_of(ACTIVO), ACTIVO)))
        self.assertEqual(len(ev), origen, "metrics → Evidence debe ser 1:1")
        self.assertTrue(all(esquema.validar_fila(e) for e in ev))


if __name__ == "__main__":
    unittest.main()
