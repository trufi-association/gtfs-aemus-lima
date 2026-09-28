# Diagnostico de datos AEMUS -> GTFS

Generado por `build/etl.py` sobre el paquete del 2026-07-21.

## Resumen por ruta

| Ruta | Marca | Paradas | Ida | Ret | Sentido inferido | Fuera de Lima | >150m del trazado | Km ida | Km ret |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1132 | URBANITO | 48 | 27 | 21 | 8 | 0 | 5 | 9.9 | 9.2 |
| 1132-SX | AERODIRECTO CENTRO | 22 | 10 | 12 | 0 | 0 | 1 | 13.5 | 12.4 |
| 1180 | NUEVA AMERICA | 317 | 136 | 181 | 317 | 0 | 2 | 49.5 | 51.3 |
| 1435-SX | AERODIRECTO NORTE | 22 | 11 | 11 | 0 | 0 | 0 | 17.4 | 14.9 |
| 1185 | ETUCHISA | 268 | 133 | 135 | 1 | 0 | 0 | 51.3 | 51.6 |
| 1481 | LA 50 | 96 | 48 | 48 | 0 | 0 | 3 | 40.3 | 41.2 |

## Coherencia del sentido declarado

Porcentaje de paradas que avanzan a lo largo de su propio trazado. Un valor bajo, con el contrario alto, significa que el archivo de origen rotulo los bloques al reves.

| Ruta | Ida | Ida invertida | Retorno | Retorno invertido | Estado |
|---|---:|---:|---:|---:|---|
| 1132 URBANITO | 100% | 0% | 100% | 5% | ok |
| 1132-SX AERODIRECTO CENTRO | 77% | 0% | 100% | 0% | ok |
| 1180 NUEVA AMERICA | 100% | 0% | 98% | 4% | ok |
| 1435-SX AERODIRECTO NORTE | 100% | 0% | 100% | 0% | ok |
| 1185 ETUCHISA | 100% | 1% | 100% | 1% | ok |
| 1481 LA 50 | 100% | 0% | 100% | 0% | ok |

## Paradas con coordenadas fuera de Lima Metropolitana

Estas filas traen lat/lon inconsistentes en el archivo de origen.

_Ninguna._

## Paradas a mas de 150 m de su trazado

Sugieren coordenada equivocada o sentido mal asignado. Se listan las 15 peores por ruta.

### 1132 URBANITO (5 casos)
- 404 m -- `LUCANAS-BAUZATE Y MEZA` (-12.063230, -77.018720)
- 364 m -- `LUCANAS-28 DE JULIO` (-12.061769, -77.018976)
- 316 m -- `BAUSATE Y MEZA-PARINACOCHAS` (-12.063099, -77.017836)
- 229 m -- `BAUZATE Y MEZA-LUIS GIRIVALDI` (-12.062961, -77.016856)
- 160 m -- `BAUZATE Y MEZA-HUANUCO` (-12.062777, -77.015469)

### 1132-SX AERODIRECTO CENTRO (1 casos)
- 264 m -- `EMBARQUE AEROPUERTO` (-12.031243, -77.116532)

### 1180 NUEVA AMERICA (2 casos)
- 235 m -- `Prdo.Final o Av.03` (-11.845695, -77.000757)
- 152 m -- `TERMINAL 20A, 140` (-11.849880, -77.003660)

### 1481 LA 50 (3 casos)
- 464 m -- `DONOFRIO` (-12.057912, -77.068295)
- 308 m -- `NAPO` (-12.057055, -77.052426)
- 175 m -- `13 DE ENERO` (-12.011652, -76.998500)


## Tablas GTFS generadas

| Tabla | Filas | Estado |
|---|---:|---|
| agency.txt | 4 | Falta telefono y web por empresa |
| routes.txt | 6 | Codigo de LA 50 pendiente de confirmar |
| stops.txt | 773 | Completa |
| shapes.txt | 10283 | Completa |
| trips.txt | 12 | Sin service_id real |
| stop_times.txt | 0 | **BLOQUEADA** -- faltan horarios |
| calendar.txt | 0 | **BLOQUEADA** -- faltan dias de operacion |
| frequencies.txt | 0 | **BLOQUEADA** -- faltan frecuencias |
| fare_attributes.txt | 0 | **BLOQUEADA** -- falta tarifa |

