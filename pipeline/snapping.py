#!/usr/bin/env python3
"""
Ajusta los trazados crudos de AEMUS a la red vial de OSM (map-matching).

Motivo: los KML vienen con vertices espaciados hasta 600 m, asi que en curvas,
ovalos e intercambios la linea corta por lo derecho en vez de seguir la calle.
Valhalla devuelve la geometria real de las aristas recorridas, con perfil de
costeo 'bus', lo que ademas garantiza que el trazado sea circulable.

Criterio: matching completo. La geometria final sigue la red de OpenStreetMap
de punta a punta, sin volver nunca al KML crudo. Donde el ajuste no logra
seguir la via real —porque en el mapa falta un cruce o una via esta mal
etiquetada— el rodeo resultante se conserva y se marca: es el sintoma del
problema del mapa. El flujo es matching -> corregir OSM -> volver a correr.
Las discrepancias las reporta discrepancias.py comparando ajustado contra KML.

Salidas:
  cache_shapes_snapped.json  geometrias ajustadas (las consume etl.py)
  COMPARATIVO_SNAPPING.md    antes/despues por ruta
"""
import json
import math
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from etl import (PARSERS, RUTAS, SRC, dist_al_trazado, haversine,  # noqa: E402
                 leer_kml, partir_por_geometria)

AQUI = os.path.dirname(os.path.abspath(__file__))
VALHALLA = "https://valhalla.busboy.app/trace_attributes"

# Umbrales del control de calidad.
RADIO_BUSQUEDA = 10    # m: radio de calles candidatas por punto (ver pedir())
TOL_SIMPLIFICA = 3.0   # m: tolerancia Douglas-Peucker previa al ajuste
DESVIO_OK = 10.0       # m: por debajo, el ajuste se acepta sin mirar
CAMBIO_LARGO_MAX = 10  # %: si la ruta cambia mas que esto, algo se fue por otro lado


def decodificar(cadena, precision=6):
    """Decodifica una polilinea codificada de Valhalla a [(lat, lon), ...]."""
    factor = 10 ** precision
    puntos, i, lat, lon = [], 0, 0, 0
    while i < len(cadena):
        for eje in range(2):
            desp, turno, byte = 0, 0, 0x20
            while byte >= 0x20:
                byte = ord(cadena[i]) - 63
                i += 1
                desp |= (byte & 0x1F) << turno
                turno += 5
            delta = ~(desp >> 1) if desp & 1 else (desp >> 1)
            if eje == 0:
                lat += delta
            else:
                lon += delta
        puntos.append((lat / factor, lon / factor))
    return puntos


def simplificar(pts, tol=3.0):
    """Douglas-Peucker, el mismo criterio que 'Simplify Way' de JOSM.

    Los KML traen cientos de vertices sobre tramos rectos que no aportan forma.
    Con 3 m —el valor por defecto de JOSM— se descarta cerca del 77% de los
    puntos sin que la geometria cambie: el ajuste resultante queda igual o algo
    mejor, y shapes.txt (la tabla mas pesada del feed) baja de tamano.
    """
    if len(pts) < 3:
        return list(pts)
    lat0 = math.radians(pts[0][0])
    mx, my = 111320.0 * math.cos(lat0), 110540.0

    def rec(sub):
        if len(sub) < 3:
            return sub
        ax, ay = sub[0][1] * mx, sub[0][0] * my
        bx, by = sub[-1][1] * mx, sub[-1][0] * my
        vx, vy = bx - ax, by - ay
        largo2 = vx * vx + vy * vy
        peor, idx = -1.0, 0
        for i in range(1, len(sub) - 1):
            px, py = sub[i][1] * mx, sub[i][0] * my
            if largo2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / largo2))
                d = math.hypot(px - (ax + t * vx), py - (ay + t * vy))
            if d > peor:
                peor, idx = d, i
        if peor <= tol:
            return [sub[0], sub[-1]]
        return rec(sub[:idx + 1])[:-1] + rec(sub[idx:])

    return rec(list(pts))


def pedir(puntos):
    cuerpo = {
        "shape": [{"lat": round(a, 6), "lon": round(b, 6)} for a, b in puntos],
        "costing": "bus",
        "shape_match": "map_snap",
        # Radio de busqueda de calles candidatas por punto. El valor por defecto
        # (~50 m) alcanza las calzadas paralelas —la Av. Santa Rosa tiene seis a
        # menos de 45 m— y el matcher se confunde entre ellas. Con 10 m solo ve
        # la correcta.
        "trace_options": {"search_radius": RADIO_BUSQUEDA},
        "filters": {"attributes": ["shape", "matched.distance_from_trace_point"],
                    "action": "include"},
    }
    req = urllib.request.Request(
        VALHALLA, data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"})
    for _ in range(2):
        try:
            return json.load(urllib.request.urlopen(req, timeout=120))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                json.JSONDecodeError):
            continue
    return None


def snapear(crudo):
    """Ajusta el recorrido COMPLETO en una sola peticion a Valhalla.

    Sin trocear ni subdividir. Trocear introducia saltos en las junturas entre
    pedazos; mandar la ruta entera deja que el matcher resuelva el recorrido de
    corrido. Si el defecto queda —una discrepancia grande contra el KML— lo
    detecta despues discrepancias.py, que es el unico juez.

    Devuelve (geometria_ajustada, desvios, tramos_fallidos).
    """
    base = simplificar(crudo, TOL_SIMPLIFICA)
    resp = pedir(base)
    if not resp or not resp.get("shape"):
        return list(crudo), [], 1     # sin respuesta: se conserva el crudo

    pts = decodificar(resp["shape"])
    desvios = [m.get("distance_from_trace_point")
               for m in resp.get("matched_points", [])
               if m.get("distance_from_trace_point") is not None]

    limpia = [pts[0]] if pts else []
    for p in pts[1:]:
        if haversine(limpia[-1], p) >= 0.5:
            limpia.append(p)
    return limpia, desvios, 0


def largo(pts):
    return sum(haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1))


def main():
    cache, filas, alertas = {}, [], []

    for ruta in RUTAS:
        rid = ruta["route_id"]
        paradas = PARSERS[ruta["parser"]](os.path.join(SRC, ruta["xlsx"]))
        crudos = {0: leer_kml(ruta["kml_ida"]), 1: leer_kml(ruta["kml_ret"])}
        if all(p["sentido"] is None for p in paradas):
            paradas = partir_por_geometria(paradas, crudos[0], crudos[1])
        else:
            for p in paradas:
                if p["sentido"] is None:
                    di = dist_al_trazado((p["lat"], p["lon"]), crudos[0])
                    dr = dist_al_trazado((p["lat"], p["lon"]), crudos[1])
                    p["sentido"] = 0 if (di or 0) <= (dr or 0) else 1

        for sentido, etiqueta in ((0, "IDA"), (1, "RETORNO")):
            crudo = crudos[sentido]
            nuevo, desvios, fallidos = snapear(crudo)
            if not nuevo:
                alertas.append("%s %s: el ajuste no devolvio geometria; se "
                               "conserva el trazado crudo." % (ruta["codigo"], etiqueta))
                nuevo = crudo

            km_antes, km_despues = largo(crudo) / 1000, largo(nuevo) / 1000
            cambio = 100 * (km_despues - km_antes) / km_antes if km_antes else 0

            mias = [p for p in paradas if p["sentido"] == sentido]
            def peor(traza):
                ds = [dist_al_trazado((p["lat"], p["lon"]), traza) for p in mias]
                ds = [d for d in ds if d is not None]
                return (max(ds) if ds else 0,
                        sum(1 for d in ds if d > 150))
            peor_antes, lejos_antes = peor(crudo)
            peor_despues, lejos_despues = peor(nuevo)

            desvio_max = max(desvios) if desvios else 0
            revisar = (abs(cambio) > CAMBIO_LARGO_MAX or desvio_max > DESVIO_OK * 3
                       or lejos_despues > lejos_antes or fallidos)
            estado = "REVISAR" if revisar else "ok"
            if fallidos:
                alertas.append("%s %s: %d tramo(s) sin respuesta de Valhalla; ahi "
                               "quedo el trazado crudo." % (ruta["codigo"], etiqueta, fallidos))
            if abs(cambio) > CAMBIO_LARGO_MAX:
                alertas.append("%s %s: la longitud cambio %.1f%%; verificar que el "
                               "ajuste no haya tomado otra via." % (ruta["codigo"], etiqueta, cambio))
            if lejos_despues > lejos_antes:
                alertas.append("%s %s: tras el ajuste hay mas paradas lejos del "
                               "trazado (%d -> %d)." % (ruta["codigo"], etiqueta,
                                                        lejos_antes, lejos_despues))

            cache["%s_%d" % (rid, sentido)] = nuevo
            filas.append([ruta["codigo"], ruta["marca"], etiqueta, len(crudo),
                          len(nuevo), km_antes, km_despues, cambio, desvio_max,
                          peor_antes, peor_despues, lejos_antes, lejos_despues,
                          estado])
            print("  %-8s %-8s %5d->%5d pts  %.1f->%.1f km (%+.1f%%)  peor parada "
                  "%.0f->%.0f m  %s" % (ruta["codigo"], etiqueta, len(crudo),
                  len(nuevo), km_antes, km_despues, cambio, peor_antes,
                  peor_despues, estado))

    with open(os.path.join(AQUI, "cache_shapes_snapped.json"), "w") as fh:
        json.dump(cache, fh)

    L = ["# Comparativo: trazado crudo vs. ajustado a la red vial", "",
         "Map-matching con Valhalla (perfil `bus`), criterio estricto: la geometria",
         "final sigue OpenStreetMap de punta a punta.", "",
         "| Ruta | Marca | Sentido | Puntos antes | Puntos despues | Km antes | Km despues | Cambio | Desvio max (m) | Peor parada antes (m) | Peor parada despues (m) | Paradas >150 m antes | despues | Estado |",
         "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for f in filas:
        L.append("| %s | %s | %s | %d | %d | %.1f | %.1f | %+.1f%% | %.0f | %.0f | %.0f | %d | %d | %s |" % tuple(f))

    L += ["", "## Control de calidad", ""]
    if alertas:
        L += ["Requieren mirada manual:", ""] + ["- " + a for a in alertas]
    else:
        L.append("Ningun tramo supero los umbrales: cambio de longitud por debajo de "
                 "%d%%, sin perdida de respuesta y sin paradas que se alejaran del "
                 "trazado." % CAMBIO_LARGO_MAX)

    total_antes = sum(f[3] for f in filas)
    total_despues = sum(f[4] for f in filas)
    L += ["", "## Efecto agregado", "",
          "- Vertices: **%d -> %d** (x%.1f densidad)." % (
              total_antes, total_despues, total_despues / total_antes),
          "- Kilometros totales: %.1f -> %.1f." % (
              sum(f[5] for f in filas), sum(f[6] for f in filas)),
          "- Paradas a mas de 150 m de su trazado: **%d -> %d**." % (
              sum(f[11] for f in filas), sum(f[12] for f in filas)), ""]

    with open(os.path.join(AQUI, "COMPARATIVO_SNAPPING.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    # El reporte de puntos a revisar en el mapa lo genera discrepancias.py, que
    # compara el ajustado contra el KML en todo el recorrido (no solo en picos).
    print("\nMatching de ruta completa (sin trocear).")
    print("(el detalle, en REVISAR_OSM.md tras correr discrepancias.py)")
    print("\n" + "\n".join(L[-8:]))


if __name__ == "__main__":
    main()
