#!/usr/bin/env python3
"""
Audita los trazados KML de AEMUS contra la red vial de OpenStreetMap.

Pregunta que responde: los recorridos que manda el cliente, .pasan por vias
donde un bus realmente puede circular, o cortan por escaleras, peatonales y
pasajes?

Metodo: map-matching con Valhalla propio (que ya tiene Lima cargada) usando el
perfil de costeo 'bus'. Si un tramo del KML no cae sobre via apta para bus, el
punto ajustado queda lejos del punto original. Ese desvio es la medida.

Salida: AUDITORIA_GEOMETRIA.md
"""
import json
import math
import os
import sys
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from etl import RUTAS, haversine, leer_kml  # noqa: E402

VALHALLA = "https://valhalla.busboy.app/trace_attributes"
TRAMO = 150          # puntos por peticion
SOLAPE = 5           # puntos repetidos entre tramos, para no perder continuidad
UMBRAL_DESVIO = 25   # m: por encima de esto el punto no esta sobre via de bus

# Tipos de via que un bus no deberia usar nunca.
USOS_NO_APTOS = {"steps", "footway", "path", "pedestrian", "cycleway",
                 "track", "bridleway"}


def trazar(puntos):
    cuerpo = {
        "shape": [{"lat": round(a, 6), "lon": round(b, 6)} for a, b in puntos],
        "costing": "bus",
        "shape_match": "map_snap",
        "filters": {"attributes": ["edge.use", "edge.road_class", "edge.length",
                                   "matched.distance_from_trace_point"],
                    "action": "include"},
    }
    req = urllib.request.Request(
        VALHALLA, data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError):
        return None


def auditar(puntos):
    """Devuelve (desvios, usos, fallos) recorriendo el trazado por tramos."""
    tramos = []
    i = 0
    while i < len(puntos):
        tramos.append(puntos[i:i + TRAMO])
        i += TRAMO - SOLAPE
    tramos = [t for t in tramos if len(t) >= 2]

    with ThreadPoolExecutor(max_workers=4) as pool:
        respuestas = list(pool.map(trazar, tramos))

    desvios, usos, fallos = [], Counter(), 0
    for resp in respuestas:
        if not resp:
            fallos += 1
            continue
        for m in resp.get("matched_points", []):
            d = m.get("distance_from_trace_point")
            if d is not None:
                desvios.append(d)
        for e in resp.get("edges", []):
            usos[e.get("use")] += 1
    return desvios, usos, fallos


def main():
    filas, detalle = [], []
    for ruta in RUTAS:
        for etiqueta, kml in (("IDA", ruta["kml_ida"]), ("RETORNO", ruta["kml_ret"])):
            pts = leer_kml(kml)
            largo = sum(haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
            desvios, usos, fallos = auditar(pts)
            if not desvios:
                filas.append([ruta["codigo"], ruta["marca"], etiqueta, len(pts),
                              largo / 1000, None, None, None, "sin respuesta"])
                continue
            malos = [d for d in desvios if d > UMBRAL_DESVIO]
            no_aptos = sum(v for k, v in usos.items() if k in USOS_NO_APTOS)
            filas.append([
                ruta["codigo"], ruta["marca"], etiqueta, len(pts), largo / 1000,
                sum(desvios) / len(desvios), max(desvios),
                100.0 * len(malos) / len(desvios),
                "%d tramos no aptos" % no_aptos if no_aptos else "ok",
            ])
            detalle.append((ruta["codigo"], etiqueta, usos, fallos))
            print("  %-8s %-8s desvio medio %5.1f m  max %6.1f m  fuera %4.1f%%"
                  % (ruta["codigo"], etiqueta, sum(desvios) / len(desvios),
                     max(desvios), 100.0 * len(malos) / len(desvios)))

    L = ["# Auditoria de trazados AEMUS contra la red vial de OSM", "",
         "Map-matching con Valhalla (perfil `bus`) sobre `valhalla.busboy.app`,",
         "que ya tiene Lima cargada. Un desvio alto significa que el KML pasa por",
         "donde un bus no puede circular.", "",
         "| Ruta | Marca | Sentido | Puntos | Km | Desvio medio (m) | Desvio max (m) | %% puntos >%d m | Vias no aptas |" % UMBRAL_DESVIO,
         "|---|---|---|---:|---:|---:|---:|---:|---|"]
    for f in filas:
        if f[5] is None:
            L.append("| %s | %s | %s | %d | %.1f | - | - | - | %s |" % tuple(f[:5] + [f[8]]))
        else:
            L.append("| %s | %s | %s | %d | %.1f | %.1f | %.1f | %.1f%% | %s |"
                     % tuple(f))

    L += ["", "## Tipos de via recorridos", ""]
    for cod, sent, usos, fallos in detalle:
        top = ", ".join("%s: %d" % kv for kv in usos.most_common(6))
        L.append("- **%s %s** -- %s%s" % (cod, sent, top,
                 " (peticiones fallidas: %d)" % fallos if fallos else ""))

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "AUDITORIA_GEOMETRIA.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L[:30]))


if __name__ == "__main__":
    main()
