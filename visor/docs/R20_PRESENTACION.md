# Presentación del Visor R20 en desarrollo

Mejora de la barra de progreso y del renderizado, conservando la distribución,
los cuatro botones, los perfiles, los contratos HTTP y el motor CAD.
No cambia la versión 20.0.0 ni los ZIP ya publicados. Este cambio de código se
incluirá en una entrega únicamente cuando el usuario la solicite.

La interfaz editable del desarrollo está en
`../src/conversor3d/resources/viewer/viewer.html`, con helpers JavaScript en
`../src/conversor3d/resources/viewer/presentation.js`. El servidor sirve ambos
desde recursos propios; el HTML histórico R19 conserva su hash. Los recursos
se incluyen en el paquete Python y en la huella de código del certificado.

## Progreso

- Barra, porcentaje y tiempo ocupan espacios separados. La fase comunicada por
  el servidor permanece visible y el pie se adapta a ventanas estrechas.
- El porcentaje procede de hitos publicados por el motor; no crece con el tiempo
  ni se usa la animación del indicador como una estimación de trabajo completado.
- Una respuesta `terminado` conserva como máximo 99 % mientras se descarga el
  STEP. Sólo recibir correctamente el archivo habilita Exportar y muestra 100 %.
- Un error detiene la animación y conserva el porcentaje alcanzado. Nuevo
  mantiene la cancelación del proceso y limpia la presentación anterior.
- El indicador incluye semántica accesible y respeta movimiento reducido.

## Vista 3D

Se suavizan exclusivamente las normales de iluminación de vértices de pantalla
coincidentes, con umbral de 35 grados para conservar aristas marcadas. No se
redondean ni desplazan posiciones, ni se modifican los bytes del STL o el modelo
que recibe el conversor. El suavizado no reconstruye superficies CAD y no reduce
las caras del STEP. Se conserva la iluminación plana por encima de 200.000
triángulos o ante una acumulación patológica de direcciones coincidentes.

La resolución de dibujo usa supersampling acotado, el límite del renderbuffer
de WebGL y un presupuesto de ocho millones de píxeles para el aumento de
resolución. Las pantallas mayores conservan como mínimo su resolución nativa
si el renderbuffer lo permite. La iluminación tiene luz principal y de relleno.
Encuadrar y la importación ajustan la cámara a las dimensiones y al aspecto de
la ventana; se conservan el giro, desplazamiento y zoom existentes.

## Comprobaciones

Los tests de `../tests/test_viewer.py` comprueban los helpers JavaScript con Node
cuando está disponible: progreso sin avances inventados, descarga antes de
completar, errores/cancelación, conservación exacta de posiciones, aristas
marcadas, presupuesto de suavizado y encuadre. Node no es dependencia del Visor.

La comprobación de navegador distingue estados simulados de una conversión
real. Las pruebas en Chromium/Linux no sustituyen las del PC Windows del
usuario. La integridad de R19 y el evaluador independiente siguen siendo
obligatorios; esta presentación no modifica sus límites.

Verificación local del 13 de noviembre de 2026: 52 tests de desarrollo
aprobados y 357 hashes R19 intactos. Chromium/Linux comprobó estados de progreso,
error, cancelación, descarga y exportación, sin errores JavaScript/WebGL, con
ventanas de 390, 650, 900, 1280 y 1880 píxeles. Estos escenarios de estados
controlados se comprobaron por separado de una conversión real desde la UI:
una caja de 4 × 5 × 6 mm se convirtió, descargó y reimportó en OCP como un sólido
válido de 6 caras y 120 mm³, con tolerancia máxima de arista de 1e-7 mm.
