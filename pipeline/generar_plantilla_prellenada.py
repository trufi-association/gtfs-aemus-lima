#!/usr/bin/env python3
"""
Genera la plantilla operativa PRE-LLENADA para la reunion con AEMUS.

Combina tres origenes, cada uno con su color:
  VERDE  = observado por Trufi en los GPS de la flota (a confirmar)
  CREMA  = declarado por el operador (lo que URBANITO envio)
  BLANCO = pendiente: no hay dato, lo debe aportar AEMUS

Incluye una hoja "Estado de datos" con la matriz de que falta por ruta.

Uso: python3 generar_plantilla_prellenada.py <ruta_a_frecuencias_gps.json>
Salida: PLANTILLA_HORARIOS_AEMUS_PRELLENADA.xlsx (en la carpeta del cliente)
"""
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from etl import AGENCIAS, RUTAS  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
CLIENTE = os.path.abspath(os.path.join(AQUI, "..", ".."))

OSCURO = "2C3438"
VERDE = "D9EAD3"     # observado GPS
CREMA = "FFF2CC"     # declarado operador
GRIS = "F2F6F7"      # etiquetas de fila
BLANCO = "FFFFFF"

CAB = ["Código", "Empresa", "Ruta", "Sentido", "Tipo de día",
       "Desde", "Hasta", "Cada cuántos min", "Origen del dato", "Observaciones"]

# Datos declarados por URBANITO en su archivo (rutas 1132 y 1132-SX).
DECLARADO = {
    "1132-SX": {
        "IDA": ("05:00", "00:00", "15"),
        "RETORNO": ("06:00", "00:00", "15"),
        "obs": "Declarado URBANITO · dom desde 05:00 · frec. 15 en todas las franjas",
    },
}
# Tarifas declaradas por URBANITO.
TARIFAS_DECL = {
    "1132": [("Adulto", "2.50"), ("Escolar / universitario", "1.20")],
    "1132-SX": [("Adulto", "5.00"), ("Escolar / universitario", "2.50")],
}
GPS_RUTAS = {"1185", "1481", "1132"}


def empresa_de(ruta):
    return next(a[1] for a in AGENCIAS if a[0] == ruta["agency_id"])


def cabecera(ws, ncols):
    b = Side(style="thin", color="D7DEE0")
    for c in range(1, ncols + 1):
        cel = ws.cell(row=1, column=c)
        cel.font = Font(bold=True, size=10, color="FFFFFF")
        cel.fill = PatternFill("solid", fgColor=OSCURO)
        cel.alignment = Alignment(vertical="center", wrap_text=True)
        cel.border = Border(bottom=b)
    ws.row_dimensions[1].height = 30


def fila(ws, valores, color):
    ws.append(valores)
    b = Side(style="thin", color="E4EAEC")
    for c in range(1, len(CAB) + 1):
        cel = ws.cell(row=ws.max_row, column=c)
        cel.font = Font(size=10)
        cel.border = Border(bottom=b)
        cel.fill = PatternFill("solid", fgColor=(GRIS if c <= 5 else color))


def main():
    freq = json.load(open(sys.argv[1], encoding="utf-8"))
    wb = Workbook()

    # ---------- Hoja 1: Instrucciones / leyenda ----------
    ws = wb.active
    ws.title = "Instrucciones"
    ws["A1"] = "Información operativa de rutas — AEMUS (pre-llenada)"
    ws["A1"].font = Font(bold=True, size=15, color=OSCURO)
    ws["A2"] = "Trufi Association e.V. · GTFS de Lima"
    ws["A2"].font = Font(size=11, color="6E7A80")
    notas = [
        ("", ""),
        ("Cómo leer los colores", ""),
        ("VERDE", "Lo que Trufi OBSERVÓ en los GPS de su propia flota (jul-2026). "
                  "Es una referencia: por favor confírmenlo o corríjanlo."),
        ("CREMA", "Lo que ustedes ya nos declararon (URBANITO). Verificar que siga vigente."),
        ("BLANCO", "Pendiente: no tenemos el dato. Lo necesitamos de ustedes."),
        ("", ""),
        ("Sobre las frecuencias", "No pedimos una frecuencia única. Cada fila es un "
                                   "tramo horario (Desde–Hasta) con su frecuencia. Si "
                                   "depende de la hora pico, así se refleja: varias filas."),
        ("", "Si despachan por tabla de salidas con horas fijas, mándennos esa tabla "
             "tal cual: nos sirve igual o mejor."),
        ("", ""),
        ("Ojo", "Lo observado por GPS incluye toda la actividad de la unidad (incluido "
                "regreso a cochera de madrugada/noche); por eso el horario puede verse "
                "más amplio que el servicio comercial. Ese es justo el dato a confirmar."),
    ]
    r = 4
    for t, x in notas:
        if t:
            ws.cell(row=r, column=1, value=t).font = Font(bold=True, size=10, color=OSCURO)
        if x:
            cel = ws.cell(row=r, column=2, value=x)
            cel.alignment = Alignment(wrap_text=True, vertical="top")
            cel.font = Font(size=10)
            ws.row_dimensions[r].height = 15 * (1 + len(x) // 70)
        r += 1
    for etq, col, celda in (("VERDE", VERDE, "A6"), ("CREMA", CREMA, "A7"),
                            ("BLANCO", BLANCO, "A8")):
        ws[celda].fill = PatternFill("solid", fgColor=col)
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 92

    # ---------- Hoja 2: Frecuencias ----------
    ws = wb.create_sheet("Frecuencias")
    ws.append(CAB)
    cabecera(ws, len(CAB))
    for ruta in RUTAS:
        cod = ruta["codigo"]
        emp = empresa_de(ruta)
        if cod in GPS_RUTAS:
            fr = freq.get(cod, {})
            for sent in ("IDA", "RETORNO"):
                s = fr.get("sentidos", {}).get(sent)
                if not s:
                    continue
                for tipo, datos in s["tipos"].items():
                    if not datos:
                        continue
                    # Solo pre-llenamos con cifras si la muestra es suficiente
                    # (L-V tiene 8-10 días; sábado/domingo suelen tener 1-2 y el
                    # dato sale ruidoso). Si no, dejamos la fila marcada a confirmar.
                    if datos["dias_muestra"] < 3:
                        fila(ws, [cod, emp, ruta["marca"], sent, tipo, "", "", "",
                                  "GPS (Trufi)",
                                  "Muestra GPS insuficiente (%d día) — confirmar con "
                                  "AEMUS" % datos["dias_muestra"]], CREMA)
                        continue
                    bloques = [b for b in datos["bloques"] if b["cada_min"]]
                    if not bloques:
                        continue
                    bloques[0] = dict(bloques[0], desde=datos["primera"])
                    bloques[-1] = dict(bloques[-1], hasta=datos["ultima"])
                    obs = "GPS %d días muestra — confirmar" % datos["dias_muestra"]
                    for b in bloques:
                        fila(ws, [cod, emp, ruta["marca"], sent, tipo, b["desde"],
                                  b["hasta"], b["cada_min"], "GPS (Trufi)", obs], VERDE)
        elif cod in DECLARADO:
            d = DECLARADO[cod]
            for sent in ("IDA", "RETORNO"):
                de, ha, ca = d[sent]
                fila(ws, [cod, emp, ruta["marca"], sent, "Lunes a viernes", de, ha,
                          ca, "Declarado URBANITO", d["obs"]], CREMA)
        else:  # pendiente: 1180, 1435-SX
            for sent in ("IDA", "RETORNO"):
                fila(ws, [cod, emp, ruta["marca"], sent, "Lunes a viernes", "", "",
                          "", "PENDIENTE", "Sin dato — completar por AEMUS"], BLANCO)
    for col, w in zip("ABCDEFGHIJ", (8, 30, 20, 9, 17, 8, 8, 10, 16, 40)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "F2"

    # ---------- Hoja 3: Tarifas ----------
    ws = wb.create_sheet("Tarifas")
    cab2 = ["Código", "Empresa", "Ruta", "Tipo de pasaje", "Tarifa (S/)",
            "Origen", "Observaciones"]
    ws.append(cab2)
    cabecera(ws, len(cab2))
    b = Side(style="thin", color="E4EAEC")
    for ruta in RUTAS:
        cod = ruta["codigo"]
        emp = empresa_de(ruta)
        tipos = TARIFAS_DECL.get(cod)
        for tipo, tar in (tipos or [("Adulto", ""), ("Escolar / universitario", "")]):
            ws.append([cod, emp, ruta["marca"], tipo, tar,
                       "Declarado URBANITO" if tipos else "PENDIENTE",
                       "" if tipos else "Sin dato — completar por AEMUS"])
            for c in range(1, len(cab2) + 1):
                cel = ws.cell(row=ws.max_row, column=c)
                cel.font = Font(size=10)
                cel.border = Border(bottom=b)
                cel.fill = PatternFill("solid", fgColor=(
                    GRIS if c <= 4 else (CREMA if tipos else BLANCO)))
    for col, w in zip("ABCDEFG", (8, 30, 20, 24, 12, 18, 34)):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "E2"

    # ---------- Hoja 4: Estado de datos (qué falta) ----------
    ws = wb.create_sheet("Estado de datos")
    cabE = ["Código", "Ruta", "Empresa", "Frecuencias", "Tarifa",
            "Numeración oficial", "GPS recibido"]
    ws.append(cabE)
    cabecera(ws, len(cabE))
    estado = {
        "1132":    ("GPS (confirmar)", "Declarada", "OK (1132)", "Sí"),
        "1132-SX": ("Declarada URBANITO", "Declarada", "OK (11132-SX)", "Mezclado con 1132 — separar"),
        "1180":    ("PENDIENTE", "PENDIENTE", "Por confirmar", "NO — pedir"),
        "1435-SX": ("PENDIENTE", "PENDIENTE", "Por confirmar", "NO — pedir"),
        "1185":    ("GPS (confirmar)", "PENDIENTE", "Por confirmar", "Sí"),
        "1481":    ("GPS (confirmar)", "PENDIENTE", "OK (1481 confirmado)", "Sí"),
    }
    b = Side(style="thin", color="E4EAEC")
    for ruta in RUTAS:
        cod = ruta["codigo"]
        fr, ta, nu, gp = estado[cod]
        ws.append([cod, ruta["marca"], empresa_de(ruta), fr, ta, nu, gp])
        for c in range(1, len(cabE) + 1):
            cel = ws.cell(row=ws.max_row, column=c)
            cel.font = Font(size=10)
            cel.border = Border(bottom=b)
            val = cel.value or ""
            color = BLANCO
            if "PENDIENTE" in val or val.startswith("NO"):
                color = "F4CCCC"   # rojo claro
            elif "GPS" in val or "Declarad" in val or val == "Sí" or "OK" in val:
                color = VERDE
            elif "Mezclado" in val or "confirmar" in val or "Por confirmar" in val:
                color = CREMA
            cel.fill = PatternFill("solid", fgColor=(GRIS if c <= 3 else color))
    for col, w in zip("ABCDEFG", (8, 20, 30, 20, 14, 22, 26)):
        ws.column_dimensions[col].width = w

    destino = os.path.join(CLIENTE, "PLANTILLA_HORARIOS_AEMUS_PRELLENADA.xlsx")
    wb.save(destino)
    print("✔", destino)


if __name__ == "__main__":
    main()
