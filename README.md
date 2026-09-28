# GTFS AEMUS Lima — 6 rutas

Feed GTFS estático de las **seis rutas operadas por las empresas de AEMUS** (Lima y Callao, Perú),
cliente INTERNATIONAL PARTNERS S.A. Construido por **Trufi Association e.V.** a partir de los
trazados KML, los paraderos y la plantilla de horarios entregados por los operadores, más los
rastros GPS de la flota.

> **No confundir con el feed de toda Lima.** Trufi mantiene aparte un GTFS de las 449 rutas del
> plan regulador de la ATU (`gtfs-lima-atu`, con horarios supuestos). Este repositorio cubre solo
> las 6 rutas del cliente, con frecuencias reales declaradas por cada empresa, y es la base del
> tiempo real: cada `trip` es un despacho al que se amarran las posiciones GPS.

| Ruta | Marca | Empresa |
|---|---|---|
| 1132 | URBANITO | E.T. y Servicios Múltiples Satélite S.A. |
| 1132-SX | AERODIRECTO CENTRO | E.T. y Servicios Múltiples Satélite S.A. |
| 1180 | NUEVA AMÉRICA | E.T. y Servicios Nueva América S.A. |
| 1435-SX | AERODIRECTO NORTE | E.T. y Servicios Nueva América S.A. |
| 1185 | ETUCHISA | E.T. Urbanos Los Chinos S.A. |
| 1481 | LA 50 | E.T. Patrón San Sebastián S.A.C. |

## Feed vigente

`data/gtfs_aemus_lima_<fecha>.zip` (tablas sueltas en `data/gtfs/`). 12 tablas: agency, routes,
stops (773), shapes (12 trazados), trips (126 patrones), stop_times, frequencies, calendar,
calendar_dates (feriados del Perú), fare_attributes, fare_rules, feed_info.

## Estructura

```
pipeline/          scripts y bitácoras (etl.py → snapping.py → tiempos_gps.py → tabla_tiempos.py → construir_horarios.py)
  README.md        cómo correr el pipeline
  DECISIONES_GTFS_AEMUS.md   criterios y supuestos del feed (leer antes de modificar)
data/gtfs/         tablas GTFS generadas
data/tiempos_recorrido/     tiempos de recorrido por ruta, sentido y franja (GPS y estimados)
data/source/       KML original del cliente (junio 2026)
docs/              historia del proyecto: análisis del KML, normalización, snap con Valhalla
```

Los insumos crudos (XLSX de paraderos, plantilla devuelta por AEMUS, GPS de la flota) **no se
versionan**: contienen datos del operador (placas, contactos). Viven en el archivo de Trufi.

## Estado (2026-09-28)

| Bloque | Estado |
|---|---|
| Trazados y paraderos (6 rutas, 12 sentidos) | ✅ ajustados a la vía; pendiente KML vigente de 1481 y cabecera de 1132 |
| Frecuencias y tarifas (plantilla del operador) | ✅ las 6 rutas |
| Tiempos de recorrido | 🟡 GPS en 1132 y 1132-SX; estimados en las otras 4, en validación con AEMUS |
| Validación MobilityData | ⬜ pendiente |

Publicado desde el archivo de trabajo con `publicar_github.sh`. Los cambios se hacen allí, no aquí.
