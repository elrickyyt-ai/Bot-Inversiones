# -*- coding: utf-8 -*-
"""T8 de F1 (2026-09-12) -- bateria negativa e invariantes.

    Un validador que nunca ha fallado no esta demostrado.

T8 NO introduce arquitectura: refuerza lo que T2, T3, T4, T6 y T7 ya
implementaron. Su aportacion propia es una GARANTIA DE COBERTURA:

    todo codigo de fallo declarado tiene que ser DEMOSTRABLE por una mutacion

Un codigo declarado y nunca producido es vocabulario muerto: parece que el
sistema sabe detectar algo que en realidad nunca ha detectado. Esa garantia
solo es comprobable si la bateria se ejecuta desde un unico sitio, y por eso
T8 repite algunas mutaciones que sus tickets ya prueban en detalle. La
duplicacion es el precio del techo de cobertura, no un descuido.

MUTATION MATRIX -- ver MUTACIONES al final del modulo.

NINGUNA mutacion toca el repositorio: se opera sobre copias en memoria o
sobre directorios temporales. Un test que "demuestre" integridad destruyendo
el historico seria una contradiccion en sus propios terminos.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(RAIZ, "contexto"))

import estado       # noqa: E402
import extraccion   # noqa: E402
import grafo        # noqa: E402
import integridad   # noqa: E402
import validar      # noqa: E402

# --- Vocabulario de FALLO -----------------------------------------------------
# Declarado a mano y no deducido: DURABLE, POINTS, DECLARED u OK son
# constantes de clasificacion, no codigos de fallo. Distinguirlas por
# heuristica seria exactamente el tipo de atajo que este proyecto evita.
CODIGOS_DE_FALLO = {
    "validar": (validar.DIVERGENCIA_CANONICA, validar.DUPLICACION_COMO_VERDAD,
                validar.REFERENCIA_AUSENTE, validar.FUENTE_NO_RESOLUBLE,
                validar.L0_DIVERGENTE, validar.L0_SOBRE_PRESUPUESTO,
                validar.AMBIGUEDAD_RESUELTA_EN_SILENCIO, validar.AFIRMACION_SIN_FECHA,
                validar.AFIRMACION_SIN_AUTORIA, validar.EVIDENCIA_NO_RESOLUBLE,
                validar.BLOQUE_DESCONOCIDO, validar.FUERA_DE_ALCANCE,
                # DF-1 (S0.1): dos veredictos de alcance nuevos. Se anaden con
                # su mutacion (M24, M25) en la misma tirada -- declarar un
                # codigo sin demostrarlo es el "vocabulario muerto" que este
                # fichero existe para impedir.
                validar.PROTEGIDO_GLOBAL, validar.ALCANCE_NO_DECLARADO,
                # Arquitectura objetivo (S0.4): tres codigos nuevos, cada uno
                # con su mutacion (M26-M28). Misma regla de siempre -- un
                # codigo declarado y nunca producido es vocabulario muerto.
                validar.ARQUITECTURA_ANCLA_NO_RESOLUBLE,
                validar.ARQUITECTURA_ESTADO_DIVERGENTE,
                validar.ARQUITECTURA_ESTADO_DESCONOCIDO),
    "grafo": (grafo.ARCO_PROHIBIDO, grafo.POINTER_EXPANDE_L0,
              grafo.RELACION_DESCONOCIDA, grafo.L0_NO_ALCANZABLE),
    "extraccion": (extraccion.EXTRACCION_NO_REALIZADA, extraccion.ANCLA_ROTA,
                   extraccion.COPIA_PARCIAL, extraccion.SECCION_NO_ELIMINADA,
                   extraccion.ANCLA_CABECERA_ROTA, extraccion.PROCEDENCIA_NO_RESOLUBLE),
    "integridad": integridad.ESTADOS_QUE_FALLAN,
}

PROTEGIDOS = ("CLAUDE.md", "contexto/ESTADO_VIGENTE.md", "contexto/contrato.json",
              "contexto/historico/claude_md_estado_previo_a_F1.md",
              "docs/ESTADO.md", "docs/DECISIONES.md")


def _sha(rel):
    return hashlib.sha256(open(os.path.join(RAIZ, rel), "rb").read()).hexdigest()


def _huellas():
    return {p: _sha(p) for p in PROTEGIDOS}


def _contrato():
    return estado.cargar_contrato()


def _idx_copia():
    idx = grafo.indice()
    return {**idx, "aristas": [dict(a) for a in idx["aristas"]]}


def _q(clase):
    c = _contrato()
    i, q = next((i, q) for i, q in enumerate(c["state_queries"]) if q["class"] == clase)
    return c, i, q


def _codigos(informe):
    """Codigos de fallo presentes en un informe de validar()."""
    out = set()
    for r in informe["resultados"]:
        if not r["ok"] and r["motivo"]:
            out.add(r["motivo"].split(":")[0])
    for inc in informe["incidencias"]:
        out.add(inc.split(":")[0])
    return out


# --- Mutaciones ---------------------------------------------------------------
# Cada una devuelve el conjunto de codigos que produce. Todas son puras:
# reciben o construyen su propio estado y no tocan el repositorio.

def m01_canonical_source_cambiado():
    c, i, _ = _q("CODE-ANCHORED")
    c["state_queries"][i]["canonical_fingerprint"] = "0" * 64
    return _codigos(validar.validar(contrato=c))


def m02_valor_duplicado_en_superficie():
    _, _, q = _q("CODE-ANCHORED")
    v, _e = validar._resolver(q["canonical_source"])
    sup = estado.texto_superficie() + "\n" + ", ".join(validar._normalizar(v)) + "\n"
    return _codigos(validar.validar(superficie=sup))


def m03_referencia_canonica_ausente():
    _, _, q = _q("CODE-ANCHORED")
    sup = estado.texto_superficie().replace(q["canonical_source"], "(borrada)")
    return _codigos(validar.validar(superficie=sup))


def m04_fuente_canonica_inexistente():
    c, i, _ = _q("CODE-ANCHORED")
    c["state_queries"][i]["canonical_source"] = "engine/no/existe.py::LO_QUE_SEA"
    c["state_queries"][i].pop("canonical_fingerprint", None)
    return _codigos(validar.validar(contrato=c))


def m05_ambiguous_con_valor_unico():
    c, i, _ = _q("AMBIGUOUS")
    c["state_queries"][i]["value"] = 3
    return _codigos(validar.validar(contrato=c))


def m06_ambiguous_con_una_sola_fuente():
    c, i, q = _q("AMBIGUOUS")
    c["state_queries"][i]["candidate_sources"] = q["candidate_sources"][:1]
    return _codigos(validar.validar(contrato=c))


def m07_human_asserted_sin_fecha():
    c, i, _ = _q("HUMAN-ASSERTED")
    c["state_queries"][i]["asserted_at"] = None
    return _codigos(validar.validar(contrato=c))


def m08_human_asserted_sin_autoria():
    c, i, _ = _q("HUMAN-ASSERTED")
    c["state_queries"][i]["asserted_by"] = ""
    return _codigos(validar.validar(contrato=c))


def m09_evidencia_irresoluble():
    c, i, _ = _q("HUMAN-ASSERTED")
    c["state_queries"][i]["evidence_ref"] = "commit:0000000"
    return _codigos(validar.validar(contrato=c))


def m10_l0_declarado_distinto_del_efectivo():
    c = _contrato()
    c["L0"] = ["CLAUDE.md"]
    return _codigos(validar.validar(contrato=c))


def m11_sexto_bloque_en_la_superficie():
    sup = estado.texto_superficie() + "\n## UN SEXTO BLOQUE\n\ncontenido\n"
    return _codigos(validar.validar(superficie=sup))


_BLOQUE_ESTRECHO = {"bloque_activo": "X",
                    "bloques": {"X": {"escritura": ["contexto/"]}}}


def m12_alcance_ruta_no_declarada():
    """REESCRITA en S0.1. Antes mutaba "tocar engine/, data/ y knowledge/",
    apoyandose en que esa lista fuese global; DF-1 la retiro porque el alcance
    es DEL BLOQUE (S0 declara data/incoming/ y engine/contract/). La mutacion
    equivalente, y la propiedad que sobrevive, es tocar lo que el bloque
    activo NO declara."""
    out = set()
    for ruta in ("engine/knowledge/modelo.py", "data/incoming/BTC_2026.csv",
                 "knowledge/entities/securities.json"):
        ok, motivo = validar.guarda_alcance([ruta], contrato=_BLOQUE_ESTRECHO)
        assert not ok
        out.add(motivo.split(":")[0])
    return out


def m24_protegido_global_sin_manifiesto():
    """Modificar un fichero fijado por hash sin regenerar el manifiesto en el
    mismo diff. El bloque lo declara en su escritura y AUN ASI no basta."""
    c = {"bloque_activo": "X", "bloques": {"X": {"escritura": ["docs/", "contexto/"]}}}
    ok, motivo = validar.guarda_alcance(["docs/DECISIONES.md"], contrato=c)
    assert not ok
    return {motivo.split(":")[0]}


def _arq(componentes):
    """Contrato con SOLO la arquitectura mutada. El resto del informe no se
    toca: interesa el codigo que produce esta comprobacion, no otros."""
    c = _contrato()
    c["arquitectura_objetivo"] = dict(c["arquitectura_objetivo"],
                                      componentes=componentes)
    return {f["motivo"].split(":")[0]
            for f in validar.estado_arquitectura(c) if not f["ok"]}


def m26_arquitectura_ancla_no_resoluble():
    """Declarar IMPLEMENTED un componente cuyo ancla ya no existe: el caso que
    convierte un documento de arquitectura en ficcion."""
    return _arq([{"id": "X", "nivel": "1", "estado_declarado": "IMPLEMENTED",
                  "ancla": "engine/borrado/hace/tiempo.py"}])


def m27_arquitectura_estado_divergente():
    """Aparece codigo bajo un componente declarado PLANNED. Es el sentido
    inverso, y el que de verdad envejece sin que nadie lo note."""
    return _arq([{"id": "X", "nivel": "2", "estado_declarado": "PLANNED",
                  "ancla": "contexto/validar.py"}])


def m28_arquitectura_estado_desconocido():
    return _arq([{"id": "X", "nivel": "1", "estado_declarado": "CASI_LISTO",
                  "ancla": None}])


def m25_alcance_no_declarado():
    """Retirar `bloque_activo`. No existe el estado "sin guarda"."""
    c = {"bloques": {"X": {"escritura": ["contexto/"]}}}
    ok, motivo = validar.guarda_alcance(["contexto/validar.py"], contrato=c)
    assert not ok
    return {motivo.split(":")[0]}


def m13_arco_regenerable_a_historico():
    idx = _idx_copia()
    idx["aristas"].append({"origen": "engine/knowledge/modelo.py",
                           "clase_origen": grafo.REGENERABLE, "relacion": grafo.POINTS,
                           "destino": "docs/DECISIONES.md",
                           "clase_destino": grafo.HISTORICAL})
    return {e for e, _ in grafo.verificar(idx)[1]}


def m14_pointer_convertido_en_mandatory_read():
    idx = _idx_copia()
    idx["aristas"].append({"origen": "contexto/ESTADO_VIGENTE.md",
                           "clase_origen": grafo.DURABLE, "relacion": grafo.MANDATORY_READ,
                           "destino": "docs/DECISIONES.md",
                           "clase_destino": grafo.HISTORICAL})
    return {e for e, _ in grafo.verificar(idx)[1]}


def m15_relacion_desconocida():
    idx = _idx_copia()
    idx["aristas"].append({"origen": "CLAUDE.md", "clase_origen": grafo.DURABLE,
                           "relacion": "SE_INSPIRA_EN", "destino": "contexto/validar.py",
                           "clase_destino": grafo.REGENERABLE})
    return {e for e, _ in grafo.verificar(idx)[1]}


def m16_nodo_de_l0_no_alcanzable():
    idx = _idx_copia()
    idx["l0"] = sorted(set(idx["l0"]) | {"contexto/contrato.json"})
    return {e for e, _ in grafo.verificar(idx)[1]}


def m17_historico_alterado():
    base = integridad.cargar(os.path.join(RAIZ, "contexto", "manifiesto.json"))
    despues = dict(base)
    despues[sorted(base)[0]] = "0" * 64
    return {v for v in integridad.comparar(base, despues).values()
            if v in integridad.ESTADOS_QUE_FALLAN}


def m18_historico_perdido_o_movido_sin_declarar():
    base = integridad.cargar(os.path.join(RAIZ, "contexto", "manifiesto.json"))
    una = sorted(base)[0]
    perdido = dict(base)
    del perdido[una]
    movido = dict(base)
    movido["docs/renombrado_a_escondidas.md"] = movido.pop(una)
    return ({v for v in integridad.comparar(base, perdido).values()
             if v in integridad.ESTADOS_QUE_FALLAN}
            | {v for v in integridad.comparar(base, movido).values()
               if v in integridad.ESTADOS_QUE_FALLAN})


def m19_ancla_de_extraccion_rota():
    b = open(os.path.join(RAIZ, extraccion.DESTINO), "rb").read()
    return {e for e, _ in extraccion.verificar(bytes_destino=b[:-1] + b"X")[1]}


def m20_copia_parcial_y_seccion_no_eliminada():
    b = open(os.path.join(RAIZ, extraccion.DESTINO), "rb").read()
    larga = next(l.strip() for l in b.decode().split("\n")
                 if len(l.strip()) >= extraccion.LONGITUD_LINEA_DISTINTIVA)
    claude = open(os.path.join(RAIZ, "CLAUDE.md"), encoding="utf-8").read()
    a = {e for e, _ in extraccion.verificar(texto_claude=claude + "\n" + larga + "\n")[1]}
    b2 = {e for e, _ in extraccion.verificar(
        texto_claude=claude + "\n" + extraccion.MARCA_SECCION + "\n")[1]}
    return a | b2


def m21_ancla_de_cabecera_rota():
    claude = open(os.path.join(RAIZ, "CLAUDE.md"), encoding="utf-8").read()
    tocado = claude.replace("Pseudonimizar por defecto", "Pseudonimizar a veces")
    return {e for e, _ in extraccion.verificar(texto_claude=tocado)[1]}


def _repo_temporal(lectura_obligatoria=None, bytes_extra=0):
    """Raiz temporal con la forma minima que el cierre de T3 reconoce.

    Se usa para los codigos que NO son producibles sobre el repositorio
    real sin romperlo -- superar el presupuesto o no haber hecho la
    extraccion. Directorio temporal, nunca el arbol de trabajo."""
    tmp = tempfile.mkdtemp()
    linea = ""
    if lectura_obligatoria:
        with open(os.path.join(tmp, lectura_obligatoria), "w", encoding="utf-8") as fh:
            fh.write("x" * bytes_extra)
        linea = f"\n**Antes de trabajar en nada, lee `{lectura_obligatoria}`.**\n"
    with open(os.path.join(tmp, "CLAUDE.md"), "w", encoding="utf-8") as fh:
        fh.write("# temporal\n" + linea)
    return tmp


def m22_l0_por_encima_del_presupuesto():
    """Una lectura obligatoria enorme hace que L0 supere el gate."""
    tmp = _repo_temporal("enorme.md", bytes_extra=(validar.GATE_L0 + 1000) * 4)
    try:
        conjunto, _ = validar.l0_efectivo(tmp)
        assert validar.medir_l0(conjunto, tmp) > validar.GATE_L0
        return _codigos(validar.validar(raiz=tmp))
    finally:
        shutil.rmtree(tmp)


def m23_extraccion_no_realizada():
    """Sin destino historico, la verificacion de D-PRD-1 lo dice con un
    estado de dominio -- no con FileNotFoundError."""
    tmp = _repo_temporal()
    try:
        codigos = {e for e, _ in extraccion.verificar(raiz=tmp)[1]}
        _p, err = extraccion.procedencia(raiz=tmp)
        if err:
            codigos.add(err)
        return codigos
    finally:
        shutil.rmtree(tmp)


MUTACIONES = [
    ("M01", "canonicalidad", "cambiar el sello de la fuente canonica", m01_canonical_source_cambiado),
    ("M02", "duplicate-as-truth", "inyectar el valor en la superficie", m02_valor_duplicado_en_superficie),
    ("M03", "canonicalidad", "borrar la referencia canonica de la superficie", m03_referencia_canonica_ausente),
    ("M04", "canonicalidad", "apuntar a una fuente canonica inexistente", m04_fuente_canonica_inexistente),
    ("M05", "ambiguous", "almacenar un valor unico", m05_ambiguous_con_valor_unico),
    ("M06", "ambiguous", "dejar una sola fuente candidata", m06_ambiguous_con_una_sola_fuente),
    ("M07", "human-asserted", "borrar asserted_at", m07_human_asserted_sin_fecha),
    ("M08", "human-asserted", "borrar asserted_by", m08_human_asserted_sin_autoria),
    ("M09", "human-asserted", "citar un commit inexistente", m09_evidencia_irresoluble),
    ("M10", "L0", "declarado != efectivo", m10_l0_declarado_distinto_del_efectivo),
    ("M11", "superficie", "anadir un sexto bloque", m11_sexto_bloque_en_la_superficie),
    ("M12", "alcance", "tocar lo que el bloque activo no declara", m12_alcance_ruta_no_declarada),
    ("M13", "reachability", "arco REGENERABLE -> HISTORICAL", m13_arco_regenerable_a_historico),
    ("M14", "reachability", "convertir un POINTS en MANDATORY_READ", m14_pointer_convertido_en_mandatory_read),
    ("M15", "reachability", "relacion fuera del vocabulario", m15_relacion_desconocida),
    ("M16", "reachability", "fichero de L0 que no es nodo", m16_nodo_de_l0_no_alcanzable),
    ("M17", "historico", "alterar un byte", m17_historico_alterado),
    ("M18", "historico", "perder o mover sin declarar", m18_historico_perdido_o_movido_sin_declarar),
    ("M19", "extraccion", "romper el ancla del destino", m19_ancla_de_extraccion_rota),
    ("M20", "extraccion", "dejar copia parcial y la marca de seccion", m20_copia_parcial_y_seccion_no_eliminada),
    ("M21", "extraccion", "tocar el bloque de privacidad", m21_ancla_de_cabecera_rota),
    ("M22", "L0", "superar el gate de 12.000 con una lectura obligatoria enorme", m22_l0_por_encima_del_presupuesto),
    ("M23", "extraccion", "no haber realizado la extraccion", m23_extraccion_no_realizada),
    ("M24", "alcance", "modificar el historico sin regenerar el manifiesto",
     m24_protegido_global_sin_manifiesto),
    ("M25", "alcance", "retirar bloque_activo del contrato",
     m25_alcance_no_declarado),
    ("M26", "arquitectura", "IMPLEMENTED con ancla que ya no existe",
     m26_arquitectura_ancla_no_resoluble),
    ("M27", "arquitectura", "PLANNED con ancla: declaracion obsoleta",
     m27_arquitectura_estado_divergente),
    ("M28", "arquitectura", "estado fuera del vocabulario",
     m28_arquitectura_estado_desconocido),
]


class TestCadaMutacionFalla(unittest.TestCase):
    """Toda mutacion declarada tiene que producir al menos un codigo."""

    def test_todas_producen_al_menos_un_codigo_de_fallo(self):
        for mid, prop, desc, fn in MUTACIONES:
            with self.subTest(mutacion=mid):
                codigos = fn()
                self.assertTrue(codigos, f"{mid} ({prop}: {desc}) no produjo ningun fallo")


class TestCoberturaDelVocabulario(unittest.TestCase):
    """La aportacion propia de T8: ningun codigo de fallo queda sin demostrar."""

    def test_todo_codigo_de_fallo_declarado_es_demostrable(self):
        declarados = {c for grupo in CODIGOS_DE_FALLO.values() for c in grupo}
        ejercitados = set()
        for _mid, _p, _d, fn in MUTACIONES:
            ejercitados |= fn()
        sin_demostrar = sorted(declarados - ejercitados)
        self.assertEqual(sin_demostrar, [],
                         f"codigos de fallo declarados que ninguna mutacion produce "
                         f"-- vocabulario muerto: {sin_demostrar}")

    def test_ninguna_mutacion_produce_un_codigo_no_declarado(self):
        declarados = {c for grupo in CODIGOS_DE_FALLO.values() for c in grupo}
        for mid, _p, _d, fn in MUTACIONES:
            with self.subTest(mutacion=mid):
                self.assertTrue(fn() <= declarados,
                                f"{mid} produce codigos fuera del vocabulario: "
                                f"{sorted(fn() - declarados)}")


class TestPropiedades(unittest.TestCase):
    """Determinismo, idempotencia, no-escritura y restauracion."""

    def test_determinismo_del_fingerprint(self):
        _, _, q = _q("CODE-ANCHORED")
        v, _e = validar._resolver(q["canonical_source"])
        self.assertEqual(validar._huella(v), validar._huella(v))
        self.assertEqual(validar._huella(v), q["canonical_fingerprint"])

    def test_determinismo_de_la_serializacion_del_indice(self):
        a = grafo.serializar(grafo.indice())
        b = grafo.serializar(grafo.indice())
        self.assertEqual(hashlib.sha256(a.encode()).hexdigest(),
                         hashlib.sha256(b.encode()).hexdigest())

    def test_determinismo_del_manifiesto(self):
        self.assertEqual(integridad.generar(), integridad.generar())

    def test_idempotencia_ejecutar_dos_veces_no_altera_el_estado(self):
        antes = _huellas()
        for _ in range(2):
            validar.validar()
            grafo.verificar(grafo.indice())
            integridad.verificar(
                integridad.cargar(os.path.join(RAIZ, "contexto", "manifiesto.json")),
                integridad.generar(), exigir_cero_movimientos=True)
            extraccion.verificar()
        self.assertEqual(antes, _huellas())

    def test_ningun_modulo_de_contexto_escribe(self):
        for mod in ("validar.py", "grafo.py", "integridad.py", "extraccion.py", "estado.py"):
            fuente = open(os.path.join(RAIZ, "contexto", mod), encoding="utf-8").read()
            cuerpo = fuente.split("def main(")[0]
            for patron in ('"w"', "'w'", '"a"', "'a'", "os.remove", "os.rename"):
                self.assertNotIn(patron, cuerpo, f"{mod} no puede escribir: {patron}")

    def test_restauracion_tras_toda_la_bateria(self):
        antes = _huellas()
        for _mid, _p, _d, fn in MUTACIONES:
            fn()
        self.assertEqual(antes, _huellas(),
                         "una mutacion modifico un artefacto protegido")

    def test_el_estado_real_sigue_pasando_despues_de_mutar(self):
        for _mid, _p, _d, fn in MUTACIONES:
            fn()
        inf = validar.validar()
        self.assertEqual([r for r in inf["resultados"] if not r["ok"]], [])
        self.assertEqual(inf["incidencias"], [])
        self.assertTrue(grafo.verificar(grafo.indice())[0])
        self.assertTrue(extraccion.verificar()[0])


class TestNoSeResuelvenDeudasAbiertas(unittest.TestCase):
    """T8 refuerza; no resuelve."""

    def test_D_A_sigue_abierta(self):
        deudas = " ".join(_contrato()["open_debt"])
        self.assertIn("vigente de superada", deudas)

    def test_X1_sigue_ambiguous(self):
        r = next(x for x in validar.validar()["resultados"] if x["class"] == "AMBIGUOUS")
        self.assertTrue(r["ok"])
        self.assertIn("EXPOSED_TO", r["discrepancia"])

    def test_D_2_sigue_siendo_heuristica(self):
        m = _contrato()["mecanismos"]["heuristic/v1"]
        self.assertIn("formal proof of absence", m["limitacion"])

    def test_no_se_prohiben_las_citas_historicas_de_engine(self):
        """Las 11 citas de engine/ a docs/ e informes/ NO se prohiben: la
        restriccion es del GRAFO DE CONTEXTO, no del repositorio."""
        import re
        pat = re.compile(r"(docs/[\w.\-]+\.md|informes/[\w.\-]+\.md)")
        con_citas = 0
        for carpeta, _s, fs in os.walk(os.path.join(RAIZ, "engine")):
            if "__pycache__" in carpeta:
                continue
            for f in fs:
                if f.endswith(".py") and pat.search(
                        open(os.path.join(carpeta, f), encoding="utf-8").read()):
                    con_citas += 1
        self.assertGreater(con_citas, 0,
                           "si esto llega a 0, alguien prohibio algo que T7 midio legitimo")
        self.assertTrue(grafo.verificar(grafo.indice())[0],
                        "y aun asi el grafo de contexto sigue limpio")


if __name__ == "__main__":
    unittest.main(verbosity=2)
