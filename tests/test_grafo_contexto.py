# -*- coding: utf-8 -*-
"""T7 / S6 de F1 (2026-09-12) -- indice de alcanzabilidad del contexto.

Indice ESTRUCTURAL, no resolvedor semantico. Verifica las tres fronteras
del modelo de contexto y la propiedad que sostiene el presupuesto:
POINTER no expande L0.

L0 no se redefine aqui: la autoridad sigue siendo T3.
Ninguna mutacion toca el repositorio: se opera sobre copias en memoria.
"""
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "contexto"))

import estado    # noqa: E402
import grafo     # noqa: E402
import validar   # noqa: E402


def _idx():
    return grafo.indice()


class TestElIndiceExiste(unittest.TestCase):
    def test_el_indice_tiene_nodos_y_aristas(self):
        idx = _idx()
        self.assertTrue(idx.get("nodos"),
                        "el indice de alcanzabilidad no declara nodos: no esta generado")
        self.assertTrue(idx.get("aristas"),
                        "el indice de alcanzabilidad no declara aristas: no esta generado")

    def test_cada_arista_lleva_origen_relacion_destino_y_clases(self):
        for a in _idx().get("aristas", [{}]):
            for campo in ("origen", "clase_origen", "relacion", "destino", "clase_destino"):
                self.assertIn(campo, a, f"arista sin {campo}: el indice esta incompleto")

    def test_toda_relacion_pertenece_al_vocabulario(self):
        aristas = _idx().get("aristas")
        self.assertTrue(aristas, "indice sin aristas")
        for a in aristas:
            self.assertIn(a["relacion"], grafo.RELACIONES)

    def test_el_indice_declara_sus_mecanismos_versionados(self):
        idx = _idx()
        self.assertEqual(idx.get("clasificacion"), grafo.CLASIFICACION_VERSION)
        self.assertEqual(idx.get("relaciones"), grafo.RELACION_VERSION)


class TestDeterminismo(unittest.TestCase):
    def test_dos_generaciones_dan_la_misma_serializacion(self):
        a, b = grafo.serializar(grafo.indice()), grafo.serializar(grafo.indice())
        self.assertTrue(a, "la serializacion esta vacia: el indice no esta generado")
        self.assertEqual(a, b)

    def test_el_orden_incidental_no_cambia_la_serializacion(self):
        """Barajar las aristas no puede alterar el resultado."""
        import random
        idx = grafo.indice()
        self.assertTrue(idx.get("aristas"), "indice sin aristas")
        barajado = dict(idx)
        barajado["aristas"] = random.sample(idx["aristas"], len(idx["aristas"]))
        self.assertEqual(grafo.serializar(idx), grafo.serializar(barajado))


class TestLasTresFronteras(unittest.TestCase):
    def test_CLAUDE_md_alcanza_S1_por_lectura_obligatoria(self):
        aristas = _idx().get("aristas", [])
        m = [a for a in aristas
             if a["origen"] == "CLAUDE.md" and a["relacion"] == grafo.MANDATORY_READ]
        self.assertTrue(m, "CLAUDE.md no alcanza S1 por MANDATORY_READ")
        self.assertEqual(m[0]["destino"], "contexto/ESTADO_VIGENTE.md")
        self.assertEqual(m[0]["clase_destino"], grafo.DURABLE)

    def test_la_superficie_valida_sus_fuentes_canonicas(self):
        aristas = _idx().get("aristas", [])
        v = [a for a in aristas if a["relacion"] == grafo.VALIDATES]
        self.assertTrue(v, "ninguna arista VALIDATES: la superficie no valida nada")
        for a in v:
            self.assertEqual(a["clase_origen"], grafo.DURABLE)
            self.assertEqual(a["clase_destino"], grafo.REGENERABLE)

    def test_el_historico_se_alcanza_SOLO_por_POINTS(self):
        for a in _idx().get("aristas", []):
            if a["clase_destino"] == grafo.HISTORICAL:
                self.assertEqual(a["relacion"], grafo.POINTS,
                                 f"{a['origen']} -> {a['destino']} alcanza histórico "
                                 f"por {a['relacion']}, no por POINTS")

    def test_ninguna_arista_REGENERABLE_HISTORICAL(self):
        """Arco 3 del modelo: dentro del grafo de contexto no existe."""
        malas = [a for a in _idx().get("aristas", [])
                 if a["clase_origen"] == grafo.REGENERABLE
                 and a["clase_destino"] == grafo.HISTORICAL]
        self.assertEqual(malas, [], f"arco prohibido presente: {malas}")


class TestPointerNoExpandeL0(unittest.TestCase):
    def test_solo_MANDATORY_READ_expande_L0(self):
        self.assertEqual(grafo.RELACIONES_QUE_EXPANDEN_L0, (grafo.MANDATORY_READ,))

    def test_ningun_destino_POINTS_esta_en_L0(self):
        l0, _ = validar.l0_efectivo()
        aristas = _idx().get("aristas", [])
        puntos = [a for a in aristas if a["relacion"] == grafo.POINTS]
        self.assertTrue(puntos, "ninguna arista POINTS: no hay nada que comprobar")
        for a in puntos:
            self.assertNotIn(a["destino"], l0,
                             f"{a['destino']} se alcanza por POINTS y esta en L0")

    def test_los_tres_recursos_citados_no_entran_en_L0(self):
        """docs/DECISIONES.md, informes/ y contexto/historico/ se citan y NO
        expanden el contexto obligatorio."""
        l0, _ = validar.l0_efectivo()
        destinos = {a["destino"] for a in _idx().get("aristas", [])}
        for recurso in ("docs/DECISIONES.md", "docs/ESTADO.md",
                        "contexto/historico/claude_md_estado_previo_a_F1.md"):
            self.assertIn(recurso, destinos, f"{recurso} deberia estar citado")
            self.assertNotIn(recurso, l0, f"{recurso} NO puede estar en L0")
        self.assertTrue(any(d.startswith("informes/") for d in destinos),
                        "informes/ deberia estar citado desde el contexto durable")


class TestNoEsUnIndiceSemantico(unittest.TestCase):
    def test_el_indice_no_intenta_responder_que_decision_introdujo_algo(self):
        idx = _idx()
        prohibidos = ("decision_que_introdujo", "supersede", "superseded_by",
                      "motivo", "semantica")
        for a in idx.get("aristas", []):
            for campo in prohibidos:
                self.assertNotIn(campo, a, "T7 es estructural, no semantico")

    def test_no_resuelve_la_vigencia_de_las_decisiones_D_A(self):
        """D-A sigue sin resolver: T7 no clasifica decisiones.

        La comprobacion NO es una busqueda de subcadenas: `VIGENTE` aparece
        dentro del NOMBRE de contexto/ESTADO_VIGENTE.md y eso no es un
        pronunciamiento sobre nada. Se comprueba lo que importa: que el
        indice no lleve ningun campo de vigencia, que no cite ninguna
        decision concreta y que grafo.py no use el detector de T6."""
        idx = _idx()
        for a in idx["aristas"]:
            for campo in a:
                self.assertNotIn("vigen", campo.lower())
        import re as _re
        self.assertEqual(_re.findall(r"\bD-\d\d\b", grafo.serializar(idx)), [],
                         "el indice no puede citar decisiones concretas")
        fuente = open(os.path.join(RAIZ, "contexto", "grafo.py"), encoding="utf-8").read()
        self.assertNotIn("decisiones_vigentes", fuente,
                         "T7 no debe usar el detector de vigencia de T6")


class TestElModuloNoEscribe(unittest.TestCase):
    def test_grafo_py_no_abre_nada_para_escribir(self):
        fuente = open(os.path.join(RAIZ, "contexto", "grafo.py"), encoding="utf-8").read()
        cuerpo = fuente.split("def main(")[0]
        for patron in ('"w"', "'w'", '"a"', "'a'", "os.remove", "os.rename", "shutil"):
            self.assertNotIn(patron, cuerpo, f"grafo.py no puede escribir: {patron}")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestMutacionesT7(unittest.TestCase):
    """Un validador que nunca ha fallado no esta demostrado.

    TODAS las mutaciones son sobre copias EN MEMORIA del indice. Ninguna
    escribe en el repositorio ni toca un fichero historico."""

    def _copia(self):
        idx = grafo.indice()
        return {**idx, "aristas": [dict(a) for a in idx["aristas"]]}

    def _arista(self, origen, clase_o, rel, destino, clase_d):
        return {"origen": origen, "clase_origen": clase_o, "relacion": rel,
                "destino": destino, "clase_destino": clase_d}

    # --- M7: arco prohibido REGENERABLE -> HISTORICAL ---
    def test_M7_regenerable_a_historico_se_rechaza(self):
        idx = self._copia()
        idx["aristas"].append(self._arista(
            "engine/knowledge/modelo.py", grafo.REGENERABLE,
            grafo.POINTS, "docs/DECISIONES.md", grafo.HISTORICAL))
        ok, inc = grafo.verificar(idx)
        self.assertFalse(ok, "el arco REGENERABLE -> HISTORICAL tiene que fallar")
        self.assertIn(grafo.ARCO_PROHIBIDO, [e for e, _ in inc])

    def test_M7_el_motivo_explica_por_que(self):
        idx = self._copia()
        idx["aristas"].append(self._arista(
            "engine/causal/mecanismos.py", grafo.REGENERABLE,
            grafo.REFERENCE, "informes/2026-09-08_backfill_readiness_historico.md",
            grafo.HISTORICAL))
        _, inc = grafo.verificar(idx)
        motivo = next(m for e, m in inc if e == grafo.ARCO_PROHIBIDO)
        self.assertIn("el codigo es el presente", motivo)

    def test_M7_no_depende_de_la_relacion_usada(self):
        """El arco esta prohibido con CUALQUIER relacion, no solo con POINTS."""
        for rel in grafo.RELACIONES:
            idx = self._copia()
            idx["aristas"].append(self._arista(
                "engine/knowledge/modelo.py", grafo.REGENERABLE, rel,
                "docs/ESTADO.md", grafo.HISTORICAL))
            ok, inc = grafo.verificar(idx)
            self.assertFalse(ok, rel)
            self.assertIn(grafo.ARCO_PROHIBIDO, [e for e, _ in inc], rel)

    # --- M8: una relacion que expande L0 incorrectamente ---
    def test_M8_marcar_un_historico_como_lectura_obligatoria_se_rechaza(self):
        """Si un historico se declarase lectura obligatoria, L0 crecería sin
        que T3 lo hubiera puesto ahi."""
        idx = self._copia()
        idx["aristas"].append(self._arista(
            "contexto/ESTADO_VIGENTE.md", grafo.DURABLE,
            grafo.MANDATORY_READ, "docs/DECISIONES.md", grafo.HISTORICAL))
        ok, inc = grafo.verificar(idx)
        self.assertFalse(ok)
        self.assertIn(grafo.POINTER_EXPANDE_L0, [e for e, _ in inc])

    def test_M8_un_puntero_a_algo_que_esta_en_L0_se_rechaza(self):
        """La otra direccion: algo en L0 alcanzado por una relacion que NO
        expande L0 significa que el indice y T3 se contradicen."""
        idx = self._copia()
        idx["l0"] = sorted(set(idx["l0"]) | {"docs/ESTADO.md"})
        ok, inc = grafo.verificar(idx)
        self.assertFalse(ok)
        self.assertIn(grafo.POINTER_EXPANDE_L0, [e for e, _ in inc])

    def test_M8_relacion_fuera_del_vocabulario(self):
        idx = self._copia()
        idx["aristas"].append(self._arista(
            "CLAUDE.md", grafo.DURABLE, "SE_INSPIRA_EN",
            "contexto/validar.py", grafo.REGENERABLE))
        ok, inc = grafo.verificar(idx)
        self.assertFalse(ok)
        self.assertIn(grafo.RELACION_DESCONOCIDA, [e for e, _ in inc])

    def test_M8_un_fichero_de_L0_que_no_es_nodo(self):
        idx = self._copia()
        idx["l0"] = sorted(set(idx["l0"]) | {"contexto/contrato.json"})
        ok, inc = grafo.verificar(idx)
        self.assertFalse(ok)
        self.assertIn(grafo.L0_NO_ALCANZABLE, [e for e, _ in inc])

    # --- los motivos son distinguibles ---
    def test_los_motivos_de_M7_y_M8_son_distintos(self):
        self.assertNotEqual(grafo.ARCO_PROHIBIDO, grafo.POINTER_EXPANDE_L0)

    def test_ninguna_mutacion_escribio_en_el_repositorio(self):
        import hashlib
        antes = {}
        for p in ("CLAUDE.md", "contexto/ESTADO_VIGENTE.md",
                  "contexto/historico/claude_md_estado_previo_a_F1.md"):
            antes[p] = hashlib.sha256(open(os.path.join(RAIZ, p), "rb").read()).hexdigest()
        self.test_M7_regenerable_a_historico_se_rechaza()
        self.test_M8_marcar_un_historico_como_lectura_obligatoria_se_rechaza()
        for p, h in antes.items():
            self.assertEqual(
                h, hashlib.sha256(open(os.path.join(RAIZ, p), "rb").read()).hexdigest())

    def test_el_estado_real_sigue_pasando(self):
        ok, inc = grafo.verificar(grafo.indice())
        self.assertTrue(ok, inc)
