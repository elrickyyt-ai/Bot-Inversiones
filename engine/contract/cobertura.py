"""Cobertura y frescura por entidad x dominio -- P1b (2026-09-06).

DOS EJES ORTOGONALES, no un unico enum de cinco estados:

    cobertura  AVAILABLE | PARTIAL | MISSING | NOT_APPLICABLE | UNKNOWN
               responde "¿existe el dato?"
    frescura   FRESH | LAGGING | STALE | UNKNOWN
               responde "¿sigue valiendo?"

Son preguntas independientes y un dominio puede estar disponible y
caducado a la vez: IBM/fundamental tiene sus 14 metricas (AVAILABLE) y
cinco de ellas con decenas de sesiones de retraso (STALE). Colapsarlos
en un solo enum obliga a elegir cual de las dos verdades se oculta.

En los dos ejes, UNKNOWN significa "no habia declaracion con la que
comparar" y NO es permisivo.

El estado de un dominio es el de su PEOR componente, nunca el del mas
reciente: con la regla del maximo, IBM/fundamental saldria al dia
porque sus nueve metricas trimestrales lo estan.

DEPENDENCIAS (mismo criterio por capas que qa.py): por defecto lee solo
incoming/ con la biblioteca estandar, sin PyArrow, para poder correr en
el cron diario. Una metrica cuya ultima fila viva en history/ (ningun
dato en el año en curso) queda declarada UNKNOWN con su motivo, no
tratada como ausente. Con --con-history se abre tambien el parquet y
esas pasan a tener estado real.

Uso:
    python3 engine/contract/cobertura.py                 tabla + data/coverage.json
    python3 engine/contract/cobertura.py --con-history   incluye history/ (PyArrow)
    python3 engine/contract/cobertura.py --solo-tabla    no escribe el JSON
"""
import argparse
import datetime
import json
import os
import sys

import cadencias
import storage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COVERAGE_PATH = os.path.join(storage.DATA_DIR, "coverage.json")

ORDEN_FRESCURA = {"FRESH": 0, "LAGGING": 1, "STALE": 2, "UNKNOWN": 3}


def _trading_calendar():
    """trading_calendar.py vive en engine/technical/ y es stdlib puro.
    Se importa igual que adapters.py importa los motores."""
    path = os.path.join(ROOT, "engine", "technical")
    sys.path.insert(0, path)
    try:
        if "trading_calendar" in sys.modules:
            del sys.modules["trading_calendar"]
        return __import__("trading_calendar")
    finally:
        sys.path.remove(path)


def _sesiones_transcurridas(desde, hasta, tipo, tc):
    """Sesiones de mercado en el intervalo (desde, hasta] -- es decir,
    cuantas oportunidades de publicar un dato nuevo ha habido desde la
    ultima que se aprovecho. El dia del propio dato no cuenta.

    No es sessions_skipped_between() a secas: esa funcion es
    exclusive-exclusive y por tanto no cuenta el dia de hoy, asi que un
    dato de anteayer y uno de ayer darian el mismo numero.

        equity  vie 04 -> dom 06   0   (el domingo no es sesion)
        equity  vie 04 -> lun 07   1
        crypto  vie 04 -> dom 06   2   (el mercado no cierra)
        cualquiera, mismo dia      0
    """
    if hasta <= desde:
        return 0
    n = tc.sessions_skipped_between(desde, hasta, tipo)
    return n + (1 if tc.is_trading_day(hasta, tipo) else 0)


def retraso(asset_type, domain, metric, data_as_of, hoy, tc=None):
    """(retraso, unidad) en la unidad declarada, o (None, None) si no hay
    declaracion. El retraso es "cuanto ha pasado desde el dato", medido
    en la unidad en que la fuente publica: sesiones de mercado para lo
    que se publica por sesion, dias naturales para lo que se publica por
    calendario. Un sabado no es una sesion perdida para una accion y si
    es un dia perdido para una criptomoneda."""
    cad = cadencias.cadencia(domain, metric)
    if cad is None:
        return None, None
    unidad, _ = cad
    if unidad == cadencias.SESION:
        tc = tc or _trading_calendar()
        tipo = "equity" if asset_type == "equity" else "crypto"
        return _sesiones_transcurridas(data_as_of, hoy, tipo, tc), unidad
    return (hoy - data_as_of).days, unidad


def estado_frescura(asset_type, domain, metric, data_as_of, hoy, tc=None):
    """FRESH mientras no se haya pasado un periodo de cadencia entero,
    LAGGING hasta dos, STALE a partir de ahi.

    n es cada cuanto la fuente publica, no una tolerancia arbitraria: un
    IPC de 67 dias esta FRESH porque su cadencia declarada son 75, y una
    serie diaria con 3 sesiones de retraso esta STALE aunque lleve menos
    dias. Un umbral fijo en dias los clasificaria a los dos al reves."""
    cad = cadencias.cadencia(domain, metric)
    if cad is None:
        return "UNKNOWN", None, None
    _, n = cad
    r, unidad = retraso(asset_type, domain, metric, data_as_of, hoy, tc)
    if r <= n:
        return "FRESH", r, unidad
    if r <= 2 * n:
        return "LAGGING", r, unidad
    return "STALE", r, unidad


def _peor(a, b):
    if a is None:
        return b
    if ORDEN_FRESCURA[b[0]] > ORDEN_FRESCURA[a[0]]:
        return b
    if ORDEN_FRESCURA[b[0]] == ORDEN_FRESCURA[a[0]]:
        ra, rb = a[1], b[1]
        if ra is not None and rb is not None and rb > ra:
            return b
    return a


def _estado_cobertura(esperadas, presentes, sin_aplicar):
    if esperadas is None:
        return "UNKNOWN", set()
    efectivas = esperadas - sin_aplicar
    if not efectivas:
        return "NOT_APPLICABLE", set()
    faltan = efectivas - presentes
    if faltan == efectivas:
        return "MISSING", faltan
    if faltan:
        return "PARTIAL", faltan
    return "AVAILABLE", set()


def evaluar(hoy=None, con_history=False):
    hoy = hoy or datetime.date.today()
    tc = _trading_calendar()

    activos = sorted(set(storage.assets_en_incoming()) | set(storage.assets_en_history()))
    ultimo = {}   # (asset, domain, metric) -> {data_as_of, retrieved_at, asset_type}
    for a in activos:
        tipo = storage.asset_type_of(a)
        filas = storage.all_layers(tipo, a) if con_history else storage.read_incoming_rows(a)
        for r in filas:
            k = (a, r["domain"], r["metric"])
            prev = ultimo.get(k)
            if prev is None or r["data_as_of"] > prev["data_as_of"]:
                ultimo[k] = {"data_as_of": r["data_as_of"], "asset_type": r["asset_type"],
                             "retrieved_at": r["retrieved_at"]}
            elif r["retrieved_at"] > prev["retrieved_at"]:
                prev["retrieved_at"] = r["retrieved_at"]

    por_metrica = []
    for (a, dom, met), v in sorted(ultimo.items()):
        est, r, unidad = estado_frescura(v["asset_type"], dom, met, v["data_as_of"], hoy, tc)
        por_metrica.append({
            "asset_id": a, "asset_type": v["asset_type"], "domain": dom, "metric": met,
            "data_as_of": v["data_as_of"].isoformat(),
            "retrieved_at": v["retrieved_at"].isoformat(),
            "edad_data_as_of_d": (hoy - v["data_as_of"]).days,
            "retraso": r, "unidad": unidad,
            "cadencia_n": (cadencias.cadencia(dom, met) or (None, None))[1],
            "estado_frescura": est,
            "fechado_dudoso": met in cadencias.DEFECTO_DE_FECHADO,
        })

    # --- agregacion por (activo, dominio) ---
    dominios = {}
    for fila in por_metrica:
        k = (fila["asset_id"], fila["domain"])
        d = dominios.setdefault(k, {"asset_type": fila["asset_type"], "presentes": set(),
                                    "peor": None, "min_dao": None, "max_ret": None})
        d["presentes"].add(fila["metric"])
        cand = (fila["estado_frescura"], fila["retraso"], fila["metric"], fila["unidad"],
                fila["data_as_of"])
        d["peor"] = _peor(d["peor"], cand)
        if d["min_dao"] is None or fila["data_as_of"] < d["min_dao"]:
            d["min_dao"] = fila["data_as_of"]
        if d["max_ret"] is None or fila["retrieved_at"] > d["max_ret"]:
            d["max_ret"] = fila["retrieved_at"]

    # dominios declarados que no han producido ni una fila: MISSING, no ausencia
    for a in activos:
        tipo = storage.asset_type_of(a)
        for (t, dom) in cadencias.ESPERADAS:
            if t == tipo and (a, dom) not in dominios:
                dominios[(a, dom)] = {"asset_type": tipo, "presentes": set(),
                                      "peor": None, "min_dao": None, "max_ret": None}

    por_dominio = []
    for (a, dom), d in sorted(dominios.items()):
        esp = cadencias.esperadas(a, d["asset_type"], dom)
        sin_aplicar = {m for m in (esp or ()) if cadencias.no_aplica(a, dom, m)}
        cob, faltan = _estado_cobertura(esp, d["presentes"], sin_aplicar)
        no_declaradas = sorted(d["presentes"] - esp) if esp else []
        peor = d["peor"] or ("UNKNOWN", None, None, None, None)
        por_dominio.append({
            "asset_id": a, "asset_type": d["asset_type"], "domain": dom,
            "cobertura": cob,
            "esperadas": len(esp) if esp else None,
            "presentes": len(d["presentes"]),
            "no_aplican": sorted(sin_aplicar),
            "faltan": sorted(faltan),
            "metricas_no_declaradas": no_declaradas,
            "estado_frescura": peor[0],
            "retraso": peor[1],
            "unidad": peor[3],
            "metrica_que_manda": peor[2],
            # fecha de la metrica que manda, distinta de data_as_of_min:
            # el minimo del dominio puede ser de otra metrica.
            "data_as_of_peor": peor[4],
            "data_as_of_min": d["min_dao"],
            "retrieved_at_max": d["max_ret"],
        })

    return {
        "generado_para": hoy.isoformat(),
        "incluye_history": con_history,
        "nota": ("Sin history/: una metrica sin filas en el año en curso no aparece. "
                 "Ejecutar con --con-history para incluirlas." if not con_history else ""),
        "por_dominio": por_dominio,
        "por_metrica": por_metrica,
    }


def _imprimir(res):
    print(f"COBERTURA Y FRESCURA — {res['generado_para']} "
          f"({'incluye history/' if res['incluye_history'] else 'solo incoming/, sin PyArrow'})\n")
    print(f"{'ACTIVO':6} {'DOMINIO':12} {'COBERTURA':18} {'FRESCURA':9} {'RETRASO':>10} "
          f"{'ÚLTIMO DATO':>12} {'ÚLTIMA MIRADA':>21}  MÉTRICA QUE MANDA")
    for f in res["por_dominio"]:
        cob = f"{f['cobertura']} {f['presentes']}/{f['esperadas'] or '?'}"
        r = "—" if f["retraso"] is None else f"{f['retraso']} {f['unidad'] or ''}".strip()
        print(f"{f['asset_id']:6} {f['domain']:12} {cob:18} "
              f"{f['estado_frescura']:9} {r:>10} "
              f"{str(f['data_as_of_min']):>12} {str(f['retrieved_at_max']):>21}  "
              f"{f['metrica_que_manda'] or ''}")
        if f["faltan"]:
            print(f"{'':6} {'':12} └─ faltan: {', '.join(f['faltan'])}")
        if f["no_aplican"]:
            print(f"{'':6} {'':12} └─ no aplican (declarado): {', '.join(f['no_aplican'])}")
        if f["metricas_no_declaradas"]:
            print(f"{'':6} {'':12} └─ presentes SIN declarar: {', '.join(f['metricas_no_declaradas'])}")

    dudosas = sorted({f["metric"] for f in res["por_metrica"] if f["fechado_dudoso"]})
    if dudosas:
        print(f"\nAviso de fechado (registrado en cadencias.py, NO corregido): "
              f"{', '.join(dudosas)}\n  se escriben con la fecha del trimestre aunque "
              f"dependen del precio del día, así que su retraso está sobreestimado.")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--con-history", action="store_true",
                    help="incluye history/ (requiere PyArrow)")
    ap.add_argument("--solo-tabla", action="store_true",
                    help="no escribe data/coverage.json")
    args = ap.parse_args(argv)

    res = evaluar(con_history=args.con_history)
    _imprimir(res)
    if not args.solo_tabla:
        tmp = COVERAGE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        os.replace(tmp, COVERAGE_PATH)
        print(f"\nEscrito {os.path.relpath(COVERAGE_PATH, ROOT)} "
              f"({len(res['por_dominio'])} dominios, {len(res['por_metrica'])} métricas).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
