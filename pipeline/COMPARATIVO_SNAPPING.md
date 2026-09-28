# Comparativo: trazado crudo vs. ajustado a la red vial

Map-matching con Valhalla (perfil `bus`), criterio estricto: la geometria
final sigue OpenStreetMap de punta a punta.

| Ruta | Marca | Sentido | Puntos antes | Puntos despues | Km antes | Km despues | Cambio | Desvio max (m) | Peor parada antes (m) | Peor parada despues (m) | Paradas >150 m antes | despues | Estado |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1132 | URBANITO | IDA | 250 | 313 | 9.9 | 9.9 | -0.0% | 8 | 407 | 404 | 4 | 4 | ok |
| 1132 | URBANITO | RETORNO | 237 | 236 | 9.3 | 9.2 | -0.2% | 8 | 366 | 364 | 1 | 1 | ok |
| 1132-SX | AERODIRECTO CENTRO | IDA | 257 | 371 | 13.4 | 13.5 | +0.4% | 9 | 264 | 264 | 1 | 1 | ok |
| 1132-SX | AERODIRECTO CENTRO | RETORNO | 247 | 341 | 12.3 | 12.4 | +0.3% | 7 | 151 | 149 | 1 | 0 | ok |
| 1180 | NUEVA AMERICA | IDA | 1202 | 1494 | 49.5 | 49.4 | -0.1% | 10 | 31 | 32 | 0 | 0 | ok |
| 1180 | NUEVA AMERICA | RETORNO | 920 | 1554 | 51.6 | 51.6 | +0.0% | 8 | 202 | 138 | 1 | 0 | ok |
| 1435-SX | AERODIRECTO NORTE | IDA | 546 | 482 | 17.3 | 17.3 | +0.1% | 9 | 16 | 12 | 0 | 0 | ok |
| 1435-SX | AERODIRECTO NORTE | RETORNO | 435 | 470 | 14.9 | 15.0 | +0.6% | 10 | 87 | 86 | 0 | 0 | ok |
| 1185 | ETUCHISA | IDA | 632 | 999 | 51.3 | 51.4 | +0.1% | 10 | 103 | 103 | 0 | 0 | ok |
| 1185 | ETUCHISA | RETORNO | 948 | 933 | 51.6 | 51.8 | +0.4% | 8 | 69 | 70 | 0 | 0 | ok |
| 1481 | LA 50 | IDA | 682 | 1225 | 39.8 | 40.0 | +0.5% | 9 | 173 | 175 | 1 | 1 | ok |
| 1481 | LA 50 | RETORNO | 731 | 1277 | 40.7 | 40.9 | +0.3% | 9 | 465 | 464 | 2 | 2 | ok |

## Control de calidad

Ningun tramo supero los umbrales: cambio de longitud por debajo de 10%, sin perdida de respuesta y sin paradas que se alejaran del trazado.

## Efecto agregado

- Vertices: **7087 -> 9695** (x1.4 densidad).
- Kilometros totales: 361.7 -> 362.3.
- Paradas a mas de 150 m de su trazado: **11 -> 9**.

