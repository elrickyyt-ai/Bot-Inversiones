# -*- coding: utf-8 -*-
"""Validador del contexto durable. T6-SLICE de F1 (2026-09-12).

ANDAMIAJE + BALA TRAZADORA. En BLOCK 1A solo existe la clase
CODE-ANCHORED. AMBIGUOUS, HUMAN-ASSERTED y UNDECLARED son T6 completo y
NO estan implementados.

    DURABLE CONTEXT  ->  references / validates  ->  CANONICAL SOURCE
    DURABLE CONTEXT  -X  duplicates as truth     -X  CANONICAL SOURCE
"""
import hashlib
import importlib
import json
import os
import re
import sys

import estado as _estado

RAIZ = _estado.RAIZ

# --- Mecanismos versionados (D-1.1 y D-2) -----------------------------------
#
# canonical-fingerprint/v1  [N] COMPORTAMIENTO NORMATIVO
#
#   fingerprint = SHA-256( canonical_serialization( canonical_value ) )  -> hex
#
#   normalizacion   una coleccion (set, frozenset, list, tuple) se normaliza a
#                   la lista ORDENADA de str(x) de sus elementos. Un escalar, a
#                   str(x). El orden incidental de representacion NO forma parte
#                   del valor: frozenset, list y tuple con los mismos elementos
#                   producen el MISMO fingerprint. La multiplicidad SI se
#                   conserva -- ["A","A"] y {"A"} son valores distintos.
#   serializacion   coleccion: elementos unidos por "\n" (LF). Escalar: su str.
#   codificacion    UTF-8.
#   algoritmo       SHA-256, en hexadecimal minusculas.
#
#   QUE ES: metadata / provenance. Registra contra QUE estado de la fuente
#   canonica se declaro la consulta.
#   QUE NO ES: query result. El validador NUNCA lo usa para responder la
#   pregunta -- eso se hace SIEMPRE resolviendo la fuente viva. Por eso es
#   compatible con el Arco 1: el valor canonico no se almacena.
#
#   Cambiar cualquiera de los cuatro puntos exige canonical-fingerprint/v2.
CANONICAL_FINGERPRINT_VERSION = "canonical-fingerprint/v1"

# heuristic/v1  [N] DETECCION DE DUPLICACION COMO VERDAD (D-2)
#
#   Busca renderizaciones DIRECTAS del valor canonico completo dentro de la
#   superficie. NO es una prueba formal de ausencia:
#
#       heuristic detection  !=  formal proof of absence
#
#   No garantiza detectar parafrasis ni representaciones semanticamente
#   equivalentes. La proteccion PRIMARIA del Arco 1 no es esta deteccion,
#   sino el contrato:
#
#       CODE-ANCHORED -> canonical_source -> canonical_fingerprint -> NO value field
#
#   OPEN DEBT: Structural enforcement of no-value duplication.
DUPLICACION_HEURISTICA_VERSION = "heuristic/v1"

DIVERGENCIA_CANONICA = "DIVERGENCIA_CANONICA"
DUPLICACION_COMO_VERDAD = "DUPLICACION_COMO_VERDAD"
REFERENCIA_AUSENTE = "REFERENCIA_AUSENTE"
FUENTE_NO_RESOLUBLE = "FUENTE_NO_RESOLUBLE"


class ValidacionError(Exception):
    pass


# --- Estados de respuesta (T2/T6 completos) ---------------------------------
#
#   DECLARED    la pregunta tiene entrada en el registro
#   UNDECLARED  NO la tiene -> respuesta explicita, NUNCA un valor por defecto
#
# Son un EJE DISTINTO de las clases: CODE-ANCHORED / AMBIGUOUS /
# HUMAN-ASSERTED clasifican una entrada declarada; DECLARED/UNDECLARED dicen
# si hay entrada. El validador no los confunde.
DECLARED = "DECLARED"
UNDECLARED = "UNDECLARED"

# l0-closure/v1  [N] CIERRE EFECTIVO DE L0 (P-2)
#
#   L0_efectivo = (a) todo CLAUDE.md del arbol, excluyendo .git/
#               + (b) ficheros traidos por import explicito desde (a)
#               + (c) lecturas obligatorias INCONDICIONALES declaradas en (a)
#
#   FRONTERA:  OBLIGATORY LOAD != REFERENCE != POINTER
#   Una cita, un enlace, un canonical_source o un historical_pointer NO
#   expanden L0. Solo lo hace una declaracion explicita de lectura
#   obligatoria previa. Sin esta frontera, el grafo de referencias
#   convertiria el contexto pequeno en un cierre recursivo.
#
#   Una lectura obligatoria CONDICIONAL (acotada a una parte del trabajo, como
#   el protocolo de privacidad: "antes de tratar cualquier dato del usuario")
#   es L2, no L0. Su ENUNCIADO vive en L0; su texto integro se recupera bajo
#   demanda (decision del PRD, seccion CONTEXT MODEL).
#
#   HEURISTICA DECLARADA, con su limite: reconoce el patron imperativo de
#   lectura con una ruta entre backticks. Una lectura obligatoria redactada
#   de otra forma no seria detectada. La comprobacion declarado-vs-efectivo
#   atrapa el caso contrario -- algo que se carga y no se declaro -- pero no
#   este. Es enumerable desde el sistema de ficheros y NO introspecciona el
#   comportamiento interno de ningun runtime externo.
L0_CLOSURE_VERSION = "l0-closure/v1"
_PATRON_LECTURA = re.compile(r"(?im)^.*?\b(?:lee|leer)\b[^`\n]*`([^`\n]+)`")
_PATRON_CONDICION = re.compile(r"(?i)antes de\s+(.+?),")
_ALCANCE_INCONDICIONAL = ("trabajar en nada",)
_PATRON_IMPORT = re.compile(r"(?m)^@([^\s]+)\s*$")

GATE_L0 = 12000
OBJETIVO_L0 = 10000          # NO vinculante: nunca es criterio de fallo

L0_DIVERGENTE = "L0_DIVERGENTE"
L0_SOBRE_PRESUPUESTO = "L0_SOBRE_PRESUPUESTO"
AMBIGUEDAD_RESUELTA_EN_SILENCIO = "AMBIGUEDAD_RESUELTA_EN_SILENCIO"
AFIRMACION_SIN_FECHA = "AFIRMACION_SIN_FECHA"
AFIRMACION_SIN_AUTORIA = "AFIRMACION_SIN_AUTORIA"
EVIDENCIA_NO_RESOLUBLE = "EVIDENCIA_NO_RESOLUBLE"
BLOQUE_DESCONOCIDO = "BLOQUE_DESCONOCIDO"

# --- Alcance por bloque (DF-1, S0.1) ---------------------------------------
#
#   Sustituye el interruptor binario `alcance_bloque.vigente`. El defecto de
#   aquel mecanismo no era la lista: era que apagarlo dejaba proteccion CERO,
#   y que un bloque solo podia declarar QUE su alcance aplicaba, nunca CUAL
#   era. Aqui cada bloque declara su propia lista de escritura y SIEMPRE hay
#   un bloque activo.
#
#   CUATRO VEREDICTOS, en este orden de precedencia:
#
#     ALCANCE_NO_DECLARADO  sin bloque activo, o apunta a un bloque que el
#                           contrato no declara. Gana sobre todo y FALLA: no
#                           existe el estado "sin guarda".
#     PROTEGIDO_GLOBAL      la ruta esta bajo la autoridad de la integridad
#                           historica. Gana sobre la lista del bloque, de modo
#                           que NINGUN bloque puede autorizarse a si mismo el
#                           historico. Es CONDICIONAL, no una prohibicion
#                           absoluta: ver _condicion_protegido().
#     PERMITIDO             prefijo declarado en bloques[activo].escritura
#     FUERA_DE_ALCANCE      todo lo demas. DENEGACION POR DEFECTO: lo no
#                           declarado nunca se permite, igual que UNDECLARED
#                           nunca degrada a valor por defecto.
#
#   NINGUNA LISTA DE ARBOLES PROTEGIDOS SE DECLARA AQUI. Se DERIVA de quien
#   ya posee esa autoridad -- las claves de contexto/manifiesto.json y el
#   destino de la extraccion D-PRD-1. Escribir la lista en este modulo seria
#   una segunda copia, que es el defecto que DF-1 venia a corregir.
PERMITIDO = "PERMITIDO"
PROTEGIDO_GLOBAL = "PROTEGIDO_GLOBAL"
FUERA_DE_ALCANCE = "FUERA_DE_ALCANCE"
ALCANCE_NO_DECLARADO = "ALCANCE_NO_DECLARADO"

VEREDICTOS_ALCANCE = (ALCANCE_NO_DECLARADO, PROTEGIDO_GLOBAL,
                      PERMITIDO, FUERA_DE_ALCANCE)

# El unico veredicto que pasa sin condicion. PROTEGIDO_GLOBAL pasa solo si se
# cumple su condicion; los otros dos fallan siempre.
VEREDICTOS_QUE_PASAN = (PERMITIDO,)

# Ruta del mecanismo que concede permiso sobre el historico. NO es una lista
# de arboles: es el fichero que hay que regenerar para que integridad.py
# pueda pronunciarse.
MANIFIESTO = "contexto/manifiesto.json"
AUTORIDAD_EXTRACCION = "contexto/extraccion.py"


def consultar(query_id, contrato=None):
    """(estado, entrada). UNDECLARED NUNCA trae un valor por defecto."""
    for q in _estado.consultas(contrato or _estado.cargar_contrato()):
        if q["query_id"] == query_id:
            return DECLARED, q
    return UNDECLARED, None


def l0_efectivo(raiz=RAIZ):
    """Cierre enumerable de L0 segun P-2. Devuelve (conjunto, detalle)."""
    pendientes, conjunto, condicionales, imports = [], [], [], []
    for carpeta, subdirs, ficheros in os.walk(raiz):
        subdirs[:] = [d for d in subdirs if d not in (".git", "__pycache__")]
        for f in ficheros:
            if f == "CLAUDE.md":
                rel = os.path.relpath(os.path.join(carpeta, f), raiz).replace(os.sep, "/")
                conjunto.append(rel)
                pendientes.append(rel)

    vistos = set(conjunto)
    while pendientes:
        rel = pendientes.pop()
        destino = os.path.join(raiz, rel)
        if not os.path.isfile(destino):
            continue
        texto = open(destino, encoding="utf-8").read()
        for ruta in _PATRON_IMPORT.findall(texto):          # (b) imports
            if ruta not in vistos:
                vistos.add(ruta); conjunto.append(ruta); imports.append(ruta)
                pendientes.append(ruta)
        for linea in texto.split("\n"):                      # (c) lecturas
            m = _PATRON_LECTURA.search(linea)
            if not m:
                continue
            ruta = m.group(1).strip()
            if not os.path.isfile(os.path.join(raiz, ruta)):
                continue
            cond = _PATRON_CONDICION.search(linea)
            incondicional = bool(cond) and any(
                a in cond.group(1) for a in _ALCANCE_INCONDICIONAL)
            if incondicional:
                if ruta not in vistos:
                    vistos.add(ruta); conjunto.append(ruta); pendientes.append(ruta)
            elif ruta not in condicionales:
                condicionales.append(ruta)
    return sorted(conjunto), {"metodo": L0_CLOSURE_VERSION, "imports": sorted(imports),
                              "L2_condicional": sorted(condicionales)}


def medir_l0(conjunto, raiz=RAIZ):
    """l0-budget/v1: ceil(bytes_utf8 / 4), sumado. PROXY, no medicion."""
    total = 0
    for rel in conjunto:
        p = os.path.join(raiz, rel)
        if os.path.isfile(p):
            total += -(-os.path.getsize(p) // 4)
    return total


# vigencia-decisiones/v1  [N] REGLA DECLARADA, con su limite
#
#   Una decision se considera marcada como vigente si su cuerpo contiene
#   alguno de los marcadores en negrita del conjunto declarado. Medido sobre
#   docs/DECISIONES.md: el fichero usa CUATRO redacciones distintas --
#   "**Vigente**" (50), "**Vigente.**" (D-01), "**VIGENTE e IMPLEMENTADA**"
#   (D-21) y solo "**Decision vigente**" dentro de un bullet (D-27).
#
#   LIMITE, y es importante: con esta regla las 53 decisiones salen marcadas.
#   Eso NO significa que ninguna haya sido superada -- significa que
#   DECISIONES.md NO distingue vigente de superada de forma legible por
#   maquina, porque el protocolo prohibe borrar historia y las revisiones se
#   anaden DENTRO de la misma entrada. Esa distincion es una DEUDA ABIERTA;
#   F1 no la resuelve ni la inventa.
VIGENCIA_DECISIONES_VERSION = "vigencia-decisiones/v1"
_MARCADOR_VIGENCIA = re.compile(r"(?i)\*\*(?:decisi[oó]n\s+)?vigente")


def decisiones_vigentes(raiz=RAIZ):
    """IDs marcados como vigentes segun vigencia-decisiones/v1."""
    p = os.path.join(raiz, "docs", "DECISIONES.md")
    if not os.path.isfile(p):
        return []
    trozos = re.split(r"(?m)^##\s+(D-\d+)", open(p, encoding="utf-8").read())
    return [trozos[i] for i in range(1, len(trozos), 2)
            if _MARCADOR_VIGENCIA.search(trozos[i + 1])]


def guardas_superficie(texto):
    """Anti-deriva: exactamente cinco bloques, ni uno mas."""
    bloques = list(_estado.bloques(texto))
    esperados = list(_estado.BLOQUES_SUPERFICIE)
    if bloques == esperados:
        return True, None
    sobra = [b for b in bloques if b not in esperados]
    if sobra:
        return False, (f"{BLOQUE_DESCONOCIDO}: la superficie no admite un SEXTO bloque "
                       f"(ni un septimo): {sobra}")
    return False, f"{BLOQUE_DESCONOCIDO}: faltan bloques {set(esperados) - set(bloques)}"


def bloque_activo(contrato=None):
    """(id, declaracion) del bloque activo. Sin declaracion NO se asume nada:
    devuelve (None, None) y el veredicto sera ALCANCE_NO_DECLARADO."""
    c = contrato or _estado.cargar_contrato()
    bid = c.get("bloque_activo")
    if not bid:
        return None, None
    decl = (c.get("bloques") or {}).get(bid)
    if decl is None:
        return bid, None          # activo pero NO declarado -> sigue fallando
    return bid, decl


# --- Arquitectura objetivo (S0.4) ------------------------------------------
#
#   "esta en la arquitectura"  !=  "esta implementado"
#
# Esa confusion es la que convierte un documento de arquitectura en ficcion a
# los tres meses. Aqui se impide por mecanismo, no por disciplina: IMPLEMENTED
# es el UNICO estado que se DERIVA -- se calcula resolviendo el ancla -- y los
# otros tres son declaraciones de intencion que el codigo no puede deducir.
# La ausencia de codigo no dice si algo esta planificado o prohibido.
#
# Y la comprobacion va en LOS DOS SENTIDOS, que es lo que la hace util:
#   declarar IMPLEMENTED/PARTIAL sin ancla resoluble   -> ANCLA_NO_RESOLUBLE
#   declarar PLANNED/NOT_AUTHORIZED y que exista ancla -> ESTADO_DIVERGENTE
# Lo segundo detecta el caso que de verdad envejece: aparece codigo bajo un
# componente declarado PLANNED y la declaracion se queda obsoleta en silencio.
IMPLEMENTED = "IMPLEMENTED"
PARTIAL = "PARTIAL"
PLANNED = "PLANNED"
NOT_AUTHORIZED = "NOT_AUTHORIZED"

ESTADOS_ARQUITECTURA = (IMPLEMENTED, PARTIAL, PLANNED, NOT_AUTHORIZED)

# Estados que EXIGEN ancla resoluble, y estados que exigen su AUSENCIA.
ESTADOS_CON_ANCLA = (IMPLEMENTED, PARTIAL)
ESTADOS_SIN_ANCLA = (PLANNED, NOT_AUTHORIZED)

ARQUITECTURA_ANCLA_NO_RESOLUBLE = "ARQUITECTURA_ANCLA_NO_RESOLUBLE"
ARQUITECTURA_ESTADO_DIVERGENTE = "ARQUITECTURA_ESTADO_DIVERGENTE"
ARQUITECTURA_ESTADO_DESCONOCIDO = "ARQUITECTURA_ESTADO_DESCONOCIDO"


def componentes_arquitectura(contrato=None):
    c = contrato or _estado.cargar_contrato()
    return ((c.get("arquitectura_objetivo") or {}).get("componentes")) or []


def estado_arquitectura(contrato=None, raiz=RAIZ):
    """[{id, nivel, estado_declarado, ancla, ancla_resuelve, estado_efectivo,
    ok, motivo}] por componente.

    `estado_efectivo` NO se lee del contrato: para IMPLEMENTED se deriva de
    que el ancla exista. Un componente declarado IMPLEMENTED cuyo ancla haya
    desaparecido no sale IMPLEMENTED -- sale con su fallo."""
    out = []
    for comp in componentes_arquitectura(contrato):
        declarado = comp.get("estado_declarado")
        ancla = comp.get("ancla")
        resuelve = bool(ancla) and os.path.exists(os.path.join(raiz, ancla))
        fila = {"id": comp.get("id"), "nivel": comp.get("nivel"),
                "estado_declarado": declarado, "ancla": ancla,
                "ancla_resuelve": resuelve, "estado_efectivo": None,
                "ok": True, "motivo": None}

        if declarado not in ESTADOS_ARQUITECTURA:
            fila.update(ok=False, motivo=(
                f"{ARQUITECTURA_ESTADO_DESCONOCIDO}: {comp.get('id')} declara "
                f"{declarado!r}, fuera de {list(ESTADOS_ARQUITECTURA)}"))
        elif declarado in ESTADOS_CON_ANCLA and not resuelve:
            fila.update(ok=False, motivo=(
                f"{ARQUITECTURA_ANCLA_NO_RESOLUBLE}: {comp.get('id')} declara "
                f"{declarado} pero su ancla {ancla!r} no existe"))
        elif declarado in ESTADOS_SIN_ANCLA and ancla:
            fila.update(ok=False, motivo=(
                f"{ARQUITECTURA_ESTADO_DIVERGENTE}: {comp.get('id')} declara "
                f"{declarado} y sin embargo declara ancla {ancla!r}: si ya hay "
                f"codigo, la declaracion ha quedado obsoleta"))
        else:
            # IMPLEMENTED se DERIVA; los otros tres son la declaracion misma.
            fila["estado_efectivo"] = IMPLEMENTED if (
                declarado == IMPLEMENTED and resuelve) else declarado
        out.append(fila)
    return out


def rango_bloque(bid=None, contrato=None):
    """(desde, hasta, hasta_es_operativo) del bloque.

    BLOQUE = desde + hasta. `desde~1..hasta` es el rango REPRODUCIBLE del
    bloque: los commits que escribio. La guarda se evalua sobre ese rango y
    NO sobre el diff contra la rama base -- un bloque responde de lo que
    escribio, no de lo que la base todavia ignora.

    Mientras el bloque esta abierto, `hasta` es None y quien ejecute resuelve
    a HEAD como valor OPERATIVO (hasta_es_operativo=True). Al cerrar el bloque
    se fija al commit real y el rango queda reproducible para siempre: el
    significado historico de un bloque cerrado no puede depender de HEAD."""
    c = contrato or _estado.cargar_contrato()
    bid = bid or c.get("bloque_activo")
    decl = (c.get("bloques") or {}).get(bid) or {}
    desde, hasta = decl.get("desde"), decl.get("hasta")
    return desde, hasta, (hasta is None)


def superficie_protegida(raiz=RAIZ):
    """Rutas bajo autoridad de la integridad historica. DERIVADAS, nunca
    declaradas aqui.

    Son (a) las claves del manifiesto -- los ficheros de docs/ e informes/
    fijados por sha256 -- y (b) el destino de la extraccion D-PRD-1, cuya
    ancla es byte-exacta.

    CLAUDE.md queda FUERA a proposito: T5 dejo su bloque "Punto de entrada
    obligatorio" explicitamente REESCRIBIBLE y retiro el ancla de la cabecera
    completa. Sus partes intocables (preambulo y privacidad) ya las vigila
    extraccion.py por ancla propia, que el gate de PR ejecuta. Incluirlo aqui
    bloquearia la actualizacion legitima del puntero a la superficie."""
    return _rutas_manifiesto(raiz) | _rutas_extraccion(raiz)


def _rutas_manifiesto(raiz=RAIZ):
    mod = _mod_contexto("integridad", raiz)
    return set(mod.cargar(os.path.join(raiz, "contexto", "manifiesto.json")))


def _rutas_extraccion(raiz=RAIZ):
    return {_mod_contexto("extraccion", raiz).DESTINO}


def _condicion_protegido(ruta, rutas, raiz=RAIZ):
    """(ok, motivo) para una ruta PROTEGIDO_GLOBAL.

    PROTEGIDO_GLOBAL no es "nunca escribible": el protocolo de informes de
    docs/07 EXIGE escribir en docs/ e informes/ al cerrar una fase, asi que
    una prohibicion absoluta haria inejecutable el cierre. Lo que significa
    es que el alcance del bloque NO BASTA -- el permiso lo concede otro
    mecanismo, y por eso ningun bloque puede concederselo a si mismo:

      manifiesto  pasa si contexto/manifiesto.json viaja en el MISMO diff.
                  Entonces integridad.py decide, con su propia autoridad.
      extraccion  pasa si contexto/extraccion.py viaja en el MISMO diff.
                  Misma logica: se toca la AUTORIDAD al lado del dato.

    La simetria importa. Una version anterior de esta funcion no dejaba pasar
    NUNCA el destino de la extraccion, y eso rechazaba al propio bloque que lo
    CREO (T5, 8c38056): crear no es alterar, igual que en el manifiesto una
    ruta nueva es ADDED y no ALTERED. La autorizacion explicita -- mover la
    autoridad en el mismo commit -- distingue las dos cosas sin necesidad de
    una excepcion."""
    if ruta in _rutas_extraccion(raiz):
        if AUTORIDAD_EXTRACCION in rutas:
            return True, None
        return False, (f"{PROTEGIDO_GLOBAL}: {ruta} es el destino de la extraccion "
                       f"D-PRD-1. Crearlo o modificarlo exige mover su autoridad, "
                       f"{AUTORIDAD_EXTRACCION}, en el MISMO commit; ningun bloque "
                       f"puede autorizarselo por alcance")
    if MANIFIESTO in rutas:
        return True, None
    return False, (f"{PROTEGIDO_GLOBAL}: {ruta} esta fijada por hash en {MANIFIESTO}. "
                   f"Modificarla exige regenerar {MANIFIESTO} en el MISMO commit "
                   f"(DF-2), y ningun bloque puede autorizarselo por alcance")


def _mod_contexto(nombre, raiz=RAIZ):
    import importlib
    carpeta = os.path.join(raiz, "contexto")
    sys.path.insert(0, carpeta)
    try:
        return importlib.import_module(nombre)
    finally:
        sys.path.remove(carpeta)


def veredicto_alcance(rutas, contrato=None, raiz=RAIZ):
    """{ruta: veredicto} para el diff completo, por precedencia estricta."""
    bid, decl = bloque_activo(contrato)
    if decl is None:
        return {r: ALCANCE_NO_DECLARADO for r in rutas}, bid
    protegidas = superficie_protegida(raiz)
    escritura = tuple(decl.get("escritura") or ())
    out = {}
    for r in rutas:
        if r in protegidas:
            out[r] = PROTEGIDO_GLOBAL
        elif escritura and r.startswith(escritura):
            out[r] = PERMITIDO
        else:
            out[r] = FUERA_DE_ALCANCE          # denegacion por defecto
    return out, bid


def guarda_alcance(rutas, contrato=None, raiz=RAIZ):
    """(ok, motivo) sobre el diff completo. Fachada estable del veredicto."""
    veredictos, bid = veredicto_alcance(rutas, contrato, raiz)
    if not veredictos:
        return True, None
    sin_declarar = [r for r, v in veredictos.items() if v == ALCANCE_NO_DECLARADO]
    if sin_declarar:
        return False, (f"{ALCANCE_NO_DECLARADO}: bloque_activo={bid!r} no esta "
                       f"declarado en `bloques`; la guarda no asume nada")
    fuera = sorted(r for r, v in veredictos.items() if v == FUERA_DE_ALCANCE)
    if fuera:
        return False, (f"{FUERA_DE_ALCANCE}: el bloque {bid} no declara escritura "
                       f"sobre {fuera}")
    for r in sorted(r for r, v in veredictos.items() if v == PROTEGIDO_GLOBAL):
        ok, motivo = _condicion_protegido(r, rutas, raiz)
        if not ok:
            return False, motivo
    return True, None


def _evidencia_resoluble(ref, raiz=RAIZ):
    if ref.startswith("file:"):
        return os.path.isfile(os.path.join(raiz, ref[5:]))
    if ref.startswith("commit:"):
        import subprocess
        r = subprocess.run(["git", "-C", raiz, "cat-file", "-e", ref[7:] + "^{commit}"],
                           capture_output=True)
        return r.returncode == 0
    return False


def _resolver(canonical_source):
    """`ruta/al/modulo.py::SIMBOLO` -> valor vivo de ese simbolo.

    Importar engine/ es LEER, no modificar: es justamente el sentido de
    CODE-ANCHORED. Nada de este modulo escribe alli."""
    try:
        ruta, simbolo = canonical_source.split("::")
    except ValueError:
        raise ValidacionError(f"canonical_source mal formado: {canonical_source!r}")
    destino = os.path.join(RAIZ, ruta)
    if not os.path.isfile(destino):
        return None, f"{FUENTE_NO_RESOLUBLE}: no existe {ruta}"
    carpeta = os.path.dirname(destino)
    nombre = os.path.basename(destino)[:-3]
    sys.path.insert(0, carpeta)
    try:
        mod = importlib.import_module(nombre)
    except Exception as e:                                   # noqa: BLE001
        return None, f"{FUENTE_NO_RESOLUBLE}: {ruta} no importable ({e})"
    finally:
        sys.path.remove(carpeta)
    if not hasattr(mod, simbolo):
        return None, f"{FUENTE_NO_RESOLUBLE}: {ruta} no define {simbolo}"
    return getattr(mod, simbolo), None


def _normalizar(v):
    """Un frozenset, un set y una lista con los mismos elementos son el
    mismo valor. El orden y el tipo del contenedor no son la verdad."""
    if isinstance(v, (set, frozenset, list, tuple)):
        return sorted(str(x) for x in v)
    return v


def canonical_serialization(v):
    """Serializacion canonica de canonical-fingerprint/v1. Ver cabecera."""
    n = _normalizar(v)
    return "\n".join(n) if isinstance(n, list) else str(n)


def _huella(v):
    """canonical-fingerprint/v1. METADATA DE PROCEDENCIA, no respuesta.

    El validador nunca lo usa para responder la STATE QUERY: solo para
    detectar que la consulta se declaro contra otro estado del codigo."""
    return hashlib.sha256(canonical_serialization(v).encode("utf-8")).hexdigest()


def _renderizaciones(v):
    """Formas en que alguien escribiria ESE valor en la superficie.

    HEURISTICA DECLARADA, con su limite: detecta que el valor completo se
    haya pegado en el documento. Una parafrasis la evadiria. Se acepta
    porque el fallo que importa -- copiar el valor para no tener que
    referenciarlo -- produce siempre una de estas formas."""
    n = _normalizar(v)
    if not isinstance(n, list):
        return {str(n)}
    return {", ".join(n), " \u00b7 ".join(n), " ".join(n),
            json.dumps(n), repr(n), repr(sorted(n))}


def _validar_code_anchored(c, superficie, bloque):
    r = {"query_id": c["query_id"], "class": c["class"], "ok": True, "motivo": None,
         "canonical_source": c["canonical_source"], "valor_resuelto": None}
    valor, error = _resolver(c["canonical_source"])
    if error:
        return dict(r, ok=False, motivo=error)
    r["valor_resuelto"] = _normalizar(valor)
    r["fingerprint_resuelto"] = _huella(valor)

    declarado = c.get("canonical_fingerprint")
    if declarado and declarado != r["fingerprint_resuelto"]:
        return dict(r, ok=False,
                    motivo=f"{DIVERGENCIA_CANONICA}: la fuente canonica cambio desde que se "
                           f"declaro {c['query_id']} (sello {declarado[:12]} != "
                           f"{r['fingerprint_resuelto'][:12]})")
    if c["canonical_source"] not in bloque:
        return dict(r, ok=False,
                    motivo=f"{REFERENCIA_AUSENTE}: la superficie no referencia "
                           f"{c['canonical_source']}")
    if any(x in superficie for x in _renderizaciones(valor)):
        return dict(r, ok=False,
                    motivo=f"{DUPLICACION_COMO_VERDAD}: la superficie almacena el valor de "
                           f"{c['query_id']} en vez de referenciarlo")
    if "value" in c or "valor" in c:
        return dict(r, ok=False,
                    motivo=f"{DUPLICACION_COMO_VERDAD}: el registro almacena el valor de "
                           f"{c['query_id']} en vez de referenciarlo")
    return r


def _validar_ambiguous(c):
    """Una AMBIGUOUS se valida por que SIGUE siendo ambigua, nunca por valor.

    Si las fuentes convergen, la entrada CADUCA y hay que reclasificarla --
    no se auto-resuelve. Es la propiedad que impide que el contexto fabrique
    certeza falsa sobre una pregunta con dos respuestas defendibles."""
    r = {"query_id": c["query_id"], "class": c["class"], "ok": True, "motivo": None,
         "candidate_sources": [f["canonical_source"] for f in c["candidate_sources"]]}
    if "value" in c or "valor" in c:
        return dict(r, ok=False,
                    motivo=f"{AMBIGUEDAD_RESUELTA_EN_SILENCIO}: {c['query_id']} almacena un "
                           f"valor unico para una pregunta con dos respuestas defendibles")
    if len(c["candidate_sources"]) < 2:
        return dict(r, ok=False,
                    motivo=f"{AMBIGUEDAD_RESUELTA_EN_SILENCIO}: una AMBIGUOUS necesita >=2 fuentes")
    valores = []
    for f in c["candidate_sources"]:
        v, err = _resolver(f["canonical_source"])
        if err:
            return dict(r, ok=False, motivo=err)
        valores.append(v)
    if c.get("discrepancy_check") == "interseccion_no_vacia":
        comun = set(_normalizar(valores[0])) & set(_normalizar(valores[1]))
        r["discrepancia"] = sorted(comun)
        if not comun:
            return dict(r, ok=False,
                        motivo=f"{AMBIGUEDAD_RESUELTA_EN_SILENCIO}: las fuentes de "
                               f"{c['query_id']} ya no discrepan; la entrada CADUCO y hay "
                               f"que reclasificarla, no darla por resuelta")
    return r


def _validar_human_asserted(c, raiz):
    """Se verifica TRAZABILIDAD, nunca veracidad. Una afirmacion falsa pero
    bien citada pasa: es el techo declarado de esta arquitectura."""
    r = {"query_id": c["query_id"], "class": c["class"], "ok": True, "motivo": None,
         "asserted_at": c.get("asserted_at"), "evidence_ref": c.get("evidence_ref")}
    if not c.get("asserted_at"):
        return dict(r, ok=False, motivo=f"{AFIRMACION_SIN_FECHA}: {c['query_id']}")
    if not c.get("asserted_by"):
        return dict(r, ok=False, motivo=f"{AFIRMACION_SIN_AUTORIA}: {c['query_id']}")
    ref = c.get("evidence_ref")
    if not ref or not _evidencia_resoluble(ref, raiz):
        return dict(r, ok=False,
                    motivo=f"{EVIDENCIA_NO_RESOLUBLE}: {c['query_id']} cita {ref!r}, que no "
                           f"resuelve a un commit ni a un fichero existente")
    return r


def validar(contrato=None, superficie=None, raiz=RAIZ):
    """Informe por consulta declarada, para las TRES clases.

    T6 COMPLETO: CODE-ANCHORED (igualdad con la fuente), AMBIGUOUS (sigue
    discrepando, sin valor unico) y HUMAN-ASSERTED (trazabilidad).
    """
    contrato = contrato or _estado.cargar_contrato()
    superficie = superficie if superficie is not None else _estado.texto_superficie(contrato)
    bloque = _estado.bloques(superficie).get(contrato["bloque_de_referencias"], "")

    resultados = []
    for c in _estado.consultas(contrato):
        if c["class"] == "CODE-ANCHORED":
            resultados.append(_validar_code_anchored(c, superficie, bloque))
        elif c["class"] == "AMBIGUOUS":
            resultados.append(_validar_ambiguous(c))
        elif c["class"] == "HUMAN-ASSERTED":
            resultados.append(_validar_human_asserted(c, raiz))

    conjunto, detalle = l0_efectivo(raiz)
    l0 = {"metodo_cierre": L0_CLOSURE_VERSION, "metodo_medida": "l0-budget/v1",
          "efectivo": conjunto, "declarado": sorted(contrato.get("L0", [])),
          "tokens": medir_l0(conjunto, raiz), "gate": GATE_L0, **detalle}
    incidencias = []
    if l0["declarado"] != l0["efectivo"]:
        incidencias.append(f"{L0_DIVERGENTE}: declarado {l0['declarado']} != "
                           f"efectivo {l0['efectivo']}")
    if l0["tokens"] > GATE_L0:
        incidencias.append(f"{L0_SOBRE_PRESUPUESTO}: {l0['tokens']} > {GATE_L0}")
    ok_sup, motivo_sup = guardas_superficie(superficie)
    if not ok_sup:
        incidencias.append(motivo_sup)

    arquitectura = estado_arquitectura(contrato, raiz)
    for fila in arquitectura:
        if not fila["ok"]:
            incidencias.append(fila["motivo"])

    return {"arquitectura": arquitectura,
            "consultas_declaradas": len(_estado.consultas(contrato)),
            "fingerprint_version": CANONICAL_FINGERPRINT_VERSION,
            "duplicacion_deteccion": DUPLICACION_HEURISTICA_VERSION,
            "vigencia_decisiones": VIGENCIA_DECISIONES_VERSION,
            "l0": l0, "incidencias": incidencias, "resultados": resultados}


def main(argv=None):
    informe = validar()
    l0 = informe["l0"]
    print(f"CONTEXTO DURABLE - {informe['consultas_declaradas']} consulta(s) declarada(s)")
    print(f"  L0 ({l0['metodo_medida']}, PROXY declarado)  {l0['tokens']} tok / gate {l0['gate']}")
    print(f"     cierre {l0['metodo_cierre']}: {l0['efectivo']}")
    if l0["L2_condicional"]:
        print(f"     L2 condicional (no cuenta): {l0['L2_condicional']}")
    por_clase = {}
    for r in informe["resultados"]:
        por_clase.setdefault(r["class"], []).append(r)
    for clase, rs in sorted(por_clase.items()):
        print(f"  {clase:16s} {len(rs)} consulta(s)")
    arq = informe.get("arquitectura") or []
    if arq:
        conteo = {}
        for f in arq:
            conteo[f["estado_efectivo"] or "FALLO"] = \
                conteo.get(f["estado_efectivo"] or "FALLO", 0) + 1
        derivados = sum(1 for f in arq if f["estado_declarado"] == IMPLEMENTED)
        print(f"  ARQUITECTURA     {len(arq)} componente(s) . "
              + " . ".join(f"{k}={v}" for k, v in sorted(conteo.items())))
        print(f"     IMPLEMENTED derivado del ancla en {derivados}; "
              f"PARTIAL/PLANNED/NOT_AUTHORIZED son declaraciones")
    fallos = [r for r in informe["resultados"] if not r["ok"]]
    for r in fallos:
        print(f"  FAIL {r['query_id']}: {r['motivo']}")
    for inc in informe["incidencias"]:
        print(f"  FAIL {inc}")
    ok = not fallos and not informe["incidencias"]
    print(f"RESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
