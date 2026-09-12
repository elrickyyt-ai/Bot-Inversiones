# -*- coding: utf-8 -*-
"""Superficie durable -- S0.3.

Fija la separacion de las tres clases, que es lo que hace que el contexto sea
recuperable sin leer el historico:

    DURABLE      lo que NO puede deducirse de nada        -> la superficie
    REGENERABLE  lo que se calcula desde codigo/estado    -> se REFERENCIA
    HISTORICAL   decisiones, informes, narrativa          -> se APUNTA

El riesgo que estos tests vigilan no es que falte algo: es que la superficie
se convierta en un segundo histórico, o en una copia de cifras que envejecen
en silencio. Por eso la mayoria comprueba AUSENCIAS.
"""
import os
import re
import subprocess
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "contexto"))

import estado  # noqa: E402
import validar  # noqa: E402


def _superficie():
    return estado.texto_superficie()


class TestLosOchoBloques(unittest.TestCase):

    def test_la_superficie_tiene_los_bloques_declarados_en_orden(self):
        presentes = [l[3:].strip() for l in _superficie().splitlines()
                     if l.startswith("## ")]
        self.assertEqual(presentes, list(estado.BLOQUES_SUPERFICIE))

    def test_los_tres_bloques_de_S03_estan(self):
        for b in ("ACTIVE BLOCK", "OPEN DEBTS", "CONTINUITY RULES"):
            self.assertIn(b, estado.BLOQUES_SUPERFICIE, b)

    def test_un_bloque_no_declarado_sigue_fallando(self):
        """La guarda anti-deriva no se relajo al pasar de cinco a ocho."""
        sup = _superficie() + "\n## UN BLOQUE DE MAS\n\ncontenido\n"
        ok, motivo = validar.guardas_superficie(sup)
        self.assertFalse(ok)
        self.assertIn(validar.BLOQUE_DESCONOCIDO, motivo)

    def test_el_numero_de_bloques_no_esta_escrito_en_el_validador(self):
        """Paso de cinco a ocho sin tocar validar.py: el numero vive en
        estado.BLOQUES_SUPERFICIE y alli solamente."""
        with open(os.path.join(RAIZ, "contexto", "validar.py"),
                  encoding="utf-8") as fh:
            fuente = fh.read()
        i = fuente.index("def guardas_superficie")
        cuerpo = fuente[i:i + 1200]
        for palabra in ("cinco", "SEXTO", "septimo", "ocho"):
            self.assertNotIn(palabra, cuerpo, palabra)


class TestLoDurableEsLoQueNoSeDeduce(unittest.TestCase):
    """Lo unico que la superficie debe ALMACENAR."""

    def setUp(self):
        self.txt = _superficie()

    def test_la_rama_canonica_esta_declarada(self):
        """Ninguna ejecucion puede deducir que rama es la autoridad. Su
        ausencia hizo que una sesion entera concluyese, sobre la rama
        equivocada, que el proyecto no existia."""
        self.assertIn("claude/session-abz5pi", self.txt)
        self.assertIn("D-57", self.txt)

    def test_dice_que_la_integracion_es_por_merge_y_no_por_rebase(self):
        """No es preferencia: un rebase romperia _evidencia_resoluble()."""
        self.assertRegex(self.txt, r"(?i)merge.{0,40}nunca rebase|nunca rebase")

    def test_el_bloque_activo_se_referencia_y_no_se_copia(self):
        bid = estado.cargar_contrato()["bloque_activo"]
        self.assertIn("contrato.json::bloque_activo", self.txt)
        self.assertNotIn(f"bloque activo: {bid}", self.txt.lower())

    def test_las_reglas_de_continuidad_dan_un_orden(self):
        i = self.txt.index("## CONTINUITY RULES")
        bloque = self.txt[i:self.txt.index("## HISTORICAL POINTERS")]
        self.assertRegex(bloque, r"(?m)^1\.")
        self.assertRegex(bloque, r"(?m)^8\.")
        self.assertIn("no puede implicar pérdida del estado", bloque)


class TestLoCalculableNoSeCopia(unittest.TestCase):
    """El fallo que S0 existe para no repetir: una cifra viva escrita a mano
    caduca y nada lo detecta. Paso con `f1_estado`."""

    def setUp(self):
        self.txt = _superficie()

    def test_ninguna_cifra_viva_aparece_en_la_superficie(self):
        """Tests, saltos, tokens de L0, nodos y aristas del grafo, ficheros del
        manifiesto: todo eso se obtiene ejecutando, no leyendo."""
        vivas = {
            "tests de la suite": self._tests(),
            "saltos del PR": validar._estado.cargar_contrato()["ci_pr"]["skips_esperados"],
            "tokens de L0": validar.medir_l0(validar.l0_efectivo()[0]),
            "ficheros del manifiesto": len(validar._rutas_manifiesto()),
            "componentes de arquitectura": len(validar.componentes_arquitectura()),
        }
        # `(?<![-\w])` evita el falso positivo de los IDs de decision: `D-44`
        # contiene 44 y no es una cifra viva. Lo detecto este propio test.
        for nombre, valor in vivas.items():
            self.assertNotRegex(self.txt, rf"(?<![-\w]){valor}(?![-\w])",
                                f"la superficie copia una cifra viva "
                                f"({nombre} = {valor})")

    def test_el_estado_de_cierre_se_calcula_y_no_se_afirma(self):
        self.assertIn("veredicto_cierre", self.txt)
        self.assertRegex(self.txt, r"(?i)se calcula, no se lee")

    def test_las_deudas_se_referencian_y_no_se_enumeran(self):
        i = self.txt.index("## OPEN DEBTS")
        bloque = self.txt[i:self.txt.index("## INVARIANTS")]
        self.assertIn("contrato.json::open_debt", bloque)
        # Ningun ID de deuda concreto: una lista copiada envejece sola.
        self.assertNotRegex(bloque, r"\bD[FCD]-\d\b")

    def _tests(self):
        """Cuantos tests tiene la suite AHORA. Se cuenta cargandola, no con un
        literal: un literal aqui seria la misma clase de cifra que el test
        prohibe en la superficie."""
        import unittest as _u
        return _u.defaultTestLoader.discover(os.path.join(RAIZ, "tests")).countTestCases()


class TestNoDuplicaNingunaFuente(unittest.TestCase):
    """`referencia y valida; nunca duplica como verdad`, aplicado a los tres
    documentos que la superficie apunta."""

    def setUp(self):
        self.txt = _superficie()

    def _leer(self, rel):
        with open(os.path.join(RAIZ, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_no_copia_docs_ESTADO(self):
        for linea in ("P6.2a INTEGRIDAD TEMPORAL",
                      "resolve_instrument(identifier, as_of)"):
            self.assertIn(linea, self._leer("docs/ESTADO.md"))
            self.assertNotIn(linea, self.txt)

    def test_no_copia_la_arquitectura_objetivo(self):
        for cid in ("EVENT_CLAIM", "POLICY_REGISTRY", "BROKER_ORDER"):
            self.assertNotIn(cid, self.txt, cid)

    def test_no_copia_el_texto_de_ninguna_decision(self):
        """ACTIVE DECISIONS enumera IDs; el texto vive en DECISIONES.md."""
        dec = self._leer("docs/DECISIONES.md")
        for titulo in re.findall(r"(?m)^## D-\d+ · (.+)$", dec)[:12]:
            self.assertNotIn(titulo, self.txt, titulo[:40])

    def test_apunta_al_roadmap_sin_reescribirlo(self):
        self.assertIn("P6.2", self.txt)
        self.assertIn("trazabilidad_fases_P0_P61", self.txt)
        # Pero no reproduce la tabla de fases cerradas de ESTADO.md
        self.assertNotIn("Historical Instrument Master", self.txt)


class TestLasTresClasesSonCoherentes(unittest.TestCase):

    def test_L0_declarado_coincide_con_el_efectivo(self):
        informe = validar.validar()
        self.assertEqual(informe["l0"]["declarado"], informe["l0"]["efectivo"])
        self.assertEqual(informe["incidencias"], [])

    def test_L0_sigue_bajo_el_gate(self):
        informe = validar.validar()
        self.assertLess(informe["l0"]["tokens"], validar.GATE_L0)

    def test_solo_dos_ficheros_son_DURABLE(self):
        """Anadir tres bloques no puede expandir L0: un POINTER no lo expande."""
        conjunto, _d = validar.l0_efectivo()
        self.assertEqual(sorted(conjunto),
                         ["CLAUDE.md", "contexto/ESTADO_VIGENTE.md"])

    def test_los_destinos_HISTORICAL_se_alcanzan_solo_por_POINTS(self):
        sys.path.insert(0, os.path.join(RAIZ, "contexto"))
        import grafo
        idx = grafo.indice()
        for a in idx["aristas"]:
            if a["clase_destino"] == grafo.HISTORICAL:
                self.assertEqual(a["relacion"], grafo.POINTS,
                                 f"{a['destino']} se alcanza por {a['relacion']}")

    def test_el_documento_objetivo_no_es_DURABLE_ni_HISTORICAL(self):
        """Vive en contexto/ porque docs/ lo clasificaria HISTORICAL (DF-7) y
        L0 no debe crecer con el."""
        sys.path.insert(0, os.path.join(RAIZ, "contexto"))
        import grafo
        conjunto, _d = validar.l0_efectivo()
        clase = grafo.clasificar("contexto/ARQUITECTURA_OBJETIVO.md", conjunto)
        self.assertEqual(clase, grafo.OTRO)


class TestF1SigueCerrada(unittest.TestCase):
    """S0.3 no puede reabrir lo que S0.2 cerro."""

    def test_F1_sigue_CLOSED(self):
        e, d = validar.veredicto_cierre("F1")
        self.assertEqual(e, validar.CLOSED, d["motivos"])

    def test_las_siete_obligaciones_siguen_cumpliendose(self):
        _e, d = validar.veredicto_cierre("F1")
        for k in validar.OBLIGACIONES_CIERRE:
            self.assertTrue(d["obligaciones"][k][0], k)

    def test_la_superficie_distingue_F1_cerrada_de_arquitectura_terminada(self):
        txt = _superficie()
        self.assertRegex(txt, r"(?i)no significa que la arquitectura esté")
        self.assertIn("PLANNED", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
