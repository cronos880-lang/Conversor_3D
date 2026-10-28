# Visor R11 experimental: resultados reales

**La maneta pasa de 9.351 caras planas a 36 caras (29 planos, cinco cilindros y dos superficies de revolución). La bancada pasa de 1.896 caras a 239 (150 planos, 25 cilindros, 14 superficies de extrusión y 50 B-splines).** Son resultados del programa completo, desde los STL originales, con perfil Precisión. La bancada se convierte además mediante carga, conversión y descarga reales en Chromium. Los dos STEP finales se contrastan con los validadores R10 congelados.

**La regresión aporta un tercer caso mejorado sin ajuste específico: Grapa pasa de 622 a 20 caras**, con diez planos, dos cilindros y ocho superficies de extrusión. Mantiene sus dos grupos cilíndricos y Euler 2; el error de volumen es 0,006990 %, el de caja 0,000034 mm y el máximo denso 0,001042 mm. También supera CAD exacto, BOP, tres fronteras finas CGAL sin cruces y el contraste independiente R10.

## Cambio del motor

La mejora genera una hipótesis compacta desde el STL y mide sus perfiles de revolución y extrusión sobre los vértices y triángulos originales. Extiende las regiones cilíndricas confirmadas, recupera regiones del STL que la hipótesis CAD había recortado y reúne continuaciones de un mismo perfil cuando la costura oblicua procede de la segmentación. Ajusta los encuentros entre planos, cilindros y barridos con una curva 3D común y curvas UV coherentes en ambas superficies. Conserva las curvas ya exactas, evitando que una reparación genérica posterior las altere. No identifica piezas por nombre, radio conocido ni huella; no necesita los STEP históricos para convertir.

Primero conserva el resultado aprobado de R10. La fase nueva se intenta sobre una única componente sana, cerrada, orientada y sin cruces, de hasta 20.000 triángulos y 30 MB, cuando el resultado anterior tiene al menos 500 caras. Debe reducirlas al menos un 25 % y superar todos los controles. Trabaja en otro proceso con un presupuesto adicional de 450 segundos. Ante fallo o agotamiento conserva el resultado anterior; la sustitución se hace de forma atómica después de validar. No se cambia la interfaz ni se pide otra decisión de precisión.

Las 150 fuentes entregadas coinciden con las congeladas y ejecutadas. Las doce funciones/clases previas de motor_v2 conservan su AST; quince módulos de aceptación y rutas anteriores son idénticos byte a byte a R10. **21/24 bloques DATA son idénticos a R10**. Resultados diferentes: maneta, Grapa, Bancada_Motor.

## Precisión y validez

Se mantienen los límites de aceptación de Precisión: caja 0,02 mm, p95 denso 0,02 mm, máximo observado 0,06 mm y error de volumen 0,5 %. El control de cilindros sigue en 0,008 mm sobre las caras recortadas, no sobre un cilindro infinito. No se aumenta la tolerancia CAD; ambos objetivos mantienen 0,0000001 mm en sus aristas.

Hay una distinción interna: la nueva propuesta de planos usa un ajuste a los triángulos fuente de hasta 0,0001 mm, frente al ajuste primario de 0,00001 mm de la segmentación previa. Es un límite de construcción de la hipótesis; los evaluadores geométricos finales permanecen idénticos. Los perfiles se acotan a 0,003 mm contra la fuente, y la correspondencia 3D/UV a 0,00000005 mm. No se redondean radios a medidas nominales.

| Medida | Maneta R11 | Bancada R11 | Límite original |
|---|---:|---:|---:|
| Error de volumen | 0.022278 % | 0.026121 % | 0,5 % |
| Diferencia de caja | 0.000057 mm | 0.000561 mm | 0,02 mm |
| p95 denso máximo | 0.00169959 mm | 0.00080804 mm | 0,02 mm |
| Máximo en inspección densa | 0.016033 mm | 0.003438 mm | 0,06 mm |

Cada STEP final contiene un único sólido, supera CAD exacto y BOP sin interferencias. Se conservan los tres grupos cilíndricos confirmados en la maneta y los quince de la bancada. Euler se conserva en 0 y −14 respectivamente. Los contrastes independientes y sus huellas figuran en contrastes_finales_R10.json.

| Objetivo | Deflexión (mm) | Triángulos de frontera | Cerrado/orientado | Cruces CGAL | Máximo observado (mm) |
|---|---:|---:|---|---:|---:|
| maneta | 0.00025 | 154934 | Sí | 0 | 0.00275584 |
| maneta | 0.0005 | 53020 | Sí | 0 | 0.02092283 |
| maneta | 0.001 | 21572 | Sí | 0 | 0.02357907 |
| Bancada_Motor | 0.00025 | 310372 | Sí | 0 | 0.00343626 |
| Bancada_Motor | 0.0005 | 162026 | Sí | 0 | 0.00343743 |
| Bancada_Motor | 0.001 | 89160 | Sí | 0 | 0.00343626 |

Las distancias son observaciones de muestreo determinista, no una garantía Hausdorff global. El máximo de los mallados finos de la maneta puede superar el de la inspección densa y se informa por separado. La bancada conserva 50 caras B-spline: no se promete eliminar toda superficie libre ni recuperar el diseño paramétrico original.

## Pruebas de regresión

**280 pruebas automáticas aprobadas, sin fallos, errores ni omisiones. 24 conversiones aprobadas: 15 por CLI y nueve por navegador.** Se comprueban carga del STL, perfil por defecto, identidad de la instancia, descarga idéntica al backend, errores JavaScript y conservación del original. También pasan la cancelación sin descarga residual, una conversión posterior y la lectura fría de los 24 STEP más la caja de control.

Los registros conservan también los intentos intermedios rechazados. La aprobación de cada caso corresponde a su salida final validada, con código de éxito y STEP comprobado.

El cubo-carrito y sus tres giros están incluidos. El cubo se repara, se convierte y permite descargar el STL reparado con la huella certificada. Se cubren trece de las catorce piezas históricas; **Embudo sigue aplazado por indicación del usuario, por lo que no se declara 14/14**. Se añaden cinco regresiones previas y Lego 4×2, soporte móvil y Technic PEGS.

| Pieza | Caras STEP | Máximo denso (mm) | DATA igual a R10 |
|---|---:|---:|---|
| Tirante | 22 | 0.027430 | Sí |
| conector | 19998 | 0.010826 | Sí |
| Pieza_Nueva_Detenida | 8892 | 0.020334 | Sí |
| Estefi | 1769 | 0.000000 | Sí |
| Con fallos pero si step | 2567 | 0.000592 | Sí |
| chasis - Part 2 | 13803 | 0.006785 | Sí |
| Dimensiones | 1100 | 0.000005 | Sí |
| maneta | 36 | 0.016033 | No |
| 1x1-lego-brick | 2672 | 0.000000 | Sí |
| spur | 1405 | 0.004738 | Sí |
| Grapa | 20 | 0.001042 | No |
| cubo-carrito_giro_3 | 1853 | 0.000000 | Sí |
| cubo-carrito_giro_1 | 1838 | 0.000000 | Sí |
| Spoiler_arrière_Porsche_-_5 | 28 | 0.002827 | Sí |
| cubo-carrito_giro_2 | 1195 | 0.000000 | Sí |
| Bancada_Motor | 239 | 0.003438 | No |
| LLanta_Trasera | 53 | 0.002138 | Sí |
| V_legoBrick4x2 | 1149 | 0.005932 | Sí |
| M3 PClip - 2mm | 1484 | 0.000000 | Sí |
| cubo-carrito | 1152 | 0.000000 | Sí |
| pinza | 448 | 0.003787 | Sí |
| 6558_fixed | 8713 | 0.016360 | Sí |
| Soporte_movil_2 | 493 | 0.018513 | Sí |
| Technic_PEGS_Cross_x6_A | 2044 | 0.000050 | Sí |

Los tiempos y SHA-256 están en RESULTADOS_REGRESION.csv/JSON. Se han ejecutado hasta dos conversiones concurrentes en Linux, con dos CPU y 8 GiB; los tiempos no son una comparación controlada de velocidad con tu ordenador. Esta entrega prioriza calidad y puede añadir tiempo de validación.

## Limitaciones y ensayos descartados

Se descartaron bancadas que parecían compactas pero fallaban BOP o CAD exacto. Sus registros se conservan como investigación NO APROBADA y sus STEP no se incluyen como resultados utilizables. La corrección final resuelve intersecciones entre barridos y conserva su correspondencia UV/3D. Las pruebas comprueban también que un hexágono no se convierta indebidamente en cilindro y que un rechazo mantenga el STEP anterior.

**No ejecutado en este entorno:** Windows nativo, importación e inspección visual en Onshape y prueba física con la Creality K1C. La validación OCC/CGAL no sustituye esas pruebas. La ausencia de líneas espurias en Onshape debe confirmarse allí. Tampoco se promete mejorar todos los STL defectuosos ni superficies arbitrarias.

## Entrega y uso

Extrae el ZIP completo en una carpeta nueva y abre Iniciar.bat. Incluye Visor_experimental_fuentes; reutiliza un entorno compatible de R7/R8/R9/R10 sin modificarlo, o usa Instalar_Entorno.bat con Python 3.12 x64. Debe indicar R11 experimental, puerto 8777. Mantén Automático (precisión). El perfil 0,08 permite otro margen, pero no obliga a reconocer más cilindros.

Se entregan fuentes completas, archivos modificados y parche desde R10, STEP antes/después, entradas y evaluadores para reproducción, registros reales y huellas. La verificación del ZIP extraído se documenta en VERIFICACION_PAQUETE.json y verificacion_extraida. Las versiones anteriores y la web de main se conservan.
