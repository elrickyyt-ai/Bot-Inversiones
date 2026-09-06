"""Cobertura y frescura -- P1b (2026-09-06).

Casi todo se prueba contra las funciones puras con fechas explicitas, no
contra data/: el contenido de data/ cambia cada dia que corre el cron y
un test que dependiera de el se volveria ruido. Lo que se prueba aqui es
la SEMANTICA -- que un umbral en dias naturales clasificaria al reves,
que el estado de un dominio es el de su peor componente, que una ausencia
comprobada no es lo mismo que un hueco -- no los valores de hoy.
"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine", "contract"))

import cadencias  # noqa: E402
import cobertura  # noqa: E402

D = datetime.date


class TestUnidadDeCadencia(unittest.TestCase):
    """La unidad importa tanto como el umbral."""

    def test_un_viernes_visto_un_domingo_esta_al_dia_en_acciones(self):
        # 2026-09-04 viernes, 2026-09-06 domingo. En sesiones NYSE no
        # falta nada; en dias naturales parecerian 2 dias de retraso.
        est, r, unidad = cobertura.estado_frescura(
            "equity", "tecnico", "precio", D(2026, 9, 4), D(2026, 9, 6))
        self.assertEqual((est, r, unidad), ("FRESH", 0, cadencias.SESION))

    def test_el_mismo_hueco_en_cripto_si_cuenta(self):
        # El mercado cripto no cierra el fin de semana: del viernes al
        # domingo han pasado dos dias en los que deberia haber dato.
        est, r, _ = cobertura.estado_frescura(
            "crypto", "tecnico", "precio", D(2026, 9, 4), D(2026, 9, 6))
        self.assertEqual((est, r), ("LAGGING", 2))

    def test_festivo_bursatil_no_cuenta_como_retraso(self):
        """El 4 de julio de 2026 cae en sabado, asi que el mercado cierra
        el viernes 3. Del jueves 2 al lunes 6 solo ha habido UNA sesion
        (el propio lunes), aunque hayan pasado cuatro dias naturales."""
        est, r, _ = cobertura.estado_frescura(
            "equity", "tecnico", "precio", D(2026, 7, 2), D(2026, 7, 6))
        self.assertEqual((est, r), ("FRESH", 1))
        # el mismo tramo en cripto son cuatro dias, y eso si es retraso
        est_c, r_c, _ = cobertura.estado_frescura(
            "crypto", "tecnico", "precio", D(2026, 7, 2), D(2026, 7, 6))
        self.assertEqual((est_c, r_c), ("STALE", 4))


class TestUmbralAbsolutoClasificariaAlReves(unittest.TestCase):
    def test_67_dias_de_ipc_estan_al_dia(self):
        """El IPC se publica mensualmente y con semanas de retraso: 67
        dias es su comportamiento normal, no una anomalia."""
        est, r, unidad = cobertura.estado_frescura(
            "macro", "macro", "cpi_yoy_pct", D(2026, 7, 1), D(2026, 9, 6))
        self.assertEqual((est, r, unidad), ("FRESH", 67, cadencias.DIA))

    def test_dos_sesiones_de_una_serie_diaria_no_lo_estan(self):
        est, r, _ = cobertura.estado_frescura(
            "equity", "tecnico", "confluencia_sesgo", D(2026, 9, 2), D(2026, 9, 6))
        self.assertEqual((est, r), ("LAGGING", 2))

    def test_una_regla_de_30_dias_habria_acertado_al_reves_en_los_dos(self):
        """Comprobacion explicita de que el criterio por cadencia y un
        umbral fijo de 30 dias dan diagnosticos OPUESTOS en estos dos
        casos reales -- que es el argumento entero de P1b."""
        ipc = cobertura.estado_frescura("macro", "macro", "cpi_yoy_pct",
                                        D(2026, 7, 1), D(2026, 9, 6))
        diaria = cobertura.estado_frescura("equity", "tecnico", "confluencia_sesgo",
                                           D(2026, 9, 2), D(2026, 9, 6))
        umbral_30 = lambda f: "STALE" if (D(2026, 9, 6) - f).days > 30 else "FRESH"
        self.assertEqual(ipc[0], "FRESH")
        self.assertEqual(umbral_30(D(2026, 7, 1)), "STALE")      # se equivoca
        self.assertEqual(diaria[0], "LAGGING")
        self.assertEqual(umbral_30(D(2026, 9, 2)), "FRESH")      # se equivoca


class TestUnknownNoEsPermisivo(unittest.TestCase):
    def test_metrica_sin_cadencia_declarada_es_unknown(self):
        est, r, unidad = cobertura.estado_frescura(
            "crypto", "dominio_inventado", "metrica_inventada", D(2026, 9, 6), D(2026, 9, 6))
        self.assertEqual(est, "UNKNOWN")
        self.assertIsNone(r)
        self.assertIsNone(unidad)

    def test_unknown_es_peor_que_stale_al_agregar(self):
        """Un dominio con una metrica caducada y otra sin declarar no
        puede reportarse como STALE: hay algo que ni siquiera se sabe."""
        self.assertGreater(cobertura.ORDEN_FRESCURA["UNKNOWN"],
                           cobertura.ORDEN_FRESCURA["STALE"])

    def test_cobertura_sin_conjunto_declarado_es_unknown(self):
        est, faltan = cobertura._estado_cobertura(None, {"a", "b"}, set())
        self.assertEqual(est, "UNKNOWN")
        self.assertEqual(faltan, set())


class TestElDominioValeLoQueSuPeorComponente(unittest.TestCase):
    def test_peor_gana_al_mas_reciente(self):
        fresh = ("FRESH", 0, "precio", "sesion")
        stale = ("STALE", 47, "pe_ratio", "sesion")
        self.assertEqual(cobertura._peor(fresh, stale), stale)
        self.assertEqual(cobertura._peor(stale, fresh), stale)

    def test_a_igual_estado_gana_el_retraso_mayor(self):
        a = ("LAGGING", 2, "x", "sesion")
        b = ("LAGGING", 3, "y", "sesion")
        self.assertEqual(cobertura._peor(a, b), b)
        self.assertEqual(cobertura._peor(b, a), b)


class TestLaAusenciaTieneCausas(unittest.TestCase):
    """Tres ausencias identicas de tvl_percentile_365d con tres causas
    que no se parecen. Sin la declaracion, las tres son la misma casilla
    vacia."""

    ESP = cadencias.ESPERADAS[("crypto", "fundamental")]
    PRESENTES = {"market_cap_percentile_365d", "fdv_mcap_ratio", "supply_pct_of_max"}

    def _evaluar(self, asset_id):
        sin_aplicar = {m for m in self.ESP if cadencias.no_aplica(asset_id, "fundamental", m)}
        return cobertura._estado_cobertura(self.ESP, self.PRESENTES, sin_aplicar)

    def test_btc_no_tiene_tvl_por_naturaleza_y_su_cobertura_es_completa(self):
        est, faltan = self._evaluar("BTC")
        self.assertEqual(est, "AVAILABLE")
        self.assertEqual(faltan, set())

    def test_xrp_igual_que_btc(self):
        self.assertEqual(self._evaluar("XRP")[0], "AVAILABLE")

    def test_dot_si_es_un_hueco_porque_la_fuente_falla(self):
        """DefiLlama reporta TVL=0 en toda la serie de Polkadot. Es una
        incidencia real de la fuente, no una metrica que no aplique, y
        por eso DOT NO esta en la tabla NO_APLICA."""
        est, faltan = self._evaluar("DOT")
        self.assertEqual(est, "PARTIAL")
        self.assertEqual(faltan, {"tvl_percentile_365d"})

    def test_dominio_entero_sin_ninguna_metrica_es_missing(self):
        est, faltan = cobertura._estado_cobertura(self.ESP, set(), set())
        self.assertEqual(est, "MISSING")

    def test_si_todo_lo_esperado_no_aplica_el_dominio_no_aplica(self):
        est, _ = cobertura._estado_cobertura(self.ESP, set(), set(self.ESP))
        self.assertEqual(est, "NOT_APPLICABLE")


class TestDeclaracionCoherente(unittest.TestCase):
    def test_toda_metrica_esperada_tiene_cadencia_declarada(self):
        """Si se declara que una metrica deberia existir pero no cuando
        deberia refrescarse, su frescura sale UNKNOWN para siempre."""
        sin_cadencia = []
        for (_, dominio), metricas in cadencias.ESPERADAS.items():
            for m in metricas:
                if cadencias.cadencia(dominio, m) is None:
                    sin_cadencia.append((dominio, m))
        for (aid, dominio), metricas in cadencias.ESPERADAS_POR_ACTIVO.items():
            for m in metricas:
                if cadencias.cadencia(dominio, m) is None:
                    sin_cadencia.append((dominio, m))
        self.assertEqual(sin_cadencia, [])

    def test_no_aplica_solo_menciona_metricas_que_se_esperan(self):
        """Declarar que algo no aplica sin que nadie lo esperase es una
        entrada muerta que nadie va a retirar."""
        for (aid, dominio, metric) in cadencias.NO_APLICA:
            esp = cadencias.ESPERADAS.get(("crypto", dominio)) or set()
            self.assertIn(metric, esp, f"{aid}/{dominio}/{metric} no esta en ESPERADAS")

    def test_el_defecto_de_fechado_registrado_sigue_siendo_de_cadencia_diaria(self):
        """Estas cinco se escriben con la fecha del trimestre pese a
        depender del precio del dia (registrado en P1, no corregido).
        Si alguien cambia su cadencia declarada a trimestral, el defecto
        deja de verse y este test lo impide."""
        for m in cadencias.DEFECTO_DE_FECHADO:
            self.assertEqual(cadencias.cadencia("fundamental", m), (cadencias.SESION, 1))


class TestIntegracionConLosDatosReales(unittest.TestCase):
    """Una sola prueba contra data/, y solo de estructura: los valores
    cambian cada dia y no deben fijarse en un test."""

    @classmethod
    def setUpClass(cls):
        cls.res = cobertura.evaluar()

    def test_estructura_y_estados_validos(self):
        self.assertIn("por_dominio", self.res)
        self.assertIn("por_metrica", self.res)
        self.assertTrue(self.res["por_dominio"])
        for f in self.res["por_dominio"]:
            self.assertIn(f["cobertura"],
                          {"AVAILABLE", "PARTIAL", "MISSING", "NOT_APPLICABLE", "UNKNOWN"})
            self.assertIn(f["estado_frescura"], {"FRESH", "LAGGING", "STALE", "UNKNOWN"})

    def test_los_dos_ejes_son_independientes(self):
        """Debe existir al menos un dominio disponible Y no fresco. Si
        no existiera, el modelo de dos ejes seria innecesario -- y lo
        que hay hoy en data/ es justamente IBM/XOM fundamental."""
        mixtos = [f for f in self.res["por_dominio"]
                  if f["cobertura"] == "AVAILABLE" and f["estado_frescura"] in ("STALE", "LAGGING")]
        self.assertTrue(mixtos, "ningun dominio disponible-y-no-fresco: revisar el modelo")

    def test_ningun_dominio_declarado_se_queda_sin_evaluar(self):
        for f in self.res["por_dominio"]:
            self.assertIsNotNone(f["asset_id"])
            self.assertIsNotNone(f["domain"])

    def test_las_metricas_presentes_estan_todas_declaradas(self):
        """Un motor que empiece a emitir una metrica nueva sin declararla
        la deja fuera del calculo de cobertura sin que nadie se entere."""
        no_declaradas = {(f["asset_id"], f["domain"], m)
                         for f in self.res["por_dominio"]
                         for m in f["metricas_no_declaradas"]}
        self.assertEqual(no_declaradas, set())


if __name__ == "__main__":
    unittest.main()
