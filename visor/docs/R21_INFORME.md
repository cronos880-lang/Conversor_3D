# R21 experimental: rendimiento con controles conservados

R21 es una ACTUALIZACIÓN ligera para una instalación R20 existente. No contiene
otro entorno Python, los binarios de terceros ni una copia del motor histórico.
R20 conserva sus archivos y su entorno; R21 se abre desde una carpeta independiente.

## Avance demostrado

- Se omiten propuestas imposibles para el contrato o que sólo encontrarían caras
  planas/cilíndricas que el proponente actual conserva.
- Se verifica y reutiliza un certificado R19 completo generado dentro de la misma
  conversión cuando sus bytes, STL, perfil y nonce corresponden a la salida elegida.
- En una reconversión, se reutiliza la geometría R19 de referencia y se ejecuta un
  control frío completo nuevo antes de utilizarla. No se guardan certificados en
  la caché ni se reutilizan aprobaciones entre conversiones.
- Se conserva el diagnóstico de un fallo de R19: etapa, código nativo, mensaje y
  rutas de registros. No se afirma que el fallo del PC Windows del usuario esté resuelto.
- Se incluyen la barra de progreso y la presentación 3D del desarrollo posterior a R20.

## Comparación local de ocho piezas sintéticas

Segundos por conversión, medidos con otras pruebas en curso en Linux. Son
mediciones de esta batería, no una promesa de velocidad para Windows. Cada
salida pasó el control frío completo, material original y tres mallados.

| Pieza | R20 primera | Mejora primera | Mejora repetida | Caras conservadas |
|---|---:|---:|---:|---:|
| box | 30.14 | 29.31 | 6.04 | 6 |
| cylinder | 33.95 | 29.15 | 6.38 | 3 |
| prismatic_L | 20.70 | 15.63 | 3.38 | 8 |
| rotated_cylinder | 43.61 | 20.30 | 4.50 | 3 |
| small_hole | 47.91 | 40.76 | 10.99 | 7 |
| stepped_prism | 32.71 | 27.82 | 5.99 | 8 |
| thin_wall | 38.19 | 29.29 | 5.64 | 10 |
| two_holes | 22.41 | 16.94 | 4.43 | 8 |

Las 24 salidas conservaron el conteo de caras y la desviación máxima medida
de su caso, sin discrepancias de material y con tolerancia B-Rep máxima de
1e-7 mm. Los nonces de las conversiones primera y repetida fueron distintos.

## Límites geométricos

Esta entrega no anuncia una reconstrucción analítica nueva aceptada. El ensayo
aislado de revolución generó cinco caras para el cilindro con redondeos, pero
el evaluador congelado lo rechazó: la referencia facetada no contiene los
cilindros que exige su contraste de recortes. Se mantiene la referencia y el
prototipo no se incorpora como ruta automática. No se cambian los validadores
ni sus límites para aprobarlo.

La primera conversión de una pieza difícil sigue utilizando R19 completo. La
caché de referencia sólo acelera entradas idénticas ya procesadas bajo el mismo
perfil, dependencias y núcleo. El STEP final siempre conserva un certificado
completo correspondiente a sus bytes y al STL. Las 53 caras planas y las 18
cilíndricas protegidas de Bancada no se reconstruyen ni se desplazan.

## Almacenamiento y recuperación

La caché local de referencias tiene un presupuesto de 64 MiB por STEP y 256 MiB
para el conjunto; no borra referencias anteriores para hacer sitio. Una entrada
dañada, incompatible o rechazada por el control frío vuelve al cálculo R19.
Los archivos del usuario no se utilizan como destino de la caché. Los datos y
registros R21 quedan en su propia carpeta `datos`.

No hay dependencias nuevas. Python 3.12 x64 y las bibliotecas bloqueadas son las
de R20. Se comprueban los 357 hashes R19 y las dependencias antes de arrancar.
Para volver a R20 basta cerrar R21 y utilizar el lanzador R20 original.

Las pruebas Linux y las de un runner Windows no sustituyen las pruebas del PC
del usuario. El conversor web y sus automatizaciones no se modifican.
