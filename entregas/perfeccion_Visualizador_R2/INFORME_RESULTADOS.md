# perfeccion_Visualizador R2 — resultados reales y trabajo pendiente

Fecha: 23 de octubre de 2026. Visor Python experimental, Linux/Python 3.12.
Trabajo de esta fase iniciado a las 17:22 UTC. Esta entrega es un avance y no
una actualización estable con las tres piezas resueltas.

## Resultado

- **Fallo_Dimensional.stl: corregido y verificado.** Cuatro cuerpos cerrados
  entraban en contacto con redondeos numéricos que dejaban membranas internas
  espurias. La reparación anterior fallaba con 1,600 mm de discrepancia; la
  nueva estabiliza únicamente contactos preexistentes. El máximo desplazamiento
  de vértice fue 0,0000002343 mm y la unión se contrasta de nuevo con el original.
  El STEP tiene 61 caras y un sólido válido, sin autointerferencias OCC. La
  comprobación independiente densa midió como máximo 0,00785 mm y no encontró
  discrepancias en 1.882 puntos de material alejados de la superficie.
- **Pieza ambigua.stl: reparación de entrada implementada; CAD pendiente.**
  Contiene ocho cuerpos cerrados. Cuatro salientes huecos tienen discos
  coincidentes y opuestos en el fondo, de espesor exactamente cero. La nueva
  regularización cancela solo esa cobertura opuesta, conserva la frontera
  orientada y no crea ni mueve vértices. Permite contrastar la unión con una
  referencia independiente. Sin embargo, un prototipo CAD de 146 caras que
  pasaba BRepCheck, cero interferencias, 800 muestras por dirección y todas las
  aristas falló la inspección densa: **0,348500 mm**, frente a **0,060 mm**.
  Se ha incorporado ese rechazo al programa. Ese prototipo NO se entrega como
  STEP aprobado. La reconstrucción de contornos circulares y encuentros con
  la base necesita trabajo adicional; no se cambia una cota para admitirla.
- **4600_fixed.stl: pendiente de conversión válida.** La malla tiene 9.536
  triángulos, es cerrada y contiene un cuerpo. El 78 % corresponde a comprobaciones
  CAD y ensayos de reconstrucción, no a un porcentaje proporcional al tiempo.
  Se reprodujo además una alteración de la caché de triangulación de OpenCascade
  durante la medición; ahora el muestreo usa una copia y preserva el B-Rep
  reimportado para juzgarlo. Esto elimina un falso diagnóstico, pero el candidato
  resultante conserva defectos reales: un prototipo de 688 caras arroja 395
  avisos avanzados de interferencia OCC. Las variantes y el saneamiento probado
  no dieron un STEP aprobado. Una ejecución completa acabó en rechazo a los
  259,328 segundos; no se declara solucionada porque arranque o exporte algo.

El STEP aprobado de la primera pieza está junto al ZIP y en las evidencias.
Los candidatos defectuosos se incluyen únicamente en una carpeta llamada
`material_pruebas/regresiones_cad_no_aceptados` para reproducir los tests que
obligan a rechazarlos. No deben usarse como piezas finales.

## Cambios implementados

`contactos_numericos.py` estabiliza planos de contacto ya existentes, con
movimiento máximo limitado por la escala y por 0,000020 mm. No cierra separaciones
por cercanía. `preprocesador_stl.py` vuelve a verificar el resultado en coordenadas
originales frente a la unión independiente obtenida del STL original.

`regularizacion_planar.py` detecta y cancela caras coplanares opuestas dentro de
5·10^-10 mm. Exige la misma frontera orientada, volumen, caja y vértices existentes.
La referencia poliédrica OCC en `verificacion_reparacion.py` revalida el sólido
individual y comprueba que no quedan interferencias. No rellena agujeros abiertos.

`motor_v2.py` conserva el motor de superficies y las estrategias históricas para
entradas sanas. La ruta precisa posterior a una reparación verificada admite hasta
12.000 triángulos. El muestreo trabaja sobre una única copia para conservar la
secuencia de teselado histórica sin modificar la topología que se inspecciona.
Los mensajes de avance describen la reimportación, el muestreo y el número de
puntos verificados durante el 78 %. El HTML permanece byte a byte idéntico.

`saneamiento_cad.py` ensaya un recálculo de intersecciones de caras y reparación
de aristas pequeñas con precisión 0,001 mm y booleano sin fuzzy adicional. Solo
admite un sólido válido, reexportado y reimportado que pase todos los controles.
Ninguna de las tres piezas necesita un resultado de ese rescate para considerarse
aprobada en esta entrega: la primera pasa sin él y las otras siguen pendientes.

`validacion_densa.py` añade para entradas reparadas 3.000 puntos STL, incluidos
interiores de triángulos con semilla fija, y muestras de vértices, centroides y
aristas CAD finas. Los mismos límites anteriores se aplican a estas muestras.
La comprobación OCC avanzada se exige en entradas reparadas y en los casos donde
se ha reproducido el defecto de caché. Una forma cerrada no basta para aceptarla.

## Precisión y límites

No se relajan los límites de aceptación: caja 0,020 mm, volumen 0,5 %, p95
0,020–0,030 mm según la escala histórica y máximo observado 0,060 mm. Solo se
conserva el margen de preparación que ya existía cuando se emplea reducción
medida de malla; no se añade para las tres piezas nuevas ni para el cubo.
La unión tiene controles adicionales de caja/máximo 0,002 mm y volumen 0,001 %.

Las tolerancias internas que almacena OCC en aristas pueden diferir de los
parámetros de construcción y se registran en el JSON. No se las ha incrementado
como mecanismo para hacer pasar las pruebas. La aceptación depende de distancias,
volumen, cotas e integridad del STEP realmente escrito y reimportado.

Las distancias son mediciones muestreadas, no una demostración Hausdorff global.
Por ello se han mantenido las pruebas independientes de ocupación y volumen
adaptativo, además de aumentar el muestreo. La pieza ambigua demuestra por qué
una inspección topológica y una muestra pequeña no bastan.

## Regresiones y pruebas

Se regeneraron los STEP de las **12 piezas históricas que convertían en la
referencia**, con las mismas huellas de entrada. Coinciden sus indicadores
comparados de caras, volumen, caja, distancias y tolerancias; todos vuelven a
reimportar como un sólido válido. Ver `comparacion_regresion_12.json` y la batería.

También se regeneraron el cubo-carrito y sus tres giros, conservando los mismos
indicadores comparados. El control denso añadido se repite sobre esos cuatro
casos en la batería final. Las pruebas independientes de la entrega previa del
cubo, incluyendo el canal y el volumen adaptativo, se conservan en la entrega
anterior; aquí se comprueba además la identidad binaria de la sección DATA del STEP y de
los STL original/reparado con aquellos archivos verificados. No se ha vuelto a
ejecutar el verificador independiente del cubo: se certifica que la geometría
ensayada es exactamente la misma, sin depender de que parezca igual en pantalla.

**No se afirma 14/14:** el embudo se ha aplazado por indicación del propietario;
el conector agotaba 900 s también en la referencia y no se ha vuelto a ejecutar.
Las doce conversiones históricas que funcionaban siguen siendo la regresión
positiva repetida en esta fase.

Las pruebas automatizadas incluyen casos negativos de separaciones reales,
contactos por arista/punto, fondos finos reales, cancelación plana, los dos STL
multicuerpo, la falsa invalidación de caché y el rechazo del prototipo que pasa
BRepCheck pero pierde geometría. Los resultados JUnit y los registros completos
se incluyen en `evidencias`; los tests de casos reales se ejecutan con sus
variables de entorno, no se omiten por faltar las piezas.

## Instalación y alcance

Extraer `perfeccion_Visualizador_R2.zip` en una carpeta nueva. Los lanzadores
`Instalar_Entorno.bat` e `Iniciar.bat` están directamente en la raíz y llaman a
la aplicación completa en `Visor_experimental_fuentes`. Requiere Python 3.12
64 bits. Usa el puerto experimental 8766. No sobrescribir la instalación estable.

Windows nativo y la instalación de sus dependencias no se han ejecutado en esta
sesión Linux. El test de API local no es un ensayo manual del navegador. Onshape
Move face sigue pendiente. Esta entrega no actualiza ni valida el conversor
WebAssembly publicado en GitHub Pages. La rama principal y la entrega anterior
se conservan; los nuevos archivos se añaden en la rama experimental existente.

## Siguiente trabajo concreto

Corregir la construcción/parametrización de contornos del B-Rep para la pieza
ambigua y las interferencias de 4600_fixed, conservando los nuevos fixtures de
rechazo como regresión. Cada corrección deberá superar la inspección densa,
material/cavidades y reimportación del STEP antes de contar el caso como resuelto.
No es necesario invertir tiempo en el embudo para continuar estas dos piezas.

## Cierre de la batería final

45 pruebas automáticas aprobadas, cero fallos/errores y cero omitidas. Tres avisos NumPy proceden de casos degenerados negativos deliberados.

| Pieza nueva | Resultado del programa final | Segundos | RAM pico MB |
|---|---|---:|---:|
| 4600_fixed.stl | Límite de recursos: tiempo_agotado | 420.209 | 691.44 |
| Fallo_Dimensional.stl | Aprobada, también por verificación independiente | 80.679 | 668.89 |
| Pieza ambigua.stl | Límite de recursos: tiempo_agotado | 420.135 | 845.67 |

En esta repetición había otras pruebas en marcha. Los tiempos no deben utilizarse como comparación de rendimiento. 4600_fixed alcanzó el límite de 420 s; la ejecución previa completa de 259,328 s también acabó rechazada. No se interpreta el timeout como prueba geométrica ni como conversión resuelta.

| Cubo-carrito final | Segundos | Control denso adicional |
|---|---:|---|
| cubo-carrito.stl | 176.459 | Aprobado; máximo 0.026240 mm |
| cubo-carrito_giro_1.stl | 197.171 | Aprobado; máximo 0.023355 mm |
| cubo-carrito_giro_2.stl | 66.001 | Aprobado; máximo 0.011917 mm |
| cubo-carrito_giro_3.stl | 233.455 | Aprobado; máximo 0.012582 mm |

La batería final del cubo mantiene los mismos indicadores históricos, verificados en `comparacion_cubo_final.json`. La prueba de identidad con la geometría previamente verificada y el informe independiente anterior están en `entrega_cubo/identidad_geometria_previamente_verificada.json`. La comprobación independiente de la primera pieza nueva, con volumen adaptativo y material, está en `entrega_r2/verificacion_independiente.json`. Los otros dos casos se registran como pendientes, nunca como aprobados.
