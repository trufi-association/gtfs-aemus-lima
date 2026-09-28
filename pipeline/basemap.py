#!/usr/bin/env python3
"""
Descarga una vez la red vial de Lima desde OpenStreetMap y la deja lista para
incrustar en el visor como mapa de fondo.

Por que incrustar en vez de pedir teselas: el visor debe funcionar publicado
(donde las peticiones a servidores externos estan bloqueadas), abierto como
archivo local y sin conexion. Un fondo vectorial propio cumple las tres cosas
y ademas pesa menos que un juego de teselas.

Salida: basemap.json
"""
import json
import math
import os
import urllib.parse
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
ESPEJOS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter"]

# Margen alrededor de las rutas, en grados (~2 km).
MARGEN = 0.02

# Dos niveles de jerarquia: las troncales se dibujan un poco mas marcadas.
CAPAS = {
    "troncal": "motorway|trunk|primary",
    "secundaria": "secondary|tertiary",
}

# Las calles locales son las que dan textura de ciudad al acercar, pero
# descargarlas para toda Lima pesaria demasiado. Se piden solo en un corredor
# alrededor de las rutas, que es donde alguien va a hacer zoom.
LOCAL = "residential|unclassified|living_street|pedestrian"
CORREDOR = 500        # m a cada lado de la ruta
PASO_CORREDOR = 250   # m entre puntos de referencia de la consulta


def consultar(query):
    datos = urllib.parse.urlencode({"data": query}).encode()
    ultimo = None
    for url in ESPEJOS:
        try:
            req = urllib.request.Request(
                url, data=datos,
                headers={"User-Agent": "Trufi-GTFS-Lima/1.0 (leonardo@trufi-association.org)"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except Exception as e:          # noqa: BLE001 — se prueba el siguiente espejo
            ultimo = e
            continue
    raise SystemExit("Overpass no respondio: %s" % ultimo)


def simplificar(pts, tol_m):
    if len(pts) < 3:
        return pts
    lat0 = math.radians(pts[0][0])
    mx, my = 111320.0 * math.cos(lat0), 110540.0

    def rec(sub):
        if len(sub) < 3:
            return sub
        ax, ay = sub[0][1] * mx, sub[0][0] * my
        bx, by = sub[-1][1] * mx, sub[-1][0] * my
        vx, vy = bx - ax, by - ay
        l2 = vx * vx + vy * vy
        peor, idx = -1.0, 0
        for i in range(1, len(sub) - 1):
            px, py = sub[i][1] * mx, sub[i][0] * my
            if l2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / l2))
                d = math.hypot(px - (ax + t * vx), py - (ay + t * vy))
            if d > peor:
                peor, idx = d, i
        if peor <= tol_m:
            return [sub[0], sub[-1]]
        return rec(sub[:idx + 1])[:-1] + rec(sub[idx:])

    return rec(list(pts))


def main():
    con_datos = json.load(open(os.path.join(AQUI, "datos_visor.json")))
    la, lo = [], []
    for r in con_datos["rutas"]:
        for s in r["trazado"]:
            for c in s:
                la.append(c[0])
                lo.append(c[1])
    sur, norte = min(la) - MARGEN, max(la) + MARGEN
    oeste, este = min(lo) - MARGEN, max(lo) + MARGEN
    caja = "%f,%f,%f,%f" % (sur, oeste, norte, este)

    salida = {"bbox": [sur, oeste, norte, este]}
    for capa, tipos in CAPAS.items():
        q = ('[out:json][timeout:180];way["highway"~"^(%s)$"](%s);out geom;'
             % (tipos, caja))
        print("descargando %s ..." % capa)
        datos = consultar(q)
        lineas = []
        for el in datos.get("elements", []):
            geo = el.get("geometry") or []
            if len(geo) < 2:
                continue
            pts = [(g["lat"], g["lon"]) for g in geo]
            pts = simplificar(pts, 30.0 if capa == "troncal" else 45.0)
            lineas.append([[round(a, 4), round(b, 4)] for a, b in pts])
        salida[capa] = lineas
        print("  %s: %d vias, %d puntos" % (capa, len(lineas),
                                            sum(len(x) for x in lineas)))

    # Calles locales, solo en el corredor de las rutas.
    print("descargando calles locales del corredor ...")
    puntos = []
    for r in con_datos["rutas"]:
        for s in r["trazado"]:
            acum = PASO_CORREDOR
            for i in range(len(s) - 1):
                a, b = s[i], s[i + 1]
                dy = (b[0] - a[0]) * 110540
                dx = (b[1] - a[1]) * 111320 * math.cos(math.radians(a[0]))
                tramo = math.hypot(dx, dy)
                acum += tramo
                if acum >= PASO_CORREDOR:
                    puntos.append((round(a[0], 5), round(a[1], 5)))
                    acum = 0
    print("  %d puntos de referencia" % len(puntos))

    locales, vistos = [], set()
    LOTE = 220
    for i in range(0, len(puntos), LOTE):
        lote = puntos[i:i + LOTE]
        coords = ",".join("%s,%s" % (a, b) for a, b in lote)
        q = ('[out:json][timeout:180];way["highway"~"^(%s)$"](around:%d,%s);out geom;'
             % (LOCAL, CORREDOR, coords))
        try:
            datos = consultar(q)
        except SystemExit:
            print("  lote %d omitido" % (i // LOTE))
            continue
        for el in datos.get("elements", []):
            if el.get("id") in vistos:
                continue
            vistos.add(el.get("id"))
            geo = el.get("geometry") or []
            if len(geo) < 2:
                continue
            pts = simplificar([(g["lat"], g["lon"]) for g in geo], 20.0)
            locales.append([[round(a, 5), round(b, 5)] for a, b in pts])
        print("  lote %d/%d — %d vias acumuladas"
              % (i // LOTE + 1, (len(puntos) + LOTE - 1) // LOTE, len(locales)))
    salida["local"] = locales

    # Costa: da referencia inmediata de donde esta el mar.
    print("descargando costa ...")
    q = '[out:json][timeout:180];way["natural"="coastline"](%s);out geom;' % caja
    try:
        datos = consultar(q)
        costa = []
        for el in datos.get("elements", []):
            geo = el.get("geometry") or []
            if len(geo) < 2:
                continue
            pts = simplificar([(g["lat"], g["lon"]) for g in geo], 60.0)
            costa.append([[round(a, 4), round(b, 4)] for a, b in pts])
        salida["costa"] = costa
        print("  costa: %d tramos" % len(costa))
    except SystemExit:
        salida["costa"] = []

    destino = os.path.join(AQUI, "basemap.json")
    with open(destino, "w") as fh:
        json.dump(salida, fh, separators=(",", ":"))
    print("%s  (%.0f KB)" % (destino, os.path.getsize(destino) / 1024))


if __name__ == "__main__":
    main()
