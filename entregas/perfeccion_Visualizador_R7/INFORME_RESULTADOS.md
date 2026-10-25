# R7 experimental: recuperación de STEP que antes se rechazaban

Cierre: 2026-10-25T02:10:13.900188+02:00, hora de Madrid. Desarrollo en una copia independiente desde el 24/10/2026 a las 23:30, hora de Madrid. **6558 y Pieza Nueva ya superan la conversión completa y los controles contra el STL original.** La mejora se integra en el motor como recuperación adicional; las rutas anteriores conservan prioridad. Esta entrega no modifica main ni la aplicación WebAssembly.

## Qué cambia

Una malla puede estar cerrada y no tener intersecciones exactas, pero presentar separaciones entre caras menores que la resolución numérica de OpenCascade. R7 ajusta conjuntamente esos contactos mediante restricciones geométricas, comprueba las posiciones intermedias con CGAL y conserva todas las envolventes de material y cavidades. Construye después un B-Rep con vértices y aristas compartidos por índice y consolida planos con tolerancias estrictas.

Se adelanta además el rechazo de candidatos que ya superan el error de volumen del 0,5 %. En el conector se observó un candidato con un error de volumen del 60,023868 % que consumía decenas de minutos en la medición posterior; comprobar su volumen tardó menos de dos segundos. El límite no cambia: se evita trabajo que no puede rescatar el candidato y se permite probar las demás rutas. La comprobación completa con el rechazo anticipado descartó ese mismo candidato en 13,370 s. Un segundo candidato nativo, válido como sólido y de 46 caras, también se rechazó por una desviación densa de 0,633853 mm frente a 0,060000 mm; la validez CAD y pocas caras no bastan. Los registros conservan el ensayo anterior y la repetición completa.

Se corrige también el cálculo de proximidad para triángulos microscópicos: las tolerancias absolutas de las funciones anteriores podían devolver distancias erróneas o NaN. Las nuevas pruebas contrastan escalas y orientaciones. El método no selecciona casos por nombre o huella del archivo.

**La recuperación produce un STEP sólido facetado. Las curvas siguen facetadas; no recupera cilindros, un historial paramétrico ni garantiza Move face.** La interfaz lo indica como «STEP de recuperación · curvas facetadas». El motor analítico anterior continúa usándose cuando supera sus comprobaciones; 30383 conserva sus 182 caras y su geometría previa.

## Resultados completos

| Pieza | STEP aprobado | Caras STEP | Error volumen % | Máximo observado mm | Tiempo s |
|---|---:|---:|---:|---:|---:|
| 6558_fixed.stl | Sí | 8713 | 0.000107 | 0.058964 | 463.779 |
| Con fallos pero si step.stl | Sí | 2567 | 0.0 | 0.000592 | 549.554 |
| Dimensiones tambien.stl | No | — | — | — | 137.359 |
| Dimensiones.stl | Sí | 1100 | 0.0 | 5e-06 | 206.49 |
| Pieza ambigua.stl | No | — | — | — | 375.635 |
| conector.stl (motor completo) | Sí | 19998 | 0.002912 | 0.010826 | 460.705 |
| Pieza_Nueva_Detenida.stl (navegador) | Sí | 8892 | 3e-06 | 0.020334 | 939.319 |

La tabla usa para 6558 el máximo observado por la comprobación independiente más densa. El registro del motor indica 0,016360 mm sobre su propio conjunto de muestras; ambas mediciones permanecen por debajo de 0,060000 mm.

En 6558 se conserva su cavidad cerrada; en Pieza Nueva, las cuatro cavidades. Ambos STEP se reimportan como un sólido válido, con cero interferencias OCC y tolerancia máxima de aristas de 0,0000001 mm. Se comprueba la característica de Euler, el número de envolventes y puntos de vacío OUT/material IN para cada cavidad. El Euler corregido cuenta contornos que comparten vértices como una frontera conectada; se contrasta de forma independiente teselando los STEP, sin sustituir la puerta de topología.

La inspección independiente de las superficies de ambos STEP encuentra mallas estancas y orientadas, cero vértices no manifold, cero intersecciones CGAL y Euler -70/-186. Las distancias máximas muestreadas contra el original son 0,0589640834 y 0,0203341585 mm. Los resultados del primer recorrido completo tienen DATA STEP idéntico a esos modelos verificados; el STEP descargado del recorrido final se vuelve a leer y comprobar. Son medidas muestreadas, no una demostración global Hausdorff respecto del STL original.

Dimensiones también sigue rechazándose: su regularización no conserva la topología. Pieza ambigua produce un candidato CAD válido pero se rechaza por máximo superficial muestreado 0,061414 mm, superior al límite de 0,060000 mm. No se distribuye ese candidato como STEP aprobado ni se cambia el límite para aceptarlo.

## Regresión y controles negativos

- **123 pruebas automáticas aprobadas, sin fallos, errores ni omisiones.** Se registran tres avisos de bibliotecas durante casos negativos; el stdout completo está incluido. Incluyen las anteriores y las nuevas guardias de material, cavidades, taladros, entradas abiertas, aliases de salida y cuerpos microscópicos. Los dos fixtures R5 se vuelven a contrastar; no se cuentan como nuevas conversiones.
- **Cubo-carrito 4/4**, incluidas tres rotaciones. Conversión e inspección densa repetidas; DATA STEP y STL reparado idénticos a los resultados previamente verificados de forma independiente. Se adjunta certificado de identidad; no se afirma reejecutar el verificador independiente del cubo.
- **Regresión histórica 12/12**, frente a 10/12 en R6. Las diez conversiones anteriores conservan DATA STEP y las métricas geométricas comparadas. Pinza y chasis pasan ahora. El chasis de 190.912 triángulos usa preparación verificada de 20.000 caras, dentro del presupuesto histórico de 0,010 mm, conserva Euler y se juzga finalmente contra el original sin margen adicional. El primer ensayo rechazado del chasis se conserva, además de la repetición completa aprobada.
- Referencia inmediata del conector sin rechazo anticipado: no aprobado, 2300.738 s, interrupción tiempo_agotado.
- **Conector repetido: aprobado**, 460.705 s. Se adjunta su resultado real. La comparación inmediata antes/después mantiene el mismo límite de 2300 s. La referencia histórica de 900 s sigue siendo un ensayo distinto. Se conserva la estrategia elegida en el JSON para distinguir reconstrucción nativa y recuperación facetada. **No se afirma 14/14**: el embudo continúa aplazado por indicación del usuario.
- Chromium Linux, interfaz real: 30383 en Automático, 182 caras, descarga, cambio de perfil invalida el STEP y Nuevo. Segundo flujo completo con Pieza Nueva: carga del original, conversión, etiqueta facetada, precisión alcanzada y descarga. Los STEP descargados se reimportan. En un primer intento el test leyó el mensaje antes de que el DOM terminara de actualizarse; el motor sí finalizó en 1343,377 s. Se corrigió la espera del test y se repitió el flujo completo; el registro inicial permanece incluido.
- Los controles negativos rellenan una cavidad o un taladro con una variación de volumen inferior al 0,5 %; deben rechazarse por pérdida de topología. Una cavidad con pared casi tangente se convierte tanto en su orientación original como rotada. No se eliminan islas pequeñas para forzar un único sólido.

Ensayo adicional del módulo aislado del conector: aprobado, 334.583 s. Es una invocación directa del módulo de recuperación, no el recorrido completo de la interfaz; sus evidencias están en conector_directo.

Tras integrar el rechazo temprano del volumen se repite la validación fría de los STEP de 6558, Pieza Nueva y cubo-carrito, con todas las métricas geométricas comparadas idénticas. También se repiten la batería completa de pruebas y las 12 conversiones de regresión.

Los tiempos se midieron en Linux con cuota de dos CPU y trabajos concurrentes. No son una medición de Windows ni del ordenador del usuario. El servidor conserva el presupuesto adaptativo acotado y el control de RAM; la cancelación incluye los procesos hijos. No se presentan timeouts como fallos dimensionales.

## Precisión preservada y límites

Automático mantiene caja 0,020 mm, volumen 0,5 %, p95 0,020–0,030 mm según escala y máximo observado 0,060 mm. **Los perfiles, la inspección densa, el control topológico, el preprocesador y el reparador exacto anteriores permanecen idénticos a R6**, al igual que las funciones de preparación y núcleo CAD. La función de calidad añade únicamente un rechazo temprano del mismo error de volumen, antes de calcular la caja o teselar un candidato inviable. Se incluyen huellas del código y comparación. No se activa 0,08 mm silenciosamente ni se escala la pieza.

La estabilización adicional limita el movimiento a 0,002 mm, volumen 0,001 % y caja 0,002 mm respecto de la malla preparada. Mantener la misma triangulación permite calcular una cota global del movimiento superficial adicional a partir de los vértices. Esta cota se refiere a esa fase, **no al error total frente al STL original**. Después se aplican de nuevo las puertas históricas contra el original. Las cavidades y el campo de material tienen controles propios; un volumen correcto o isValid por sí solos no bastan.

No es un reparador universal. Se requiere una frontera cerrada y orientada; las entradas densas necesitan una preparación segura, y no se aceptan más de 250.000 triángulos en esta recuperación ni más de 25.000 en su malla de trabajo. El límite de entrada sigue en 30 MB. Se rechazan los casos que no permiten verificar material, topología o precisión.

Los 47 archivos de la R1 original se contrastan con el ZIP y permanecen intactos. **Windows nativo, WebAssembly, Onshape/Move face, laminador e impresión K1C no se han probado en esta fase.** Esta copia Python experimental no equivale a una validación o actualización del conversor estático de main. No se da por superada toda la validación histórica de 14 piezas.

## Uso y entrega

Extraer todo el ZIP en una carpeta nueva. Ejecutar Instalar_Entorno.bat y después Iniciar.bat. La carpeta Visor_experimental_fuentes está incluida, requiere Python 3.12 de 64 bits, muestra R7 experimental y usa el puerto 8771. Conservar la instalación anterior. No copiar archivos aislados sobre ella. La instalación nativa de Windows queda pendiente.

Se entregan aplicación completa, archivos modificados, patch frente a R6 publicada, material original de prueba, STEP aprobados, informes reales, pruebas reproducibles y manifiesto SHA256. Los fixtures CAD rechazados están marcados como tales y sirven para controles negativos. Los módulos de investigación descartados no se incorporan al motor. Se conservan avisos y licencias de CGAL/gpytoolbox y libigl; no se añade MeshLib como dependencia de producción.

## Verificación del archivo descargable

El ZIP final se ha extraído en una carpeta con espacios y se han ejecutado desde sus fuentes dos recuperaciones reales: una caja y una cavidad casi tangente rotada. Ambas pasan, incluido el worker aislado y las guardias geométricas. La evidencia externa `VERIFICACION_PAQUETE.json` identifica el SHA256 exacto del ZIP probado. Esta comprobación se realizó en Linux.
