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

    def test_ningun_componente_de_orquestacion_de_agente(self):
        """El diseno conceptual de origen incluia TASK, COMPLEXITY GATE y
        WORKFLOW. Registrarlos habria introducido por la puerta de atras la
        infraestructura de agente que los invariantes prohiben."""
        ids = {f["id"] for f in self.filas}
        for prohibido in ("TASK", "COMPLEXITY_GATE", "WORKFLOW",
                          "CONTEXT_RESOLUTION", "RESOURCE_RESOLUTION"):
            self.assertNotIn(prohibido, ids, prohibido)

    def test_el_validador_incorpora_la_arquitectura_a_su_informe(self):
        informe = validar.validar()
        self.assertIn("arquitectura", informe)
        self.assertEqual(len(informe["arquitectura"]), len(self.filas))


class TestNoEscribeNada(unittest.TestCase):

    def test_ninguna_comprobacion_altero_el_repositorio(self):
        import subprocess
        r = subprocess.run(["git", "-C", RAIZ, "status", "--porcelain",
                            "docs", "informes", "engine", "knowledge", "data"],
                           capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
