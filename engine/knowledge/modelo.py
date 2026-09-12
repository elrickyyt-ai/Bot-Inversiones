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
    # D-21 (2026-09-07). Una referencia de mercado NO es un "security":
    # un indice no es negociable, no tiene sector ni mercado de cotizacion,
    # y meterlo en DimAsset rompe cosas medibles (ver la auditoria de D-21).
    # Un ETF que replica un indice SI es un security -- y por eso el
    # benchmark declara con que clase de serie se construye.
    "benchmark":    "referencia metodologica contra la que se mide una reaccion; no es un instrumento analizado",
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
    # D-21. Dos predicados, no uno con un flag: lo que cambia entre ellos
    # no es un matiz sino si la relacion habilita o no un retorno anormal.
    # NINGUNO de los dos es simetrico -- "ETH respecto a BTC" y "BTC
    # respecto a ETH" son relaciones distintas, con signo opuesto, y el
    # validador no las normaliza.
    "BENCHMARKED_BY": ({"security"}, {"benchmark"}),
    "COMPARED_TO":    ({"security"}, {"security", "benchmark"}),
    # Instrument Master v1 (2026-09-08). Un instrumento sucede a otro tras
    # una transformacion societaria. NO es un mecanismo economico: que
    # DowDuPont pasara a DuPont no conecta a DuPont con los clientes de Dow,
    # asi que queda fuera del recorrido causal (D-23).
    "SUCCEEDED_BY":   ({"security"}, {"security"}),
}

# --- Naturaleza semantica de cada predicado (P5A hardening, 2026-09-11) ---
#
# Refina la clasificacion de D-45, que tenia cuatro clases, separando
# IDENTITY de STRUCTURAL: no es lo mismo "que entidad esta detras de este
# instrumento" que "en que mercado cotiza". La primera resuelve identidad;
# la segunda solo situa.
#
# Se clasifica por lo que la relacion SIGNIFICA, nunca por el nombre de las
# entidades que une. Un hub estructural (un mercado, un pais, un sector) no
# crea causalidad por el hecho de que dos cosas cuelguen de el.
CAUSAL = "CAUSAL"            # transmite un efecto economico
IDENTITY = "IDENTITY"        # dice QUIEN es o en que se convirtio algo
STRUCTURAL = "STRUCTURAL"    # situa el instrumento en una estructura de mercado
MEASUREMENT = "MEASUREMENT"  # relacion de medida o comparacion (D-21/D-23)
REFERENCE = "REFERENCE"      # atributo de clasificacion o localizacion

SEMANTICA_PREDICADO = {
    "SUPPLIES":       CAUSAL,
    "USES":           CAUSAL,
    "DEPENDS_ON":     CAUSAL,
    "SUBSTITUTES":    CAUSAL,
    "EXPOSED_TO":     CAUSAL,
    "ISSUED_BY":      IDENTITY,
    "SUCCEEDED_BY":   IDENTITY,
    "LISTED_ON":      STRUCTURAL,
    "DOMICILED_IN":   REFERENCE,
    "CLASSIFIED_AS":  REFERENCE,
    "BENCHMARKED_BY": MEASUREMENT,
    "COMPARED_TO":    MEASUREMENT,
}
PREDICADOS_CAUSALES = frozenset(p for p, c in SEMANTICA_PREDICADO.items() if c == CAUSAL)


def semantica_de(predicado):
    """Clase semantica de un predicado. Lo no declarado NO es causal: el
    sistema no deduce semantica por ausencia de una excepcion."""
    return SEMANTICA_PREDICADO.get(predicado, REFERENCE)


def tiene_contenido_causal(aristas):
    """Variante C de D-49, literal: un camino tiene contenido causal si
    contiene AL MENOS UNA arista causal.

    No exige que TODAS lo sean -- esa era la variante B, que D-49 midio
    destruyendo 84 caminos de la forma EXPOSED_TO|EXPOSED_TO|LISTED_ON, que
    son legitimos: el contenido economico esta en las dos primeras aristas y
    la tercera solo situa el resultado."""
    return any(semantica_de(a.get("predicate")) == CAUSAL for a in aristas)


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

# --- D-21: referencias de mercado -----------------------------------------
# Un benchmark FORMAL habilita el retorno anormal. Una comparison
# REFERENCE contextualiza y no lo habilita nunca. La diferencia no es de
# grado: si BTC fuese el benchmark de BTC su retorno anormal seria cero
# por construccion.
ROLES_REFERENCIA = {
    "MARKET":      "referencia general del mercado del activo",
    "SECTOR":      "referencia del sector economico del activo",
    "ASSET_CLASS": "referencia de la clase de activo",
    "PEER":        "otro instrumento comparable -- NUNCA un benchmark formal",
}

# Declarados y NO activos. Mismo patron que D-10 con ESTIMATED: el token
# se nombra para que el dia que alguien lo use salte, en vez de aparecer
# sin que nadie lo note.
#
# ASSET_CLASS: para una accion estadounidense "mercado" (estadounidense) y
# "clase de activo" (renta variable) son cosas distintas; para un cripto
# coincidirian. Activarlo sin fijar antes cual de las dos lecturas es
# seria el error de token compartido que evito D-13.
ROLES_NO_ACTIVOS = {"ASSET_CLASS"}

# De donde sale la serie del benchmark. Determina que problemas tiene.
ORIGENES_SERIE_BENCHMARK = {
    "PUBLISHED_LEVEL": "nivel publicado por el proveedor del indice; no se restata, y la composicion es irrelevante",
    "ETF_NAV":         "valor de un instrumento negociable que replica el indice; tiene comision, tracking error y splits",
    "CONSTRUCTED":     "construida por este sistema -- PROHIBIDA, ver abajo",
}

# Un benchmark construido por el propio sistema a partir de los activos
# que ya sigue esta seleccionado ex post por construccion. Se declara para
# rechazarlo, no para usarlo.
ORIGEN_SERIE_PROHIBIDO = "CONSTRUCTED"

# El calendario es una propiedad del benchmark, no de la asignacion: el
# 28,5% de las sesiones de BTC caen en fin de semana y las de IBM cero,
# asi que un indice bursatil no puede medir un cripto ni queriendo.
CALENDARIOS_BENCHMARK = {"equity", "crypto"}

CAMPOS_BENCHMARK = {"methodology_version", "composition_source",
                    "point_in_time_capable", "calendar", "serie_desde", "serie_hasta"}

# Predicados que exigen `role`; el resto lo tienen prohibido.
PREDICADOS_CON_ROL = {"BENCHMARKED_BY", "COMPARED_TO"}

# Predicados que NO son aristas causales. Una asignacion de benchmark es
# una relacion de MEDIDA, no un mecanismo economico: que el S&P 500 sea la
# referencia de NVIDIA no crea ningun camino causal entre NVIDIA y las
# demas empresas del indice. Sin esta lista, engine/causal/caminos.py
# -- que recorre TODA relacion vigente, sin mirar el predicado -- las
# seguiria en cuanto se declarase la primera, y produciria caminos que no
# existen.
PREDICADOS_NO_CAUSALES = frozenset(PREDICADOS_CON_ROL | {"SUCCEEDED_BY"})


CAMPOS_RELACION = {
    "relationship_id", "subject", "predicate", "object", "polarity", "nature",
    "status", "support_level", "source_id", "statement", "valid_from",
    "valid_to", "last_verified", "verification_method",
    # D-21: obligatorio en PREDICADOS_CON_ROL, prohibido fuera de ellos.
    "role",
}
CAMPOS_ENTIDAD = {"entity_id", "type", "nombre", "status", "asset_id", "aliases",
                  "source_id", "nota",
                  # solo para type="benchmark"; el validador lo exige alli y
                  # lo prohibe en el resto (un sector no tiene metodologia)
                  "benchmark"}
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


def _solapan(a, b):
    """¿Se solapan las vigencias de dos relaciones? `valid_to: null`
    significa "vigente hasta nuevo aviso", no "para siempre" -- pero para
    comprobar solapamiento se trata como abierto por la derecha."""
    def _d(v, defecto):
        try:
            return datetime.date.fromisoformat(v) if v else defecto
        except (TypeError, ValueError):
            return defecto
    MIN, MAX = datetime.date.min, datetime.date.max
    a0, a1 = _d(a.get("valid_from"), MIN), _d(a.get("valid_to"), MAX)
    b0, b1 = _d(b.get("valid_from"), MIN), _d(b.get("valid_to"), MAX)
    return a0 <= b1 and b0 <= a1


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

        # --- D-21: bloque `benchmark`, exigido solo donde significa algo ---
        bm = ent.get("benchmark")
        if ent.get("type") == "benchmark":
            if not isinstance(bm, dict):
                e.append(f"{donde}: type=benchmark exige un bloque 'benchmark' con su metodologia")
            else:
                faltan = CAMPOS_BENCHMARK - set(bm)
                if faltan:
                    e.append(f"{donde}: bloque benchmark incompleto, faltan {sorted(faltan)}")
                sobra_bm = set(bm) - CAMPOS_BENCHMARK
                if sobra_bm:
                    e.append(f"{donde}: bloque benchmark con campos no reconocidos {sorted(sobra_bm)}")
                origen = bm.get("composition_source")
                if origen == ORIGEN_SERIE_PROHIBIDO:
                    e.append(f"{donde}: composition_source=CONSTRUCTED no se admite — "
                             f"una referencia construida con los propios activos del sistema "
                             f"esta seleccionada ex post por construccion")
                elif origen not in ORIGENES_SERIE_BENCHMARK:
                    e.append(f"{donde}: composition_source fuera del vocabulario: {origen!r}")
                if bm.get("calendar") not in CALENDARIOS_BENCHMARK:
                    e.append(f"{donde}: calendar fuera del vocabulario: {bm.get('calendar')!r}")
                if not isinstance(bm.get("point_in_time_capable"), bool):
                    e.append(f"{donde}: point_in_time_capable tiene que ser booleano, no {bm.get('point_in_time_capable')!r}")
                if not bm.get("methodology_version"):
                    e.append(f"{donde}: sin methodology_version — un cambio de metodologia del proveedor "
                             f"no puede pasar inadvertido")
                d0 = _fecha(bm.get("serie_desde"), donde, "benchmark.serie_desde", e)
                d1 = _fecha(bm.get("serie_hasta"), donde, "benchmark.serie_hasta", e)
                if bm.get("serie_desde") is None:
                    e.append(f"{donde}: sin serie_desde — sin ventana de disponibilidad no hay "
                             f"compatibilidad temporal que comprobar")
                if d0 and d1 and d1 < d0:
                    e.append(f"{donde}: serie_hasta anterior a serie_desde")
        elif bm is not None:
            e.append(f"{donde}: solo una entidad de tipo benchmark puede llevar bloque 'benchmark'")
        for al in ent.get("aliases") or []:
            if not al.get("scheme") or not al.get("value"):
                e.append(f"{donde}: alias sin scheme o sin value")
            _fecha(al.get("valid_from"), donde, "alias.valid_from", e)
            _fecha(al.get("valid_to"), donde, "alias.valid_to", e)

    # Un mismo (scheme, value) no puede apuntar a dos entidades A LA VEZ.
    #
    # Instrument Master v1 (2026-09-08): antes la comprobacion era global y
    # eso daba por supuesto que un ticker identifica a una sola entidad en
    # toda la historia -- justo el supuesto que MOB desmiente (el simbolo de
    # Mobil Corporation designa hoy a Mobilicom Limited). Un ticker
    # REUTILIZADO es legitimo mientras las vigencias no se solapen; lo que
    # sigue prohibido es que dos entidades lo reclamen en la misma fecha.
    por_alias = {}
    for ent in k["entities"]:
        for al in ent.get("aliases") or []:
            clave = (al.get("scheme"), al.get("value"))
            por_alias.setdefault(clave, []).append((ent.get("entity_id"), al))
    for clave, quienes in sorted(por_alias.items()):
        for i in range(len(quienes)):
            for j in range(i + 1, len(quienes)):
                (id_a, al_a), (id_b, al_b) = quienes[i], quienes[j]
                if id_a != id_b and _solapan(al_a, al_b):
                    e.append(f"alias ambiguo {clave}: {id_a} y {id_b} lo reclaman "
                             f"en vigencias que se solapan")

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

        # --- D-21: rol de la referencia ---
        role = r.get("role")
        if pred in PREDICADOS_CON_ROL:
            if role is None:
                e.append(f"{donde}: {pred} exige `role` — sin el no se sabe que representa la referencia")
            elif role in ROLES_NO_ACTIVOS:
                e.append(f"{donde}: role={role} esta declarado pero NO activo — su definicion no esta "
                         f"cerrada (ver ROLES_NO_ACTIVOS)")
            elif role not in ROLES_REFERENCIA:
                e.append(f"{donde}: role fuera del vocabulario: {role!r}")
            # Un PEER no asciende a benchmark porque falte el bueno.
            if pred == "BENCHMARKED_BY" and role == "PEER":
                e.append(f"{donde}: un PEER no puede ser benchmark formal — "
                         f"produce PEER_RELATIVE_RETURN, nunca ABNORMAL_RETURN")
            # Coherencia entre lo que el rol dice y lo que el objeto es.
            if r.get("object") in entidades:
                tipo_obj = entidades[r["object"]]["type"]
                if role == "PEER" and tipo_obj != "security":
                    e.append(f"{donde}: role=PEER exige un objeto de tipo security, no {tipo_obj}")
                if role in ("MARKET", "SECTOR") and tipo_obj != "benchmark":
                    e.append(f"{donde}: role={role} exige un objeto de tipo benchmark, no {tipo_obj}")
            # Nadie es su propia referencia: el retorno anormal seria cero
            # por construccion.
            if r.get("subject") == r.get("object"):
                e.append(f"{donde}: {r.get('subject')} no puede ser referencia de si mismo")
        elif role is not None:
            e.append(f"{donde}: `role` solo tiene sentido en {sorted(PREDICADOS_CON_ROL)}")

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

    # --- D-21: una asignacion por (activo, rol, periodo) ---------------
    # Es la defensa ESTRUCTURAL contra el benchmark selection bias: si un
    # activo pudiera tener dos benchmarks del mismo rol vigentes a la vez,
    # el calculo podria quedarse con el que diera el resultado mas
    # interesante. Con esta regla la eleccion es un acto de curacion con
    # fecha de commit, no una decision del codigo.
    asignaciones = {}
    for r in k["relationships"]:
        if r.get("predicate") != "BENCHMARKED_BY" or r.get("polarity") != "AFFIRMS":
            continue
        clave = (r.get("subject"), r.get("role"))
        asignaciones.setdefault(clave, []).append(r)
    for (suj, role), rels in sorted(asignaciones.items(), key=lambda x: (str(x[0][0]), str(x[0][1]))):
        for i, a in enumerate(rels):
            for b in rels[i + 1:]:
                if _solapan(a, b):
                    e.append(f"relacion {a.get('relationship_id')} y {b.get('relationship_id')}: "
                             f"{suj} tiene dos benchmarks de rol {role} con vigencias solapadas — "
                             f"un (activo, rol, periodo) admite exactamente uno")

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
