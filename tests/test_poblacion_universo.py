"""Auditoria de poblacion -- universo congelado, cobertura y leakage (2026-09-08).

La propiedad que ordena estos tests: el universo se DECLARA antes de medir,
y lo no medido nunca se rellena.
"""
import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for sub in ("contract", "events", "knowledge", "technical"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", sub))

import perfil_reaccion as pr   # noqa: E402
import universo as uni         # noqa: E402

HOY = "2026-09-08"


from _parquet import requiere_parquet  # noqa: E402


class TestUniversoCongelado(unittest.TestCase):

    def test_el_universo_tiene_el_tamano_pedido_y_diversidad_sectorial(self):
        inc = uni.universo()["included_assets"]
        self.assertGreaterEqual(len(inc), 30)
        self.assertLessEqual(len(inc), 50)
        self.assertGreaterEqual(len({a["sector"] for a in inc}), 5)

    def test_la_seleccion_es_reproducible_desde_su_regla(self):
        """La muestra declarada se deriva de la regla escrita, no de una lista suelta."""
        orden = sorted(uni.simbolos())
        stride3 = {orden[i] for i in range(0, len(orden), 3)}
        acciones = {a["symbol"] for a in uni.universo()["included_assets"]
                    if "accion_corporativa_posterior" in a}
        cohorte_v1 = set(pr.SIMBOLOS_V1)
        esperada = stride3 | acciones | cohorte_v1
        self.assertEqual(set(uni.muestra_declarada()), esperada)

    def test_el_universo_incluye_activos_que_dejaron_de_existir(self):
        """Sin ellos el universo tendria sesgo de superviviencia por construccion."""
        con_accion = [a for a in uni.universo()["included_assets"]
                      if "accion_corporativa_posterior" in a]
        self.assertTrue(con_accion)
        for a in con_accion:
            self.assertTrue(a["accion_corporativa_posterior"].strip())

    def test_el_universo_lista_empresas_a_auditar_no_activos_consultables(self):
        """Si el universo fuese "lo consultable", el proveedor decidiria quien
        existio en nuestro pasado -- y DWDP/UTX habrian sido bajas."""
        sem = uni.universo()["semantica"]
        self.assertIn("AUDITARSE", sem["significado"].upper())
        self.assertTrue(sem["por_que_cambio"].strip())
        # Los dos casos que la regla protege siguen en el universo.
        self.assertTrue({"DWDP", "UTX"} <= set(uni.simbolos()))

    def test_cada_exclusion_lleva_su_motivo(self):
        for a in uni.universo()["excluded_assets"]:
            self.assertTrue(a["exclusion_reason"].strip(), a["symbol"])

    def test_la_cohorte_de_v1_esta_dentro_del_universo(self):
        self.assertTrue(set(pr.SIMBOLOS_V1) <= set(uni.simbolos()))

    def test_las_dos_declaraciones_son_coherentes(self):
        self.assertEqual(uni.incoherencias(), [])


class TestCobertura(unittest.TestCase):

    def test_ningun_activo_no_medido_tiene_numeros_inventados(self):
        c = uni.cobertura()
        self.assertEqual(c["no_medidos"]["estado"], uni.NO_MEDIDO)
        medidos = {r["symbol"] for r in c["medidos"]}
        sin_medir = (set(c["no_medidos"]["simbolos_declarados_sin_medir"])
                     | set(c["no_medidos"]["resto_del_universo_sin_medir"]))
        self.assertFalse(medidos & sin_medir)

    def test_un_ticker_desaparecido_se_registra_vacio_no_ausente(self):
        """DWDP y UTX existen en el registro CON cero trimestres: la ausencia
        de dato es un dato, no una fila que falta."""
        regs = uni.registros_medidos()
        for sym in ("DWDP", "UTX"):
            self.assertIn(sym, regs)
            self.assertEqual(regs[sym]["quarters_available"], 0)
            self.assertEqual(regs[sym]["estado"], uni.TICKER_AUSENTE)

    def test_las_series_medidas_son_trimestralmente_contiguas(self):
        r = uni.resumen_cobertura()
        self.assertEqual(r["no_contiguos"], [])
        self.assertEqual(r["con_datos"], len(r["contiguos"]))

    def test_el_reportTime_esta_completo_en_todo_lo_medido(self):
        """Sin reportTime no hay first_tradable_at, y sin el no hay event study."""
        self.assertEqual(uni.resumen_cobertura()["sin_reportTime"], 0)

    def test_el_reportTime_no_es_constante_por_activo(self):
        """MSFT mezcla pre y post: asumirlo constante romperia first_tradable_at."""
        msft = uni.registros_medidos()["MSFT"]
        self.assertGreater(msft["pre_market_count"], 0)
        self.assertGreater(msft["post_market_count"], 0)

    def test_la_condicion_de_avance_no_se_cumple_todavia(self):
        """El exito de esta auditoria NO es poder avanzar: es saber que falta."""
        cond = uni.condicion_de_avance()
        self.assertFalse(cond["avanzar_a_v2"])
        self.assertFalse(cond["n_assets_suficiente"])
        self.assertTrue(cond["timestamp_suficiente"])

    def test_la_condicion_de_avance_es_transversal_no_de_volumen(self):
        """Muchos eventos de pocos activos no desbloquean nada."""
        self.assertFalse(uni.condicion_de_avance(n_assets_con_datos=3)["avanzar_a_v2"])
        self.assertTrue(uni.condicion_de_avance(
            n_assets_con_datos=uni.MIN_ACTIVOS_ALTO)["avanzar_a_v2"])


@requiere_parquet
class TestClaseDeHorizonte(unittest.TestCase):

    def test_2_60d_no_es_un_horizonte_de_reaccion(self):
        self.assertEqual(pr.HORIZON_CLASS["2_60d"], "LONGER_TERM_CONTEXT")
        self.assertNotIn("2_60d", pr.HORIZONTES_DE_REACCION)

    def test_los_tres_primarios_si_lo_son(self):
        for h in ("0_1d", "2_5d", "2_20d"):
            self.assertIn(h, pr.HORIZONTES_DE_REACCION)

    def test_2_60d_se_sigue_publicando(self):
        """Reclasificarlo no es eliminarlo."""
        p = pr.perfil(pr.observaciones_v1(), "earnings_release",
                      "ABNORMAL_RETURN", "2_60d", HOY)
        self.assertEqual(p["status"], "VALID")
        self.assertIsNotNone(p["statistics"])
        self.assertEqual(p["horizon_class"], "LONGER_TERM_CONTEXT")

    def test_toda_celda_declara_su_clase_de_horizonte(self):
        for p in pr.rejilla(pr.observaciones_v1(), HOY):
            self.assertIn(p["horizon_class"], pr.CLASES_DE_HORIZONTE)


@requiere_parquet
class TestModeloDeIndependencia(unittest.TestCase):

    def test_earnings_se_agrupa_por_activo(self):
        self.assertEqual(pr.INDEPENDENCE_MODEL["earnings_release"], "ASSET_CLUSTERED")

    def test_toda_clase_de_evento_declara_su_modelo(self):
        for clase in pr.CLASES_DE_EVENTO:
            self.assertIn(clase, pr.INDEPENDENCE_MODEL)
            self.assertIn(pr.INDEPENDENCE_MODEL[clase], pr.MODELOS_DE_INDEPENDENCIA)

    def test_toda_celda_declara_el_modelo(self):
        for p in pr.rejilla(pr.observaciones_v1(), HOY):
            self.assertEqual(p["independence_model"], "ASSET_CLUSTERED")

    def test_declarar_la_dependencia_no_es_corregirla(self):
        """D-31 sigue vigente: se reconoce la dependencia, no se calcula n_effective."""
        self.assertFalse([n for n in dir(pr) if "effective" in n.lower()])


@requiere_parquet
class TestProfileLeakage(unittest.TestCase):
    """Un perfil fechado en T debe salir identico aunque el dataset contenga
    observaciones posteriores a T."""

    @classmethod
    def setUpClass(cls):
        cls.completo = pr.observaciones_v1()

    def _truncar(self, T):
        return [o for o in self.completo
                if o["published_at"] and o["published_at"] <= T]

    def test_la_huella_no_cambia_al_anadir_observaciones_posteriores(self):
        for T in ("2015-01-01", "2018-06-30", "2020-01-01", "2023-01-01"):
            trunc = self._truncar(T)
            self.assertLess(len(trunc), len(self.completo), T)
            for m in pr.MEDIDAS:
                for h in pr.HORIZONTES:
                    a = pr.perfil(self.completo, "earnings_release", m, h, T)
                    b = pr.perfil(trunc, "earnings_release", m, h, T)
                    self.assertEqual(pr.huella(a), pr.huella(b), f"{m}/{h} en {T}")

    def test_las_estadisticas_son_identicas_no_solo_parecidas(self):
        T = "2020-01-01"
        trunc = self._truncar(T)
        for m in pr.MEDIDAS:
            for h in pr.HORIZONTES:
                a = pr.perfil(self.completo, "earnings_release", m, h, T)
                b = pr.perfil(trunc, "earnings_release", m, h, T)
                self.assertEqual(a["statistics"], b["statistics"], f"{m}/{h}")
                self.assertEqual(a["n_observations"], b["n_observations"])
                self.assertEqual(a["status"], b["status"])

    def test_solo_la_contabilidad_de_exclusiones_puede_diferir(self):
        """Y difiere legitimamente: describe el dataset ofrecido, no el perfil."""
        T = "2020-01-01"
        trunc = self._truncar(T)
        a = pr.perfil(self.completo, "earnings_release", "RAW_RETURN", "2_20d", T)
        b = pr.perfil(trunc, "earnings_release", "RAW_RETURN", "2_20d", T)
        distintos = {k for k in a
                     if json.dumps(a[k], sort_keys=True, default=str)
                     != json.dumps(b.get(k), sort_keys=True, default=str)}
        self.assertTrue(distintos)
        self.assertTrue(distintos <= set(pr.CAMPOS_DE_PROCEDENCIA), distintos)

    def test_la_huella_si_cambia_cuando_cambia_el_as_of(self):
        """Si no, la huella no estaria midiendo nada."""
        a = pr.perfil(self.completo, "earnings_release", "RAW_RETURN", "2_20d", "2020-01-01")
        b = pr.perfil(self.completo, "earnings_release", "RAW_RETURN", "2_20d", "2023-01-01")
        self.assertNotEqual(pr.huella(a), pr.huella(b))


if __name__ == "__main__":
    unittest.main(verbosity=2)
