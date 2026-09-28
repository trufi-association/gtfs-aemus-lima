#!/usr/bin/env python3
"""Deriva tiempos de recorrido (terminal a terminal) por sentido y franja a partir de GPS.
Uso: tiempos_gps.py <carpeta_csv> <route_id>[,<route_id>...]  -> imprime JSON resumen
Metodo: 5 puntos de control al 10/30/50/70/90 % del trazado; un viaje = pasos consecutivos
por los 5 en orden y en menos de 4 h; tiempo 10->90 % escalado a la longitud total."""
import csv, glob, json, math, os, sys, datetime as dt, statistics as st
from collections import defaultdict
sys.path.insert(0, "/home/leonardo/Dropbox/gestion/clientes/aemus/gtfs_aemus/build")
GTFS = "/home/leonardo/Dropbox/gestion/clientes/aemus/gtfs_aemus/build/gtfs"
R = 150.0
FRACS = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)
FRANJAS = [("00:00-06:00",0,6),("06:00-09:00",6,9),("09:00-14:00",9,14),("14:00-17:00",14,17),("17:00-21:00",17,21),("21:00-24:00",21,24)]

def equirect(a, b):
    lat0 = math.radians((a[0]+b[0])/2)
    return math.hypot((b[1]-a[1])*math.cos(lat0)*111320, (b[0]-a[0])*110540)

def shapes():
    out = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(GTFS,"shapes.txt"))):
        out[r["shape_id"]].append((float(r["shape_pt_lat"]), float(r["shape_pt_lon"]), float(r["shape_dist_traveled"])))
    return out

def punto_a(pts, frac):
    L = pts[-1][2]; obj = L*frac
    return min(pts, key=lambda p: abs(p[2]-obj))

def pasos(file, ctrls):
    """dict idx_ctrl -> lista de datetimes (dedup 8 min)."""
    out = defaultdict(list); ult = {}
    with open(file, newline="") as fh:
        rd = csv.reader(fh); next(rd, None)
        for row in rd:
            if len(row) < 4: continue
            try: la=float(row[2]); lo=float(row[3]); t=dt.datetime.strptime(row[1],"%Y-%m-%d %H:%M:%S")
            except ValueError: continue
            for i,c in enumerate(ctrls):
                if equirect((la,lo),(c[0],c[1])) <= R:
                    if i in ult and (t-ult[i]).total_seconds() < 480: ult[i]=t; continue
                    ult[i]=t; out[i].append(t)
    return out

def dseg_acc(ctrls, a, b):
    return ctrls[b][2]-ctrls[a][2]

def viajes(p, ctrls, L):
    """Empareja pasos consecutivos por los 5 controles en orden."""
    res = []
    d_tot = ctrls[-1][2]-ctrls[0][2]
    for t0 in p.get(0, []):
        t_prev = t0; ok = True; faltan = 0; i_prev = 0
        for i in range(1, len(ctrls)):
            dseg = ctrls[i][2]-ctrls[i-1][2]
            cand = [t for t in p.get(i, []) if t > t_prev and 3 <= dseg_acc(ctrls, i_prev, i)/1000/(((t-t_prev).total_seconds())/3600) <= 60]
            if not cand:
                faltan += 1
                if faltan > 2 or i == len(ctrls)-1: ok=False; break
                continue
            t_prev = cand[0]; i_prev = i
        if not ok: continue
        # descartar si hubo otro paso por el control 0 entre medias (vuelta parcial)
        if any(t0 < t < t_prev for t in p.get(0, [])): continue
        mins = (t_prev-t0).total_seconds()/60
        res.append((t0, mins * L/d_tot, mins))
    return res

def main():
    root, rids = sys.argv[1], sys.argv[2].split(",")
    files = glob.glob(os.path.join(root, "**", "*.csv"), recursive=True)
    sh = shapes(); salida = {}
    for rid in rids:
        salida[rid] = {}
        for d in (0,1):
            pts = sh[f"{rid}_{d}"]; L = pts[-1][2]
            cand = [punto_a(pts,f) for f in FRACS]
            PP = [pasos(f, cand) for f in files]
            cnt = [sum(len(p.get(i,[])) for p in PP) for i in range(len(cand))]
            keep = [i for i,c in enumerate(cnt) if c >= 0.25*max(cnt)]
            keep = list(range(keep[0], keep[-1]+1))  # bloque contiguo
            ctrls = [cand[i] for i in keep]
            print(f"  {rid} dir{d}: pasos por control {cnt} -> usa {[FRACS[i] for i in keep]} (cubre {ctrls[-1][2]-ctrls[0][2]:.0f} m de {L:.0f})")
            todos = []
            for p in PP:
                q = {j: p.get(i, []) for j,i in enumerate(keep)}
                todos += viajes(q, ctrls, L)
            por_franja = {}
            for nombre,h0,h1 in FRANJAS:
                v = [m for t,m,_ in todos if h0 <= t.hour < h1 and t.weekday() < 5]
                if len(v) >= 3:
                    por_franja[nombre] = {"n": len(v), "mediana_min": round(st.median(v)), "p25": round(st.quantiles(v, n=4)[0]), "p75": round(st.quantiles(v, n=4)[2])}
            vtot = [m for _,m,_ in todos]
            salida[rid][d] = {"km": round(L/1000,1), "n_viajes": len(vtot),
                "mediana_min": round(st.median(vtot)) if vtot else None,
                "franjas": por_franja}
            print(f"{rid} dir{d} {L/1000:.1f} km  viajes={len(vtot)}  mediana={salida[rid][d]['mediana_min']} min")
            for k,v in por_franja.items(): print(f"    {k}: n={v['n']} med={v['mediana_min']} p25={v['p25']} p75={v['p75']}")
    json.dump(salida, open(os.path.join(root,"tiempos_gps.json"),"w"), indent=1, ensure_ascii=False)
main()
