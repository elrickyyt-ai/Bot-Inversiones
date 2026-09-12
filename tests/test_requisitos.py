"""Evidence Gap -> Data Requirement -- P5D (2026-09-07).

Lo que se prueba no es que el resolutor devuelva estados. Es que NO
convierta una ausencia en una respuesta:

  - que una metrica no se convierta en la variable del mecanismo sin una
    declaracion explicita y justificada,
  - que un proxy no pueda hacerse pasar por medicion,
  - que la falta de dato no se degrade nunca a "no aplica",
  - y que una errata del catalogo no se presente como un hueco de datos
    (fallo real cometido al escribirlo: dominio "technical" en vez de
    "tecnico").
"""
import datetime
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
for _sub in ("contract", "causal", "knowledge", "requirements"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", _sub))

import cadencias  # noqa: E402
import caminos  # noqa: E402
import catalogo  # noqa: E402
import esquema_requisito as E  # noqa: E402
import mecanismos  # noqa: E402
import modelo  # noqa: E402
import resolver  # noqa: E402
import valoracion  # noqa: E402

HOY = datetime.date(2026, 9, 7)


from _parquet import requiere_parquet  # noqa: E402


def _k():
    return modelo.cargar()


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k = _k()
        cls.idx = resolver._indice_metricas(HOY, True)

    def r(self, variable, entity_id):
        req = resolver.resolver(variable, entity_id, self.k, self.idx)
        self.assertEqual(E.validar(req), [], req["requirement_id"])
        return req


class TestElVocabularioNoSeDuplica(unittest.TestCase):
    def test_los_cinco_estados_vienen_de_p1b_no_de_una_copia(self):
        """Misma pregunta ('existe el dato?') sobre un sujeto distinto.
        Si P5D redefiniera los estados, divergirian en silencio -- que es
        como `source_priority` acabo significando dos cosas en P0."""
        self.assertIs(E.DISPONIBILIDAD, cadencias.ESTADOS_COBERTURA)
        self.assertIs(E.FRESCURA, cadencias.ORDEN_FRESCURA)

    def test_cobertura_no_emite_ningun_estado_fuera_de_la_declaracion(self):
        import cobertura
        cob = cobertura.evaluar(hoy=HOY, con_history=False)
        emitidos = {d["cobertura"] for d in cob["por_dominio"]}
        self.assertTrue(emitidos)
        self.assertTrue(emitidos <= set(cadencias.ESTADOS_COBERTURA), emitidos)

    def test_los_dos_ejes_solo_comparten_unknown_y_es_deliberado(self):
        """P1b: un dominio puede estar disponible y caducado a la vez, y
        por eso son dos campos y no un enum.

        Escribi este test exigiendo conjuntos disjuntos, por analogia con
        las tres direcciones de P5B, y fallo. La analogia era mia, no del
        proyecto: alli MIXED y DIVERGENT son conceptos DISTINTOS y por eso
        no pueden compartir token. Aqui UNKNOWN significa lo mismo en los
        dos ejes -- 'no habia declaracion con la que comparar', literal en
        el docstring de cobertura.py -- asi que compartirlo es correcto y
        separarlo habria creado dos nombres para una idea. Lo que si tiene
        que seguir siendo cierto es que no compartan nada mas."""
        self.assertEqual(set(E.DISPONIBILIDAD) & set(E.FRESCURA), {"UNKNOWN"})


class TestElCatalogoEsDeclaracionNoInferencia(unittest.TestCase):
    def test_toda_candidata_declara_relacion_y_justificacion(self):
        for clave, cs in catalogo.OBSERVABLES.items():
            for c in cs:
                self.assertIn(c["relation"], E.RELACIONES, clave)
                self.assertTrue(c["justification"].strip(), clave)

    def test_todo_proxy_declara_su_confusor(self):
        """Un proxy sin decir en que se diferencia de la variable es una
        equivalencia disfrazada."""
        for clave, cs in catalogo.OBSERVABLES.items():
            for c in cs:
                if c["relation"] == "PROXY":
                    self.assertTrue(c.get("confounder", "").strip(), clave)

    def test_toda_candidata_apunta_a_una_metrica_que_el_contrato_emite(self):
        """El fallo real que motiva este test: la candidata de `price` se
        declaro sobre el dominio 'technical' y el contrato lo llama
        'tecnico'. El resolutor no fallaba: devolvia MISSING, presentando
        una errata del catalogo como un hueco de datos."""
        for dom, met in catalogo.dominios_metricas_declaradas():
            self.assertIsNotNone(
                cadencias.cadencia(dom, met),
                f"({dom}, {met}) no existe en cadencias.CADENCIAS")

    def test_las_variables_del_catalogo_son_las_de_p5b(self):
        self.assertEqual(set(catalogo.CONCEPTO_DE_VARIABLE),
                         set(mecanismos.VARIABLES_MECANISMO))
        for variable, _ in catalogo.OBSERVABLES:
            self.assertIn(variable, mecanismos.VARIABLES_MECANISMO)

    def test_ningun_concepto_inventado(self):
        """Hoy las cinco variables tienen concept_id null, y eso es una
        ausencia medida. Si algun dia se declara uno, tiene que existir
        de verdad en knowledge/concepts/."""
        declarados = {c["concept_id"] for c in _k()["concepts"]}
        for variable, cid in catalogo.CONCEPTO_DE_VARIABLE.items():
            if cid is not None:
                self.assertIn(cid, declarados, variable)


@requiere_parquet
class TestElProxyNoSeHacePasarPorMedicion(_Base):
    def test_revenue_no_es_demanda_pero_si_es_proxy_declarado(self):
        """El caso que el usuario puso como limite: `revenue` de NVIDIA
        NO debe convertirse automaticamente en `demand(org:nvidia)`."""
        req = self.r("demand", "org:nvidia")
        self.assertEqual(req["availability"], "PARTIAL")
        self.assertIn("ONLY_PROXY", req["reasons"])
        self.assertEqual(req["resolved_by"], "revenue_growth_yoy_pct")
        usada = next(c for c in req["candidates"] if c["presente"])
        self.assertEqual(usada["relation"], "PROXY")

    def test_el_confusor_llega_hasta_el_resultado(self):
        """No basta con declararlo en el catalogo: quien lea el requisito
        tiene que ver por que no es una medicion."""
        req = self.r("demand", "org:nvidia")
        self.assertTrue(any("precio x volumen" in u for u in req["unknowns"]))

    def test_solo_proxy_nunca_puede_llegar_a_available(self):
        """Misma regla que P5B aplica a un signo que depende de un
        supuesto: el validador la hace cumplir, no la buena voluntad."""
        req = self.r("demand", "org:nvidia")
        malo = dict(req, availability="AVAILABLE")
        self.assertTrue(any("solo con proxies" in x for x in E.validar(malo)))

    def test_una_medicion_directa_si_resuelve(self):
        """Contrapeso: si todo saliera PARTIAL o MISSING el test anterior
        no probaria nada."""
        req = self.r("price", "sec:BTC")
        self.assertEqual(req["availability"], "AVAILABLE")
        self.assertEqual(req["resolved_by"], "precio")
        self.assertEqual(req["candidates"][0]["relation"], "MEASURES")

    def test_disponible_y_caducado_a_la_vez(self):
        req = self.r("price", "sec:BTC")
        self.assertEqual(req["availability"], "AVAILABLE")
        self.assertIn(req["freshness"], cadencias.ORDEN_FRESCURA)


@requiere_parquet
class TestLaAusenciaNoSeConvierteEnRespuesta(_Base):
    def test_sin_dato_es_missing_nunca_not_applicable(self):
        """NO SOURCE != SOURCE SAYS IT DOES NOT EXIST."""
        req = self.r("capacity_utilization", "tech:cowos")
        self.assertEqual(req["availability"], "MISSING")
        self.assertNotEqual(req["availability"], "NOT_APPLICABLE")

    def test_not_applicable_exige_declaracion(self):
        req = self.r("capacity_utilization", "tech:cowos")
        malo = dict(req, availability="NOT_APPLICABLE")
        self.assertTrue(any("sin declaracion" in x for x in E.validar(malo)))

    def test_hoy_no_hay_nada_declarado_como_no_aplicable(self):
        """La tabla esta vacia a proposito: nada esta comprobado todavia.
        Su analoga de P1b (cadencias.NO_APLICA) SI tiene entradas, y esa
        diferencia es la que separa una comprobacion de una suposicion."""
        self.assertEqual(catalogo.NO_APLICA_VARIABLE, {})
        self.assertTrue(cadencias.NO_APLICA)

    def test_cada_missing_dice_cual_de_los_tres_motivos_es(self):
        """'No hay dato' tiene tres causas distintas y confundirlas
        manda a buscar en el sitio equivocado."""
        casos = {
            # ni observable ni metrica candidata
            ("capacity_utilization", "tech:cowos"): "NO_CANDIDATE_METRIC",
            # hay metrica candidata, pero la entidad no se observa aqui
            ("demand", "org:tsmc"): "NO_OBSERVABLE",
            # se observa la entidad, pero nadie declaro metrica
            ("inventory", "org:nvidia"): "NO_CANDIDATE_METRIC",
        }
        for (v, e), motivo in casos.items():
            req = self.r(v, e)
            self.assertEqual(req["availability"], "MISSING", (v, e))
            self.assertIn(motivo, req["reasons"], (v, e))
            self.assertTrue(req["unknowns"], (v, e))

    def test_una_entidad_que_no_existe_es_unknown_no_missing(self):
        """UNKNOWN es 'no habia con que comparar'. Decir MISSING seria
        afirmar que buscamos el dato de algo que ni existe."""
        req = self.r("demand", "org:esta-no-existe")
        self.assertEqual(req["availability"], "UNKNOWN")
        self.assertIn("ENTITY_NOT_DECLARED", req["reasons"])


@requiere_parquet
class TestElPuenteConP5B(_Base):
    """La cadena completa sobre el Knowledge real de P5C."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        evento = {"event_id": "ev4:p5d", "primary_entity": "org:nvidia",
                  "action": "demand_change", "direction": "UP"}
        cs = caminos.descubrir(evento["event_id"], "org:nvidia", cls.k, HOY, 2)
        vals = [valoracion.valorar(evento, c, [], cls.k, modelo.vigente, HOY) for c in cs]
        cls.reqs = resolver.resolver_valoraciones(vals, cls.k, HOY, True)
        cls.por_id = {r["requirement_id"]: r for r in cls.reqs}

    def test_todo_requisito_de_p5b_queda_resuelto_a_un_estado(self):
        self.assertTrue(self.reqs)
        for r in self.reqs:
            self.assertEqual(E.validar(r), [], r["requirement_id"])
            self.assertIn(r["availability"], E.DISPONIBILIDAD)

    def test_los_dos_requisitos_de_la_cadena_de_p5c_estan(self):
        self.assertIn("req:demand:org:nvidia", self.por_id)
        self.assertIn("req:capacity_utilization:tech:cowos", self.por_id)

    def test_el_mismo_requisito_se_resuelve_una_vez_y_dice_a_quien_bloquea(self):
        """Aparece en decenas de caminos; resolverlo una vez por camino
        seria ruido, y perder a quien bloquea seria perder el motivo."""
        ids = [r["requirement_id"] for r in self.reqs]
        self.assertEqual(len(ids), len(set(ids)))
        r = self.por_id["req:capacity_utilization:tech:cowos"]
        self.assertGreater(len(r["blocking_for"]), 1)
        self.assertTrue({b["mechanism"] for b in r["blocking_for"]}
                        <= set(mecanismos.MECANISMOS) | {mecanismos.NO_MECHANISM})

    def test_el_cuello_de_botella_queda_nombrado(self):
        """El resultado que justifica la fase: lo que bloquea a P6 no es
        el algoritmo de impacto, es que la utilizacion de capacidad de
        CoWoS no la publica ninguna fuente que este sistema tenga."""
        r = self.por_id["req:capacity_utilization:tech:cowos"]
        self.assertEqual(r["availability"], "MISSING")
        self.assertIsNone(r["observable_asset_id"])
        self.assertIn("NO_OBSERVABLE", r["reasons"])

    def test_no_se_toca_nada_al_resolver(self):
        import hashlib
        def huella():
            h = hashlib.sha256()
            for sub in ("knowledge", "engine/causal", "engine/requirements",
                        "data/incoming"):
                for raiz, _, fs in sorted(os.walk(os.path.join(RAIZ, sub))):
                    if "__pycache__" in raiz:
                        continue
                    for f in sorted(fs):
                        if f.endswith((".json", ".csv", ".py")):
                            with open(os.path.join(raiz, f), "rb") as fh:
                                h.update(fh.read())
            return h.hexdigest()
        antes = huella()
        resolver.resolver("demand", "org:nvidia", self.k, self.idx)
        self.assertEqual(antes, huella())


class TestInvariantesEpistemicos(unittest.TestCase):
    """La regla transversal del proyecto, comprobada donde vive cada una.

        NO RELATION  != RELATION DENIES
        NO EVIDENCE  != EVIDENCE OF NO EFFECT
        NO SOURCE    != SOURCE SAYS IT DOES NOT EXIST

    Son la misma regla en tres capas. Este bloque existe para que se
    rompan juntas si alguien afloja una.
    """

    def test_no_relacion_no_es_relacion_negada(self):
        """P2: DENIES exige fuente igual que AFFIRMS. Una ausencia de
        fila no puede producir una negacion."""
        k = _k()
        negaciones = [r for r in k["relationships"] if r["polarity"] == "DENIES"]
        self.assertTrue(negaciones)
        for r in negaciones:
            self.assertTrue(r["source_id"], r["relationship_id"])
            self.assertTrue(r["verification_method"], r["relationship_id"])

    def test_no_evidencia_no_es_evidencia_de_no_efecto(self):
        """P5B: UNKNOWN y NEUTRAL son valores distintos, y la falta de
        medicion produce el primero. Colapsarlos afirmaria que no hay
        efecto cuando lo que no hay es medida."""
        self.assertIn("UNKNOWN", mecanismos.DIRECCIONES)
        self.assertIn("NEUTRAL", mecanismos.DIRECCIONES)
        k = _k()
        evento = {"event_id": "ev4:inv", "primary_entity": "org:nvidia",
                  "action": "demand_change", "direction": "UP"}
        cs = caminos.descubrir(evento["event_id"], "org:nvidia", k, HOY, 2)
        camino = next(c for c in cs
                      if [a["relationship_id"] for a in c["edges"]] == ["rel:0046", "rel:0048"])
        a = valoracion.valorar(evento, camino, [], k, modelo.vigente, HOY)
        self.assertEqual(a["overall_direction"], "UNKNOWN")
        for t in a["segments"]:
            self.assertNotEqual(t["economic_direction"], "NEUTRAL")

    def test_no_fuente_no_es_fuente_que_dice_que_no_existe(self):
        """P5D: MISSING y NOT_APPLICABLE son estados distintos y el
        segundo exige declaracion."""
        self.assertIn("MISSING", E.DISPONIBILIDAD)
        self.assertIn("NOT_APPLICABLE", E.DISPONIBILIDAD)
        self.assertIn("DECLARED_NOT_APPLICABLE", E.MOTIVOS)

    def test_unknown_nunca_es_permisivo_en_ninguna_de_las_tres_capas(self):
        """En los tres ejes, 'no se sabe' es el PEOR valor, no uno
        intermedio. En frescura esta explicito en el orden; en las otras
        dos, en que ningun resultado se da por bueno con UNKNOWN."""
        self.assertEqual(max(cadencias.ORDEN_FRESCURA.values()),
                         cadencias.ORDEN_FRESCURA["UNKNOWN"])
        self.assertIn("UNKNOWN", mecanismos.SOPORTES)
        self.assertIn("UNKNOWN", E.DISPONIBILIDAD)


if __name__ == "__main__":
    unittest.main()
