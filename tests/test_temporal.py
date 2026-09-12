"""Integridad temporal -- P6.2a (2026-09-07).

Demuestra, con el fixture negativo `tests/fixtures/temporal/look_ahead.json`,
que la invariante que el contrato ya tenia (`data_as_of <= retrieved_at`)
NO es suficiente para impedir un look-ahead, y que la que se anade en
`engine/contract/temporal.py` si lo detecta.
"""
import datetime
import json
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "engine", "contract"))

import schema      # noqa: E402
import temporal    # noqa: E402

FIXTURE = os.path.join(RAIZ, "tests", "fixtures", "temporal", "look_ahead.json")


def _fixture():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


class TestFixtureNegativo(unittest.TestCase):
    """El caso que la invariante vieja deja pasar."""

    @classmethod
    def setUpClass(cls):
        cls.f = _fixture()
        cls.defectuosa = cls.f["defectuosa"]
        cls.corregida = cls.f["corregida"]
        cls.as_of = cls.f["analysis_as_of_intermedio"]

    def test_la_invariante_vieja_acepta_las_dos_filas(self):
        """`data_as_of <= retrieved_at` no distingue entre la fila bien
        fechada y la mal fechada. No es un fallo del validador: es que esa
        invariante compara con la fecha de DESCARGA, no con la del analisis."""
        self.assertTrue(schema.validate_metric_row(self.defectuosa))
        self.assertTrue(schema.validate_metric_row(self.corregida))
        for fila in (self.defectuosa, self.corregida):
            self.assertLessEqual(fila["data_as_of"], fila["retrieved_at"][:10])

    def test_la_fila_defectuosa_seria_visible_en_una_fecha_imposible(self):
        """Filtrando por data_as_of -- que es lo que haria cualquier
        consulta as-of hoy -- la fila mal fechada aparece el 2026-07-01,
        21 dias antes de que IBM publicase esos resultados."""
        self.assertLessEqual(self.defectuosa["data_as_of"], self.as_of)
        self.assertGreater(self.corregida["data_as_of"], self.as_of)

    def test_la_invariante_nueva_rechaza_la_fila_en_esa_fecha(self):
        """Con `usable_en`, la fila corregida NO participa en un analisis
        fechado el 2026-07-01. Es el comportamiento que se buscaba."""
        usable, estado = temporal.usable_en(self.corregida, self.as_of)
        self.assertFalse(usable)
        self.assertEqual(estado, temporal.EXACTO)

    def test_la_misma_fila_si_es_usable_despues_de_publicarse(self):
        """La regla excluye por fecha, no por metrica: el 2026-07-22 la
        misma fila ya es utilizable."""
        usable, _ = temporal.usable_en(self.corregida, "2026-07-22")
        self.assertTrue(usable)
        usable, _ = temporal.usable_en(self.corregida, "2026-09-01")
        self.assertTrue(usable)

    def test_el_desfase_del_fixture_es_el_real_de_la_fuente(self):
        """El fixture no inventa fechas: sale del payload congelado."""
        with open(os.path.join(RAIZ, "tests", "fixtures", "equity", "IBM_earnings.json")) as fh:
            q = json.load(fh)["quarterlyEarnings"][0]
        self.assertEqual(self.defectuosa["data_as_of"], q["fiscalDateEnding"])
        self.assertEqual(self.corregida["data_as_of"], q["reportedDate"])
        dias = (datetime.date.fromisoformat(q["reportedDate"])
                - datetime.date.fromisoformat(q["fiscalDateEnding"])).days
        self.assertEqual(dias, 22)


class TestSemantica(unittest.TestCase):

    def test_lo_no_declarado_es_ambiguo_nunca_seguro(self):
        """Regla dura heredada de cadencias.py: la ausencia de declaracion
        es ausencia de criterio, no permiso."""
        self.assertEqual(temporal.clasificar("dominio_inventado", "metrica_inventada"), "AMBIGUOUS")

    def test_los_dos_grupos_de_fundamentales_llevan_relojes_distintos(self):
        grupo_a = ["eps", "roe_pct", "revenue_growth_yoy_pct", "profit_margin_pct",
                   "operating_margin_pct", "earnings_beats_8q", "earnings_misses_8q",
                   "earnings_surprise_avg_pct", "earnings_surprise_last_pct"]
        grupo_b = ["pe_ratio", "peg_ratio", "analyst_target_price",
                   "analyst_upside_pct", "analyst_n_analistas"]
        for m in grupo_a:
            self.assertEqual(temporal.clasificar("fundamental", m), "SAFE", m)
        for m in grupo_b:
            self.assertEqual(temporal.clasificar("fundamental", m), "STALE", m)

    def test_stale_no_es_look_ahead(self):
        """Son defectos de signo contrario y el vocabulario no los mezcla.
        La cota de available_at de una fila STALE es su retrieved_at (fue
        conocible al descargarla), no su data_as_of."""
        fila = dict(_fixture()["defectuosa"], metric="pe_ratio", value=20.57)
        fecha, estado = temporal.available_at(fila)
        self.assertEqual(estado, temporal.COTA_CONSERVADORA)
        self.assertEqual(fecha, datetime.date(2026, 9, 3))
        self.assertNotEqual(temporal.clasificar("fundamental", "pe_ratio"), "LOOK_AHEAD")

    def test_macro_da_cota_conservadora_no_fecha_exacta(self):
        """FRED no trae la fecha de publicacion (eso es ALFRED). La cota
        excluye, no afirma: sirve para decir 'esto seguro que no se sabia',
        nunca para decir 'esto se supo tal dia'."""
        fila = {"domain": "macro", "metric": "cpi_yoy_pct",
                "data_as_of": "2026-06-01", "retrieved_at": "2026-09-04T06:00:00Z"}
        fecha, estado = temporal.available_at(fila)
        self.assertEqual(estado, temporal.COTA_CONSERVADORA)
        self.assertEqual(fecha, datetime.date(2026, 7, 16))  # 2026-06-01 + 45 dias
        # con la cota, el IPC de junio NO es usable el 1 de julio
        self.assertFalse(temporal.usable_en(fila, "2026-07-01")[0])
        # y en modo estricto (backtest formal) no es usable nunca por cota
        self.assertFalse(temporal.usable_en(fila, "2026-09-01", admitir_cota=False)[0])

    def test_desconocido_no_es_permisivo(self):
        fila = {"domain": "dominio_inventado", "metric": "x",
                "data_as_of": "2020-01-01", "retrieved_at": "2026-01-01T00:00:00Z"}
        usable, estado = temporal.usable_en(fila, "2026-06-01")
        self.assertFalse(usable)
        self.assertEqual(estado, temporal.DESCONOCIDO)


class TestOrdenDeRelojes(unittest.TestCase):

    def test_orden_valido_no_exige_que_esten_todos(self):
        self.assertTrue(temporal.validar_orden(
            {"period_end": "2026-06-30", "retrieved_at": "2026-09-03"}))

    def test_detecta_contradiccion(self):
        with self.assertRaises(temporal.TemporalError):
            temporal.validar_orden(
                {"published_at": "2026-07-22", "available_at": "2026-07-01"})

    def test_el_caso_real_de_ibm_es_coherente(self):
        self.assertTrue(temporal.validar_orden({
            "period_end": "2026-06-30",
            "published_at": "2026-07-22",
            "available_at": "2026-07-22",
            "retrieved_at": "2026-09-03",
        }))


class TestCoherenciaEntreTablas(unittest.TestCase):

    def test_cadencias_y_temporal_no_divergen(self):
        """Si alguien corrige el defecto de fechado del grupo B en
        cadencias.py y se olvida de aqui (o al reves), esto lo dice."""
        self.assertTrue(temporal.comprobar_coherencia_con_cadencias())


if __name__ == "__main__":
    unittest.main()
