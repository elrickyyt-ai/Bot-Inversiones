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

    def test_F1_esta_cerrada_por_veredicto(self):
        """ACTUALIZADO en S0.2: mientras DF-6 estuvo abierta este test exigia
        OPEN, y era correcto -- el gate de PR de T9, entregable de F1, fallaba
        en clean-room. Resuelta DF-6, las siete obligaciones pasan y el
        veredicto es CLOSED. No se relajo ninguna obligacion: se resolvio la
        deuda que las incumplia."""
        self.assertEqual(self.estado, validar.CLOSED, self.detalle["motivos"])

    def test_las_siete_obligaciones_se_cumplen(self):
        ob = self.detalle["obligaciones"]
        incumplidas = [k for k, v in ob.items() if not v[0]]
        self.assertEqual(incumplidas, [], f"detalle: {ob}")

    def test_ya_no_hay_deudas_que_bloqueen_F1(self):
        self.assertEqual(validar.deudas_bloqueantes("F1"), [])

    def test_DF6_queda_registrada_como_resuelta_no_borrada(self):
        """La historia no se borra: la deuda sigue en el registro, con lo que
        era y como se resolvio."""
        deudas = " ".join(estado.cargar_contrato()["open_debt"])
        self.assertIn("DF-6", deudas)
        self.assertIn("RESUELTA en S0.2", deudas)
        self.assertNotIn("bloqueante_para:F1", deudas.replace(" ", ""))

    def test_cada_obligacion_por_separado(self):
        ob = self.detalle["obligaciones"]
        for k in validar.OBLIGACIONES_CIERRE:
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


class TestCoherenciaYAutorreferencia(unittest.TestCase):
    """Dos propiedades descubiertas al sellar F1."""

    def test_nadie_puede_declararse_CLOSED_sin_el_veredicto(self):
        """`bloques[*].estado` es una etiqueta de ciclo de vida, legible, y NO
        la autoridad. Exigir igualdad estricta seria confundir dos cosas: un
        bloque EN CURSO se etiqueta OPEN mientras su veredicto es UNDECLARED
        -- todavia no ha declarado cierre -- y eso no es una contradiccion.

        El invariante que SI importa, y es el que D-56 protege: no se puede
        DECLARAR CLOSED sin que el veredicto lo confirme."""
        c = estado.cargar_contrato()
        for bid, b in c["bloques"].items():
            declarado = b.get("estado")
            if declarado is None:
                continue
            calculado, d = validar.veredicto_cierre(bid, c)
            if declarado == validar.CLOSED:
                self.assertEqual(calculado, validar.CLOSED,
                                 f"{bid} se declara CLOSED y el veredicto da "
                                 f"{calculado}: {d['motivos']}")
            else:
                self.assertNotEqual(
                    calculado, validar.CLOSED,
                    f"{bid} esta cerrado por veredicto y no lo declara")

    def test_el_contrato_se_excluye_de_su_propio_sello(self):
        """Medido al sellar F1: incluir contrato.json en su propia huella la
        invalidaba en el acto -- pasaba de 0efbe3e3 a bbbad2a2 y el veredicto de
        CLOSED a STALE sin que el material cerrado hubiese cambiado. Un sello no
        puede ser parte de lo que sella."""
        decl = estado.cargar_contrato()["bloques"]["F1"]["cierre"]
        self.assertIn(validar._CONTRATO_REL, decl["entregables"],
                       "el contrato SI es un entregable de F1")
        con = validar.huella_cierre(dict(decl, _bloqueantes=[]))
        sin_contrato = [r for r in decl["entregables"]
                        if r != validar._CONTRATO_REL]
        self.assertEqual(
            con,
            validar.huella_cierre(dict(decl, entregables=sin_contrato,
                                       _bloqueantes=[])),
            "la huella no puede depender del fichero que la guarda")

    def test_el_sello_de_F1_esta_fijado_y_corresponde(self):
        decl = estado.cargar_contrato()["bloques"]["F1"]["cierre"]
        self.assertTrue(decl.get("huella"), "un bloque CLOSED tiene que sellar")
        self.assertEqual(decl["huella"],
                         validar.huella_cierre(dict(decl, _bloqueantes=[])))

    def test_el_sello_se_toma_en_el_commit_de_cierre_no_en_el_worktree(self):
        """La propiedad que S0.3 obligo a corregir. ESTADO_VIGENTE.md es un
        entregable de F1 y S0.3 lo amplia con autorizacion; si el sello leyera
        el worktree, F1 se volveria STALE por una mejora POSTERIOR. El
        significado historico de un bloque cerrado no puede depender de HEAD --
        el mismo defecto que S0.1 corrigio con `hasta`."""
        decl = estado.cargar_contrato()["bloques"]["F1"]["cierre"]
        rel = "contexto/ESTADO_VIGENTE.md"
        self.assertIn(rel, decl["entregables"])

        en_cierre = validar._contenido_en(decl["commit_de_cierre"], rel)
        with open(os.path.join(RAIZ, rel), "rb") as fh:
            ahora = fh.read()
        self.assertNotEqual(en_cierre, ahora,
                            "S0.3 tiene que haber cambiado este entregable")

        e, d = validar.veredicto_cierre("F1")
        self.assertEqual(e, validar.CLOSED,
                         f"una mejora posterior no puede caducar el cierre: "
                         f"{d['motivos']}")

    def test_el_sello_no_depende_del_worktree(self):
        decl = dict(estado.cargar_contrato()["bloques"]["F1"]["cierre"],
                    _bloqueantes=[])
        a = validar.huella_cierre(decl)
        b = validar.huella_cierre(decl)
        self.assertEqual(a, b)
        # Y difiere de la que daria el worktree: son bases distintas.
        sin_commit = dict(decl)
        sin_commit.pop("commit_de_cierre")
        self.assertNotEqual(a, validar.huella_cierre(sin_commit))

    def test_tocar_un_entregable_dejaria_F1_en_STALE(self):
        """La propiedad que hace util el sello, comprobada sin tocar nada."""
        c = estado.cargar_contrato()
        c["bloques"]["F1"]["cierre"] = dict(
            c["bloques"]["F1"]["cierre"],
            entregables=["contexto/grafo.py"])      # otro contenido
        e, d = validar.veredicto_cierre("F1", c)
        self.assertEqual(e, validar.STALE, d["motivos"])


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
