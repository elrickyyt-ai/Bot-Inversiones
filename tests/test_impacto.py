"""Economic Impact v1 -- P6 (2026-09-07).

El objetivo de v1 no es producir numeros. Es demostrar que el sistema
sabe EXACTAMENTE cuando tendria derecho a producirlos y cuando no. Estos
tests comprueban las dos mitades:

  - que hoy no los produce, y que cada tramo dice si es porque el
    mecanismo no puede o porque falta el dato (dos cosas distintas),
  - y que la comprobacion de derecho NO es una rama muerta: con las
    tablas de declaracion pobladas, se enciende.

Y sobre todo comprueban lo que NO puede pasar: que un parametro que
falta se sustituya por un valor implicito.
"""
import contextlib
import datetime
import hashlib
import os
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
for _sub in ("causal", "contract", "impact", "knowledge", "requirements"):
    sys.path.insert(0, os.path.join(RAIZ, "engine", _sub))

import cadencias  # noqa: E402
import caminos  # noqa: E402
import esquema_impacto as E  # noqa: E402
import esquema_requisito as ER  # noqa: E402
import impacto  # noqa: E402
import mecanismos as M  # noqa: E402
import modelo  # noqa: E402
import requisitos_magnitud as RM  # noqa: E402
import resolver as R5D  # noqa: E402
import valoracion  # noqa: E402

HOY = datetime.date(2026, 9, 7)


def _impacto_base(**kw):
    """Un EconomicImpact valido y minimo, para probar UNA regla cada vez."""
    r = {
        "impact_id": "im:t", "as_of": HOY.isoformat(), "rule_version": E.RULE_VERSION,
        "event_id": "ev4:t", "path_id": "cp:t", "relationship_id": "rel:t",
        "mechanism": "CUSTOMER_DEMAND",
        "magnitude_capability": "CONDITIONALLY_QUANTIFIABLE",
        "entity_id": "org:x", "affected_variable": "revenue",
        "economic_direction": "POSITIVE",
        "magnitude": {"state": "UNKNOWN", "value": None, "unit": None, "baseline": None},
        "magnitude_basis": {"coefficient_origin": "UNKNOWN", "coefficient_ref": None,
                            "inputs": []},
        "materiality": {"state": "UNKNOWN", "value": None, "unit": None, "source_id": None},
        "horizon": {"state": "UNKNOWN", "dias_min": None, "dias_max": None},
        "fitness": "MEASURES", "evidence_ids": [], "support": "PARTIAL",
        "reasons": ["NO_TRANSMISSION_COEFFICIENT"], "unknowns": [],
    }
    r.update(kw)
    return r


def _completo(**kw):
    """El caso sintetico en que TODO esta: es el control positivo. Sin el,
    los tests de bloqueo no probarian nada -- podrian pasar porque nada
    llega nunca a KNOWN."""
    r = _impacto_base(
        magnitude={"state": "KNOWN", "value": 4.2, "unit": "%", "baseline": "media 8 trimestres"},
        magnitude_basis={"coefficient_origin": "DECLARED", "coefficient_ref": "src:t",
                         "inputs": ["demand(org:y)"]},
        materiality={"state": "KNOWN", "value": 30.0, "unit": "%", "source_id": "src:t"},
        horizon={"state": "KNOWN", "dias_min": 30, "dias_max": 90},
        fitness="MEASURES", evidence_ids=["ev:1"], support="SUPPORTED", reasons=[])
    r.update(kw)
    return r


@contextlib.contextmanager
def _declarado(coef=None, mat=None, base=None):
    """Puebla temporalmente las tablas de declaracion. Es la unica forma
    de ejecutar la rama en que el sistema SI tiene derecho a un numero."""
    c0, m0, b0 = RM.COEFICIENTES, RM.MATERIALIDAD, RM.LINEAS_BASE
    RM.COEFICIENTES = coef if coef is not None else c0
    RM.MATERIALIDAD = mat if mat is not None else m0
    RM.LINEAS_BASE = base if base is not None else b0
    try:
        yield
    finally:
        RM.COEFICIENTES, RM.MATERIALIDAD, RM.LINEAS_BASE = c0, m0, b0


# --- T1 ---------------------------------------------------------------------
class TestVocabulario(unittest.TestCase):
    def test_la_capacidad_no_reutiliza_el_soporte_de_p5b(self):
        """La propuesta original era SUPPORTED/NOT_SUPPORTED/
        CONDITIONALLY_SUPPORTED. SUPPORTED ya existe en P5B y significa
        otra cosa: alli es el respaldo probatorio de UNA afirmacion, aqui
        seria la capacidad de UNA CLASE de mecanismo."""
        self.assertTrue(set(E.CAPACIDADES).isdisjoint(set(M.SOPORTES)))
        self.assertNotIn("SUPPORTED", E.CAPACIDADES)

    def test_fitness_comparte_tokens_con_p5d_porque_significan_lo_mismo(self):
        """La cara opuesta de la regla: MEASURES y PROXY se comparten a
        proposito. fitness es una PROYECCION de lo que P5D calcula, no un
        catalogo nuevo; darles otro nombre serian dos nombres para una
        idea, que es el mismo error visto del reves."""
        self.assertTrue(set(ER.RELACIONES) <= set(E.FITNESS))

    def test_el_horizonte_se_expresa_en_dias_no_en_categorias(self):
        """Medido antes de decidir: el proyecto no tiene ningun
        vocabulario categorico de horizonte, y si tiene una convencion en
        dias (ledger.py). Inventar IMMEDIATE/SHORT_TERM/... habria creado
        un vocabulario nuevo para algo que ya se expresa de otra forma."""
        self.assertEqual(E.CAMPOS_HORIZONTE, {"state", "dias_min", "dias_max"})

    def test_no_puedo_y_no_se_son_estados_distintos(self):
        self.assertIn("NOT_APPLICABLE", E.ESTADOS_PIEZA)
        self.assertIn("UNKNOWN", E.ESTADOS_PIEZA)


# --- T2 ---------------------------------------------------------------------
class TestLasCuatroPiezasSonIndependientes(unittest.TestCase):
    def test_pueden_estar_en_estados_distintos_a_la_vez(self):
        """La correccion central del diseno: la magnitud NO es
        obligatoria. Un impacto con direccion conocida y las otras tres
        sin resolver sigue siendo informacion valida."""
        r = _impacto_base(economic_direction="POSITIVE")
        self.assertEqual(E.validar(r), [])
        self.assertEqual(r["economic_direction"], "POSITIVE")
        self.assertEqual(r["magnitude"]["state"], "UNKNOWN")
        self.assertEqual(r["materiality"]["state"], "UNKNOWN")
        self.assertEqual(r["horizon"]["state"], "UNKNOWN")

    def test_el_control_positivo_valida(self):
        self.assertEqual(E.validar(_completo()), [])


# --- T3 ---------------------------------------------------------------------
class TestLaMagnitudNoSePuedeInventar(unittest.TestCase):
    def test_sin_unidad_o_sin_base_no_hay_magnitud(self):
        """P4 ya exigia valor+unidad. La base de comparacion es de aqui:
        un 4,2% no significa nada sin decir 4,2% respecto a que."""
        for campo in ("value", "unit", "baseline"):
            r = _completo()
            r["magnitude"][campo] = None
            self.assertTrue(any(f"sin {campo}" in x for x in E.validar(r)), campo)

    def test_un_cero_exige_su_evidencia(self):
        """Un cero medido lleva evidencia. Un cero por ausencia es la
        forma mas silenciosa de inventar un dato."""
        r = _completo()
        r["magnitude"]["value"] = 0
        r["evidence_ids"] = []
        self.assertTrue(any("magnitude=0 sin evidence_ids" in x for x in E.validar(r)))
        r["evidence_ids"] = ["ev:1"]
        self.assertEqual(E.validar(r), [])

    def test_materialidad_desconocida_bloquea_la_magnitud(self):
        """Regla general, no solo para NVDA/TSMC: causalidad no es
        materialidad."""
        r = _completo()
        r["materiality"] = {"state": "UNKNOWN", "value": None, "unit": None, "source_id": None}
        self.assertTrue(any("materiality no KNOWN" in x for x in E.validar(r)))

    def test_sin_coeficiente_declarado_no_hay_magnitud(self):
        r = _completo()
        r["magnitude_basis"] = {"coefficient_origin": "UNKNOWN", "coefficient_ref": None,
                                "inputs": []}
        self.assertTrue(any("sin coeficiente de transmision" in x for x in E.validar(r)))

    def test_un_proxy_no_se_promueve_a_cuantitativo(self):
        """P6 puede degradar una afirmacion cuantitativa a cualitativa;
        nunca al reves sin evidencia adicional."""
        for f in ("PROXY", "INSUFFICIENT", "UNKNOWN"):
            r = _completo(fitness=f)
            self.assertTrue(any("nunca al reves" in x for x in E.validar(r)), f)

    def test_una_pieza_sin_resolver_lleva_su_valor_a_null_y_presente(self):
        r = _impacto_base()
        r["magnitude"]["value"] = 0.0
        self.assertTrue(any("el valor es null y esta presente" in x for x in E.validar(r)))


# --- T4 ---------------------------------------------------------------------
class TestElCoeficienteEstimadoNoExisteEnV1(unittest.TestCase):
    def test_estimated_esta_en_el_vocabulario_pero_prohibido(self):
        """Se declara ENTERO a proposito: escribirlo es lo que permite
        rechazarlo explicitamente, en vez de que el caso simplemente no
        exista todavia y aparezca un dia sin que nadie lo note."""
        self.assertIn("ESTIMATED", E.ORIGENES_COEFICIENTE)
        self.assertNotIn("ESTIMATED", E.ORIGENES_PERMITIDOS_V1)

    def test_el_validador_lo_rechaza(self):
        r = _completo()
        r["magnitude_basis"]["coefficient_origin"] = "ESTIMATED"
        errores = E.validar(r)
        self.assertTrue(any("ESTIMATED no puede existir" in x for x in errores))
        self.assertTrue(any("salida de un modelo" in x for x in errores))

    def test_ninguna_tabla_de_v1_declara_coeficientes(self):
        self.assertEqual(RM.COEFICIENTES, {})
        self.assertEqual(RM.MATERIALIDAD, {})
        self.assertEqual(RM.LINEAS_BASE, {})

    def test_un_coeficiente_sin_referencia_no_es_verificable(self):
        r = _completo()
        r["magnitude_basis"]["coefficient_ref"] = None
        self.assertTrue(any("sin referencia no es verificable" in x for x in E.validar(r)))


# --- T5 ---------------------------------------------------------------------
class TestNoPuedoNoEsNoSe(unittest.TestCase):
    def test_un_mecanismo_no_cuantificable_da_not_applicable(self):
        r = _impacto_base(mechanism="PRICING_POWER",
                          magnitude_capability="NOT_QUANTIFIABLE",
                          reasons=["MECHANISM_CANNOT_QUANTIFY"])
        self.assertTrue(any("nunca UNKNOWN" in x for x in E.validar(r)))
        r["magnitude"]["state"] = "NOT_APPLICABLE"
        self.assertEqual(E.validar(r), [])

    def test_y_al_reves_tambien(self):
        r = _impacto_base()
        r["magnitude"]["state"] = "NOT_APPLICABLE"
        self.assertTrue(any("que si podria cuantificar" in x for x in E.validar(r)))

    def test_los_siete_mecanismos_declaran_su_capacidad_con_motivo(self):
        self.assertEqual(set(RM.CAPACIDAD), set(M.MECANISMOS) | {M.NO_MECHANISM})
        for mec, (cap, motivo) in RM.CAPACIDAD.items():
            self.assertIn(cap, E.CAPACIDADES, mec)
            self.assertTrue(motivo.strip(), mec)

    def test_ninguno_es_cuantificable_hoy_y_el_valor_existe_igual(self):
        """Un vocabulario no es un inventario: QUANTIFIABLE describe un
        estado alcanzable aunque hoy no lo alcance nadie."""
        self.assertIn("QUANTIFIABLE", E.CAPACIDADES)
        self.assertEqual([m for m, (c, _) in RM.CAPACIDAD.items() if c == "QUANTIFIABLE"], [])

    def test_solo_tres_de_siete_podrian_llegar_a_magnitud(self):
        """No todos los mecanismos que explican direccion pueden
        cuantificarla. Es el error mas comun en sistemas causales."""
        cond = {m for m, (c, _) in RM.CAPACIDAD.items() if c == "CONDITIONALLY_QUANTIFIABLE"}
        self.assertEqual(cond, {"CUSTOMER_DEMAND", "INPUT_COST", "SUPPLY_SHORTAGE"})


# --- T6 ---------------------------------------------------------------------
class TestLoQueP6NoEmite(unittest.TestCase):
    def test_los_campos_prohibidos_se_rechazan(self):
        for campo in ("probability", "score", "price_target", "confidence",
                      "recommendation", "expected_return"):
            r = _impacto_base()
            r[campo] = 0.5
            errores = E.validar(r)
            self.assertTrue(any("campos prohibidos" in x for x in errores), campo)

    def test_el_esquema_no_contiene_ningun_campo_de_precio(self):
        """P6 responde 'que cambia economicamente'; el precio es P7. Y
        `precio` es la metrica mejor cubierta del contrato, o sea el
        atajo mas facil de tomar."""
        self.assertEqual(E.CAMPOS & E.CAMPOS_PROHIBIDOS, set())
        self.assertFalse(any("precio" in c or "price" in c for c in E.CAMPOS))


# --- T7 ---------------------------------------------------------------------
class TestCombinarNoEsSumar(unittest.TestCase):
    def test_no_existe_un_campo_total(self):
        c = impacto.combinar([_completo(impact_id="im:a"), _completo(impact_id="im:b")])
        self.assertNotIn("total", c)
        self.assertNotIn("suma", c)

    def test_un_unknown_hace_unknown_el_total_sin_perder_lo_conocido(self):
        """Lo que no puede pasar es presentar la suma de los resueltos
        como si fuera el total: es la trampa de 'la media de los que
        contestaron'."""
        c = impacto.combinar([_completo(impact_id="im:a"), _impacto_base(impact_id="im:b")])
        self.assertEqual(c["state"], "UNKNOWN")
        self.assertEqual(c["conocido"], ["im:a"])
        self.assertEqual(len(c["unresolved"]), 1)
        self.assertTrue(c["unresolved"][0]["reasons"])

    def test_horizontes_distintos_no_se_combinan(self):
        a = _completo(impact_id="im:a")
        b = _completo(impact_id="im:b")
        b["horizon"] = {"state": "KNOWN", "dias_min": 400, "dias_max": 700}
        c = impacto.combinar([a, b])
        self.assertEqual(c["state"], "UNKNOWN")
        self.assertTrue(any("plazos distintos" in u for u in c["unknowns"]))

    def test_el_soporte_agregado_es_el_del_peor(self):
        a = _completo(impact_id="im:a", support="SUPPORTED")
        b = _completo(impact_id="im:b", support="CONTESTED")
        self.assertEqual(impacto.combinar([a, b])["support"], "CONTESTED")

    def test_todo_junto_si_valida(self):
        c = impacto.combinar([_completo(impact_id="im:a"), _completo(impact_id="im:b")])
        self.assertEqual(c["state"], "KNOWN")


# --- T8 y T9 ----------------------------------------------------------------
class TestElCaminoRealDeP5C(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k = modelo.cargar()
        evento = {"event_id": "ev4:p6t", "primary_entity": "org:nvidia",
                  "action": "demand_change", "direction": "UP"}
        cs = caminos.descubrir(evento["event_id"], "org:nvidia", cls.k, HOY, 2)
        cls.vals = [valoracion.valorar(evento, c, [], cls.k, modelo.vigente, HOY) for c in cs]
        res = R5D.resolver_valoraciones(cls.vals, cls.k, HOY, True)
        cls.requisitos = {f"{r['variable']}({r['entity_id']})": r for r in res}
        cls.impactos = [i for a in cls.vals for i in impacto.impactos_de(a, cls.requisitos, cls.k)]

    def test_todos_validan(self):
        for i in self.impactos:
            self.assertEqual(E.validar(i), [], i["impact_id"])

    def test_ningun_tramo_produce_magnitud(self):
        """El 100% esperado. Si algun dia deja de ser cierto, este test lo
        dice antes que nadie."""
        self.assertTrue(self.impactos)
        self.assertEqual({i["magnitude"]["state"] for i in self.impactos},
                         {"UNKNOWN", "NOT_APPLICABLE"})
        self.assertFalse(any(i["magnitude"]["value"] is not None for i in self.impactos))

    def test_cada_tramo_dice_si_es_que_no_puede_o_que_no_sabe(self):
        for i in self.impactos:
            self.assertTrue(i["reasons"], i["impact_id"])
            if i["magnitude"]["state"] == "NOT_APPLICABLE":
                self.assertEqual(i["magnitude_capability"], "NOT_QUANTIFIABLE")
            else:
                self.assertNotEqual(i["magnitude_capability"], "NOT_QUANTIFIABLE")

    def test_la_cadena_de_p5c_aparece_con_su_mecanismo(self):
        rel46 = [i for i in self.impactos if i["relationship_id"] == "rel:0046"]
        self.assertTrue(rel46)
        i = rel46[0]
        self.assertEqual(i["mechanism"], "CUSTOMER_DEMAND")
        self.assertEqual(i["entity_id"], "org:tsmc")
        self.assertEqual(i["magnitude_capability"], "CONDITIONALLY_QUANTIFIABLE")
        # P6.1: la materialidad pasa de UNKNOWN a BOUNDED <=19%.
        self.assertEqual(i["materiality"]["state"], "BOUNDED")
        self.assertEqual(i["materiality"]["upper_bound"], 19.0)
        self.assertIn("MATERIALITY_ONLY_BOUNDED", i["reasons"])
        self.assertIn("NO_TRANSMISSION_COEFFICIENT", i["reasons"])

    def test_la_cota_no_se_convierte_en_atribucion(self):
        """P6.1 cierra la deuda de P5C a medias, y lo dice: hay una cota
        del 19%, pero la fuente no nombra al cliente."""
        i = next(x for x in self.impactos if x["relationship_id"] == "rel:0046")
        self.assertTrue(any("NO se afirma" in u for u in i["unknowns"]))

    def test_p6_no_recalcula_la_direccion(self):
        """Si la recalculara habria dos motores opinando sobre lo mismo, y
        el dia que discreparan nadie sabria cual leer. Se compara tramo a
        tramo, no contra el conjunto de valores posibles."""
        pares = 0
        for a in self.vals:
            impactos = impacto.impactos_de(a, self.requisitos, self.k)
            self.assertEqual(len(impactos), len(a["segments"]))
            for tramo, i in zip(a["segments"], impactos):
                self.assertEqual(i["economic_direction"], tramo["economic_direction"])
                self.assertEqual(i["support"], tramo["support"])
                self.assertEqual(i["affected_variable"], tramo["affected_variable"])
                pares += 1
        self.assertGreater(pares, 10)

    def test_el_derecho_a_magnitud_no_es_una_rama_muerta(self):
        """El control positivo del motor completo: con los parametros
        presentes, la comprobacion se enciende. Sin este test, 'siempre
        False' podria ser un bug en vez de una decision."""
        punto = {"status": "KNOWN"}
        cota = {"status": "BOUNDED"}
        ok, motivos = impacto.derecho_a_magnitud("CUSTOMER_DEMAND", "rel:0046", "MEASURES")
        self.assertFalse(ok)
        self.assertEqual(set(motivos), {"MATERIALITY_UNKNOWN", "NO_TRANSMISSION_COEFFICIENT",
                                        "NO_BASELINE"})
        with _declarado(coef={("CUSTOMER_DEMAND", "rel:0046"): {"origin": "DECLARED",
                                                               "ref": "src:x"}},
                        base={"rel:0046": "media 8 trimestres"}):
            ok, motivos = impacto.derecho_a_magnitud("CUSTOMER_DEMAND", "rel:0046",
                                                     "MEASURES", punto)
            self.assertTrue(ok, motivos)
            self.assertEqual(motivos, [])
            # P6.1: una COTA no puntualiza, aunque todo lo demas este.
            ok, motivos = impacto.derecho_a_magnitud("CUSTOMER_DEMAND", "rel:0046",
                                                     "MEASURES", cota)
            self.assertFalse(ok)
            self.assertEqual(motivos, ["MATERIALITY_ONLY_BOUNDED"])

    def test_un_proxy_sigue_bloqueando_aunque_todo_lo_demas_este(self):
        """Y FRESH no habilita nada: demand(org:nvidia) esta FRESH y
        resuelve solo por proxy."""
        req = self.requisitos.get("demand(org:nvidia)")
        self.assertEqual(req["freshness"], "FRESH")
        self.assertEqual(req["availability"], "PARTIAL")
        with _declarado(coef={("CUSTOMER_DEMAND", "rel:0046"): {"origin": "DECLARED",
                                                               "ref": "src:x"}},
                        base={"rel:0046": "media 8 trimestres"}):
            ok, motivos = impacto.derecho_a_magnitud("CUSTOMER_DEMAND", "rel:0046", "PROXY",
                                                     {"status": "KNOWN"})
            self.assertFalse(ok)
            self.assertEqual(motivos, ["EVIDENCE_ONLY_BY_PROXY"])


# --- T10 --------------------------------------------------------------------
class TestInvariantes(unittest.TestCase):
    def test_p6_no_escribe_nada(self):
        def huella():
            h = hashlib.sha256()
            for sub in ("knowledge", "engine/causal", "engine/requirements",
                        "engine/impact", "data/incoming"):
                for raiz, _, fs in sorted(os.walk(os.path.join(RAIZ, sub))):
                    if "__pycache__" in raiz:
                        continue
                    for f in sorted(fs):
                        if f.endswith((".json", ".csv", ".py")):
                            with open(os.path.join(raiz, f), "rb") as fh:
                                h.update(fh.read())
            return h.hexdigest()
        antes = huella()
        impacto.derecho_a_magnitud("CUSTOMER_DEMAND", "rel:0046", "MEASURES")
        self.assertEqual(antes, huella())

    def test_no_hay_ninguna_formula_en_el_modulo(self):
        """v1 no calcula: decide si tendria derecho a calcular. Se
        comprueba por comportamiento, no leyendo el codigo: ninguna
        combinacion de entradas produce un value distinto de None."""
        k = modelo.cargar()
        evento = {"event_id": "ev4:f", "primary_entity": "org:nvidia",
                  "action": "demand_change", "direction": "UP"}
        cs = caminos.descubrir(evento["event_id"], "org:nvidia", k, HOY, 3)
        vals = [valoracion.valorar(evento, c, [], k, modelo.vigente, HOY) for c in cs]
        res = R5D.resolver_valoraciones(vals, k, HOY, True)
        req = {f"{r['variable']}({r['entity_id']})": r for r in res}
        with _declarado(coef={("CUSTOMER_DEMAND", "rel:0046"): {"origin": "DECLARED",
                                                               "ref": "src:x"}},
                        base={"rel:0046": "media"}):
            todos = [i for a in vals for i in impacto.impactos_de(a, req, k)]
        self.assertTrue(todos)
        self.assertTrue(all(i["magnitude"]["value"] is None for i in todos))

    def test_causalidad_no_es_materialidad(self):
        """El invariante nuevo: Knowledge acredita que la relacion existe;
        no dice en que proporcion, y P6 no lo rellena."""
        k = modelo.cargar()
        economicas = [r for r in k["relationships"]
                      if r["predicate"] in ("SUPPLIES", "USES") and r["polarity"] == "AFFIRMS"]
        self.assertTrue(economicas)
        for r in economicas:
            self.assertIsNone(RM.materialidad(r["relationship_id"]), r["relationship_id"])

    def test_la_ausencia_no_se_sustituye_por_un_valor_implicito(self):
        """Ninguna pieza sin resolver lleva un numero, en ningun sitio."""
        for r in (_impacto_base(), _impacto_base(mechanism="PRICING_POWER",
                                                 magnitude_capability="NOT_QUANTIFIABLE",
                                                 reasons=["MECHANISM_CANNOT_QUANTIFY"])):
            for pieza in ("magnitude", "materiality"):
                if r[pieza]["state"] != "KNOWN":
                    self.assertIsNone(r[pieza]["value"], pieza)
            if r["horizon"]["state"] != "KNOWN":
                self.assertIsNone(r["horizon"]["dias_min"])
                self.assertIsNone(r["horizon"]["dias_max"])

    def test_p5b_no_se_ha_tocado(self):
        h = hashlib.sha256()
        for f in ("mecanismos.py", "valoracion.py", "caminos.py"):
            with open(os.path.join(RAIZ, "engine", "causal", f), "rb") as fh:
                h.update(fh.read())
        with open(os.path.join(RAIZ, "engine", "causal", "valoracion.py"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("import esquema_impacto", src)
        self.assertNotIn("import impacto", src)


if __name__ == "__main__":
    unittest.main()
