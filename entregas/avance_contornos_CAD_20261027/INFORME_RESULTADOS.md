# Avance de contornos CAD: pinza verificada; actualización pendiente

Fecha de corte UTC: 2026-10-27T01:12:34.529345+00:00. Rama: `perfeccion_Visualizador`. Base de esta fase: commit `2cd8699` (M2).

**No se publica una nueva versión instalable del Visor.** Se entrega código completo de desarrollo, los once archivos nuevos/modificados de esta fase, el parche, STEP verificados y evidencias reales. La nueva construcción está implementada en la API de superficies y se activa explícitamente con `contornos_compartidos=True`; no está conectada automáticamente a `motor_v2`, al servidor ni a la interfaz. Abrir las fuentes con los `.bat` heredados ejecuta la ruta habitual y no activa esta mejora.

## Resultado principal: pinza desde el STL original

La API real convierte el STL original sin refinamiento previo, sin sustituir funciones durante el ensayo y sin condiciones por nombre de pieza. El código ensayado coincide con los 111 archivos congelados que se entregan. El STEP resultante tiene **447 caras**, frente a las **2.144 caras de la recuperación facetada R7**: una reducción del **79,15 %**. Conserva los **10 cilindros respaldados por el STL**; contiene 11 caras cilíndricas, que no equivalen a once cilindros independientes.

| Control | Resultado real |
|---|---|
| Lectura fría exacta OpenCascade | Válida, 1 sólido, 0 aristas con parametrización incoherente |
| Interferencias CAD BOP | 0 |
| Diferencia de caja | 0,000495 mm |
| Diferencia de volumen | 0,036864 % |
| Máximo observado en contraste geométrico denso | 0,003787 mm |
| Tolerancia máxima de arista CAD | 0,0000001 mm |
| Mallados absolutos 0,00025 / 0,0005 / 0,001 mm | Los tres cerrados, orientados, Euler −2, vértices manifold, 0 intersecciones CGAL |
| Máximo observado en esos tres mallados | 0,003788 mm |
| Tiempo del ensayo API, incluida lectura fría y BOP | 51.704 s |
| Tiempo de comprobación independiente posterior | 25.576 s |

Se emplearon el evaluador R7 y el control fino M1 **sin modificar**, incluidos en el paquete con sus huellas. No se han retirado triángulos degenerados, dispensado huecos ni cambiado los ajustes del mallador para aprobar el resultado. Las distancias son medidas por muestreo determinista y controles numéricos; **no constituyen una demostración Hausdorff global**. No se ha comprobado este STEP en Onshape ni se afirma que tenga historial paramétrico editable. La repetición desde las fuentes del paquete volvió a superar todas las puertas y produjo un bloque `DATA` idéntico al primer ensayo API; se conservan ambos resultados.

Archivos principales: `resultados_verificados/pinza_api_integrada.step`, `evidencias/resultados/pinza_api_integrada.json`, `evidencias/resultados/pinza_api_contraste.json`. También se conserva un prototipo anterior de 436 caras que pasó todas las puertas con una entrada OFF refinada localmente. Es una prueba separada; el resultado principal de 447 caras usa directamente el STL original.

## Mejora implementada en el motor

Se construyen curvas de borde compartidas y sus pcurvas con la misma parametrización en las dos caras. Los encuentros analíticos se calculan sobre las superficies respaldadas por la entrada. Se conservan las esquinas y se dividen las zonas que no admiten la misma superficie sin perder la geometría fuente.

Se corrigió un problema numérico concreto: un tramo inferior a un milímetro estaba descrito mediante una elipse de radio mayor de 191 millones de milímetros. Su representación racional local evita la cancelación numérica sin cambiar la curva dentro del presupuesto numérico verificado. Los parches triangulares pasan a usar un dominio regular, eliminando el ápice colapsado que provocaba fallos reales de mallado. Las caras sólo se convierten a planos cuando todos los polos de pesos positivos demuestran la coplanaridad de la superficie completa.

Archivos nuevos: `contornos_compatibles.py`, `pcurvas_compartidas.py`, `fijacion_contornos.py`, `parches_triangulares.py`, `planos_canonicos.py` en `motor_superficies`, y cuatro archivos de pruebas. Se añaden parámetros opcionales en `meshfit_brep.py` y `meshfit_step.py`. El valor por defecto es falso y conserva el comportamiento anterior. No se ha sustituido el motor indiscriminadamente.

## Tolerancias y pruebas automáticas

Se mantienen los límites originales del perfil Precisión: caja 0,020 mm, volumen 0,5 %, p95 0,020 mm y máximo observado 0,060 mm. `TOLERANCIAS_VERIFICADAS.json` compara las constantes y las huellas de los archivos de validación con R7. La opción de 0,08 mm no se ha seleccionado ni convertido en una aceptación automática en estos ensayos.

**170 pruebas pasan, 0 fallan y 0 se omiten**, incluidas las 17 nuevas. El primer intento de la suite tuvo 153 pasadas, 2 fallos por variables de fixtures ausentes y 15 omisiones; se conserva íntegro. Se configuraron las rutas de los materiales existentes y se repitió la suite sin modificar las pruebas ni sus expectativas. La ejecución configurada y su XML son la referencia final.

## Regresión de conversiones completas: ruta habitual

21 de 21 casos ejecutados a este corte; 21 pasados. No se cuentan como éxito los no ejecutados. Cada caso comprueba las huellas del STL y de las fuentes, realiza una conversión completa con perfil Precisión y conserva salida, registros, tiempo y RAM. Se usan dos colas, con los mismos límites individuales y fuentes. Se replanificaron los tres casos finales para terminar antes de las 01:12 UTC y reservar tiempo de entrega dentro de las cinco horas: los intentos iniciales interrumpidos se conservan y no se cuentan como fallos CAD ni como éxitos. `REPLANIFICACION.json` registra la intervención; el resumen combinado identifica la procedencia de cada resultado. **Esta batería usa la ruta habitual, no `contornos_compartidos=True`.**

La columna M1 compara el bloque `DATA` del STEP con la regresión de la fase anterior. Para evitar duplicar otros 157 MB de STEP se entregan las huellas SHA256 de esos bloques M1 en `REFERENCIAS_M1_SHA256.json`; las ejecuciones de esta fase realizaron la comparación directa de bytes y se han contrastado también esas huellas con los 21 resultados nuevos. Se entregan completos los STEP R7 y los resultados M3. La comparación R7 se muestra aparte: diferencias ya existentes antes de esta fase no se presentan como identidad con R7. La cabecera del STEP, que contiene metadatos variables, no forma parte de esa comparación.

| Caso | Conversión | Segundos | DATA idéntico a M1 | DATA idéntico a R7 |
|---|---|---:|---|---|
| cubo-carrito | PASA | 51.551 | sí | sí |
| cubo-carrito_giro_1 | PASA | 57.094 | sí | sí |
| cubo-carrito_giro_2 | PASA | 40.351 | sí | sí |
| cubo-carrito_giro_3 | PASA | 103.913 | sí | sí |
| 1x1-lego-brick | PASA | 36.136 | sí | sí |
| Bancada_Motor | PASA | 170.283 | sí | no |
| Estefi | PASA | 314.27 | sí | sí |
| Grapa | PASA | 45.254 | sí | sí |
| LLanta_Trasera | PASA | 30.462 | sí | sí |
| M3 PClip - 2mm | PASA | 82.47 | sí | sí |
| Spoiler_arrière_Porsche_-_5 | PASA | 6.666 | sí | sí |
| Tirante | PASA | 50.124 | sí | sí |
| chasis - Part 2 | PASA | 359.667 | sí | sí |
| maneta | PASA | 20.679 | sí | sí |
| pinza | PASA | 84.602 | sí | no |
| spur | PASA | 147.544 | sí | sí |
| conector | PASA | 753.205 | sí | sí |
| 6558_fixed | PASA | 597.779 | sí | sí |
| Dimensiones | PASA | 159.941 | sí | sí |
| Con fallos pero si step | PASA | 537.849 | sí | sí |
| Pieza_Nueva_Detenida | PASA | 1128.221 | sí | sí |

Los 14 históricos son las doce piezas del grupo `historica12`, conector y embudo. Embudo sigue aplazado por petición del usuario: **no se declara 14/14**. Las cuatro rotaciones del cubo-carrito sí se han vuelto a ejecutar; conservan exactamente el contenido geométrico STEP de referencia R7 y M1.

## Fallos y límites que permanecen

**Lego 4×2:** la API nueva produjo 940 caras sin bordes libres ni caras rechazadas por el control ordinario, pero el sólido completo fue inválido y no se exportó como resultado aprobado. La composición por booleanos de sus cavidades también se ensayó por separado y falló: exactitud falsa y una incidencia BOP. No se han rellenado sus ocho cavidades ni invertido silenciosamente el STL para forzar un éxito. Sigue siendo el siguiente bloqueo de calidad.

**Bancada:** el ensayo API produjo lectura exacta válida, 2.080 caras y BOP 0 a los 291,353 s. El proceso alcanzó el límite de 300 s durante su salida y terminó con código 124; no se registra como finalización normal. La comprobación independiente pasó geometría (caja 0,000561 mm, volumen 0,002782 %, máximo denso observado 0,000730 mm), pero **falló la conservación de los cilindros respaldados**: falta el cilindro exterior de radio 2,5 mm de una de las zonas. Se rechazó el candidato en esa puerta y **no se ejecutaron después los tres mallados**. Que pase geometría y exactitud no convierte este resultado en una mejora aprobada. El diagnóstico y las variantes posteriores conservan su estado separado en los JSON y registros.

**No probados en esta fase:** Windows nativo, Onshape, impresión en Creality K1C, conversión WebAssembly y el flujo de la nueva ruta en navegador. Tampoco se ha repetido aquí la batería externa completa ni se han resuelto todos los STL recientes del usuario. Las pruebas Python no validan WebAssembly. No se ha medido una mejora general de velocidad ni se ha resuelto el problema de las líneas exteriores de 6558 en Onshape.

Los intentos anteriores que sólo pasaron la comprobación estándar o exacta, pero fallaron en geometría, BOP o mallado, permanecen como resultados negativos. Entre ellos: una desviación de 0,418376 mm antes de acondicionar la elipse; parches Coons con exactitud válida pero mallados ambiguos; y un intento de cambiar el mallador que tampoco los corrigió. No se adoptaron excepciones a los controles para aceptarlos.

## Reproducción y continuación

Consulta `REPRODUCIR.md`. Se incluyen fuentes completas, parche respecto a M2, fixtures privados, STEP de referencia R7, huellas de referencia M1, evaluadores inmutables, entorno de referencia, resultados JSON/XML y registros de intentos. Los STEP fallidos grandes se excluyen de los resultados recomendados; sus errores y registros se conservan.

El siguiente paso es resolver la composición/contención CAD de Lego con sus cavidades y completar la generalización de los parches regulares. Después debe integrarse la ruta como recuperación vigilada tras un rechazo concreto, sin desplazar conversiones que ya pasan, y repetir las puertas en el flujo real antes de entregar una actualización instalable.


## Candidato posterior: prioridad de cilindros confirmados

Este candidato se conserva **separado de M3** en `variante_prioridad_cilindros/fuentes`, con su propia huella y parche. Primero asigna las superficies cilíndricas respaldadas por todos sus vértices y centroides (límite anterior de 0,008 mm); después segmenta las demás regiones. Las entidades manuales del usuario mantienen prioridad. El caso negativo de un hexágono impide tomar como cilindro un polígono sólo porque sus vértices estén sobre una circunferencia.

Estado de Bancada en este candidato: **NO CONSTA aprobado en todas las puertas**. Estado de la repetición completa de pinza: **PASA**. No se publica como actualización del Visor.

| Medida de Bancada en la variante | Resultado registrado |
|---|---|
| Caras / sólidos / BOP | 1896 / 1 / 0 |
| Exactitud en lectura fría | True |
| Cilindros confirmados / preservados | 15 / 15 |
| Caja / volumen | 0.000561 mm / 0.003693 % |
| Desviación máxima densa observada | 0.00073 mm |
| Resoluciones finas completadas | 0 de 3 |
| Error de comprobación independiente | El mallado fino del STEP cambia la frontera o deja zonas abiertas; descartado. |
| Suite del candidato (total / fallos / errores / omitidas) | 173 / 0 / 0 / 0 |

La batería de 21 conversiones de esta entrega corresponde a las fuentes M3. **No se afirma que haya sido repetida con este candidato posterior.** Sus verificaciones específicas se registran en `variante_prioridad_cilindros/ESTADO.json`. Tampoco resuelve el Lego ni activa la mejora en la interfaz.
