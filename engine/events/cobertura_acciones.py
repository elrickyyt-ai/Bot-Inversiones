"""Cobertura de acciones corporativas sobre los eventos existentes (2026-09-08).

La pregunta, cuantitativa: de los eventos que ya tenemos, ¿cuantos llevan
dentro de sus ventanas una transformacion que pueda romper la continuidad
economica del instrumento?

No corrige nada. No recalcula ningun perfil. Mide.

La regla que aplica (D-41): no es "hay accion corporativa" sino "cambia el
instrumento economico". Un split dentro de la ventana no invalida -- el
ajuste se cancela en el cociente. Una escision si, aunque el cociente sea
aritmeticamente correcto, porque compara dos empresas distintas.
"""
import bisect
import json
import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)

import estudio_resultados as er   # noqa: E402
import identidad as idn           # noqa: E402
import perfil_reaccion as pr      # noqa: E402

RUTA = os.path.join(DIR, "acciones_corporativas.json")

# Que tipo de accion rompe que continuidad. Es la particion de D-41,
# expresada sobre los tipos declarados en el registro.
NO_CAMBIAN_INSTRUMENTO = ("SPLIT", "TICKER_CHANGE", "NAME_CHANGE",
                          "REORGANIZATION", "SUCCESSION")
CAMBIAN_INSTRUMENTO = ("MERGER", "SPINOFF")
SIN_CLASIFICAR = ("UNKNOWN",)

# Como deberia tratarse cada tipo. NO es una politica implantada: es la
# recomendacion que esta auditoria propone, con su justificacion.
POLITICA_PROPUESTA = {
    "SPLIT":          "FLAG",
    "TICKER_CHANGE":  "FLAG",
    "NAME_CHANGE":    "FLAG",
    "REORGANIZATION": "FLAG",
    "SUCCESSION":     "FLAG",
    "MERGER":         "EXCLUDE",
    "SPINOFF":        "EXCLUDE",
    "UNKNOWN":        "AMBIGUOUS",
}


def registro():
    with open(RUTA, encoding="utf-8") as fh:
        return json.load(fh)


def acciones_de(asset_id):
    return [a for a in registro()["acciones"] if a["asset_id"] == asset_id]


def _distancia_en_sesiones(fechas, desde, hasta):
    """Sesiones entre dos fechas del calendario del activo. Negativo = antes."""
    i = bisect.bisect_left(fechas, desde)
    j = bisect.bisect_left(fechas, hasta)
    return j - i


def acciones_en_ventanas(observacion, fechas, largo_estimacion=None):
    """Que acciones corporativas caen en que ventana de esta observacion."""
    largo = largo_estimacion or er.LARGO_VENTANA_ESTIMACION
    s1 = observacion["first_tradable_at"]
    if not s1:
        return []
    ventanas = {}
    ven = er.ventana_estimacion(fechas, s1, largo)
    if ven:
        ventanas["estimation_window"] = (ven[0], ven[-1])
    for h in pr.HORIZONTES:
        ses = er.sesiones_reaccion(fechas, s1, h)
        if ses:
            ventanas[h] = (min(ses + [s1]), max(ses))

    out = []
    for a in acciones_de(observacion["asset_id"]):
        dentro = [nombre for nombre, (ini, fin) in ventanas.items()
                  if ini <= a["fecha"] <= fin]
        out.append({
            "fecha": a["fecha"],
            "action_type": a["tipo"],
            "verificado_contra_sec": a["verificado_contra_sec"],
            "corporate_action_within_window": dentro,
            "distance_to_event": _distancia_en_sesiones(fechas, s1, a["fecha"]),
            "cambia_instrumento": a["tipo"] in CAMBIAN_INSTRUMENTO,
            "sin_clasificar": a["tipo"] in SIN_CLASIFICAR,
        })
    return out


def clasificar_observacion(acciones, horizonte):
    """LIMPIA / MARCADA / AMBIGUA para un horizonte concreto.

    LIMPIA   ninguna accion en estimacion ni en el horizonte
    MARCADA  solo acciones que no cambian el instrumento (ajustables)
    AMBIGUA  hay fusion, escision o accion sin clasificar en ventana
    """
    relevantes = [a for a in acciones
                  if "estimation_window" in a["corporate_action_within_window"]
                  or horizonte in a["corporate_action_within_window"]]
    if not relevantes:
        return "LIMPIA", []
    if any(a["cambia_instrumento"] or a["sin_clasificar"] for a in relevantes):
        return "AMBIGUA", relevantes
    return "MARCADA", relevantes


def medir(observaciones=None):
    obs = observaciones if observaciones is not None else pr.observaciones_v1()
    series = {s: er.series_del_activo(s) for s in {o["asset_id"] for o in obs}}
    calendarios = {s: sorted(series[s]["precio"]) for s in series}

    detalle = []
    for o in obs:
        acc = acciones_en_ventanas(o, calendarios[o["asset_id"]])
        fila = {"asset_id": o["asset_id"], "first_tradable_at": o["first_tradable_at"],
                "period_end": o["period_end"], "acciones": acc, "por_horizonte": {}}
        for h in pr.HORIZONTES:
            estado, rel = clasificar_observacion(acc, h)
            fila["por_horizonte"][h] = {"estado": estado,
                                        "tipos": sorted({a["action_type"] for a in rel})}
        detalle.append(fila)
    return detalle


def resumen(detalle):
    out = {}
    for h in pr.HORIZONTES:
        c = {"n_events": len(detalle), "n_events_clean": 0,
             "n_events_with_corporate_action": 0, "n_events_ambiguous": 0}
        for f in detalle:
            e = f["por_horizonte"][h]["estado"]
            if e == "LIMPIA":
                c["n_events_clean"] += 1
            else:
                c["n_events_with_corporate_action"] += 1
                if e == "AMBIGUA":
                    c["n_events_ambiguous"] += 1
        c["pct_ambiguous"] = round(100 * c["n_events_ambiguous"] / c["n_events"], 1)
        out[h] = c
    return out


def resumen_por_activo(detalle):
    out = {}
    for f in detalle:
        a = out.setdefault(f["asset_id"], {h: {"limpia": 0, "marcada": 0, "ambigua": 0}
                                           for h in pr.HORIZONTES})
        for h in pr.HORIZONTES:
            a[h][f["por_horizonte"][h]["estado"].lower()] += 1
    return out


if __name__ == "__main__":
    det = medir()
    res = resumen(det)
    print("=== COBERTURA DE ACCIONES CORPORATIVAS · %d eventos ===" % len(det))
    print("  %-7s %9s %9s %11s %11s" % ("horiz", "n_events", "clean", "con_accion", "ambiguous"))
    for h, c in res.items():
        print("  %-7s %9d %9d %11d %11d  (%.1f%%)" % (
            h, c["n_events"], c["n_events_clean"],
            c["n_events_with_corporate_action"], c["n_events_ambiguous"], c["pct_ambiguous"]))

    print("\n=== POR ACTIVO (limpia / marcada / ambigua) ===")
    por = resumen_por_activo(det)
    print("  %-6s %s" % ("activo", "  ".join("%-18s" % h for h in pr.HORIZONTES)))
    for a in sorted(por):
        print("  %-6s %s" % (a, "  ".join(
            "%-18s" % ("%d / %d / %d" % (por[a][h]["limpia"], por[a][h]["marcada"], por[a][h]["ambigua"]))
            for h in pr.HORIZONTES)))

    print("\n=== EVENTOS AFECTADOS ===")
    for f in det:
        tocados = {h: f["por_horizonte"][h] for h in pr.HORIZONTES
                   if f["por_horizonte"][h]["estado"] != "LIMPIA"}
        if tocados:
            print("  %-5s %s  ->  %s" % (f["asset_id"], f["first_tradable_at"],
                  ", ".join("%s:%s(%s)" % (h, v["estado"], ",".join(v["tipos"]))
                            for h, v in tocados.items())))
