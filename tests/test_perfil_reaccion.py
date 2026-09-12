"""HistoricalReactionProfile v1 -- descriptivo, no predictivo (2026-09-07).

La propiedad que ordena todos estos tests: **un perfil nunca desaparece
por falta de datos**. Si no se puede construir, devuelve por que.
"""
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("contract", "events", "knowledge", "technical"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", sub))

import estudio_resultados as er   # noqa: E402
import perfil_reaccion as pr      # noqa: E402

HOY = "2026-09-07"


from _parquet import requiere_parquet  # noqa: E402


@requiere_parquet
class TestRejillaCompleta(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.obs = pr.observaciones_v1()
        cls.rejilla = pr.rejilla(cls.obs, HOY)

    def test_ningun_perfil_desaparece(self):
        """5 medidas x 4 horizontes = 20 celdas, todas presentes."""
        self.assertEqual(len(self.rejilla), len(pr.MEDIDAS) * len(pr.HORIZONTES))
        for p in self.rejilla:
            self.assertIn(p["status"], pr.ESTADOS, f"{p['measure_type']}/{p['horizon']}")

    def test_todo_perfil_no_valido_dice_por_que(self):
        for p in self.rejilla:
            if p["status"] != "VALID":
                self.assertTrue(p["status_reason"], f"{p['measure_type']}/{p['horizon']}")

    def test_todo_perfil_lleva_as_of_y_metodologia(self):
        for p in self.rejilla:
            self.assertEqual(p["as_of_date"], HOY)
            self.assertEqual(p["methodology_version"], pr.METHODOLOGY_VERSION)

    def test_los_cinco_conteos_estan_siempre(self):
        for p in self.rejilla:
            for k in ("n_observations", "n_events", "n_independent_events",
                      "n_episodes", "n_independent_episodes"):
                self.assertIn(k, p)

    def test_descriptivo_y_predictivo_son_estados_distintos(self):
        """COMPUTABLE != INTERPRETABLE != PREDICTIVO. Colapsarlos en un
        unico VALID invita a leer una cifra calculable como una certeza."""
        for p in self.rejilla:
            self.assertEqual(p["descriptive_status"], p["status"])
            self.assertEqual(p["predictive_status"], "NOT_EVALUATED")
            self.assertIn(p["predictive_status"], pr.PREDICTIVE_STATUS)

    def test_toda_medida_declara_su_semantica(self):
        for p in self.rejilla:
            self.assertIn(p["semantica"], pr.FAMILIAS_SEMANTICAS)
            self.assertNotIn(p["semantica"], pr.FAMILIAS_NO_IMPLEMENTADAS)

    def test_solo_las_medidas_relativas_al_pre_evento_declaran_ventana(self):
        for p in self.rejilla:
            if p["semantica"] == "RELATIVE_TO_PRE_EVENT" and p["status"] != "INSUFFICIENT_METHODOLOGY":
                self.assertEqual(p["estimation_window"], "[-20,-1]")
            elif p["semantica"] != "RELATIVE_TO_PRE_EVENT":
                self.assertIsNone(p["estimation_window"])
            self.assertEqual(p["reaction_window"], p["horizon"])

    def test_ningun_perfil_produce_señal(self):
        prohibidos = ("score", "signal", "señal", "buy", "sell", "peso", "weight",
                      "reaction_gap", "confidence", "prediccion")
        for p in self.rejilla:
            for clave in p:
                self.assertNotIn(clave.lower(), prohibidos)


@requiere_parquet
class TestPoblacionYExclusiones(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.obs = pr.observaciones_v1()

    def test_nada_se_descarta_en_silencio(self):
        """incluidas + excluidas == poblacion de partida, siempre."""
        for medida in pr.MEDIDAS:
            for h in pr.HORIZONTES:
                inc, exc = pr.poblacion(self.obs, medida, h, HOY)
                self.assertEqual(len(inc) + len(exc), len(self.obs),
                                 f"{medida}/{h}")

    def test_toda_exclusion_lleva_motivo(self):
        for medida in pr.MEDIDAS:
            for h in pr.HORIZONTES:
                _inc, exc = pr.poblacion(self.obs, medida, h, HOY)
                for x in exc:
                    self.assertTrue(x["motivo"])
                    self.assertIn("asset_id", x)
                    self.assertIn("published_at", x)

    def test_la_tasa_de_exclusion_se_reporta_aunque_el_perfil_sea_valido(self):
        p = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "2_60d", HOY)
        self.assertGreater(p["n_excluidas"], 0)
        self.assertIsNotNone(p["tasa_exclusion"])
        self.assertTrue(p["exclusiones_por_motivo"])

    def test_el_solape_se_marca_y_no_se_elimina(self):
        """REESCRITO (D-30). Antes el solape EXCLUIA. Ahora se marca y se
        publican las dos muestras: eliminarlo de entrada impedia medir
        cuanto cambia la distribucion al quitar la contaminacion."""
        corto = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "0_1d", HOY)
        largo = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "2_60d", HOY)
        self.assertEqual(corto["overlap_event_count"], 0)
        self.assertGreater(largo["overlap_event_count"], 0)
        # con FLAG, los solapados SIGUEN en la muestra completa...
        self.assertNotIn(pr.EXCL_SOLAPE, largo["exclusiones_por_motivo"])
        # ...y ademas se publica la version sin ellos
        self.assertIsNotNone(largo["statistics_non_overlapping"])
        self.assertLess(largo["n_non_overlapping"], largo["n_observations"])

    def test_la_politica_EXCLUDE_sigue_disponible(self):
        p = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "2_60d", HOY,
                      politica_solape="EXCLUDE")
        self.assertIn(pr.EXCL_SOLAPE, p["exclusiones_por_motivo"])


@requiere_parquet
class TestPointInTime(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.obs = pr.observaciones_v1()

    def test_un_as_of_historico_reduce_la_poblacion(self):
        hoy = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "0_1d", HOY)
        ayer = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "0_1d", "2020-01-01")
        self.assertLess(ayer["n_observations"], hoy["n_observations"])
        self.assertEqual(ayer["n_observations"], 18)

    def test_reproducible_dos_veces_da_lo_mismo(self):
        a = pr.perfil(self.obs, "earnings_release", "ABNORMAL_RETURN", "0_1d", "2020-01-01")
        b = pr.perfil(self.obs, "earnings_release", "ABNORMAL_RETURN", "0_1d", "2020-01-01")
        self.assertEqual(a["statistics"], b["statistics"])
        self.assertEqual(a["n_observations"], b["n_observations"])

    def test_ningun_evento_incluido_era_desconocido_en_as_of(self):
        for as_of in ("2010-01-01", "2020-01-01", HOY):
            inc, _exc = pr.poblacion(self.obs, "RAW_RETURN", "0_1d", as_of)
            for o, _v in inc:
                self.assertLessEqual(o["available_at"][:10], as_of)

    def test_una_ventana_que_termina_despues_de_as_of_se_excluye(self):
        """El evento puede ser conocible y su ventana no haber terminado:
        usarla seria look-ahead igualmente."""
        inc, exc = pr.poblacion(self.obs, "RAW_RETURN", "2_60d", "2020-01-25")
        motivos = {x["motivo"] for x in exc}
        self.assertIn(pr.EXCL_PIT_VENTANA, motivos)
        for o, _v in inc:
            self.assertLessEqual(o["ventanas"]["2_60d"][1], "2020-01-25")

    def test_antes_de_todos_los_eventos_es_pit_invalid(self):
        p = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "0_1d", "1990-01-01")
        self.assertEqual(p["status"], "PIT_INVALID")
        self.assertEqual(p["n_observations"], 0)


@requiere_parquet
class TestEstados(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.obs = pr.observaciones_v1()
        cls.sin_bm = []
        for sym in pr.SIMBOLOS_V1:
            cls.sin_bm += er.estudiar(
                sym, os.path.join(pr.FIXTURES, f"{sym}_earnings.json"), con_benchmark=False)

    def test_sin_benchmark_el_abnormal_es_no_benchmark(self):
        p = pr.perfil(self.sin_bm, "earnings_release", "ABNORMAL_RETURN", "0_1d", HOY)
        self.assertEqual(p["status"], "NO_BENCHMARK")
        self.assertIsNone(p["statistics"])

    def test_sin_benchmark_el_raw_sigue_siendo_valido(self):
        """La regla de D-21 llevada al perfil: la ausencia de benchmark
        limita QUE medidas, no si hay perfil."""
        p = pr.perfil(self.sin_bm, "earnings_release", "RAW_RETURN", "0_1d", HOY)
        self.assertEqual(p["status"], "VALID")
        self.assertIsNotNone(p["statistics"])

    def test_peer_relative_sin_referencia_declarada(self):
        p = pr.perfil(self.obs, "earnings_release", "PEER_RELATIVE_RETURN", "0_1d", HOY)
        self.assertEqual(p["status"], "INSUFFICIENT_COMPARABILITY")

    def test_el_volumen_se_mide_contra_la_ventana_de_estimacion(self):
        """REESCRITO (D-27). Antes `VOLUME_CHANGE` normalizaba contra la
        sesion del propio evento y solo 0_1d era publicable. Ahora la base
        es la mediana de [-20,-1] y los cuatro horizontes son
        interpretables: 2,04x el dia del evento, decayendo a 1,01x."""
        for h, esperado in (("0_1d", 2.0), ("2_5d", 1.2), ("2_20d", 1.0), ("2_60d", 1.0)):
            p = pr.perfil(self.obs, "earnings_release", "VOLUME_RELATIVE_TO_PRE_EVENT", h, HOY)
            self.assertEqual(p["status"], "VALID", h)
            self.assertEqual(p["semantica"], "RELATIVE_TO_PRE_EVENT")
            self.assertEqual(p["estimation_window"], "[-20,-1]")
            self.assertAlmostEqual(p["statistics"]["median"], esperado, delta=0.35)

    def test_el_neutro_de_un_cociente_es_uno_no_cero(self):
        """Con neutro=0, prob_positive de un cociente seria 1,00 siempre:
        un numero cierto y completamente vacio."""
        p = pr.perfil(self.obs, "earnings_release", "VOLUME_RELATIVE_TO_PRE_EVENT", "0_1d", HOY)
        self.assertEqual(p["statistics"]["neutro"], 1.0)
        self.assertLess(p["statistics"]["prob_positive"], 1.0)
        r = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "0_1d", HOY)
        self.assertEqual(r["statistics"]["neutro"], 0.0)

    def test_la_volatilidad_disponible_no_tiene_metodologia(self):
        """Es una media movil de 30 sesiones: el valor del evento ya
        contiene la ventana de estimacion entera."""
        for h in pr.HORIZONTES:
            p = pr.perfil(self.obs, "earnings_release",
                          "VOLATILITY_RELATIVE_TO_PRE_EVENT", h, HOY)
            self.assertEqual(p["status"], "INSUFFICIENT_METHODOLOGY")
            self.assertIn("media movil", p["status_reason"])

    def test_muestra_insuficiente_sigue_reportando_la_distribucion(self):
        """INSUFFICIENT_SAMPLE no es 'no hay nada': es 'no me fio todavia'."""
        p = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "0_1d", "2020-01-01")
        self.assertEqual(p["status"], "INSUFFICIENT_SAMPLE")
        self.assertIsNotNone(p["statistics"])
        self.assertIn("minimo declarado", p["status_reason"])

    def test_el_minimo_viene_de_d22_no_de_un_numero_nuevo(self):
        self.assertEqual(pr._minimo_declarado("RAW_RETURN"),
                         er.MINIMOS_DECLARADOS[("RAW_RETURN", "reaccion_mediana_por_clase")])
        self.assertEqual(pr._minimo_declarado("ABNORMAL_RETURN"),
                         er.MINIMOS_DECLARADOS[("ABNORMAL_RETURN", "reaccion_mediana_por_clase")])

    def test_la_estabilidad_dice_que_no_es_evaluable_en_vez_de_afirmar(self):
        p = pr.perfil(self.obs, "earnings_release", "ABNORMAL_RETURN", "0_1d", HOY)
        self.assertFalse(p["estabilidad"]["evaluable"])
        self.assertIn("80", p["estabilidad"]["motivo"])


@requiere_parquet
class TestBenchmarkEnElPerfil(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.obs = pr.observaciones_v1()

    def test_el_perfil_abnormal_lleva_la_identidad_del_benchmark(self):
        """Sin estos metadatos el perfil seria irreproducible."""
        p = pr.perfil(self.obs, "earnings_release", "ABNORMAL_RETURN", "0_1d", HOY)
        self.assertEqual(p["benchmark_id"], "bm:sp500")
        self.assertEqual(p["benchmark_methodology_version"], "yahoo-^GSPC-close-1d/v1")
        self.assertEqual(p["metodo_ajuste"], er.DIFERENCIA_SIMPLE)

    def test_el_perfil_raw_no_inventa_benchmark(self):
        p = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "0_1d", HOY)
        self.assertIsNone(p["benchmark_id"])

    def test_mezclar_dos_benchmarks_hace_el_perfil_irreproducible(self):
        mezcla = [dict(o) for o in self.obs]
        mezcla[0]["benchmark_id"] = "bm:otro"
        p = pr.perfil(mezcla, "earnings_release", "ABNORMAL_RETURN", "0_1d", HOY)
        self.assertEqual(p["status"], "INSUFFICIENT_COMPARABILITY")
        self.assertIn("irreproducible", p["status_reason"])


class TestEstadisticos(unittest.TestCase):

    def test_sobre_un_vector_conocido(self):
        st = pr.estadisticos([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertEqual(st["median"], 5.5)
        self.assertEqual(st["mean"], 5.5)
        self.assertEqual(st["min"], 1)
        self.assertEqual(st["max"], 10)
        self.assertEqual(st["prob_positive"], 1.0)
        self.assertEqual(st["dispersion_iqr"], round(st["p75"] - st["p25"], 2))

    def test_no_se_reporta_solo_la_media(self):
        st = pr.estadisticos([1, 2, 3, 100])
        for k in ("median", "mean", "p10", "p25", "p75", "p90", "prob_positive", "dispersion_iqr"):
            self.assertIn(k, st)
        # con una cola, mediana y media difieren mucho: por eso van las dos
        self.assertNotEqual(st["median"], st["mean"])

    def test_vector_vacio_no_da_estadisticos_inventados(self):
        self.assertIsNone(pr.estadisticos([]))


@requiere_parquet
class TestValidacionManualContraElMVP(unittest.TestCase):
    """Comprobacion de una muestra pequeña contra las observaciones del
    Event Study MVP, como pidio el encargo."""

    @classmethod
    def setUpClass(cls):
        cls.obs = pr.observaciones_v1()

    def test_raw_0_1d_coincide_con_el_mvp(self):
        import statistics as st
        directo = [o["raw_return_1s_pct"] for o in self.obs if o["raw_return_1s_pct"] is not None]
        p = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "0_1d", HOY)
        self.assertEqual(p["n_observations"], len(directo))
        self.assertAlmostEqual(p["statistics"]["median"], st.median(directo), places=2)
        self.assertAlmostEqual(p["statistics"]["mean"], sum(directo) / len(directo), places=2)
        self.assertEqual(p["statistics"]["min"], min(directo))
        self.assertEqual(p["statistics"]["max"], max(directo))

    def test_abnormal_0_1d_coincide_con_el_mvp(self):
        import statistics as st
        directo = [o["market_adjusted_return_pct"] for o in self.obs
                   if o["market_adjusted_return_pct"] is not None]
        p = pr.perfil(self.obs, "earnings_release", "ABNORMAL_RETURN", "0_1d", HOY)
        self.assertEqual(p["n_observations"], len(directo))
        # delta y no places: el perfil redondea a 2 decimales y con n par la
        # mediana cae entre dos valores (-0,585 -> -0,58). El redondeo es
        # del perfil, no una discrepancia de calculo.
        self.assertAlmostEqual(p["statistics"]["median"], st.median(directo), delta=0.01)

    def test_raw_y_abnormal_son_distribuciones_DISTINTAS(self):
        """Si coincidieran, el ajuste no estaria haciendo nada."""
        r = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "0_1d", HOY)
        a = pr.perfil(self.obs, "earnings_release", "ABNORMAL_RETURN", "0_1d", HOY)
        self.assertNotEqual(r["statistics"]["median"], a["statistics"]["median"])
        self.assertNotEqual(r["statistics"]["prob_positive"], a["statistics"]["prob_positive"])

    def test_tres_eventos_concretos(self):
        esperado = {("NVDA", "2023-05-24"): (24.37, 23.49),
                    ("IBM", "2014-10-20"): (-7.11, -8.02),
                    ("XOM", "2020-05-01"): (-7.17, -4.36)}
        vistos = 0
        for o in self.obs:
            clave = (o["asset_id"], o["published_at"])
            if clave in esperado:
                raw, abn = esperado[clave]
                self.assertAlmostEqual(o["medidas"][("RAW_RETURN", "0_1d")], raw, places=2)
                self.assertAlmostEqual(o["medidas"][("ABNORMAL_RETURN", "0_1d")], abn, places=2)
                vistos += 1
        self.assertEqual(vistos, 3)


@requiere_parquet
class TestIndependencia(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.obs = pr.observaciones_v1()

    def test_los_episodios_no_aplican_a_una_publicacion_de_resultados(self):
        """'No puedo' no es 'no se': ningun dato adicional daria un
        episode_id a una publicacion de resultados, porque el episodio es
        una construccion de la capa de noticias."""
        p = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "0_1d", HOY)
        self.assertEqual(p["n_episodes"], pr.NO_APLICA)
        self.assertEqual(p["n_independent_episodes"], pr.NO_APLICA)

    def test_eventos_y_eventos_independientes_se_reportan_por_separado(self):
        p = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "2_60d", HOY)
        self.assertIn("n_events", p)
        self.assertIn("n_independent_events", p)
        # tras el filtro de solape, lo que queda es independiente
        self.assertEqual(p["n_events"], p["n_independent_events"])

    def test_un_evento_no_cuenta_dos_veces(self):
        p = pr.perfil(self.obs, "earnings_release", "RAW_RETURN", "0_1d", HOY)
        claves = {(o["asset_id"], o["period_end"]) for o in self.obs}
        self.assertEqual(p["n_events"], len(claves))


@requiere_parquet
class TestElPerfilNoSeUsaParaDecidir(unittest.TestCase):
    """PREDICTIVE_STATUS = NOT_EVALUATED tiene que ser una barrera real.

    Un perfil `VALID` describe lo que ocurrio; no esta validado fuera de
    muestra. La distincion entre los dos estados existe justamente para
    que no se cuele en una decision por parecerse a una senal."""

    def test_ningun_motor_de_decision_importa_el_perfil(self):
        for carpeta in ("scoring", "reasoning"):
            base = os.path.join(RAIZ, "engine", carpeta)
            if not os.path.isdir(base):
                continue
            for raiz, _, ficheros in os.walk(base):
                for f in ficheros:
                    if not f.endswith(".py"):
                        continue
                    with open(os.path.join(raiz, f), encoding="utf-8") as fh:
                        self.assertNotIn("perfil_reaccion", fh.read(),
                                         f"{carpeta}/{f} importa el perfil")

    def test_toda_la_rejilla_declara_no_evaluado_prediccionalmente(self):
        for p in pr.rejilla(pr.observaciones_v1(), HOY):
            self.assertEqual(p["predictive_status"], "NOT_EVALUATED",
                             f"{p['measure_type']}/{p['horizon']}")


if __name__ == "__main__":
    unittest.main()
