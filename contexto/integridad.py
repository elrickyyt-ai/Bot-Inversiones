# -*- coding: utf-8 -*-
"""Integridad del contenido historico. T1 de F1 (2026-09-12).

    Ningun contenido historico se pierde ni se altera.

NO se usa "el historico no cambia". La diferencia importa: F1 podria
reorganizar estructura en el futuro, y la propiedad real es la
CONSERVACION DEL CONTENIDO, no la inmovilidad de las rutas.

POR QUE NO SE REUTILIZA EL PATRON DE P5A
----------------------------------------
`tests/test_caminos.py` comprueba invariancia concatenando los CONTENIDOS
de los ficheros en orden y hasheando el resultado. Para lo que hace P5A
-- demostrar que un recorrido no escribe -- es suficiente. Aqui no lo es,
y se midio por que: ese patron no registra rutas ni numero de ficheros,
de modo que un renombrado, un movimiento de contenido entre dos ficheros
o una particion con los mismos bytes en el mismo orden pasan INVISIBLES.

Y renombrar, mover y partir es exactamente el trabajo que F1 podria hacer.
Por eso aqui el manifiesto es `ruta -> sha256`, por fichero, y la
comparacion mira las rutas Y los contenidos por separado.

Este modulo NO modifica ningun fichero. Solo lee.
"""
import hashlib
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Alcance del manifiesto principal (precision P-1 del contrato): SOLO
# docs/ e informes/. La extraccion de CLAUDE.md (D-PRD-1, ticket T5) se
# verifica con un mecanismo separado y NO es una entrada `ADDED` de aqui.
ARBOLES = ("docs", "informes")
EXTENSIONES = (".md",)

# engine/, data/ y knowledge/ quedan FUERA a proposito: ya los cubren
# qa.py, consulta.py --validar y la suite. Duplicarlo seria ruido.

PRESERVED = "PRESERVED"   # misma ruta, mismo contenido
MOVED = "MOVED"           # contenido identico, ruta distinta, DECLARADO
ADDED = "ADDED"           # ruta nueva, DECLARADA
LOST = "LOST"             # ruta desaparecida sin declaracion -> siempre falla
ALTERED = "ALTERED"       # misma ruta, contenido distinto -> siempre falla

ESTADOS = (PRESERVED, MOVED, ADDED, LOST, ALTERED)

# LOST y ALTERED no tienen flag de excepcion y no deben tenerlo nunca:
# son la propiedad entera de este modulo.
ESTADOS_QUE_FALLAN = (LOST, ALTERED)


class IntegridadError(Exception):
    pass


def _sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def generar(raiz=RAIZ):
    """Manifiesto `ruta relativa -> sha256` del contenido historico."""
    m = {}
    for arbol in ARBOLES:
        base = os.path.join(raiz, arbol)
        if not os.path.isdir(base):
            continue
        for carpeta, _, ficheros in os.walk(base):
            for f in sorted(ficheros):
                if not f.endswith(EXTENSIONES):
                    continue
                p = os.path.join(carpeta, f)
                m[os.path.relpath(p, raiz).replace(os.sep, "/")] = _sha256(p)
    return dict(sorted(m.items()))


def comparar(anterior, actual, movimientos=(), adiciones=()):
    """Clasifica cada ruta en uno de los cinco estados.

    `movimientos` es una lista de pares (ruta_antigua, ruta_nueva) y
    `adiciones` una lista de rutas nuevas. Ambas son DECLARACIONES: lo que
    no se declara y cambia, falla. Esa es la mitad del mecanismo -- la
    otra mitad es que el contenido coincida.
    """
    mov = {a: b for a, b in movimientos}
    add = set(adiciones)
    resultado = {}

    for ruta, h in anterior.items():
        if ruta in mov:
            destino = mov[ruta]
            if actual.get(destino) == h:
                resultado[destino] = MOVED
            else:
                # Movimiento declarado pero el contenido no coincide: es una
                # alteracion disfrazada de movimiento, y es peor que ambas.
                resultado[destino] = ALTERED
            continue
        if ruta not in actual:
            resultado[ruta] = LOST
        elif actual[ruta] != h:
            resultado[ruta] = ALTERED
        else:
            resultado[ruta] = PRESERVED

    for ruta in actual:
        if ruta in resultado:
            continue
        # Ruta nueva: solo es legitima si esta declarada.
        resultado[ruta] = ADDED if ruta in add else LOST
    return resultado


def _contenidos(m):
    return sorted(m.values())


def verificar(anterior, actual, movimientos=(), adiciones=(), exigir_cero_movimientos=False):
    """Las TRES comprobaciones. Devuelve (ok, incidencias, resultado).

    H-a  el conjunto de CONTENIDOS se conserva        -> perdida, truncamiento, alteracion
    H-b  el conjunto de RUTAS se conserva salvo
         MOVED/ADDED declarados                        -> movimiento o borrado silencioso
    H-c  MOVED == 0 en este bloque                     -> cualquier movimiento es un error aqui

    H-b es lo que el patron concatenado de P5A no podia hacer.
    """
    resultado = comparar(anterior, actual, movimientos, adiciones)
    incidencias = []

    # H-a: todo contenido que existia sigue existiendo en alguna ruta.
    antes, ahora = _contenidos(anterior), set(actual.values())
    for ruta, h in anterior.items():
        if h not in ahora:
            incidencias.append(("H-a", f"contenido perdido o alterado: {ruta}"))

    # H-b: ninguna ruta cambia sin declaracion.
    for ruta, estado in sorted(resultado.items()):
        if estado in ESTADOS_QUE_FALLAN:
            incidencias.append(("H-b", f"{estado}: {ruta}"))

    # H-c: en este bloque no se mueve nada dentro de docs/ + informes/.
    if exigir_cero_movimientos:
        movidos = [r for r, e in resultado.items() if e == MOVED]
        if movidos:
            incidencias.append(("H-c", f"MOVED debe ser 0 en este bloque: {sorted(movidos)}"))

    return (not incidencias), incidencias, resultado


def cargar(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["ficheros"]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Integridad del contenido historico.")
    ap.add_argument("--manifiesto", default=os.path.join(RAIZ, "contexto", "manifiesto.json"))
    ap.add_argument("--generar", action="store_true", help="imprime el manifiesto actual")
    args = ap.parse_args(argv)

    actual = generar()
    if args.generar:
        print(json.dumps({"alcance": list(ARBOLES), "extensiones": list(EXTENSIONES),
                          "n": len(actual), "ficheros": actual},
                         indent=1, ensure_ascii=False, sort_keys=True))
        return 0

    anterior = cargar(args.manifiesto)
    ok, incidencias, resultado = verificar(anterior, actual, exigir_cero_movimientos=True)
    conteo = {e: sum(1 for v in resultado.values() if v == e) for e in ESTADOS}
    print(f"INTEGRIDAD HISTORICA - {len(actual)} fichero(s) en {'/'.join(ARBOLES)}")
    print("  " + " . ".join(f"{e}={conteo[e]}" for e in ESTADOS))
    for regla, msg in incidencias:
        print(f"  [{regla}] {msg}")
    print(f"RESULTADO: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
