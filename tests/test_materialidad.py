"""Materiality -- P6.1 (2026-09-07).

    Evidence (de entidad) + Knowledge (la relacion) -> Materiality (derivada)

El test central es el de la vigencia: el 20-F publica tres cotas y solo
una es aplicable. Y no se elige por ser la menor, ni la mayor, ni la mas
reciente, sino por ser la unica cuyo periodo intersecta con la vigencia
de la relacion causal. Hay una fixture sintetica donde la aplicable es
justo la MAYOR y la MAS ANTIGUA, para que ningun `min` ni `max`
accidental pueda pasar el test por casualidad.
"""
import copy
import datetime
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
for _sub in ("causal", "impact", "knowledge"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", _sub))

import esquema_impacto as EI  # noqa: E402
import esquema_materialidad as EM  # noqa: E402
import materialidad as MT  # noqa: E402
import modelo  # noqa: E402
import observaciones as OBS  # noqa: E402
import requisitos_magnitud as RM  # noqa: E402

HOY = datetime.date(2026, 9, 7)
SRE = "SUPPLIER_REVENUE_EXPOSURE"


def _k():
    return modelo.cargar()


def _resolver(sujeto="org:tsmc", contraparte="org:nvidia", k=None, basis=SRE):
    m = MT.resolver_materialidad(basis, sujeto, contraparte, k or _k(), HOY)
    assert EM.validar(m) == [], EM.validar(m)
    return m


class TestElVocabulario(unittest.TestCase):
    def test_point_no_se_introduce_porque_ya_existe_known(self):
        """El diseno pedia POINT/BOUNDED/UNKNOWN/NOT_APPLICABLE. `KNOWN`
        ya significa exactamente lo que POINT: anadirlo serian dos nombres
        para una idea, el error espejo del invariante. Magnitud y
        materialidad comparten el MISMO vocabulario."""
        self.assertIs(EM.ESTADOS, EI.ESTADOS_PIEZA)
        self.assertNotIn("POINT", EM.ESTADOS)
        self.assertIn("KNOWN", EM.ESTADOS)
        self.assertIn("BOUNDED", EM.ESTADOS)

    def test_bound_no_coexiste_con_bounded(self):
        self.assertNotIn("BOUND", EM.ESTADOS)

    def test_solo_cuatro_bases_y_ninguna_redundante(self):
        """DEMAND_SHARE no entra: ningun mecanismo la pide.
        CUSTOMER_REVENUE_SHARE tampoco: es la MISMA magnitud que
        SUPPLIER_REVENUE_EXPOSURE vista del otro lado."""
        self.assertEqual(set(EM.BASES), {"SUPPLIER_REVENUE_EXPOSURE", "COST_SHARE",
                                         "VOLUME_SHARE", "CAPACITY_SHARE"})
        self.assertNotIn("DEMAND_SHARE", EM.BASES)
        self.assertNotIn("CUSTOMER_REVENUE_SHARE", EM.BASES)

    def test_cada_mecanismo_que_pide_materialidad_declara_cual(self):
        """Cierra el defecto medido en P6: cuatro significados entrando
        por el mismo hueco."""
        for mec, ent in RM.ENTRADAS.items():
            decl = RM.basis_de(mec)
            if ent["materialidad"]:
                self.assertIsNotNone(decl, mec)
                self.assertIn(decl[0], EM.BASES, mec)
                self.assertIn(decl[1], ("from", "to"), mec)
            else:
                self.assertIsNone(decl, mec)

    def test_toda_base_declara_sujeto_y_poblacion(self):
        for b in EM.BASES:
            self.assertTrue(EM.BASES[b]["sujeto"])
            self.assertIn(b, MT.POBLACION, b)


class TestLaDerivacionReal(unittest.TestCase):
    """TSMC ← NVIDIA sobre el Knowledge real de P5C."""

    def test_da_una_cota_no_un_valor(self):
        m = _resolver()
        self.assertEqual(m["status"], "BOUNDED")
        self.assertEqual(m["upper_bound"], 19.0)
        self.assertIsNone(m["value"], "una cota no puntualiza")

    def test_no_atribuye_el_19_a_nvidia(self):
        """La fuente no nombra al cliente. Que NVIDIA sea ese cliente NO
        se afirma, y el resultado lo dice con todas las letras."""
        m = _resolver()
        self.assertTrue(any("NO se afirma" in u for u in m["unknowns"]))

    def test_es_auditable_hasta_la_observacion_y_la_relacion(self):
        m = _resolver()
        self.assertEqual(m["evidence_ids"], ["obs:tsmc:largest_customer:2025"])
        self.assertEqual(m["applied_via"], "rel:0046")
        self.assertEqual(m["observed_on"], "org:tsmc")
        self.assertEqual(m["observed_period"], ["2025-01-01", "2025-12-31"])
        self.assertEqual(m["scope"], "POPULATION_BOUND")

    def test_la_observacion_es_literal_del_documento(self):
        o = next(x for x in OBS.OBSERVACIONES if x["observation_id"].endswith("2025"))
        self.assertIn("19%", o["literal"])
        self.assertEqual(o["source_id"], "src:tsmc-20f-fy2025")
        fuentes = {s["source_id"] for s in _k()["sources"]}
        for x in OBS.OBSERVACIONES:
            self.assertIn(x["source_id"], fuentes, x["observation_id"])


class TestLaVigenciaTemporal(unittest.TestCase):
    """EL TEST CENTRAL. El 20-F da 25% (2023), 22% (2024) y 19% (2025);
    rel:0046 solo esta atestiguada desde 2025-01-27."""

    def test_solo_la_cota_del_periodo_vigente_se_aplica(self):
        m = _resolver()
        self.assertEqual(m["upper_bound"], 19.0)
        self.assertNotIn(m["upper_bound"], (25.0, 22.0))

    def test_las_otras_se_descartan_por_vigencia_no_por_ser_peores(self):
        m = _resolver()
        self.assertIn("RELATIONSHIP_NOT_VALID_IN_PERIOD", str(m["unknowns"]))
        self.assertTrue(any("no por ser peores" in u for u in m["unknowns"]))

    def test_no_se_elige_por_min_ni_por_max_ni_por_la_mas_reciente(self):
        """Sobre el Knowledge real, 19% es a la vez la menor y la mas
        reciente, asi que un `min` o un `latest` accidental pasarian.
        Esta fixture invierte el caso: la relacion vale SOLO en 2023, y
        entonces la aplicable es la MAYOR (25%) y la MAS ANTIGUA."""
        k = copy.deepcopy(_k())
        for r in k["relationships"]:
            if r["relationship_id"] == "rel:0046":
                r["valid_from"], r["valid_to"] = "2023-01-01", "2023-12-31"
        m = _resolver(k=k)
        self.assertEqual(m["status"], "BOUNDED")
        self.assertEqual(m["upper_bound"], 25.0, "se eligio por aplicabilidad, no por valor")
        self.assertEqual(m["evidence_ids"], ["obs:tsmc:largest_customer:2023"])

    def test_si_ninguna_intersecta_no_hay_cota(self):
        k = copy.deepcopy(_k())
        for r in k["relationships"]:
            if r["relationship_id"] == "rel:0046":
                r["valid_from"], r["valid_to"] = "2019-01-01", "2019-12-31"
        m = _resolver(k=k)
        self.assertEqual(m["status"], "UNKNOWN")
        self.assertIn("RELATIONSHIP_NOT_VALID_IN_PERIOD", m["reasons"])


class TestLosDosMotivosSeDistinguen(unittest.TestCase):
    """Una evidencia valida pero inaplicable no puede acabar
    indistinguible de un hueco de datos: mandaria a buscar una fuente que
    el sistema ya tiene."""

    def test_evidencia_que_existe_pero_no_alcanza(self):
        m = _resolver(contraparte="org:ibm")
        self.assertEqual(m["status"], "UNKNOWN")
        self.assertIn("EVIDENCE_EXISTS_BUT_NOT_APPLICABLE", m["reasons"])
        self.assertNotIn("NO_SUPPORTING_EVIDENCE", m["reasons"])
        self.assertIn("NO_RELATIONSHIP", m["reasons"])

    def test_ausencia_real_de_evidencia(self):
        m = _resolver(basis="COST_SHARE", sujeto="org:nvidia", contraparte="tech:cowos")
        self.assertEqual(m["status"], "UNKNOWN")
        self.assertIn("NO_SUPPORTING_EVIDENCE", m["reasons"])
        self.assertNotIn("EVIDENCE_EXISTS_BUT_NOT_APPLICABLE", m["reasons"])

    def test_los_dos_dan_unknown_pero_no_son_el_mismo_unknown(self):
        a = _resolver(contraparte="org:ibm")
        b = _resolver(basis="COST_SHARE", sujeto="org:nvidia", contraparte="tech:cowos")
        self.assertEqual(a["status"], b["status"])
        self.assertNotEqual(set(a["reasons"]), set(b["reasons"]))


class TestElAlcanceDeLaPoblacion(unittest.TestCase):
    """La cota de TSMC no dice nada sobre un proveedor de NVIDIA."""

    def _con_samsung(self):
        k = copy.deepcopy(_k())
        k["entities"].append({"entity_id": "org:samsung", "type": "organization",
                              "nombre": "Samsung Electronics", "status": "ACTIVE",
                              "asset_id": None, "aliases": [],
                              "source_id": "src:nvda-10k-fy2026"})
        k["relationships"].append({
            "relationship_id": "rel:t01", "subject": "org:samsung", "predicate": "SUPPLIES",
            "object": "org:nvidia", "polarity": "AFFIRMS", "nature": "STRUCTURAL",
            "status": "VERIFIED", "support_level": "ALTO", "source_id": "src:nvda-10k-fy2026",
            "statement": "misma frase del 10-K", "valid_from": "2025-01-27", "valid_to": None,
            "last_verified": "2026-09-07", "verification_method": "fixture"})
        return k

    def test_la_cota_de_tsmc_no_alcanza_a_samsung(self):
        """Samsung suministra a NVIDIA, pero no es cliente de TSMC: la
        poblacion acotada es la de los clientes de TSMC."""
        m = _resolver(sujeto="org:tsmc", contraparte="org:samsung", k=self._con_samsung())
        self.assertEqual(m["status"], "UNKNOWN")
        self.assertIn("NO_RELATIONSHIP", m["reasons"])
        self.assertIsNone(m["upper_bound"])

    def test_y_nvidia_sigue_acotada_en_el_mismo_grafo(self):
        """Contrapeso: si el test anterior pasara porque nada se acota
        nunca, no probaria nada."""
        m = _resolver(k=self._con_samsung())
        self.assertEqual(m["upper_bound"], 19.0)

    def test_el_sentido_de_la_relacion_importa(self):
        """`org:nvidia SUPPLIES org:tsmc` no existe: preguntar por la
        exposicion de NVIDIA a TSMC no puede reutilizar la cota."""
        m = _resolver(sujeto="org:nvidia", contraparte="org:tsmc")
        self.assertEqual(m["status"], "UNKNOWN")
        self.assertIn("NO_SUPPORTING_EVIDENCE", m["reasons"])


class TestLaCotaTrivial(unittest.TestCase):
    def test_una_cota_del_100_no_se_emite(self):
        """UNKNOWN no es 0% ni <=100%. Un tope aritmetico parece
        informacion sin serlo, y eso lo hace peor que un UNKNOWN."""
        orig = OBS.OBSERVACIONES
        try:
            OBS.OBSERVACIONES = [dict(orig[0], upper_bound=100.0,
                                      observation_id="obs:trivial")]
            m = _resolver()
            self.assertEqual(m["status"], "UNKNOWN")
            self.assertIn("TRIVIAL_BOUND_DISCARDED", m["reasons"])
        finally:
            OBS.OBSERVACIONES = orig

    def test_el_validador_tambien_la_rechaza(self):
        m = _resolver()
        malo = dict(m, upper_bound=100.0)
        self.assertTrue(any("no estricta" in x for x in EM.validar(malo)))


class TestElValidador(unittest.TestCase):
    def test_bounded_sin_observacion_ni_relacion_no_es_derivable(self):
        m = _resolver()
        for campo in ("evidence_ids", "applied_via"):
            malo = dict(m)
            malo[campo] = [] if campo == "evidence_ids" else None
            self.assertTrue(EM.validar(malo), campo)

    def test_bounded_con_value_es_contradictorio(self):
        malo = dict(_resolver(), value=19.0)
        self.assertTrue(any("no seria una cota" in x for x in EM.validar(malo)))

    def test_sin_resolver_no_lleva_numeros(self):
        m = _resolver(contraparte="org:ibm")
        self.assertIsNone(m["value"])
        self.assertIsNone(m["upper_bound"])
        malo = dict(m, upper_bound=19.0)
        self.assertTrue(any("va a null" in x for x in EM.validar(malo)))

    def test_la_materialidad_no_se_almacena(self):
        """No hay ningun fichero de materialidades ni funcion de
        escritura: si se guardara, en dos meses nadie sabria si el 19% es
        lo que dijo el 20-F o lo que dedujo el sistema."""
        import inspect
        src = inspect.getsource(MT)
        self.assertNotIn("open(", src)
        self.assertNotIn("json.dump", src)


if __name__ == "__main__":
    unittest.main()
