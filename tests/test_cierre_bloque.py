# -*- coding: utf-8 -*-
"""Cierre de bloque -- D-56 (S0.4).

    CLOSED no puede ser una afirmacion HUMAN-ASSERTED.

Es la leccion de `f1_estado`: una afirmacion bien citada caduco tres commits
despues de escribirse, el mismo dia, y PASO el validador porque el mecanismo
verifica trazabilidad y no vigencia. Estos tests fijan que el cierre es un
veredicto CALCULADO sobre siete obligaciones, que caduca solo, y que la
afirmacion humana queda acotada a la intencion.

Todos los contratos de prueba son diccionarios en memoria.
"""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "contexto"))

import estado  # noqa: E402
import validar  # noqa: E402

HEAD_REAL = "f784b8591ad00606fd85c9c979688c8b9feea88d"


def _cierre(**kw):
    """Un cierre que cumple las siete obligaciones, para mutarlo."""
    base = {
        "commit_de_cierre": HEAD_REAL,
        "entregables": ["contexto/validar.py"],
        "tests": "python3 -m unittest discover -s tests",
        "validadores": ["contexto/validar.py"],
        "ultima_verificacion": {"commit": HEAD_REAL, "fecha": "2026-09-12"},
    }
    base.update(kw)
    return base


def _contrato(cierre="__base__", bid="B", activo="OTRO", desde=HEAD_REAL):
    bloque = {"escritura": ["contexto/"], "desde": desde, "hasta": None}
    if cierre is not None:
        bloque["cierre"] = _cierre() if cierre == "__base__" else cierre
    return {"bloque_activo": activo, "bloques": {bid: bloque}, "open_debt": []}


class TestCuatroEstados(unittest.TestCase):

    def test_el_vocabulario_tiene_cuatro_estados(self):
        self.assertEqual(len(validar.ESTADOS_CIERRE), 4)
        for e in ("UNDECLARED", "OPEN", "STALE", "CLOSED"):
            self.assertIn(e, validar.ESTADOS_CIERRE)

    def test_UNDECLARED_no_es_OPEN(self):
        """La ausencia de registro de cierre no es un cierre a medias:
        es que nadie lo ha declarado."""
        e, d = validar.veredicto_cierre("B", _contrato(cierre=None))
        self.assertEqual(e, validar.UNDECLARED_CIERRE)
        self.assertNotEqual(e, validar.OPEN)
        self.assertIn(validar.CIERRE_SIN_DECLARAR, d["motivos"][0])

    def test_las_siete_obligaciones_estan_declaradas(self):
        self.assertEqual(len(validar.OBLIGACIONES_CIERRE), 7)
        e, d = validar.veredicto_cierre("B", _contrato())
        self.assertEqual(sorted(d["obligaciones"]),
                         sorted(validar.OBLIGACIONES_CIERRE))

    def test_un_cierre_completo_da_CLOSED(self):
        e, d = validar.veredicto_cierre("B", _contrato())
        self.assertEqual(e, validar.CLOSED, d["motivos"])


class TestCadaObligacionPuedeFallar(unittest.TestCase):
    """Una obligacion que nunca ha impedido un cierre no esta demostrada."""

    def _falla(self, **kw):
        e, d = validar.veredicto_cierre("B", _contrato(cierre=_cierre(**kw)))
        return e, d

    def test_1_entregable_ausente(self):
        e, d = self._falla(entregables=["informes/no_existe.md"])
        self.assertEqual(e, validar.OPEN)
        self.assertFalse(d["obligaciones"]["entregables"][0])

    def test_2_sin_comando_de_tests(self):
        e, d = self._falla(tests="")
        self.assertEqual(e, validar.OPEN)
        self.assertFalse(d["obligaciones"]["tests"][0])

    def test_3_validador_no_resoluble(self):
        e, d = self._falla(validadores=["contexto/no_existe.py"])
        self.assertEqual(e, validar.OPEN)
        self.assertFalse(d["obligaciones"]["validadores"][0])

    def test_4_sin_sucesor_activo(self):
        """Cerrar un bloque sin declarar el siguiente dejaria el repositorio
        sin bloque activo, que es el estado que D-54 prohibe."""
        c = _contrato(activo="B")          # el propio bloque sigue activo
        e, d = validar.veredicto_cierre("B", c)
        self.assertEqual(e, validar.OPEN)
        self.assertFalse(d["obligaciones"]["alcance"][0])

    def test_4b_sin_rango_propio(self):
        e, d = validar.veredicto_cierre("B", _contrato(desde=None))
        self.assertEqual(e, validar.OPEN)
        self.assertFalse(d["obligaciones"]["alcance"][0])

    def test_5_deuda_bloqueante(self):
        c = _contrato()
        c["open_debt"] = ["DF-X (bloqueante_para:B): algo sin resolver"]
        e, d = validar.veredicto_cierre("B", c)
        self.assertEqual(e, validar.OPEN)
        self.assertFalse(d["obligaciones"]["deudas_bloqueantes"][0])

    def test_5b_una_deuda_que_no_bloquea_este_bloque_no_impide_cerrar(self):
        c = _contrato()
        c["open_debt"] = ["DF-Y (bloqueante_para:OTRO_BLOQUE): algo"]
        e, _ = validar.veredicto_cierre("B", c)
        self.assertEqual(e, validar.CLOSED)

    def test_6_verificacion_de_otro_commit(self):
        """Verificar en un commit y cerrar en otro no demuestra nada."""
        e, d = self._falla(ultima_verificacion={"commit": "0" * 40})
        self.assertEqual(e, validar.OPEN)
        self.assertFalse(d["obligaciones"]["ultima_verificacion"][0])

    def test_6b_sin_verificacion(self):
        e, d = self._falla(ultima_verificacion={})
        self.assertEqual(e, validar.OPEN)

    def test_7_commit_no_resoluble(self):
        e, d = self._falla(commit_de_cierre="0" * 40,
                           ultima_verificacion={"commit": "0" * 40})
        self.assertEqual(e, validar.OPEN)
        self.assertFalse(d["obligaciones"]["commit"][0])


class TestLaIntencionNoCierra(unittest.TestCase):
    """La afirmacion humana queda acotada a la intencion."""

    def test_la_intencion_no_basta_si_una_obligacion_falla(self):
        c = _contrato(cierre=_cierre(
            intencion="doy por completo el alcance de este bloque",
            intencion_declarada_por="el usuario",
            entregables=["informes/no_existe.md"]))
        e, _ = validar.veredicto_cierre("B", c)
        self.assertEqual(e, validar.OPEN,
                         "una intencion declarada no puede cerrar un bloque")

    def test_el_contrato_real_declara_que_la_intencion_no_cierra(self):
        f1 = estado.cargar_contrato()["bloques"]["F1"]["cierre"]
        self.assertIn("intencion", f1)
        self.assertIn("_la_intencion_no_cierra", f1)
        self.assertIn("se CALCULAN", f1["_la_intencion_no_cierra"])

    def test_f1_estado_r2_no_declara_el_cierre(self):
        """La revision de la afirmacion humana habla de alcance, NO de cierre:
        el cierre es un veredicto, y mezclarlos repetiria el fallo."""
        q = next(x for x in estado.cargar_contrato()["state_queries"]
                 if x["query_id"] == "f1_estado_r2")
        self.assertIn("veredicto_cierre", q["asserted_value"])
        self.assertIn("NO declara el cierre", q["_test_verifica"])


class TestCaducidad(unittest.TestCase):
    """El cierre caduca solo, sin que nadie tenga que revisarlo."""

    def test_una_huella_que_ya_no_corresponde_da_STALE(self):
        c = _contrato(cierre=_cierre(huella="0" * 64))
        e, d = validar.veredicto_cierre("B", c)
        self.assertEqual(e, validar.STALE)
        self.assertIn(validar.CIERRE_CADUCADO, d["motivos"][0])

    def test_STALE_nunca_se_queda_en_CLOSED(self):
        c = _contrato(cierre=_cierre(huella="0" * 64))
        e, _ = validar.veredicto_cierre("B", c)
        self.assertNotEqual(e, validar.CLOSED)

    def test_la_huella_cambia_si_cambia_un_entregable(self):
        a = validar.huella_cierre(_cierre(entregables=["contexto/validar.py"]))
        b = validar.huella_cierre(_cierre(entregables=["contexto/grafo.py"]))
        self.assertNotEqual(a, b)

    def test_la_huella_cambia_si_cambia_el_comando_de_tests(self):
        a = validar.huella_cierre(_cierre())
        b = validar.huella_cierre(_cierre(tests="pytest -x"))
        self.assertNotEqual(a, b)

    def test_la_huella_cambia_si_aparece_una_deuda_bloqueante(self):
        a = validar.huella_cierre(_cierre(_bloqueantes=[]))
        b = validar.huella_cierre(_cierre(_bloqueantes=["DF-X bloquea"]))
        self.assertNotEqual(a, b)

    def test_la_huella_es_determinista(self):
        self.assertEqual(validar.huella_cierre(_cierre()),
                         validar.huella_cierre(_cierre()))

    def test_un_entregable_ausente_cambia_la_huella(self):
        """AUSENTE no es lo mismo que un contenido cualquiera."""
        a = validar.huella_cierre(_cierre(entregables=["informes/no_existe.md"]))
        b = validar.huella_cierre(_cierre(entregables=["contexto/validar.py"]))
        self.assertNotEqual(a, b)


class TestF1Real(unittest.TestCase):
    """El veredicto sobre el bloque real. Hoy debe dar OPEN."""

    def setUp(self):
        self.estado, self.detalle = validar.veredicto_cierre("F1")

    def test_F1_no_esta_cerrada(self):
        self.assertEqual(self.estado, validar.OPEN,
                         "F1 no puede cerrarse mientras DF-6 la bloquee")

    def test_la_unica_obligacion_incumplida_es_la_de_deudas(self):
        ob = self.detalle["obligaciones"]
        incumplidas = [k for k, v in ob.items() if not v[0]]
        self.assertEqual(incumplidas, ["deudas_bloqueantes"],
                         f"detalle: {ob}")

    def test_DF6_es_la_deuda_que_bloquea(self):
        bl = validar.deudas_bloqueantes("F1")
        self.assertEqual(len(bl), 1)
        self.assertIn("DF-6", bl[0])
        self.assertIn("pyarrow", bl[0])

    def test_las_otras_seis_obligaciones_se_cumplen(self):
        ob = self.detalle["obligaciones"]
        for k in ("entregables", "tests", "validadores", "alcance",
                  "ultima_verificacion", "commit"):
            self.assertTrue(ob[k][0], f"{k}: {ob[k][1]}")

    def test_los_diez_entregables_de_F1_resuelven(self):
        ent = estado.cargar_contrato()["bloques"]["F1"]["cierre"]["entregables"]
        self.assertEqual(len(ent), 10)
        for rel in ent:
            self.assertTrue(os.path.exists(os.path.join(RAIZ, rel)), rel)

    def test_el_informe_de_T10_es_uno_de_los_entregables(self):
        ent = estado.cargar_contrato()["bloques"]["F1"]["cierre"]["entregables"]
        self.assertIn("informes/2026-09-12_f1_contexto_durable_y_cierre.md", ent)

    def test_el_commit_de_cierre_es_el_hasta_del_rango(self):
        """El cierre se verifica en el ultimo commit propio del bloque."""
        _desde, hasta, _op = validar.rango_bloque("F1")
        cierre = estado.cargar_contrato()["bloques"]["F1"]["cierre"]
        self.assertEqual(cierre["commit_de_cierre"], hasta)


class TestElValorCaducadoSeConserva(unittest.TestCase):
    """La historia no se borra: el f1_estado obsoleto sigue ahi."""

    def setUp(self):
        self.qs = {q["query_id"]: q
                   for q in estado.cargar_contrato()["state_queries"]}

    def test_la_entrada_vieja_sigue_existiendo_con_su_valor(self):
        q = self.qs["f1_estado"]
        self.assertIn("T7-T10 pendientes", q["asserted_value"])
        self.assertEqual(q["superseded_by"], "f1_estado_r2")

    def test_declara_por_que_caduco(self):
        q = self.qs["f1_estado"]
        self.assertIn("_caducidad", q)
        self.assertIn("MISMO DIA", q["_caducidad"])
        for commit in ("30022c9", "032c9e5", "f784b85", "8c38056"):
            self.assertIn(commit, q["_caducidad"], commit)

    def test_la_cadena_de_revision_es_bidireccional(self):
        self.assertEqual(self.qs["f1_estado_r2"]["supersedes"], "f1_estado")


if __name__ == "__main__":
    unittest.main(verbosity=2)
