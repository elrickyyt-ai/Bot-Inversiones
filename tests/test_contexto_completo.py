# -*- coding: utf-8 -*-
"""Cierre de F1 -- T2, T3, T4 y T6 COMPLETOS (2026-09-12).

NO es el slice de BLOCK 1A. Aqui se exigen las tres clases, los dos
estados de respuesta, el cierre efectivo de L0 y la superficie real.

Ninguna mutacion toca el repositorio: se opera sobre copias en memoria.
"""
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "contexto"))
sys.path.insert(0, os.path.join(RAIZ, "engine", "knowledge"))

import estado      # noqa: E402
import validar     # noqa: E402


def _c():
    return estado.cargar_contrato()


def _por_clase(clase):
    return [q for q in estado.consultas() if q["class"] == clase]


class TestT2Completo(unittest.TestCase):
    """Las TRES clases y los DOS estados de respuesta."""

    def test_las_tres_clases_estan_declaradas(self):
        c = _c()
        self.assertEqual(sorted(c.get("clases", {})),
                         ["AMBIGUOUS", "CODE-ANCHORED", "HUMAN-ASSERTED"],
                         "T2 completo exige las tres clases; el slice solo tenia CODE-ANCHORED")

    def test_los_dos_estados_de_respuesta_estan_declarados(self):
        self.assertEqual(sorted(_c().get("estados_de_respuesta", {})),
                         ["DECLARED", "UNDECLARED"])

    def test_hay_consultas_de_las_tres_clases(self):
        for clase in ("CODE-ANCHORED", "AMBIGUOUS", "HUMAN-ASSERTED"):
            self.assertTrue(_por_clase(clase), f"ninguna consulta de clase {clase}")

    def test_ninguna_code_anchored_almacena_valor(self):
        for q in _por_clase("CODE-ANCHORED"):
            self.assertNotIn("value", q)
            self.assertNotIn("valor", q)

    def test_ninguna_ambiguous_almacena_valor_unico(self):
        for q in _por_clase("AMBIGUOUS"):
            self.assertNotIn("value", q)
            self.assertGreaterEqual(len(q.get("candidate_sources", [])), 2)
            self.assertIn("ambiguity_note", q)

    def test_toda_human_asserted_tiene_fecha_autoria_y_evidencia(self):
        for q in _por_clase("HUMAN-ASSERTED"):
            for campo in ("asserted_value", "asserted_at", "asserted_by", "evidence_ref"):
                self.assertIn(campo, q, f"{q['query_id']} sin {campo}")

    def test_X1_sigue_ambiguous_y_sin_resolver(self):
        x1 = [q for q in _por_clase("AMBIGUOUS") if "EXPOSED_TO" in str(q)]
        self.assertTrue(x1, "X-1 tiene que seguir registrada como AMBIGUOUS")
        self.assertNotIn("value", x1[0])
        self.assertIsNone(x1[0].get("resolution_ref", None) or None,
                          "X-1 no se resuelve en F1")

    def test_p5b_implementado_es_human_asserted(self):
        p5b = [q for q in _por_clase("HUMAN-ASSERTED") if "p5b" in q["query_id"]]
        self.assertTrue(p5b, "'¿esta P5B implementado?' tiene que seguir HUMAN-ASSERTED")


class TestT3Completo(unittest.TestCase):
    """L0 efectivo por cierre enumerable (P-2), no por suposicion."""

    def test_el_cierre_se_descubre_no_se_asume(self):
        conjunto, detalle = validar.l0_efectivo()
        self.assertIsInstance(conjunto, list)
        self.assertIn("CLAUDE.md", conjunto)
        self.assertEqual(detalle["metodo"], validar.L0_CLOSURE_VERSION)

    def test_el_cierre_refleja_el_estado_tras_T5(self):
        conjunto, _ = validar.l0_efectivo()
        self.assertIn("contexto/ESTADO_VIGENTE.md", conjunto)
        self.assertNotIn("docs/ESTADO.md", conjunto,
                         "docs/ESTADO.md dejo de ser lectura obligatoria en T5")

    def test_una_referencia_no_expande_L0(self):
        """OBLIGATORY LOAD != REFERENCE != POINTER (P-2)."""
        conjunto, _ = validar.l0_efectivo()
        for solo_puntero in ("docs/DECISIONES.md", "docs/07-protocolo-de-informes.md",
                             "informes", "contexto/historico"):
            self.assertFalse(any(solo_puntero in r for r in conjunto),
                             f"{solo_puntero} es puntero, no carga obligatoria")

    def test_una_lectura_obligatoria_CONDICIONAL_es_L2_no_L0(self):
        """El protocolo de privacidad se lee antes de tratar datos del
        usuario: es obligatorio CONDICIONAL. Su enunciado esta en L0; su
        texto integro es L2 (decision del PRD §4)."""
        conjunto, detalle = validar.l0_efectivo()
        self.assertNotIn("docs/00-protocolo-privacidad.md", conjunto)
        self.assertIn("docs/00-protocolo-privacidad.md", detalle.get("L2_condicional", []))

    def test_declarado_y_efectivo_coinciden(self):
        conjunto, _ = validar.l0_efectivo()
        self.assertEqual(sorted(_c().get("L0", [])), sorted(conjunto))

    def test_el_presupuesto_se_mide_y_pasa_el_gate(self):
        conjunto, _ = validar.l0_efectivo()
        n = validar.medir_l0(conjunto)
        self.assertIsInstance(n, int)
        self.assertGreater(n, 0)
        self.assertLessEqual(n, 12000, "gate duro L0 <= 12.000")

    def test_el_objetivo_de_10000_NO_es_criterio_de_fallo(self):
        pres = _c().get("presupuesto_L0")
        self.assertIsNotNone(pres, "el contrato no declara el presupuesto L0")
        self.assertEqual(pres["gate_duro"], 12000)
        self.assertFalse(pres["objetivo_10000_es_criterio_de_fallo"])


class TestT4Completo(unittest.TestCase):
    """S1 deja de ser placeholder."""

    def _bloques(self):
        return estado.bloques(estado.texto_superficie())

    def test_exactamente_los_cinco_bloques(self):
        self.assertEqual(list(self._bloques()), list(estado.BLOQUES_SUPERFICIE))

    def test_ningun_bloque_sigue_siendo_placeholder(self):
        for nombre, cuerpo in self._bloques().items():
            self.assertNotIn("Pendiente de T4 completo", cuerpo,
                             f"el bloque {nombre} sigue siendo un placeholder")

    def test_canonical_references_cita_todas_las_fuentes_declaradas(self):
        b = self._bloques()["CANONICAL REFERENCES"]
        for q in _por_clase("CODE-ANCHORED"):
            self.assertIn(q["canonical_source"], b, f"{q['query_id']} sin referencia en S1")

    def test_active_decisions_coincide_con_las_vigentes(self):
        b = self._bloques()["ACTIVE DECISIONS"]
        vigentes = validar.decisiones_vigentes()
        self.assertTrue(vigentes)
        for d in vigentes:
            self.assertIn(d, b, f"{d} esta vigente y no aparece en S1")

    def test_la_superficie_no_almacena_ningun_valor_canonico(self):
        for r in validar.validar()["resultados"]:
            if r["class"] == "CODE-ANCHORED":
                self.assertTrue(r["ok"], r.get("motivo"))

    def test_invariants_no_duplica_el_protocolo_de_privacidad(self):
        """CLAUDE.md ya lo resume; repetirlo seria duplicar dentro de L0."""
        b = self._bloques()["INVARIANTS"]
        self.assertNotIn("Pseudonimizar por defecto", b)
        self.assertIn("docs/00-protocolo-privacidad.md", b)


class TestT6Completo(unittest.TestCase):
    """El validador cubre las tres clases y los dos estados."""

    def test_valida_las_tres_clases(self):
        clases = {r["class"] for r in validar.validar()["resultados"]}
        self.assertEqual(clases, {"CODE-ANCHORED", "AMBIGUOUS", "HUMAN-ASSERTED"})

    def test_todo_pasa_sobre_el_estado_real(self):
        inf = validar.validar()
        fallos = [r for r in inf["resultados"] if not r["ok"]]
        self.assertEqual(fallos, [], [f["motivo"] for f in fallos])

    def test_una_pregunta_declarada_devuelve_DECLARED(self):
        e, q = validar.consultar("predicados_no_causales")
        self.assertEqual(e, validar.DECLARED)
        self.assertIsNotNone(q)

    def test_una_pregunta_no_declarada_devuelve_UNDECLARED(self):
        e, q = validar.consultar("una_pregunta_que_nadie_declaro")
        self.assertEqual(e, validar.UNDECLARED)
        self.assertIsNone(q, "UNDECLARED no puede traer un valor por defecto")

    def test_los_mecanismos_siguen_versionados(self):
        inf = validar.validar()
        self.assertEqual(inf["fingerprint_version"], "canonical-fingerprint/v1")
        self.assertEqual(inf["duplicacion_deteccion"], "heuristic/v1")

    def test_guarda_anti_deriva_sexto_bloque(self):
        texto = estado.texto_superficie() + "\n## UN SEXTO BLOQUE\n\ncontenido\n"
        ok, motivo = validar.guardas_superficie(texto)
        self.assertFalse(ok)
        self.assertIn("SEXTO", motivo.upper())

    def test_guarda_anti_deriva_alcance(self):
        ok, motivo = validar.guarda_alcance(["engine/knowledge/modelo.py"])
        self.assertFalse(ok)
        ok2, _ = validar.guarda_alcance(["contexto/validar.py"])
        self.assertTrue(ok2)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestMutacionesT2T3T4T6(unittest.TestCase):
    """Un validador que nunca ha fallado no esta demostrado.

    Todas las mutaciones son sobre copias EN MEMORIA del contrato o de la
    superficie. Ninguna escribe en el repositorio."""

    def _q(self, clase):
        c = _c()
        i, q = next((i, q) for i, q in enumerate(c["state_queries"]) if q["class"] == clase)
        return c, i, q

    def _fallo(self, contrato=None, superficie=None):
        inf = validar.validar(contrato=contrato, superficie=superficie)
        return [r for r in inf["resultados"] if not r["ok"]], inf["incidencias"]

    # --- CODE-ANCHORED ---
    def test_M_divergencia_canonica(self):
        c, i, _ = self._q("CODE-ANCHORED")
        c["state_queries"][i]["canonical_fingerprint"] = "0" * 64
        fallos, _ = self._fallo(contrato=c)
        self.assertIn(validar.DIVERGENCIA_CANONICA, fallos[0]["motivo"])

    def test_M_duplicacion_en_el_registro(self):
        c, i, q = self._q("CODE-ANCHORED")
        valor, _ = validar._resolver(q["canonical_source"])
        c["state_queries"][i]["value"] = validar._normalizar(valor)
        fallos, _ = self._fallo(contrato=c)
        self.assertIn(validar.DUPLICACION_COMO_VERDAD, fallos[0]["motivo"])

    def test_M_duplicacion_en_la_superficie(self):
        _, _, q = self._q("CODE-ANCHORED")
        valor, _ = validar._resolver(q["canonical_source"])
        sup = estado.texto_superficie() + "\n" + ", ".join(validar._normalizar(valor)) + "\n"
        fallos, _ = self._fallo(superficie=sup)
        self.assertTrue(any(validar.DUPLICACION_COMO_VERDAD in f["motivo"] for f in fallos))

    def test_M_referencia_ausente(self):
        sup = estado.texto_superficie().replace(
            "engine/knowledge/modelo.py::PREDICADOS_NO_CAUSALES", "(referencia borrada)")
        fallos, _ = self._fallo(superficie=sup)
        self.assertTrue(any(validar.REFERENCIA_AUSENTE in f["motivo"] for f in fallos))

    # --- AMBIGUOUS ---
    def test_M_ambiguedad_con_valor_unico(self):
        c, i, _ = self._q("AMBIGUOUS")
        c["state_queries"][i]["value"] = 3
        fallos, _ = self._fallo(contrato=c)
        self.assertIn(validar.AMBIGUEDAD_RESUELTA_EN_SILENCIO, fallos[0]["motivo"])

    def test_M_ambiguedad_con_una_sola_fuente(self):
        c, i, q = self._q("AMBIGUOUS")
        c["state_queries"][i]["candidate_sources"] = q["candidate_sources"][:1]
        fallos, _ = self._fallo(contrato=c)
        self.assertIn(validar.AMBIGUEDAD_RESUELTA_EN_SILENCIO, fallos[0]["motivo"])

    def test_M_ambiguedad_que_dejo_de_discrepar_CADUCA(self):
        """Si las fuentes convergen, la entrada no se auto-resuelve: caduca."""
        c, i, q = self._q("AMBIGUOUS")
        c["state_queries"][i]["candidate_sources"] = [
            q["candidate_sources"][0],
            {"canonical_source": "engine/causal/mecanismos.py::VARIABLES_MECANISMO",
             "lectura": "fuente que no comparte ningun elemento"}]
        fallos, _ = self._fallo(contrato=c)
        self.assertIn(validar.AMBIGUEDAD_RESUELTA_EN_SILENCIO, fallos[0]["motivo"])
        self.assertIn("CADUC", fallos[0]["motivo"].upper())

    def test_la_ambiguedad_real_SIGUE_discrepando(self):
        r = next(x for x in validar.validar()["resultados"] if x["class"] == "AMBIGUOUS")
        self.assertTrue(r["ok"])
        self.assertIn("EXPOSED_TO", r["discrepancia"])

    # --- HUMAN-ASSERTED ---
    def test_M_afirmacion_sin_fecha(self):
        c, i, _ = self._q("HUMAN-ASSERTED")
        c["state_queries"][i]["asserted_at"] = None
        fallos, _ = self._fallo(contrato=c)
        self.assertIn(validar.AFIRMACION_SIN_FECHA, fallos[0]["motivo"])

    def test_M_afirmacion_sin_autoria(self):
        c, i, _ = self._q("HUMAN-ASSERTED")
        c["state_queries"][i]["asserted_by"] = ""
        fallos, _ = self._fallo(contrato=c)
        self.assertIn(validar.AFIRMACION_SIN_AUTORIA, fallos[0]["motivo"])

    def test_M_evidencia_no_resoluble(self):
        c, i, _ = self._q("HUMAN-ASSERTED")
        c["state_queries"][i]["evidence_ref"] = "commit:0000000"
        fallos, _ = self._fallo(contrato=c)
        self.assertIn(validar.EVIDENCIA_NO_RESOLUBLE, fallos[0]["motivo"])

    def test_la_veracidad_NO_se_verifica(self):
        """Techo declarado: una afirmacion falsa pero bien citada pasa."""
        c, i, _ = self._q("HUMAN-ASSERTED")
        c["state_queries"][i]["asserted_value"] = "una afirmacion rotundamente falsa"
        fallos, _ = self._fallo(contrato=c)
        self.assertEqual(fallos, [], "F1 verifica trazabilidad, no veracidad")

    # --- L0 y guardas ---
    def test_M_L0_divergente(self):
        c = _c(); c["L0"] = ["CLAUDE.md"]
        _, inc = self._fallo(contrato=c)
        self.assertTrue(any(validar.L0_DIVERGENTE in i for i in inc))

    def test_M_sexto_bloque(self):
        sup = estado.texto_superficie() + "\n## UN SEXTO BLOQUE\n\ncontenido\n"
        _, inc = self._fallo(superficie=sup)
        self.assertTrue(any(validar.BLOQUE_DESCONOCIDO in i for i in inc))

    def test_M_fuera_de_alcance(self):
        """REESCRITO en S0.1 (protocolo de informes, §3). Se apoyaba en que
        engine/, data/ y knowledge/ estuviesen prohibidos en global; DF-1
        retiro esa lista porque el alcance es del BLOQUE -- S0 declara
        data/incoming/ y engine/contract/ legitimamente. La mutacion sigue
        siendo la misma: rutas que el bloque activo NO declara."""
        c = {"bloque_activo": "X", "bloques": {"X": {"escritura": ["contexto/"]}}}
        for ruta in ("engine/knowledge/modelo.py", "data/incoming/BTC_2026.csv",
                     "knowledge/entities/securities.json"):
            ok, motivo = validar.guarda_alcance([ruta], contrato=c)
            self.assertFalse(ok, ruta)
            self.assertIn(validar.FUERA_DE_ALCANCE, motivo)

    def test_ninguna_mutacion_escribio_en_el_repositorio(self):
        import hashlib
        for p in ("contexto/contrato.json", "contexto/ESTADO_VIGENTE.md", "CLAUDE.md"):
            ruta = os.path.join(RAIZ, p)
            self.assertTrue(os.path.isfile(ruta))
        # el estado real sigue dando PASS tras todas las mutaciones anteriores
        inf = validar.validar()
        self.assertEqual([r for r in inf["resultados"] if not r["ok"]], [])
        self.assertEqual(inf["incidencias"], [])
