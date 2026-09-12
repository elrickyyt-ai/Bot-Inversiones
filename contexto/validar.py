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


def _huella(v):
    """Sello del valor normalizado. NO es el valor: el validador nunca lo
    usa para responder la pregunta, solo para detectar que el contexto se
    declaro contra otro estado del codigo."""
    n = _normalizar(v)
    base = "\n".join(n) if isinstance(n, list) else str(n)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


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
    return {"consultas_declaradas": len(_estado.consultas(contrato)), "resultados": resultados}


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
