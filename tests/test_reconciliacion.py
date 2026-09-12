# -*- coding: utf-8 -*-
"""Reconciliacion de las 754 filas del cron -- S0.5.

Lo que estos tests protegen no es "el CSV se creo": es que el dato que existia
en la rama canonica siga siendo EL MISMO dato, con su procedencia intacta.

    origen           objetos git, `git show <commit>:data/metrics/{ID}.json`
    clave logica     (asset_id, domain, metric, data_as_of, source)
    retrieved_at     PRESERVADO -- un refetch lo destruiria
    idempotencia     segunda ejecucion, 0 escrituras

Ningun test escribe: la escritura se hizo una vez y aqui se comprueba que
repetirla no anade nada.
"""
import os
import subprocess
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "engine", "contract"))

import reconciliar_metrics as rm  # noqa: E402
import storage  # noqa: E402

TOTAL = 754


class TestFuenteYAlcance(unittest.TestCase):

    def test_los_commits_estan_pinados_no_son_ramas(self):
        """Una rama se mueve; un commit no. La operacion tiene que dar el
        mismo resultado manana."""
        for sha in (rm.BASE, rm.CANONICA):
            self.assertRegex(sha, r"^[0-9a-f]{40}$")
            r = subprocess.run(["git", "-C", RAIZ, "cat-file", "-e",
                                f"{sha}^{{commit}}"], capture_output=True)
            self.assertEqual(r.returncode, 0, sha)

    def test_la_herramienta_no_tiene_nada_de_red(self):
        """La prueba mas dura del "sin refetch": no hay con que."""
        with open(os.path.join(RAIZ, "engine", "contract",
                               "reconciliar_metrics.py"), encoding="utf-8") as fh:
            fuente = fh.read()
        for patron in ("requests", "urllib", "urlopen", "socket", "http://",
                       "https://", "api.", "fetch_data"):
            self.assertNotIn(patron, fuente, patron)

    def test_el_delta_son_exactamente_754_filas(self):
        total = sum(len(rm.delta(a)) for a in rm.ACTIVOS)
        self.assertEqual(total, TOTAL)

    def test_por_activo_el_reparto_es_el_medido(self):
        esperado = {"ADA": 128, "BTC": 120, "DOT": 120, "EA": 7,
                    "ETH": 128, "SOL": 128, "US": 3, "XRP": 120}
        real = {a: len(rm.delta(a)) for a in rm.ACTIVOS}
        self.assertEqual(real, esperado)

    def test_todas_las_filas_caen_en_el_anio_abierto(self):
        """Es lo que decide el carril: 2026 esta en incoming/, no en history/,
        que llega a 2025. Si alguna cayese fuera, el carril seria otro."""
        for a in rm.ACTIVOS:
            anios = {r["data_as_of"][:4] for r in rm.delta(a)}
            self.assertEqual(anios, {"2026"}, f"{a}: {anios}")

    def test_el_carril_no_es_el_de_datos_tardios(self):
        """`late` es para anos ya consolidados en parquet. No es el caso."""
        destino = storage.incoming_path("BTC", rm.ANIO_ESPERADO)
        self.assertTrue(destino.endswith("BTC_2026.csv"))
        self.assertNotIn("_late", destino)


class TestComparacionFilaAFila(unittest.TestCase):
    """Valor a valor, no por sumas: el criterio que `3a1b087` ya corrigio."""

    def test_las_754_coinciden_campo_por_campo_con_el_origen_git(self):
        total, incidencias = 0, []
        for a in rm.ACTIVOS:
            n, inc = rm.verificar(a)
            total += n
            incidencias += inc
        self.assertEqual(incidencias, [], incidencias[:5])
        self.assertEqual(total, TOTAL)

    def test_retrieved_at_preservado_en_las_754(self):
        """Un refetch pondria la hora de hoy y destruiria la procedencia
        point-in-time, que es parte de la evidencia de lo que habia."""
        distintos = []
        for a in rm.ACTIVOS:
            dest = {storage.logical_key(f): f for f in storage.read_incoming(
                storage.incoming_path(a, rm.ANIO_ESPERADO))}
            for r in rm.delta(a):
                fila = storage.from_json_row(r)
                real = dest.get(storage.logical_key(fila))
                self.assertIsNotNone(real)
                if real["retrieved_at"] != fila["retrieved_at"]:
                    distintos.append((a, r["metric"], r["retrieved_at"]))
        self.assertEqual(distintos, [])

    def test_la_clave_logica_excluye_retrieved_at(self):
        """Por eso la reconciliacion es idempotente: identifica el HECHO, no
        la fila fisica."""
        import datetime
        a = dict(storage.from_json_row(rm.delta("BTC")[0]))
        b = dict(a, retrieved_at=datetime.datetime(2000, 1, 1))
        self.assertEqual(storage.logical_key(a), storage.logical_key(b))

    def test_ninguna_fila_inventada(self):
        """Toda clave escrita que pertenezca al delta tiene origen en git."""
        for a in rm.ACTIVOS:
            del_git = {storage.logical_key(storage.from_json_row(r))
                       for r in rm.delta(a)}
            en_csv = {storage.logical_key(f) for f in storage.read_incoming(
                storage.incoming_path(a, rm.ANIO_ESPERADO))}
            self.assertTrue(del_git <= en_csv, f"{a}: faltan claves del delta")


class TestIdempotencia(unittest.TestCase):

    def test_una_segunda_pasada_no_escribe_nada(self):
        """La propiedad fuerte: no "el CSV parece correcto", sino que repetir
        la operacion no anade ni una fila."""
        for a in rm.ACTIVOS:
            r = rm.reconciliar(a, escribir=False)
            self.assertEqual(r["nuevas"], 0, f"{a}: {r}")
            self.assertEqual(r["ya_presentes"], r["leidas"], f"{a}: {r}")

    def test_el_total_ya_presente_es_754(self):
        ya = sum(rm.reconciliar(a, escribir=False)["ya_presentes"]
                 for a in rm.ACTIVOS)
        self.assertEqual(ya, TOTAL)

    def test_ninguna_clave_logica_duplicada_en_los_ocho_csv(self):
        for a in rm.ACTIVOS:
            filas = storage.read_incoming(
                storage.incoming_path(a, rm.ANIO_ESPERADO))
            claves = [storage.logical_key(f) for f in filas]
            dup = len(claves) - len(set(claves))
            self.assertEqual(dup, 0, f"{a}: {dup} clave(s) duplicada(s)")

    def test_ninguna_fecha_con_dos_fuentes_para_la_misma_metrica(self):
        for a in rm.ACTIVOS:
            por_hecho = {}
            for f in storage.read_incoming(
                    storage.incoming_path(a, rm.ANIO_ESPERADO)):
                k = (f["asset_id"], f["domain"], f["metric"],
                     f["data_as_of"].isoformat())
                por_hecho.setdefault(k, set()).add(f["source"])
            multiples = {k: v for k, v in por_hecho.items() if len(v) > 1}
            self.assertEqual(multiples, {}, f"{a}: {list(multiples)[:3]}")


class TestElBorradoDeF1SeMantiene(unittest.TestCase):
    """Las 8 colisiones modify/delete se resuelven SIN resucitar los JSON."""

    def test_los_ocho_json_siguen_eliminados(self):
        for a in rm.ACTIVOS:
            ruta = os.path.join(RAIZ, "data", "metrics", f"{a}.json")
            self.assertFalse(os.path.exists(ruta), ruta)

    def test_el_directorio_data_metrics_no_existe(self):
        self.assertFalse(os.path.isdir(os.path.join(RAIZ, "data", "metrics")))

    def test_ninguna_particion_de_history_fue_tocada(self):
        """El carril es el ano abierto, asi que ningun parquet cambia y ningun
        hash del manifiesto de history/ se mueve."""
        r = subprocess.run(["git", "-C", RAIZ, "status", "--porcelain",
                            "data/history"], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "")

    def test_solo_se_escribio_en_incoming(self):
        r = subprocess.run(["git", "-C", RAIZ, "status", "--porcelain", "data"],
                           capture_output=True, text=True)
        for linea in r.stdout.splitlines():
            ruta = linea[3:].strip()
            self.assertTrue(ruta.startswith("data/incoming/"),
                            f"S0.5 no puede tocar {ruta}")


class TestNoSeTocoElMotor(unittest.TestCase):

    def test_RULE_VERSION_intacta(self):
        sys.path.insert(0, os.path.join(RAIZ, "engine", "causal"))
        import mecanismos
        self.assertEqual(mecanismos.RULE_VERSION, "p5b/v1")

    def test_P5A_y_P5B_sin_cambios_respecto_al_cierre_de_F1(self):
        """Ni un byte de la capa causal desde el commit con el que F1 cerro."""
        cierre_f1 = "f784b8591ad00606fd85c9c979688c8b9feea88d"
        for rel in ("engine/causal/caminos.py", "engine/causal/valoracion.py",
                    "engine/causal/mecanismos.py", "engine/knowledge/modelo.py"):
            r = subprocess.run(["git", "-C", RAIZ, "diff", "--name-only",
                                cierre_f1, "--", rel],
                               capture_output=True, text=True)
            self.assertEqual(r.stdout.strip(), "", f"{rel} cambio en S0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
