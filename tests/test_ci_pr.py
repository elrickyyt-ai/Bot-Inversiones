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

AUTORIDADES = ("python3 -m unittest discover -s tests",
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
