# -*- coding: utf-8 -*-
"""Guarda de alcance conectada al diff real de un PR. T9 de F1 (2026-09-12).

NO REIMPLEMENTA NINGUNA REGLA. La regla vive en `validar.guarda_alcance()`
y aqui solo se hacen dos cosas:

    1. obtener el diff real           git diff --name-only base..head
    2. delegar en la autoridad        validar.guarda_alcance(rutas)

Si este modulo llegara a contener una segunda copia de la regla -- una lista
de arboles prohibidos, por ejemplo -- seria un defecto de diseno, no una
optimizacion.

POR QUE EXISTE UN INTERRUPTOR
-----------------------------
El alcance "no tocar engine/, data/ ni knowledge/" es del BLOQUE F1, no del
repositorio para siempre. El siguiente bloque de producto (AssessmentContract)
tiene que tocar engine/ por definicion. Un gate permanente bloquearia el
roadmap entero, asi que la vigencia se DECLARA en el contrato y apagarla es
un acto explicito y revisable, no editar un YAML a escondidas.
"""
import os
import subprocess

import estado as _estado
import validar as _validar

RAIZ = _estado.RAIZ

ALCANCE_NO_DECLARADO = "ALCANCE_NO_DECLARADO"


def alcance_vigente(contrato=None):
    """(vigente, declaracion). Sin declaracion no se asume nada."""
    c = contrato or _estado.cargar_contrato()
    d = c.get("alcance_bloque")
    if not d:
        return None, None
    return bool(d.get("vigente")), d


def ficheros_cambiados(base=None, head="HEAD", raiz=RAIZ):
    """Diff real. Sin base, se compara con el primer padre de head."""
    rango = f"{base}..{head}" if base else f"{head}~1..{head}"
    r = subprocess.run(["git", "-C", raiz, "diff", "--name-only", rango],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git diff fallo: {r.stderr.strip()}")
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def verificar(rutas, contrato=None):
    """(codigo_salida, motivo). Delega la REGLA; decide solo si se aplica."""
    vigente, decl = alcance_vigente(contrato)
    if vigente is None:
        return 1, (f"{ALCANCE_NO_DECLARADO}: el contrato no declara `alcance_bloque`; "
                   f"la guarda no puede saber si aplica")
    if not vigente:
        return 0, f"alcance de {decl.get('bloque')} no vigente: la guarda no aplica"
    ok, motivo = _validar.guarda_alcance(rutas)
    return (0 if ok else 1), motivo


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Guarda de alcance sobre el diff de un PR.")
    ap.add_argument("--base", default=os.environ.get("BASE_SHA") or None)
    ap.add_argument("--head", default=os.environ.get("HEAD_SHA") or "HEAD")
    args = ap.parse_args(argv)

    rutas = ficheros_cambiados(args.base, args.head)
    codigo, motivo = verificar(rutas)
    vigente, decl = alcance_vigente()
    print(f"GUARDA DE ALCANCE - {len(rutas)} fichero(s) en el diff")
    if decl:
        print(f"  bloque {decl.get('bloque')} . vigente={vigente}")
    for r in rutas[:20]:
        print(f"    {r}")
    if len(rutas) > 20:
        print(f"    ... y {len(rutas) - 20} mas")
    if motivo:
        print(f"  {motivo}")
    print(f"RESULTADO: {'PASS' if codigo == 0 else 'FAIL'}")
    return codigo


if __name__ == "__main__":
    import sys
    sys.exit(main())
