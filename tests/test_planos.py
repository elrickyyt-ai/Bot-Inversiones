# -*- coding: utf-8 -*-
"""Separacion de planos PR / CRON -- D-60 (S0.11).

Partir una suite en dos tiene un riesgo evidente y uno real. El evidente es
ejecutar menos tests. El real es que un modulo desaparezca EN SILENCIO: nadie
lo ejecuta, nadie lo nota, y la cobertura se pierde sin que ningun rojo lo
anuncie.

Estos tests existen para que eso no pueda pasar. La propiedad que fijan no es
"el cron ejecuta N modulos", sino:

    todo modulo de tests/ esta clasificado          (no hay olvidados)
    la union de los tres planos == tests/           (ni sobra ni falta)
    lo que el cron no ejecuta, lo ejecuta el PR     (nada se pierde)
    ningun modulo de gobernanza entra en el cron    (no hay dependencia
                                                     indebida de historia)

Este modulo pertenece a GOVERNANCE_ONLY: valida el contrato, no el dato.
"""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "contexto"))

import estado  # noqa: E402
import suite_cron  # noqa: E402
import suite_pr  # noqa: E402

DATA = "DATA_OPERATIONAL"
GOB = "GOVERNANCE_ONLY"
AMBOS = "BOTH"


def _modulos_en_disco():
    return {f[:-3] for f in os.listdir(os.path.join(RAIZ, "tests"))
            if f.startswith("test_") and f.endswith(".py")}


def _decl():
    return estado.cargar_contrato()["ci_cron"]


class TestNingunTestOlvidado(unittest.TestCase):
    """La propiedad que hace segura la separacion."""

    def test_todo_modulo_de_tests_esta_clasificado(self):
        plano = _decl()["plano"]
        sin_clasificar = sorted(_modulos_en_disco() - set(plano))
        self.assertEqual(sin_clasificar, [],
                         f"modulos sin plano declarado: {sin_clasificar}. "
                         f"Un modulo sin clasificar no lo ejecuta nadie")

    def test_no_se_declara_ningun_modulo_que_no_exista(self):
        plano = _decl()["plano"]
        fantasmas = sorted(set(plano) - _modulos_en_disco())
        self.assertEqual(fantasmas, [], f"declarados y ausentes: {fantasmas}")

    def test_los_tres_planos_son_el_vocabulario_completo(self):
        valores = set(_decl()["plano"].values())
        self.assertTrue(valores <= {DATA, GOB, AMBOS}, sorted(valores))
        self.assertEqual(set(_decl()["planos"]), {DATA, GOB, AMBOS})

    def test_lo_que_el_cron_no_ejecuta_lo_ejecuta_el_PR(self):
        """El gate de PR corre `discover -s tests`, o sea TODO. Asi que la
        cobertura no se pierde: solo se reparte."""
        ruta = os.path.join(RAIZ, ".github", "workflows", "verificar-contexto.yml")
        with open(ruta, encoding="utf-8") as fh:
            y = fh.read()
        self.assertIn("suite_pr.py", y)
        with open(os.path.join(RAIZ, "contexto", "suite_pr.py"), encoding="utf-8") as fh:
            self.assertIn("discover", fh.read())


class TestElCronSoloEjecutaPlanoDeDatos(unittest.TestCase):

    def setUp(self):
        self.decl = _decl()
        self.cron = self.decl["cron_ejecuta"]
        self.plano = self.decl["plano"]

    def test_ninguna_entrada_del_cron_es_GOVERNANCE_ONLY(self):
        """Lo que impide que vuelva a entrar una dependencia de historia git."""
        malas = [e for e in self.cron
                 if self.plano.get(e.split(".")[0]) == GOB]
        self.assertEqual(malas, [], f"gobernanza colada en el cron: {malas}")

    def test_todo_DATA_OPERATIONAL_se_ejecuta_en_el_cron(self):
        """Al reves tambien: un modulo de datos que no corriese en el cron
        seria cobertura operacional perdida en el ciclo diario."""
        de_datos = {m for m, p in self.plano.items() if p == DATA}
        ejecutados = {e.split(".")[0] for e in self.cron}
        self.assertEqual(sorted(de_datos - ejecutados), [])

    def test_los_BOTH_entran_por_clase_y_no_por_modulo(self):
        """Un modulo mixto no puede entrar entero: arrastraria sus tests de
        gobernanza. Entra nombrando las clases operacionales."""
        for m, p in self.plano.items():
            if p != AMBOS:
                continue
            self.assertNotIn(m, self.cron, f"{m} es BOTH y entra entero")
            clases = [e for e in self.cron if e.startswith(m + ".")]
            self.assertTrue(clases, f"{m} es BOTH y no aporta ninguna clase")

    def test_cada_entrada_del_cron_existe_de_verdad(self):
        import importlib
        sys.path.insert(0, os.path.join(RAIZ, "tests"))
        for e in self.cron:
            mod, _, clase = e.partition(".")
            m = importlib.import_module(mod)
            if clase:
                self.assertTrue(hasattr(m, clase), f"{e} no existe")


class TestElContratoNoLlevaLaRegla(unittest.TestCase):
    """Misma disciplina que suite_pr: ni numeros ni listas en el codigo."""

    def setUp(self):
        with open(os.path.join(RAIZ, "contexto", "suite_cron.py"),
                  encoding="utf-8") as fh:
            self.fuente = fh.read()

    def test_la_autoridad_no_lleva_ningun_numero_de_saltos(self):
        for n in ("187", "781", "1137"):
            self.assertNotIn(n, self.fuente, n)

    def test_la_autoridad_no_lleva_la_lista_de_modulos(self):
        for m in ("test_contract", "test_storage_core", "test_impacto"):
            self.assertNotIn(m, self.fuente, m)

    def test_reutiliza_la_regla_de_suite_pr_en_vez_de_copiarla(self):
        self.assertIn("_pr.evaluar", self.fuente)
        self.assertNotIn("def evaluar", self.fuente)
        self.assertIs(suite_cron._pr, suite_pr)

    def test_sin_seleccion_declarada_no_asume_que_son_todos(self):
        sel, _d = suite_cron.declaracion({"ci_cron": {}})
        self.assertEqual(sel, ())

    def test_los_dos_perfiles_estan_declarados(self):
        for p in suite_cron.PERFILES:
            self.assertIsNotNone(suite_cron.esperados(p), p)


class TestElCronNoDependeDeHistoriaGit(unittest.TestCase):
    """La razon de ser de todo esto."""

    def test_el_workflow_del_cron_NO_pide_historia_completa(self):
        ruta = os.path.join(RAIZ, ".github", "workflows",
                            "actualizar-datos-libres.yml")
        with open(ruta, encoding="utf-8") as fh:
            y = fh.read()
        # Solo YAML EJECUTABLE: el comentario que explica por que no lo lleva
        # contiene la cadena, y prohibirla ahi seria prohibir documentarlo.
        ejecutable = "\n".join(l for l in y.splitlines()
                               if not l.lstrip().startswith("#"))
        self.assertNotIn("fetch-depth", ejecutable,
                         "el cron no debe pedir historia: valida datos, no gobernanza")
        self.assertIn("suite_cron.py", ejecutable)

    def test_el_gate_de_PR_SI_pide_historia_completa(self):
        ruta = os.path.join(RAIZ, ".github", "workflows", "verificar-contexto.yml")
        with open(ruta, encoding="utf-8") as fh:
            self.assertIn("fetch-depth: 0", fh.read())

    def test_los_modulos_que_dependen_de_git_estan_todos_en_gobernanza(self):
        """Medido ejecutando la suite sobre un clon --depth 1, no por nombre:
        estos 7 fueron exactamente los que fallaron alli."""
        medidos = ("test_alcance_bloque", "test_ci_pr", "test_cierre_bloque",
                   "test_contexto_completo", "test_invariantes_f1",
                   "test_reconciliacion", "test_superficie_durable")
        for m in medidos:
            self.assertIn(_decl()["plano"][m], (GOB, AMBOS), m)

    def test_el_contrato_declara_el_riesgo_del_paso_en_vacio(self):
        """Bajo shallow hay tests que pasan SIN comprobar nada. Por eso el
        criterio no es 'no falla en shallow'."""
        self.assertRegex(_decl()["paso_en_vacio"], r"(?i)sin comprobar nada")


if __name__ == "__main__":
    unittest.main(verbosity=2)
