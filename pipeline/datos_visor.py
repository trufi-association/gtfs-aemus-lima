#!/usr/bin/env python3
"""
Genera el paquete de datos que consume el visor de calidad.

Reune en un solo JSON lo que hoy esta disperso en varios reportes: trazados,
paraderos, la auditoria de map-matching y los hallazgos que requieren decision
del cliente. El visor lo incrusta, asi que se simplifican las geometrias para
que el archivo sea liviano sin perder fidelidad visual.
"""
import datetime
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from etl import (KML_DIR, PARSERS, RUTAS, SNAPPED, SRC,  # noqa: E402
                 dist_al_trazado, haversine, leer_kml, partir_por_geometria,
                 proyectar)

AQUI = os.path.dirname(os.path.abspath(__file__))

# Umbrales de clasificacion de un paradero segun su distancia al recorrido.
OK = 25       # m — dentro de la tolerancia normal de digitalizacion
REVISAR = 150  # m — por encima, requiere verificacion del operador

COLORES = {"1132": "#00508c", "1132SX": "#3fb498", "1180": "#ed6a5b",
           "1435SX": "#a97500", "1185": "#5c9833", "1481": "#7b4fa3"}


def simplificar(pts, tol=1.0):
    """Douglas-Peucker sobre coordenadas geograficas (tolerancia en metros).

    Con el mapa de fondo servido por teselas ya no hace falta recortar la
    geometria para ahorrar peso: la tolerancia es minima para no perder las
    curvas que el ajuste a la red vial acaba de reconstruir.
    """
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
        largo2 = vx * vx + vy * vy
        peor_d, peor_i = -1.0, 0
        for i in range(1, len(sub) - 1):
            px, py = sub[i][1] * mx, sub[i][0] * my
            if largo2 == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / largo2))
                d = math.hypot(px - (ax + t * vx), py - (ay + t * vy))
            if d > peor_d:
                peor_d, peor_i = d, i
        if peor_d <= tol:
            return [sub[0], sub[-1]]
        return rec(sub[:peor_i + 1])[:-1] + rec(sub[peor_i:])

    return rec(list(pts))


REFS = os.path.join(AQUI, "referencias.json")
HOY = datetime.date.today().isoformat()


def clave_estable(codigo, parada):
    """Identidad de un paradero que sobrevive a que cambien los datos.

    No se usan la distancia ni el orden, que son justamente lo que varia cuando
    AEMUS corrige un trazado. Nombre y sentido si se mantienen.

    El nombre solo no basta: la 1180 tiene dos paraderos consecutivos llamados
    'Pdro. Torre Blanca' en el mismo sentido, separados por 8 m. Tampoco sirve
    la coordenada, por lo pegados que estan. Se desempata con el orden relativo
    entre homonimos, que solo cambiaria si AEMUS reordenara la ruta.
    """
    nombre = " ".join(str(parada["n"]).upper().split())
    return "%s|%d|%s|%d" % (codigo, parada["s"], nombre, parada.get("rep", 1))


def marcar_repeticiones(paradas):
    """Numera los paraderos que comparten nombre y sentido, por orden de paso."""
    grupos = {}
    for p in sorted(paradas, key=lambda x: (x["s"], x["q"])):
        k = (p["s"], " ".join(str(p["n"]).upper().split()))
        grupos[k] = grupos.get(k, 0) + 1
        p["rep"] = grupos[k]


def cargar_refs():
    try:
        with open(REFS, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"asignadas": {}, "ultimo": {}}


def asignar_refs(codigo, observadas, registro, fecha):
    """Da una referencia a cada paradero observado, conservando las ya emitidas.

    Un numero emitido no se reutiliza nunca, aunque el paradero deje de estar
    observado: si se cita '1132-03' en un correo, debe seguir significando lo
    mismo dentro de seis meses.
    """
    asignadas, ultimo = registro["asignadas"], registro["ultimo"]
    nuevas = 0
    for p in sorted(observadas, key=lambda x: -x["d"]):
        k = clave_estable(codigo, p)
        if k not in asignadas:
            n = ultimo.get(codigo, 0) + 1
            ultimo[codigo] = n
            asignadas[k] = {"ref": "%s-%02d" % (codigo, n), "desde": fecha}
            nuevas += 1
        p["ref"] = asignadas[k]["ref"]
        p["desde"] = asignadas[k]["desde"]
    return nuevas


def fecha_kml(nombre):
    """Fecha del archivo KML tal como vino en el paquete de AEMUS.

    Revela si un recorrido se reenvio sin actualizar: varios archivos del
    paquete de julio de 2026 son de 2025 e incluso de 2023.
    """
    ruta = os.path.join(KML_DIR, nombre)
    try:
        return datetime.date.fromtimestamp(os.path.getmtime(ruta)).isoformat()
    except OSError:
        return None


def leer_auditoria():
    """Recupera la tabla de map-matching que dejo auditoria_geometria.py."""
    ruta = os.path.join(AQUI, "AUDITORIA_GEOMETRIA.md")
    datos = {}
    try:
        with open(ruta, encoding="utf-8") as fh:
            for ln in fh:
                if not ln.startswith("|") or "---" in ln or "Ruta |" in ln:
                    continue
                c = [x.strip() for x in ln.strip().strip("|").split("|")]
                if len(c) < 9 or c[5] in ("-", ""):
                    continue
                datos.setdefault(c[0], {})[c[2]] = {
                    "medio": float(c[5]), "max": float(c[6]),
                    "fuera": c[7], "vias": c[8]}
    except OSError:
        pass
    return datos


def main():
    try:
        with open(os.path.join(AQUI, "traza_estricta.json"), encoding="utf-8") as fh:
            globals()["TRAZA"] = json.load(fh)
    except (OSError, ValueError):
        globals()["TRAZA"] = {}
    auditoria = leer_auditoria()
    registro = cargar_refs()
    nuevas, vigentes = 0, set()
    salida = {"rutas": [], "resumen": {}}
    total_paradas = total_ok = total_medio = total_alto = 0

    for ruta in RUTAS:
        rid = ruta["route_id"]
        paradas = PARSERS[ruta["parser"]](os.path.join(SRC, ruta["xlsx"]))
        crudo = {0: leer_kml(ruta["kml_ida"]), 1: leer_kml(ruta["kml_ret"])}
        traza = {s: [tuple(p) for p in SNAPPED.get("%s_%d" % (rid, s), crudo[s])]
                 for s in (0, 1)}

        faltantes = sum(1 for p in paradas if p["sentido"] is None)
        if faltantes == len(paradas):
            paradas = partir_por_geometria(paradas, traza[0], traza[1])
            inferido = "todas"
        elif faltantes:
            for p in paradas:
                if p["sentido"] is None:
                    di = dist_al_trazado((p["lat"], p["lon"]), traza[0])
                    dr = dist_al_trazado((p["lat"], p["lon"]), traza[1])
                    p["sentido"] = 0 if (di or 0) <= (dr or 0) else 1
            inferido = "%d de %d" % (faltantes, len(paradas))
        else:
            inferido = "ninguna"

        for p in paradas:
            p["dist"], p["recorrido"] = proyectar((p["lat"], p["lon"]), traza[p["sentido"]])
        paradas.sort(key=lambda p: (p["sentido"], p["recorrido"] or 0))

        lista, seq = [], {0: 0, 1: 0}
        for p in paradas:
            s = p["sentido"]
            seq[s] += 1
            d = round(p["dist"] or 0)
            estado = "ok" if d <= OK else ("medio" if d <= REVISAR else "alto")
            total_paradas += 1
            total_ok += estado == "ok"
            total_medio += estado == "medio"
            total_alto += estado == "alto"
            lista.append({"n": p["nombre"], "la": round(p["lat"], 6),
                          "lo": round(p["lon"], 6), "s": s, "q": seq[s],
                          "d": d, "e": estado})

        # Identificador estable por observacion: es lo que permite al operador
        # responder "el 1132-03 si pasa por ahi" sin describir el paradero.
        marcar_repeticiones(lista)
        obs = [x for x in lista if x["e"] != "ok"]
        nuevas += asignar_refs(ruta["codigo"], obs, registro, HOY)
        vigentes.update(clave_estable(ruta["codigo"], x) for x in obs)

        km = {s: sum(haversine(traza[s][i], traza[s][i + 1])
                     for i in range(len(traza[s]) - 1)) / 1000 for s in (0, 1)}

        salida["rutas"].append({
            "id": rid, "codigo": ruta["codigo"], "marca": ruta["marca"],
            "nombre": ruta["nombre_largo"], "empresa": ruta["agency_id"],
            "color": COLORES.get(rid, "#2C3438"),
            "codigo_interno": ruta["codigo_interno"],
            "sentido_inferido": inferido,
            "auditoria": auditoria.get(ruta["codigo"], {}),
            "km": [round(km[0], 1), round(km[1], 1)],
            "vertices": [len(traza[0]), len(traza[1])],
            "vertices_crudo": [len(crudo[0]), len(crudo[1])],
            "trazado": [[[round(a, 5), round(b, 5)] for a, b in simplificar(traza[0])],
                        [[round(a, 5), round(b, 5)] for a, b in simplificar(traza[1])]],
            # El recorrido tal como lo envio AEMUS, antes de ajustarlo a la red
            # vial. El visor lo ofrece como capa opcional para poder comparar.
            "crudo": [[[round(a, 5), round(b, 5)] for a, b in simplificar(crudo[0])],
                      [[round(a, 5), round(b, 5)] for a, b in simplificar(crudo[1])]],
            "kml": [ruta["kml_ida"], ruta["kml_ret"]],
            "kml_fecha": [fecha_kml(ruta["kml_ida"]), fecha_kml(ruta["kml_ret"])],
            # Auditoria contra la red vial estricta (trace_route): el recorrido
            # navegable y los puntos donde se aparta del KML o se corta. Cada
            # marcador es una maniobra indebida del bus o un error de mapa.
            "traza_ok": [TRAZA.get("%s_0" % rid, {}).get("traza", []),
                         TRAZA.get("%s_1" % rid, {}).get("traza", [])],
            "marcas": [TRAZA.get("%s_0" % rid, {}).get("marcadores", []),
                       TRAZA.get("%s_1" % rid, {}).get("marcadores", [])],
            "paradas": lista,
        })

    # Hallazgos que no son de un paradero concreto sino de la ruta o del
    # conjunto. Llevan el mismo tipo de referencia para poder citarlos igual.
    salida["hallazgos"] = [
        {"ref": "GEN-01", "ambito": "Las seis rutas",
         "titulo": "Numeración de rutas sin confirmar",
         "texto": "Conviven cuatro numeraciones para las mismas rutas. La 1481 "
                  "LA 50 figura también como 1431 y como 1066. Se requiere el "
                  "cuadro oficial vigente del plan regulador.",
         "pide": "Cuadro de rutas oficial vigente."},
        {"ref": "1132-G1", "ambito": "Ruta 1132 URBANITO",
         "titulo": "Posible tramo faltante en el recorrido",
         "texto": "Cinco paraderos de Bauzate y Meza y Lucanas quedan hasta a "
                  "400 m del recorrido. El ajuste a la red vial no los acercó, "
                  "así que no son coordenadas erróneas: al trazado le faltaría "
                  "ese tramo.",
         "pide": "Confirmar si la ruta circula por ese sector y enviar el trazado."},
        {"ref": "1435-G1", "ambito": "Ruta 1435-SX AERODIRECTO NORTE",
         "titulo": "Elemento sin identificar",
         "texto": "El archivo de paraderos incluye un «Polígono sin título» que "
                  "no corresponde a un paradero. Se excluyó del procesamiento.",
         "pide": "Indicar qué representa y confirmar si 24 paraderos es el total."},
        {"ref": "1180-G1", "ambito": "Ruta 1180 NUEVA AMÉRICA",
         "titulo": "Sentido deducido por geometría",
         "texto": "Sus 310 paraderos vienen numerados de corrido, sin marca de "
                  "ida o retorno. El sentido se dedujo proyectando cada paradero "
                  "sobre ambos recorridos.",
         "pide": "Confirmar que se listan primero todos los de ida y luego los de vuelta."},
        {"ref": "GEN-02", "ambito": "Las cuatro empresas",
         "titulo": "Faltan datos de contacto",
         "texto": "Se recibió razón social y RUC, pero no teléfono de atención al "
                  "público ni sitio web. El estándar GTFS los usa para indicarle "
                  "al pasajero a quién dirigirse.",
         "pide": "Teléfono y sitio web por empresa."},
    ]

    # Discrepancias del ajuste contra el KML, si discrepancias.py ya corrio.
    try:
        with open(os.path.join(AQUI, "discrepancias.json"), encoding="utf-8") as fh:
            salida["discrepancias"] = json.load(fh)
    except (OSError, ValueError):
        salida["discrepancias"] = []

    salida["resumen"] = {
        "paradas": total_paradas, "ok": total_ok,
        "medio": total_medio, "alto": total_alto,
        "rutas": len(RUTAS), "empresas": 4,
    }

    # Observaciones que ya no aparecen: el paradero se corrigio o el trazado
    # cambio. La referencia se conserva para poder decir "1132-03 resuelto".
    resueltas = []
    for k, v in registro["asignadas"].items():
        if k not in vigentes:
            codigo, sentido, nombre = k.split("|", 2)
            v.setdefault("resuelta", HOY)
            resueltas.append({"ref": v["ref"], "ruta": codigo, "n": nombre,
                              "s": int(sentido), "desde": v["desde"],
                              "resuelta": v["resuelta"]})
        elif "resuelta" in v:
            del v["resuelta"]          # volvio a aparecer
    salida["resueltas"] = sorted(resueltas, key=lambda x: x["ref"])
    salida["fecha"] = HOY

    with open(REFS, "w", encoding="utf-8") as fh:
        json.dump(registro, fh, ensure_ascii=False, indent=1, sort_keys=True)

    destino = os.path.join(AQUI, "datos_visor.json")
    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(salida, fh, ensure_ascii=False, separators=(",", ":"))
    print("%s  (%.0f KB)" % (destino, os.path.getsize(destino) / 1024))
    print("paradas %d — ok %d · revisar %d · alto %d"
          % (total_paradas, total_ok, total_medio, total_alto))
    print("referencias: %d vigentes (%d nuevas) · %d resueltas"
          % (len(vigentes), nuevas, len(resueltas)))


if __name__ == "__main__":
    main()
