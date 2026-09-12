# -*- coding: utf-8 -*-
"""Alcance por bloque -- DF-1 (S0.1).

Matriz de veredictos del contrato de alcance. Lo que estos tests fijan no es
"engine/ esta prohibido" -- esa era la formulacion del interruptor que S0.1
sustituye, y era justamente el defecto: el alcance es DEL BLOQUE, no del
repositorio para siempre. Lo que fijan es:

    lo no declarado no se permite          (denegacion por defecto)
    la proteccion global gana siempre      (ningun bloque se autoriza el historico)
    no existe el estado "sin guarda"       (ALCANCE_NO_DECLARADO falla)

Todos los contratos de prueba son diccionarios EN MEMORIA: ningun test
escribe en el repositorio ni toca contexto/contrato.json.
"""
import copy
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "contexto"))

import estado  # noqa: E402
import validar  # noqa: E402


def _contrato(bloque_activo="S0", bloques=None):
    """Contrato minimo en memoria. No lee ni escribe el real salvo que se pida."""
    c = {"bloque_activo": bloque_activo}
    if bloques is not None:
        c["bloques"] = bloques
    return c


SOLO_CONTEXTO = {"S0": {"escritura": ["contexto/"]}}
CON_DOCS = {"S0": {"escritura": ["contexto/", "docs/", "informes/"]}}


class TestVeredictosBasicos(unittest.TestCase):
    """T-1.1, T-1.2, T-1.3, T-1.8: los tres veredictos no condicionales."""

    def test_T11_ruta_declarada_es_permitida(self):
        v, _ = validar.veredicto_alcance(["contexto/validar.py"],
                                         _contrato(bloques=SOLO_CONTEXTO))
        self.assertEqual(v["contexto/validar.py"], validar.PERMITIDO)

    def test_T12_ruta_no_declarada_por_el_bloque_queda_fuera(self):
        ruta = "engine/causal/mecanismos.py"
        v, _ = validar.veredicto_alcance([ruta], _contrato(bloques=SOLO_CONTEXTO))
        self.assertEqual(v[ruta], validar.FUERA_DE_ALCANCE)
        ok, motivo = validar.guarda_alcance([ruta], _contrato(bloques=SOLO_CONTEXTO))
        self.assertFalse(ok)
        self.assertIn(validar.FUERA_DE_ALCANCE, motivo)

    def test_T13_la_misma_ruta_es_permitida_si_el_bloque_la_declara(self):
        """El alcance es del BLOQUE. Esta es la propiedad que DF-1 aporta y que
        el interruptor no podia expresar: no hay arbol prohibido para siempre."""
        ruta = "engine/causal/mecanismos.py"
        bloques = {"PC-1": {"escritura": ["engine/", "tests/"]}}
        v, _ = validar.veredicto_alcance([ruta], _contrato("PC-1", bloques))
        self.assertEqual(v[ruta], validar.PERMITIDO)

    def test_T18_denegacion_por_defecto(self):
        """Una ruta que no encaja en NINGUNA regla no se permite. Mismo
        invariante que UNDECLARED != valor por defecto."""
        for ruta in ("ruta/inventada/x.py", "README.md", "otro.txt"):
            v, _ = validar.veredicto_alcance([ruta], _contrato(bloques=SOLO_CONTEXTO))
            self.assertEqual(v[ruta], validar.FUERA_DE_ALCANCE, ruta)


class TestProteccionGlobal(unittest.TestCase):
    """T-1.4, T-1.5, T-1.6, T-1.7: la proteccion global y su condicion."""

    def setUp(self):
        self.protegida = sorted(validar.superficie_protegida())
        self.una = "docs/DECISIONES.md"
        self.assertIn(self.una, self.protegida,
                      "el manifiesto debe fijar DECISIONES.md")

    def test_la_superficie_protegida_es_derivada_no_declarada(self):
        """No hay lista de arboles en ninguna parte: sale del manifiesto."""
        del_manifiesto = validar._rutas_manifiesto()
        de_extraccion = validar._rutas_extraccion()
        self.assertEqual(set(self.protegida), del_manifiesto | de_extraccion)
        self.assertGreaterEqual(len(del_manifiesto), 43)

    def test_T14_modificar_el_historico_sin_el_manifiesto_falla(self):
        ok, motivo = validar.guarda_alcance([self.una], _contrato(bloques=CON_DOCS))
        self.assertFalse(ok)
        self.assertIn(validar.PROTEGIDO_GLOBAL, motivo)
        self.assertIn("manifiesto", motivo)

    def test_T15_con_el_manifiesto_en_el_mismo_diff_pasa(self):
        """PROTEGIDO_GLOBAL no es una prohibicion absoluta: docs/07 EXIGE
        escribir en docs/ al cerrar una fase. Es una condicion."""
        rutas = [self.una, validar.MANIFIESTO]
        ok, motivo = validar.guarda_alcance(rutas, _contrato(bloques=CON_DOCS))
        self.assertTrue(ok, motivo)

    def test_T16_un_bloque_no_puede_autorizarse_el_historico(self):
        """Aunque lo declare en su escritura, el veredicto sigue siendo
        PROTEGIDO_GLOBAL: el permiso lo concede OTRO mecanismo."""
        bloques = {"S0": {"escritura": ["docs/", "docs/DECISIONES.md", "contexto/"]}}
        v, _ = validar.veredicto_alcance([self.una], _contrato(bloques=bloques))
        self.assertEqual(v[self.una], validar.PROTEGIDO_GLOBAL)
        ok, motivo = validar.guarda_alcance([self.una], _contrato(bloques=bloques))
        self.assertFalse(ok, "declararlo en escritura NO puede bastar")
        self.assertIn(validar.PROTEGIDO_GLOBAL, motivo)

    def test_T17_anadir_un_informe_nuevo_no_es_proteccion_global(self):
        """Anadir != alterar. Un fichero que no esta en el manifiesto no esta
        fijado por hash, asi que el alcance del bloque basta."""
        nuevo = "informes/2026-09-12_f1_contexto_durable_y_cierre.md"
        self.assertNotIn(nuevo, self.protegida)
        v, _ = validar.veredicto_alcance([nuevo], _contrato(bloques=CON_DOCS))
        self.assertEqual(v[nuevo], validar.PERMITIDO)

    def test_el_destino_de_la_extraccion_no_pasa_por_alcance(self):
        destino = sorted(validar._rutas_extraccion())[0]
        ok, motivo = validar.guarda_alcance(
            [destino, validar.MANIFIESTO],
            _contrato(bloques={"S0": {"escritura": ["contexto/"]}}))
        self.assertFalse(ok, "ni con el manifiesto: su autoridad es extraccion.py")
        self.assertIn("extraccion.py", motivo)


class TestSinDeclaracion(unittest.TestCase):
    """T-1.9, T-1.10: no existe el estado "sin guarda"."""

    def test_T19_sin_bloque_activo_falla(self):
        v, _ = validar.veredicto_alcance(["contexto/x.py"], _contrato(None, SOLO_CONTEXTO))
        self.assertEqual(v["contexto/x.py"], validar.ALCANCE_NO_DECLARADO)
        ok, motivo = validar.guarda_alcance(["contexto/x.py"],
                                            _contrato(None, SOLO_CONTEXTO))
        self.assertFalse(ok)
        self.assertIn(validar.ALCANCE_NO_DECLARADO, motivo)

    def test_T110_bloque_activo_no_declarado_falla_no_pasa(self):
        """El caso peligroso: activo pero sin entrada. NUNCA debe pasar."""
        ok, motivo = validar.guarda_alcance(
            ["contexto/x.py"], _contrato("BLOQUE_FANTASMA", SOLO_CONTEXTO))
        self.assertFalse(ok, "un bloque sin declarar no puede dar PASS")
        self.assertIn(validar.ALCANCE_NO_DECLARADO, motivo)

    def test_sin_clave_bloques_falla(self):
        ok, motivo = validar.guarda_alcance(["contexto/x.py"], _contrato("S0", None))
        self.assertFalse(ok)
        self.assertIn(validar.ALCANCE_NO_DECLARADO, motivo)

    def test_escritura_vacia_no_permite_nada(self):
        bloques = {"S0": {"escritura": []}}
        v, _ = validar.veredicto_alcance(["contexto/x.py"], _contrato(bloques=bloques))
        self.assertEqual(v["contexto/x.py"], validar.FUERA_DE_ALCANCE)


class TestNoHayInterruptor(unittest.TestCase):
    """T-1.11: el test que cierra DF-1."""

    def test_T111_ninguna_clave_del_contrato_desactiva_la_guarda(self):
        """El defecto de `alcance_bloque.vigente` era que un booleano dejaba
        proteccion CERO. Ninguna combinacion puede reproducirlo."""
        ruta = "engine/causal/mecanismos.py"
        for extra in ({}, {"vigente": False}, {"activo": False},
                      {"aplica": False}, {"enabled": False}, {"skip": True}):
            bloques = {"S0": dict({"escritura": ["contexto/"]}, **extra)}
            ok, _ = validar.guarda_alcance([ruta], _contrato(bloques=bloques))
            self.assertFalse(ok, f"{extra} no puede desactivar la guarda")

    def test_el_contrato_real_no_declara_ningun_interruptor(self):
        c = estado.cargar_contrato()
        self.assertNotIn("alcance_bloque", c, "el interruptor debe estar retirado")
        self.assertIn("bloque_activo", c)
        self.assertIn("bloques", c)
        for bid, decl in c["bloques"].items():
            self.assertNotIn("vigente", decl, bid)
            self.assertIn("escritura", decl, bid)

    def test_el_contrato_real_tiene_bloque_activo_declarado(self):
        bid, decl = validar.bloque_activo()
        self.assertIsNotNone(bid)
        self.assertIsNotNone(decl, f"bloque_activo {bid!r} debe estar en `bloques`")


class TestNoHaySegundaCopia(unittest.TestCase):
    """T-1.12: la regla vive en un solo sitio."""

    def test_T112_ninguna_lista_de_arboles_fuera_de_la_autoridad(self):
        """ARBOLES_PROHIBIDOS era la lista global. No puede reaparecer en
        ningun sitio, ni en el validador."""
        self.assertFalse(hasattr(validar, "ARBOLES_PROHIBIDOS"),
                         "la lista global no puede volver")
        for rel in ("contexto/validar.py", "contexto/alcance_pr.py",
                    "contexto/contrato.json",
                    ".github/workflows/verificar-contexto.yml"):
            with open(os.path.join(RAIZ, rel), encoding="utf-8") as fh:
                cuerpo = fh.read()
            self.assertNotIn("ARBOLES_PROHIBIDOS =", cuerpo, rel)

    def test_alcance_pr_delega_y_no_reimplementa(self):
        with open(os.path.join(RAIZ, "contexto", "alcance_pr.py"),
                  encoding="utf-8") as fh:
            cuerpo = fh.read()
        self.assertIn("guarda_alcance", cuerpo, "tiene que delegar en la autoridad")
        for prohibido in ('"engine/"', '"data/"', '"knowledge/"'):
            self.assertNotIn(prohibido, cuerpo,
                             "no puede llevar su propia lista de arboles")

    def test_los_veredictos_estan_declarados_una_sola_vez(self):
        import alcance_pr
        self.assertIs(alcance_pr.ALCANCE_NO_DECLARADO, validar.ALCANCE_NO_DECLARADO)
        self.assertIs(alcance_pr.FUERA_DE_ALCANCE, validar.FUERA_DE_ALCANCE)
        self.assertEqual(len(set(validar.VEREDICTOS_ALCANCE)), 4)


class TestDiffCompletoDelPR(unittest.TestCase):
    """El `exit=0` historico solo habia mirado el ultimo commit."""

    def test_sin_base_se_declara_que_el_rango_es_parcial(self):
        import alcance_pr
        self.assertTrue(alcance_pr.rango_parcial(None))
        self.assertFalse(alcance_pr.rango_parcial("abc123"))

    def test_el_workflow_inyecta_base_y_head_del_pr(self):
        ruta = os.path.join(RAIZ, ".github", "workflows", "verificar-contexto.yml")
        with open(ruta, encoding="utf-8") as fh:
            y = fh.read()
        self.assertIn("BASE_SHA", y)
        self.assertIn("HEAD_SHA", y)
        self.assertIn("pull_request.base.sha", y)


class TestTransicionDeBloque(unittest.TestCase):
    """La transicion es SUSTITUCION, no apagado."""

    def test_cambiar_de_bloque_cambia_el_alcance_sin_desactivar_nada(self):
        bloques = {"F1": {"escritura": ["contexto/"]},
                   "PC-1": {"escritura": ["engine/"]}}
        ruta = "engine/causal/valoracion.py"
        v_f1, _ = validar.veredicto_alcance([ruta], _contrato("F1", bloques))
        v_pc1, _ = validar.veredicto_alcance([ruta], _contrato("PC-1", bloques))
        self.assertEqual(v_f1[ruta], validar.FUERA_DE_ALCANCE)
        self.assertEqual(v_pc1[ruta], validar.PERMITIDO)
        # Y en ambos casos el historico sigue protegido:
        for bid in ("F1", "PC-1"):
            ok, _ = validar.guarda_alcance(["docs/DECISIONES.md"],
                                           _contrato(bid, bloques))
            self.assertFalse(ok, bid)

    def test_pc1_esta_declarado_pero_no_autorizado(self):
        c = estado.cargar_contrato()
        pc1 = c["bloques"].get("PC-1")
        self.assertIsNotNone(pc1)
        self.assertIsNone(pc1.get("decision"), "PC-1 no puede llevar decision aun")
        self.assertEqual(pc1.get("estado"), "UNDECLARED")
        self.assertNotEqual(c["bloque_activo"], "PC-1")


class TestNoEscribeNada(unittest.TestCase):

    def test_ninguna_comprobacion_altero_el_repositorio(self):
        import subprocess
        r = subprocess.run(["git", "-C", RAIZ, "status", "--porcelain",
                            "docs", "informes", "knowledge"],
                           capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "",
                         "los tests de alcance no pueden tocar el historico")


if __name__ == "__main__":
    unittest.main(verbosity=2)
