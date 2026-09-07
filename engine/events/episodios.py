"""Episodios -- P6.2d (2026-09-07). La tercera unidad, sobre P4.

P4 ya distingue las dos primeras:

    DOCUMENTO   una pieza de informacion concreta (un articulo)
                -> Evidence, con su evidence_id y su source_ref
    EVENTO      un hecho identificable
                -> Event, deduplicado por identity_key

Falta la tercera, y su ausencia tiene consecuencias medibles:

    EPISODIO    una secuencia causal en curso: rumor -> anuncio ->
                aplazamiento -> resolucion

Sin episodio, cinco articulos sobre la misma tramitacion legislativa son
cinco hechos distintos. P4 ya evita el doble conteo por REDUNDANCIA (tres
articulos del mismo medio son 3 evidencias y 1 fuente), pero no el doble
conteo por CONTINUIDAD: cinco piezas sobre distintos momentos del mismo
hilo son legitimamente cinco eventos, y aun asi un solo asunto abierto.

Un episodio NO se infiere. La pertenencia se DECLARA en episodios.json,
con su criterio escrito y su justificacion documento a documento -- el
mismo trato que knowledge/ da a las relaciones (D-04: el motor no escribe
conocimiento). Agrupar por parecido de texto seria justo lo que P4 se
prohibio en su regla de identidad: "ningun campo de texto libre entra en
la clave".

Lo que este modulo NO hace, a proposito: no agrupa automaticamente, no
propone episodios candidatos y no cierra episodios solo. El estado OPEN /
RESOLVED lo pone una persona con una fuente.
"""
import json
import os

RUTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "episodios.json")

ESTADOS = {
    "OPEN":     "el hilo sigue abierto: puede haber nuevos hechos que cambien la lectura",
    "RESOLVED": "el hilo se cerro con un hecho concreto, citado en fuentes",
}

CAMPOS_EPISODIO = {"episode_id", "titulo", "entidad_principal", "estado",
                   "criterio", "documentos", "fuentes", "por_que_importa"}
CAMPOS_DOCUMENTO = {"news_id", "fecha", "fuente", "por_que"}


class EpisodioError(ValueError):
    pass


def cargar(ruta=RUTA):
    with open(ruta, encoding="utf-8") as fh:
        return json.load(fh)["episodios"]


def validar(episodios):
    vistos = set()
    for ep in episodios:
        faltan = CAMPOS_EPISODIO - set(ep)
        if faltan:
            raise EpisodioError(f"episodio {ep.get('episode_id')}: faltan {sorted(faltan)}")
        sobra = set(ep) - CAMPOS_EPISODIO
        if sobra:
            raise EpisodioError(f"episodio {ep['episode_id']}: campos no reconocidos {sorted(sobra)}")
        if ep["estado"] not in ESTADOS:
            raise EpisodioError(f"episodio {ep['episode_id']}: estado {ep['estado']!r} fuera del vocabulario")
        if ep["episode_id"] in vistos:
            raise EpisodioError(f"episode_id duplicado: {ep['episode_id']}")
        vistos.add(ep["episode_id"])
        if not ep["documentos"]:
            raise EpisodioError(f"episodio {ep['episode_id']}: sin documentos declarados")
        if not ep["criterio"].strip():
            raise EpisodioError(f"episodio {ep['episode_id']}: sin criterio de pertenencia escrito")
        for d in ep["documentos"]:
            if set(d) != CAMPOS_DOCUMENTO:
                raise EpisodioError(f"episodio {ep['episode_id']}: documento mal formado {sorted(d)}")
            if not d["por_que"].strip():
                # Un documento sin justificacion es una agrupacion sin auditar.
                raise EpisodioError(f"episodio {ep['episode_id']}: documento {d['news_id']} sin 'por_que'")
    return True


def indice_por_documento(episodios=None):
    """{news_id: episode_id}. Un documento pertenece como mucho a un
    episodio: si hiciera falta que perteneciese a dos, eso significaria
    que el criterio de uno de los dos esta mal escrito, y es preferible
    que salte aqui a que se reparta el mismo hecho entre dos hilos."""
    episodios = cargar() if episodios is None else episodios
    idx = {}
    for ep in episodios:
        for d in ep["documentos"]:
            if d["news_id"] in idx:
                raise EpisodioError(
                    f"documento {d['news_id']} declarado en dos episodios: "
                    f"{idx[d['news_id']]} y {ep['episode_id']}")
            idx[d["news_id"]] = ep["episode_id"]
    return idx


def _news_id_de_evidencia(evidence_id):
    """'ev:news:XRP:<news_id>:news_sentiment' -> '<news_id>'.

    El news_id del Data Contract (sha1 de la URL, 16 caracteres) es el
    identificador ESTABLE del documento. Los event_id son derivados y se
    regeneran; declarar un episodio contra ellos lo romperia en cada
    reconsolidacion."""
    partes = evidence_id.split(":")
    if len(partes) >= 4 and partes[1] == "news":
        return partes[3]
    return None


def asignar(eventos, evidencias, claims, episodios=None):
    """Anade `episode_id` a los eventos cuyos documentos estan declarados.

    No modifica nada mas y no inventa: un evento sin documento declarado
    se queda con episode_id = None, que significa "no se ha declarado que
    pertenezca a ningun episodio", NO "es un hecho aislado".
    """
    idx = indice_por_documento(episodios)
    claims_por_id = {c["claim_id"]: c for c in claims}
    for ev in eventos:
        encontrados = set()
        for cid in ev.get("claim_ids", []):
            for eid in claims_por_id.get(cid, {}).get("evidence_ids", []):
                nid = _news_id_de_evidencia(eid)
                if nid and nid in idx:
                    encontrados.add(idx[nid])
        if len(encontrados) > 1:
            raise EpisodioError(
                f"evento {ev['event_id']}: sus documentos pertenecen a {sorted(encontrados)}")
        ev["episode_id"] = encontrados.pop() if encontrados else None
    return eventos


def resumen(eventos, claims):
    """Lo que hace visible el episodio: cuantos DOCUMENTOS, cuantas
    EVIDENCIAS, cuantos EVENTOS y cuantos EPISODIOS. Los cuatro numeros
    son distintos y esa es justamente la razon de que exista esta capa.

    Documento no es lo mismo que evidencia: un articulo produce hoy dos
    evidencias (sentimiento y etiqueta), asi que sumar evidence_count
    contaria cada articulo dos veces. Se cuentan news_id distintos.
    """
    claims_por_id = {c["claim_id"]: c for c in claims}
    documentos = set()
    for ev in eventos:
        for cid in ev.get("claim_ids", []):
            for eid in claims_por_id.get(cid, {}).get("evidence_ids", []):
                nid = _news_id_de_evidencia(eid)
                if nid:
                    documentos.add(nid)
    con_episodio = [ev for ev in eventos if ev.get("episode_id")]
    return {
        "documentos_distintos": len(documentos),
        "evidencias": sum(ev.get("evidence_count", 0) for ev in eventos),
        "eventos": len(eventos),
        "eventos_con_episodio_declarado": len(con_episodio),
        "episodios_distintos": len({ev["episode_id"] for ev in con_episodio}),
    }


if __name__ == "__main__":
    eps = cargar()
    validar(eps)
    print(f"episodios declarados: {len(eps)}")
    for ep in eps:
        print(f"  {ep['episode_id']}  [{ep['estado']}]  {len(ep['documentos'])} documentos — {ep['titulo']}")
