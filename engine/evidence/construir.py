"""Genera, mide y comprueba Evidence. P3 (2026-09-06).

Evidence es una vista derivada: por defecto NO se escribe en ningun
sitio. Materializarla es una opcion explicita y va a data/evidence/,
gitignored, como data/current/ y data/coverage.json.

Uso:
    python3 engine/evidence/construir.py --contar
    python3 engine/evidence/construir.py --reversibilidad 500
    python3 engine/evidence/construir.py --muestra
    python3 engine/evidence/construir.py --materializar
"""
import argparse
import collections
import datetime
import json
import os
import sys

import adaptadores
import esquema

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVIDENCE_DIR = os.path.join(ROOT, "data", "evidence")


def _storage():
    return adaptadores._mod("contract", "storage")


def _normalizar(fila_contrato):
    """La fila del contrato tal y como la devuelve storage, quedandose
    solo con las columnas del contrato (storage puede traer extras)."""
    st = _storage()
    return {c: fila_contrato.get(c) for c in st.COLUMNS}


def verificar_reversibilidad(n=500, asset_ids=None):
    """original -> Evidence -> reconstruccion, campo a campo.

    La reconstruccion usa Evidence MAS DimAsset: asset_type es un
    atributo estatico del activo y su sitio es la dimension, no cada una
    de las 507.330 filas. Eso se declara aqui en vez de disimularse
    duplicando la columna.
    """
    st = _storage()
    idx = adaptadores.indice_entidades()
    activos = asset_ids or sorted(set(st.assets_en_incoming()) | set(st.assets_en_history()))
    revisadas, diferencias = 0, []
    for a in activos:
        eid = idx.get(a)
        if eid is None:
            continue
        tipo = st.asset_type_of(a)          # <- DimAsset, via storage
        for r in st.resolve(st.all_layers(tipo, a)):
            original = _normalizar(r)
            ev = adaptadores.adaptar_metrica(r, eid)
            volvio = adaptadores.reconstruir_metrica(ev, tipo)
            volvio["retrieved_at"] = datetime.datetime.fromisoformat(volvio["retrieved_at"])
            for campo in st.COLUMNS:
                if original[campo] != volvio.get(campo):
                    diferencias.append(
                        f"{ev['evidence_id']} · {campo}: {original[campo]!r} -> {volvio.get(campo)!r}")
            revisadas += 1
            if n and revisadas >= n:
                return revisadas, diferencias
    return revisadas, diferencias


# Campos que P3 se compromete a preservar de una noticia. NO es la fila
# entera: source_domain es derivable de source_ref (la URL) y
# persona_influyente es null en las 50 filas existentes -- es un enlace a
# una entidad de tipo `person` que P3 no modela todavia. Carrear un campo
# vacio "por si acaso" seria justo lo que el encargo prohibe.
CAMPOS_NOTICIA_PRESERVADOS = ["headline", "summary", "relevance", "sentiment",
                              "sentiment_label", "data_as_of", "retrieved_at",
                              "source", "source_priority", "url", "asset_id"]


def verificar_reversibilidad_noticias():
    """Comprueba que los campos preservados vuelven identicos desde las
    dos filas de Evidence que produce cada articulo."""
    import glob
    revisados, difs = 0, []
    filas, _ = adaptadores.evidencia_de_noticias()
    por_id = {}
    for e in filas:
        por_id.setdefault(e["evidence_id"].rsplit(":", 1)[0], {})[e["metric"]] = e
    for p in sorted(glob.glob(os.path.join(adaptadores.NEWS_DIR, "*.json"))):
        for art in json.load(open(p, encoding="utf-8")):
            par = por_id.get(f"ev:news:{art['asset_id']}:{art['news_id']}")
            if not par:
                difs.append(f"{art['news_id']}: sin Evidence")
                continue
            score, label = par["news_sentiment"], par["news_sentiment_label"]
            volvio = {
                "headline": score["headline"], "summary": score["summary"],
                "relevance": score["relevance"], "sentiment": score["value_num"],
                "sentiment_label": label["value_text"],
                "data_as_of": score["occurred_at"], "retrieved_at": score["known_at"],
                "source": score["source"], "source_priority": score["source_rank"],
                "url": score["source_ref"],
                "asset_id": score["evidence_id"].split(":")[2],
            }
            for c in CAMPOS_NOTICIA_PRESERVADOS:
                if art.get(c) != volvio.get(c):
                    difs.append(f"{art['news_id']} · {c}: {art.get(c)!r} -> {volvio.get(c)!r}")
            revisados += 1
    return revisados, difs


def contar():
    st = _storage()
    resumen = {"metricas": collections.Counter(), "por_dominio": collections.Counter(),
               "por_naturaleza": collections.Counter(), "por_granularidad": collections.Counter(),
               "por_claim": collections.Counter(), "con_concepto": 0,
               "con_derived_from": 0, "total": 0}
    for e in adaptadores.evidencia_de_metricas():
        resumen["total"] += 1
        resumen["por_dominio"][e["domain"]] += 1
        resumen["por_naturaleza"][e["nature"]] += 1
        resumen["por_granularidad"][e["granularity"]] += 1
        resumen["por_claim"][e["claim_type"]] += 1
        if e["concept_id"]:
            resumen["con_concepto"] += 1
        if e["derived_from"]:
            resumen["con_derived_from"] += 1
    noticias, sin_resolver = adaptadores.evidencia_de_noticias()
    for e in noticias:
        resumen["total"] += 1
        resumen["por_dominio"][e["domain"]] += 1
        resumen["por_naturaleza"][e["nature"]] += 1
        resumen["por_granularidad"][e["granularity"]] += 1
        resumen["por_claim"][e["claim_type"]] += 1
        if e["derived_from"]:
            resumen["con_derived_from"] += 1
    resumen["noticias"] = len(noticias)
    resumen["no_resueltas"] = sin_resolver
    resumen["activos_no_resueltos"] = adaptadores.activos_no_resueltos()
    return resumen


def materializar():
    """data/evidence/{asset_id}.jsonl -- una fila por linea, para poder
    escribir 500.000 filas sin cargarlas todas en memoria."""
    st = _storage()
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    idx = adaptadores.indice_entidades()
    escritas = 0
    for a in sorted(idx):
        if a not in set(st.assets_en_incoming()) | set(st.assets_en_history()):
            continue
        destino = os.path.join(EVIDENCE_DIR, f"{a}.jsonl")
        tmp = destino + ".tmp"
        n = 0
        with open(tmp, "w", encoding="utf-8") as f:
            for e in adaptadores.evidencia_de_metricas([a]):
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
                n += 1
        os.replace(tmp, destino)
        print(f"  {a}: {n:,} filas")
        escritas += n
    noticias, _ = adaptadores.evidencia_de_noticias()
    if noticias:
        with open(os.path.join(EVIDENCE_DIR, "_noticias.jsonl"), "w", encoding="utf-8") as f:
            for e in noticias:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"  noticias: {len(noticias):,} filas")
        escritas += len(noticias)
    return escritas


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--contar", action="store_true")
    ap.add_argument("--reversibilidad", type=int, metavar="N")
    ap.add_argument("--muestra", action="store_true")
    ap.add_argument("--materializar", action="store_true")
    ap.add_argument("--reversibilidad-noticias", action="store_true")
    args = ap.parse_args(argv)

    if args.reversibilidad:
        revisadas, difs = verificar_reversibilidad(args.reversibilidad)
        print(f"REVERSIBILIDAD — {revisadas:,} filas: original → Evidence → reconstrucción")
        print("Reconstrucción = Evidence + DimAsset (asset_type es atributo estático del activo).")
        print(f"Diferencias: {len(difs)}")
        for d in difs[:10]:
            print(f"  {d}")
        print(f"RESULTADO: {'PASS' if not difs else 'FAIL'}")
        return 0 if not difs else 1

    if args.reversibilidad_noticias:
        n, difs = verificar_reversibilidad_noticias()
        print(f"REVERSIBILIDAD DE NOTICIAS — {n} artículos, campos preservados: "
              f"{', '.join(CAMPOS_NOTICIA_PRESERVADOS)}")
        print("No se preservan source_domain (derivable de source_ref) ni persona_influyente")
        print("(null en las 50 filas; es un enlace a una entidad `person` que P3 no modela).")
        print(f"Diferencias: {len(difs)}")
        for d in difs[:10]:
            print(f"  {d}")
        print(f"RESULTADO: {'PASS' if not difs else 'FAIL'}")
        return 0 if not difs else 1

    if args.materializar:
        print("Materializando Evidence en data/evidence/ (derivado, gitignored):")
        print(f"TOTAL: {materializar():,} filas")
        return 0

    if args.muestra:
        st = _storage()
        idx = adaptadores.indice_entidades()
        ejemplos = {}
        for e in adaptadores.evidencia_de_metricas(["IBM"]):
            if e["nature"] == "MEASURED" and "MEASURED" not in ejemplos:
                ejemplos["MEASURED"] = e
            if e["nature"] == "DERIVED" and e["derived_from"] and "DERIVED" not in ejemplos:
                ejemplos["DERIVED"] = e
            if len(ejemplos) == 2:
                break
        noticias, _ = adaptadores.evidencia_de_noticias()
        if noticias:
            ejemplos[noticias[0]["claim_type"]] = noticias[0]
        for etiqueta, e in ejemplos.items():
            print(f"\n────── {etiqueta} ──────")
            print(json.dumps(e, ensure_ascii=False, indent=1))
        return 0

    r = contar()
    print(f"EVIDENCE — vista derivada, no materializada por defecto\n")
    print(f"TOTAL: {r['total']:,} filas  ({r['total'] - r['noticias']:,} de métricas + {r['noticias']} de noticias)")
    print(f"  por dominio      {dict(r['por_dominio'])}")
    print(f"  por naturaleza   {dict(r['por_naturaleza'])}")
    print(f"  por granularidad {dict(r['por_granularidad'])}")
    print(f"  por claim_type   {dict(r['por_claim'])}")
    print(f"  con concept_id de P2:      {r['con_concepto']:,}")
    print(f"  con derived_from resuelto: {r['con_derived_from']:,}")
    print(f"  entidades no resueltas:    métricas {r['activos_no_resueltos'] or 'ninguna'} · "
          f"noticias {len(r['no_resueltas'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
