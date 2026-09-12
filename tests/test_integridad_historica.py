# -*- coding: utf-8 -*-
"""T1 de F1 (2026-09-12) -- integridad del contenido historico.

    Ningun contenido historico se pierde ni se altera.

NINGUN test de este fichero escribe en el repositorio real. Las
mutaciones se hacen sobre copias en memoria del manifiesto o sobre
directorios temporales. Un test que "demuestre" integridad alterando el
historico de verdad seria una contradiccion en sus propios terminos.
"""
import os
import shutil
import sys
import tempfile
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "contexto"))

import integridad  # noqa: E402

BASE = integridad.cargar(os.path.join(RAIZ, "contexto", "manifiesto.json"))


class TestAlcance(unittest.TestCase):
    """El manifiesto cubre lo que dice cubrir, y nada mas."""

    def test_cubre_exactamente_los_43_ficheros_historicos(self):
        actual = integridad.generar()
        self.assertEqual(len(actual), 43)
        self.assertEqual(set(actual), set(BASE))

    def test_solo_docs_e_informes(self):
        for ruta in integridad.generar():
            self.assertTrue(ruta.startswith(("docs/", "informes/")), ruta)

    def test_engine_data_y_knowledge_quedan_fuera(self):
        """Ya los cubren qa.py, consulta.py y la suite. Duplicar es ruido."""
        rutas = " ".join(integridad.generar())
        for fuera in ("engine/", "data/", "knowledge/"):
            self.assertNotIn(fuera, rutas)

    def test_el_manifiesto_versionado_coincide_con_el_arbol_real(self):
        self.assertEqual(integridad.generar(), BASE)


class TestLosCincoEstados(unittest.TestCase):
    """Cada estado tiene su test. Un estado sin test no esta implementado."""

    def setUp(self):
        self.antes = dict(BASE)
        self.despues = dict(BASE)
        self.una = sorted(BASE)[0]

    def test_preserved(self):
        r = integridad.comparar(self.antes, self.despues)
        self.assertEqual(set(r.values()), {integridad.PRESERVED})

    def test_altered(self):
        self.despues[self.una] = "0" * 64
        r = integridad.comparar(self.antes, self.despues)
        self.assertEqual(r[self.una], integridad.ALTERED)

    def test_lost(self):
        del self.despues[self.una]
        r = integridad.comparar(self.antes, self.despues)
        self.assertEqual(r[self.una], integridad.LOST)

    def test_moved_declarado(self):
        nueva = "docs/otra_ruta.md"
        self.despues[nueva] = self.despues.pop(self.una)
        r = integridad.comparar(self.antes, self.despues, movimientos=[(self.una, nueva)])
        self.assertEqual(r[nueva], integridad.MOVED)

    def test_added_declarado(self):
        self.despues["docs/nuevo.md"] = "a" * 64
        r = integridad.comparar(self.antes, self.despues, adiciones=["docs/nuevo.md"])
        self.assertEqual(r["docs/nuevo.md"], integridad.ADDED)


class TestLoQueNuncaPuedePasar(unittest.TestCase):
    """LOST y ALTERED fallan siempre. No hay flag que los desactive."""

    def setUp(self):
        self.antes = dict(BASE)
        self.una = sorted(BASE)[0]

    def test_alterar_un_byte_falla(self):
        despues = dict(self.antes)
        despues[self.una] = "0" * 64
        ok, inc, _ = integridad.verificar(self.antes, despues)
        self.assertFalse(ok)
        self.assertIn("H-a", [regla for regla, _ in inc])

    def test_borrar_un_fichero_falla(self):
        despues = dict(self.antes)
        del despues[self.una]
        ok, inc, _ = integridad.verificar(self.antes, despues)
        self.assertFalse(ok)

    def test_no_existe_ninguna_forma_de_desactivar_lost_ni_altered(self):
        """Comprobacion sobre el codigo: si alguien anade un flag de
        excepcion, este test se rompe y debe romperse."""
        self.assertEqual(integridad.ESTADOS_QUE_FALLAN,
                         (integridad.LOST, integridad.ALTERED))


class TestRenombradoElPuntoCiegoDeP5A(unittest.TestCase):
    """El fallo concreto que el patron concatenado de P5A no detecta."""

    def setUp(self):
        self.antes = dict(BASE)
        self.una = sorted(BASE)[0]

    def test_renombrar_sin_declararlo_falla(self):
        despues = dict(self.antes)
        despues["docs/renombrado_a_escondidas.md"] = despues.pop(self.una)
        ok, inc, r = integridad.verificar(self.antes, despues)
        self.assertFalse(ok, "un renombrado no declarado tiene que fallar")
        self.assertEqual(r[self.una], integridad.LOST)

    def test_renombrar_declarandolo_pasa(self):
        nueva = "docs/renombrado_declarado.md"
        despues = dict(self.antes)
        despues[nueva] = despues.pop(self.una)
        ok, _, r = integridad.verificar(self.antes, despues, movimientos=[(self.una, nueva)])
        self.assertTrue(ok)
        self.assertEqual(r[nueva], integridad.MOVED)

    def test_un_movimiento_declarado_que_ademas_altera_es_altered(self):
        """Peor que un movimiento y peor que una alteracion: las dos."""
        nueva = "docs/movido_y_tocado.md"
        despues = dict(self.antes)
        despues.pop(self.una)
        despues[nueva] = "0" * 64
        ok, _, r = integridad.verificar(self.antes, despues, movimientos=[(self.una, nueva)])
        self.assertFalse(ok)
        self.assertEqual(r[nueva], integridad.ALTERED)

    def test_el_hash_concatenado_de_p5a_NO_detecta_el_renombrado(self):
        """Evidencia viva de por que existe este modulo.

        Se reproduce el patron de test_caminos.py sobre un arbol temporal:
        concatena contenidos en orden y hashea. Un renombrado que conserva
        el orden alfabetico produce EL MISMO hash. El manifiesto por
        fichero si lo ve. Este test compara los dos mecanismos.
        """
        import hashlib

        def huella_concatenada(raiz):
            h = hashlib.sha256()
            for carpeta, _, fs in sorted(os.walk(raiz)):
                for f in sorted(fs):
                    h.update(open(os.path.join(carpeta, f), "rb").read())
            return h.hexdigest()

        tmp = tempfile.mkdtemp()
        try:
            d = os.path.join(tmp, "docs")
            os.makedirs(d)
            open(os.path.join(d, "a.md"), "w").write("alfa")
            open(os.path.join(d, "b.md"), "w").write("beta")
            antes_concat = huella_concatenada(tmp)
            antes_manif = integridad.generar(tmp)

            # Renombrado que conserva el orden alfabetico: a.md -> aa.md
            os.rename(os.path.join(d, "a.md"), os.path.join(d, "aa.md"))
            despues_concat = huella_concatenada(tmp)
            despues_manif = integridad.generar(tmp)

            self.assertEqual(antes_concat, despues_concat,
                             "si esto cambia, el patron de P5A si lo veia")
            self.assertNotEqual(antes_manif, despues_manif,
                                "el manifiesto por fichero TIENE que verlo")
            ok, _, _ = integridad.verificar(antes_manif, despues_manif)
            self.assertFalse(ok)
        finally:
            shutil.rmtree(tmp)


class TestBloqueActual(unittest.TestCase):
    """H-c: en F1 no se mueve nada dentro de docs/ + informes/."""

    def test_moved_es_cero_en_este_bloque(self):
        ok, inc, r = integridad.verificar(BASE, integridad.generar(),
                                          exigir_cero_movimientos=True)
        self.assertTrue(ok, inc)
        self.assertEqual(sum(1 for v in r.values() if v == integridad.MOVED), 0)

    def test_un_movimiento_aqui_seria_un_error_aunque_este_declarado(self):
        nueva = "docs/lo_que_sea.md"
        una = sorted(BASE)[0]
        despues = dict(BASE)
        despues[nueva] = despues.pop(una)
        ok, inc, _ = integridad.verificar(BASE, despues, movimientos=[(una, nueva)],
                                          exigir_cero_movimientos=True)
        self.assertFalse(ok)
        self.assertIn("H-c", [regla for regla, _ in inc])


class TestNoEscribe(unittest.TestCase):
    def test_el_modulo_no_abre_ningun_fichero_para_escribir(self):
        fuente = open(os.path.join(RAIZ, "contexto", "integridad.py"), encoding="utf-8").read()
        cuerpo = fuente.split("def main(")[0]
        for patron in ('"w"', "'w'", '"a"', "'a'", "os.remove", "os.rename", "shutil"):
            self.assertNotIn(patron, cuerpo, f"integridad.py no puede escribir: {patron}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
