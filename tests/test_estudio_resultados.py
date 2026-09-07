"""Event study minimo sobre resultados -- P6.2c (2026-09-07).

Comprueba las cinco propiedades que esta vertical tenia que demostrar:
el evento se fecha bien, la sorpresa se calcula sin look-ahead, la
reaccion se mide DESPUES del primer momento negociable, bruto y anormal
no se confunden, y los eventos solapados se detectan.
"""
import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "engine", "contract"))
sys.path.insert(0, os.path.join(RAIZ, "engine", "events"))

import estudio_resultados as er  # noqa: E402
import temporal                  # noqa: E402

FIXTURES = os.path.join(RAIZ, "tests", "fixtures", "eventos_resultados")
SIMBOLOS = ("IBM", "NVDA", "XOM")


def _path(sym):
    return os.path.join(FIXTURES, f"{sym}_earnings.json")


class TestFixtures(unittest.TestCase):
    """Las fixtures se transcribieron a mano desde la respuesta en vivo.
    Estas comprobaciones existen para que un error de transcripcion no
    pase inadvertido y contamine todo lo que viene despues."""

    def test_la_sorpresa_declarada_es_coherente_con_los_eps(self):
        """surprisePercentage ~= (reportado - estimado) / |estimado| * 100,
        comprobado solo donde el estimado es sano (no cero, no negativo)."""
        for sym in SIMBOLOS:
            for e in er.leer_eventos(_path(sym)):
                est, rep, sur = e["expected_eps"], e["reported_eps"], e["surprise_pct"]
                if not est or est <= 0:
                    continue
                esperado = (rep - est) / abs(est) * 100
                self.assertAlmostEqual(sur, esperado, delta=0.6,
                                       msg=f"{sym} {e['period_end']}: {sur} vs {esperado:.4f}")

    def test_publicacion_siempre_posterior_al_cierre_del_trimestre(self):
        for sym in SIMBOLOS:
            for e in er.leer_eventos(_path(sym)):
                self.assertTrue(temporal.validar_orden({
                    "period_end": e["period_end"], "published_at": e["published_at"]}))

    def test_las_dos_franjas_estan_representadas(self):
        """Si todas las fixtures fuesen post-market, la distincion de
        first_tradable_at no estaria puesta a prueba por ningun caso."""
        franjas = set()
        for sym in SIMBOLOS:
            franjas |= {e["report_time"] for e in er.leer_eventos(_path(sym))}
        self.assertEqual(franjas, {"pre-market", "post-market"})


class TestPrimeraSesionNegociable(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fechas, cls.px = er.serie_de_precios("XOM")

    def test_pre_market_negocia_el_mismo_dia(self):
        t1, razon = er.first_tradable_at(self.fechas, "2026-07-31", "pre-market")
        self.assertIsNone(razon)
        self.assertEqual(t1, "2026-07-31")

    def test_post_market_negocia_la_sesion_siguiente(self):
        """XOM publico post-market el viernes 2024-04-26: la primera
        sesion negociable es el lunes 2024-04-29, no el sabado."""
        t1, razon = er.first_tradable_at(self.fechas, "2024-04-26", "post-market")
        self.assertIsNone(razon)
        self.assertEqual(t1, "2024-04-29")

    def test_sin_franja_no_se_elige_una_por_defecto(self):
        """Las dos opciones difieren en una sesion entera de reaccion.
        Elegir seria inventar el dato que falta."""
        t1, razon = er.first_tradable_at(self.fechas, "2024-04-26", None)
        self.assertIsNone(t1)
        self.assertEqual(razon, er.SIN_MOMENTO)

    def test_la_misma_fecha_da_sesiones_distintas_segun_la_franja(self):
        pre, _ = er.first_tradable_at(self.fechas, "2024-04-26", "pre-market")
        post, _ = er.first_tradable_at(self.fechas, "2024-04-26", "post-market")
        self.assertNotEqual(pre, post)


class TestObservaciones(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.obs = {s: er.estudiar(s, _path(s)) for s in SIMBOLOS}
        cls.todas = [o for v in cls.obs.values() for o in v]

    def test_la_reaccion_se_mide_despues_del_primer_momento_negociable(self):
        for o in self.todas:
            if o["raw_return_1s_pct"] is None:
                continue
            self.assertGreaterEqual(o["first_tradable_at"], o["available_at"])
            self.assertLess(o["sesion_previa"], o["first_tradable_at"])

    def test_available_at_no_se_disfraza_de_marca_de_tiempo(self):
        for o in self.todas:
            self.assertEqual(o["timestamp_semantics"], er.PROVEEDOR_DIA)
            self.assertEqual(o["available_at"], o["published_at"])

    def test_bruto_y_anormal_no_se_confunden(self):
        """REESCRITO (2026-09-07). Este test afirmaba que el retorno
        anormal no existia todavia y que su ausencia llevaba razon. La
        primera mitad caduco al declararse `bm:sp500`; la segunda sigue
        siendo cierta y se refuerza: si hay ajuste, viaja con la identidad
        del benchmark que lo produjo -- un `market_adjusted_return` sin
        saber contra que es irreproducible; si no lo hay, con su razon."""
        for o in self.todas:
            self.assertIn("raw_return_1s_pct", o)
            self.assertIn("market_adjusted_return_pct", o)
            if o["market_adjusted_return_pct"] is None:
                self.assertIsNotNone(o["razon_sin_ajuste"])
                self.assertIsNone(o["benchmark_id"])
            else:
                self.assertIsNone(o["razon_sin_ajuste"])
                self.assertIsNotNone(o["benchmark_id"])
                self.assertIsNotNone(o["benchmark_methodology_version"])
                self.assertIsNotNone(o["metodo_ajuste"])
                # y nunca son el mismo campo
                self.assertIsNot(o["raw_return_1s_pct"], o["market_adjusted_return_pct"])

    def test_sin_benchmark_la_ausencia_lleva_razon(self):
        """La otra mitad, ahora comprobada donde de verdad aplica: un
        activo sin asignacion declarada."""
        obs = er.estudiar("IBM", _path("IBM"), con_benchmark=False)
        for o in obs:
            self.assertIsNone(o["market_adjusted_return_pct"])
            self.assertEqual(o["razon_sin_ajuste"], er.SIN_BENCHMARK)

    def test_los_52_eventos_tienen_reaccion_medible(self):
        medibles = [o for o in self.todas if o["raw_return_1s_pct"] is not None]
        self.assertEqual(len(self.todas), 52)
        self.assertEqual(len(medibles), 52)

    def test_caso_real_nvda_2023_05_24(self):
        """Publicado post-market el 2023-05-24; la reaccion se mide el 25."""
        o = next(x for x in self.obs["NVDA"] if x["published_at"] == "2023-05-24")
        self.assertEqual(o["first_tradable_at"], "2023-05-25")
        self.assertAlmostEqual(o["raw_return_1s_pct"], 24.37, places=2)

    def test_caso_real_ibm_2014_10_20_pre_market(self):
        """Pre-market: la reaccion se mide en la sesion del propio anuncio."""
        o = next(x for x in self.obs["IBM"] if x["published_at"] == "2014-10-20")
        self.assertEqual(o["first_tradable_at"], "2014-10-20")
        self.assertAlmostEqual(o["raw_return_1s_pct"], -7.11, places=2)


class TestSolapamiento(unittest.TestCase):

    def test_ventana_corta_no_solapa_trimestres(self):
        """A 20 sesiones, dos resultados trimestrales (~63 sesiones de
        distancia) nunca se pisan. Es el resultado esperado, y que sea
        cero no significa que la comprobacion no sirva."""
        obs = er.estudiar("IBM", _path("IBM"), ventana_sesiones=20)
        recientes = [o for o in obs if o["published_at"] >= "2018-01-01"]
        self.assertTrue(all(o["solapa_con"] is None for o in recientes))

    def test_ventana_larga_si_detecta_el_siguiente_evento(self):
        """A 90 sesiones la ventana alcanza al trimestre siguiente y el
        solapamiento aparece. Es la prueba de que el detector funciona."""
        obs = er.estudiar("IBM", _path("IBM"), ventana_sesiones=90)
        recientes = [o for o in obs if o["published_at"] >= "2018-10-01"]
        solapados = [o for o in recientes if o["solapa_con"]]
        self.assertTrue(solapados, "a 90 sesiones tiene que haber solapamiento")


class TestElegibilidadPorFamilia(unittest.TestCase):
    """REESCRITO EN D-21 (2026-09-07). Antes habia una sola puerta:
    `suficiencia_de_muestra()` bloqueaba TODA agregacion por
    `SIN_RETORNO_ANORMAL`. Era demasiado gruesa -- bloquear la agregacion
    de retornos anormales sin benchmark es correcto, bloquear tambien la
    de raw_return no lo es. La propiedad que sigue siendo cierta, y la
    que ahora importa, es que cada familia responde por su cuenta."""

    @classmethod
    def setUpClass(cls):
        cls.todas = [o for s in SIMBOLOS for o in er.estudiar(s, _path(s))]

    def test_raw_return_es_elegible_sin_benchmark(self):
        """La regla critica de D-21: la ausencia de benchmark limita QUE
        MEDIDAS pueden llamarse retorno anormal, no si hay analisis."""
        ok, informe = er.elegibilidad(self.todas, "RAW_RETURN")
        self.assertTrue(ok)
        self.assertEqual(informe["motivo"], "SUFICIENTE")
        self.assertEqual(informe["sin_solapamiento"], 52)

    def test_abnormal_return_no_es_elegible_sin_benchmark(self):
        ok, informe = er.elegibilidad(self.todas, "ABNORMAL_RETURN")
        self.assertFalse(ok)
        self.assertIn(er.SIN_BENCHMARK, informe["motivo"])

    def test_la_elegibilidad_de_raw_no_depende_de_la_de_abnormal(self):
        """Test 10 del encargo. Las dos familias se evaluan sobre las
        MISMAS observaciones y dan resultados distintos."""
        raw_ok, _ = er.elegibilidad(self.todas, "RAW_RETURN")
        abn_ok, _ = er.elegibilidad(self.todas, "ABNORMAL_RETURN")
        self.assertTrue(raw_ok)
        self.assertFalse(abn_ok)

    def test_el_minimo_es_por_familia_y_pregunta(self):
        """No hay un umbral global. Y ABNORMAL_RETURN exige mas que
        RAW_RETURN porque lleva encima el error del propio benchmark."""
        m = er.MINIMOS_DECLARADOS
        self.assertGreater(m[("ABNORMAL_RETURN", "reaccion_mediana_por_clase")],
                           m[("RAW_RETURN", "reaccion_mediana_por_clase")])
        self.assertGreater(m[("RAW_RETURN", "reaccion_mediana_condicionada")],
                           m[("RAW_RETURN", "reaccion_mediana_por_clase")])

    def test_el_umbral_10_de_pct_in_window_no_se_ha_vuelto_global(self):
        """Regla explicita del usuario: ese `10` era el minimo razonable
        para un percentil en ventana movil, y no se generaliza."""
        self.assertNotIn(10, set(er.MINIMOS_DECLARADOS.values()))
        sys.path.insert(0, os.path.join(RAIZ, "engine", "crypto"))
        try:
            if "score" in sys.modules:
                del sys.modules["score"]
            crypto = __import__("score")
        finally:
            sys.path.remove(os.path.join(RAIZ, "engine", "crypto"))
        # el modulo de cripto sigue intacto: se niega con menos de 10
        self.assertIsNone(crypto._pct_in_window(list(range(9))))
        self.assertIsNotNone(crypto._pct_in_window(list(range(10))))

    def test_no_devuelve_ningun_estadistico(self):
        for fam in er.FAMILIAS_DE_MEDIDA:
            _ok, informe = er.elegibilidad(self.todas, fam)
            for prohibido in ("mediana", "media", "p10", "p90", "median", "mean"):
                self.assertNotIn(prohibido, informe)

    def test_familia_o_pregunta_no_declarada_no_pasa(self):
        ok, informe = er.elegibilidad(self.todas, "LO_QUE_SEA")
        self.assertFalse(ok)
        self.assertEqual(informe["motivo"], "FAMILIA_NO_DECLARADA")
        ok, informe = er.elegibilidad(self.todas, "RAW_RETURN", pregunta="lo_que_sea")
        self.assertFalse(ok)
        self.assertEqual(informe["motivo"], "PREGUNTA_NO_DECLARADA")


if __name__ == "__main__":
    unittest.main()
