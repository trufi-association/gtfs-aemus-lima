#!/usr/bin/env python3
"""
Auditoria de trazados: compara el recorrido del KML contra la red vial ESTRICTA.

Para cada ruta y sentido:
  1. simplifica el KML a 3 m (Douglas-Peucker, como 'Simplify Way' de JOSM),
  2. pide a Valhalla un `trace_route` — un recorrido navegable, obligado a
     seguir vias conectadas (a diferencia de map_snap, no interpola en recta),
  3. mide donde ese recorrido estricto se aparta del KML mas de UMBRAL metros.

Cada separacion marcada es una de dos cosas, que decide un humano con el
satelite: una MANIOBRA INDEBIDA del bus (cruza un camellon, va en contrasentido)
o un ERROR DEL MAPA (falta una via, sobra una restriccion de giro, un oneway
esta invertido). No se corrige nada automaticamente: se marca para revision.

La geometria que va al GTFS NO sale de aca (esa es map_snap, que sigue lo que el
bus realmente hace). Esto es solo el detector.

Salida: traza_estricta.json  (geometrias trace_route + marcadores por ruta)
"""
import json
import math
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from etl import RUTAS, haversine, leer_kml  # noqa: E402
from snapping import decodificar, simplificar  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
VALHALLA = "https://valhalla.busboy.app/trace_route"
TOL_SIMPLIFICA = 3.0   # m: mismo criterio que el pipeline
UMBRAL = 30.0          # m: separacion a partir de la cual se marca (evita el
                       # ruido de calzadas paralelas, que ronda 10-20 m)


def _pedir(pts):
    """Un unico trace_route. Devuelve la geometria o None."""
    cuerpo = {"shape": [{"lat": round(a, 6), "lon": round(b, 6)} for a, b in pts],
              "costing": "auto", "shape_match": "map_snap"}
    req = urllib.request.Request(
        VALHALLA, data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=240))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError):
        return None
    geo = []
    for lg in d["trip"]["legs"]:
        g = decodificar(lg["shape"])
        if geo and g and haversine(geo[-1], g[0]) < 2:
            g = g[1:]
        geo.extend(g)
    return geo


def trace_route(pts):
    """Recorrido navegable sobre la red, resiliente a cortes.

    trace_route a veces trunca: en un vertice la red no le deja continuar
    —una maniobra imposible o un error de mapa—. En vez de perder el resto de
    la ruta, se marca ese punto como 'corte' y se reanuda desde el vertice
    siguiente. Cada corte es un hallazgo tan valido como una separacion.

    Devuelve (geometria, cortes) donde cortes es lista de puntos (lat, lon).
    """
    geo, cortes = [], []
    i = 0
    while i < len(pts) - 1:
        tramo = _pedir(pts[i:])
        if not tramo:
            i += 1                      # este vertice no arranca: saltarlo
            continue
        if geo and tramo and haversine(geo[-1], tramo[0]) < 2:
            tramo = tramo[1:]
        geo.extend(tramo)
        # .hasta que vertice del shape llego? el mas cercano al final.
        fin = geo[-1] if geo else pts[i]
        # vertice del shape mas cercano al punto final alcanzado
        k = min(range(i, len(pts)), key=lambda j: haversine(pts[j], fin))
        if k >= len(pts) - 2:
            break                        # llego (casi) al final: listo
        cortes.append(pts[k + 1])        # aqui no pudo seguir
        i = k + 2                        # reanudar salteando el vertice trabado
    return geo, cortes


def dist_a_linea(p, linea):
    """Distancia minima del punto p a la polilinea (metros)."""
    lat0 = math.radians(p[0])
    mx, my = 111320.0 * math.cos(lat0), 110540.0
    px, py = p[1] * mx, p[0] * my
    mejor = float("inf")
    for i in range(len(linea) - 1):
        ax, ay = linea[i][1] * mx, linea[i][0] * my
        bx, by = linea[i + 1][1] * mx, linea[i + 1][0] * my
        vx, vy = bx - ax, by - ay
        l2 = vx * vx + vy * vy
        t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / l2))
        d = math.hypot(px - (ax + t * vx), py - (ay + t * vy))
        if d < mejor:
            mejor = d
    return mejor


def marcadores(traza, kml):
    """Zonas donde la traza estricta se aparta del KML mas de UMBRAL.

    Se agrupan puntos contiguos por encima del umbral y se toma el peor de cada
    grupo, para no repetir el mismo lugar en cada vertice.
    """
    seps = [(dist_a_linea(p, kml), p) for p in traza]
    grupos, actual = [], []
    for d, p in seps:
        if d > UMBRAL:
            actual.append((d, p))
        elif actual:
            grupos.append(actual)
            actual = []
    if actual:
        grupos.append(actual)
    out = []
    for g in grupos:
        dmax, pmax = max(g, key=lambda x: x[0])
        out.append({"lat": round(pmax[0], 6), "lon": round(pmax[1], 6),
                    "sep": round(dmax)})
    return sorted(out, key=lambda m: -m["sep"])


def main():
    salida, total_marc = {}, 0
    for ruta in RUTAS:
        rid = ruta["route_id"]
        for sentido, clave in ((0, "kml_ida"), (1, "kml_ret")):
            kml = leer_kml(ruta[clave])
            simp = simplificar(kml, TOL_SIMPLIFICA)
            traza, cortes = trace_route(simp)
            km_kml = sum(haversine(kml[i], kml[i + 1])
                         for i in range(len(kml) - 1)) / 1000
            if not traza:
                print("  %-8s %-3s  trace_route no respondio"
                      % (ruta["codigo"], "ida" if sentido == 0 else "ret"))
                continue
            km_tr = sum(haversine(traza[i], traza[i + 1])
                        for i in range(len(traza) - 1)) / 1000
            # Dos tipos de hallazgo: separaciones (la traza se aparta del KML) y
            # cortes (la red no dejo continuar). Ambos van como marcadores.
            marc = marcadores(traza, simp)
            for c in cortes:
                marc.append({"lat": round(c[0], 6), "lon": round(c[1], 6),
                             "sep": None, "corte": True})
            total_marc += len(marc)
            salida["%s_%d" % (rid, sentido)] = {
                "traza": [[round(a, 5), round(b, 5)] for a, b in traza],
                "marcadores": marc, "km_kml": round(km_kml, 2),
                "km_traza": round(km_tr, 2), "cortes": len(cortes)}
            print("  %-8s %-3s  KML %5.1f km -> traza %5.1f km (%+4.0f%%) | "
                  "separaciones: %2d · cortes: %d"
                  % (ruta["codigo"], "ida" if sentido == 0 else "ret", km_kml,
                     km_tr, 100 * (km_tr - km_kml) / km_kml,
                     len(marc) - len(cortes), len(cortes)))

    with open(os.path.join(AQUI, "traza_estricta.json"), "w", encoding="utf-8") as fh:
        json.dump(salida, fh, ensure_ascii=False, separators=(",", ":"))
    print("\ntotal de marcadores a revisar: %d" % total_marc)


if __name__ == "__main__":
    main()
