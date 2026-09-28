#!/usr/bin/env python3
"""
ETL AEMUS Lima -> GTFS parcial.

Entrada:  clientes/aemus/resolicitud-gtfs-lima/  (paquete AEMUS del 2026-07-21)
Salida:   build/gtfs/          tablas GTFS que ya se pueden construir
          build/diagnostico.md reporte de calidad de datos

Lo que SI se puede construir hoy: agency, routes, stops, shapes, trips.
Lo que NO: stop_times, calendar, frequencies -- dependen de los horarios
y frecuencias que AEMUS aun no entrega.
"""
import csv
import json
import math
import os
import re
import unicodedata
import xml.etree.ElementTree as ET

import openpyxl

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(BASE, "resolicitud-gtfs-lima")
KML_DIR = os.path.join(SRC, "Rutas_Activas_LIM", "Rutas_Activas_LIM")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gtfs")
KNS = "{http://www.opengis.net/kml/2.2}"

# --- catalogo maestro -------------------------------------------------------
# Unifica las cuatro nomenclaturas que conviven en el material de AEMUS.
# 'codigo_interno' es como viene rotulado dentro del XLSX (numeracion antigua).
# 'codigo' es el vigente segun la carta a la ATU y el PPT de julio 2026.
AGENCIAS = [
    # agency_id, nombre corto, razon social, RUC
    ("SATELITE", "E.T. y Servicios Multiples Satelite S.A.",
     "EMPRESA DE TRANSPORTE Y SERVICIOS MULTIPLES SATELITE S.A", "20106977608"),
    ("SANSEBASTIAN", "E.T. Patron San Sebastian S.A.C.",
     "EMPRESA DE TRANSPORTES PATRON SAN SEBASTIAN S.A.C.", "20107410253"),
    ("NUEVAAMERICA", "E.T. y Servicios Nueva America S.A.",
     "EMPRESA DE TRANSPORTES Y SERVICIOS NUEVA AMERICA S.A.", "20160058430"),
    ("LOSCHINOS", "E.T. Urbanos Los Chinos S.A.",
     "EMPRESA DE TRANSPORTES URBANOS LOS CHINOS S.A.", "20194541008"),
]

RUTAS = [
    {
        "route_id": "1132", "codigo": "1132", "codigo_interno": "R-9605",
        "nombre_corto": "1132", "nombre_largo": "Callao - La Victoria",
        "agency_id": "SATELITE", "marca": "URBANITO",
        "xlsx": "R-1132_URBANITO.xlsx", "parser": "urbanito",
        "kml_ida": "R9605-IDA_Revision_ETRASEMU.kml",
        "kml_ret": "R9605-RET_Revision_ETRASEMU.kml",
    },
    {
        "route_id": "1132SX", "codigo": "1132-SX", "codigo_interno": "R-1132B",
        "nombre_corto": "1132SX", "nombre_largo": "Aerodirecto Centro: Lima - Callao",
        "agency_id": "SATELITE", "marca": "AERODIRECTO CENTRO",
        "xlsx": "R-1132Sx_AERODIRECTO CENTRO.xlsx", "parser": "aerodirecto_centro",
        "kml_ida": "IDA_AERODIRECTO.kml",
        "kml_ret": "RETORNO_AERODIRECTO.kml",
    },
    {
        "route_id": "1180", "codigo": "1180", "codigo_interno": "R-1702",
        "nombre_corto": "1180", "nombre_largo": "Torre Blanca (Carabayllo) - Pamplona Alta (S.J.M.)",
        "agency_id": "NUEVAAMERICA", "marca": "NUEVA AMERICA",
        "xlsx": "R-1180_NUEVA AMERICA.xlsx", "parser": "reinicio_numero",
        "kml_ida": "NAME_IDA.kml",
        "kml_ret": "NAME_RET.kml",
    },
    {
        "route_id": "1435SX", "codigo": "1435-SX", "codigo_interno": "R-1435XS",
        "nombre_corto": "1435SX", "nombre_largo": "Aerodirecto Norte",
        "agency_id": "NUEVAAMERICA", "marca": "AERODIRECTO NORTE",
        "xlsx": "R-1435Sx_AERODIRECTO NORTE.xlsx", "parser": "aerodirecto_norte",
        "kml_ida": "IDA_AERODIRECTO_NORTE.kml",
        "kml_ret": "RETORNO_AERODIRECTO_NORTE.kml",
    },
    {
        "route_id": "1185", "codigo": "1185", "codigo_interno": "R-1802",
        "nombre_corto": "1185", "nombre_largo": "Ensenada (Puente Piedra) - Av. Lima (Villa El Salvador)",
        "agency_id": "LOSCHINOS", "marca": "ETUCHISA",
        "xlsx": "R-1185_ETUCHISA-A.xlsx", "parser": "prefijo_ab",
        "kml_ida": "1802_IDA_ETUCHISA.kml",
        "kml_ret": "1802_RET_ETUCHISA.kml",
    },
    {
        # OJO: el codigo de esta ruta esta en disputa (1481 / 1431 / 1066 / IO66).
        # Se adopta 1481 por ser el de la carta a la ATU y el PPT de julio 2026,
        # pendiente de confirmacion en el cuadro oficial.
        "route_id": "1481", "codigo": "1481", "codigo_interno": "R-IO66",
        "nombre_corto": "1481", "nombre_largo": "Linea 50: San Juan de Lurigancho - Callao",
        "agency_id": "SANSEBASTIAN", "marca": "LA 50",
        "xlsx": "R-IO66 LA 50.xlsx", "parser": "columna_sentido",
        "kml_ida": "io66 IDA_ETSS.kml",
        "kml_ret": "io66 RET_ETSS.kml",
    },
]

# Caja delimitadora de Lima Metropolitana + Callao. Fuera de esto, la
# coordenada esta mal.
LIMA_BBOX = (-12.60, -11.55, -77.30, -76.60)  # lat_min, lat_max, lon_min, lon_max

# Trazados ya ajustados a la red vial, si snapping.py corrio antes.
_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "cache_shapes_snapped.json")
try:
    with open(_CACHE) as _fh:
        SNAPPED = json.load(_fh)
except (OSError, ValueError):
    SNAPPED = {}


def limpiar(texto):
    """Repara mojibake UTF-8 leido como latin-1 y normaliza espacios."""
    if texto is None:
        return ""
    s = str(texto)
    if any(m in s for m in ("Ã", "Â", "â€")):
        try:
            s = s.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    s = unicodedata.normalize("NFC", s)
    return re.sub(r"\s+", " ", s).strip()


def haversine(a, b):
    R = 6371000.0
    p1, l1 = math.radians(a[0]), math.radians(a[1])
    p2, l2 = math.radians(b[0]), math.radians(b[1])
    h = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


def en_lima(lat, lon):
    return (LIMA_BBOX[0] <= lat <= LIMA_BBOX[1]
            and LIMA_BBOX[2] <= lon <= LIMA_BBOX[3])


# --- lectura de KML ---------------------------------------------------------
def leer_kml(nombre):
    """Devuelve la lista de puntos (lat, lon) del LineString mas largo.

    NAME_IDA.kml trae dos LineStrings que son tramos consecutivos del mismo
    recorrido; se concatenan en el orden que los deja continuos.
    """
    ruta = os.path.join(KML_DIR, nombre)
    lineas = []
    for ls in ET.parse(ruta).getroot().iter(KNS + "LineString"):
        crd = ls.find(KNS + "coordinates")
        if crd is None or not crd.text:
            continue
        pts = []
        for tok in crd.text.split():
            partes = tok.split(",")
            if len(partes) >= 2:
                pts.append((float(partes[1]), float(partes[0])))
        if len(pts) > 1:
            lineas.append(pts)
    if not lineas:
        return []
    if len(lineas) == 1:
        return lineas[0]
    # Varios tramos: encadenar por proximidad extremo-con-extremo.
    tramos = sorted(lineas, key=len, reverse=True)
    cadena = list(tramos[0])
    for tr in tramos[1:]:
        opciones = [
            (haversine(cadena[-1], tr[0]), "fin-ini", tr),
            (haversine(cadena[-1], tr[-1]), "fin-fin", list(reversed(tr))),
            (haversine(cadena[0], tr[-1]), "ini-fin", None),
            (haversine(cadena[0], tr[0]), "ini-ini", None),
        ]
        d, modo, cuerpo = min(opciones, key=lambda x: x[0])
        if modo == "fin-ini" or modo == "fin-fin":
            cadena = cadena + cuerpo
        elif modo == "ini-fin":
            cadena = tr + cadena
        else:
            cadena = list(reversed(tr)) + cadena
    return cadena


# --- parsers de paraderos ---------------------------------------------------
def _filas(path):
    ws = openpyxl.load_workbook(path, data_only=True).active
    return list(ws.iter_rows(values_only=True))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_urbanito(path):
    """1132 URBANITO: el sentido va en el primer caracter del codigo (1.. / 2..)."""
    filas = _filas(path)
    hdr = [h for h in filas[0]]
    idx = {h: i for i, h in enumerate(hdr) if h}
    out = []
    for r in filas[1:]:
        cod = limpiar(r[idx["rp_codigo_alfanumerico"]])
        lat, lon = _num(r[idx["latitud"]]), _num(r[idx["longitud"]])
        if lat is None or lon is None:
            continue
        sentido = 0 if cod.startswith("1") else 1 if cod.startswith("2") else None
        out.append({"nombre": limpiar(r[idx["Name"]]), "codigo": cod,
                    "orden": _num(r[idx["rp_numero"]]), "lat": lat, "lon": lon,
                    "sentido": sentido})
    return out


def parse_aerodirecto_centro(path):
    """1132-SX: columnas sin encabezado -> sentido, codigo, nombre, id, 'lat, lon'."""
    out = []
    for r in _filas(path):
        if not r or not r[0] or str(r[0]).strip() not in ("IDA", "RETORNO"):
            continue
        try:
            lat, lon = [float(x) for x in str(r[4]).split(",")]
        except (ValueError, TypeError, IndexError):
            continue
        out.append({"nombre": limpiar(r[2]), "codigo": limpiar(r[3]),
                    "orden": None, "lat": lat, "lon": lon,
                    "sentido": 0 if str(r[0]).strip() == "IDA" else 1})
    for i, p in enumerate(out):
        p["orden"] = i + 1
    return out


def parse_columna_sentido(path):
    """1481 LA 50: trae columna SENTIDO explicita."""
    filas = _filas(path)
    idx = {h: i for i, h in enumerate(filas[0]) if h}
    out = []
    for r in filas[1:]:
        lat, lon = _num(r[idx["LATITUD"]]), _num(r[idx["LONGITUD"]])
        if lat is None or lon is None:
            continue
        s = limpiar(r[idx["SENTIDO"]]).upper()
        out.append({"nombre": limpiar(r[idx["Name"]]), "codigo": "",
                    "orden": _num(r[idx["Ndeg"]]), "lat": lat, "lon": lon,
                    "sentido": 0 if s == "IDA" else 1})
    return out


def parse_prefijo_ab(path):
    """1185 ETUCHISA: el nombre arranca con A## (ida) o B## (retorno)."""
    filas = _filas(path)
    idx = {h: i for i, h in enumerate(filas[0]) if h}
    out = []
    for r in filas[1:]:
        lat, lon = _num(r[idx["Latitud"]]), _num(r[idx["Longitud"]])
        if lat is None or lon is None:
            continue
        nombre = limpiar(r[idx["Name"]])
        m = re.match(r"^([AB])\d+\s*", nombre)
        sentido = None
        if m:
            sentido = 0 if m.group(1) == "A" else 1
            nombre = nombre[m.end():].strip() or nombre
        out.append({"nombre": nombre, "codigo": limpiar(r[idx["Codigo"]]),
                    "orden": _num(r[idx["Numero"]]), "lat": lat, "lon": lon,
                    "sentido": sentido})
    return out


def parse_reinicio_numero(path):
    """1180 NUEVA AMERICA: numeracion corrida 1..310 sin marcador de sentido.

    Se lee plano y el sentido se resuelve despues por geometria (ver
    partir_por_geometria), porque el archivo no lo declara de ninguna forma.
    """
    filas = _filas(path)
    idx = {h: i for i, h in enumerate(filas[0]) if h}
    out = []
    for r in filas[1:]:
        lat, lon = _num(r[idx["Latitud"]]), _num(r[idx["Longitud"]])
        if lat is None or lon is None:
            continue
        out.append({"nombre": limpiar(r[idx["Name"]]),
                    "codigo": limpiar(r[idx["Codigo_alfanumerico"]]),
                    "orden": _num(r[idx["Numero"]]), "lat": lat, "lon": lon,
                    "sentido": None})
    return out


def parse_aerodirecto_norte(path):
    """1435-SX: sin columna de sentido. Una fila 'IDA' separa los bloques y la
    ultima es el 'Poligono sin titulo' que AEMUS no ha explicado.

    Esa fila rotula el bloque que viene DESPUES, no el anterior: el primer
    bloque va del norte al aeropuerto (retorno) y el segundo del aeropuerto al
    norte (ida), que es el sentido de IDA_AERODIRECTO_NORTE.kml. Lo confirma
    la comprobacion de coherencia: leido al reves, ninguna parada avanza a lo
    largo de su trazado.
    """
    filas = _filas(path)
    idx = {h: i for i, h in enumerate(filas[0]) if h}
    crudo = []
    for r in filas[1:]:
        lat, lon = _num(r[idx["Y"]]), _num(r[idx["X"]])
        if lat is None or lon is None:
            continue
        crudo.append({"nombre": limpiar(r[idx["Name"]]), "codigo": "",
                      "orden": None, "lat": lat, "lon": lon, "sentido": None})
    out, sentido = [], 1               # antes del marcador: retorno
    for p in crudo:
        etiqueta = p["nombre"].upper()
        if etiqueta == "IDA":            # marcador, no es paradero
            sentido = 0
            continue
        if "POLIGONO" in etiqueta or "POLÍGONO" in etiqueta:
            continue                      # elemento no identificado
        p["sentido"] = sentido
        out.append(p)
    for i, p in enumerate(out):
        p["orden"] = i + 1
    return out


PARSERS = {
    "urbanito": parse_urbanito,
    "aerodirecto_centro": parse_aerodirecto_centro,
    "columna_sentido": parse_columna_sentido,
    "prefijo_ab": parse_prefijo_ab,
    "reinicio_numero": parse_reinicio_numero,
    "aerodirecto_norte": parse_aerodirecto_norte,
}


# --- validacion geometrica --------------------------------------------------
def proyectar(punto, trazado):
    """Proyecta el punto sobre la polilinea.

    Devuelve (distancia_perpendicular_m, distancia_recorrida_m). La segunda es
    cuanto hay que avanzar por el trazado hasta llegar al punto proyectado: es
    justo lo que ordena las paradas a lo largo del recorrido.
    """
    if not trazado:
        return None, None
    lat0 = math.radians(punto[0])
    mx = 111320.0 * math.cos(lat0)   # metros por grado de longitud
    my = 110540.0                    # metros por grado de latitud
    px, py = punto[1] * mx, punto[0] * my

    mejor_d2, mejor_s = float("inf"), 0.0
    recorrido = 0.0
    for i in range(len(trazado) - 1):
        ax, ay = trazado[i][1] * mx, trazado[i][0] * my
        bx, by = trazado[i + 1][1] * mx, trazado[i + 1][0] * my
        vx, vy = bx - ax, by - ay
        largo2 = vx * vx + vy * vy
        if largo2 == 0:
            continue
        t = ((px - ax) * vx + (py - ay) * vy) / largo2
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t * vx, ay + t * vy
        d2 = (px - cx) ** 2 + (py - cy) ** 2
        if d2 < mejor_d2:
            mejor_d2 = d2
            mejor_s = recorrido + t * math.sqrt(largo2)
        recorrido += math.sqrt(largo2)
    return math.sqrt(mejor_d2), mejor_s


def coherencia_sentido(paradas, traza):
    """Porcentaje de paradas consecutivas que avanzan a lo largo del trazado.

    Si el bloque esta asignado al sentido correcto, cada parada queda mas
    adelante que la anterior. Un valor bajo delata que el archivo rotulo los
    bloques al reves, que es justo lo que pasaba con la 1435-SX.
    """
    if len(paradas) < 3:
        return 100
    rec = [proyectar((p["lat"], p["lon"]), traza)[1] for p in paradas]
    subidas = sum(1 for i in range(1, len(rec)) if rec[i] > rec[i - 1])
    return 100 * subidas // (len(rec) - 1)


def dist_al_trazado(punto, trazado, muestreo=1):
    """Distancia perpendicular del punto al trazado."""
    d, _ = proyectar(punto, trazado)
    return d


def partir_por_geometria(paradas, ida, ret):
    """Asigna sentido cuando el archivo no lo declara.

    Las paradas vienen numeradas de corrido: primero todo el recorrido de ida y
    luego el de vuelta. Se busca el corte k que deja a las paradas 0..k lo mas
    pegadas posible al trazado de ida y a las k..n lo mas pegadas al de vuelta.
    Comparar distancias acumuladas es mas estable que buscar el maximo, porque
    ambos sentidos comparten avenidas y las proyecciones se confunden ahi.
    """
    if not ida or not ret:
        return paradas
    d_ida = [proyectar((p["lat"], p["lon"]), ida)[0] for p in paradas]
    d_ret = [proyectar((p["lat"], p["lon"]), ret)[0] for p in paradas]

    n = len(paradas)
    suf = [0.0] * (n + 1)          # coste de mandar el tramo final al retorno
    for i in range(n - 1, -1, -1):
        suf[i] = suf[i + 1] + d_ret[i]
    mejor_k, mejor_coste, acum = 0, float("inf"), 0.0
    for k in range(n + 1):
        coste = acum + suf[k]
        if coste < mejor_coste:
            mejor_coste, mejor_k = coste, k
        if k < n:
            acum += d_ida[k]

    for i, p in enumerate(paradas):
        p["sentido"] = 0 if i < mejor_k else 1
    return paradas


def main():
    os.makedirs(OUT, exist_ok=True)
    diag = []
    stops, trips, shapes_rows, routes_rows = [], [], [], []
    stop_seen = {}

    for ruta in RUTAS:
        rid = ruta["route_id"]
        paradas = PARSERS[ruta["parser"]](os.path.join(SRC, ruta["xlsx"]))
        ida = leer_kml(ruta["kml_ida"])
        ret = leer_kml(ruta["kml_ret"])
        # Si snapping.py ya ajusto los trazados a la red vial, se usan esos:
        # siguen la curvatura real de la calle en vez de cortar por lo derecho.
        if SNAPPED:
            ida = [tuple(p) for p in SNAPPED.get("%s_0" % rid, ida)]
            ret = [tuple(p) for p in SNAPPED.get("%s_1" % rid, ret)]
        faltantes = sum(1 for p in paradas if p["sentido"] is None)
        if faltantes == len(paradas):
            # El archivo no declara sentido en ninguna fila: hay que inferirlo
            # para toda la ruta.
            paradas = partir_por_geometria(paradas, ida, ret)
            inferidas = len(paradas)
        elif faltantes:
            # Solo faltan algunas: se respeta lo declarado y se resuelven esas
            # por cercania, sin tocar el resto.
            for p in paradas:
                if p["sentido"] is None:
                    di = dist_al_trazado((p["lat"], p["lon"]), ida)
                    dr = dist_al_trazado((p["lat"], p["lon"]), ret)
                    p["sentido"] = 0 if (di or 0) <= (dr or 0) else 1
            inferidas = faltantes
        else:
            inferidas = 0

        # Orden real a lo largo del recorrido. Es el stop_sequence que usara
        # stop_times.txt en cuanto AEMUS entregue los horarios.
        for p in paradas:
            trazado = ida if p["sentido"] == 0 else ret
            p["dist"], p["recorrido"] = proyectar((p["lat"], p["lon"]), trazado)
        paradas.sort(key=lambda p: (p["sentido"], p["recorrido"] or 0))

        # shapes
        for nombre_sh, pts in (("%s_0" % rid, ida), ("%s_1" % rid, ret)):
            acumulado = 0.0
            for i, (lat, lon) in enumerate(pts):
                if i:
                    acumulado += haversine(pts[i - 1], (lat, lon))
                shapes_rows.append([nombre_sh, "%.6f" % lat, "%.6f" % lon,
                                    i, "%.1f" % acumulado])

        routes_rows.append([rid, ruta["agency_id"], ruta["nombre_corto"],
                            ruta["nombre_largo"], 3])

        for direccion, pts in ((0, ida), (1, ret)):
            trips.append(["%s_%d" % (rid, direccion), rid,
                          "%s_%d" % (rid, direccion), direccion,
                          "%s_%d" % (rid, direccion)])

        # stops + control de calidad
        fuera, lejos, sin_sentido, dups = [], [], 0, 0
        for p in paradas:
            if p["sentido"] is None:
                sin_sentido += 1
            if not en_lima(p["lat"], p["lon"]):
                fuera.append(p)
                continue
            d = p["dist"]
            if d is not None and d > 150:
                lejos.append((p, round(d)))
            sid = "%s_%s_%s" % (rid, p["sentido"], p["codigo"] or int(p["orden"] or 0))
            if sid in stop_seen:
                dups += 1
                sid = sid + "_b"
            stop_seen[sid] = True
            stops.append([sid, p["nombre"] or "Paradero", "%.6f" % p["lat"],
                          "%.6f" % p["lon"]])

        coher = {}
        for sd in (0, 1):
            blo = [p for p in paradas if p["sentido"] == sd]
            traza = ida if sd == 0 else ret
            otra = ret if sd == 0 else ida
            coher[sd] = (coherencia_sentido(blo, traza),
                         coherencia_sentido(blo, otra))

        diag.append({
            "coherencia": coher,
            "ruta": ruta, "total": len(paradas),
            "ida": sum(1 for p in paradas if p["sentido"] == 0),
            "ret": sum(1 for p in paradas if p["sentido"] == 1),
            "sin_sentido": inferidas, "fuera": fuera, "lejos": lejos,
            "dups": dups,
            "km_ida": sum(haversine(ida[i], ida[i + 1]) for i in range(len(ida) - 1)) / 1000,
            "km_ret": sum(haversine(ret[i], ret[i + 1]) for i in range(len(ret) - 1)) / 1000,
            "paradas": paradas,
        })

    # Secuencia de paradas a lo largo de cada recorrido. Es el insumo directo
    # de stop_times.txt: en cuanto lleguen los horarios, solo hay que repartir
    # los tiempos sobre esta secuencia.
    sec_rows = []
    for d in diag:
        rid = d["ruta"]["route_id"]
        seq = {0: 0, 1: 0}
        for p in d["paradas"]:
            s = p["sentido"]
            seq[s] += 1
            sec_rows.append([rid, d["ruta"]["marca"], s, seq[s], p["nombre"],
                             "%.6f" % p["lat"], "%.6f" % p["lon"],
                             "%.0f" % (p["recorrido"] or 0),
                             "%.0f" % (p["dist"] or 0)])

    def escribir(nombre, cabecera, filas):
        with open(os.path.join(OUT, nombre), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(cabecera)
            w.writerows(filas)

    escribir("agency.txt",
             ["agency_id", "agency_name", "agency_url", "agency_timezone", "agency_lang"],
             [[a[0], a[1], "https://www.aemus.com.pe", "America/Lima", "es"]
              for a in AGENCIAS])
    escribir("routes.txt",
             ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type"],
             routes_rows)
    escribir("stops.txt", ["stop_id", "stop_name", "stop_lat", "stop_lon"], stops)
    escribir("shapes.txt",
             ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence",
              "shape_dist_traveled"], shapes_rows)
    escribir("trips.txt",
             ["trip_id", "route_id", "service_id", "direction_id", "shape_id"], trips)

    with open(os.path.join(os.path.dirname(OUT), "secuencia_paradas.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["route_id", "marca", "direction_id", "stop_sequence",
                    "stop_name", "lat", "lon", "recorrido_m", "desvio_m"])
        w.writerows(sec_rows)

    # Plantilla que se le pide llenar a AEMUS. Una fila por ruta y sentido.
    campos = ["primera_salida", "ultima_salida", "frec_punta_am_min",
              "frec_valle_min", "frec_punta_pm_min", "opera_lun_vie",
              "opera_sabado", "opera_domingo_feriado", "tarifa_soles"]
    with open(os.path.join(os.path.dirname(OUT), "PLANTILLA_HORARIOS_AEMUS.csv"),
              "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["codigo_ruta", "empresa", "ruta", "sentido"] + campos)
        for r in RUTAS:
            emp = next(a[1] for a in AGENCIAS if a[0] == r["agency_id"])
            for sent in ("IDA", "RETORNO"):
                w.writerow([r["codigo"], emp, r["marca"], sent] + [""] * len(campos))

    # --- reporte -----------------------------------------------------------
    L = ["# Diagnostico de datos AEMUS -> GTFS",
         "", "Generado por `build/etl.py` sobre el paquete del 2026-07-21.", "",
         "## Resumen por ruta", "",
         "| Ruta | Marca | Paradas | Ida | Ret | Sentido inferido | Fuera de Lima | >150m del trazado | Km ida | Km ret |",
         "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for d in diag:
        L.append("| %s | %s | %d | %d | %d | %d | %d | %d | %.1f | %.1f |" % (
            d["ruta"]["codigo"], d["ruta"]["marca"], d["total"], d["ida"], d["ret"],
            d["sin_sentido"], len(d["fuera"]), len(d["lejos"]), d["km_ida"], d["km_ret"]))

    L += ["", "## Coherencia del sentido declarado", "",
          "Porcentaje de paradas que avanzan a lo largo de su propio trazado. "
          "Un valor bajo, con el contrario alto, significa que el archivo de "
          "origen rotulo los bloques al reves.", "",
          "| Ruta | Ida | Ida invertida | Retorno | Retorno invertido | Estado |",
          "|---|---:|---:|---:|---:|---|"]
    for d in diag:
        c = d["coherencia"]
        mal = c[0][1] > c[0][0] + 25 or c[1][1] > c[1][0] + 25
        L.append("| %s %s | %d%% | %d%% | %d%% | %d%% | %s |" % (
            d["ruta"]["codigo"], d["ruta"]["marca"], c[0][0], c[0][1],
            c[1][0], c[1][1], "**INVERTIDO**" if mal else "ok"))

    L += ["", "## Paradas con coordenadas fuera de Lima Metropolitana", "",
          "Estas filas traen lat/lon inconsistentes en el archivo de origen.", ""]
    hay = False
    for d in diag:
        for p in d["fuera"]:
            hay = True
            L.append("- **%s** (%s): `%s` -> %.6f, %.6f" % (
                d["ruta"]["codigo"], d["ruta"]["marca"], p["nombre"], p["lat"], p["lon"]))
    if not hay:
        L.append("_Ninguna._")

    L += ["", "## Paradas a mas de 150 m de su trazado", "",
          "Sugieren coordenada equivocada o sentido mal asignado. "
          "Se listan las 15 peores por ruta.", ""]
    for d in diag:
        if not d["lejos"]:
            continue
        L.append("### %s %s (%d casos)" % (d["ruta"]["codigo"], d["ruta"]["marca"], len(d["lejos"])))
        for p, dist in sorted(d["lejos"], key=lambda x: -x[1])[:15]:
            L.append("- %s m -- `%s` (%.6f, %.6f)" % (dist, p["nombre"], p["lat"], p["lon"]))
        L.append("")

    L += ["", "## Tablas GTFS generadas", "",
          "| Tabla | Filas | Estado |", "|---|---:|---|",
          "| agency.txt | %d | Falta telefono y web por empresa |" % len(AGENCIAS),
          "| routes.txt | %d | Codigo de LA 50 pendiente de confirmar |" % len(routes_rows),
          "| stops.txt | %d | Completa |" % len(stops),
          "| shapes.txt | %d | Completa |" % len(shapes_rows),
          "| trips.txt | %d | Sin service_id real |" % len(trips),
          "| stop_times.txt | 0 | **BLOQUEADA** -- faltan horarios |",
          "| calendar.txt | 0 | **BLOQUEADA** -- faltan dias de operacion |",
          "| frequencies.txt | 0 | **BLOQUEADA** -- faltan frecuencias |",
          "| fare_attributes.txt | 0 | **BLOQUEADA** -- falta tarifa |", ""]

    with open(os.path.join(os.path.dirname(OUT), "diagnostico.md"), "w",
              encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    print("\n".join(L[:40]))
    print("\nGTFS parcial en:", OUT)


if __name__ == "__main__":
    main()
