"""Pruebas de DEMOSTRACION de la auditoria de compatibilidad (2026-09-07).

No son pruebas de regresion del comportamiento deseado: existen para
demostrar con datos reales congelados los hallazgos del informe
`informes/2026-09-07_auditoria_event_studies_y_pit.md`, para que ninguno
de ellos quede como una afirmacion de prosa sin verificar.

Las que documentan un defecto conocido van marcadas con
`@unittest.expectedFailure`: si alguien corrige el defecto, unittest
reporta "unexpected success" y eso es la senal de que hay que quitar la
marca y mover la prueba a la suite normal. Nunca dejar una de estas
marcada despues de corregir el hallazgo.
"""
import datetime
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_engines import _materialize_fixtures  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "engine", "contract"))
import schema  # noqa: E402


def _import_contract(modname):
    path = os.path.join(ROOT, "engine", "contract")
    sys.path.insert(0, path)
    try:
        if modname in sys.modules:
            del sys.modules[modname]
        return __import__(modname)
    finally:
        sys.path.remove(path)


class TestHallazgoLookAheadEnSorpresaDeResultados(unittest.TestCase):
    """HALLAZGO 1 (PARTIAL, look-ahead real en `data/` hoy).

    `adapt_equity()` sella la sorpresa de resultados con
    `fundamental_as_of` = LatestQuarter = `fiscalDateEnding` (fin del
    trimestre), pero la sorpresa solo fue CONOCIBLE en `reportedDate`
    (la fecha de publicacion de resultados). Alpha Vantage ya da ambas
    fechas en el mismo payload: el adaptador descarta la que importa
    para point-in-time.

    Es el mismo patron de bug ya corregido dos veces en este proyecto
    (BTC/XRP `fecha_dato` con `datetime.now()`, y `adapt_macro()`), pero
    aqui la fecha no es "demasiado tarde" sino "demasiado pronto", que
    es la direccion peligrosa: en un backtest el dato aparece como
    disponible antes de existir.
    """

    @classmethod
    def setUpClass(cls):
        _materialize_fixtures()
        cls.mod = _import_contract("adapters")

    def _reported_date(self, symbol):
        with open(os.path.join(FIXTURES, "equity", f"{symbol}_earnings.json")) as fh:
            return json.load(fh)["quarterlyEarnings"][0]["reportedDate"]

    def test_la_fuente_si_trae_la_fecha_de_publicacion(self):
        """El dato PIT existe en la fuente -- no es un limite de Alpha Vantage."""
        for symbol in ("IBM", "XOM"):
            with open(os.path.join(FIXTURES, "equity", f"{symbol}_earnings.json")) as fh:
                q = json.load(fh)["quarterlyEarnings"][0]
            self.assertIn("reportedDate", q)
            self.assertIn("estimatedEPS", q)      # expectativa (consenso)
            self.assertIn("reportedEPS", q)       # realizado
            self.assertIn("surprisePercentage", q)  # sorpresa ya escalada
            fis = datetime.date.fromisoformat(q["fiscalDateEnding"])
            rep = datetime.date.fromisoformat(q["reportedDate"])
            self.assertGreater(rep, fis, "reportedDate siempre es posterior al cierre del trimestre")

    def test_el_desfase_es_material_no_marginal(self):
        """22-32 dias de diferencia en las fixtures reales: no es un matiz."""
        desfases = []
        for symbol in ("IBM", "XOM"):
            with open(os.path.join(FIXTURES, "equity", f"{symbol}_earnings.json")) as fh:
                for q in json.load(fh)["quarterlyEarnings"]:
                    fis = datetime.date.fromisoformat(q["fiscalDateEnding"])
                    rep = datetime.date.fromisoformat(q["reportedDate"])
                    desfases.append((rep - fis).days)
        self.assertGreaterEqual(min(desfases), 20)
        self.assertGreaterEqual(max(desfases), 30)

    @unittest.expectedFailure
    def test_sorpresa_deberia_sellarse_con_la_fecha_en_que_fue_conocible(self):
        """DEFECTO CONOCIDO. Al corregirlo, quitar @expectedFailure."""
        rows = self.mod.adapt_equity("IBM")
        sorpresa = next(r for r in rows if r["metric"] == "earnings_surprise_last_pct")
        self.assertEqual(sorpresa["data_as_of"], self._reported_date("IBM"))

    def test_qa_actual_no_puede_detectar_este_look_ahead(self):
        """La regla temporal vigente (`data_as_of <= retrieved_at`) pasa
        sin problema con una fecha DEMASIADO TEMPRANA -- por eso el
        hallazgo no lo levanto `qa.py`. No es un fallo de qa.py: es que
        la invariante que valida no es la que hace falta aqui."""
        rows = self.mod.adapt_equity("IBM")
        sorpresa = next(r for r in rows if r["metric"] == "earnings_surprise_last_pct")
        self.assertTrue(schema.validate_metric_row(sorpresa))
        self.assertLess(sorpresa["data_as_of"], self._reported_date("IBM"))


class TestHallazgoDocumentoNoEsEvento(unittest.TestCase):
    """HALLAZGO 2 (MISSING). `adapt_news()` produce una fila por
    DOCUMENTO (`news_id` = sha1 de la URL). No hay `event_id` ni
    `episode_id`, asi que N articulos sobre el mismo hecho economico
    cuentan N veces. Sobre los datos reales de XRP ya en `data/news/`,
    7 de 50 filas pertenecen al mismo hilo regulatorio (Clarity Act)."""

    @classmethod
    def setUpClass(cls):
        _materialize_fixtures()
        cls.mod = _import_contract("adapters")

    def test_el_contrato_de_noticias_no_tiene_identidad_de_evento(self):
        self.assertIn("news_id", schema.NEWS_FIELDS)
        self.assertNotIn("event_id", schema.NEWS_FIELDS)
        self.assertNotIn("episode_id", schema.NEWS_FIELDS)

    def test_news_id_identifica_la_url_no_el_hecho(self):
        rows = self.mod.adapt_news("XRP", "crypto")
        self.assertTrue(rows)
        # dos documentos distintos sobre el mismo hecho tendrian dos
        # news_id distintos: la unicidad es de documento, no de evento.
        self.assertEqual(len(rows), len({r["news_id"] for r in rows}))

    def test_ningun_campo_permite_agrupar_por_hecho_economico(self):
        rows = self.mod.adapt_news("XRP", "crypto")
        agrupables = set(rows[0]) & {"event_id", "episode_id", "event_class", "surprise"}
        self.assertEqual(agrupables, set())


class TestHallazgoReaccionSinBenchmark(unittest.TestCase):
    """HALLAZGO 3 (PARTIAL / decision vigente sin implementar).

    `ledger.evaluate_pending()` juzga una tesis con rentabilidad BRUTA
    del activo. La Fase 0 ya decidio ("Version intermedia") comparar
    "contra benchmark", y el MVP ya incluia beta en el Risk Domain --
    ninguna de las dos cosas esta implementada. Hoy no seria posible
    aunque se quisiera: no hay ningun indice de mercado en DimAsset.
    """

    def test_no_hay_ningun_benchmark_en_dimasset(self):
        tipos = set()
        d = os.path.join(ROOT, "data", "assets")
        for fname in os.listdir(d):
            with open(os.path.join(d, fname)) as fh:
                tipos.add(json.load(fh)["asset_type"])
        self.assertEqual(tipos, {"crypto", "equity", "macro"})
        self.assertNotIn("index", tipos)
        self.assertNotIn("benchmark", tipos)

    def test_el_veredicto_del_ledger_es_rentabilidad_bruta(self):
        sys.path.insert(0, os.path.join(ROOT, "engine", "reasoning"))
        try:
            if "ledger" in sys.modules:
                del sys.modules["ledger"]
            ledger = __import__("ledger")
        finally:
            sys.path.remove(os.path.join(ROOT, "engine", "reasoning"))

        import tempfile
        tmp = tempfile.mkdtemp()
        original = ledger.LEDGER_DIR
        ledger.LEDGER_DIR = tmp
        try:
            entrada = {
                "id": "TEST_1", "activo": "TEST",
                "fecha_registro": "2026-01-01",
                "precio_en_el_momento": 100.0,
                "horizonte_evaluacion_dias": 90,
                "umbral_movimiento_significativo_pct": 10.0,
                "umbral_metodologia": "test",
                "tesis": {}, "evaluacion": None,
            }
            with open(os.path.join(tmp, "TEST.jsonl"), "w", encoding="utf-8") as fh:
                fh.write(json.dumps(entrada) + "\n")
            evaluadas = ledger.evaluate_pending("TEST", 115.0, hoy=datetime.date(2026, 6, 1))
        finally:
            ledger.LEDGER_DIR = original

        self.assertEqual(len(evaluadas), 1)
        ev = evaluadas[0]["evaluacion"]
        # +15% bruto supera el umbral de +10% -> "acerto el bull case",
        # con independencia de lo que hiciera el mercado en esos 90 dias.
        self.assertEqual(ev["variacion_pct"], 15.0)
        self.assertEqual(ev["veredicto"], "bull_case")
        self.assertNotIn("benchmark", ev)
        self.assertNotIn("variacion_ajustada_pct", ev)


class TestHallazgoSuficienciaDeEvidenciaYaTienePrecedente(unittest.TestCase):
    """HALLAZGO 4 (PARTIAL, a favor del proyecto). "Evidence
    Sufficiency" no hay que inventarla desde cero: `_pct_in_window()`
    ya se niega a calcular un percentil con menos de 10 observaciones,
    y devuelve None en vez de un numero con falsa precision. Es
    exactamente el principio que la investigacion propone generalizar."""

    @classmethod
    def setUpClass(cls):
        _materialize_fixtures()
        sys.path.insert(0, os.path.join(ROOT, "engine", "crypto"))
        try:
            if "score" in sys.modules:
                del sys.modules["score"]
            cls.crypto = __import__("score")
        finally:
            sys.path.remove(os.path.join(ROOT, "engine", "crypto"))

    def test_se_niega_a_calcular_con_muestra_insuficiente(self):
        self.assertIsNone(self.crypto._pct_in_window([1, 2, 3]))
        self.assertIsNone(self.crypto._pct_in_window(list(range(9))))
        self.assertIsNotNone(self.crypto._pct_in_window(list(range(10))))

    def test_devuelve_none_no_un_valor_por_defecto(self):
        """La ausencia se propaga como ausencia -- no se rellena con 50%
        ni con 0. Es la mitad de la regla que falta generalizar."""
        self.assertIsNone(self.crypto._pct_in_window([5, 5, 5, 5, 5, 5, 5, 5, 5, 5]))


class TestHallazgoEventStudyYaEsComputableHoy(unittest.TestCase):
    """HALLAZGO 5 (el mas importante para decidir el siguiente paso).

    Verificado en vivo el 2026-09-07 (2 llamadas a Alpha Vantage
    EARNINGS): el plan GRATUITO devuelve la historia trimestral completa
    -- IBM 123 trimestres desde 1996-03-31, NVDA 111 desde 1999-04-30 --
    y cada trimestre trae `fiscalDateEnding` (event_occurred_at),
    `reportedDate` (available_at), `estimatedEPS` (expectativa),
    `reportedEPS` (realizado), `surprisePercentage` (sorpresa escalada)
    y `reportTime` (pre-market / post-market, que es lo que resuelve
    first_tradable_at). `engine/equity/score.py` corta la serie con
    `earn[:8]` y el adaptador tira todas esas fechas.

    Con eso mas los precios diarios que el backfill del bloque 4 ya
    dejo en `data/metrics/` (IBM/XOM desde 1970, NVDA desde su OPV de
    1999), un primer event study es computable HOY, sin fuente nueva.

    Los eventos de abajo estan copiados literalmente de esa consulta en
    vivo; los precios salen del propio Data Contract. El retorno es
    BRUTO -- sin ajustar por mercado ni sector -- que es exactamente la
    pieza que falta (ver TestHallazgoReaccionSinBenchmark).
    """

    # (reportedDate, reportTime, surprisePercentage) -- Alpha Vantage, 2026-09-07
    EVENTOS = {
        "NVDA": [
            ("2018-11-15", "post-market", -2.1277),
            ("2022-11-16", "post-market", -18.3099),
            ("2023-05-24", "post-market", 18.4783),
        ],
        "IBM": [
            ("2014-10-20", "pre-market", -18.0556),
            ("2018-01-18", "post-market", 0.1934),
        ],
    }

    @staticmethod
    def _serie_precios(symbol):
        with open(os.path.join(ROOT, "data", "metrics", f"{symbol}.json")) as fh:
            rows = [r for r in json.load(fh) if r["metric"] == "precio"]
        px = {r["data_as_of"]: r["value"] for r in rows}
        return sorted(px), px

    @classmethod
    def _primera_sesion_negociable(cls, fechas, reported_date, report_time):
        """`reportTime` resuelve first_tradable_at sin datos intradia:
        pre-market -> la propia sesion del anuncio; post-market -> la
        siguiente. Es una aproximacion diaria explicita, no un supuesto
        escondido."""
        import bisect
        if report_time == "pre-market":
            i = bisect.bisect_left(fechas, reported_date)
        else:
            i = bisect.bisect_right(fechas, reported_date)
        return i

    def test_hay_precio_para_la_primera_sesion_negociable_de_cada_evento(self):
        for symbol, eventos in self.EVENTOS.items():
            fechas, _ = self._serie_precios(symbol)
            for rep, rt, _s in eventos:
                i = self._primera_sesion_negociable(fechas, rep, rt)
                self.assertGreater(i, 0, f"{symbol} {rep}: sin sesion previa")
                self.assertLess(i, len(fechas), f"{symbol} {rep}: sin sesion posterior")

    def test_la_sorpresa_no_explica_la_reaccion_por_si_sola(self):
        """La razon de ser de todo el trabajo propuesto, demostrada con
        datos propios: en NVDA una sorpresa NEGATIVA pequena (-2.1%) fue
        seguida de -18.8%, y una sorpresa negativa ENORME (-18.3%) de
        solo -1.5%. Ni el signo ni la magnitud de la sorpresa bastan --
        y el sentimiento de la noticia habria acertado aun menos."""
        fechas, px = self._serie_precios("NVDA")

        def ret_1d(rep, rt):
            i = self._primera_sesion_negociable(fechas, rep, rt)
            return (px[fechas[i]] - px[fechas[i - 1]]) / px[fechas[i - 1]] * 100

        sorpresa_pequena = ret_1d("2018-11-15", "post-market")
        sorpresa_enorme = ret_1d("2022-11-16", "post-market")
        self.assertLess(sorpresa_pequena, -15)
        self.assertGreater(sorpresa_enorme, -5)
        # la reaccion mas violenta corresponde a la sorpresa MAS PEQUENA
        self.assertLess(sorpresa_pequena, sorpresa_enorme)

    def test_el_retorno_calculado_es_bruto_no_anormal(self):
        """Deja constancia de la limitacion: sin indice de mercado en
        DimAsset, -18.8% de NVDA incluye lo que hiciera el Nasdaq ese
        dia. No se puede separar evento de mercado con lo que hay."""
        d = os.path.join(ROOT, "data", "assets")
        assets = []
        for fname in os.listdir(d):
            with open(os.path.join(d, fname)) as fh:
                assets.append(json.load(fh))
        indices = [a for a in assets if a["asset_type"] not in ("crypto", "equity", "macro")]
        self.assertEqual(indices, [])
        # ninguna de las 3 acciones es un indice: son valores individuales
        equities = {a["asset_id"] for a in assets if a["asset_type"] == "equity"}
        self.assertEqual(equities, {"IBM", "NVDA", "XOM"})


if __name__ == "__main__":
    unittest.main()
