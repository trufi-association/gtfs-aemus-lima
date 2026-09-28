# Build GTFS Lima — AEMUS

Pipeline que convierte el paquete de AEMUS (KML + XLSX de paraderos) en tablas GTFS.

## Uso

```bash
python3 etl.py
```

Requiere `openpyxl`. Lee de `../../resolicitud-gtfs-lima/` y escribe:

| Salida | Qué es |
|---|---|
| `gtfs/` | Tablas GTFS ya construibles (agency, routes, stops, shapes, trips) |
| `diagnostico.md` | Reporte de calidad de datos por ruta |
| `secuencia_paradas.csv` | Orden real de cada parada a lo largo del recorrido |
| `PLANTILLA_HORARIOS_AEMUS.csv` | Formulario a enviar a AEMUS con lo que falta |

## Estado

**Construido (5 tablas):** las 6 rutas con sus 4 agencias, 773 paradas y 12 trazados
(ida + retorno por ruta), con distancia acumulada.

**Completado 28-sep-2026:** con la plantilla devuelta por AEMUS, `construir_horarios.py`
genera `calendar`, `calendar_dates`, `trips` (126, uno por franja), `stop_times`,
`frequencies`, `fare_attributes`, `fare_rules` y `feed_info`, y empaqueta
`../gtfs_aemus_lima_<fecha>.zip`. Criterios en `DECISIONES_GTFS_AEMUS.md`.

```bash
python3 tiempos_gps.py <carpeta_csv_gps> 1132,1132SX   # tiempos reales (opcional, si hay GPS)
python3 tabla_tiempos.py                                # CSV de tiempos por franja para validar con AEMUS
python3 construir_horarios.py                           # tablas de horario + zip
```

`secuencia_paradas.csv` deja el trabajo listo para ese momento: ya tiene el
`stop_sequence` de cada parada y los metros recorridos hasta ella, así que armar
`stop_times.txt` se reduce a repartir tiempos sobre esa secuencia.

## Decisiones que toma el ETL

**Sentido de las paradas.** Cada archivo de AEMUS lo codifica distinto: columna
explícita (LA 50, Aerodirecto Centro), prefijo `A`/`B` en el nombre (ETUCHISA),
primer dígito del código (URBANITO), un marcador suelto entre bloques (Aerodirecto
Norte). La 1180 NUEVA AMÉRICA no lo codifica de ninguna forma: sus 310 paradas vienen
numeradas de corrido. Para esa se infiere por geometría, buscando el corte que deja
cada mitad más pegada a su trazado. Se respeta siempre lo que el archivo declare; la
inferencia solo cubre lo que falta, y el diagnóstico reporta cuántas paradas fueron
inferidas.

**Orden de las paradas.** No se usa la numeración del archivo sino la proyección de
cada parada sobre su trazado. Así el orden refleja el recorrido real aunque la
numeración de origen tenga huecos o duplicados (ETUCHISA repite el número 265).

**Coordenadas.** Los XLSX traen dos pares de coordenadas por fila (`X`/`Y` y
`Latitud`/`Longitud`) que en varias filas no coinciden — a veces por kilómetros. Se
usa `Latitud`/`Longitud`, que es el par consistente con los trazados.

**Codificación.** Los nombres llegan con mojibake (`HuascarÃ¡n`, `CAÃ‘ETE`). Se
reparan en `limpiar()`.

## Pendientes con AEMUS

1. **Horarios, frecuencias, días y tarifa** por ruta y sentido — bloquea el feed.
2. **Cuadro de rutas oficial.** El código de LA 50 está en disputa: 1481 (carta a la
   ATU y PPT), 1431 (acta del 14-jul), 1066/IO66 (nombre de archivo). El ETL adopta
   1481 provisionalmente.
3. **Teléfono y web** de las 4 empresas, para `agency.txt`.
4. **Ruta 1132 URBANITO:** cinco paradas de Bauzate y Meza / Lucanas quedan hasta a
   400 m del trazado. Sugiere que al KML le falta ese tramo del recorrido.
5. **Ruta 1435-SX:** el "Polígono sin título" del XLSX se descarta por ahora; falta
   que AEMUS explique qué representa.
