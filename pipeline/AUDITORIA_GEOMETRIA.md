# Auditoria de trazados AEMUS contra la red vial de OSM

Map-matching con Valhalla (perfil `bus`) sobre `valhalla.busboy.app`,
que ya tiene Lima cargada. Un desvio alto significa que el KML pasa por
donde un bus no puede circular.

| Ruta | Marca | Sentido | Puntos | Km | Desvio medio (m) | Desvio max (m) | % puntos >25 m | Vias no aptas |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1132 | URBANITO | IDA | 250 | 9.9 | 2.0 | 8.3 | 0.0% | ok |
| 1132 | URBANITO | RETORNO | 237 | 9.3 | 1.7 | 11.6 | 0.0% | ok |
| 1132-SX | AERODIRECTO CENTRO | IDA | 257 | 13.4 | 3.7 | 47.6 | 1.5% | ok |
| 1132-SX | AERODIRECTO CENTRO | RETORNO | 247 | 12.3 | 2.8 | 28.1 | 1.6% | ok |
| 1180 | NUEVA AMERICA | IDA | 1202 | 49.5 | 2.4 | 25.8 | 0.1% | ok |
| 1180 | NUEVA AMERICA | RETORNO | 920 | 51.6 | 2.5 | 37.3 | 1.2% | ok |
| 1435-SX | AERODIRECTO NORTE | IDA | 546 | 17.3 | 3.0 | 46.5 | 0.2% | ok |
| 1435-SX | AERODIRECTO NORTE | RETORNO | 435 | 14.9 | 2.0 | 12.4 | 0.0% | ok |
| 1185 | ETUCHISA | IDA | 632 | 51.3 | 2.7 | 14.0 | 0.0% | ok |
| 1185 | ETUCHISA | RETORNO | 948 | 51.6 | 2.1 | 13.2 | 0.0% | ok |
| 1481 | LA 50 | IDA | 682 | 39.8 | 2.2 | 46.1 | 0.4% | ok |
| 1481 | LA 50 | RETORNO | 731 | 40.7 | 2.1 | 40.5 | 0.3% | ok |

## Tipos de via recorridos

- **1132 IDA** -- road: 224, service_road: 1, turn_channel: 1
- **1132 RETORNO** -- road: 214, turn_channel: 2, service_road: 1
- **1132-SX IDA** -- road: 212, turn_channel: 7, ramp: 1
- **1132-SX RETORNO** -- road: 213, service_road: 7, turn_channel: 3, ramp: 3
- **1180 IDA** -- road: 869, service_road: 30, ramp: 11, turn_channel: 2
- **1180 RETORNO** -- road: 869, ramp: 22, turn_channel: 9
- **1435-SX IDA** -- road: 267, turn_channel: 4, ramp: 2
- **1435-SX RETORNO** -- road: 206, service_road: 8, turn_channel: 2, parking_aisle: 1
- **1185 IDA** -- road: 555, ramp: 4, turn_channel: 2
- **1185 RETORNO** -- road: 538, ramp: 10, turn_channel: 3, service_road: 1
- **1481 IDA** -- road: 872, turn_channel: 2
- **1481 RETORNO** -- road: 942, service_road: 8, turn_channel: 2
