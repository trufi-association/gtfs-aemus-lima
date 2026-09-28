#!/usr/bin/env python3
"""
Deriva horarios y frecuencias REALES de los rastros GPS de la flota.

No es la fuente oficial: es una referencia observada para que AEMUS confirme o
corrija. Solo hay GPS de 3 de las 6 rutas (1185 ETUCHISA, 1481 LA 50, 1132
URBANITO); las demas quedan como pendientes.

Metodo:
  - Se elige un punto de control DENTRO del recorrido de cada sentido (no el
    terminal: ahi el retorno se sub-detecta). Se prueba varias fracciones del
    trazado y se toma la que mas despachos capta ("mejor mirador").
  - Cada paso de un vehiculo por ese punto (dedup 15 min) es un despacho.
  - Por tipo de dia (L-V, sabado, domingo) y franja horaria: frecuencia =
    minutos de la franja / despachos promedio por dia.

Requiere la carpeta de CSV crudos (un CSV por vehiculo/semana). Pasar su ruta
como argumento. Salida: frecuencias_gps.json en esa carpeta.
"""
import csv
import datetime
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from etl import RUTAS, leer_kml  # noqa: E402

R = 60.0  # m: radio de deteccion del paso por el punto de control
FRANJAS = [("04:00", "06:00", 4, 6), ("06:00", "09:00", 6, 9),
           ("09:00", "17:00", 9, 17), ("17:00", "21:00", 17, 21),
           ("21:00", "24:00", 21, 24)]
# Operador -> ruta (confirmado por geometria) y carpetas de datos.
OPER = [("1185", ["ETUCHISA"]),
        ("1481", ["ETP_SAN_SEBASTIAN"]),
        ("1132", ["SEMANA_30_20-07-2026_26-07-2026",
                  "SEMANA_31_27-07-2026_02-08-2026"])]
TIPOS = [("Lunes a viernes", lambda w: w < 5),
         ("Sábado", lambda w: w == 5),
         ("Domingo y feriados", lambda w: w == 6)]


def equirect(a, b):
    lat0 = math.radians((a[0] + b[0]) / 2)
    return math.hypot((b[1] - a[1]) * math.cos(lat0) * 111320,
                      (b[0] - a[0]) * 110540)


def pasos_por(files, ctrl):
    """Lista de datetimes de paso por ctrl (dedup 15 min por vehiculo)."""
    out = []
    for f in files:
        ult = None
        with open(f, newline="") as fh:
            rd = csv.reader(fh)
            next(rd, None)
            for row in rd:
                if len(row) < 5:
                    continue
                try:
                    la = float(row[2]); lo = float(row[3])
                except ValueError:
                    continue
                if equirect((la, lo), ctrl) > R:
                    continue
                try:
                    dt = datetime.datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                if ult and (dt - ult).total_seconds() < 900:
                    ult = dt
                    continue
                ult = dt
                out.append(dt)
    return out


def hhmm(x):
    return "%02d:%02d" % (int(x), round((x - int(x)) * 60))


def mejor_mirador(files, pts):
    """Punto interior del trazado que capta mas despachos (0.5/0.65/0.8)."""
    mejor, mejor_n, mejor_pasos = None, -1, None
    for frac in (0.5, 0.65, 0.8):
        ctrl = pts[min(len(pts) - 1, int(len(pts) * frac))]
        pasos = pasos_por(files, ctrl)
        if len(pasos) > mejor_n:
            mejor, mejor_n, mejor_pasos = ctrl, len(pasos), pasos
    return mejor, mejor_pasos


def resumen_tipo(pasos, cumple):
    hs = [(p.date(), p.hour + p.minute / 60) for p in pasos if cumple(p.weekday())]
    if not hs:
        return None
    dias = sorted(set(d for d, _ in hs))
    primeras = sorted(min(h for dd, h in hs if dd == d) for d in dias)
    ultimas = sorted(max(h for dd, h in hs if dd == d) for d in dias)
    prim = primeras[len(primeras) // 2]
    ult = ultimas[len(ultimas) // 2]
    bloques = []
    for a, b, h0, h1 in FRANJAS:
        cnt = sum(1 for _, h in hs if h0 <= h < h1)
        dd = cnt / len(dias)
        head = round((h1 - h0) * 60 / dd) if dd >= 0.5 else None
        bloques.append({"desde": a, "hasta": b, "cada_min": head,
                        "desp_dia": round(dd, 1)})
    return {"primera": hhmm(prim), "ultima": hhmm(ult), "dias_muestra": len(dias),
            "bloques": bloques}


def main():
    root = sys.argv[1]
    salida = {}
    for cod, carpetas in OPER:
        ruta = next(r for r in RUTAS if r["codigo"] == cod)
        files = []
        for c in carpetas:
            files += glob.glob(os.path.join(root, c, "**", "*.csv"), recursive=True)
        salida[cod] = {"marca": ruta["marca"], "sentidos": {}}
        print("### %s — %s  [%d archivos]" % (cod, ruta["marca"], len(files)))
        for key, sent in (("kml_ida", "IDA"), ("kml_ret", "RETORNO")):
            pts = leer_kml(ruta[key])
            ctrl, pasos = mejor_mirador(files, pts)
            portipo = {}
            for nombre, cumple in TIPOS:
                r = resumen_tipo(pasos, cumple)
                portipo[nombre] = r
            salida[cod]["sentidos"][sent] = {
                "ctrl": [round(ctrl[0], 6), round(ctrl[1], 6)], "tipos": portipo}
            lv = portipo["Lunes a viernes"]
            if lv:
                fr = " · ".join("%s-%s:%s" % (b["desde"], b["hasta"],
                               b["cada_min"] or "—") for b in lv["bloques"])
                print("   %-7s L-V  %s→%s  | %s" % (sent, lv["primera"],
                      lv["ultima"], fr))
            else:
                print("   %-7s sin datos" % sent)
    with open(os.path.join(root, "frecuencias_gps.json"), "w",
              encoding="utf-8") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=1)
    print("\n✔ frecuencias_gps.json")


if __name__ == "__main__":
    main()
