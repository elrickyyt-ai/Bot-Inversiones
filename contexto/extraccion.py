# -*- coding: utf-8 -*-
"""Integridad de D-PRD-1: la extraccion de CLAUDE.md. T5 de F1 (2026-09-12).

MECANISMO SEPARADO, a proposito (precision P-1 del contrato):

    MANIFIESTO PRINCIPAL   docs/ + informes/   43 .md   MOVED = 0
    D-PRD-1 INTEGRITY      CLAUDE.md seccion -> destino historico

La extraccion NO es una entrada `ADDED` del manifiesto principal. Si lo
fuera, el destino tendria que vivir en docs/ o informes/ y el manifiesto
se estaria verificando a si mismo. Por eso el destino vive fuera de esos
dos arboles y su integridad se comprueba aqui.

QUE PROTEGE D-PRD-1 (H-5, opcion A)
-----------------------------------
1. El contenido historico extraido      -> ancla COMPLETA del fichero
2. Dos secciones de CLAUDE.md que NO deben cambiar:
       preambulo   251 B
       privacidad  834 B
   El bloque "Punto de entrada obligatorio" (794 B) es REESCRIBIBLE: su
   modificacion es parte deliberada de T5 y NO tiene ancla propia. El
   hash 639266a8... de la cabecera completa quedo RETIRADO como ancla
   contractual.

Este modulo no escribe nada. Solo lee y verifica.
"""
import hashlib
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MARCA_SECCION = "## Estado del proyecto"
DESTINO = "contexto/historico/claude_md_estado_previo_a_F1.md"

# Anclas contractuales. Medidas sobre CLAUDE.md@e924a3e2, repositorio@3b008f0.
ANCLA_EXTRACCION = "ff2003f9d59a162f9c6d753dddbb9c57ff5ba1881bcd593e0ee4a1840c75a9b5"
ANCLA_PREAMBULO = "949372999c924487"    # prefijo; 251 bytes
ANCLA_PRIVACIDAD = "e0e046e1d8bc7e9a"   # prefijo; 834 bytes

ORIGEN = {"fichero": "CLAUDE.md", "seccion": MARCA_SECCION,
          "momento": "estado previo a F1",
          "fichero_sha256": "e924a3e20cf3b209456b6e3b7df09358438941edf9d98d2d89c7c44211b11e16",
          "repositorio": "3b008f0"}

# Estados de dominio. NO se usan excepciones de sistema para decir que la
# extraccion no se ha hecho: eso produciria un RED invalido.
OK = "OK"
EXTRACCION_NO_REALIZADA = "EXTRACCION_NO_REALIZADA"
ANCLA_ROTA = "ANCLA_ROTA"
COPIA_PARCIAL = "COPIA_PARCIAL"
SECCION_NO_ELIMINADA = "SECCION_NO_ELIMINADA"
ANCLA_CABECERA_ROTA = "ANCLA_CABECERA_ROTA"
PROCEDENCIA_NO_RESOLUBLE = "PROCEDENCIA_NO_RESOLUBLE"

# copia-parcial/v1 -- HEURISTICA DECLARADA, misma disciplina que heuristic/v1
# (D-2). Detecta la marca de la seccion y cualquier linea larga y distintiva
# del contenido extraido que siga en CLAUDE.md. NO es prueba formal de
# ausencia: una parafrasis la evadiria.
#     heuristic detection != formal proof of absence
COPIA_PARCIAL_VERSION = "copia-parcial/v1"
LONGITUD_LINEA_DISTINTIVA = 80


def _sha256(b):
    return hashlib.sha256(b).hexdigest()


def partes_originales(texto):
    """Las cuatro piezas de CLAUDE.md tal como estaba antes de T5."""
    i = texto.index(MARCA_SECCION)
    cab = texto[:i]
    j = cab.index("## Punto de entrada obligatorio")
    k = cab.index("## Protocolo obligatorio de privacidad")
    return {"preambulo": cab[:j], "entrada": cab[j:k],
            "privacidad": cab[k:], "seccion": texto[i:]}


def verificar(raiz=RAIZ, texto_claude=None, bytes_destino=None):
    """Devuelve (ok, incidencias). Las incidencias son estados de dominio.

    `texto_claude` y `bytes_destino` permiten mutar en memoria sin tocar
    los ficheros reales -- es como se prueban M3 y M4.
    """
    incidencias = []

    destino = os.path.join(raiz, DESTINO)
    if bytes_destino is None:
        if not os.path.isfile(destino):
            return False, [(EXTRACCION_NO_REALIZADA,
                            f"la extraccion de D-PRD-1 no se ha realizado: no existe {DESTINO}")]
        bytes_destino = open(destino, "rb").read()

    # 1. El contenido extraido, con su ancla COMPLETA de fichero.
    h = _sha256(bytes_destino)
    if h != ANCLA_EXTRACCION:
        incidencias.append((ANCLA_ROTA,
                            f"el destino no coincide con el ancla contractual "
                            f"({h[:12]} != {ANCLA_EXTRACCION[:12]})"))

    if texto_claude is None:
        texto_claude = open(os.path.join(raiz, "CLAUDE.md"), encoding="utf-8").read()

    # 2. La seccion desaparece por completo de CLAUDE.md.
    if MARCA_SECCION in texto_claude:
        incidencias.append((SECCION_NO_ELIMINADA,
                            f"CLAUDE.md sigue conteniendo {MARCA_SECCION!r}"))

    # 3. Y no queda ningun rastro distintivo del contenido extraido.
    extraido = bytes_destino.decode("utf-8", errors="replace")
    for linea in extraido.split("\n"):
        l = linea.strip()
        if len(l) >= LONGITUD_LINEA_DISTINTIVA and l in texto_claude:
            incidencias.append((COPIA_PARCIAL,
                                f"CLAUDE.md conserva una copia parcial del estado extraido: "
                                f"{l[:60]}..."))
            break

    # 4. Las dos secciones protegidas por H-5, byte a byte.
    try:
        j = texto_claude.index("## Punto de entrada obligatorio")
        k = texto_claude.index("## Protocolo obligatorio de privacidad")
    except ValueError:
        incidencias.append((ANCLA_CABECERA_ROTA,
                            "CLAUDE.md ya no tiene los bloques de entrada y privacidad"))
        return (not incidencias), incidencias
    for nombre, trozo, ancla in (("preambulo", texto_claude[:j], ANCLA_PREAMBULO),
                                 ("privacidad", texto_claude[k:], ANCLA_PRIVACIDAD)):
        real = _sha256(trozo.encode("utf-8"))
        if not real.startswith(ancla):
            incidencias.append((ANCLA_CABECERA_ROTA,
                                f"el bloque {nombre} cambio ({real[:16]} != {ancla})"))

    return (not incidencias), incidencias


def procedencia(raiz=RAIZ):
    """Responde: de donde procede este contenido historico."""
    destino = os.path.join(raiz, DESTINO)
    if not os.path.isfile(destino):
        return None, PROCEDENCIA_NO_RESOLUBLE
    d = dict(ORIGEN)
    d["destino"] = DESTINO
    d["ancla"] = ANCLA_EXTRACCION
    d["coincide"] = _sha256(open(destino, "rb").read()) == ANCLA_EXTRACCION
    return d, None


def main(argv=None):
    ok, incidencias = verificar()
    print(f"D-PRD-1 INTEGRITY - {DESTINO}")
    p, err = procedencia()
    if p:
        print(f"  procede de  {p['fichero']} -> {p['seccion']!r} -> {p['momento']}")
        print(f"              {p['fichero']}@{p['fichero_sha256'][:8]}  repo@{p['repositorio']}")
        print(f"  ancla       {p['ancla'][:24]}...  coincide={p['coincide']}")
    else:
        print(f"  procedencia {err}")
    for estado, msg in incidencias:
        print(f"  [{estado}] {msg}")
    print(f"RESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
