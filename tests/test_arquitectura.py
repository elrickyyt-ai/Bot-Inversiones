# -*- coding: utf-8 -*-
"""Arquitectura objetivo -- S0.4.

    "esta en la arquitectura"  !=  "esta implementado"

Lo que estos tests fijan es que esa distincion es MECANICA y no depende de que
alguien se acuerde de actualizar una tabla:

    IMPLEMENTED se DERIVA del ancla de codigo
    PARTIAL / PLANNED / NOT_AUTHORIZED son DECLARACIONES, no derivables
    y la comprobacion va en los DOS sentidos

Ninguna mutacion escribe en el repositorio: todos los contratos de prueba son
diccionarios en memoria.
"""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "contexto"))

import estado  # noqa: E402
import validar  # noqa: E402

OBJETIVO = "contexto/ARQUITECTURA_OBJETIVO.md"


def _contrato(componentes):
    return {"arquitectura_objetivo": {"componentes": componentes}}


class TestEstadoDerivadoVsDeclarativo(unittest.TestCase):
    """La separacion que pedia la autorizacion, punto 4."""

    def test_implemented_se_deriva_del_ancla(self):
        c = _contrato([{"id": "X", "nivel": "1", "estado_declarado": "IMPLEMENTED",
                        "ancla": "contexto/validar.py"}])
        f = validar.estado_arquitectura(c)[0]
        self.assertTrue(f["ancla_resuelve"])
        self.assertEqual(f["estado_efectivo"], validar.IMPLEMENTED)
        self.assertTrue(f["ok"])

    def test_implemented_sin_ancla_resoluble_FALLA(self):
        """El caso que convierte un documento de arquitectura en ficcion: el
        componente se borra y la tabla sigue diciendo IMPLEMENTED."""
        c = _contrato([{"id": "X", "nivel": "1", "estado_declarado": "IMPLEMENTED",
                        "ancla": "engine/no/existe.py"}])
        f = validar.estado_arquitectura(c)[0]
        self.assertFalse(f["ok"])
        self.assertIn(validar.ARQUITECTURA_ANCLA_NO_RESOLUBLE, f["motivo"])
        self.assertIsNone(f["estado_efectivo"],
                          "no puede salir IMPLEMENTED si el ancla no existe")

    def test_partial_exige_ancla(self):
        c = _contrato([{"id": "X", "nivel": "1", "estado_declarado": "PARTIAL",
                        "ancla": None}])
        f = validar.estado_arquitectura(c)[0]
        self.assertFalse(f["ok"])
        self.assertIn(validar.ARQUITECTURA_ANCLA_NO_RESOLUBLE, f["motivo"])

    def test_planned_y_not_authorized_son_declaraciones_no_derivadas(self):
        """Sin codigo no se puede CALCULAR si algo esta planificado o prohibido:
        la ausencia de ancla no distingue los dos casos. Por eso son declarativos
        y el estado efectivo es la declaracion misma."""
        for declarado in ("PLANNED", "NOT_AUTHORIZED"):
            c = _contrato([{"id": "X", "nivel": "2",
                            "estado_declarado": declarado, "ancla": None}])
            f = validar.estado_arquitectura(c)[0]
            self.assertTrue(f["ok"], declarado)
            self.assertEqual(f["estado_efectivo"], declarado)
            self.assertFalse(f["ancla_resuelve"])

    def test_planned_con_ancla_FALLA_por_declaracion_obsoleta(self):
        """El sentido inverso, y es el que de verdad envejece: aparece codigo
        bajo un componente declarado PLANNED."""
        c = _contrato([{"id": "X", "nivel": "2", "estado_declarado": "PLANNED",
                        "ancla": "contexto/validar.py"}])
        f = validar.estado_arquitectura(c)[0]
        self.assertFalse(f["ok"])
        self.assertIn(validar.ARQUITECTURA_ESTADO_DIVERGENTE, f["motivo"])

    def test_not_authorized_con_ancla_FALLA(self):
        c = _contrato([{"id": "X", "nivel": "2",
                        "estado_declarado": "NOT_AUTHORIZED",
                        "ancla": "contexto/validar.py"}])
        f = validar.estado_arquitectura(c)[0]
        self.assertFalse(f["ok"])
        self.assertIn(validar.ARQUITECTURA_ESTADO_DIVERGENTE, f["motivo"])

    def test_estado_fuera_del_vocabulario_FALLA(self):
        c = _contrato([{"id": "X", "nivel": "1", "estado_declarado": "CASI",
                        "ancla": None}])
        f = validar.estado_arquitectura(c)[0]
        self.assertFalse(f["ok"])
        self.assertIn(validar.ARQUITECTURA_ESTADO_DESCONOCIDO, f["motivo"])

    def test_el_vocabulario_tiene_exactamente_cuatro_estados(self):
        self.assertEqual(len(validar.ESTADOS_ARQUITECTURA), 4)
        self.assertEqual(set(validar.ESTADOS_CON_ANCLA) |
                         set(validar.ESTADOS_SIN_ANCLA),
                         set(validar.ESTADOS_ARQUITECTURA))
        self.assertFalse(set(validar.ESTADOS_CON_ANCLA) &
                         set(validar.ESTADOS_SIN_ANCLA),
                         "un estado no puede exigir ancla y su ausencia")


class TestNotAuthorizedNoEsNoImplementado(unittest.TestCase):
    """Punto 5 de la autorizacion: NOT_AUTHORIZED no es sinonimo de PLANNED,
    ni de D-01."""

    def setUp(self):
        self.comp = {c["id"]: c for c in validar.componentes_arquitectura()}

    def test_son_estados_distintos_con_semantica_distinta(self):
        self.assertNotEqual(validar.PLANNED, validar.NOT_AUTHORIZED)
        estados = estado.cargar_contrato()["arquitectura_objetivo"]["estados"]
        self.assertIn("deliberadamente", estados["NOT_AUTHORIZED"])
        self.assertNotIn("deliberadamente", estados["PLANNED"])

    def test_execution_y_broker_estan_no_autorizados(self):
        for cid in ("EXECUTION_GATE", "BROKER_ORDER"):
            self.assertEqual(self.comp[cid]["estado_declarado"],
                             validar.NOT_AUTHORIZED, cid)

    def test_investment_proposal_esta_planned_no_prohibido(self):
        """Se va a construir; no esta prohibido. Es el puente del sistema."""
        self.assertEqual(self.comp["INVESTMENT_PROPOSAL"]["estado_declarado"],
                         validar.PLANNED)

    def test_el_contrato_declara_que_no_son_sinonimos_de_D01(self):
        a = estado.cargar_contrato()["arquitectura_objetivo"]
        nota = a["_not_authorized_no_es_d01"]
        self.assertIn("D-01", nota)
        self.assertIn("no son sinonimos", nota)


class TestNoDuplicaElEstadoActual(unittest.TestCase):
    """Punto 3: ARQUITECTURA_OBJETIVO.md no puede ser una segunda ESTADO.md."""

    def setUp(self):
        with open(os.path.join(RAIZ, OBJETIVO), encoding="utf-8") as fh:
            self.txt = fh.read()

    def test_declara_explicitamente_que_no_dice_que_existe_hoy(self):
        self.assertIn("no dice qué existe hoy", self.txt)
        self.assertIn("docs/ESTADO.md", self.txt)

    def test_no_copia_el_diagrama_de_arquitectura_actual(self):
        """ESTADO.md seccion 2 tiene su propio diagrama con las fases P*. Si
        aparecieran aqui, seria duplicacion como verdad."""
        with open(os.path.join(RAIZ, "docs", "ESTADO.md"), encoding="utf-8") as fh:
            actual = fh.read()
        # Lineas distintivas del diagrama de ESTADO.md que no deben reaparecer
        for linea in ("P6.2a INTEGRIDAD TEMPORAL", "resolve_instrument(identifier, as_of)",
                      "P5D  Data Requirements"):
            self.assertIn(linea, actual, "linea de referencia no encontrada")
            self.assertNotIn(linea, self.txt, f"duplica ESTADO.md: {linea!r}")

    def test_no_transcribe_la_tabla_de_estados_calculados(self):
        """El documento REFIERE el calculo; no lleva la tabla dentro, que
        quedaria obsoleta sin que nada lo detectase."""
        self.assertIn("estado_arquitectura()", self.txt)
        for cid in ("EVENT_CLAIM", "CAUSAL_ASSESSMENT", "POLICY_REGISTRY"):
            self.assertNotIn(cid, self.txt,
                             "los ids del contrato no se transcriben aqui")


class TestNamespacesSeparados(unittest.TestCase):
    """Punto 6: contexto:L0 y autonomia:L0..L4 no se mezclan."""

    def setUp(self):
        self.ns = estado.cargar_contrato()["arquitectura_objetivo"]["namespaces"]
        with open(os.path.join(RAIZ, OBJETIVO), encoding="utf-8") as fh:
            self.txt = fh.read()

    def test_los_dos_namespaces_estan_declarados(self):
        self.assertIn("contexto:L0", self.ns)
        self.assertIn("autonomia:L0..L4", self.ns)
        self.assertIn("_colision", self.ns)

    def test_la_escalera_de_autonomia_siempre_lleva_namespace(self):
        """Un `L3` a secas reintroduciria la ambiguedad."""
        for nivel in ("autonomia:L0", "autonomia:L3", "autonomia:L4"):
            self.assertIn(nivel, self.txt, nivel)

    def test_no_se_renombra_el_mecanismo_implementado(self):
        c = estado.cargar_contrato()
        self.assertIn("L0", c, "contexto:L0 sigue siendo la clave L0 del contrato")
        self.assertIn("presupuesto_L0", c)
        self.assertEqual(validar.L0_CLOSURE_VERSION, "l0-closure/v1")

    def test_la_colision_esta_registrada_como_deuda(self):
        deudas = " ".join(estado.cargar_contrato()["open_debt"])
        self.assertIn("DC-5", deudas)


class TestDeudasRegistradas(unittest.TestCase):
    """Punto 7: las tres deudas quedan registradas y sin resolver."""

    def setUp(self):
        self.deudas = " ".join(estado.cargar_contrato()["open_debt"])

    def test_las_tres_deudas_estan(self):
        for d in ("DC-5", "DD-4", "DF-7"):
            self.assertIn(d, self.deudas, d)

    def test_clasificacion_nodos_v2_queda_fuera_de_S0(self):
        self.assertIn("clasificacion-nodos/v2", self.deudas)
        self.assertIn("FUERA de S0", self.deudas)
        # Y no se ha implementado: el mecanismo sigue en v1
        import grafo
        self.assertIn("clasificacion-nodos/v1", open(
            os.path.join(RAIZ, "contexto", "grafo.py"), encoding="utf-8").read())
        self.assertEqual(grafo.clasificar("docs/x.md", []), grafo.HISTORICAL,
                         "v1 sigue vigente: docs/ es HISTORICAL")


class TestArquitecturaReal(unittest.TestCase):
    """El contrato real, sobre el codigo real."""

    def setUp(self):
        self.filas = validar.estado_arquitectura()

    def test_todos_los_componentes_pasan(self):
        for f in self.filas:
            self.assertTrue(f["ok"], f["motivo"])

    def test_los_tres_niveles_y_el_transversal_estan_representados(self):
        niveles = {f["nivel"] for f in self.filas}
        self.assertEqual(niveles, {"1-comprender", "2-decidir",
                                   "3-aprender", "transversal"})

    def test_el_nucleo_epistemologico_esta_implementado(self):
        efectivo = {f["id"]: f["estado_efectivo"] for f in self.filas}
        for cid in ("DATA", "EVIDENCE", "EVENT_CLAIM", "KNOWLEDGE", "CAUSAL_PATH",
                    "CAUSAL_ASSESSMENT", "ECONOMIC_IMPACT", "MATERIALITY", "THESIS"):
            self.assertEqual(efectivo[cid], validar.IMPLEMENTED, cid)

    def test_la_capa_de_decision_no_esta_implementada(self):
        """Lo que la auditoria encontro: el repo no conoce el nivel 2."""
        efectivo = {f["id"]: f["estado_efectivo"] for f in self.filas}
        for cid in ("INVESTMENT_PROPOSAL", "RISK_ASSESSMENT",
                    "INDEPENDENT_VERIFICATION", "HUMAN_APPROVAL"):
            self.assertNotEqual(efectivo[cid], validar.IMPLEMENTED, cid)

    def test_los_assessments_son_parciales_no_implementados(self):
        """Existen como calculo, no como objeto contratado."""
        efectivo = {f["id"]: f["estado_efectivo"] for f in self.filas}
        for cid in ("TECHNICAL_ASSESSMENT", "FUNDAMENTAL_ASSESSMENT"):
            self.assertEqual(efectivo[cid], validar.PARTIAL, cid)

    def test_run_es_transversal_y_esta_planificado(self):
        run = next(f for f in self.filas if f["id"] == "RUN")
        self.assertEqual(run["nivel"], "transversal")
        self.assertEqual(run["estado_efectivo"], validar.PLANNED)

    def test_el_operating_model_no_es_un_componente(self):
        """Las DOS dimensiones no se mezclan. El System Operating Model (B) se
        conserva como flujo conceptual en el documento, pero NO entra en el
        registro de componentes ni recibe estados: darle IMPLEMENTED/PLANNED lo
        convertiria en una hoja de ruta de orquestacion que nadie autorizo."""
        ids = {f["id"] for f in self.filas}
        for concepto in ("PROJECT", "TASK", "COMPLEXITY_GATE", "WORKFLOW",
                         "CONTEXT_RESOLUTION", "RESOURCE_RESOLUTION",
                         "RESEARCH", "ANALYSIS", "VERIFICATION"):
            self.assertNotIn(concepto, ids, concepto)

    def test_los_ids_son_estables_y_unicos(self):
        """Son la clave por la que el validador resuelve cada ancla."""
        import re
        ids = [f["id"] for f in self.filas]
        self.assertEqual(len(ids), len(set(ids)), "ids duplicados")
        for i in ids:
            self.assertRegex(i, r"^[A-Z][A-Z0-9_]*$", i)

    def test_el_validador_incorpora_la_arquitectura_a_su_informe(self):
        informe = validar.validar()
        self.assertIn("arquitectura", informe)
        self.assertEqual(len(informe["arquitectura"]), len(self.filas))


class TestSystemOperatingModel(unittest.TestCase):
    """Dimension B: conservada como concepto, nunca como maquinaria."""

    def setUp(self):
        with open(os.path.join(RAIZ, OBJETIVO), encoding="utf-8") as fh:
            self.txt = fh.read()

    def test_el_flujo_operativo_esta_documentado(self):
        """Excluirlo del documento fue un error de la primera version de S0.4:
        define como trabaja el sistema y es parte de la arquitectura."""
        self.assertIn("System Operating Model", self.txt)
        for paso in ("PROJECT", "TASK", "COMPLEXITY GATE",
                     "CONTEXT / RESOURCE", "WORKFLOW",
                     "RESEARCH", "ANALYSIS", "VERIFICATION"):
            self.assertIn(paso, self.txt, paso)

    def test_las_dos_dimensiones_estan_declaradas_como_distintas(self):
        self.assertIn("dos dimensiones", self.txt)
        self.assertIn("NO está en el registro de componentes", self.txt)

    def test_lo_prohibido_es_la_maquinaria_no_el_concepto(self):
        self.assertIn("Lo que sigue prohibido es la **maquinaria**", self.txt)
        for maquinaria in ("Task Router", "agentes", "skills", "hooks"):
            self.assertIn(maquinaria, self.txt, maquinaria)

    def test_no_existe_maquinaria_de_orquestacion_en_el_arbol(self):
        """La comprobacion que de verdad importa: conservar el concepto no ha
        creado ni un fichero de orquestacion."""
        import subprocess
        r = subprocess.run(["git", "-C", RAIZ, "ls-files"],
                           capture_output=True, text=True)
        for patron in ("task_router", "taskrouter", "agent_manager",
                       "agentmanager", "subagent", "orchestrat"):
            hits = [l for l in r.stdout.lower().splitlines() if patron in l]
            self.assertEqual(hits, [], f"{patron}: {hits}")


class TestGranularidadDeclarada(unittest.TestCase):
    """29 componentes no son 29 capacidades nuevas."""

    def setUp(self):
        with open(os.path.join(RAIZ, OBJETIVO), encoding="utf-8") as fh:
            self.txt = fh.read()

    def test_el_numero_se_declara_como_descomposicion(self):
        self.assertIn("descomposición normativa", self.txt)
        self.assertIn("no una afirmación de que se hayan", self.txt)

    def test_se_citan_las_granularidades_anteriores(self):
        """26 eslabones de la cadena conceptual, 10 capas de la Fase 0."""
        self.assertIn("26", self.txt)
        self.assertIn("docs/00-arquitectura-conceptual.md", self.txt)

    def test_el_numero_declarado_coincide_con_el_registro(self):
        n = len(validar.componentes_arquitectura())
        self.assertIn(f"**{n} componentes**", self.txt)


class TestBacktestNoEsValidacionDePoliticas(unittest.TestCase):
    """PARTIAL no puede leerse como que exista el ciclo de promocion."""

    def setUp(self):
        self.comp = {c["id"]: c for c in validar.componentes_arquitectura()}
        with open(os.path.join(RAIZ, OBJETIVO), encoding="utf-8") as fh:
            self.txt = fh.read()

    def test_el_contrato_declara_que_no_es_backtesting_de_politica(self):
        nota = self.comp["BACKTEST"]["_nota"]
        self.assertIn("NO es backtesting de politica", nota)
        self.assertIn("NO existe en ninguna de sus etapas", nota)

    def test_el_documento_lo_dice_de_forma_visible(self):
        self.assertIn("el bucle de aprendizaje NO existe todavía", self.txt)
        self.assertIn("eso no es backtesting de política", self.txt)

    def test_el_resto_del_ciclo_de_promocion_no_esta_implementado(self):
        efectivo = {f["id"]: f["estado_efectivo"]
                    for f in validar.estado_arquitectura()}
        for cid in ("RISK_TEST", "OOS", "SHADOW", "POLICY_GATE",
                    "POLICY_REGISTRY", "NEW_VERSION", "CANDIDATE_IMPROVEMENT"):
            self.assertEqual(efectivo[cid], validar.PLANNED, cid)

    def test_backtest_no_puede_salir_implemented(self):
        self.assertEqual(self.comp["BACKTEST"]["estado_declarado"],
                         validar.PARTIAL)


class TestFronteraEconomica(unittest.TestCase):
    """THESIS explica; INVESTMENT PROPOSAL decide."""

    def setUp(self):
        with open(os.path.join(RAIZ, OBJETIVO), encoding="utf-8") as fh:
            self.txt = fh.read()

    def test_la_frontera_es_visible(self):
        self.assertIn("La frontera económica del sistema", self.txt)
        self.assertIn("DECISIÓN CANDIDATA", self.txt)
        self.assertIn("aquí el sistema deja de analizar", self.txt)

    def test_dice_que_P1_P6_no_era_solo_analytics(self):
        self.assertIn("no fue «construir más analytics»", self.txt)


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
        validar.estado_arquitectura()
        validar.componentes_arquitectura()
        validar.validar()


if __name__ == "__main__":
    unittest.main(verbosity=2)
