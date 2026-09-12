"""Ontologia de benchmark -- D-21 (2026-09-07).

Los diez tests que el usuario fijo como criterio de aceptacion. Ninguno
necesita datos de benchmark reales: se validan conjuntos de Knowledge
sinteticos, que es lo que permite fijar la ontologia ANTES de introducir
ningun indice concreto.
"""
import copy
import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "engine", "knowledge"))
sys.path.insert(0, os.path.join(RAIZ, "engine", "contract"))
sys.path.insert(0, os.path.join(RAIZ, "engine", "events"))

import modelo               # noqa: E402
import estudio_resultados as er  # noqa: E402


def _fuente():
    return {"source_id": "src:test", "tipo": "DATA_PROVIDER", "publisher": None,
            "titulo": "fuente de prueba", "localizador": "https://example.invalid/x",
            "fecha_publicacion": None, "fecha_consulta": "2026-09-07",
            "accesible": True, "nota": None}


def _security(eid, nombre, asset_id=None):
    return {"entity_id": eid, "type": "security", "nombre": nombre, "status": "ACTIVE",
            "asset_id": asset_id, "aliases": [], "source_id": "src:test", "nota": None}


def _benchmark(eid, nombre, calendar="equity", origen="PUBLISHED_LEVEL",
               desde="1970-01-02", hasta=None, pit=True, version="v1"):
    return {"entity_id": eid, "type": "benchmark", "nombre": nombre, "status": "ACTIVE",
            "asset_id": None, "aliases": [], "source_id": "src:test", "nota": None,
            "benchmark": {"methodology_version": version, "composition_source": origen,
                          "point_in_time_capable": pit, "calendar": calendar,
                          "serie_desde": desde, "serie_hasta": hasta}}


def _rel(rid, subject, predicate, obj, role=None, desde="2026-01-01", hasta=None):
    r = {"relationship_id": rid, "subject": subject, "predicate": predicate,
         "object": obj, "polarity": "AFFIRMS", "nature": "ASSERTED",
         "status": "PROVISIONAL", "support_level": "MEDIO", "source_id": "src:test",
         "statement": "asignacion de prueba", "valid_from": desde, "valid_to": hasta,
         "last_verified": "2026-09-07", "verification_method": "test"}
    if role is not None:
        r["role"] = role
    return r


def _k(entidades, relaciones):
    return {"entities": entidades, "concepts": [], "relationships": relaciones,
            "sources": [_fuente()]}


class TestOntologia(unittest.TestCase):

    # --- 1 ---
    def test_un_indice_puede_ser_benchmark_sin_ser_asset(self):
        """Un indice no es un 'instrumento negociable' y no tiene sector,
        industria ni mercado de cotizacion. Existe en Knowledge con su
        propio tipo, y NO como un asset_id."""
        bm = _benchmark("bm:test-market", "Indice de prueba")
        self.assertEqual(modelo.validar(_k([bm], [])), [])
        self.assertEqual(bm["type"], "benchmark")
        self.assertIsNone(bm["asset_id"])
        self.assertNotEqual(bm["type"], "security")

    def test_un_benchmark_exige_metodologia_vigencia_y_origen(self):
        bm = _benchmark("bm:x", "X")
        del bm["benchmark"]["methodology_version"]
        self.assertTrue(any("methodology_version" in e or "incompleto" in e
                            for e in modelo.validar(_k([bm], []))))
        bm2 = _benchmark("bm:y", "Y")
        bm2["benchmark"]["serie_desde"] = None
        self.assertTrue(any("serie_desde" in e for e in modelo.validar(_k([bm2], []))))

    def test_una_referencia_construida_por_el_sistema_se_rechaza(self):
        """Mismo patron que D-10 con ESTIMATED: el token se declara para
        que salte. Un indice hecho con los activos que el sistema ya sigue
        esta seleccionado ex post por construccion."""
        bm = _benchmark("bm:casero", "Indice casero", origen="CONSTRUCTED")
        self.assertTrue(any("CONSTRUCTED" in e for e in modelo.validar(_k([bm], []))))

    def test_solo_un_benchmark_lleva_bloque_benchmark(self):
        sec = _security("sec:IBM", "IBM", "IBM")
        sec["benchmark"] = {"methodology_version": "v1"}
        self.assertTrue(any("solo una entidad de tipo benchmark" in e
                            for e in modelo.validar(_k([sec], []))))

    # --- 2 ---
    def test_un_asset_tiene_benchmark_mediante_knowledge(self):
        """Sin tabla nueva: la relacion de Knowledge ya lleva sujeto,
        objeto, vigencia, fuente y verificacion."""
        ents = [_security("sec:IBM", "IBM", "IBM"), _benchmark("bm:market-us", "Mercado EEUU")]
        rel = _rel("rel:t1", "sec:IBM", "BENCHMARKED_BY", "bm:market-us", role="MARKET")
        self.assertEqual(modelo.validar(_k(ents, [rel])), [])
        for campo in ("valid_from", "valid_to", "source_id", "nature", "status"):
            self.assertIn(campo, rel)

    def test_no_existe_tabla_de_asignacion_paralela(self):
        """La decision es que la asignacion vive en Knowledge (D-21). Si
        alguien crea una tabla aparte, este test lo dice."""
        for nombre in ("asset_benchmark_map.json", "benchmark_assignment.json",
                       "AssetBenchmarkAssignment.json"):
            self.assertFalse(os.path.exists(os.path.join(RAIZ, "knowledge", nombre)))
            self.assertFalse(os.path.exists(os.path.join(RAIZ, "data", nombre)))

    # --- 3 ---
    def test_una_comparison_reference_no_se_convierte_en_benchmark(self):
        """Un PEER produce PEER_RELATIVE_RETURN, nunca ABNORMAL_RETURN,
        y el validador no deja declararlo como benchmark formal."""
        ents = [_security("sec:ETH", "Ether", "ETH"), _security("sec:BTC", "Bitcoin", "BTC")]
        ok = _rel("rel:t2", "sec:ETH", "COMPARED_TO", "sec:BTC", role="PEER")
        self.assertEqual(modelo.validar(_k(ents, [ok])), [])
        mal = _rel("rel:t3", "sec:ETH", "BENCHMARKED_BY", "sec:BTC", role="PEER")
        errores = modelo.validar(_k(ents, [mal]))
        self.assertTrue(any("PEER no puede ser benchmark formal" in e for e in errores))

    def test_el_rol_tiene_que_ser_coherente_con_lo_que_el_objeto_es(self):
        ents = [_security("sec:IBM", "IBM", "IBM"), _security("sec:XOM", "XOM", "XOM"),
                _benchmark("bm:m", "Mercado")]
        mal = _rel("rel:t4", "sec:IBM", "COMPARED_TO", "sec:XOM", role="MARKET")
        self.assertTrue(any("role=MARKET exige un objeto de tipo benchmark" in e
                            for e in modelo.validar(_k(ents, [mal]))))
        mal2 = _rel("rel:t5", "sec:IBM", "COMPARED_TO", "bm:m", role="PEER")
        self.assertTrue(any("role=PEER exige un objeto de tipo security" in e
                            for e in modelo.validar(_k(ents, [mal2]))))

    def test_un_rol_declarado_pero_no_activo_se_rechaza(self):
        ents = [_security("sec:IBM", "IBM", "IBM"), _benchmark("bm:m", "Mercado")]
        r = _rel("rel:t6", "sec:IBM", "BENCHMARKED_BY", "bm:m", role="ASSET_CLASS")
        self.assertIn("ASSET_CLASS", modelo.ROLES_NO_ACTIVOS)
        self.assertTrue(any("NO activo" in e for e in modelo.validar(_k(ents, [r]))))

    # --- 4 ---
    def test_btc_no_puede_ser_benchmark_de_btc(self):
        """El retorno anormal seria cero por construccion."""
        ents = [_security("sec:BTC", "Bitcoin", "BTC")]
        r = _rel("rel:t7", "sec:BTC", "COMPARED_TO", "sec:BTC", role="PEER")
        self.assertTrue(any("no puede ser referencia de si mismo" in e
                            for e in modelo.validar(_k(ents, [r]))))

    # --- 7 ---
    def test_peer_relative_conserva_la_direccion(self):
        """ETH respecto a BTC y BTC respecto a ETH son relaciones
        DISTINTAS, con signo opuesto. El validador no las normaliza."""
        ents = [_security("sec:ETH", "Ether", "ETH"), _security("sec:BTC", "Bitcoin", "BTC")]
        ida = _rel("rel:t8", "sec:ETH", "COMPARED_TO", "sec:BTC", role="PEER")
        vuelta = _rel("rel:t9", "sec:BTC", "COMPARED_TO", "sec:ETH", role="PEER")
        self.assertEqual(modelo.validar(_k(ents, [ida, vuelta])), [])
        self.assertNotEqual((ida["subject"], ida["object"]), (vuelta["subject"], vuelta["object"]))

    def test_la_direccion_no_se_normaliza_en_la_unicidad(self):
        """La regla de unicidad es por (activo, rol, periodo) del SUJETO.
        Dos relaciones inversas no son un duplicado."""
        ents = [_security("sec:ETH", "Ether", "ETH"), _security("sec:BTC", "Bitcoin", "BTC")]
        ida = _rel("rel:ta", "sec:ETH", "COMPARED_TO", "sec:BTC", role="PEER")
        vuelta = _rel("rel:tb", "sec:BTC", "COMPARED_TO", "sec:ETH", role="PEER")
        self.assertEqual(modelo.validar(_k(ents, [ida, vuelta])), [])

    # --- 9 ---
    def test_no_se_puede_declarar_dos_benchmarks_del_mismo_rol_a_la_vez(self):
        """Defensa ESTRUCTURAL contra el selection bias: si un activo
        pudiera tener dos benchmarks MARKET vigentes, el calculo podria
        quedarse con el que diera el resultado mas interesante."""
        ents = [_security("sec:NVDA", "NVIDIA", "NVDA"),
                _benchmark("bm:a", "Indice A"), _benchmark("bm:b", "Indice B")]
        a = _rel("rel:tc", "sec:NVDA", "BENCHMARKED_BY", "bm:a", role="MARKET")
        b = _rel("rel:td", "sec:NVDA", "BENCHMARKED_BY", "bm:b", role="MARKET")
        self.assertTrue(any("exactamente uno" in e for e in modelo.validar(_k(ents, [a, b]))))

    def test_si_pueden_sucederse_en_el_tiempo(self):
        """Vigencias que no se solapan son un cambio de benchmark, no una
        eleccion entre dos."""
        ents = [_security("sec:NVDA", "NVIDIA", "NVDA"),
                _benchmark("bm:a", "Indice A"), _benchmark("bm:b", "Indice B")]
        a = _rel("rel:te", "sec:NVDA", "BENCHMARKED_BY", "bm:a", role="MARKET",
                 desde="2020-01-01", hasta="2023-12-31")
        b = _rel("rel:tf", "sec:NVDA", "BENCHMARKED_BY", "bm:b", role="MARKET",
                 desde="2024-01-01")
        self.assertEqual(modelo.validar(_k(ents, [a, b])), [])

    def test_el_calculo_no_puede_escribir_conocimiento(self):
        """D-04 hecho test: si el modulo que calcula pudiera crear la
        asignacion, podria elegirla despues de ver el resultado."""
        publicas = [n for n in dir(modelo) if not n.startswith("_")]
        prohibidas = [n for n in publicas
                      if any(v in n.lower() for v in ("escribir", "guardar", "write", "save",
                                                      "crear", "insert", "update", "delete"))]
        self.assertEqual(prohibidas, [])
        # y `benchmark_elegible` COMPRUEBA una asignacion, no la busca
        import inspect
        firma = inspect.signature(er.benchmark_elegible)
        self.assertIn("asignacion", firma.parameters)
        self.assertIn("entidad_benchmark", firma.parameters)


class TestElegibilidadDelBenchmark(unittest.TestCase):
    """Las cuatro condiciones de D-21 para que exista retorno anormal."""

    def setUp(self):
        self.bm = _benchmark("bm:market-us", "Mercado EEUU", calendar="equity",
                             desde="1970-01-02")
        self.asig = _rel("rel:x", "sec:IBM", "BENCHMARKED_BY", "bm:market-us",
                         role="MARKET", desde="1970-01-02")

    def test_caso_valido(self):
        ok, motivo = er.benchmark_elegible("2024-01-25", "equity", self.asig, self.bm)
        self.assertTrue(ok)
        self.assertIsNone(motivo)

    # --- 8 ---
    def test_calendario_incompatible_no_produce_retorno_anormal(self):
        """El 28,5% de las sesiones de BTC caen en fin de semana y las de
        IBM cero: un indice bursatil no puede medir un cripto ni queriendo."""
        ok, motivo = er.benchmark_elegible("2024-01-25", "crypto", self.asig, self.bm)
        self.assertFalse(ok)
        self.assertEqual(motivo, er.CALENDARIO_INCOMPATIBLE)

    def test_fuera_de_la_vigencia_de_la_asignacion(self):
        asig = dict(self.asig, valid_from="2020-01-01")
        ok, motivo = er.benchmark_elegible("2018-11-16", "equity", asig, self.bm)
        self.assertFalse(ok)
        self.assertEqual(motivo, er.FUERA_DE_VIGENCIA)

    def test_fuera_de_la_serie_del_benchmark(self):
        """XLK no existe antes de 1998-12-22: no es un fallo, es un
        valid_from."""
        bm = _benchmark("bm:sector", "Sector", desde="1998-12-22")
        asig = _rel("rel:y", "sec:IBM", "BENCHMARKED_BY", "bm:sector",
                    role="SECTOR", desde="1970-01-02")
        ok, motivo = er.benchmark_elegible("1990-05-10", "equity", asig, bm)
        self.assertFalse(ok)
        self.assertEqual(motivo, er.FUERA_DE_SERIE)

    def test_sin_metodologia_declarada(self):
        bm = _benchmark("bm:sin", "Sin metodologia", pit=False)
        ok, motivo = er.benchmark_elegible("2024-01-25", "equity",
                                           dict(self.asig, object="bm:sin"), bm)
        self.assertFalse(ok)
        self.assertEqual(motivo, er.SIN_METODOLOGIA)

    def test_una_comparison_reference_no_habilita_retorno_anormal(self):
        asig = _rel("rel:z", "sec:ETH", "COMPARED_TO", "sec:BTC", role="PEER")
        ok, motivo = er.benchmark_elegible("2024-01-25", "crypto", asig, self.bm)
        self.assertFalse(ok)
        self.assertEqual(motivo, er.NO_ES_BENCHMARK_FORMAL)

    def test_sin_asignacion_no_se_sustituye_por_nada(self):
        ok, motivo = er.benchmark_elegible("2024-01-25", "equity", None, None)
        self.assertFalse(ok)
        self.assertEqual(motivo, er.SIN_ASIGNACION)


class TestElPrimerBenchmarkDeclarado(unittest.TestCase):
    """REESCRITO (2026-09-07). Estos dos tests comprobaban que NO habia
    ningun benchmark declarado, y estaban puestos para fallar el dia que
    se declarase el primero. Ese dia es hoy: `bm:sp500`. La propiedad que
    sigue siendo cierta, y la que ahora importa, es que **solo** hay lo
    que se autorizo declarar -- ni Nasdaq, ni ETF sectoriales, ni cripto."""

    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()

    def test_solo_hay_el_benchmark_autorizado(self):
        bms = [e["entity_id"] for e in self.k["entities"] if e["type"] == "benchmark"]
        self.assertEqual(sorted(bms), ["bm:sp500"])

    def test_solo_hay_las_tres_asignaciones_autorizadas(self):
        refs = [r for r in self.k["relationships"]
                if r.get("predicate") in modelo.PREDICADOS_CON_ROL]
        self.assertEqual(len(refs), 3)
        self.assertEqual({r["predicate"] for r in refs}, {"BENCHMARKED_BY"})
        self.assertEqual({r["role"] for r in refs}, {"MARKET"})
        self.assertEqual(sorted(r["subject"] for r in refs),
                         ["sec:IBM.NYSE", "sec:NVDA.NASDAQ", "sec:XOM.NYSE"])

    def test_no_hay_comparison_references_todavia(self):
        """Nasdaq-100 y Nasdaq Composite quedan para la siguiente vertical."""
        self.assertEqual(
            [r for r in self.k["relationships"] if r.get("predicate") == "COMPARED_TO"], [])

    def test_ningun_activo_cripto_tiene_benchmark(self):
        cripto = {e["entity_id"] for e in self.k["entities"]
                  if e["type"] == "security" and e.get("asset_id") in
                  ("BTC", "ETH", "ADA", "SOL", "DOT", "XRP")}
        asignados = {r["subject"] for r in self.k["relationships"]
                     if r.get("predicate") == "BENCHMARKED_BY"}
        self.assertEqual(cripto & asignados, set())

    def test_el_conjunto_real_sigue_validando(self):
        self.assertEqual(modelo.validar(self.k), [])


if __name__ == "__main__":
    unittest.main()
