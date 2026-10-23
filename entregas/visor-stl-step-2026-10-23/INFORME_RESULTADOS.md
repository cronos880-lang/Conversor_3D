# Resultado del desarrollo — Visor STL → STEP

**AVANCE EXPERIMENTAL NO VALIDADO. No sustituir la R1 estable.**

23/10/2026. Cierre de evidencias: 13:07 CEST, Europe/Madrid. Trabajo transcurrido: aproximadamente 51 minutos, por debajo del límite de cinco horas.

## Resultado principal

Se ha implementado la reparación conservadora de la **malla** del cubo-carrito,
con contraste independiente y pruebas rotadas. **No se ha conseguido una
conversión STEP final aceptada del cubo-carrito con el motor actual**. La ejecución
completa terminó por tiempo a los 420.143 s, con pico observado de
735.95 MB. Los candidatos que se pudieron evaluar no superaron
los controles de volumen/caja. No se entrega ninguno como resultado válido.

La batería completa dio **12/14 conversiones válidas en R1 y 12/14
en la experimental** con este entorno y protocolo. 12 piezas tienen calidad
conservada según la comparación estricta y sus STEP se reimportaron otra vez.
Los fallos de la referencia se conservan como fallos: no permiten afirmar que
las 14 conversiones funcionan. **35/35 pruebas unitarias y de API
pasaron**, sin omitir las pruebas con STL reales. Windows y Onshape no se ejecutaron.

Por estas razones, la puerta automática de aceptación devuelve
`apto_para_entrega_validada = false`. Se entrega código completo de trabajo,
parche y evidencias como **progreso**, no una versión experimental aprobada.

## Cambios implementados

- Clasificador independiente: incidencias de aristas 1/2/>2, duplicados,
  degenerados, orientación, componentes cerrados/abiertos y ruta/gravedad JSON.
  El modo completo usa `BRepAlgoAPI_Check` para autointerferencias y analiza
  contacto/solapamiento. Informa si no pudo completar una comprobación.
- Unión de componentes cerrados con Manifold 3.4.0 en doble precisión y contraste
  con una unión poliédrica OpenCascade construida desde la entrada. Nunca se
  borran islas por porcentaje de triángulos ni se unen cuerpos por cercanía.
- Normalización de interfaces planas **ya conectadas por aristas coincidentes**
  para evitar el alabeo nanométrico que introduce STL float32 al rotar. Movimiento
  y simplificación numérica limitados a 0,000020 mm; comprobación geométrica posterior.
  La referencia usa la misma definición explícita de interfaz y un booleano distinto;
  no se construye desde la malla candidata.
- Cierre local conservador mediante **referencia cerrada explícita**, entre 1 y
  4 triángulos faltantes y diámetro limitado. Conserva los vértices y todas las
  caras existentes. Sin referencia, una abertura sigue siendo ambigua y se rechaza.
- Integración antes de **todas** las estrategias de entrada. Las mallas sanas
  usan el mismo archivo, sin reescritura. Brick conserva la soldadura microscópica
  que la lectura histórica `trimesh.process=True` ya realizaba.
- Evidencias JSON/STL conservadas incluso si falla el CAD; vigilancia de tiempo
  y RAM del proceso existente y sus descendientes. API y cancelación probadas en Linux.
- Batería reproducible con SHA-256, tiempos, RAM, resultado real y puerta de aceptación.
  El HTML es idéntico; la copia experimental usa 8766 para separarse de la R1 (8765).
- Corrección de empaquetado: `networkx==3.6.1`, dependencia no declarada que la
  ruta de perfiles histórica requiere. Se repitió Spur en R1 tras instalarla;
  la experimental usa también ese entorno. El primer ensayo interrumpido por
  esa carencia se conserva aparte y no se contabiliza como resultado geométrico.

No se copiaron los umbrales permisivos de EasyMeshFit, `_close_mesh`, suavizado
global ni eliminación de cuerpos pequeños. Se adaptaron las ideas de guardia,
QC reimportado y batería, preservando el núcleo CAD del Visor.

## Cubo-carrito: medidas de la reparación

| Medida | Entrada | STL reparado reimportado |
|---|---:|---:|
| Triángulos | 1880 | 1872 |
| Componentes | 2 | 1 |
| Aristas abiertas | 0 | 0 |
| Aristas >2 caras | 4 | 0 |
| Euler del sólido reparado | — | 0 |

Volumen de referencia independiente: **59242.563132597 mm³**.
Error de volumen del STL preparado: **6.14081939525e-14 %**.
Error de caja: **0 mm**. p95 bidireccional observado:
**5.46721434891e-16 mm**. Máximo superficial observado:
**1.00485917356e-14 mm**, con [6808, 6808] muestras por dirección
(todos los vértices, centroides y puntos de área deterministas).

El STL final tiene SHA-256 `62b965480624020bf2a3db180337d519dda4906886e53cfab8144337c229ec2f` y es **idéntico en bytes**
al STL preparado de la prueba completa CAD que agotó el tiempo. Por tanto, los
cambios finales de diagnóstico no ocultan una prueba CAD hecha con otra geometría.
Se contrastó también con el archivo reparado aportado, sin reutilizarlo para generar
la solución. Se preserva el túnel de la pieza (Euler 0 / género 1).

Las tres rotaciones 3D se prueban automáticamente tras serializar y reimportar
el STL. Esto demuestra la reparación de malla en esos casos, **no** una conversión
CAD rotada que todavía no ha pasado en el caso base.

## Batería real de las 14 piezas

Valores de error de la experimental aceptada; caras antes → después. El máximo
es observado en muestras, no una cota Hausdorff global. Las columnas vacías no
significan error cero: no existe un resultado STEP aceptado.

| STL | R1 original | Experimental | Caras | Volumen error % | Caja mm | p95 mm | Máximo mm |
|---|---|---|---:|---:|---:|---:|---:|
| 1x1-lego-brick.stl | válido | válido | 33 → 33 | 0.031434 | 0.000294 | 0.003205 | 0.004228 |
| Bancada_Motor.stl | válido | válido | 89 → 89 | 0.224992 | 0.000561 | 0.005200 | 0.029947 |
| Estefi.stl | válido | válido | 228 → 228 | 0.029257 | 0.007909 | 0.011725 | 0.036159 |
| Fast+Funnel+large.stl | tiempo_agotado | tiempo_agotado | — → — | — | — | — | — |
| Grapa.stl | válido | válido | 18 → 18 | 0.023370 | 0.010337 | 0.002298 | 0.009310 |
| LLanta_Trasera.stl | válido | válido | 42 → 42 | 0.032442 | 0.000058 | 0.002040 | 0.002109 |
| M3 PClip - 2mm.stl | válido | válido | 54 → 54 | 0.037385 | 0.002792 | 0.004743 | 0.007472 |
| Spoiler_arrière_Porsche_-_5.stl | válido | válido | 28 → 28 | 0.012459 | 0.000051 | 0.002332 | 0.002602 |
| Tirante.stl | válido | válido | 22 → 22 | 0.109325 | 0.000951 | 0.003463 | 0.004875 |
| chasis - Part 2.stl | válido | válido | 215 → 215 | 0.246375 | 0.016289 | 0.029307 | 0.054200 |
| conector.stl | tiempo_agotado | tiempo_agotado | — → — | — | — | — | — |
| maneta.stl | válido | válido | 42 → 42 | 0.107602 | 0.000057 | 0.007588 | 0.014472 |
| pinza.stl | válido | válido | 131 → 131 | 0.068255 | 0.000712 | 0.005840 | 0.035241 |
| spur.stl | válido | válido | 1405 → 1405 | 0.007408 | 0.000000 | 0.001249 | 0.003014 |

Spur se volvió a ejecutar en la referencia tras detectar que `networkx` faltaba
en los requisitos originales. Es el único STL de esta colección que entra en la
ruta de perfiles de 20.000–60.000 triángulos; las otras trece pruebas no usaron
esa ruta. Los registros anteriores se conservan en `evidencias/ensayo_spur_sin_networkx`.

Detalles completos, límites específicos, tolerancias de aristas, tipos de caras,
RAM y segundos están en `COMPARATIVA_14.csv` y `evidencias/*/bateria.json`.
Las reimportaciones independientes están en `evidencias/aceptacion.json`.

Se usaron los límites temporales del servidor: 420 s (<1 MB), 600 s (1–5 MB),
900 s (≥5 MB). Dos baterías y algunos ensayos coexistieron en el entorno; los
segundos son tiempo de pared observado, **no un benchmark justo de velocidad**.
Un tiempo agotado demuestra que no se completó la prueba con este protocolo,
no que la pieza sea imposible de convertir en otro entorno. No se amplió el
límite para presentar una conversión como terminada.

## Tolerancias y conservación del programa

Comprobación estructural del código: `_calidad`, `convertir`, comparadores y
todas las estrategias de `main` son iguales a R1 (el antiguo main solo se renombra
para envolver la entrada). Todos los módulos de `motor_superficies` y el HTML
mantienen sus bytes originales. Los 47 archivos de la copia R1 coinciden con su ZIP.

- Caja CAD: 0,020 mm; volumen: 0,5 %.
- p95: el criterio original de 0,020–0,030 mm según escala y densidad.
- Máximo observado: 0,060 mm, más **solo** el margen de simplificación que ya
  tenía R1, acotado a 0,010 mm. La reparación no añade margen CAD.
- Verificación adicional de unión: caja/máximo superficial observado 0,002 mm;
  volumen 0,001 %. La tolerancia de cosido/booleano OCC es 0,0000001 mm.

Los límites CAD no se relajaron. No se aceptó uniones solo por `is_watertight`.
El informe explica que las comprobaciones superficiales son muestreadas.

## Bloqueos y trabajo pendiente

- Fast+Funnel+large.stl: la conversión completa no pasa en ambas copias.
- conector.stl: la conversión completa no pasa en ambas copias.
- Cubo-carrito: falta una conversión STEP completa que pase los controles.
- Pruebas nativas Windows pendientes; disponibilidad de wheels no equivale a ejecución.

El bloqueo principal es la reconstrucción/exportación CAD del cubo-carrito:
en ensayos dirigidos, un candidato de 71 caras pasó validez interna pero al
reimportar STEP presentó 1,612 % de error de volumen y 0,1016 mm de caja. Otros
ensayos de segmentación, refinamiento de entrada y rotación tampoco superaron
los mismos límites. Los logs están en `evidencias/candidatos/`. Son ensayos de
diagnóstico y no forman nuevas estrategias de producción.

Para continuar, hace falta una corrección acotada y probada del recorrido
B-Rep → STEP o del ajuste que lo alimenta. Esta entrega mantiene esos módulos
intactos conforme al encargo y **no sustituye su rechazo por un STEP facetado**.
Las conversiones históricas que no completaron deberán repetirse sin carga
concurrente, con el mismo protocolo, antes de declarar su estado definitivo.

No se dispone de un ejecutor Windows ni sesión Onshape. Se verificó que existen
wheels Windows x64 de Manifold y psutil para Python 3.12 y 3.13;
esto **no** prueba instalación/ejecución Windows, UI real Windows ni Move face.
Las pruebas automatizadas no garantizan preservar cualquier rosca/ranura de
cualquier STL: se ensayan el túnel del caso real y canales pasantes sintéticos.
El clasificador completo limita autointerferencias a 20.000 caras / 8 cuerpos;
las comprobaciones no realizadas se indican expresamente.

## Contenido y reproducción

`AVANCE_NO_VALIDADO_Visor_STL_STEP_2026-10-23.zip` contiene la copia completa de
fuentes experimentales, archivos modificados y nuevos, material STL de prueba,
parche unificado, resultados antes/después, STEP históricos aceptados, registros,
JUnit XML y freeze del entorno. **No es una publicación ni instalación estable.**
La fuente original se conserva en el ZIP aportado; no se ha modificado el proyecto
Edu3d del entorno ni se ha subido nada a GitHub u otros servicios.

Ver `Visor_experimental_fuentes/GUIA_REPRODUCIR.md`. Ejecutar las pruebas completas
con `VISOR_MATERIAL_PRUEBAS` configurado: omitir los STL reales bloquea la aceptación.
