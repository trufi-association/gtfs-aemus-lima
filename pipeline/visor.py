#!/usr/bin/env python3
"""
Ensambla el visor de calidad en un unico archivo HTML autocontenido.

Junta la plantilla, la hoja de estilo, el codigo de la aplicacion, las
tipografias corporativas y los datos generados por datos_visor.py. El mapa de
fondo se pide a un servicio de teselas, asi que no viaja dentro del archivo.

Uso:
    python3 datos_visor.py && python3 visor.py

Salida: clientes/aemus/visor_calidad_gtfs.html
"""
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
PIEZAS = os.path.join(AQUI, "visor")
CLIENTE = os.path.dirname(os.path.dirname(AQUI))
DESTINO = os.path.join(CLIENTE, "visor_calidad_gtfs.html")


def leer(ruta):
    with open(ruta, encoding="utf-8") as fh:
        return fh.read()


def main():
    fuentes = {}
    for linea in leer(os.path.join(PIEZAS, "fuentes_b64.txt")).split("\n"):
        if "|" in linea:
            nombre, valor = linea.split("|", 1)
            fuentes[nombre] = valor

    pagina = (leer(os.path.join(PIEZAS, "visor_plantilla.html"))
              .replace("__MONT__", fuentes["mont-bold"])
              .replace("__SSREG__", fuentes["ss-reg"])
              .replace("__SSSEMI__", fuentes["ss-semi"])
              .replace("__DATOS__", leer(os.path.join(AQUI, "datos_visor.json")))
              .replace("__SCRIPT__", leer(os.path.join(PIEZAS, "visor_script.js"))))

    with open(DESTINO, "w", encoding="utf-8") as fh:
        fh.write(pagina)
    print("%s  (%.0f KB)" % (DESTINO, os.path.getsize(DESTINO) / 1024))


if __name__ == "__main__":
    main()
