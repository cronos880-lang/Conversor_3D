# perfeccion_Visualizador — resultados de la fase cubo-carrito

Evidencia cerrada: 2026-10-23T16:30:51.419316+00:00. Entorno de referencia Linux / Python 3.12. Trabajo iniciado en esta fase a las 16:01 UTC del 23/10/2026.

## Resultado y alcance

El cubo-carrito original se repara y convierte en un STEP que supera los controles geométricos originales del Visor. También pasan tres giros, incluidos dos giros compuestos 3D. Los cuatro archivos exportados se han reimportado e inspeccionado de nuevo. Las 12 piezas que convertían en la referencia vuelven a convertir sin empeorar los indicadores comparados.

Esta es una entrega experimental de esa fase, no una sustitución estable de R1 ni una declaración de 14/14 conversiones. Se ha respetado la indicación de aplazar el embudo. El conector tampoco se ha vuelto a ejecutar: en la referencia y en la fase anterior agotaba 900 s. Windows nativo y Move face en Onshape siguen pendientes.

El paquete corresponde al Visor Python aportado. No modifica ni valida la conversión WebAssembly de la aplicación publicada en GitHub Pages.

## Cambios implementados

Se conserva el preprocesador de la fase anterior: clasifica la topología, une cuerpos cerrados mediante Manifold en doble precisión y contrasta la unión con un booleano poliédrico independiente de OpenCascade. Las aberturas ambiguas siguen rechazándose; los cierres locales necesitan referencia explícita.

La ruta nueva solo se activa después de una reparación verificada y hasta 5.000 triángulos. Usa el mismo motor de superficies con límites internos de ajuste menores: regiones 0,015 mm, B-splines 0,005 mm, curvas de arista 0,003 mm y movimiento de proyección 0,020 mm. Esos valores son parámetros de construcción, no tolerancias máximas almacenadas en las aristas del B-Rep.

El ajuste anterior podía mezclar una pared plana con su redondeo y producir ondas superiores a 0,1 mm. También podía devolver coeficientes B-spline del orden de 10^15 mm para una región de unos 25 mm. Ahora la ruta experimental rechaza coeficientes no finitos o desproporcionados respecto al tamaño local. Que OpenCascade declare válido un sólido no basta para aceptarlo.

Si el ensamblaje directo falla, se ensaya un marco rígido local inferido de las normales de caras grandes. El STEP se restaura a las coordenadas originales y vuelve a pasar el validador histórico frente al STL reparado original. La serialización local está limitada a 0,000020 mm y su error no se suma a ninguna tolerancia. En el tercer giro el máximo medido fue 0,000003908 mm.

Las entradas sanas conservan sus estrategias. `evidencias/integridad_codigo.json` confirma que `_calidad`, el núcleo histórico `_main_cad`, la comparación de candidatos y el HTML mantienen el mismo código que la R1 original. La copia estable coincide byte a byte con los 47 archivos de su ZIP de origen. `CAMBIOS_FASE_CUBO.patch` recoge los cambios frente a la entrega experimental anterior.

## Resultados reales del cubo-carrito

El original contiene 1.880 triángulos, dos cuerpos individualmente estancos y cuatro aristas con más de dos caras. La unión produce 1.872 triángulos, un cuerpo estanco, ninguna arista abierta ni no manifold y género 1: conserva el túnel. El volumen de referencia independiente del caso original es 59242.563132597 mm³.

Cada STEP de la tabla contiene exactamente un sólido válido, sin aristas de parametrización incoherente. OpenCascade no detecta autointerferencias. Cuatro puntos del canal permanecen fuera del material y dos puntos de paredes permanecen dentro, aplicando en cada caso el mismo giro que al STL.

| Caso | Caras STEP | Segundos | Error volumen % (validador original) | Error caja mm | p95 denso mm, peor dirección | Máximo denso mm, peor dirección |
|---|---:|---:|---:|---:|---:|---:|
| cubo-carrito.stl | 255 | 42.944 | 0.082105 | 0.000000 | 0.006413 | 0.026240 |
| cubo-carrito_giro_1.stl | 239 | 40.162 | 0.006406 | 0.000003 | 0.006014 | 0.023355 |
| cubo-carrito_giro_2.stl | 324 | 40.276 | 0.029381 | 0.000125 | 0.006493 | 0.011917 |
| cubo-carrito_giro_3.stl | 272 | 80.490 | 0.084060 | 0.000004 | 0.005862 | 0.012582 |

Los límites de aceptación siguen siendo 0,5 % de volumen, 0,020 mm de caja, p95 de 0,020–0,030 mm según la escala original (0,030 en este caso) y máximo observado de 0,060 mm. No hay margen adicional de preparación en estas cuatro conversiones.

El STEP original tiene 223 caras planas, 16 cilindros y 16 B-splines. Algunas esquinas conservan parches planos. Es un B-Rep de superficies y no incluye historial de operaciones paramétricas. La posibilidad concreta de editar una cara con Move face requiere probarla en Onshape.

La comprobación densa mide 6.808 puntos STL contra el shell B-Rep por caso: todos los vértices y centroides más 4.000 puntos de área con semilla fija. En sentido inverso utiliza vértices y centroides de una teselación CAD fina, además de puntos de aristas; en el original son 62,989 muestras. Los resultados son mediciones muestreadas, no una cota Hausdorff global.

Se repite además la integración adaptativa del volumen con precisiones 10^-6 y 10^-8 y se exige convergencia. En el original da 59247.080402460 mm³, error 0.007625041 %. Esta medición adicional no sustituye el cálculo del validador heredado, que también debe pasar.

Los tiempos incluyen diagnóstico, unión y conversión completa. El tercer giro incluye el intento directo rechazado y el rescate en marco local. Durante algunas mediciones había otras pruebas ejecutándose; estos tiempos no son una comparación de rendimiento con la batería histórica. El pico de RAM registrado del proceso de conversión fue 686.21 MB en los cuatro casos.

## Regresión de las 14 piezas históricas

La columna de referencia procede de las ejecuciones anteriores sobre la R1 original intacta. Esta fase repite 12 conversiones completas. En esas 12 coinciden las huellas de los STL y no empeoran caras, volumen, caja, p95/máximos en ambos sentidos ni tolerancias de arista. Los STEP se han reimportado de nuevo y sus huellas coinciden con los archivos que produjeron las métricas.

| STL | Referencia R1 | Esta fase |
|---|---|---|
| 1x1-lego-brick.stl | Aceptada | Aceptada; mismos indicadores |
| Bancada_Motor.stl | Aceptada | Aceptada; mismos indicadores |
| Estefi.stl | Aceptada | Aceptada; mismos indicadores |
| Fast+Funnel+large.stl | Tiempo agotado (600 s) | Aplazada por petición del usuario |
| Grapa.stl | Aceptada | Aceptada; mismos indicadores |
| LLanta_Trasera.stl | Aceptada | Aceptada; mismos indicadores |
| M3 PClip - 2mm.stl | Aceptada | Aceptada; mismos indicadores |
| Spoiler_arrière_Porsche_-_5.stl | Aceptada | Aceptada; mismos indicadores |
| Tirante.stl | Aceptada | Aceptada; mismos indicadores |
| chasis - Part 2.stl | Aceptada | Aceptada; mismos indicadores |
| conector.stl | Tiempo agotado (900 s) | No repetida en esta fase |
| maneta.stl | Aceptada | Aceptada; mismos indicadores |
| pinza.stl | Aceptada | Aceptada; mismos indicadores |
| spur.stl | Aceptada | Aceptada; mismos indicadores |

Los dos tiempos agotados eran bloqueos previos, no conversiones aprobadas. No se presentan como éxitos ni se presupone que están resueltos. La puerta global sigue dando `apto_para_entrega_validada: false`, por la batería incompleta de 14 y Windows pendiente. Ver `evidencias/aceptacion_global.json`.

## Pruebas y archivos de evidencia

- 35 pruebas de topología, uniones, huecos, rotaciones, casos negativos, límites de recursos, API real local y cancelación: aprobadas, sin fallos ni omisiones. JUnit: `evidencias/pruebas_entrega.xml`.
- Cuatro conversiones completas y cuatro verificaciones independientes densas: aprobadas. Resultados, SHA-256, STEP, STL reparados y logs: `evidencias/cubo_bateria/`.
- Doce regresiones completas y reimportación independiente: aprobadas, sin deterioro detectado. Evidencia nueva: `evidencias/regresion_12/`; referencia: `evidencias/baseline_historica/`.
- Se conservan registros de la fase anterior, incluido el tiempo agotado del cubo antes de esta corrección, en `evidencias/fase_previa/`.
- Código e interfaz probados identificados en `evidencias/fuentes_probadas_sha256.json`; contenido del paquete en `MANIFIESTO_SHA256.txt`.

Las pruebas de API necesitan sockets locales autorizados por el entorno. Los STL no se envían a servicios de conversión externos. No se han ejecutado pruebas nativas Windows, edición en Onshape ni pruebas del motor WebAssembly.

## Cómo probar la entrega

Descomprimir `perfeccion_Visualizador.zip` en una carpeta nueva. La aplicación completa está en `Visor_experimental_fuentes/`. En Windows, ejecutar `Instalar_Entorno.bat` y después `Iniciar.bat`; esta copia abre el puerto 8766. El entorno Python debe instalarse como indica el instalador, no viene preinstalado en el ZIP.

Para inspeccionar inmediatamente el resultado CAD, abrir `evidencias/cubo_bateria/cubo-carrito.step`. Para repetir las pruebas, seguir `Visor_experimental_fuentes/GUIA_REPRODUCIR.md`. Conservar la instalación estable como referencia.
