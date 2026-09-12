# -*- coding: utf-8 -*-
"""T9 de F1 (2026-09-12) -- CI de pull request.

La CI EJECUTA AUTORIDADES; no reimplementa ninguna regla. Estos tests
comprueban justamente eso: que el workflow invoca lo que ya existe, que no
silencia fallos, que no instala dependencias y que no arrastra el QA de
datos al PR.

    PR CI      = integridad de codigo y contexto
    cron diario = QA de datos + verificacion parquet

Ninguna mutacion toca ficheros reales protegidos.
"""
import os
import subprocess
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "contexto"))

import alcance_pr  # noqa: E402
import estado      # noqa: E402
import validar     # noqa: E402

WORKFLOW = os.path.join(RAIZ, ".github", "workflows", "verificar-contexto.yml")
CRON = os.path.join(RAIZ, ".github", "workflows", "actualizar-datos-libres.yml")

AUTORIDADES = ("contexto/suite_pr.py",          # DF-6: la suite, con saltos declarados
               "engine/knowledge/consulta.py --validar",
               "contexto/integridad.py",
               "contexto/extraccion.py",
               "contexto/validar.py",
               "contexto/grafo.py",
               "contexto/alcance_pr.py")


def _texto(path):
    return open(path, encoding="utf-8").read() if os.path.isfile(path) else ""


def _ejecutable(path):
    """El YAML SIN sus comentarios.

    Las prohibiciones ("no ejecutes --require-parquet", "no silencies
    fallos", "no copies una regla") son sobre lo que el workflow HACE. Un
    comentario que explica por que algo NO esta no es una violacion, y
    comprobarlo sobre el fichero entero produce un falso positivo -- ocurrio
    al escribir este test y por eso existe esta funcion."""
    lineas = []
    for l in _texto(path).split("\n"):
        sin = l.split("#", 1)[0] if not l.lstrip().startswith("#") else ""
        lineas.append(sin)
    return "\n".join(lineas)


class TestElWorkflowExiste(unittest.TestCase):
    def test_existe_un_workflow_de_pull_request(self):
        self.assertTrue(_texto(WORKFLOW),
                        "no existe el workflow de PR: el gate de T9 no esta construido")

    def test_se_dispara_en_pull_request(self):
        t = _texto(WORKFLOW)
        self.assertTrue(t, "workflow ausente")
        self.assertIn("pull_request", t, "el workflow no se dispara en pull_request")


class TestEjecutaLasAutoridades(unittest.TestCase):
    def test_invoca_todas_las_autoridades_existentes(self):
        t = _texto(WORKFLOW)
        self.assertTrue(t, "workflow ausente")
        for cmd in AUTORIDADES:
            self.assertIn(cmd, t, f"el workflow no ejecuta la autoridad: {cmd}")

    def test_no_reimplementa_ninguna_regla(self):
        """Si el YAML EJECUTA una constante de regla, hay una segunda
        implementacion y eso es un defecto de diseno."""
        self.assertTrue(_texto(WORKFLOW), "workflow ausente")
        t = _ejecutable(WORKFLOW)

        # Constantes de regla: ninguna puede aparecer.
        for constante in ("ARBOLES_PROHIBIDOS", "canonical_fingerprint",
                          "PREDICADOS_NO_CAUSALES", "l0-budget", "12000", "sha256",
                          "MANDATORY_READ", "CODE-ANCHORED"):
            self.assertNotIn(constante, t,
                             f"el workflow reimplementa o duplica una regla: {constante}")

        # La lista de arboles prohibidos tampoco puede aparecer COMO DATO.
        #
        # Distincion que costo dos falsos positivos al escribir este test:
        # `engine/knowledge/consulta.py` en un `run:` es EJECUTAR una
        # autoridad, y contiene dos arboles protegidos sin ser una lista de
        # reglas. Lo que delataria una copia es un arbol suelto, no formando
        # parte de una ruta a un script que se invoca.
        import re as _re
        for arbol in ("engine/", "data/", "knowledge/"):
            for m in _re.finditer(_re.escape(arbol), t):
                token = _re.search(r"\S*" + _re.escape(arbol) + r"\S*",
                                   t[max(0, m.start() - 60):m.end() + 60]).group(0)
                self.assertTrue(token.endswith(".py"),
                                f"el workflow menciona {arbol} fuera de una ruta "
                                f"ejecutable: {token!r} -- parece una regla copiada")


class TestNoArrastraElQaDeDatos(unittest.TestCase):
    def test_no_ejecuta_require_parquet(self):
        self.assertTrue(_texto(WORKFLOW), "workflow ausente")
        t = _ejecutable(WORKFLOW)
        self.assertTrue(t, "workflow ausente")
        self.assertNotIn("--require-parquet", t,
                         "el QA de datos con parquet es del cron diario, no del PR")

    def test_no_instala_dependencias(self):
        self.assertTrue(_texto(WORKFLOW), "workflow ausente")
        t = _ejecutable(WORKFLOW)
        self.assertTrue(t, "workflow ausente")
        for patron in ("pip install", "npm install", "apt-get", "tiktoken", "pyarrow"):
            self.assertNotIn(patron, t, f"el PR CHECK no instala nada: {patron}")

    def test_el_cron_diario_sigue_intacto_y_sigue_siendo_el_dueno_del_qa(self):
        c = _texto(CRON)
        self.assertIn("--require-parquet", c)
        self.assertIn("schedule", c)
        self.assertNotIn("pull_request", c,
                         "el cron de datos no debe dispararse en PR")


class TestNoSilenciaFallos(unittest.TestCase):
    def test_no_hay_escapes_que_conviertan_FAIL_en_PASS(self):
        self.assertTrue(_texto(WORKFLOW), "workflow ausente")
        t = _ejecutable(WORKFLOW)
        self.assertTrue(t, "workflow ausente")
        for escape in ("|| true", "continue-on-error", "2>/dev/null", "|| exit 0",
                       "set +e", "|| echo"):
            self.assertNotIn(escape, t, f"el workflow silencia fallos: {escape}")


class TestGuardaDeAlcanceConectada(unittest.TestCase):
    """Conectada a un diff real, y delegando la regla."""

    def test_el_alcance_del_bloque_esta_declarado(self):
        """REESCRITO en S0.1 (protocolo de informes, §3). Se apoyaba en
        `alcance_vigente()` y en la clave `alcance_bloque`, que DF-1 retiro.
        La propiedad que sigue siendo cierta -- y es mas fuerte -- es que
        SIEMPRE hay un bloque activo declarado, con su lista de escritura."""
        bid, decl = alcance_pr.bloque_activo()
        self.assertIsNotNone(bid, "el contrato no declara `bloque_activo`")
        self.assertIsNotNone(decl, f"bloque_activo {bid!r} no esta en `bloques`")
        self.assertTrue(decl.get("escritura"), "el bloque debe declarar que escribe")

    def test_una_ruta_no_declarada_por_el_bloque_produce_FAIL(self):
        """REESCRITO en S0.1. Antes fijaba que engine/, data/ y knowledge/
        estaban prohibidos SIEMPRE; eso era la formulacion del interruptor y
        caduco al resolverse DF-1: el alcance es del BLOQUE (S0 declara
        data/incoming/ y engine/contract/ legitimamente).

        La propiedad que sobrevive: lo que el bloque activo NO declara no se
        permite. Se fija con un contrato explicito en memoria, para no
        depender de que bloque este activo hoy."""
        c = {"bloque_activo": "X", "bloques": {"X": {"escritura": ["contexto/"]}}}
        for ruta in ("engine/knowledge/modelo.py", "data/incoming/BTC_2026.csv",
                     "knowledge/entities/securities.json"):
            codigo, motivo = alcance_pr.verificar([ruta], contrato=c)
            self.assertEqual(codigo, 1, ruta)
            self.assertIn(validar.FUERA_DE_ALCANCE, motivo)

    def test_los_cambios_legitimos_de_F1_pasan(self):
        """contexto/, tests/ y la configuracion de CI no se bloquean."""
        rutas = ["contexto/validar.py", "tests/test_ci_pr.py",
                 ".github/workflows/verificar-contexto.yml", "informes/nuevo.md"]
        codigo, motivo = alcance_pr.verificar(rutas)
        self.assertEqual(codigo, 0, motivo)

    def test_lee_un_diff_de_git_de_verdad(self):
        rutas = alcance_pr.ficheros_cambiados(head="HEAD")
        self.assertIsInstance(rutas, list)

    def test_delega_la_regla_y_no_la_copia(self):
        fuente = open(os.path.join(RAIZ, "contexto", "alcance_pr.py"),
                      encoding="utf-8").read()
        cuerpo = fuente.split('"""', 2)[-1]
        self.assertIn("guarda_alcance", cuerpo, "tiene que delegar en la autoridad")
        self.assertNotIn("ARBOLES_PROHIBIDOS =", cuerpo,
                         "no puede tener su propia copia de la lista")

    def test_sin_declaracion_no_asume_nada(self):
        """REESCRITO en S0.1: la clave que se retira ahora es `bloque_activo`,
        no `alcance_bloque`. La propiedad es identica -- sin declaracion la
        guarda no asume nada y falla."""
        c = estado.cargar_contrato()
        c.pop("bloque_activo", None)
        codigo, motivo = alcance_pr.verificar(["engine/x.py"], contrato=c)
        self.assertEqual(codigo, 1)
        self.assertIn(alcance_pr.ALCANCE_NO_DECLARADO, motivo)

    def test_no_queda_ningun_interruptor_que_apagar(self):
        """REESCRITO en S0.1, y la propiedad se INVIERTE a proposito.

        El test anterior EXIGIA que existiese un interruptor (`vigente` +
        `como_se_cierra`). DF-1 demostro que ese interruptor era el defecto:
        apagarlo dejaba proteccion cero. La transicion correcta entre bloques
        es SUSTITUIR el alcance, no desactivarlo, asi que ahora se exige lo
        contrario -- que ningun interruptor exista."""
        c = estado.cargar_contrato()
        self.assertNotIn("alcance_bloque", c)
        for bid, decl in c["bloques"].items():
            self.assertNotIn("vigente", decl, bid)
            self.assertNotIn("como_se_cierra", decl, bid)
        # Y el alcance sigue aplicandose sobre una ruta no declarada:
        codigo, _ = alcance_pr.verificar(["engine/causal/mecanismos.py"])
        self.assertEqual(codigo, 1, "la guarda tiene que seguir aplicando")


class TestDF6SaltosDeclarados(unittest.TestCase):
    """DF-6: el gate era irreproducible en clean-room y nadie lo supo porque el
    repositorio no habia tenido ni un PR."""

    def setUp(self):
        sys.path.insert(0, os.path.join(RAIZ, "contexto"))
        import suite_pr
        self.sp = suite_pr
        self.esperados, self.decl = suite_pr.declaracion()

    def test_el_contrato_declara_los_saltos(self):
        self.assertIsInstance(self.esperados, int)
        self.assertGreater(self.esperados, 0)
        self.assertTrue(self.decl.get("motivo"))

    def test_el_numero_no_esta_en_el_workflow_ni_en_la_autoridad(self):
        """Seria una segunda copia: el mismo defecto que DF-1 corrigio."""
        n = str(self.esperados)
        self.assertNotIn(n, _ejecutable(WORKFLOW))
        with open(os.path.join(RAIZ, "contexto", "suite_pr.py"),
                  encoding="utf-8") as fh:
            fuente = fh.read()
        cuerpo = fuente.split('"""', 2)[-1]
        self.assertNotIn(n, cuerpo, "la autoridad LEE el numero, no lo lleva")

    def test_saltos_distintos_de_los_declarados_FALLAN(self):
        """En los DOS sentidos, y por razones distintas."""
        base = f"Ran 1052 tests in 3.5s\n\nOK (skipped={self.esperados})\n"
        ok, cod, _ = self.sp.evaluar(base, self.esperados)
        self.assertTrue(ok, "el caso declarado tiene que pasar")
        for delta in (+1, -1):
            salida = base.replace(f"skipped={self.esperados}",
                                  f"skipped={self.esperados + delta}")
            ok2, cod2, _ = self.sp.evaluar(salida, self.esperados)
            self.assertFalse(ok2, f"delta {delta:+d}")
            self.assertEqual(cod2, self.sp.SUITE_SKIPS_INESPERADOS)

    def test_un_error_de_import_no_es_un_salto(self):
        salida = ("Ran 927 tests in 3.5s\n\nFAILED (errors=43, skipped=12)\n")
        ok, cod, cifras = self.sp.evaluar(salida, self.esperados)
        self.assertFalse(ok)
        self.assertEqual(cod, self.sp.SUITE_CON_ERRORES,
                         "43 ImportError no pueden confundirse con saltos")
        self.assertEqual(cifras["errors"], 43)

    def test_un_fallo_de_test_tambien_falla(self):
        salida = (f"Ran 1052 tests in 3.5s\n\n"
                  f"FAILED (failures=1, skipped={self.esperados})\n")
        ok, cod, _ = self.sp.evaluar(salida, self.esperados)
        self.assertFalse(ok)
        self.assertEqual(cod, self.sp.SUITE_CON_ERRORES)

    def test_sin_declaracion_no_asume_nada(self):
        ok, cod, _ = self.sp.evaluar("Ran 1 test\n\nOK\n", None)
        self.assertFalse(ok)
        self.assertEqual(cod, self.sp.SUITE_SIN_DECLARACION)

    def test_una_salida_no_interpretable_falla(self):
        ok, cod, _ = self.sp.evaluar("el runner murio", self.esperados)
        self.assertFalse(ok)
        self.assertEqual(cod, self.sp.SUITE_NO_INTERPRETABLE)

    @unittest.skipIf(os.environ.get("BOTINV_SUITE_ANIDADA") == "1",
                     "ejecucion anidada: este test lanza la suite entera y "
                     "sin este guarda se invocaria a si mismo en recursion")
    def test_el_clean_room_real_coincide_con_lo_declarado(self):
        """La comprobacion que de verdad cierra DF-6: se ejecuta la suite con
        pyarrow inutilizable y se exige 0 errores y los saltos declarados.

        El marcador BOTINV_SUITE_ANIDADA corta la recursion: sin el, cada nivel
        lanzaria la suite completa otra vez. Detectado al escribir el test."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "pyarrow.py"), "w") as fh:
                fh.write("raise ImportError('clean-room')\n")
            env = dict(os.environ, PYTHONPATH=tmp, BOTINV_SUITE_ANIDADA="1")
            r = subprocess.run([sys.executable, "-m", "unittest", "discover",
                                "-s", "tests"], capture_output=True, text=True,
                               cwd=RAIZ, env=env)
        salida = r.stdout + r.stderr
        cifras = self.sp.leer(salida)
        self.assertIsNotNone(cifras, salida[-400:])
        self.assertEqual(cifras["errors"], 0, "ningun ImportError en clean-room")
        self.assertEqual(cifras["failures"], 0)
        self.assertEqual(cifras["skipped"], self.esperados + 1,
                         "el anidado salta uno mas: este propio test")
        self.assertEqual(r.returncode, 0)

    def test_el_cron_fija_la_version_de_pyarrow(self):
        """Un proyecto que pinea todas sus fuentes no puede dejar suelta la
        biblioteca que serializa su historico."""
        c = _texto(CRON)
        self.assertRegex(c, r"pip install[^\n]*pyarrow==\d+\.\d+")

    def test_el_cron_sigue_siendo_el_dueno_del_qa_de_parquet(self):
        c = _texto(CRON)
        self.assertIn("--require-parquet", c)
        self.assertIn("pyarrow", c)

    def test_el_PR_sigue_sin_instalar_nada(self):
        t = _ejecutable(WORKFLOW)
        for patron in ("pip install", "npm install", "apt-get", "pyarrow"):
            self.assertNotIn(patron, t, patron)


class TestLasAutoridadesSiguenPasando(unittest.TestCase):
    """El caso PASS: sobre el estado real, todas devuelven 0."""

    def test_cada_autoridad_devuelve_cero(self):
        for script in ("contexto/integridad.py", "contexto/extraccion.py",
                       "contexto/validar.py", "contexto/grafo.py"):
            r = subprocess.run([sys.executable, os.path.join(RAIZ, script)],
                               capture_output=True, text=True, cwd=RAIZ)
            self.assertEqual(r.returncode, 0, f"{script}: {r.stdout}{r.stderr}")

    def test_consulta_validar_devuelve_cero(self):
        r = subprocess.run([sys.executable, os.path.join(RAIZ, "engine", "knowledge",
                                                         "consulta.py"), "--validar"],
                           capture_output=True, text=True, cwd=RAIZ)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestElPipelinePropagaElFAIL(unittest.TestCase):
    """El punto de T9: si una autoridad falla, el PR falla.

    Se comprueba con procesos reales -- el mismo mecanismo que usa el
    workflow -- sobre COPIAS temporales. Ningun fichero protegido se toca.
    """

    def _copia_de_trabajo(self):
        """Copia minima del repositorio donde SI se puede romper algo."""
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp()
        for sub in ("contexto", "docs", "informes", "engine/knowledge"):
            shutil.copytree(os.path.join(RAIZ, sub), os.path.join(tmp, sub),
                            ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(os.path.join(RAIZ, "CLAUDE.md"), os.path.join(tmp, "CLAUDE.md"))
        return tmp

    def _correr(self, script, cwd):
        return subprocess.run([sys.executable, os.path.join(cwd, script)],
                              capture_output=True, text=True, cwd=cwd)

    def test_PASS_el_pipeline_limpio_devuelve_cero(self):
        tmp = self._copia_de_trabajo()
        try:
            r = self._correr("contexto/integridad.py", tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("PASS", r.stdout)
        finally:
            import shutil
            shutil.rmtree(tmp)

    def test_FAIL_historico_alterado_hace_fallar_el_job(self):
        """Caso FAIL histórico: alterar un artefacto protegido -> exit != 0."""
        tmp = self._copia_de_trabajo()
        try:
            victima = os.path.join(tmp, "docs", "ESTADO.md")
            with open(victima, "a", encoding="utf-8") as fh:
                fh.write("\n<!-- alteracion artificial -->\n")
            r = self._correr("contexto/integridad.py", tmp)
            self.assertNotEqual(r.returncode, 0,
                                "un historico alterado TIENE que hacer fallar el job")
            self.assertIn("ALTERED", r.stdout)
            self.assertIn("FAIL", r.stdout)
        finally:
            import shutil
            shutil.rmtree(tmp)

    def test_FAIL_historico_perdido_hace_fallar_el_job(self):
        tmp = self._copia_de_trabajo()
        try:
            os.remove(os.path.join(tmp, "docs", "ESTADO.md"))
            r = self._correr("contexto/integridad.py", tmp)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("LOST", r.stdout)
        finally:
            import shutil
            shutil.rmtree(tmp)

    def test_FAIL_de_alcance_un_cambio_en_engine_hace_fallar_el_job(self):
        """Caso FAIL de alcance, sobre el diff, sin tocar engine/ real."""
        codigo, motivo = alcance_pr.verificar(
            ["contexto/validar.py", "engine/knowledge/modelo.py"])
        self.assertEqual(codigo, 1)
        self.assertIn(validar.FUERA_DE_ALCANCE, motivo)

    def test_FAIL_de_contexto_L0_divergente_hace_fallar_el_job(self):
        """Caso FAIL de contexto: se reutiliza la mutacion de T8, no se
        duplica la bateria."""
        c = estado.cargar_contrato()
        c["L0"] = ["CLAUDE.md"]
        informe = validar.validar(contrato=c)
        self.assertTrue(informe["incidencias"])
        self.assertTrue(any(validar.L0_DIVERGENTE in i for i in informe["incidencias"]))

    def test_el_codigo_de_salida_no_se_captura_en_ningun_sitio(self):
        """Ninguna autoridad envuelve su fallo en un try que devuelva 0."""
        for mod in ("integridad.py", "extraccion.py", "validar.py", "grafo.py",
                    "alcance_pr.py"):
            fuente = open(os.path.join(RAIZ, "contexto", mod), encoding="utf-8").read()
            main = fuente[fuente.index("def main("):]
            self.assertIn("return", main)
            self.assertNotIn("except Exception:\n        return 0", main)
