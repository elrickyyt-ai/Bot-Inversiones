# -*- coding: utf-8 -*-
"""Bala trazadora de F1 -- BLOCK 1A (2026-09-12).

    STATE QUERY  ->  STATE SURFACE  ->  CANONICAL REFERENCE
                 ->  VALIDATOR      ->  PASS
                 ->  M1 divergencia canonica    -> FAIL
                 ->  M2 duplicacion como verdad -> FAIL

UNA sola consulta, de clase CODE-ANCHORED, sobre
`modelo.PREDICADOS_NO_CAUSALES`. Se eligio un frozenset y no un escalar
como RULE_VERSION a proposito: es el caso mas pequeno que OBLIGA a decidir
como se compara una coleccion, que es donde viven los fallos reales de
divergencia (orden, tipo, normalizacion).

Esta bala NO cubre AMBIGUOUS, HUMAN-ASSERTED, UNDECLARED, presupuesto L0,
indice de alcanzabilidad ni la reubicacion de D-PRD-1. Es deliberado: la
bala demuestra el MECANISMO, no las capacidades.

NINGUNA mutacion toca el repositorio real: M1 es en memoria sobre el
modulo ya importado y M2 sobre una copia en memoria de la superficie.
"""
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "contexto"))
sys.path.insert(0, os.path.join(RAIZ, "engine", "knowledge"))

import estado  # noqa: E402
import validar  # noqa: E402
import modelo  # noqa: E402

CONSULTA = "predicados_no_causales"


def _resultado(informe, query_id=CONSULTA):
    return {r["query_id"]: r for r in informe["resultados"]}.get(query_id)


class TestLaBalaTrazadora(unittest.TestCase):
    """El recorrido completo, extremo a extremo."""

    def test_1_la_consulta_esta_declarada_como_code_anchored(self):
        cs = {c["query_id"]: c for c in estado.consultas()}
        self.assertIn(CONSULTA, cs,
                      "el registro de STATE QUERY no declara la consulta de la bala: "
                      "el mecanismo de STATE QUERY no existe todavia")
        self.assertEqual(cs[CONSULTA]["class"], "CODE-ANCHORED")

    def test_2_la_consulta_no_almacena_su_valor(self):
        """Arco 1 del modelo de contexto: se referencia, no se duplica."""
        cs = {c["query_id"]: c for c in estado.consultas()}
        self.assertIn(CONSULTA, cs, "consulta no declarada")
        self.assertNotIn("value", cs[CONSULTA])
        self.assertNotIn("valor", cs[CONSULTA])

    def test_3_la_superficie_la_referencia_en_canonical_references(self):
        bloques = estado.bloques(estado.texto_superficie())
        self.assertIn("CANONICAL REFERENCES", bloques)
        cs = {c["query_id"]: c for c in estado.consultas()}
        self.assertIn(CONSULTA, cs, "consulta no declarada")
        self.assertIn(cs[CONSULTA]["canonical_source"], bloques["CANONICAL REFERENCES"],
                      "la superficie no referencia la fuente canonica de la consulta")

    def test_4_el_validador_la_resuelve_y_da_PASS(self):
        informe = validar.validar()
        r = _resultado(informe)
        self.assertIsNotNone(r, "el validador no produce resultado para la consulta: "
                                "el mecanismo de STATE QUERY no existe todavia")
        self.assertTrue(r["ok"], r.get("motivo"))

    def test_5_el_valor_resuelto_es_el_de_la_fuente_canonica(self):
        informe = validar.validar()
        r = _resultado(informe)
        self.assertIsNotNone(r, "el validador no produce resultado para la consulta")
        self.assertEqual(sorted(r["valor_resuelto"]),
                         sorted(modelo.PREDICADOS_NO_CAUSALES))


class TestM1DivergenciaCanonica(unittest.TestCase):
    """M1 -- la fuente canonica cambia y el contexto durable no se entera.

    La mutacion es EN MEMORIA sobre el modulo ya importado. `_resolver`
    usa importlib, que devuelve el modulo cacheado en sys.modules, asi que
    ve el parche sin que nada se escriba en engine/."""

    def setUp(self):
        self.original = modelo.PREDICADOS_NO_CAUSALES

    def tearDown(self):
        modelo.PREDICADOS_NO_CAUSALES = self.original

    def test_mutar_la_fuente_canonica_produce_FAIL(self):
        modelo.PREDICADOS_NO_CAUSALES = frozenset(self.original - {"SUCCEEDED_BY"})
        r = _resultado(validar.validar())
        self.assertFalse(r["ok"], "mutar la fuente canonica TIENE que fallar")

    def test_el_motivo_es_divergencia_canonica(self):
        modelo.PREDICADOS_NO_CAUSALES = frozenset(self.original - {"SUCCEEDED_BY"})
        r = _resultado(validar.validar())
        self.assertIn(validar.DIVERGENCIA_CANONICA, r["motivo"])

    def test_sin_mutacion_vuelve_a_pasar(self):
        """Que el fallo sea consecuencia de la mutacion y no de otra cosa."""
        self.assertTrue(_resultado(validar.validar())["ok"])

    def test_la_mutacion_no_escribe_en_engine(self):
        import hashlib
        ruta = os.path.join(RAIZ, "engine", "knowledge", "modelo.py")
        antes = hashlib.sha256(open(ruta, "rb").read()).hexdigest()
        modelo.PREDICADOS_NO_CAUSALES = frozenset({"LO_QUE_SEA"})
        validar.validar()
        self.assertEqual(antes, hashlib.sha256(open(ruta, "rb").read()).hexdigest())


class TestM2DuplicacionComoVerdad(unittest.TestCase):
    """M2 -- la superficie almacena el valor en vez de referenciarlo.

    Es la mutacion que importa: M1 prueba que el validador compara; M2
    prueba el Arco 1 del modelo de contexto, que es el invariante mas
    profundo de F1 y el que alguien romperia "simplificando".

    La mutacion es sobre una COPIA EN MEMORIA de la superficie."""

    def _superficie_con_el_valor_pegado(self):
        texto = estado.texto_superficie()
        valor = ", ".join(sorted(modelo.PREDICADOS_NO_CAUSALES))
        return texto.replace("## CANONICAL REFERENCES",
                             f"## CANONICAL REFERENCES\n\nPredicados no causales: {valor}")

    def test_almacenar_el_valor_en_la_superficie_produce_FAIL(self):
        r = _resultado(validar.validar(superficie=self._superficie_con_el_valor_pegado()))
        self.assertFalse(r["ok"], "duplicar el valor TIENE que fallar")

    def test_el_motivo_es_duplicacion_como_verdad(self):
        r = _resultado(validar.validar(superficie=self._superficie_con_el_valor_pegado()))
        self.assertIn(validar.DUPLICACION_COMO_VERDAD, r["motivo"])

    def test_almacenar_el_valor_en_el_registro_tambien_falla(self):
        """La otra mitad del Arco 1: tampoco vale duplicarlo en el contrato."""
        c = estado.cargar_contrato()
        c["state_queries"][0]["value"] = sorted(modelo.PREDICADOS_NO_CAUSALES)
        r = _resultado(validar.validar(contrato=c))
        self.assertFalse(r["ok"])
        self.assertIn(validar.DUPLICACION_COMO_VERDAD, r["motivo"])

    def test_la_superficie_real_no_contiene_el_valor(self):
        self.assertNotIn(", ".join(sorted(modelo.PREDICADOS_NO_CAUSALES)),
                         estado.texto_superficie())

    def test_la_mutacion_no_escribe_en_el_repositorio(self):
        import hashlib
        ruta = estado.ruta_superficie()
        antes = hashlib.sha256(open(ruta, "rb").read()).hexdigest()
        validar.validar(superficie=self._superficie_con_el_valor_pegado())
        self.assertEqual(antes, hashlib.sha256(open(ruta, "rb").read()).hexdigest())


class TestM1YM2SonDistintas(unittest.TestCase):
    """Condicion de parada 4: si los motivos coincidieran, el validador no
    distinguiria dos violaciones distintas y no estaria terminado."""

    def test_los_motivos_son_distintos(self):
        original = modelo.PREDICADOS_NO_CAUSALES
        try:
            modelo.PREDICADOS_NO_CAUSALES = frozenset(original - {"SUCCEEDED_BY"})
            m1 = _resultado(validar.validar())["motivo"]
        finally:
            modelo.PREDICADOS_NO_CAUSALES = original
        texto = estado.texto_superficie()
        valor = ", ".join(sorted(modelo.PREDICADOS_NO_CAUSALES))
        m2 = _resultado(validar.validar(
            superficie=texto.replace("## CANONICAL REFERENCES",
                                     f"## CANONICAL REFERENCES\n\n{valor}")))["motivo"]
        self.assertNotEqual(m1, m2)
        self.assertIn(validar.DIVERGENCIA_CANONICA, m1)
        self.assertIn(validar.DUPLICACION_COMO_VERDAD, m2)


class TestElSliceEsUnSlice(unittest.TestCase):
    """P-3: T2-SLICE / T4-SLICE / T6-SLICE no son T2/T4/T6 completos."""

    def test_solo_esta_declarada_la_clase_code_anchored(self):
        c = estado.cargar_contrato()
        self.assertEqual(list(c["clases_declaradas_en_este_slice"]), ["CODE-ANCHORED"])
        self.assertEqual(c["clases_pendientes_de_T2_completo"],
                         ["AMBIGUOUS", "HUMAN-ASSERTED"])

    def test_la_superficie_tiene_exactamente_los_cinco_bloques(self):
        self.assertEqual(list(estado.bloques(estado.texto_superficie())),
                         list(estado.BLOQUES_SUPERFICIE))

    def test_el_slice_no_implementa_ambiguous_ni_human_asserted_ni_undeclared(self):
        fuente = open(os.path.join(RAIZ, "contexto", "validar.py"), encoding="utf-8").read()
        cuerpo = fuente.split('"""', 2)[-1]
        for pendiente in ("AMBIGUOUS", "HUMAN_ASSERTED", "UNDECLARED"):
            self.assertNotIn(f'{pendiente} = "', cuerpo,
                             f"{pendiente} es T6 completo, no entra en la bala")


if __name__ == "__main__":
    unittest.main(verbosity=2)
