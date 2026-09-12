# -*- coding: utf-8 -*-
"""Indice de alcanzabilidad del contexto. T7 / S6 de F1 (2026-09-12).

    Indice ESTRUCTURAL generado. NO es un resolvedor semantico.

Responde "que se alcanza desde donde y por que clase de arista", no "que
decision introdujo este comportamiento". Esa segunda pregunta es indice
semantico y esta explicitamente fuera de F1: se responde con `git log -S`
y con la cadena de revisiones de docs/DECISIONES.md.

LO QUE VERIFICA -- las tres fronteras del modelo de contexto:

    DURABLE  --VALIDATES-->  REGENERABLE      referencia y valida
    DURABLE  --POINTS----->  HISTORICAL       apunta, no incorpora
    REGENERABLE  -X->  HISTORICAL             sin arco (dentro del grafo)

Y la propiedad que sostiene el presupuesto:

    POINTER NO EXPANDE L0

L0 NO SE REDEFINE AQUI. La autoridad sigue siendo T3
(`validar.l0_efectivo()`): este modulo lo CONSUME para clasificar, nunca
lo reimplementa.

Este modulo no escribe nada. Solo lee.
"""
import os
import re

import estado as _estado
import validar as _validar

RAIZ = _estado.RAIZ

# clasificacion-nodos/v1  [N] por prefijo declarado, no por adivinacion
DURABLE = "DURABLE"
REGENERABLE = "REGENERABLE"
HISTORICAL = "HISTORICAL"
OTRO = "OTRO"
CLASIFICACION_VERSION = "clasificacion-nodos/v1"

ARBOLES_HISTORICOS = ("docs/", "informes/", "contexto/historico/")
EXTENSIONES_REGENERABLES = (".py",)

# relacion-contexto/v1  [N] cuatro relaciones, una sola expande L0
MANDATORY_READ = "MANDATORY_READ"   # UNICA que expande L0 (autoridad: T3)
VALIDATES = "VALIDATES"             # durable -> fuente canonica declarada
POINTS = "POINTS"                   # durable -> historico
REFERENCE = "REFERENCE"             # mencion que no es ninguna de las anteriores
RELACIONES = (MANDATORY_READ, VALIDATES, POINTS, REFERENCE)
RELACION_VERSION = "relacion-contexto/v1"

RELACIONES_QUE_EXPANDEN_L0 = (MANDATORY_READ,)

# Motivos de dominio
ARCO_PROHIBIDO = "ARCO_PROHIBIDO"
POINTER_EXPANDE_L0 = "POINTER_EXPANDE_L0"
RELACION_DESCONOCIDA = "RELACION_DESCONOCIDA"
L0_NO_ALCANZABLE = "L0_NO_ALCANZABLE"

_EXT = r"(?:md|py|json|csv|ya?ml)"
_TOKEN_RUTA = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./\-]*\." + _EXT)
_BACKTICKS = re.compile(r"`([^`\n]+)`")
_ENLACE_MD = re.compile(r"\]\(([^)\s]+)\)")


def clasificar(ruta, l0):
    """clasificacion-nodos/v1. DURABLE es exactamente el L0 de T3."""
    if ruta in l0:
        return DURABLE
    if ruta.startswith(ARBOLES_HISTORICOS):
        return HISTORICAL
    if ruta.endswith(EXTENSIONES_REGENERABLES):
        return REGENERABLE
    return OTRO


def fuentes_canonicas(contrato=None):
    """Ficheros declarados como fuente canonica en el contrato."""
    c = contrato or _estado.cargar_contrato()
    out = set()
    for q in _estado.consultas(c):
        if q.get("canonical_source"):
            out.add(q["canonical_source"].split("::")[0])
        for f in q.get("candidate_sources", []):
            out.add(f["canonical_source"].split("::")[0])
    return out


_TOKEN_DIR = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./\-]*/")


def _rutas_citadas(texto, raiz):
    """Rutas que un documento menciona y que existen de verdad.

    Se aceptan ficheros y DIRECTORIOS: `informes/` es un puntero legitimo
    al registro historico aunque no nombre un informe concreto."""
    brutos = []
    for span in _BACKTICKS.findall(texto):
        brutos += _TOKEN_RUTA.findall(span)
        brutos += _TOKEN_DIR.findall(span)
    brutos += _ENLACE_MD.findall(texto)
    vistas = []
    for r in brutos:
        r = r.strip().lstrip("./")
        if r and os.path.exists(os.path.join(raiz, r)) and r not in vistas:
            vistas.append(r)
    return vistas


def _en_l0_por_carga_automatica(ruta):
    """Regla (a) de T3: todo CLAUDE.md del arbol se carga solo."""
    return os.path.basename(ruta) == "CLAUDE.md"


def _relacion(clase_origen, destino, clase_destino, canonicas):
    """relacion-contexto/v1. Una sola relacion expande L0.

    MANDATORY_READ solo cuando el destino esta en L0 *porque alguien lo
    declaro*. Un CLAUDE.md esta en L0 por la regla (a) de T3 -- carga
    automatica --, no porque otro fichero lo declare: citarlo es REFERENCE.
    Esta distincion es la que impide que el indice invente una expansion
    de L0 que T3 no hizo."""
    if clase_destino == DURABLE and os.path.basename(destino) != "CLAUDE.md":
        return MANDATORY_READ
    if clase_destino == HISTORICAL:
        return POINTS
    if clase_origen == DURABLE and destino in canonicas:
        return VALIDATES
    return REFERENCE


def indice(raiz=RAIZ, contrato=None):
    """Indice determinista del grafo de contexto, enraizado en L0.

    Se expande desde los nodos DURABLE y desde las fuentes canonicas
    declaradas. NO se recorre engine/ entero: el indice describe el GRAFO
    DE CONTEXTO, no el repositorio."""
    l0, _ = _validar.l0_efectivo(raiz)
    canonicas = fuentes_canonicas(contrato)

    nodos, aristas, vistos = {}, [], set()
    pendientes = list(l0)
    while pendientes:
        origen = pendientes.pop(0)
        if origen in vistos:
            continue
        vistos.add(origen)
        clase_o = clasificar(origen, l0)
        nodos[origen] = clase_o
        ruta = os.path.join(raiz, origen)
        if not os.path.isfile(ruta):
            continue
        # Se expande desde lo durable y desde las fuentes canonicas. Nada mas.
        if clase_o == HISTORICAL or (clase_o == REGENERABLE and origen not in canonicas):
            continue
        texto = open(ruta, encoding="utf-8", errors="replace").read()
        for destino in _rutas_citadas(texto, raiz):
            if destino == origen:
                continue
            clase_d = clasificar(destino, l0)
            nodos.setdefault(destino, clase_d)
            aristas.append({"origen": origen, "clase_origen": clase_o,
                            "relacion": _relacion(clase_o, destino, clase_d, canonicas),
                            "destino": destino, "clase_destino": clase_d})
            if destino not in vistos:
                pendientes.append(destino)

    return {"clasificacion": CLASIFICACION_VERSION, "relaciones": RELACION_VERSION,
            "l0": sorted(l0), "canonicas": sorted(canonicas),
            "nodos": dict(sorted(nodos.items())),
            "aristas": _ordenar(aristas)}


def _ordenar(aristas):
    """Orden total y estable: el indice no puede depender del filesystem."""
    unicas = {(a["origen"], a["relacion"], a["destino"]): a for a in aristas}
    return [unicas[k] for k in sorted(unicas)]


def serializar(idx):
    """Serializacion determinista, independiente del orden incidental."""
    if not idx.get("aristas"):
        return ""
    L = [f"# indice de alcanzabilidad del contexto",
         f"# {idx['clasificacion']} . {idx['relaciones']}",
         f"# nodos={len(idx['nodos'])} aristas={len(idx['aristas'])}", ""]
    for a in _ordenar(idx["aristas"]):
        L.append(f"{a['origen']}\t{a['clase_origen']}\t{a['relacion']}\t"
                 f"{a['destino']}\t{a['clase_destino']}")
    return "\n".join(L) + "\n"


def verificar(idx):
    """(ok, incidencias) sobre las fronteras del modelo de contexto."""
    incidencias = []
    l0 = set(idx.get("l0", []))
    if not idx.get("aristas"):
        return False, [(L0_NO_ALCANZABLE, "el indice de alcanzabilidad no esta generado")]

    for rel in l0:
        if rel not in idx["nodos"]:
            incidencias.append((L0_NO_ALCANZABLE, f"{rel} esta en L0 y no es nodo del indice"))

    for a in idx["aristas"]:
        if a["relacion"] not in RELACIONES:
            incidencias.append((RELACION_DESCONOCIDA,
                                f"{a['origen']} -> {a['destino']}: {a['relacion']}"))
        # Arco 3: dentro del grafo de contexto no existe.
        if a["clase_origen"] == REGENERABLE and a["clase_destino"] == HISTORICAL:
            incidencias.append((ARCO_PROHIBIDO,
                                f"{a['origen']} ({REGENERABLE}) -> {a['destino']} "
                                f"({HISTORICAL}): el codigo es el presente, el historico "
                                f"es el registro; no hay arco directo"))
        # Un puntero NO expande el contexto obligatorio.
        # Excepcion: un CLAUDE.md esta en L0 por la regla (a) de T3 -- carga
        # automatica --, no porque nadie lo cite. Citarlo no expande nada.
        if (a["relacion"] not in RELACIONES_QUE_EXPANDEN_L0 and a["destino"] in l0
                and not _en_l0_por_carga_automatica(a["destino"])):
            incidencias.append((POINTER_EXPANDE_L0,
                                f"{a['destino']} se alcanza por {a['relacion']} y esta en L0"))
        if a["relacion"] in RELACIONES_QUE_EXPANDEN_L0 and a["destino"] not in l0:
            incidencias.append((POINTER_EXPANDE_L0,
                                f"{a['origen']} -> {a['destino']} se marca "
                                f"{a['relacion']} pero T3 no lo puso en L0"))
    return (not incidencias), incidencias


def main(argv=None):
    idx = indice()
    ok, incidencias = verificar(idx)
    print(serializar(idx).rstrip() or "INDICE DE ALCANZABILIDAD - no generado")
    for estado_, msg in incidencias:
        print(f"  [{estado_}] {msg}")
    print(f"RESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
