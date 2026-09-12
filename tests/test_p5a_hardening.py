# -*- coding: utf-8 -*-
"""P5A hardening -- D-49 variante C aplicada (D-53, 2026-09-11).

    "no restringir el recorrido; exigir >=1 arista CAUSAL en el camino emitido"
    -- docs/DECISIONES.md, D-49, literal.

LO QUE ESTOS TESTS PROTEGEN
---------------------------
La regla es SEMANTICA: un camino es causal porque CONTIENE al menos una
arista declarada causal, no porque nadie lo haya metido en una lista
negra. `el sistema no debe deducir semantica por ausencia de una
excepcion` (D-49).

Los nombres de entidades reales que aparecen aqui (NVDA, NASDAQ, MOB,
WBA) son EVIDENCIA MEDIDA y registrada en D-52, no parte de la regla. Un
test explicito comprueba que la regla no menciona ninguna entidad
concreta -- es la mitad del encargo que mas facil seria incumplir sin
darse cuenta.
"""
import datetime
import inspect
import json
import os
import re
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "engine", "causal"))
sys.path.insert(0, os.path.join(RAIZ, "engine", "knowledge"))

import caminos  # noqa: E402
import modelo  # noqa: E402

HOY = datetime.date(2026, 9, 7)
FIX_DIR = os.path.join(RAIZ, "tests", "fixtures", "caminos")
CASOS = json.load(open(os.path.join(FIX_DIR, "casos.json"), encoding="utf-8"))
MONOTONIA = json.load(open(os.path.join(FIX_DIR, "identidad_monotonia.json"), encoding="utf-8"))


def forma(c):
    return "|".join(a["predicate"] for a in c["edges"])


def ids(c):
    return [n["entity_id"] for n in c["nodes"]]


def _arista(predicado):
    """Arista minima: `tiene_contenido_causal` solo mira el predicado."""
    return {"predicate": predicado}


class TestUnoLaReglaEsSemantica(unittest.TestCase):
    """La regla no puede depender de nombres ni de una lista negra."""

    def test_la_regla_no_menciona_ninguna_entidad_concreta(self):
        """OBLIGATORIO 1 del encargo: `No hardcodear NASDAQ, MOB, WBA ni
        otros nombres concretos`.

        Se comprueba sobre el CODIGO de las funciones que implementan la
        regla (`inspect.getsource`), no sobre el fichero entero: un mensaje
        de error de otra funcion que ponga `ej. org:nvidia` no es la regla.
        El patron usa los prefijos del propio modelo, no una lista fija."""
        fuente = "".join(inspect.getsource(f) for f in (
            modelo.semantica_de,
            modelo.tiene_contenido_causal,
            caminos.caminos_causales,
            caminos._componer,
        ))
        patron = re.compile(r"\b[a-z]{2,6}:[A-Za-z0-9_.\-]+")
        encontrados = {m.group(0) for m in patron.finditer(fuente)}
        self.assertEqual(encontrados, set(),
                         f"la regla menciona entidades concretas: {sorted(encontrados)}")
        # La tabla semantica tampoco: sus claves son predicados y sus
        # valores clases, nunca identificadores de entidad.
        for k, v in modelo.SEMANTICA_PREDICADO.items():
            self.assertNotIn(":", k)
            self.assertNotIn(":", v)

    def test_lo_no_declarado_no_es_causal(self):
        """Un predicado que nadie clasifico NO se asume causal. Es la
        inversion exacta de la lista negra."""
        self.assertEqual(modelo.semantica_de("UN_PREDICADO_QUE_NO_EXISTE"),
                         modelo.REFERENCE)
        self.assertFalse(modelo.tiene_contenido_causal([_arista("UN_PREDICADO_QUE_NO_EXISTE")]))

    def test_todo_predicado_del_modelo_tiene_clase_declarada(self):
        sin_clase = sorted(set(modelo.PREDICADOS) - set(modelo.SEMANTICA_PREDICADO))
        self.assertEqual(sin_clase, [],
                         f"predicados sin semantica declarada: {sin_clase}")

    def test_una_sola_arista_causal_basta(self):
        """Variante C, no la B: no se exige que TODAS las aristas sean
        causales. La B destruia 84 caminos EXPOSED_TO|EXPOSED_TO|LISTED_ON
        legitimos (D-49)."""
        mezcla = [_arista("ISSUED_BY"), _arista("SUPPLIES"), _arista("LISTED_ON")]
        self.assertTrue(modelo.tiene_contenido_causal(mezcla))


class TestDosPredicadosNoCausales(unittest.TestCase):
    """OBLIGATORIOS 2-5: benchmark, SUCCEEDED_BY, ISSUED_BY, LISTED_ON."""

    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()

    def test_la_arista_de_benchmark_no_aporta_contenido_causal(self):
        """D-21/D-23: una asignacion de benchmark es una relacion de MEDIDA.
        Doble guarda: sigue fuera del indice (lista negra previa) Y, si
        alguien la dejara entrar, no haria causal a ningun camino."""
        for p in ("BENCHMARKED_BY", "COMPARED_TO"):
            self.assertEqual(modelo.semantica_de(p), modelo.MEASUREMENT)
            self.assertFalse(modelo.tiene_contenido_causal([_arista(p)]))
        # Y siguen sin recorrerse: el indice no las ve.
        salidas, _ = caminos.indice(self.k, HOY)
        recorridos = {r["predicate"] for dest in salidas.values() for (_, r, _) in dest}
        self.assertFalse(recorridos & {"BENCHMARKED_BY", "COMPARED_TO"})

    def test_succeeded_by_no_aporta_contenido_causal(self):
        """D-50: la sucesion de instrumento dice QUE hubo sucesion, no que
        se transmita ningun efecto economico. Existe en el Knowledge real."""
        declaradas = [r for r in self.k["relationships"] if r["predicate"] == "SUCCEEDED_BY"]
        self.assertTrue(declaradas, "la evidencia de D-50 dejo de existir")
        self.assertEqual(modelo.semantica_de("SUCCEEDED_BY"), modelo.IDENTITY)
        self.assertFalse(modelo.tiene_contenido_causal([_arista("SUCCEEDED_BY")]))

    def test_issued_by_solo_no_hace_causal_un_camino(self):
        """ISSUED_BY es IDENTITY: es el PUENTE que permite pasar del
        instrumento a la entidad, y por eso se recorre -- pero un camino
        hecho solo de identidad no transmite nada."""
        self.assertEqual(modelo.semantica_de("ISSUED_BY"), modelo.IDENTITY)
        self.assertFalse(modelo.tiene_contenido_causal(
            [_arista("ISSUED_BY"), _arista("DOMICILED_IN")]))

    def test_listed_on_solo_no_hace_causal_un_camino(self):
        """LISTED_ON es STRUCTURAL: situa el instrumento en un mercado.
        Cotizar en el mismo sitio no es un mecanismo economico."""
        self.assertEqual(modelo.semantica_de("LISTED_ON"), modelo.STRUCTURAL)
        self.assertFalse(modelo.tiene_contenido_causal(
            [_arista("LISTED_ON"), _arista("LISTED_ON")]))


class TestTresGrafoReal(unittest.TestCase):
    """OBLIGATORIOS 6-7: los dos caminos espurios que midio D-52, y el
    caso causal legitimo que pasa por una relacion estructural."""

    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()
        cls.todos = caminos.descubrir("ev:d53", "sec:NVDA.NASDAQ", cls.k, HOY, max_depth=3)
        cls.causales = caminos.caminos_causales("ev:d53", "sec:NVDA.NASDAQ", cls.k,
                                                HOY, max_depth=3)

    def _cruzados(self, marcas):
        return [c for c in self.todos
                if any(m in i for i in ids(c) for m in marcas)]

    def test_el_camino_al_instrumento_reutilizado_deja_de_ser_causal(self):
        """D-52, caso 1: NVDA -> mercado -> MOB (Mobilicom). Nombres reales
        porque son la EVIDENCIA medida; la regla que los elimina no los
        menciona (ver TestUno)."""
        cruzados = self._cruzados(("MOB", "mobilicom"))
        self.assertTrue(cruzados, "la evidencia de D-52 dejo de reproducirse")
        for c in cruzados:
            self.assertEqual(c["path_semantics"], caminos.STRUCTURAL_ONLY_PATH, forma(c))
        self.assertEqual([c for c in self.causales if c in cruzados], [])

    def test_el_camino_a_la_otra_empresa_del_mercado_deja_de_ser_causal(self):
        """D-52, caso 2: NVDA -> mercado -> WBA (Walgreens)."""
        cruzados = self._cruzados(("WBA", "walgreens"))
        self.assertTrue(cruzados, "la evidencia de D-52 dejo de reproducirse")
        for c in cruzados:
            self.assertEqual(c["path_semantics"], caminos.STRUCTURAL_ONLY_PATH, forma(c))
        self.assertEqual([c for c in self.causales if c in cruzados], [])

    def test_un_camino_causal_que_atraviesa_una_relacion_estructural_sobrevive(self):
        """El criterio que hizo descartar la variante B: el contenido
        economico esta en las dos primeras aristas y la tercera solo situa
        el resultado. Medido: 28 caminos, 28 sobreviven."""
        objetivo = "EXPOSED_TO|EXPOSED_TO|LISTED_ON"
        antes = [c for c in self.todos if forma(c) == objetivo]
        despues = [c for c in self.causales if forma(c) == objetivo]
        self.assertTrue(antes, "la forma que motivo descartar la variante B ya no existe")
        self.assertEqual(len(antes), len(despues),
                         "la variante C no puede eliminar caminos con contenido causal")

    def test_ningun_camino_eliminado_contenia_una_arista_causal(self):
        """La propiedad general, no solo una forma concreta: lo que sale del
        conjunto causal no tenia causalidad dentro."""
        eliminados = [c for c in self.todos if c not in self.causales]
        self.assertTrue(eliminados)
        for c in eliminados:
            self.assertFalse(modelo.tiene_contenido_causal(c["edges"]), forma(c))

    def test_el_conjunto_causal_es_subconjunto_estricto_y_no_inventa_nada(self):
        """`added` tiene que ser 0: la variante C no restringe el recorrido,
        asi que no puede aparecer ningun camino nuevo."""
        ids_todos = {c["path_id"] for c in self.todos}
        ids_caus = {c["path_id"] for c in self.causales}
        self.assertTrue(ids_caus < ids_todos)
        self.assertEqual(ids_caus - ids_todos, set())


class TestCuatroFixturesCompletas(unittest.TestCase):
    """OBLIGATORIO 8: comparacion completa antes/despues sobre las fixtures
    sinteticas. El criterio que D-49 no pudo cumplir con la variante B."""

    def _comparar(self, key, origen, prof):
        k = CASOS[key]
        antes = caminos.descubrir("ev:d53", origen, k, HOY, max_depth=prof)
        despues = caminos.caminos_causales("ev:d53", origen, k, HOY, max_depth=prof)
        return antes, despues

    def test_el_ciclo_sobrevive_entero(self):
        antes, despues = self._comparar("T5_ciclo", "org:a", 6)
        self.assertEqual(len(antes), len(despues), "T5 pierde caminos")
        self.assertEqual({c["path_semantics"] for c in antes}, {caminos.CAUSAL_PATH})

    def test_la_contradiccion_sobrevive_entera(self):
        antes, despues = self._comparar("T6_contradiccion", "org:a", 1)
        self.assertEqual(len(antes), len(despues), "T6 pierde caminos")
        self.assertEqual({c["path_semantics"] for c in antes}, {caminos.CAUSAL_PATH})
        # Una contradiccion sigue siendo visible: no se silencia por ser causal.
        for c in despues:
            self.assertEqual(c["validity"], "CONTESTED")


class TestCincoVigencia(unittest.TestCase):
    """OBLIGATORIO 9: la semantica no puede saltarse `as_of`. Un camino es
    causal en una fecha porque sus aristas causales estaban vigentes en esa
    fecha, no porque lo esten hoy."""

    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()

    def test_antes_de_que_la_relacion_causal_exista_no_hay_camino_causal(self):
        """Las relaciones de cadena de suministro del Knowledge real tienen
        `valid_from` en 2025; antes de esa fecha no habia ninguna."""
        antes_de = min(r["valid_from"] for r in self.k["relationships"]
                       if modelo.semantica_de(r["predicate"]) == modelo.CAUSAL)
        d = datetime.date.fromisoformat(antes_de) - datetime.timedelta(days=1)
        self.assertEqual(caminos.caminos_causales("ev:d53", "org:nvidia", self.k,
                                                  d, max_depth=2), [])

    def test_despues_si(self):
        cs = caminos.caminos_causales("ev:d53", "org:nvidia", self.k, HOY, max_depth=2)
        self.assertTrue(cs)
        for c in cs:
            self.assertEqual(c["as_of"], HOY.isoformat())

    def test_la_fecha_no_altera_la_clasificacion_de_un_predicado(self):
        """Lo que cambia con la fecha es QUE aristas hay, no que significa
        cada predicado: la semantica es del modelo, no del calendario."""
        for d in (datetime.date(2020, 1, 1), HOY):
            cs = caminos.descubrir("ev:d53", "sec:NVDA.NASDAQ", self.k, d, max_depth=2)
            for c in cs:
                esperado = (caminos.CAUSAL_PATH
                            if modelo.tiene_contenido_causal(c["edges"])
                            else caminos.STRUCTURAL_ONLY_PATH)
                self.assertEqual(c["path_semantics"], esperado)


class TestSeisIdentidadMonotonia(unittest.TestCase):
    """OBLIGATORIO 10 + IDENTITY_MONOTONICITY (propuesta, no invariant).

    Propiedad: anadir conocimiento de identidad/estructura VERDADERO no
    puede aumentar las relaciones causales entre entidades economicamente
    independientes.

    Fixture sintetica a proposito: la propiedad es sobre la semantica de
    las relaciones, no sobre ninguna entidad real. `CON_IDENTIDAD` anade
    emision, cotizacion en el MISMO mercado, domicilio en el MISMO pais y
    una sucesion de instrumento -- todo verdadero, nada causal.
    """

    @classmethod
    def setUpClass(cls):
        cls.base_todos = caminos.descubrir("ev:m", "sec:alfa", MONOTONIA["BASE"],
                                           HOY, max_depth=3)
        cls.base_caus = caminos.caminos_causales("ev:m", "sec:alfa", MONOTONIA["BASE"],
                                                 HOY, max_depth=3)
        cls.con_todos = caminos.descubrir("ev:m", "sec:alfa", MONOTONIA["CON_IDENTIDAD"],
                                          HOY, max_depth=3)
        cls.con_caus = caminos.caminos_causales("ev:m", "sec:alfa",
                                                MONOTONIA["CON_IDENTIDAD"],
                                                HOY, max_depth=3)

    def test_la_fixture_declara_conocimiento_verdadero_y_no_causal(self):
        """Si la fixture colase una arista causal nueva, el test de
        monotonia pasaria por la razon equivocada."""
        nuevos = ({r["relationship_id"] for r in MONOTONIA["CON_IDENTIDAD"]["relationships"]}
                  - {r["relationship_id"] for r in MONOTONIA["BASE"]["relationships"]})
        self.assertTrue(nuevos)
        por_id = {r["relationship_id"]: r for r in MONOTONIA["CON_IDENTIDAD"]["relationships"]}
        for rid in nuevos:
            self.assertNotEqual(modelo.semantica_de(por_id[rid]["predicate"]),
                                modelo.CAUSAL, rid)

    def test_declarar_identidad_verdadera_aumenta_los_caminos_totales(self):
        """El grafo SI crece: eso es correcto y no se oculta."""
        self.assertGreater(len(self.con_todos), len(self.base_todos))

    def test_pero_no_crea_ninguna_relacion_causal_nueva(self):
        """IDENTITY_MONOTONICITY. Es exactamente lo que D-52 midio que la
        lista negra NO cumplia."""
        self.assertEqual(len(self.con_caus), len(self.base_caus))
        self.assertEqual({forma(c) for c in self.con_caus},
                         {forma(c) for c in self.base_caus})

    def test_el_hub_estructural_compartido_no_conecta_causalmente(self):
        """Dos instrumentos independientes que cuelgan del mismo mercado y
        del mismo pais: hay camino, pero no causal."""
        cruzados = [c for c in self.con_todos if "sec:beta" in ids(c)]
        self.assertTrue(cruzados, "la fixture ya no reproduce el hub compartido")
        for c in cruzados:
            self.assertEqual(c["path_semantics"], caminos.STRUCTURAL_ONLY_PATH, forma(c))


class TestSieteContratoDelCamino(unittest.TestCase):
    """`path_semantics` es un campo del contrato, no un detalle interno."""

    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()
        cls.cs = caminos.descubrir("ev:d53", "sec:NVDA.NASDAQ", cls.k, HOY, max_depth=3)

    def test_todo_camino_declara_su_semantica(self):
        for c in self.cs:
            self.assertIn(c["path_semantics"], caminos.SEMANTICAS_CAMINO)

    def test_el_validador_rechaza_una_semantica_fuera_del_vocabulario(self):
        c = dict(self.cs[0])
        c["path_semantics"] = "PROBABLEMENTE_CAUSAL"
        with self.assertRaises(caminos.PathError):
            caminos.validar(c, self.k)

    def test_el_validador_rechaza_un_camino_que_no_la_declara(self):
        """No declararla dejaria que el consumidor la dedujera por ausencia
        -- justo lo que D-49 prohibe."""
        c = dict(self.cs[0])
        del c["path_semantics"]
        with self.assertRaises(caminos.PathError):
            caminos.validar(c, self.k)

    def test_la_semantica_no_es_un_valor_economico(self):
        """P5A sigue sin insinuar signo ni magnitud: CAUSAL_PATH dice que
        hay un mecanismo declarado, no hacia donde ni cuanto."""
        for c in self.cs:
            self.assertNotIsInstance(c["path_semantics"], (int, float))
            self.assertNotIn(c["path_semantics"],
                             ("POSITIVE", "NEGATIVE", "UP", "DOWN", "ALCISTA", "BAJISTA"))

    def test_la_explicacion_dice_si_el_camino_es_causal(self):
        texto = caminos.explicar(self.cs[0], self.k)
        self.assertIn(self.cs[0]["path_semantics"], texto)


if __name__ == "__main__":
    unittest.main(verbosity=2)
