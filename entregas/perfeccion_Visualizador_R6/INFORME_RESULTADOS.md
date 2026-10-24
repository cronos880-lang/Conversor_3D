# R6 experimental: validación de cavidades corregida; dos conversiones todavía pendientes

Cierre: 2026-10-24T22:57:32.451655+02:00, hora de Madrid. La fase R6 comenzó el 24/10/2026 a las 18:25 aproximadamente, hora de Madrid. Se trabaja sobre una copia independiente de R5. **No se han resuelto los STEP de 6558_fixed ni Pieza_Nueva_Detenida. Esta entrega documenta progreso y no es una actualización estable.**

## Cambio integrado y demostrado

El validador medía la distancia STL→CAD contra el primer shell del sólido. En piezas con una cavidad cerrada dejaba fuera las paredes interiores. R6 utiliza todas las fronteras del sólido, tanto en el control principal como en las comprobaciones locales y la proyección al B-Rep. Cuando existe un solo shell se conserva el recorrido anterior.

Dos pruebas nuevas exportan y reimportan un STEP con una cavidad cerrada: el modelo correcto supera la validación completa, incluidas inspección densa e interferencias. El control negativo rellena esa misma cavidad; aunque el volumen solo cambia aproximadamente un 0,1 %, por debajo del 0,5 % permitido, el programa lo rechaza por pérdida de geometría superficial. No se han relajado las tolerancias para hacerlo pasar.

Se mantiene una opción de punto medio para la compactación local de aristas, usada únicamente en los ensayos separados; su valor predeterminado sigue desactivado. Las nuevas estrategias CAD de investigación **no se integran en la ruta de conversión** al no superar los controles completos.

## Resultados reales

- **92 pruebas automáticas aprobadas, cero fallos, errores u omisiones**, en la batería R6. Incluye las 90 pruebas anteriores y los dos controles de cavidad. Las pruebas sobre las mallas regularizadas R5 vuelven a leer y contrastar esos fixtures; no se cuentan como nuevas conversiones STEP.
- **Cubo-carrito 4/4**, incluidas tres orientaciones rotadas. Se repite la conversión e inspección densa. DATA STEP y STL regularizados coinciden con los archivos previamente verificados de forma independiente; se incluye el certificado de identidad. No se afirma haber repetido el verificador independiente completo.
- **Regresión histórica: 10/12, igual que R5.** Las diez geometrías aceptadas conservan DATA STEP idéntico. Chasis y pinza permanecen rechazados. **Las 14 piezas originales no están superadas:** embudo continúa aplazado por indicación del usuario y conector no se ha repetido en esta fase.
- **Chromium Linux, aplicación Python R6:** carga real de 30383, conversión en Automático, 182 caras, descarga, invalidación al cambiar el perfil y Nuevo. El STEP descargado se reimporta: un sólido válido, cero interferencias y DATA idéntico a R5/R4. La referencia independiente anterior se aplica por identidad; no se repite Onshape.
- Se vuelven a ejecutar las dos piezas nuevas en procesos R6 separados. El resultado es el siguiente; un rechazo o timeout no se cuenta como éxito:

| Pieza | STEP aprobado | Malla regularizada | Resultado | Tiempo total s |
|---|---:|---:|---|---:|
| 6558_fixed.stl | No | Sí | cad_pendiente_tras_reparacion | 442.359 |
| Pieza_Nueva_Detenida.stl | No | Sí | cad_pendiente_tras_reparacion | 559.775 |

Ambas reparaciones R6 producen exactamente los mismos STL regularizados que R5 por SHA256: cero intersecciones CGAL, cero vértices no manifold, un cuerpo positivo y respectivamente una y cuatro cavidades. La desviación máxima observada frente al STL original es 0,0589640834 mm en 6558 y 0,0203341585 mm en Pieza Nueva. Estos valores corresponden a la reparación STL, no a un STEP aprobado. Los originales permanecen intactos.

Los informes y registros completos están en `evidencias/casos_finales`. El Visor conserva el error explícito y la descarga del STL regularizado cuando está disponible. Una malla regularizada **no demuestra un STEP válido ni una impresión correcta**. La prueba visual de este flujo con rechazo de R5 se conserva únicamente como referencia; no se presenta como repetida en R6.

## Investigación realizada y descartada como solución terminada

Se han desarrollado y probado por separado reconstrucciones por planos y cilindros, envolventes por secciones con certificado de cobertura, partición de celdas y clasificación por el campo de material del STL. En 6558 se obtuvo un STEP reimportable y con volumen dentro del límite, pero la prueba superficial lo rechazó: p95 observado 0,064434 mm y máximo muestreado 0,109451 mm, frente a 0,020 y 0,060 mm. No sirve como conversión aprobada. La pieza nueva produjo todavía dos cuerpos y un error de volumen superior al permitido.

También se reconstruyeron las cinco cavidades individuales de ambas mallas, con comprobación CAD y errores locales publicados. Las cavidades laminares requirieron una representación de espesor mínimo; esos ensayos no prueban el ensamblaje del STEP completo ni se activan en el Visor.

La regularización numérica de 6558 mejoró la calidad de los triángulos manteniendo cero intersecciones CGAL. El último acondicionamiento realizó 17 movimientos sobre 15 vértices, con desviación máxima observada de 0,00000329424 mm respecto de su entrada intermedia y ninguna altura de triángulo inferior a 0,000001 mm. Esa cifra no es el error total frente al STL original. El B-Rep resultante aún presenta 112 incidencias `BOPAlgo_SelfIntersect` en el control OCC, aunque `isValid()` devuelve verdadero, y se rechaza. Se conserva el diagnóstico con tipos y cajas de los elementos implicados. La validez de una malla y `isValid()` no bastan.

Se ensayaron además retriangulación, colapsos locales, parches planos y remallado. El remallado global produjo autointersecciones y no se usa. Un ensayo de cierre se detuvo al alcanzar su límite de memoria. Otros ensayos previos alcanzaron límites de recursos; los registros distinguen esos casos de los fallos geométricos. No se distribuyen los STEP rechazados como archivos utilizables. Los códigos, parámetros y resultados de investigación se conservan en `laboratorio_r6` y `evidencias/ensayos_r6`; algunos scripts requieren adaptar rutas y regenerar sus artefactos intermedios.

## Precisión y alcance

Automático conserva el perfil de precisión. Caja exterior 0,020 mm, volumen 0,5 %, p95 superficial 0,020–0,030 mm según escala y máximo observado 0,060 mm, con las reglas históricas del motor. La reparación conserva sus puertas locales de 0,002 mm y 0,001 % de volumen. No se activa 0,08 mm silenciosamente ni se escala la pieza para cumplir el límite. Las distancias son mediciones reproducibles de muestras, no una cota Hausdorff global ni recuperación de la intención de diseño.

Los 47 archivos de la R1 original se contrastan con el ZIP y permanecen intactos. La aplicación estática WebAssembly de `main` no se modifica. Las pruebas descritas validan el backend Python experimental; **no validan WebAssembly ni Windows nativo**. Tampoco se han probado Move face en Onshape, el laminador ni la impresión física en la K1C. Los tiempos son de un entorno Linux con procesos concurrentes y no permiten juzgar la velocidad del ordenador del usuario.

## Entrega y siguiente trabajo pendiente

Extraer todo el ZIP en una carpeta nueva. Ejecutar `Instalar_Entorno.bat` y después `Iniciar.bat`. Las fuentes completas están en `Visor_experimental_fuentes`; encabezado R6 y puerto 8770. Requiere Python 3.12 de 64 bits. No instalar archivos aislados sobre la versión anterior. La instalación nativa de Windows queda pendiente.

Se adjuntan aplicación completa, archivos modificados, patch frente a R5, material de prueba, evidencias y manifiesto SHA256. Las fuentes opcionales de reparación y sus dependencias/licencias se conservan. MeshLib y PyMeshLab no se añaden como dependencias de producción.

El trabajo que falta es obtener un B-Rep con separación numérica suficiente entre caras, aristas y vértices, conservando los detalles de las ranuras y las cavidades, y superar tras la exportación todos los controles contra el STL original. **No se da por terminada esa mejora.**
