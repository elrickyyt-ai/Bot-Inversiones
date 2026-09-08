"""Preparacion para ampliar la poblacion historica -- auditoria (2026-09-08).

La pregunta: de las 31 empresas del universo historico, ¿cuantas podemos
reconstruir point-in-time como ENTIDADES, EVENTOS, PRECIOS e INSTRUMENTOS,
y que componente impide ampliar con rigor?

`BACKFILL_READY` NO se decide con un porcentaje global. Se decide por
componente, porque un 90% de cobertura de precios cuyo 10% ausente son
exactamente las empresas deslistadas NO es un 90%: es un sesgo de
superviviencia con otro nombre.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
RUTA = os.path.join(DIR, "readiness_universo.json")

AVAILABLE, UNAVAILABLE, NOT_MEASURED, AMBIGUOUS = (
    "AVAILABLE", "UNAVAILABLE", "NOT_MEASURED", "AMBIGUOUS")
ESTADOS = (AVAILABLE, UNAVAILABLE, NOT_MEASURED, AMBIGUOUS)

# Componentes SIN los cuales no se puede reconstruir un evento historico.
# La expectativa NO esta: su ausencia no elimina el evento (D-38).
COMPONENTES_BLOQUEANTES = ("historical_identity", "SEC_event", "actual_financials",
                           "price", "benchmark")
# Componentes que condicionan la INTERPRETACION, no la existencia.
COMPONENTES_CONDICIONANTES = ("CIK", "historical_ticker", "corporate_actions",
                              "successor_mapping", "event_study_eligibility")
COMPONENTES_OPCIONALES = ("AV_enrichment", "expectation")

UMBRAL_BLOQUEANTE = 0.95


def declaracion():
    with open(RUTA, encoding="utf-8") as fh:
        return json.load(fh)


def matriz():
    d = declaracion()
    return d["columnas"], d["matriz"]


def cobertura():
    """n_available / n_unavailable / n_not_measured / n_ambiguous por componente."""
    cols, mat = matriz()
    out = {}
    for c in cols:
        cnt = {e: 0 for e in ESTADOS}
        for s in mat:
            cnt[mat[s][c]] += 1
        n = len(mat)
        out[c] = {"n_available": cnt[AVAILABLE], "n_unavailable": cnt[UNAVAILABLE],
                  "n_not_measured": cnt[NOT_MEASURED], "n_ambiguous": cnt[AMBIGUOUS],
                  "coverage_rate": round(cnt[AVAILABLE] / n, 3)}
    return out


def ausencias_con_forma_de_superviviencia():
    """¿Las ausencias caen justo sobre los activos que dejaron de cotizar?

    Es la comprobacion que impide leer un 90% como 'casi completo'. Si el
    10% ausente son exactamente los deslistados, la muestra que quedaria
    es de supervivientes."""
    _, mat = matriz()
    med = declaracion()["medicion_por_activo"]
    fuera = {s for s, f in med.items() if not f.get("en_directorio_actual")}
    sin_precio = {s for s in mat if mat[s]["price"] == UNAVAILABLE}
    return {
        "fuera_del_directorio_actual": sorted(fuera),
        "sin_precio": sorted(sin_precio),
        "coinciden": fuera == sin_precio,
        "lectura": ("las ausencias de precio son EXACTAMENTE los activos que el "
                    "directorio actual ya no lista: la cobertura que falta no es "
                    "aleatoria, tiene forma de sesgo de superviviencia")
        if fuera == sin_precio else "las ausencias no coinciden con los deslistados",
    }


def cuello_de_botella():
    """El componente que impide ampliar, y por que."""
    cob = cobertura()
    candidatos = [(c, cob[c]["coverage_rate"]) for c in
                  COMPONENTES_BLOQUEANTES + COMPONENTES_CONDICIONANTES]
    candidatos.sort(key=lambda t: t[1])
    return [{"componente": c, "coverage_rate": r,
             "clase": "BLOQUEANTE" if c in COMPONENTES_BLOQUEANTES else "CONDICIONANTE"}
            for c, r in candidatos if r < UMBRAL_BLOQUEANTE]


def backfill_ready():
    """No es un porcentaje global: es una conjuncion justificada."""
    cob = cobertura()
    superv = ausencias_con_forma_de_superviviencia()
    razones = []

    bloqueantes_ok = True
    for c in COMPONENTES_BLOQUEANTES:
        r = cob[c]["coverage_rate"]
        if r < UMBRAL_BLOQUEANTE:
            bloqueantes_ok = False
            razones.append(f"{c} cubre {r:.1%}, por debajo de {UMBRAL_BLOQUEANTE:.0%}")

    if superv["coinciden"]:
        bloqueantes_ok = False
        razones.append("las ausencias de precio coinciden exactamente con los "
                       "activos deslistados: ampliar ahora produciria una cohorte "
                       "de supervivientes")

    for c in ("historical_ticker", "corporate_actions"):
        if cob[c]["coverage_rate"] < UMBRAL_BLOQUEANTE:
            razones.append(f"{c} cubre {cob[c]['coverage_rate']:.1%}: sin fuente "
                           f"determinista, la identidad del instrumento no es "
                           f"reconstruible con rigor")

    return {
        "BACKFILL_READY": bool(bloqueantes_ok) and not razones,
        "razones": razones,
        "universo_minimo_efectivo": sum(
            1 for s in matriz()[1]
            if all(matriz()[1][s][c] == AVAILABLE for c in COMPONENTES_BLOQUEANTES)),
        "n_universo": len(matriz()[1]),
    }


if __name__ == "__main__":
    cols, mat = matriz()
    print("=== COBERTURA POR COMPONENTE (%d activos) ===" % len(mat))
    print("  %-26s %6s %6s %6s %6s %10s" % ("componente", "AVAIL", "UNAV", "NOTM", "AMBI", "coverage"))
    cob = cobertura()
    for c in cols:
        v = cob[c]
        print("  %-26s %6d %6d %6d %6d %9.1f%%" % (
            c, v["n_available"], v["n_unavailable"], v["n_not_measured"],
            v["n_ambiguous"], 100 * v["coverage_rate"]))

    print("\n=== FORMA DE LAS AUSENCIAS ===")
    s = ausencias_con_forma_de_superviviencia()
    print("  fuera del directorio actual :", s["fuera_del_directorio_actual"])
    print("  sin precio                  :", s["sin_precio"])
    print("  ¿coinciden?                 :", s["coinciden"])
    print(" ", s["lectura"])

    print("\n=== CUELLO DE BOTELLA ===")
    for x in cuello_de_botella():
        print("  %-26s %6.1f%%  %s" % (x["componente"], 100 * x["coverage_rate"], x["clase"]))

    print("\n=== READINESS ===")
    r = backfill_ready()
    print("  BACKFILL_READY:", r["BACKFILL_READY"])
    print("  universo minimo efectivo: %d de %d" % (r["universo_minimo_efectivo"], r["n_universo"]))
    for x in r["razones"]:
        print("   -", x)
