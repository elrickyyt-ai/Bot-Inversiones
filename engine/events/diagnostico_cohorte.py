"""Diagnostico de dependencia y solapamiento de una cohorte -- D-27/D-30.

No calcula perfiles: mide si los perfiles son INTERPRETABLES.

    COMPUTABLE  !=  INTERPRETABLE  !=  PREDICTIVO

`perfil_reaccion.py` demostro lo primero. Este modulo mide lo segundo:
cuanta informacion independiente contiene de verdad una cohorte y cuanto
se contaminan sus ventanas entre si. Lo tercero -- walk-forward, fuera de
muestra -- no se toca aqui.

Deliberadamente NO define `n_effective`: primero hay que saber por que
unidad clusterizar. Publica los conteos y un `independence_status` de tres
valores mientras esa decision no este tomada, en vez de una formula
elegida de cualquier manera.
"""
import bisect
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import estudio_resultados as er   # noqa: E402
import perfil_reaccion as pr      # noqa: E402

# Umbrales DECLARADOS para el estado de independencia. No son una formula
# de n_effective: son una lectura conservadora de la diversidad transversal
# mientras la unidad de cluster no este decidida.
#
# El cuello de botella no es n_events sino n_assets: 1.000 eventos de 3
# tickers no son 1.000 unidades independientes de informacion.
MIN_ACTIVOS_ALTO = 30
MIN_ACTIVOS_MEDIO = 10


def _mediana(xs):
    o = sorted(xs)
    n = len(o)
    if not n:
        return None
    return o[n // 2] if n % 2 else (o[n // 2 - 1] + o[n // 2]) / 2


def intervalos_entre_eventos(observaciones, asset_id, fechas):
    """Separacion, EN SESIONES, entre eventos sucesivos del mismo activo.

    En sesiones y no en dias naturales: es la unidad en la que se miden los
    horizontes, y comparar ambas cosas en dias daria un numero que no se
    puede contrastar con la ventana."""
    o = sorted([x for x in observaciones
                if x["asset_id"] == asset_id and x["first_tradable_at"]],
               key=lambda x: x["published_at"])
    idx = [bisect.bisect_left(fechas, x["first_tradable_at"]) for x in o]
    return [b - a for a, b in zip(idx, idx[1:])]


def dependencia(observaciones):
    """Los conteos que hacen falta ANTES de hablar de n_effective."""
    activos = {o["asset_id"] for o in observaciones}
    episodios = {o.get("episode_id") for o in observaciones if o.get("episode_id")}
    por_activo = {}
    for o in observaciones:
        por_activo[o["asset_id"]] = por_activo.get(o["asset_id"], 0) + 1

    if len(activos) >= MIN_ACTIVOS_ALTO:
        estado = "HIGH"
    elif len(activos) >= MIN_ACTIVOS_MEDIO:
        estado = "MEDIUM"
    else:
        estado = "LOW"

    return {
        "n_observations": len(observaciones),
        "n_events": len({(o["asset_id"], o.get("event_class"), o["period_end"])
                         for o in observaciones}),
        "n_assets": len(activos),
        # Un activo aporta una unidad independiente de informacion como
        # mucho: sus trimestres comparten empresa, sector y regimen.
        "n_independent_assets": len(activos),
        "n_episodes": len(episodios) if episodios else pr.NO_APLICA,
        "events_per_asset": por_activo,
        "events_per_asset_median": _mediana(list(por_activo.values())),
        "events_per_episode": pr.NO_APLICA if not episodios else round(
            len(observaciones) / len(episodios), 2),
        "independence_status": estado,
        "cluster_recomendado": "asset",
        "razon_cluster": (
            "los eventos de un mismo activo comparten empresa, sector, mercado y regimen, "
            "y ademas se suceden en el tiempo. El episodio no aplica a un evento programado "
            "(D-28), asi que clusterizar por episodio no separaria nada en esta cohorte."),
    }


def solapamiento(observaciones, horizonte):
    """Cuantas ventanas de este horizonte alcanzan al evento siguiente."""
    con = [o for o in observaciones if o.get("solapa_por_horizonte", {}).get(horizonte)]
    medibles = [o for o in observaciones if o["medidas"].get(("RAW_RETURN", horizonte)) is not None]
    return {
        "horizonte": horizonte,
        "ventana_sesiones": er.VENTANA_SESIONES[horizonte],
        "overlap_event_count": len(con),
        "overlap_rate": round(len(con) / len(medibles), 3) if medibles else None,
        "n_medibles": len(medibles),
    }


def contaminacion_estructural(observaciones, series, horizonte):
    """Cuanto ocupa la ventana del horizonte del intervalo TIPICO entre
    eventos del mismo activo.

    Es distinto del solapamiento tecnico: una ventana puede no alcanzar al
    evento siguiente y aun asi cubrir casi todo el trimestre, con lo que
    "deriva posterior al evento" y "lo que paso hasta el evento siguiente"
    dejan de ser cosas distinguibles."""
    intervalos = []
    for sym in {o["asset_id"] for o in observaciones}:
        fechas = sorted(series[sym]["precio"])
        intervalos += [d for d in intervalos_entre_eventos(observaciones, sym, fechas) if d < 150]
    ventana = er.VENTANA_SESIONES[horizonte]
    med = _mediana(intervalos)
    return {
        "horizonte": horizonte,
        "ventana_sesiones": ventana,
        "intervalo_mediano_entre_eventos": med,
        "intervalos_consecutivos_observados": sorted(intervalos),
        "cobertura_del_intervalo": round(ventana / med, 3) if med else None,
        "n_intervalos": len(intervalos),
    }


def ventana_estimacion_diagnostico(observaciones, series, largo=None):
    """Disponibilidad y contaminacion de la ventana de estimacion."""
    largo = largo or er.LARGO_VENTANA_ESTIMACION
    completa = incompleta = contaminada = 0
    sin_volumen = 0
    for o in observaciones:
        if not o["first_tradable_at"]:
            continue
        sym = o["asset_id"]
        fechas = sorted(series[sym]["precio"])
        ven = er.ventana_estimacion(fechas, o["first_tradable_at"], largo)
        if not ven:
            incompleta += 1
            continue
        completa += 1
        otros = [x for x in observaciones
                 if x["asset_id"] == sym and x is not o and x["first_tradable_at"]
                 and ven[0] <= x["first_tradable_at"] <= ven[-1]]
        if otros:
            contaminada += 1
        if any(d not in series[sym]["volumen"] for d in ven):
            sin_volumen += 1
    return {
        "largo": largo,
        "con_ventana_completa": completa,
        "sin_ventana_completa": incompleta,
        "contaminadas_por_otro_evento": contaminada,
        "con_huecos_de_volumen": sin_volumen,
    }


def comparar_muestras(observaciones, measure_type, horizonte, as_of):
    """full_sample frente a non_overlapping_sample. No elimina nada: mide
    cuanto cambia la distribucion al quitar la contaminacion."""
    p = pr.perfil(observaciones, "earnings_release", measure_type, horizonte, as_of)
    full, limpia = p["statistics"], p["statistics_non_overlapping"]
    if not full:
        return {"medida": measure_type, "horizonte": horizonte, "comparable": False,
                "motivo": p["status"]}
    if not limpia:
        return {"medida": measure_type, "horizonte": horizonte, "comparable": False,
                "motivo": "no hay ningun evento solapado que quitar"}
    return {
        "medida": measure_type, "horizonte": horizonte, "comparable": True,
        "n_full": p["n_observations"], "n_limpia": p.get("n_non_overlapping"),
        "median_full": full["median"], "median_limpia": limpia["median"],
        "delta_median": round(limpia["median"] - full["median"], 3),
        "prob_full": full["prob_positive"], "prob_limpia": limpia["prob_positive"],
    }


def informe(as_of="2026-09-07"):
    obs = pr.observaciones_v1()
    series = {s: er.series_del_activo(s) for s in pr.SIMBOLOS_V1}
    return {
        "as_of": as_of,
        "dependencia": dependencia(obs),
        "ventana_estimacion": ventana_estimacion_diagnostico(obs, series),
        "solapamiento": [solapamiento(obs, h) for h in pr.HORIZONTES],
        "contaminacion": [contaminacion_estructural(obs, series, h) for h in pr.HORIZONTES],
        "full_vs_limpia": [comparar_muestras(obs, m, h, as_of)
                           for m in ("RAW_RETURN", "ABNORMAL_RETURN")
                           for h in ("2_20d", "2_60d")],
    }


if __name__ == "__main__":
    d = informe(sys.argv[1] if len(sys.argv) > 1 else "2026-09-07")
    dep = d["dependencia"]
    print("=== DEPENDENCIA ===")
    for k in ("n_observations", "n_events", "n_assets", "n_independent_assets",
              "n_episodes", "events_per_asset", "events_per_asset_median",
              "events_per_episode", "independence_status", "cluster_recomendado"):
        print(f"  {k:26} {dep[k]}")
    print("\n=== VENTANA DE ESTIMACION ===")
    for k, v in d["ventana_estimacion"].items():
        print(f"  {k:30} {v}")
    print("\n=== SOLAPAMIENTO Y CONTAMINACION ESTRUCTURAL ===")
    print(f"  {'horiz':7} {'ventana':>8} {'solapan':>8} {'tasa':>7} {'interv.med':>11} {'cobertura':>10}")
    for so, co in zip(d["solapamiento"], d["contaminacion"]):
        print(f"  {so['horizonte']:7} {so['ventana_sesiones']:>8} {so['overlap_event_count']:>8} "
              f"{str(so['overlap_rate']):>7} {str(co['intervalo_mediano_entre_eventos']):>11} "
              f"{str(co['cobertura_del_intervalo']):>10}")
    print("\n=== FULL vs NON-OVERLAPPING ===")
    for c in d["full_vs_limpia"]:
        if not c["comparable"]:
            print(f"  {c['medida']:18} {c['horizonte']:6} no comparable: {c['motivo']}")
        else:
            print(f"  {c['medida']:18} {c['horizonte']:6} n {c['n_full']}->{c['n_limpia']} "
                  f"mediana {c['median_full']:+.2f} -> {c['median_limpia']:+.2f} "
                  f"(delta {c['delta_median']:+.3f}) · prob {c['prob_full']:.2f} -> {c['prob_limpia']:.2f}")
