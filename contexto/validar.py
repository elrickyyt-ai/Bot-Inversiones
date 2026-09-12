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


def validar(contrato=None, superficie=None):
    """Informe por consulta declarada.

    Sin consultas declaradas, cero resultados: el mecanismo de STATE QUERY
    no existe todavia.

    En T6-SLICE solo se valida CODE-ANCHORED. AMBIGUOUS, HUMAN-ASSERTED y
    UNDECLARED son T6 completo y NO estan implementados."""
    contrato = contrato or _estado.cargar_contrato()
    superficie = superficie if superficie is not None else _estado.texto_superficie(contrato)
    bloque = _estado.bloques(superficie).get(contrato["bloque_de_referencias"], "")

    resultados = []
    for c in _estado.consultas(contrato):
        if c["class"] != "CODE-ANCHORED":
            continue
        r = {"query_id": c["query_id"], "class": c["class"],
             "canonical_source": c["canonical_source"], "ok": True,
             "motivo": None, "valor_resuelto": None}
        valor, error = _resolver(c["canonical_source"])
        if error:
            r.update(ok=False, motivo=error)
            resultados.append(r)
            continue
        r["valor_resuelto"] = _normalizar(valor)
        r["fingerprint_resuelto"] = _huella(valor)

        # 0. El sello de deriva: se declaro contra ESTE estado del codigo.
        declarado = c.get("canonical_fingerprint")
        if declarado and declarado != r["fingerprint_resuelto"]:
            r.update(ok=False, motivo=f"{DIVERGENCIA_CANONICA}: la fuente canonica cambio desde "
                                      f"que se declaro la consulta {c['query_id']} "
                                      f"(sello {declarado[:12]} != {r['fingerprint_resuelto'][:12]})")
            resultados.append(r)
            continue

        # 1. La superficie tiene que REFERENCIAR la fuente.
        if c["canonical_source"] not in bloque:
            r.update(ok=False, motivo=f"{REFERENCIA_AUSENTE}: la superficie no referencia "
                                      f"{c['canonical_source']}")

        # 2. Y NO puede contener el valor: eso es duplicar como verdad.
        elif any(x in superficie for x in _renderizaciones(valor)):
            r.update(ok=False, motivo=f"{DUPLICACION_COMO_VERDAD}: la superficie almacena el "
                                      f"valor de {c['query_id']} en vez de referenciarlo")

        # 3. Si el contrato almacenase el valor, tambien seria duplicacion.
        elif "value" in c or "valor" in c:
            declarado = _normalizar(c.get("value", c.get("valor")))
            if declarado != r["valor_resuelto"]:
                r.update(ok=False, motivo=f"{DIVERGENCIA_CANONICA}: declarado {declarado!r} "
                                          f"!= canonico {r['valor_resuelto']!r}")
            else:
                r.update(ok=False, motivo=f"{DUPLICACION_COMO_VERDAD}: el registro almacena el "
                                          f"valor de {c['query_id']} en vez de referenciarlo")
        resultados.append(r)
    return {"consultas_declaradas": len(_estado.consultas(contrato)),
            "fingerprint_version": CANONICAL_FINGERPRINT_VERSION,
            "duplicacion_deteccion": DUPLICACION_HEURISTICA_VERSION,
            "resultados": resultados}


def main(argv=None):
    informe = validar()
    n = informe["consultas_declaradas"]
    print(f"CONTEXTO DURABLE - {n} consulta(s) declarada(s)")
    fallos = [r for r in informe["resultados"] if not r["ok"]]
    for r in fallos:
        print(f"  FAIL {r['query_id']}: {r['motivo']}")
    print(f"RESULTADO: {'FAIL' if fallos else 'PASS'}")
    return 1 if fallos else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
