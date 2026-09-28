# Puntos a revisar en el mapa

Sitios donde el trazado ajustado a la red vial se aparta mas de 30 m
del recorrido que envio AEMUS. Cada uno es una de dos cosas:

- **El mapa esta incompleto**: falta un cruce o un giro, o un ramal
  figura como en construccion o con acceso restringido, y el ruteador
  tuvo que dar un rodeo. Se corrige en OpenStreetMap.
- **El recorrido esta mal dibujado**: el KML pasa por una via que no
  corresponde. Se consulta al operador.

Ordenados por separacion maxima.

| Ref | Ruta | Sentido | Separacion | Tramo | Ubicacion | Ver |
|---|---|---|---:|---:|---|---|
| MAPA-01 | 1481 LA 50 | IDA | 119 m | 315 m | `-12.05562, -77.06296` | [mapa](https://www.openstreetmap.org/#map=18/-12.05562/-77.06296) |
| MAPA-02 | 1481 LA 50 | RETORNO | 72 m | 72 m | `-12.04617, -77.10372` | [mapa](https://www.openstreetmap.org/#map=18/-12.04617/-77.10372) |

## Resumen por ruta

| Ruta | Zonas | Peor caso |
|---|---:|---:|
| 1481 LA 50 | 2 | 119 m |
