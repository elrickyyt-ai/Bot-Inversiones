"""Validez analitica de una tesis segun la evidencia que usa -- P1
(2026-09-06).

La regla que se prueba aqui no es "si algo esta caducado, invalida". Es:
una evidencia caducada invalida la tesis SOLO si la tesis depende de ella.
pe_ratio con 47 sesiones de retraso aparece en el texto del bear_case y
ninguna regla se bifurca por su valor: debe producir una advertencia, no
anular la conclusion.

Casi todo se prueba con relojes sinteticos, no con data/: lo que importa
es la semantica, no las fechas de hoy.
"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine", "contract"))

from test_engines import _materialize_fixtures, _import, ROOT  # noqa: E402

import schema  # noqa: E402
from schema import ContractError  # noqa: E402

HOY = datetime.date(2026, 9, 6)


def _thesis_mod():
    return _import("reasoning", "thesis")


class TestElPapelDecideLaValidez(unittest.TestCase):
    """El caso concreto que motivo esta regla."""

    @classmethod
    def setUpClass(cls):
        cls.t = _thesis_mod()

    def _evaluar(self, entradas, relojes):
        return self.t._evaluar_evidencia(entradas, relojes, "IBM", "equity", hoy=HOY)

    def test_publicada_caducada_no_invalida(self):
        """pe_ratio de hace un trimestre + confluencia de ayer = VÁLIDA.
        La tesis no se bifurca por el P/E."""
        entradas = [
            (None, "tecnico", "confluencia_sesgo", self.t.REQUERIDA, "equity", "precio", ""),
            (None, "fundamental", "pe_ratio", self.t.PUBLICADA, "equity", "fundamental", ""),
        ]
        relojes = {"equity": {"precio": "2026-09-04", "fundamental": "2026-06-30"}}
        ev, validez = self._evaluar(entradas, relojes)
        self.assertEqual(validez, "VALID")
        self.assertEqual([e["frescura"] for e in ev], ["FRESH", "STALE"])

    def test_la_misma_metrica_caducada_si_invalida_cuando_es_requerida(self):
        """Idéntico al anterior salvo el papel de pe_ratio. Es lo único
        que cambia, y cambia el resultado."""
        entradas = [
            (None, "tecnico", "confluencia_sesgo", self.t.REQUERIDA, "equity", "precio", ""),
            (None, "fundamental", "pe_ratio", self.t.REQUERIDA, "equity", "fundamental", ""),
        ]
        relojes = {"equity": {"precio": "2026-09-04", "fundamental": "2026-06-30"}}
        _, validez = self._evaluar(entradas, relojes)
        self.assertEqual(validez, "INVALID")

    def test_contexto_caducado_no_invalida(self):
        entradas = [
            (None, "tecnico", "confluencia_sesgo", self.t.REQUERIDA, "equity", "precio", ""),
            ("US", "macro", "cpi_yoy_pct", self.t.CONTEXTO, "macro_us", "cpi_yoy_pct", ""),
        ]
        relojes = {"equity": {"precio": "2026-09-04"},
                   "macro_us": {"cpi_yoy_pct": "2025-01-01"}}
        ev, validez = self._evaluar(entradas, relojes)
        self.assertEqual(validez, "VALID")
        self.assertEqual(ev[1]["frescura"], "STALE")

    def test_requerida_sin_cadencia_declarada_es_unknown_no_valid(self):
        """"No se pudo determinar" no es "está al día"."""
        entradas = [(None, "dominio_inventado", "metrica_inventada",
                     self.t.REQUERIDA, "equity", "precio", "")]
        _, validez = self._evaluar(entradas, {"equity": {"precio": "2026-09-04"}})
        self.assertEqual(validez, "UNKNOWN")

    def test_requerida_sin_fecha_es_invalid(self):
        entradas = [(None, "tecnico", "confluencia_sesgo",
                     self.t.REQUERIDA, "equity", "precio", "")]
        _, validez = self._evaluar(entradas, {"equity": {}})
        self.assertEqual(validez, "INVALID")

    def test_lagging_no_invalida(self):
        """LAGGING es un periodo de cadencia de retraso: se avisa, no se
        anula. Solo STALE (más del doble) invalida."""
        entradas = [(None, "tecnico", "confluencia_sesgo",
                     self.t.REQUERIDA, "equity", "precio", "")]
        ev, validez = self._evaluar(entradas, {"equity": {"precio": "2026-09-02"}})
        self.assertEqual(ev[0]["frescura"], "LAGGING")
        self.assertEqual(validez, "VALID")


class TestAdvertenciasYCobertura(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = _thesis_mod()

    def test_una_cifra_caducada_que_se_publica_genera_advertencia(self):
        ev = [{"entidad": "IBM", "metrica": "analyst_target_price", "papel": self.t.PUBLICADA,
               "frescura": "STALE", "data_as_of": "2026-06-30", "retraso": 47, "unidad": "sesion"}]
        avisos = self.t._advertencias_de_frescura(ev)
        self.assertEqual(len(avisos), 1)
        self.assertIn("analyst_target_price", avisos[0])
        self.assertIn("2026-06-30", avisos[0])

    def test_lo_que_esta_al_dia_no_genera_ruido(self):
        ev = [{"entidad": "IBM", "metrica": "x", "papel": self.t.PUBLICADA,
               "frescura": "LAGGING", "data_as_of": "2026-09-04", "retraso": 2, "unidad": "sesion"}]
        self.assertEqual(self.t._advertencias_de_frescura(ev), [])

    def test_la_cobertura_ya_no_es_una_constante(self):
        """Antes era sum([True, True, True, ...]): sólo podía dar 3/4 o
        4/4 pasara lo que pasara."""
        con_datos = [{"dominio": "fundamental", "data_as_of": "2026-09-04"},
                     {"dominio": "tecnico", "data_as_of": "2026-09-04"},
                     {"dominio": "macro", "data_as_of": "2026-09-04"}]
        self.assertEqual(self.t._cobertura_real(con_datos, False), (3, 4))
        self.assertEqual(self.t._cobertura_real(con_datos, True), (4, 4))
        sin_macro = [e for e in con_datos if e["dominio"] != "macro"]
        self.assertEqual(self.t._cobertura_real(sin_macro, False), (2, 4))
        sin_fecha = [dict(e, data_as_of=None) for e in con_datos]
        self.assertEqual(self.t._cobertura_real(sin_fecha, False), (0, 4))


class TestElMapaDeEvidenciaEsCoherente(unittest.TestCase):
    """Si una evidencia REQUERIDA no tiene cadencia declarada, la tesis
    queda en UNKNOWN para siempre por una laguna de declaración, no de
    datos. Este test lo impide."""

    @classmethod
    def setUpClass(cls):
        cls.t = _thesis_mod()
        import cadencias
        cls.cad = cadencias

    def test_toda_evidencia_requerida_tiene_cadencia(self):
        sin_declarar = []
        for entradas in (self.t.EVIDENCIA_CRYPTO, self.t.EVIDENCIA_EQUITY):
            for _, dominio, metrica, papel, _, _, _ in entradas:
                if papel == self.t.REQUERIDA and self.cad.cadencia(dominio, metrica) is None:
                    sin_declarar.append((dominio, metrica))
        self.assertEqual(sin_declarar, [])

    def test_toda_evidencia_declara_un_motivo(self):
        for entradas in (self.t.EVIDENCIA_CRYPTO, self.t.EVIDENCIA_EQUITY):
            for e in entradas:
                self.assertTrue(e[6], f"evidencia sin motivo: {e[1]}.{e[2]}")

    def test_los_papeles_son_del_vocabulario_cerrado(self):
        validos = {self.t.REQUERIDA, self.t.PUBLICADA, self.t.CONTEXTO}
        for entradas in (self.t.EVIDENCIA_CRYPTO, self.t.EVIDENCIA_EQUITY):
            for e in entradas:
                self.assertIn(e[3], validos)


class TestElContratoImpideConfianzaSinEvidencia(unittest.TestCase):
    BASE = {
        "thesis_id": "IBM_2026-09-06_x", "asset_id": "IBM", "thesis_type": "equity",
        "bull_case": "b", "base_case": "b", "bear_case": "b",
        "contradictions": [], "convergences": [], "divergences": [],
        "invalidation_factors": [], "evidence": [],
        "data_as_of": "2026-09-06", "retrieved_at": "2026-09-06T10:00:00Z",
    }

    def test_valida_admite_confianza(self):
        row = dict(self.BASE, evidence_validity="VALID", confidence_pct=75)
        self.assertTrue(schema.validate_thesis_row(row))

    def test_invalida_con_confianza_es_rechazada(self):
        row = dict(self.BASE, evidence_validity="INVALID", confidence_pct=75)
        with self.assertRaises(ContractError):
            schema.validate_thesis_row(row)

    def test_unknown_con_confianza_es_rechazada(self):
        row = dict(self.BASE, evidence_validity="UNKNOWN", confidence_pct=40)
        with self.assertRaises(ContractError):
            schema.validate_thesis_row(row)

    def test_invalida_sin_confianza_es_correcta(self):
        row = dict(self.BASE, evidence_validity="INVALID", confidence_pct=None)
        self.assertTrue(schema.validate_thesis_row(row))

    def test_vocabulario_cerrado(self):
        row = dict(self.BASE, evidence_validity="CADUCADA", confidence_pct=None)
        with self.assertRaises(ContractError):
            schema.validate_thesis_row(row)


class TestSobreLasFixturesReales(unittest.TestCase):
    """Las fixtures están congeladas en 2026-07-20 (cripto) y 2026-09-02
    (acciones), así que producen los dos resultados opuestos con datos
    reales del proyecto."""

    @classmethod
    def setUpClass(cls):
        _materialize_fixtures()
        cls.t = _thesis_mod()

    def test_cripto_con_datos_de_hace_dos_meses_no_publica_confianza(self):
        r = self.t.build_thesis("BTC", None)
        self.assertEqual(r["validez_evidencia"], "INVALID")
        self.assertIsNone(r["confidence_pct"])
        requeridas = [e for e in r["evidencia"] if e["papel"] == self.t.REQUERIDA]
        self.assertTrue(all(e["frescura"] == "STALE" for e in requeridas))

    def test_acciones_con_pe_caducado_pero_tecnico_al_dia_si_publica_confianza(self):
        """El caso que motivó la regla, sobre datos reales: IBM tiene
        pe_ratio, peg_ratio y los dos analyst_* con decenas de sesiones
        de retraso, y aun así la tesis es válida porque ninguna regla
        depende de ellos."""
        r = self.t.build_thesis_equity("IBM")
        self.assertEqual(r["validez_evidencia"], "VALID")
        self.assertIsNotNone(r["confidence_pct"])
        caducadas = {e["metrica"] for e in r["evidencia"] if e["frescura"] == "STALE"}
        self.assertIn("pe_ratio", caducadas)
        self.assertTrue(all(e["papel"] != self.t.REQUERIDA
                            for e in r["evidencia"] if e["frescura"] == "STALE"))

    def test_las_cifras_caducadas_aparecen_en_las_advertencias(self):
        r = self.t.build_thesis_equity("IBM")
        texto = " ".join(r["advertencias"])
        self.assertIn("pe_ratio", texto)

    def test_la_tesis_declara_de_que_evidencia_depende(self):
        r = self.t.build_thesis_equity("IBM")
        self.assertTrue(r["evidencia"])
        for e in r["evidencia"]:
            self.assertIn(e["papel"], {self.t.REQUERIDA, self.t.PUBLICADA, self.t.CONTEXTO})
            self.assertTrue(e["motivo"], f"{e['metrica']} sin motivo declarado")


if __name__ == "__main__":
    unittest.main()
