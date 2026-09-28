#!/usr/bin/env python3
"""
Ciclo de auditoria con datos de OSM frescos.

Trae de Overpass —que refleja las ediciones de OSM en ~1 minuto, no al dia
siguiente como Geofabrik— la red vial del CORREDOR de las rutas AEMUS, arma un
PBF, reconstruye los tiles de Valhalla y deja el servidor listo para re-correr
la auditoria. Un solo comando por cada tanda de correcciones en OSM.

Por que solo el corredor: pedir todo Lima a Overpass (189k vias) arriesga
bloqueo por uso justo. Un buffer de 150 m alrededor de las rutas, y solo vias
que un bus puede recorrer, baja a ~18k vias: liviano y ocasional, sin bloqueo.

Se conservan Colombia y Bolivia (regions.osm.pbf) para no perder Tunja ni
Cochabamba en el mismo servidor. Se incluyen las relaciones de restriccion de
giro, que fueron la causa de varias discrepancias.

El servidor valhalla.busboy.app es de PRUEBAS (no produccion): se puede
reconstruir sin cuidado especial mas alla del swap del runbook.

Uso:
    python3 auditar_fresco.py            # trae, arma el PBF y build local
    python3 auditar_fresco.py --deploy   # ademas sube y hace swap en el server

Salida local: ~/valhalla_update/lima_fresco.osm.pbf  y  build/ con los tiles.
"""
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from etl import RUTAS, leer_kml  # noqa: E402
from snapping import simplificar  # noqa: E402

TRABAJO = os.path.expanduser("~/valhalla_update")
ESPEJOS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter",
           "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
BUFFER = 150   # m alrededor de las lineas de ruta
# Clases de via que un bus puede recorrer (se excluyen footway, path, cycleway).
CLASES = ("motorway|trunk|primary|secondary|tertiary|unclassified|residential|"
          "living_street|service|busway|motorway_link|trunk_link|primary_link|"
          "secondary_link|tertiary_link")


def overpass(query):
    datos = urllib.parse.urlencode({"data": query}).encode()
    ultimo = None
    for url in ESPEJOS:
        try:
            req = urllib.request.Request(
                url, data=datos,
                headers={"User-Agent": "Trufi-GTFS-Lima/1.0 (leonardo@trufi-association.org)"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 -- se prueba el siguiente espejo
            ultimo = e
            print("   espejo %s fallo (%s), probando otro..."
                  % (url.split("/")[2], type(e).__name__))
    raise SystemExit("Overpass no respondio: %s" % ultimo)


def descargar_corredor(destino):
    """Trae vias ruteables + nodos + restricciones del buffer de las rutas."""
    centros = []
    for r in RUTAS:
        for k in ("kml_ida", "kml_ret"):
            centros += simplificar(leer_kml(r[k]), 40.0)
    coords = ",".join("%.5f,%.5f" % (a, b) for a, b in centros)
    print("descargando corredor: %d puntos de referencia, buffer %d m ..."
          % (len(centros), BUFFER))
    # ways ruteables en el buffer; luego sus nodos (>); y las restricciones que
    # tocan esas vias, con sus miembros. 'out meta' incluye version/timestamp.
    q = ('[out:xml][timeout:280];'
         '(way["highway"~"^(%s)$"](around:%d,%s);)->.w;'
         '(.w; .w >;);'
         'out meta;'
         'rel(bw.w)["type"="restriction"];'
         '(._; >;);'
         'out meta;' % (CLASES, BUFFER, coords))
    xml = overpass(q)
    osm = os.path.join(TRABAJO, "corredor.osm")
    with open(osm, "wb") as fh:
        fh.write(xml)
    print("   %.1f MB descargados" % (len(xml) / 1e6))
    # osmium convierte el XML a PBF y ordena (Valhalla lo necesita ordenado).
    subprocess.run(["osmium", "sort", osm, "-o", destino, "--overwrite"],
                   check=True)
    subprocess.run(["osmium", "fileinfo", destino], check=True)


def construir_tiles():
    """Build de tiles combinando el corredor fresco + Colombia/Bolivia."""
    build = os.path.join(TRABAJO, "build_fresco")
    cf = os.path.join(build, "custom_files")
    os.makedirs(cf, exist_ok=True)
    for f in ("lima_fresco.osm.pbf", "regions.osm.pbf"):
        src = os.path.join(TRABAJO, f)
        if not os.path.exists(src):
            raise SystemExit("falta %s" % src)
        subprocess.run(["cp", "-f", src, cf], check=True)
    compose = os.path.join(build, "docker-compose.yml")
    with open(compose, "w") as fh:
        fh.write('services:\n'
                 '  valhalla-build:\n'
                 '    image: ghcr.io/gis-ops/docker-valhalla/valhalla:latest\n'
                 '    container_name: valhalla-build-fresco\n'
                 '    volumes: ["./custom_files:/custom_files"]\n'
                 '    environment:\n'
                 '      - tile_urls=\n'
                 '      - serve_tiles=False\n'
                 '      - use_tiles_ignore_pbf=False\n'
                 '      - build_tar=True\n'
                 '      - force_rebuild=True\n')
    print("construyendo tiles (corredor fresco + regiones) ...")
    subprocess.run(["docker", "compose", "up"], cwd=build, check=True)
    tar = os.path.join(cf, "valhalla_tiles.tar")
    if not os.path.exists(tar):
        raise SystemExit("el build no genero valhalla_tiles.tar")
    print("tiles listos:", tar)
    return tar


def main():
    os.makedirs(TRABAJO, exist_ok=True)
    if not os.path.exists(os.path.join(TRABAJO, "regions.osm.pbf")):
        raise SystemExit("Falta ~/valhalla_update/regions.osm.pbf "
                         "(Colombia/Bolivia). Bajalo del server una vez.")
    t0 = time.time()
    descargar_corredor(os.path.join(TRABAJO, "lima_fresco.osm.pbf"))
    construir_tiles()
    print("\nlisto en %.0f s. Tiles en ~/valhalla_update/build_fresco/custom_files/"
          % (time.time() - t0))
    print("Para verificar local y desplegar al server, seguir el runbook o "
          "usar --deploy (pendiente de implementar el swap aqui).")


if __name__ == "__main__":
    main()
