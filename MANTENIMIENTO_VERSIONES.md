# Limpieza de versiones del repositorio

Autorizada por el usuario el 12 de noviembre de 2026. Se aplica al árbol activo
de `perfeccion_Visualizador_R20` mediante un commit normal. No se reescribe el
historial, no se cambian las ramas históricas ni la visibilidad del repositorio.

## Qué se conserva

- R20 corregida, su reparación y la entrega inicial necesaria para probar la actualización.
- R19 completa como dependencia congelada: los 357 hashes se mantienen.
- R18 completa como referencia recuperable y su lanzador.
- La corrección histórica del instalador R19.
- El conversor web de `index.html`, `static/` y sus pruebas, sin cambios.
- Seis fixtures R5, idénticos byte a byte, en `visor/test-data/r5_regression.zip`.

## Qué se retira del árbol activo

21 carpetas antiguas, 3.169 archivos de entregas, cuatro lanzadores R14–R17 y
cuatro workflows de empaquetado que apuntaban a esas carpetas. Los seis archivos
de regresión se han separado antes de retirar la entrega completa R5.

| Carpeta retirada | Archivos | MiB de contenido |
| --- | ---: | ---: |
| `entregas/analisis_calidad_R9_20261027` | 10 | 0.09 |
| `entregas/avance_CAD_no_aprobado_20261026` | 31 | 130.83 |
| `entregas/avance_contornos_CAD_20261027` | 39 | 92.19 |
| `entregas/avance_motor_post_R7_20261026` | 30 | 122.31 |
| `entregas/bateria_independiente_R7_20261026` | 26 | 99.98 |
| `entregas/perfeccion_Visualizador` | 12 | 20.81 |
| `entregas/perfeccion_Visualizador_R10` | 175 | 132.83 |
| `entregas/perfeccion_Visualizador_R11` | 212 | 127.85 |
| `entregas/perfeccion_Visualizador_R12` | 308 | 26.36 |
| `entregas/perfeccion_Visualizador_R14` | 402 | 14.27 |
| `entregas/perfeccion_Visualizador_R15` | 460 | 23.03 |
| `entregas/perfeccion_Visualizador_R16` | 448 | 22.01 |
| `entregas/perfeccion_Visualizador_R17` | 456 | 19.66 |
| `entregas/perfeccion_Visualizador_R2` | 24 | 18.53 |
| `entregas/perfeccion_Visualizador_R3` | 42 | 19.81 |
| `entregas/perfeccion_Visualizador_R4` | 30 | 21.99 |
| `entregas/perfeccion_Visualizador_R5` | 44 | 31.46 |
| `entregas/perfeccion_Visualizador_R6` | 20 | 35.75 |
| `entregas/perfeccion_Visualizador_R7` | 25 | 72.11 |
| `entregas/perfeccion_Visualizador_R8` | 198 | 122.67 |
| `entregas/perfeccion_Visualizador_R9` | 177 | 139.93 |

Contenido obsoleto retirado: 1,357,351,632 bytes (1.264 GiB).
El paquete mínimo de regresión ocupa 1.414.139 bytes y conserva las seis entradas
con los hashes y la procedencia registrados en su manifiesto.

## Pruebas y descargas

El ejecutor histórico usa el paquete mínimo y comprueba su hash y el de cada
entrada antes de extraerla. Se mantienen las mismas piezas y aserciones; no se
relajan presupuestos CAD, tolerancias ni validación final. El código del motor
`visor/src/conversor3d` no cambia. Las entregas ZIP R18, R19 y R20 conservadas
no se reconstruyen ni cambian de checksum.

## Recuperación y tamaño de Git

El estado anterior completo es el commit `81d9e201d1d223e0a9b2d9471954c3b245a4e321`:

https://github.com/cronos880-lang/Conversor_3D/tree/81d9e201d1d223e0a9b2d9471954c3b245a4e321/entregas

Las versiones retiradas también siguen en sus ramas originales, conservando
las URLs históricas. Los informes y certificados que apuntan a commits concretos
siguen siendo verificables. Para repetir una entrega antigua, utilizar el commit
fuente indicado en su manifiesto, sin mezclar su ejecutor de pruebas con otro checkout.

Esta limpieza reduce los archivos de la rama activa y su descarga como ZIP.
Los objetos anteriores siguen en el historial Git: no se afirma que se haya
liberado ese mismo espacio en el almacenamiento histórico de GitHub.

Para obtener sólo el árbol actual sin descargar todas las versiones históricas:

```console
git clone --depth 1 --single-branch --branch perfeccion_Visualizador_R20 https://github.com/cronos880-lang/Conversor_3D.git
```

Un borrado de objetos históricos exigiría otra operación y actualizar la
trazabilidad de las entregas. No es necesario para trabajar con el árbol limpio.

## Verificación de la limpieza

50 pruebas del desarrollo y 427 históricas aprobadas, con las mismas 15
omisiones históricas. R18 conserva sus 342 hashes de fuentes y R19 sus
357 archivos. Los ZIP conservados no tienen cambios. Se comprobaron 18
documentos activos sin enlaces relativos ausentes.

Contenido versionado total antes: 1,441,775,210 bytes.
Después, incluidos los fixtures mínimos y la documentación: 85,839,630 bytes.
La reducción corresponde al árbol actual; el historial conserva los objetos
anteriores.
