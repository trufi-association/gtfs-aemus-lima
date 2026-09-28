# Bitácora de decisiones — GTFS AEMUS (6 rutas) · desde 2026-09-28

Complementa `README.md` (pipeline) y sigue la convención del feed ATU
(`../../ATU/DECISIONES_CONSTRUCCION_GTFS.md`): 📄 dato · 🔧 formato · ⚖️ criterio · 🔮 supuesto.
**Las marcas 🔮 son las que hay que revisar cuando AEMUS confirme.**

## Fuentes

| Fuente | Fecha | Qué aporta |
|---|---|---|
| `../../PLANTILLA_HORARIOS_AEMUS_PRELLENADA.xlsx` | devuelta 28-sep-2026 | franjas, frecuencias y tarifas de las 6 rutas (hoja Frecuencias y Tarifas) |
| `../../tiempos_recorrido/TIEMPOS_RECORRIDO_AEMUS_2026-09-28.csv` | generado 28-sep | tiempo de recorrido por ruta, sentido y franja (`tabla_tiempos.py`) |
| `../../tiempos_recorrido/tiempos_gps_1132_1132SX.json` | GPS jul-2026 | viajes observados de la flota SATELITE (`tiempos_gps.py`) |
| `secuencia_paradas.csv`, `gtfs/stops.txt`, `gtfs/shapes.txt` | etl.py, 23-jul | orden y distancia acumulada de cada paradero |

## Decisiones

### D1 — Feed basado en frecuencias ⚖️
Un `trip` por ruta, sentido, servicio y franja de la plantilla (126 trips). `stop_times.txt`
describe el patrón desde 00:00:00; `frequencies.txt` fija las salidas con el intervalo declarado
por la empresa (`exact_times=0`). Coherente con el feed ATU y con el despacho manual que
describió Juan el 18-sep: no existen horas fijas de salida.

### D2 — Servicios y calendario 📄 + ⚖️
Tipos de día de la plantilla → `service_id`: Lunes a viernes = `LV`, Sábado = `SAB`, Domingo y
feriados = `DOM`, Lunes a Sabados = `LS` (1185), Lunes a Domingo = `LD` (1132-SX, 1435-SX).
Vigencia 2026-09-28 → 2027-09-27. **Feriados nacionales del Perú** en `calendar_dates.txt`:
ese día se quita LV/SAB/LS y se añade DOM (16 fechas). La 1180 solo declaró L–V: **sábado y
domingo sin servicio en el feed** hasta que Nueva América lo complete 🔮.

### D3 — Franjas nocturnas ⚖️
«IDA NOCHE 00:00–04:00» y «RETORNO NOCHE 01:00–05:00» (1132-SX, 1435-SX) se cuelgan del día de
servicio anterior como 24:00–28:00 y 25:00–29:00, según el estándar. «Hasta 00:00» = 24:00:00.

### D4 — Tiempo de recorrido 🔮 (lo más importante a validar)
La plantilla no pide tiempo de recorrido. Se derivó así:
- **1132 y 1132-SX: GPS** de la flota SATELITE (jul-2026, 27 unidades, 2 semanas). Método en
  `tiempos_gps.py`: 9 puntos de control cada 10 % del trazado, radio 150 m; un viaje = pasos
  consecutivos en orden con velocidad por tramo entre 3 y 60 km/h; se toleran 2 controles
  perdidos; mediana por franja (solo L–V). 1132 ida: el tramo final del KML (últimos 30 %) no lo
  recorre ningún bus → se escaló el tiempo del 70 % observado. Confirma que el trazado de ida
  de la 1132 no coincide con la operación en la cabecera de La Victoria.
- **1435-SX:** velocidades por franja observadas en 1132-SX (mismo producto: directo, ~11
  paradas, corredor al aeropuerto).
- **1180, 1185, 1481:** velocidad comercial de referencia por franja (22 / 13 / 14 / 13 / 11 /
  17 km/h de madrugada a noche), coherente con los 15 km/h medios del feed ATU. Los GPS de
  ETUCHISA y San Sebastián existen (Drive, carpeta de jul-2026) pero no están en disco: al
  descargarlos, `tiempos_gps.py` los procesa igual y la tabla se regenera.
- El tiempo de cada franja de la plantilla es el de la banda horaria que contiene su punto medio.

### D5 — Tiempos entre paraderos ⚖️
Proporcionales a la distancia recorrida sobre el trazado (`shape_dist_traveled`). El primer
paradero arranca en 00:00:00; el tiempo terminal→terminal se escala al tramo entre primer y
último paradero. `timepoint=1` solo en cabeceras.

### D6 — Tarifas ⚖️
GTFS fares v1 no representa tarifas por tramo (1180, 1185, 1481 declaran de 8 a 11 escalones).
Se publica **una tarifa por ruta: la máxima de adulto** (recorrido completo): 1132 S/ 2,50 ·
1132-SX 5,00 · 1180 6,00 · 1435-SX 5,00 · 1185 6,00 · 1481 5,50. Los escalones quedan en la
plantilla para una futura implementación con fares v2 o en la app.

### D7 — Cabecera de destino 🔧
`trip_headsign` = nombre del último paradero del sentido (la plantilla no trae letreros).

## Pendiente de confirmación por AEMUS
1. Tabla de tiempos de recorrido (columna «Tiempo real según empresa» del CSV).
2. 1180: servicio de sábado y domingo; nombre de paradero de cada escalón tarifario.
3. 1435-SX: frecuencia de 60 min todo el día (la 1132-SX declara 15).
4. 1185: ida y retorno con franjas idénticas.
5. KML vigente de la 1481 (post obras Línea 1) y cabecera de la 1132 en La Victoria.

## Validación
- Integridad referencial, orden de `stop_sequence`, tiempos y distancias monótonos: OK
  (`construir_horarios.py` + comprobación posterior).
- Estadísticas con `gtfs_kit` 13 (velocidades y viajes/día): ver nota del 28-sep.
- **Pendiente:** validador MobilityData (requiere Java, no disponible en esta máquina).
