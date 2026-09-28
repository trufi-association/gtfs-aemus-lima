#!/usr/bin/env python3
"""
Localiza donde el trazado ajustado se aparta del recorrido que envio AEMUS.

El ajuste a la red vial se aplica en todo el recorrido. Alli donde el resultado
se aleja del KML original mas de lo tolerable, hay algo que revisar, y solo
puede ser una de dos cosas:

  - el mapa: falta un cruce, un giro o un ramal esta etiquetado como en
    construccion o con acceso restringido, asi que el ruteador dio un rodeo;
  - el KML: el recorrido se dibujo por una via que no corresponde.

Este reporte no decide cual de las dos es: entrega el sitio, la magnitud y el
enlace para mirarlo. Las zonas se agrupan por cercania para no repetir el mismo
lugar en cada vertice.

Salidas:
  REVISAR_OSM.md      informe legible, ordenado por gravedad
  discrepancias.json  las mismas zonas, para el visor
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from etl import RUTAS, haversine, leer_kml, proyectar  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))

UMBRAL = 30.0      # m: separacion a partir de la cual se considera discrepancia
MIN_LARGO = 40.0   # m: tramos mas cortos son ruido de digitalizacion
UNIR = 150.0       # m: zonas mas proximas que esto se tratan como una sola


def zonas(ajustado, crudo):
    """Agrupa en zonas los vertices del ajustado que se apartan del crudo."""
    marcados = []
    for p in ajustado:
        d, _ = proyectar(p, crudo)
        marcados.append((p, d if d is not None else 0.0))

    grupos, actual = [], []
    for p, d in marcados:
        if d > UMBRAL:
            actual.append((p, d))
        elif actual:
            grupos.append(actual)
            actual = []
    if actual:
        grupos.append(actual)

    # Unir grupos separados por un hueco corto: suelen ser el mismo problema.
    unidos = []
    for g in grupos:
        if unidos and haversine(unidos[-1][-1][0], g[0][0]) < UNIR:
            unidos[-1].extend(g)
        else:
            unidos.append(g)

    salida = []
    for g in unidos:
        pts = [p for p, _ in g]
        largo = sum(haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        if largo < MIN_LARGO:
            continue
        peor_p, peor_d = max(g, key=lambda x: x[1])
        centro = pts[len(pts) // 2]
        salida.append({"lat": round(centro[0], 5), "lon": round(centro[1], 5),
                       "max": round(peor_d), "largo": round(largo),
                       "lat_max": round(peor_p[0], 5), "lon_max": round(peor_p[1], 5)})
    return salida


def main():
    try:
        snap = json.load(open(os.path.join(AQUI, "cache_shapes_snapped.json")))
    except OSError:
        raise SystemExit("Falta cache_shapes_snapped.json: corre antes snapping.py")

    hallazgos = []
    for ruta in RUTAS:
        rid = ruta["route_id"]
        for sentido, etiqueta, clave in ((0, "IDA", "kml_ida"),
                                         (1, "RETORNO", "kml_ret")):
            crudo = leer_kml(ruta[clave])
            ajustado = [tuple(p) for p in snap.get("%s_%d" % (rid, sentido), [])]
            if not ajustado or not crudo:
                continue
            for z in zonas(ajustado, crudo):
                z.update({"ruta": ruta["codigo"], "marca": ruta["marca"],
                          "sentido": etiqueta})
                hallazgos.append(z)

    hallazgos.sort(key=lambda z: -z["max"])
    for i, z in enumerate(hallazgos, 1):
        z["ref"] = "MAPA-%02d" % i

    with open(os.path.join(AQUI, "discrepancias.json"), "w", encoding="utf-8") as fh:
        json.dump(hallazgos, fh, ensure_ascii=False, separators=(",", ":"))

    L = ["# Puntos a revisar en el mapa", "",
         "Sitios donde el trazado ajustado a la red vial se aparta mas de %d m"
         % int(UMBRAL),
         "del recorrido que envio AEMUS. Cada uno es una de dos cosas:", "",
         "- **El mapa esta incompleto**: falta un cruce o un giro, o un ramal",
         "  figura como en construccion o con acceso restringido, y el ruteador",
         "  tuvo que dar un rodeo. Se corrige en OpenStreetMap.",
         "- **El recorrido esta mal dibujado**: el KML pasa por una via que no",
         "  corresponde. Se consulta al operador.", "",
         "Ordenados por separacion maxima.", ""]
    if hallazgos:
        L += ["| Ref | Ruta | Sentido | Separacion | Tramo | Ubicacion | Ver |",
              "|---|---|---|---:|---:|---|---|"]
        for z in hallazgos:
            url = ("https://www.openstreetmap.org/#map=18/%.5f/%.5f"
                   % (z["lat_max"], z["lon_max"]))
            L.append("| %s | %s %s | %s | %d m | %d m | `%.5f, %.5f` | [mapa](%s) |"
                     % (z["ref"], z["ruta"], z["marca"], z["sentido"], z["max"],
                        z["largo"], z["lat_max"], z["lon_max"], url))
        L += ["", "## Resumen por ruta", "", "| Ruta | Zonas | Peor caso |",
              "|---|---:|---:|"]
        por = {}
        for z in hallazgos:
            k = "%s %s" % (z["ruta"], z["marca"])
            por.setdefault(k, []).append(z["max"])
        for k in sorted(por, key=lambda x: -max(por[x])):
            L.append("| %s | %d | %d m |" % (k, len(por[k]), max(por[k])))
    else:
        L.append("_Sin discrepancias por encima del umbral._")

    with open(os.path.join(AQUI, "REVISAR_OSM.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    print("zonas a revisar: %d" % len(hallazgos))
    for z in hallazgos[:12]:
        print("  %-8s %-9s %-8s %4d m  (tramo %4d m)  %.5f, %.5f"
              % (z["ref"], z["ruta"], z["sentido"], z["max"], z["largo"],
                 z["lat_max"], z["lon_max"]))


if __name__ == "__main__":
    main()
