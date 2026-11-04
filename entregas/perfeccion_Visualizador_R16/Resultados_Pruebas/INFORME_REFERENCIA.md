# Referencia de bancada recibida — 4 de noviembre de 2026

Se conserva intacto el STEP aportado por el usuario como referencia visual y de estructura de superficies. El STL original sigue siendo la referencia dimensional. No se ha modificado R15 ni publicado una versión nueva en esta comparación.

| Medida | STEP Easy aportado | R15 |
|---|---:|---:|
| Caras | 89 | 134 |
| Aristas | 253 | 409 |
| Superficies cilíndricas | 25 | 25 |
| Superficies planas | 59 | 57 |
| Otras superficies | 5 B-spline | 38 B-spline y 14 extrusiones |
| Error de volumen frente al STL | 0,239526 % | 0,022032 % |
| Error de caja | 0,000561 mm | 0,000561 mm |
| CAD exacto | No supera la comprobación | Supera la comprobación |
| Posibles interferencias BOP | 3 | 0 |

La referencia tiene menos fragmentación. La diferencia se concentra en el inventario de superficies distintas de planos y cilindros: 5 frente a 52. Debe localizarse su correspondencia espacial antes de fusionar regiones del motor.

La medición diagnóstica del STEP aportado toma 3.000 puntos STL→CAD y 64.267 CAD→STL: máximo observado 0,059420 mm, percentil95 máximo 0,008762 mm. Esas distancias pasan los límites superficiales vigentes, pero el STEP falla la puerta CAD exacta e interferencias y no queda certificado por pasar sólo esas mediciones. R15 tiene máximo verificado guardado de 0,003438 mm. Son mediciones por muestras, no cotas globales matemáticas.

La mayor tolerancia nativa de una arista del STEP recibido es 0,062692 mm, frente a 1e-7 mm en R15. La tolerancia interna de una arista no equivale a la desviación geométrica de toda la pieza. No se propone bajar esa etiqueta ni ampliar límites para aprobarlo.

Objetivo de desarrollo: conservar la compacidad y continuidad visual que aporta la referencia, reconstruyendo los perfiles y encuentros desde el STL para mantener la precisión de R15 y superar CAD exacto, material y regresión. La cantidad de caras no sustituye esos criterios. El archivo aportado no se usará como sustituto del original ni para una corrección especial dependiente del nombre de esta pieza.

Los JSON adjuntos conservan identidades, inventario y posiciones de los defectos. La imagen compara las aristas CAD reales; no es una prueba de Onshape. Windows nativo y Onshape no se han ejecutado aquí.
