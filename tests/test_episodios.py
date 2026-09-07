"""Episodios -- P6.2d (2026-09-07).

Demuestra la tercera unidad sobre la capa P4 que ya existia: DOCUMENTO ->
EVENTO -> EPISODIO, y que los tres numeros son distintos sobre los datos
reales de XRP.
"""
import copy
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("contract", "evidence", "events"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", sub))

import consolidar       # noqa: E402
import episodios        # noqa: E402
import esquema_evento   # noqa: E402


class TestRegistroDeclarado(unittest.TestCase):

    def setUp(self):
        self.eps = episodios.cargar()

    def test_el_registro_es_valido(self):
        self.assertTrue(episodios.validar(self.eps))

    def test_todo_episodio_declara_su_criterio_de_pertenencia(self):
        """Sin criterio escrito, la agrupacion no es auditable: nadie
        puede comprobar si un documento sexto deberia entrar o no."""
        for ep in self.eps:
            self.assertTrue(ep["criterio"].strip())
            for d in ep["documentos"]:
                self.assertTrue(d["por_que"].strip())

    def test_rechaza_un_documento_en_dos_episodios(self):
        eps = copy.deepcopy(self.eps)
        eps.append(dict(eps[0], episode_id="ep:2026:otro"))
        with self.assertRaises(episodios.EpisodioError):
            episodios.indice_por_documento(eps)

    def test_rechaza_un_estado_fuera_del_vocabulario(self):
        eps = copy.deepcopy(self.eps)
        eps[0]["estado"] = "ABIERTO_MAS_O_MENOS"
        with self.assertRaises(episodios.EpisodioError):
            episodios.validar(eps)

    def test_rechaza_un_documento_sin_justificacion(self):
        eps = copy.deepcopy(self.eps)
        eps[0]["documentos"][0]["por_que"] = "  "
        with self.assertRaises(episodios.EpisodioError):
            episodios.validar(eps)

    def test_el_episodio_de_la_clarity_act_sigue_abierto(self):
        """No es un detalle: en julio el sistema lo trato como resuelto y
        hubo que corregirlo a mano cuando el Senado aplazo la votacion."""
        ep = next(e for e in self.eps if e["episode_id"] == "ep:2026:clarity-act-senado")
        self.assertEqual(ep["estado"], "OPEN")
        self.assertEqual(len(ep["documentos"]), 5)


class TestSobreDatosReales(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.claims, cls.evs, _ = consolidar.pipeline_noticias()
        cls.eventos = episodios.asignar(
            consolidar.consolidar(cls.claims, cls.evs), cls.evs, cls.claims)

    def test_las_tres_unidades_dan_numeros_distintos(self):
        """La razon de ser de la capa: 50 documentos no son 43 eventos, y
        43 eventos no son 1 episodio."""
        r = episodios.resumen(self.eventos, self.claims)
        self.assertEqual(r["documentos_distintos"], 50)
        self.assertEqual(r["eventos"], 43)
        self.assertEqual(r["eventos_con_episodio_declarado"], 5)
        self.assertEqual(r["episodios_distintos"], 1)

    def test_cinco_documentos_distintos_caen_en_un_solo_episodio(self):
        con_ep = [e for e in self.eventos if e.get("episode_id")]
        self.assertEqual(len(con_ep), 5)
        self.assertEqual({e["episode_id"] for e in con_ep}, {"ep:2026:clarity-act-senado"})

    def test_los_eventos_siguen_validando_contra_el_esquema(self):
        """Anadir episode_id no puede romper P4."""
        por_id = {c["claim_id"]: c for c in self.claims}
        for e in self.eventos:
            esquema_evento.validar_evento(e, por_id)

    def test_sin_declaracion_el_episode_id_es_none_no_un_hueco(self):
        sin_ep = [e for e in self.eventos if e.get("episode_id") is None]
        self.assertEqual(len(sin_ep), 38)
        for e in sin_ep:
            self.assertIn("episode_id", e)  # el campo existe y vale None

    def test_el_episodio_no_se_infiere_del_texto(self):
        """Los cinco documentos del episodio no comparten ningun patron
        textual que los distinga: uno es un 'Hodler's Digest' semanal y
        otro habla de las elecciones de medio mandato. Si la pertenencia
        se calculase por parecido de titular, o se quedarian fuera o
        entrarian noticias de otra regulacion cripto."""
        ep = next(e for e in episodios.cargar()
                  if e["episode_id"] == "ep:2026:clarity-act-senado")
        titulares_declarados = {d["news_id"] for d in ep["documentos"]}
        self.assertEqual(len(titulares_declarados), 5)
        # el criterio menciona explicitamente que se excluye
        self.assertIn("Aviva", ep["criterio"])


if __name__ == "__main__":
    unittest.main()
