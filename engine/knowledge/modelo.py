"""Knowledge Model v1 -- vocabularios, carga y validacion.

P2 (2026-09-06). Esto NO es un grafo ni una base de datos: son ficheros
JSON pequenos, mantenidos a mano y versionados en git, con un validador
que se niega a aceptarlos si no cumplen las reglas de abajo.

El objetivo de v1 no es "tener una base de conocimiento". Es demostrar
que podemos sacar del codigo el conocimiento estructural que hoy vive
ahi de forma accidental y representarlo de forma explicita, trazable y
temporalmente valida, SIN cambiar todavia el comportamiento del sistema.

CUATRO REGLAS QUE EL VALIDADOR HACE CUMPLIR
-------------------------------------------
1. Ninguna relacion sin fuente resoluble. Conocer algo y poder citarlo
   son cosas distintas, y solo la segunda entra aqui.
2. `nature` NO admite INFERRED. Knowledge representa el mundo que el
   sistema considera conocido; la inferencia es una OPERACION sobre ese
   conocimiento y se calcula, se muestra y se descarta. Si la inferencia
   pudiera persistirse junto al conocimiento, en dos meses nadie sabria
   cual de las dos cosas esta leyendo.
3. Toda relacion tiene vigencia. `valid_to: null` significa "vigente
   hasta nuevo aviso", nunca "para siempre".
4. Negar exige fuente igual que afirmar. `polarity: DENIES` es una
   comprobacion, no una ausencia disfrazada.

Y UNA QUINTA QUE NO ES DEL VALIDADOR SINO DEL PROCESO
-----------------------------------------------------
Ningun resultado del motor causal puede modificar una relacion
estructural. El conocimiento se actualiza solo por
nueva fuente -> verificacion -> actualizacion controlada.
No hay ninguna funcion de escritura en este modulo: es de solo lectura
a proposito.
"""
import datetime
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KNOWLEDGE_DIR = os.path.join(ROOT, "knowledge")
PENDIENTE_DIR = os.path.join(KNOWLEDGE_DIR, "pendiente")


class KnowledgeError(Exception):
    pass


# --- Vocabularios cerrados -------------------------------------------------
# Anadir un valor cuesta una entrada aqui, con justificacion y fecha. Es
# barato, pero no gratis: es lo que impide que el vocabulario crezca a
# treinta predicados sin que nadie lo note.

TIPOS_ENTIDAD = {
    "security":     "instrumento negociable (lo que hoy es un asset_id)",
    "organization": "empresa, institucion, regulador, banco central",
    "region":       "pais o bloque economico",
    "sector":       "clasificacion economica",
    "venue":        "mercado donde se negocia",
    "product":      "bien o servicio concreto, con capacidad y precio",
    "technology":   "proceso o capacidad que se emplea, no se compra",
    "material":     "insumo fisico",
    "person":       "individuo",
}

# Una entidad no se borra cuando deja de cotizar: su identidad sigue
# existiendo y sus relaciones pasadas siguen siendo ciertas para su
# periodo de vigencia.
ESTADOS_ENTIDAD = {
    "ACTIVE":     "existe y esta operativa hoy",
    "INACTIVE":   "existio y ya no opera (delistada, disuelta)",
    "HISTORICAL": "solo se mantiene para explicar datos pasados",
    "UNKNOWN":    "no se ha comprobado su estado actual",
}

# (sujeto, objeto) permitidos por predicado. Impide aristas absurdas como
# "un mercado emitido por un material".
PREDICADOS = {
    "ISSUED_BY":     ({"security"}, {"organization"}),
    "LISTED_ON":     ({"security"}, {"venue"}),
    "DOMICILED_IN":  ({"organization"}, {"region"}),
    "CLASSIFIED_AS": ({"organization", "security"}, {"sector"}),
    "EXPOSED_TO":    ({"security", "organization"}, {"region", "product", "material", "technology"}),
    "SUPPLIES":      ({"organization"}, {"organization"}),
    "USES":          ({"organization"}, {"product", "technology"}),
    "DEPENDS_ON":    (set(TIPOS_ENTIDAD), set(TIPOS_ENTIDAD)),
    "SUBSTITUTES":   ({"product", "material", "technology"}, {"product", "material", "technology"}),
}

POLARIDADES = {
    "AFFIRMS": "la relacion se da",
    "DENIES":  "se ha comprobado que NO se da -- es informacion, no ausencia",
}

# INFERRED no esta y no puede estar. Ver regla 2 del docstring.
NATURALEZAS = {
    "STRUCTURAL": "verificable en un documento que se puede citar y releer",
    "ASSERTED":   "afirmada por una fuente identificable, no verificable en un primario",
}
NATURALEZA_PROHIBIDA = "INFERRED"

ESTADOS_RELACION = {
    "VERIFIED":    "comprobada contra su fuente",
    "PROVISIONAL": "registrada pero pendiente de evidencia independiente",
}

# Ordinal de TRES valores, deliberadamente no multiplicable. El proyecto
# ya tiene tres escalas 0-100 (confidence_pct, data_quality_pct,
# source_priority) y P0 demostro que la tercera significa cosas distintas
# segun el dominio; un cuarto numero invitaria a multiplicarlos.
#
# Y no se llama "confidence" a proposito: NO es la probabilidad de que la
# relacion sea cierta, sino el grado de respaldo que tiene hoy DENTRO del
# sistema. "confidence" queda reservado para la inferencia posterior.
SOPORTE = {"ALTO": 0, "MEDIO": 1, "BAJO": 2}

TIPOS_FUENTE = {
    "FILING":            "documento regulatorio de la propia empresa",
    "REGULATOR":         "publicacion de un regulador o banco central",
    "COMPANY_STATEMENT": "comunicacion publica de la empresa interesada",
    "PRESS":             "medio periodistico",
    "RESEARCH":          "analisis profesional de terceros",
    "DATA_PROVIDER":     "proveedor de datos (Alpha Vantage, CoinGecko...)",
    "INTERNAL_RULE":     "una regla del codigo de ESTE sistema, no evidencia externa",
    "OWN_ANALYSIS":      "analisis hecho dentro de este proyecto",
}

CAMPOS_RELACION = {
    "relationship_id", "subject", "predicate", "object", "polarity", "nature",
    "status", "support_level", "source_id", "statement", "valid_from",
    "valid_to", "last_verified", "verification_method",
}
CAMPOS_ENTIDAD = {"entity_id", "type", "nombre", "status", "asset_id", "aliases",
                  "source_id", "nota"}
CAMPOS_FUENTE = {"source_id", "tipo", "publisher", "titulo", "localizador",
                 "fecha_publicacion", "fecha_consulta", "accesible", "nota"}
CAMPOS_CONCEPTO = {"concept_id", "nombre", "unidad_canonica", "parametros",
                   "comparable_entre_entidades", "nota_comparabilidad",
                   "implementaciones"}


# --- Carga -----------------------------------------------------------------

def _leer_dir(subdir, base=None):
    d = os.path.join(base or KNOWLEDGE_DIR, subdir)
    filas = []
    if not os.path.isdir(d):
        return filas
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"):
            continue
        with open(os.path.join(d, f), encoding="utf-8") as fh:
            contenido = json.load(fh)
        for fila in contenido:
            fila["_fichero"] = os.path.join(subdir, f)
            filas.append(fila)
    return filas


def cargar(base=None):
    """Todo el conocimiento valido. `pendiente/` NO se carga: vive fuera
    del conjunto valido a proposito."""
    return {
        "entities": _leer_dir("entities", base),
        "concepts": _leer_dir("concepts", base),
        "relationships": _leer_dir("relationships", base),
        "sources": _leer_dir("sources", base),
    }


def cargar_pendiente():
    """Conocimiento CANDIDATO: declarado pero sin fuente documentada. No
    valida, no se puede recorrer, y esa es su funcion."""
    filas = []
    if not os.path.isdir(PENDIENTE_DIR):
        return filas
    for f in sorted(os.listdir(PENDIENTE_DIR)):
        if f.endswith(".json"):
            with open(os.path.join(PENDIENTE_DIR, f), encoding="utf-8") as fh:
                filas += json.load(fh)
    return filas


# --- Validacion ------------------------------------------------------------

def _fecha(v, donde, campo, errores):
    if v is None:
        return None
    try:
        return datetime.date.fromisoformat(v)
    except (TypeError, ValueError):
        errores.append(f"{donde}: {campo} no es una fecha ISO: {v!r}")
        return None


def validar(k):
    """Devuelve la lista de incidencias. Vacia = el conjunto es valido."""
    e = []
    entidades = {x.get("entity_id"): x for x in k["entities"]}
    fuentes = {x.get("source_id") for x in k["sources"]}

    # --- entidades ---
    vistos = set()
    for ent in k["entities"]:
        eid = ent.get("entity_id")
        donde = f"entidad {eid}"
        sobra = set(ent) - CAMPOS_ENTIDAD - {"_fichero"}
        if sobra:
            e.append(f"{donde}: campos no reconocidos {sorted(sobra)}")
        if not eid or ":" not in eid:
            e.append(f"{donde}: entity_id debe llevar prefijo de tipo (ej. org:nvidia)")
            continue
        if eid in vistos:
            e.append(f"{donde}: entity_id duplicado")
        vistos.add(eid)
        if ent.get("type") not in TIPOS_ENTIDAD:
            e.append(f"{donde}: type fuera del vocabulario: {ent.get('type')!r}")
        if ent.get("status") not in ESTADOS_ENTIDAD:
            e.append(f"{donde}: status fuera del vocabulario: {ent.get('status')!r}")
        if not ent.get("nombre"):
            e.append(f"{donde}: sin nombre")
        for al in ent.get("aliases") or []:
            if not al.get("scheme") or not al.get("value"):
                e.append(f"{donde}: alias sin scheme o sin value")
            _fecha(al.get("valid_from"), donde, "alias.valid_from", e)
            _fecha(al.get("valid_to"), donde, "alias.valid_to", e)

    # un mismo (scheme, value) no puede apuntar a dos entidades
    por_alias = {}
    for ent in k["entities"]:
        for al in ent.get("aliases") or []:
            clave = (al.get("scheme"), al.get("value"))
            por_alias.setdefault(clave, set()).add(ent.get("entity_id"))
    for clave, quienes in sorted(por_alias.items()):
        if len(quienes) > 1:
            e.append(f"alias ambiguo {clave}: apunta a {sorted(quienes)}")

    # --- fuentes ---
    for src in k["sources"]:
        donde = f"fuente {src.get('source_id')}"
        sobra = set(src) - CAMPOS_FUENTE - {"_fichero"}
        if sobra:
            e.append(f"{donde}: campos no reconocidos {sorted(sobra)}")
        if src.get("tipo") not in TIPOS_FUENTE:
            e.append(f"{donde}: tipo fuera del vocabulario: {src.get('tipo')!r}")
        if not src.get("localizador"):
            e.append(f"{donde}: sin localizador -- una fuente que no se puede reabrir no es una fuente")
        pub = src.get("publisher")
        if pub and pub not in entidades:
            e.append(f"{donde}: publisher {pub} no es una entidad declarada")
        _fecha(src.get("fecha_consulta"), donde, "fecha_consulta", e)

    # --- relaciones ---
    ids = set()
    for r in k["relationships"]:
        rid = r.get("relationship_id")
        donde = f"relacion {rid}"
        sobra = set(r) - CAMPOS_RELACION - {"_fichero"}
        if sobra:
            e.append(f"{donde}: campos no reconocidos {sorted(sobra)}")
        if rid in ids:
            e.append(f"{donde}: relationship_id duplicado")
        ids.add(rid)

        pred = r.get("predicate")
        if pred not in PREDICADOS:
            e.append(f"{donde}: predicado fuera del vocabulario: {pred!r}")
        for extremo in ("subject", "object"):
            if r.get(extremo) not in entidades:
                e.append(f"{donde}: {extremo} {r.get(extremo)!r} no es una entidad declarada")
        if pred in PREDICADOS and r.get("subject") in entidades and r.get("object") in entidades:
            tipos_s, tipos_o = PREDICADOS[pred]
            ts = entidades[r["subject"]]["type"]
            to = entidades[r["object"]]["type"]
            if ts not in tipos_s:
                e.append(f"{donde}: {pred} no admite un sujeto de tipo {ts}")
            if to not in tipos_o:
                e.append(f"{donde}: {pred} no admite un objeto de tipo {to}")

        if r.get("polarity") not in POLARIDADES:
            e.append(f"{donde}: polarity fuera del vocabulario: {r.get('polarity')!r}")
        nat = r.get("nature")
        if nat == NATURALEZA_PROHIBIDA:
            e.append(f"{donde}: nature=INFERRED no puede almacenarse en Knowledge — "
                     f"la inferencia se calcula, no se guarda")
        elif nat not in NATURALEZAS:
            e.append(f"{donde}: nature fuera del vocabulario: {nat!r}")
        if r.get("status") not in ESTADOS_RELACION:
            e.append(f"{donde}: status fuera del vocabulario: {r.get('status')!r}")
        if r.get("support_level") not in SOPORTE:
            e.append(f"{donde}: support_level fuera del vocabulario: {r.get('support_level')!r}")

        # Regla 1 y 4: toda relacion, tambien una negacion, exige fuente.
        if not r.get("source_id"):
            e.append(f"{donde}: sin source_id — negar o afirmar exigen fuente por igual")
        elif r["source_id"] not in fuentes:
            e.append(f"{donde}: source_id {r['source_id']} no resuelve en sources/")
        if not r.get("statement"):
            e.append(f"{donde}: sin statement — hay que poder leer qué dice la fuente")

        # Regla 3: vigencia.
        desde = _fecha(r.get("valid_from"), donde, "valid_from", e)
        hasta = _fecha(r.get("valid_to"), donde, "valid_to", e)
        if r.get("valid_from") is None:
            e.append(f"{donde}: sin valid_from — una relación sin vigencia no es comprobable")
        if desde and hasta and hasta < desde:
            e.append(f"{donde}: valid_to ({hasta}) anterior a valid_from ({desde})")
        _fecha(r.get("last_verified"), donde, "last_verified", e)
        if not r.get("verification_method"):
            e.append(f"{donde}: sin verification_method")

    # --- conceptos ---
    for c in k["concepts"]:
        donde = f"concepto {c.get('concept_id')}"
        sobra = set(c) - CAMPOS_CONCEPTO - {"_fichero"}
        if sobra:
            e.append(f"{donde}: campos no reconocidos {sorted(sobra)}")
        impl = c.get("implementaciones") or []
        if len(impl) > 1 and c.get("comparable_entre_entidades") is None:
            e.append(f"{donde}: con más de una implementación hay que declarar "
                     f"comparable_entre_entidades")
        if c.get("comparable_entre_entidades") is False and not c.get("nota_comparabilidad"):
            e.append(f"{donde}: declarado no comparable sin explicar por qué")
        for i in impl:
            if i.get("entity_id") and i["entity_id"] not in entidades:
                e.append(f"{donde}: implementación sobre entidad no declarada {i['entity_id']}")
    return e


def vigente(rel, fecha):
    """¿Estaba vigente esta relacion en `fecha`? valid_to es exclusivo:
    una relacion que termino el 2023-07-01 no estaba vigente ese dia."""
    desde = datetime.date.fromisoformat(rel["valid_from"])
    if fecha < desde:
        return False
    if rel.get("valid_to"):
        return fecha < datetime.date.fromisoformat(rel["valid_to"])
    return True
