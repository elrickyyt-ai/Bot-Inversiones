# -*- coding: utf-8 -*-
"""T5 de F1 (2026-09-12) -- D-PRD-1: extraccion de CLAUDE.md al historico.

    CLAUDE.md "## Estado del proyecto"  ->  destino historico
    sha256(destino) == ff2003f9...  (ancla COMPLETA de fichero)

H-5 opcion A: se protegen byte a byte el preambulo (251 B) y el bloque de
privacidad (834 B). El bloque "Punto de entrada obligatorio" (794 B) es
REESCRIBIBLE -- su modificacion es parte deliberada de T5. El hash
639266a8... de la cabecera completa quedo RETIRADO como ancla.

NINGUNA mutacion toca los ficheros reales: M3 y M4 se hacen sobre bytes y
texto en memoria, que es justo para lo que `verificar()` acepta parametros.
"""
import hashlib
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "contexto"))

import extraccion  # noqa: E402
import integridad  # noqa: E402


def _bytes_destino():
    p = os.path.join(RAIZ, extraccion.DESTINO)
    return open(p, "rb").read() if os.path.isfile(p) else None


def _claude():
    return open(os.path.join(RAIZ, "CLAUDE.md"), encoding="utf-8").read()


class _ExigeExtraccion(unittest.TestCase):
    """Base que convierte "la extraccion no se ha hecho" en un fallo de
    DOMINIO. Sin esto, usar el destino inexistente daria TypeError y el
    RED seria invalido: fallaria por el andamiaje, no por el mecanismo."""

    def destino(self):
        b = _bytes_destino()
        self.assertIsNotNone(
            b, "la extraccion de D-PRD-1 no se ha realizado: no existe el destino "
               "historico. El mecanismo de extraccion no existe todavia.")
        return b

    def linea_distintiva(self):
        return next(l.strip() for l in self.destino().decode("utf-8").split("\n")
                    if len(l.strip()) >= extraccion.LONGITUD_LINEA_DISTINTIVA)


class TestLaExtraccion(unittest.TestCase):
    """El recorrido de T5, extremo a extremo."""

    def test_1_el_destino_existe_y_tiene_el_ancla_exacta(self):
        b = _bytes_destino()
        self.assertIsNotNone(b, "la extraccion de D-PRD-1 no se ha realizado: "
                                "no existe el destino historico")
        self.assertEqual(hashlib.sha256(b).hexdigest(), extraccion.ANCLA_EXTRACCION)

    def test_2_el_destino_es_EXACTAMENTE_la_seccion_sin_nada_anadido(self):
        """C2: una sola linea de cabecera dentro destruiria el ancla."""
        b = _bytes_destino()
        self.assertIsNotNone(b, "la extraccion de D-PRD-1 no se ha realizado")
        self.assertTrue(b.decode("utf-8").startswith(extraccion.MARCA_SECCION),
                        "el destino no empieza por la marca de seccion")
        self.assertEqual(len(b), 23333)

    def test_3_la_seccion_desaparece_de_CLAUDE_md(self):
        self.assertNotIn(extraccion.MARCA_SECCION, _claude())

    def test_4_no_queda_copia_parcial_del_estado_en_CLAUDE_md(self):
        ok, inc = extraccion.verificar()
        self.assertNotIn(extraccion.COPIA_PARCIAL, [e for e, _ in inc])

    def test_5_el_preambulo_se_conserva_byte_a_byte(self):
        t = _claude()
        pre = t[:t.index("## Punto de entrada obligatorio")]
        self.assertTrue(hashlib.sha256(pre.encode()).hexdigest()
                        .startswith(extraccion.ANCLA_PREAMBULO))
        self.assertEqual(len(pre.encode()), 251)

    def test_6_la_privacidad_se_conserva_byte_a_byte(self):
        t = _claude()
        priv = t[t.index("## Protocolo obligatorio de privacidad"):]
        self.assertTrue(hashlib.sha256(priv.encode()).hexdigest()
                        .startswith(extraccion.ANCLA_PRIVACIDAD),
                        "el bloque de privacidad no coincide con su ancla: la seccion "
                        "de estado sigue detras y todavia no se ha extraido")
        self.assertEqual(len(priv.encode()), 834)

    def test_7_el_punto_de_entrada_apunta_a_S1_y_no_a_ESTADO_md(self):
        """El bloque reescribible: es lo que T5 cambia a proposito."""
        t = _claude()
        j = t.index("## Punto de entrada obligatorio")
        k = t.index("## Protocolo obligatorio de privacidad")
        entrada = t[j:k]
        self.assertIn("contexto/ESTADO_VIGENTE.md", entrada,
                      "el punto de entrada tiene que apuntar a S1")
        self.assertNotIn("lee `docs/ESTADO.md`", entrada,
                         "docs/ESTADO.md deja de ser lectura obligatoria")
        self.assertNotIn("se mantiene actualizado", entrada,
                         "afirmacion falsa ya medida (X-2/X-3)")

    def test_8_la_procedencia_resuelve(self):
        p, err = extraccion.procedencia()
        self.assertIsNone(err, err)
        self.assertEqual(p["fichero"], "CLAUDE.md")
        self.assertEqual(p["seccion"], extraccion.MARCA_SECCION)
        self.assertEqual(p["momento"], "estado previo a F1")
        self.assertTrue(p["coincide"])

    def test_9_la_verificacion_separada_da_PASS(self):
        ok, inc = extraccion.verificar()
        self.assertTrue(ok, inc)


class TestSeparacionDelManifiestoPrincipal(unittest.TestCase):
    """P-1: la extraccion NO es una entrada ADDED del manifiesto principal."""

    def test_el_manifiesto_principal_sigue_en_43_sin_movimientos(self):
        base = integridad.cargar(os.path.join(RAIZ, "contexto", "manifiesto.json"))
        ok, inc, r = integridad.verificar(base, integridad.generar(),
                                          exigir_cero_movimientos=True)
        self.assertTrue(ok, inc)
        conteo = {e: sum(1 for v in r.values() if v == e) for e in integridad.ESTADOS}
        self.assertEqual(conteo[integridad.PRESERVED], 43)
        self.assertEqual(conteo[integridad.MOVED], 0)
        self.assertEqual(conteo[integridad.ADDED], 0)
        self.assertEqual(conteo[integridad.LOST], 0)
        self.assertEqual(conteo[integridad.ALTERED], 0)

    def test_el_destino_vive_fuera_de_docs_e_informes(self):
        """Si viviera dentro seria ADDED del manifiesto principal."""
        self.assertFalse(extraccion.DESTINO.startswith(("docs/", "informes/")))

    def test_son_dos_mecanismos_distintos(self):
        self.assertNotIn("CLAUDE", str(integridad.ARBOLES))
        self.assertNotEqual(extraccion.DESTINO, integridad.ARBOLES)


class TestM3AnclaRota(_ExigeExtraccion):
    """M3 -- alterar un byte del destino. Mutacion EN MEMORIA."""

    def test_alterar_un_byte_produce_FAIL(self):
        b = self.destino()
        mutado = b[:-1] + (b"X" if b[-1:] != b"X" else b"Y")
        ok, inc = extraccion.verificar(bytes_destino=mutado)
        self.assertFalse(ok)
        self.assertIn(extraccion.ANCLA_ROTA, [e for e, _ in inc])

    def test_anadir_una_cabecera_dentro_tambien_rompe_el_ancla(self):
        """C2 comprobado como test, no solo como norma."""
        b = self.destino()
        ok, inc = extraccion.verificar(bytes_destino=b"<!-- procede de CLAUDE.md -->\n\n" + b)
        self.assertFalse(ok)
        self.assertIn(extraccion.ANCLA_ROTA, [e for e, _ in inc])

    def test_la_mutacion_no_escribe_en_el_repositorio(self):
        antes = hashlib.sha256(self.destino()).hexdigest()
        extraccion.verificar(bytes_destino=b"lo que sea")
        self.assertEqual(antes, hashlib.sha256(self.destino()).hexdigest())


class TestM4CopiaParcial(_ExigeExtraccion):
    """M4 -- dejar rastro del estado antiguo en CLAUDE.md. EN MEMORIA."""

    def _claude_con_rastro(self):
        return _claude() + "\n" + self.linea_distintiva() + "\n"

    def test_dejar_una_linea_del_estado_produce_FAIL(self):
        ok, inc = extraccion.verificar(texto_claude=self._claude_con_rastro())
        self.assertFalse(ok)
        self.assertIn(extraccion.COPIA_PARCIAL, [e for e, _ in inc])

    def test_dejar_la_marca_de_seccion_produce_FAIL(self):
        ok, inc = extraccion.verificar(
            texto_claude=_claude() + "\n" + extraccion.MARCA_SECCION + "\n")
        self.assertFalse(ok)
        self.assertIn(extraccion.SECCION_NO_ELIMINADA, [e for e, _ in inc])

    def test_tocar_el_bloque_de_privacidad_produce_FAIL(self):
        """El ancla de H-5 que protege un invariante del proyecto."""
        t = _claude().replace("Pseudonimizar por defecto", "Pseudonimizar a veces")
        ok, inc = extraccion.verificar(texto_claude=t)
        self.assertFalse(ok)
        self.assertIn(extraccion.ANCLA_CABECERA_ROTA, [e for e, _ in inc])

    def test_la_mutacion_no_escribe_en_el_repositorio(self):
        antes = hashlib.sha256(_claude().encode()).hexdigest()
        extraccion.verificar(texto_claude=self._claude_con_rastro())
        self.assertEqual(antes, hashlib.sha256(_claude().encode()).hexdigest())


class TestM3YM4SonDistintas(_ExigeExtraccion):
    def test_los_estados_son_distintos(self):
        b = self.destino()
        _, i3 = extraccion.verificar(bytes_destino=b[:-1] + b"X")
        _, i4 = extraccion.verificar(
            texto_claude=_claude() + "\n" + self.linea_distintiva() + "\n")
        self.assertIn(extraccion.ANCLA_ROTA, [e for e, _ in i3])
        self.assertIn(extraccion.COPIA_PARCIAL, [e for e, _ in i4])
        self.assertNotEqual(extraccion.ANCLA_ROTA, extraccion.COPIA_PARCIAL)


class TestElModuloNoEscribe(unittest.TestCase):
    def test_extraccion_py_no_abre_nada_para_escribir(self):
        fuente = open(os.path.join(RAIZ, "contexto", "extraccion.py"), encoding="utf-8").read()
        cuerpo = fuente.split("def main(")[0]
        for patron in ('"w"', "'w'", '"a"', "'a'", "os.remove", "os.rename", "shutil"):
            self.assertNotIn(patron, cuerpo, f"extraccion.py no puede escribir: {patron}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
