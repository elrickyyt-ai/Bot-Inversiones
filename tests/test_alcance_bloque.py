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
        # Un nombre que no existe: el informe de T10 ya entro al manifiesto
        # en S0.4, asi que usarlo aqui probaria lo contrario de lo que toca.
        nuevo = "informes/9999-12-31_informe_que_no_existe.md"
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
        # CADUCADO al anadir IMPORTADO (docs/07 s3): el literal `4` fijaba el
        # numero, que no es la propiedad. La propiedad -- mas fuerte, y la que
        # el `4` intentaba proteger -- es que el vocabulario este declarado una
        # sola vez y que `alcance_pr` no invente veredictos propios.
        self.assertEqual(len(set(validar.VEREDICTOS_ALCANCE)),
                         len(validar.VEREDICTOS_ALCANCE),
                         "el vocabulario no puede tener duplicados")
        declarados = set(estado.cargar_contrato()["alcance"]["veredictos"])
        self.assertEqual(declarados, set(validar.VEREDICTOS_ALCANCE),
                         "contrato y validador tienen que declarar lo mismo")


class TestDiffCompletoDelPR(unittest.TestCase):
    """El `exit=0` historico solo habia mirado el ultimo commit."""

    def test_el_origen_del_rango_se_declara_siempre(self):
        """REESCRITO con la correccion de S0.1: `rango_parcial()` desaparecio
        al pasar el rango a ser el del bloque. La propiedad que sobrevive, y
        es mas fuerte, es que la salida DECLARA que se ha medido."""
        import alcance_pr
        _r, origen = alcance_pr.rango_del_bloque()
        self.assertIn(origen, ("bloque", "bloque-abierto"))
        r2, o2 = alcance_pr.rango_del_bloque(
            {"bloque_activo": "Z", "bloques": {"Z": {"escritura": []}}})
        self.assertIsNone(r2, "sin `desde` no se inventa un rango")
        self.assertIsNone(o2)

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


class TestRangoDelBloque(unittest.TestCase):
    """BLOQUE = desde + hasta. El rango es del bloque, no el diff contra la base."""

    def test_bloque_cerrado_da_un_rango_reproducible(self):
        """`hasta` fijado: el significado historico del bloque NO depende de
        HEAD. Si dependiera, el bloque cambiaria con cada commit posterior."""
        desde, hasta, operativo = validar.rango_bloque("F1")
        self.assertTrue(desde)
        self.assertTrue(hasta, "un bloque cerrado tiene que fijar `hasta`")
        self.assertFalse(operativo)
        rango, origen = self._rango("F1")
        self.assertNotIn("HEAD", rango)
        self.assertEqual(origen, "bloque")

    def test_bloque_abierto_usa_HEAD_como_valor_operativo(self):
        desde, hasta, operativo = validar.rango_bloque("S0")
        self.assertTrue(desde)
        self.assertIsNone(hasta, "un bloque abierto deja `hasta` en null")
        self.assertTrue(operativo)
        rango, origen = self._rango("S0")
        self.assertIn("HEAD", rango)
        self.assertEqual(origen, "bloque-abierto")

    def test_bloque_sin_rango_no_lo_inventa(self):
        desde, hasta, _ = validar.rango_bloque("PC-1")
        self.assertIsNone(desde)
        self.assertIsNone(hasta)
        rango, origen = self._rango("PC-1")
        self.assertIsNone(rango)
        self.assertIsNone(origen)

    def test_cada_bloque_con_rango_cumple_su_propio_alcance(self):
        """La propiedad que el diff-contra-la-base no podia dar: un bloque
        responde de los commits que escribio."""
        import alcance_pr
        c = estado.cargar_contrato()
        for bid, decl in c["bloques"].items():
            if not decl.get("desde"):
                continue
            rango, _ = self._rango(bid)
            rutas = alcance_pr._diff(rango)
            # El contrato ENTERO, no un recorte: `alcance.importado` forma
            # parte de la regla desde que existe IMPORTADO, y un contrato
            # parcial haria fallar al bloque por una ruta que no escribio.
            ok, motivo = validar.guarda_alcance(rutas, dict(c, bloque_activo=bid))
            self.assertTrue(ok, f"{bid} incumple su propio alcance: {motivo}")

    def _rango(self, bid):
        import alcance_pr
        c = estado.cargar_contrato()
        return alcance_pr.rango_del_bloque({"bloque_activo": bid,
                                            "bloques": c["bloques"]})


class TestAutoridadDeLaExtraccion(unittest.TestCase):
    """El destino D-PRD-1: crear no es alterar, igual que en el manifiesto."""

    def setUp(self):
        self.destino = sorted(validar._rutas_extraccion())[0]
        self.c = _contrato("X", {"X": {"escritura": ["contexto/"]}})

    def test_sin_mover_su_autoridad_no_pasa(self):
        ok, motivo = validar.guarda_alcance([self.destino], self.c)
        self.assertFalse(ok)
        self.assertIn(validar.PROTEGIDO_GLOBAL, motivo)
        self.assertIn(validar.AUTORIDAD_EXTRACCION, motivo)

    def test_moviendo_su_autoridad_en_el_mismo_commit_pasa(self):
        """Es lo que hizo T5 (8c38056): creo el destino y su verificador a la
        vez. Rechazarlo habria sido rechazar al bloque que lo creo."""
        rutas = [self.destino, validar.AUTORIDAD_EXTRACCION]
        ok, motivo = validar.guarda_alcance(rutas, self.c)
        self.assertTrue(ok, motivo)

    def test_el_manifiesto_no_autoriza_la_extraccion_ni_al_contrario(self):
        """Cada dato exige SU autoridad, no una cualquiera."""
        ok, _ = validar.guarda_alcance([self.destino, validar.MANIFIESTO], self.c)
        self.assertFalse(ok, "el manifiesto no manda sobre la extraccion")
        ok2, _ = validar.guarda_alcance(
            ["docs/DECISIONES.md", validar.AUTORIDAD_EXTRACCION],
            _contrato("X", {"X": {"escritura": ["contexto/", "docs/"]}}))
        self.assertFalse(ok2, "extraccion.py no manda sobre el manifiesto")


class TestNoEscribeNada(unittest.TestCase):

    def test_ninguna_comprobacion_altero_el_repositorio(self):
        """REESCRITO en S0.4: antes exigia un arbol limpio, lo que fallaba
        durante el propio commit que modifica docs/ e informes/. Eso medía el
        estado del worktree, no la propiedad. La propiedad real es que ESTOS
        tests no escriben: se comprueba por hash antes y despues."""
        import hashlib
        rutas = ["docs/DECISIONES.md", "docs/ESTADO.md", "contexto/contrato.json",
                 "contexto/manifiesto.json", "contexto/ESTADO_VIGENTE.md"]

        def huellas():
            out = {}
            for rel in rutas:
                destino = os.path.join(RAIZ, rel)
                if os.path.isfile(destino):
                    with open(destino, "rb") as fh:
                        out[rel] = hashlib.sha256(fh.read()).hexdigest()
            return out

        antes = huellas()
        self._ejercitar()
        self.assertEqual(huellas(), antes,
                         "las comprobaciones no pueden escribir en el repositorio")

    def _ejercitar(self):
        validar.superficie_protegida()
        validar.veredicto_alcance(["docs/DECISIONES.md", "contexto/x.py"])
        validar.guarda_alcance(["docs/ESTADO.md"])
        validar.rango_bloque("F1")


if __name__ == "__main__":
    unittest.main(verbosity=2)


# --- IMPORTADO: procedencia, no permiso ------------------------------------
#
# El defecto que estos tests fijan lo descubrio el PRIMER CI REAL del proyecto,
# no una prueba de laboratorio: la equivalencia `diff(desde~1, HEAD) == lo que
# escribio el bloque` deja de ser cierta en cuanto hay un merge. Lo que se
# comprueba aqui no es "data/thesis/ pasa", sino que la unica forma de pasar
# sea tener la PROCEDENCIA demostrada contra git.


class TestImportadoNoEsAutorizacion(unittest.TestCase):
    """La propiedad mas importante: IMPORTADO no concede nada."""

    def test_no_esta_entre_los_veredictos_que_autorizan(self):
        self.assertNotIn(validar.IMPORTADO, validar.VEREDICTOS_QUE_PASAN)
        self.assertIn(validar.IMPORTADO, validar.VEREDICTOS_SIN_AUTORIA)

    def test_la_precedencia_lo_pone_debajo_de_PERMITIDO_y_PROTEGIDO(self):
        v = list(validar.VEREDICTOS_ALCANCE)
        self.assertLess(v.index(validar.ALCANCE_NO_DECLARADO), v.index(validar.PROTEGIDO_GLOBAL))
        self.assertLess(v.index(validar.PROTEGIDO_GLOBAL), v.index(validar.PERMITIDO))
        self.assertLess(v.index(validar.PERMITIDO), v.index(validar.IMPORTADO))
        self.assertLess(v.index(validar.IMPORTADO), v.index(validar.FUERA_DE_ALCANCE))

    def test_un_bloque_no_puede_fabricar_IMPORTADO_declarandolo(self):
        """Condicion 6 del encargo. Declarar una ruta en el contrato produce
        PERMITIDO -- que es una autorizacion explicita y auditable-- o nada.
        La procedencia no se declara: se demuestra contra git."""
        inventada = "engine/causal/mecanismos.py"
        c = _contrato(bloques={"S0": {"escritura": ["contexto/"],
                                      "importado": [inventada],
                                      "procedencia": "confia en mi"}})
        c["alcance"] = {"importado": {"merge_de_integracion":
                                      validar.merge_de_integracion()}}
        c["bloques"]["S0"]["desde"] = estado.cargar_contrato()["bloques"]["S0"]["desde"]
        ver, _bid = validar.veredicto_alcance([inventada], contrato=c)
        self.assertEqual(ver[inventada], validar.FUERA_DE_ALCANCE)

    def test_lo_protegido_sigue_protegido_aunque_llegase_por_el_merge(self):
        """Condicion 5. Si IMPORTADO ganase a PROTEGIDO_GLOBAL, la superficie
        historica podria blanquearse integrando. No puede."""
        protegida = sorted(validar.superficie_protegida())[0]
        c = _contrato(bloques={"S0": {"escritura": []}})
        c["alcance"] = {"importado": {"merge_de_integracion":
                                      validar.merge_de_integracion()}}
        ver, _bid = validar.veredicto_alcance([protegida], contrato=c)
        self.assertEqual(ver[protegida], validar.PROTEGIDO_GLOBAL)
        ok, motivo = validar.guarda_alcance([protegida], contrato=c)
        self.assertFalse(ok, "una ruta del manifiesto no pasa sin su condicion")
        self.assertIn(validar.PROTEGIDO_GLOBAL, motivo)


class TestLasTresCondiciones(unittest.TestCase):
    """Ninguna es opcional, y la tercera no es redundante con la segunda."""

    RUTA = "data/thesis/BTC.json"

    def setUp(self):
        self.merge = validar.merge_de_integracion()
        self.p1, self.p2 = validar._padres(self.merge)

    def test_1_con_las_tres_cumplidas_es_IMPORTADO(self):
        ok, motivo = validar.procedencia_importada(self.RUTA)
        self.assertTrue(ok, motivo)

    def test_2_una_ruta_que_el_bloque_movio_no_es_IMPORTADO(self):
        """Sobre el estado real. La topologia sintetica de
        TestTopologiaDeMerge aisla las tres condiciones una a una."""
        ok, motivo = validar.procedencia_importada("contexto/validar.py")
        self.assertFalse(ok)

    def test_3_si_el_bloque_toca_la_ruta_no_es_IMPORTADO(self):
        """La tercera condicion, sobre el caso que las otras dos no ven: el
        log del bloque. Se fuerza declarando un `desde` que SI contiene commits
        que tocan la ruta."""
        self.assertTrue(validar._tocada_por_el_bloque(
            "contexto/validar.py", estado.cargar_contrato()["bloques"]["S0"]["desde"],
            self.p1))
        self.assertFalse(validar._tocada_por_el_bloque(
            self.RUTA, estado.cargar_contrato()["bloques"]["S0"]["desde"], self.p1))

    def test_un_fichero_escrito_por_S0_se_clasifica_por_su_alcance(self):
        """Condicion 4 del encargo: autoria propia NUNCA se reclasifica."""
        for ruta in ("contexto/validar.py", "engine/contract/reconciliar_metrics.py"):
            ver, _b = validar.veredicto_alcance([ruta])
            self.assertEqual(ver[ruta], validar.PERMITIDO, ruta)
            self.assertFalse(validar.procedencia_importada(ruta)[0], ruta)

    def test_una_ruta_ausente_no_se_importa(self):
        """Borrar es un acto de autoria. Sin esta comprobacion dos ausencias
        compararian iguales y pasarian solas."""
        ok, motivo = validar.procedencia_importada("data/metrics/BTC.json")
        self.assertFalse(ok)
        self.assertIn("no existe", motivo)


class TestElMecanismoEsPequeno(unittest.TestCase):
    """No se construye un sistema generico de merges: se consulta UNO."""

    def test_sin_merge_declarado_no_se_importa_nada(self):
        c = dict(estado.cargar_contrato())
        c["alcance"] = dict(c["alcance"], importado={})
        ok, motivo = validar.procedencia_importada("data/thesis/BTC.json", contrato=c)
        self.assertFalse(ok)
        self.assertIn("sin `alcance.importado.merge_de_integracion`", motivo)

    def test_un_merge_que_no_se_resuelve_no_concede(self):
        c = dict(estado.cargar_contrato())
        c["alcance"] = dict(c["alcance"],
                            importado={"merge_de_integracion": "0" * 40})
        ok, motivo = validar.procedencia_importada("data/thesis/BTC.json", contrato=c)
        self.assertFalse(ok)
        self.assertIn("no se resuelve", motivo)

    def test_un_commit_sin_dos_padres_no_es_un_merge_de_integracion(self):
        c = dict(estado.cargar_contrato())
        sin_merge = validar._padres(validar.merge_de_integracion())[0]
        c["alcance"] = dict(c["alcance"],
                            importado={"merge_de_integracion": sin_merge})
        ok, motivo = validar.procedencia_importada("data/thesis/BTC.json", contrato=c)
        self.assertFalse(ok)
        self.assertIn("dos padres", motivo)

    def test_el_contrato_declara_el_limite_explicitamente(self):
        d = estado.cargar_contrato()["alcance"]["importado"]
        self.assertRegex(d["limite_del_mecanismo"],
                         r"(?i)no es una autorizacion generica")
        self.assertRegex(d["que_es"], r"(?i)no una autorizacion")
        self.assertEqual(len(d["condiciones"]), 4)

    def test_no_hay_descubrimiento_automatico_de_merges(self):
        """Si el modulo buscase merges por su cuenta, el mecanismo crecería
        solo. Solo puede leer el que el contrato declara."""
        with open(os.path.join(RAIZ, "contexto", "validar.py"),
                  encoding="utf-8") as fh:
            fuente = fh.read()
        i = fuente.index("def merge_de_integracion")
        j = fuente.index("def veredicto_alcance")
        for prohibido in ("--merges", "rev-list --all", "for-each-ref"):
            self.assertNotIn(prohibido, fuente[i:j], prohibido)


class TestLaIntegracionRealDeS0(unittest.TestCase):
    """Sobre el estado real, no sobre un contrato de prueba."""

    IMPORTADAS = tuple(f"data/thesis/{a}.json"
                       for a in ("ADA", "BTC", "DOT", "ETH", "SOL", "XRP"))

    def test_las_seis_rutas_del_cron_son_IMPORTADO(self):
        ver, _b = validar.veredicto_alcance(list(self.IMPORTADAS))
        for r in self.IMPORTADAS:
            self.assertEqual(ver[r], validar.IMPORTADO, r)

    def test_el_bloque_S0_vuelve_a_cumplir_su_propio_alcance(self):
        import alcance_pr
        rutas, _origen, _rango = alcance_pr.rutas_a_evaluar()
        ok, motivo = validar.guarda_alcance(rutas)
        self.assertTrue(ok, motivo)

    def test_no_queda_ninguna_ruta_FUERA_DE_ALCANCE(self):
        import alcance_pr
        rutas, _o, _r = alcance_pr.rutas_a_evaluar()
        ver, _b = validar.veredicto_alcance(rutas)
        fuera = sorted(r for r, v in ver.items() if v == validar.FUERA_DE_ALCANCE)
        self.assertEqual(fuera, [])

    def test_los_ocho_metrics_siguen_sin_resucitar(self):
        """La resolucion del merge no puede deshacerse por un cambio de guarda."""
        for a in ("ADA", "BTC", "DOT", "EA", "ETH", "SOL", "US", "XRP"):
            self.assertFalse(os.path.exists(
                os.path.join(RAIZ, "data", "metrics", f"{a}.json")))


class TestTopologiaDeMerge(unittest.TestCase):
    """Las tres condiciones, AISLADAS sobre un repositorio sintetico.

    El repositorio real no contiene el caso decisivo -- una ruta que el bloque
    modifica y luego REVIERTE -- y es justamente el que separa la condicion 3
    de la 2. Construirlo es la unica forma de demostrar que la 3 no sobra.

    Se escribe en un directorio temporal propio; el repositorio del proyecto
    no se toca.
    """

    @classmethod
    def setUpClass(cls):
        import subprocess, tempfile
        cls.tmp = tempfile.mkdtemp(prefix="botinv_merge_")
        def git(*a):
            subprocess.run(["git", "-C", cls.tmp] + list(a), check=True,
                           capture_output=True)
        def escribir(rel, txt):
            with open(os.path.join(cls.tmp, rel), "w", encoding="utf-8") as fh:
                fh.write(txt)
        cls.git, cls.escribir = staticmethod(git), staticmethod(escribir)

        git("init", "-q", "-b", "base")
        git("config", "user.email", "t@t"); git("config", "user.name", "t")
        # `raiz` es el repositorio que se juzga, y un repositorio que se juzga
        # tiene manifiesto. Vacio: aqui no hay superficie protegida que probar
        # -- de eso se ocupa test_lo_protegido_sigue_protegido... sobre el real.
        os.makedirs(os.path.join(cls.tmp, "contexto"))
        escribir(os.path.join("contexto", "manifiesto.json"), '{"ficheros": {}}\n')
        for rel in ("importada.txt", "propia.txt", "revertida.txt", "tomada_de_base.txt"):
            escribir(rel, "merge-base\n")
        git("add", "-A"); git("commit", "-qm", "merge-base")
        cls.MB = subprocess.run(["git", "-C", cls.tmp, "rev-parse", "HEAD"],
                                capture_output=True, text=True).stdout.strip()

        # Lado del BLOQUE (primer padre)
        git("checkout", "-q", "-b", "bloque")
        escribir("desde.txt", "inicio del bloque\n")
        git("add", "-A"); git("commit", "-qm", "desde")
        cls.DESDE = subprocess.run(["git", "-C", cls.tmp, "rev-parse", "HEAD"],
                                   capture_output=True, text=True).stdout.strip()
        escribir("propia.txt", "escrita por el bloque\n")
        escribir("revertida.txt", "el bloque la toca...\n")
        escribir("tomada_de_base.txt", "el bloque tambien la movio\n")
        git("add", "-A"); git("commit", "-qm", "el bloque escribe")
        escribir("revertida.txt", "merge-base\n")          # ...y la REVIERTE
        git("add", "-A"); git("commit", "-qm", "y revierte una")

        # Lado INTEGRADO (segundo padre)
        git("checkout", "-q", "base")
        for rel in ("importada.txt", "revertida.txt", "tomada_de_base.txt"):
            escribir(rel, "contenido de la base\n")
        git("add", "-A"); git("commit", "-qm", "el cron de la base")

        # Merge de integracion: la base entra en la rama del bloque
        git("checkout", "-q", "bloque")
        subprocess.run(["git", "-C", cls.tmp, "merge", "--no-ff", "--no-edit",
                        "-X", "theirs", "base"], capture_output=True)
        cls.MERGE = subprocess.run(["git", "-C", cls.tmp, "rev-parse", "HEAD"],
                                   capture_output=True, text=True).stdout.strip()

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _contrato_sintetico(self):
        return {"bloque_activo": "B",
                "bloques": {"B": {"escritura": ["propia.txt"], "desde": self.DESDE,
                                  "hasta": None}},
                "alcance": {"importado": {"merge_de_integracion": self.MERGE}}}

    def _procedencia(self, ruta):
        return validar.procedencia_importada(ruta, contrato=self._contrato_sintetico(),
                                             raiz=self.tmp)

    def test_la_topologia_es_la_esperada(self):
        """Sin esta comprobacion, un fallo de construccion pasaria por exito."""
        p1, p2 = validar._padres(self.MERGE, raiz=self.tmp)
        self.assertTrue(p1 and p2, "el merge tiene que tener dos padres")
        self.assertEqual(validar._blob("HEAD", "importada.txt", self.tmp),
                         validar._blob(p2, "importada.txt", self.tmp))

    def test_caso_1_las_tres_condiciones_cumplidas_es_IMPORTADO(self):
        ok, motivo = self._procedencia("importada.txt")
        self.assertTrue(ok, motivo)

    def test_caso_2_HEAD_igual_al_segundo_padre_pero_el_bloque_la_movio(self):
        """`HEAD == P2` NO es suficiente. La condicion 2 es obligatoria."""
        p1, p2 = validar._padres(self.MERGE, raiz=self.tmp)
        self.assertEqual(validar._blob("HEAD", "tomada_de_base.txt", self.tmp),
                         validar._blob(p2, "tomada_de_base.txt", self.tmp),
                         "premisa: el merge tomo el lado de la base")
        self.assertNotEqual(validar._blob(p1, "tomada_de_base.txt", self.tmp),
                            validar._blob(self.MB, "tomada_de_base.txt", self.tmp),
                            "premisa: el bloque la habia movido")
        ok, motivo = self._procedencia("tomada_de_base.txt")
        self.assertFalse(ok, "condicion 2 incumplida y aun asi paso")
        self.assertIn("movio la ruta respecto al merge-base", motivo)

    def test_caso_3_modificada_y_revertida_no_es_IMPORTADO(self):
        """EL CASO QUE JUSTIFICA LA TERCERA CONDICION. blob(P1) == blob(MB)
        porque el bloque deshizo su cambio, asi que la condicion 2 pasa. Pero
        el bloque SI la modifico, y el log lo ve."""
        p1, _p2 = validar._padres(self.MERGE, raiz=self.tmp)
        self.assertEqual(validar._blob(p1, "revertida.txt", self.tmp),
                         validar._blob(self.MB, "revertida.txt", self.tmp),
                         "premisa: la condicion 2 pasa")
        self.assertTrue(validar._tocada_por_el_bloque(
            "revertida.txt", self.DESDE, p1, self.tmp), "premisa: el bloque la toco")
        ok, motivo = self._procedencia("revertida.txt")
        self.assertFalse(ok, "la condicion 3 es redundante si esto pasa")
        self.assertIn("algun commit del bloque toca la ruta", motivo)

    def test_caso_4_autoria_propia_se_clasifica_por_su_alcance(self):
        c = self._contrato_sintetico()
        ver, _b = validar.veredicto_alcance(["propia.txt"], contrato=c, raiz=self.tmp)
        self.assertEqual(ver["propia.txt"], validar.PERMITIDO)
        self.assertFalse(self._procedencia("propia.txt")[0])

    def test_el_veredicto_completo_sobre_la_topologia(self):
        c = self._contrato_sintetico()
        rutas = ["importada.txt", "propia.txt", "revertida.txt", "tomada_de_base.txt"]
        ver, _b = validar.veredicto_alcance(rutas, contrato=c, raiz=self.tmp)
        self.assertEqual(ver, {"importada.txt": validar.IMPORTADO,
                               "propia.txt": validar.PERMITIDO,
                               "revertida.txt": validar.FUERA_DE_ALCANCE,
                               "tomada_de_base.txt": validar.FUERA_DE_ALCANCE})
