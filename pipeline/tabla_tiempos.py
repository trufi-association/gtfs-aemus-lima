#!/usr/bin/env python3
"""Tabla de tiempos de recorrido por ruta, sentido y franja, para validar con AEMUS.

Origen GPS: tiempos_gps_*.json (derivados con tiempos_gps.py de los rastros de la flota).
Origen ESTIMADO: velocidad comercial por franja x longitud del trazado, cuando no hay GPS.
  - Rutas urbanas largas (1180, 1185, 1481): velocidad de referencia por franja (supuesto
    profesional coherente con los 15 km/h del feed ATU, ajustado por hora).
  - Aerodirecto Norte (1435-SX): velocidades observadas en Aerodirecto Centro (1132-SX),
    mismo tipo de servicio (directo, pocas paradas, corredor al aeropuerto).
Salida: ../../tiempos_recorrido/TIEMPOS_RECORRIDO_AEMUS_<fecha>.csv
"""
import csv, datetime as dt, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from etl import AGENCIAS, RUTAS

AQUI = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.abspath(os.path.join(AQUI, "..", ".."))
DIR_T = os.path.join(CLI, "tiempos_recorrido")
FRANJAS = ["00:00-06:00", "06:00-09:00", "09:00-14:00", "14:00-17:00", "17:00-21:00", "21:00-24:00"]
# km/h de referencia para rutas urbanas convencionales (sin GPS)
VEL_URBANA = {"00:00-06:00": 22, "06:00-09:00": 13, "09:00-14:00": 14,
              "14:00-17:00": 13, "17:00-21:00": 11, "21:00-24:00": 17}
SENT = {0: "IDA", 1: "RETORNO"}


def km_shapes():
    out = {}
    for r in csv.DictReader(open(os.path.join(AQUI, "gtfs", "shapes.txt"))):
        out[r["shape_id"]] = max(out.get(r["shape_id"], 0), float(r["shape_dist_traveled"]))
    return {k: v / 1000 for k, v in out.items()}


def main():
    gps = {}
    for f in glob.glob(os.path.join(DIR_T, "tiempos_gps_*.json")):
        gps.update(json.load(open(f)))
    km = km_shapes()
    # velocidades observadas por franja en 1132-SX (para extrapolar a 1435-SX)
    vel_sx = {}
    for fr in FRANJAS:
        vs = []
        for d in ("0", "1"):
            x = gps.get("1132SX", {}).get(d, {}).get("franjas", {}).get(fr)
            if x: vs.append(km["1132SX_%s" % d] / (x["mediana_min"] / 60))
        vel_sx[fr] = sum(vs) / len(vs) if vs else None
    filas = []
    for ruta in RUTAS:
        rid = ruta["route_id"]; emp = next(a[1] for a in AGENCIAS if a[0] == ruta["agency_id"])
        for d in (0, 1):
            L = km["%s_%d" % (rid, d)]
            g = gps.get(rid, {}).get(str(d), {})
            for fr in FRANJAS:
                x = g.get("franjas", {}).get(fr)
                if x:
                    t = x["mediana_min"]; v = L / (t / 60)
                    origen = "GPS flota jul-2026"; n = x["n"]
                    obs = "mediana de %d viajes L-V; rango tipico %d-%d min" % (n, x["p25"], x["p75"])
                elif g.get("mediana_min") and fr == "00:00-06:00":
                    # sin muestra en esa franja: usar velocidad global observada +40 % (vias libres)
                    v = L / (g["mediana_min"] / 60) * 1.4; t = L / v * 60
                    origen = "ESTIMADO"; n = ""; obs = "sin viajes GPS en la franja; velocidad global de la ruta +40 %"
                elif g.get("mediana_min"):
                    v = L / (g["mediana_min"] / 60); t = g["mediana_min"]
                    origen = "ESTIMADO"; n = ""; obs = "sin viajes GPS en la franja; mediana global de la ruta"
                elif rid == "1435SX" and vel_sx.get(fr):
                    v = vel_sx[fr]; t = L / v * 60
                    origen = "ESTIMADO"; n = ""; obs = "velocidad observada en Aerodirecto Centro (mismo tipo de servicio)"
                else:
                    v = VEL_URBANA[fr]; t = L / v * 60
                    origen = "ESTIMADO"; n = ""; obs = "velocidad comercial de referencia %d km/h; sin GPS de esta ruta" % v
                filas.append([ruta["codigo"], emp, ruta["marca"], SENT[d], fr, round(L, 1),
                              int(round(t)), round(v, 1), origen, n, obs, ""])
    hoy = dt.date.today().isoformat()
    os.makedirs(DIR_T, exist_ok=True)
    out = os.path.join(DIR_T, "TIEMPOS_RECORRIDO_AEMUS_%s.csv" % hoy)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Código", "Empresa", "Ruta", "Sentido", "Franja horaria", "Longitud (km)",
                    "Tiempo de recorrido (min)", "Velocidad comercial (km/h)", "Origen del dato",
                    "Viajes GPS (muestra)", "Observaciones", "Tiempo real según empresa (min)"])
        w.writerows(filas)
    print("✔", out, len(filas), "filas")
    for f in filas: print("  ", f[0], f[3], f[4], f[6], "min", f[7], "km/h", f[8])


if __name__ == "__main__":
    main()
