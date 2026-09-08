"""Autoridad de dato por componente -- auditoria de fuentes (2026-09-08).

D-32 demostro que Alpha Vantage devuelve vacio para DWDP y UTX. La
tentacion es leer eso como "esas empresas no estan en nuestro pasado".
Es exactamente al reves, y la regla merece sobrevivir a este backfill:

    La cobertura de un proveedor NO define quien existio en nuestro
    pasado. Que una empresa falte en un proveedor es un hecho sobre el
    PROVEEDOR, nunca sobre la EMPRESA.

Este modulo no construye ningun pipeline. Lee la declaracion de
`autoridad_datos.json` y hace comprobables dos invariantes: que ningun
proveedor de enriquecimiento pueda negar la existencia de un hecho, y que
los cuatro estados de cobertura no se confundan entre si.
"""
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
RUTA = os.path.join(DIR, "autoridad_datos.json")

# Los cuatro estados. UNAVAILABLE y NOT_MEASURED NO se intercambian:
# uno dice "lo miramos y no esta", el otro "no lo hemos mirado".
AVAILABLE = "AVAILABLE"
UNAVAILABLE = "UNAVAILABLE"
NOT_MEASURED = "NOT_MEASURED"
AMBIGUOUS = "AMBIGUOUS"
ESTADOS = (AVAILABLE, UNAVAILABLE, NOT_MEASURED, AMBIGUOUS)

AUTHORITATIVE = "AUTHORITATIVE_SOURCE"
ENRICHMENT = "ENRICHMENT_SOURCE"
MARKET = "MARKET_SOURCE"
BENCHMARK = "BENCHMARK_SOURCE"
ROLES = (AUTHORITATIVE, ENRICHMENT, MARKET, BENCHMARK)

# Componentes cuya AUSENCIA no puede eliminar el evento (punto 4 y 9 del
# encargo): sin expectativa no hay sorpresa, y sin sorpresa siguen siendo
# construibles los perfiles no condicionados por ella.
COMPONENTES_NO_ESENCIALES = ("expectation_estimatedEPS", "consensus_point_in_time")

# Perfiles que NO dependen de la expectativa, y los que si.
PERFILES_SIN_EXPECTATIVA = ("RAW_RETURN", "ABNORMAL_RETURN",
                            "VOLUME_RELATIVE_TO_PRE_EVENT",
                            "VOLATILITY_RELATIVE_TO_PRE_EVENT",
                            "PEER_RELATIVE_RETURN")
PERFILES_CON_EXPECTATIVA = ("SURPRISE_CONDITIONED",)


def declaracion():
    with open(RUTA, encoding="utf-8") as fh:
        return json.load(fh)


def componentes():
    return {c["componente"]: c for c in declaracion()["componentes"]}


def proveedores():
    return {p["proveedor"]: p for p in declaracion()["matriz_proveedores"]}


def es_autoridad_de_universo(proveedor):
    """Solo una fuente AUTHORITATIVE puede decir quien existio."""
    return AUTHORITATIVE in proveedores()[proveedor]["roles"]


def existencia_de_evento(presente_en_autoridad, presente_en_enriquecimiento):
    """La regla fundacional, ejecutable.

    Un proveedor de enriquecimiento no vota sobre la existencia: si la
    autoridad dice que el hecho ocurrio, ocurrio, aunque el enriquecedor
    no lo tenga."""
    return bool(presente_en_autoridad)


def estado_del_evento(tiene_filing, tiene_available_at, tiene_actual,
                      tiene_expectativa):
    """Completitud de un earnings event.

    Filing + available_at + resultado son SUFICIENTES. La falta de
    expectativa no elimina el evento: lo deja sin sorpresa computable."""
    completo = bool(tiene_filing and tiene_available_at and tiene_actual)
    return {
        "event_status": AVAILABLE if completo else UNAVAILABLE,
        "expectation_status": AVAILABLE if tiene_expectativa else UNAVAILABLE,
        "surprise_status": AVAILABLE if (completo and tiene_expectativa) else UNAVAILABLE,
        "perfiles_construibles": list(PERFILES_SIN_EXPECTATIVA) if completo else [],
        "perfiles_bloqueados": [] if tiene_expectativa else list(PERFILES_CON_EXPECTATIVA),
    }


def matriz_cobertura(simbolos):
    """Matriz activo x componente. Lo no medido queda NOT_MEASURED.

    Dos columnas no son por activo y se resuelven aparte:
      - `benchmark` es AVAILABLE para todos porque bm:sp500 es un NIVEL
        PUBLICADO: no depende de que el activo exista (D-25).
      - `consensus` es UNAVAILABLE para todos porque ninguna fuente medida
        publica el consenso con su fecha de vigencia."""
    m = declaracion()["matriz_cobertura_medida"]
    cols, celdas = m["_columnas"], m["celdas"]
    out = {}
    for s in simbolos:
        fila = celdas.get(s, {})
        out[s] = {c: (AVAILABLE if c == "benchmark"
                      else UNAVAILABLE if c == "consensus"
                      else fila.get(c, NOT_MEASURED))
                  for c in cols}
    return out


def resumen_matriz(simbolos):
    conteo = {e: 0 for e in ESTADOS}
    for fila in matriz_cobertura(simbolos).values():
        for v in fila.values():
            conteo[v] += 1
    return conteo


def incoherencias():
    """Lo que no cuadra en la declaracion. Vacio = coherente."""
    d = declaracion()
    fallos = []
    if set(d["estados_de_cobertura"]) != set(ESTADOS):
        fallos.append("los estados declarados no coinciden con los del modulo")
    for p in d["matriz_proveedores"]:
        for rol in p["roles"]:
            if rol not in ROLES:
                fallos.append(f"{p['proveedor']}: rol desconocido {rol}")
    for c in d["componentes"]:
        if not c.get("verificado", "").strip():
            fallos.append(f"{c['componente']}: sin evidencia de verificacion")
    av = proveedores().get("Alpha Vantage", {})
    if AUTHORITATIVE in av.get("roles", []):
        fallos.append("Alpha Vantage no puede ser AUTHORITATIVE_SOURCE (regla fundacional)")
    return fallos


if __name__ == "__main__":
    d = declaracion()
    print("=== REGLA FUNDACIONAL ===")
    print(" ", d["regla_fundacional"])
    print("\n=== AUTORIDAD POR COMPONENTE ===")
    for c in d["componentes"]:
        print("  %-32s %-58s %s" % (c["componente"], c["autoridad"], c["estado"]))
    print("\n=== PROVEEDOR x ROL x CALIDAD TEMPORAL x SURVIVORSHIP ===")
    for p in d["matriz_proveedores"]:
        print("  %-20s %-24s %s" % (p["proveedor"], "/".join(p["roles"]), p["survivorship_risk"]))
    print("\n=== EVENTO SIN EXPECTATIVA ===")
    for k, v in estado_del_evento(True, True, True, False).items():
        print("  %-24s %s" % (k, v))
    import universo as uni
    simbolos = sorted(uni.simbolos())
    print("\n=== MATRIZ DE COBERTURA (%d activos) ===" % len(simbolos))
    cols = d["matriz_cobertura_medida"]["_columnas"]
    mat = matriz_cobertura(simbolos)
    print("  %-6s " % "asset" + " ".join("%-13s" % c for c in cols))
    for s_ in simbolos:
        if any(v != NOT_MEASURED for k, v in mat[s_].items()
               if k not in ("benchmark", "consensus")):
            print("  %-6s " % s_ + " ".join("%-13s" % mat[s_][c] for c in cols))
    print("  (el resto: todo NOT_MEASURED salvo benchmark/consensus)")
    print("  conteo:", resumen_matriz(simbolos))

    print("\n=== INCOHERENCIAS ===")
    f = incoherencias()
    print("  ninguna" if not f else "\n".join("  " + x for x in f))
