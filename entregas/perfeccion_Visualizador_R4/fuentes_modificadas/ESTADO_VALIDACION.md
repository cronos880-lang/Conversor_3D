# R4 experimental: mejora parcial, aceptación global pendiente

Esta copia no está certificada como sustituto estable. El informe y los JSON
adjuntos distinguen conversiones aceptadas, rechazos y pruebas no realizadas.

Se mantiene el motor de superficies anterior. La nueva reconstrucción de bandas
circulares solo se ensaya para STEP ya válidos con mucha fragmentación planar,
malla moderada y evidencia geométrica de revolución. El original se conserva
si la alternativa falla. Nunca se acepta un STEP únicamente porque tiene menos
caras: se reimporta, se validan cotas, volumen, superficies e interferencias.

El nuevo diagnóstico del enlace de vértices detecta un defecto que un recuento
de aristas cerradas no encuentra. Rechazar temprano los tres STL afectados es
un avance de diagnóstico; su reparación automática sigue pendiente.

Automático conserva los límites de precisión originales. Impresión es una
opción explícita; no se activa silenciosamente si precisión falla. La interfaz
informa del nivel alcanzado, que puede ser mejor que el presupuesto solicitado.
No se escala la pieza ni se cambian unidades o coordenadas para pasar controles.

Las distancias son muestreadas: no constituyen una cota Hausdorff universal.
La prueba Linux del servidor local no valida la aplicación WASM ni Windows.
Move face en Onshape e impresión física K1C no se han comprobado.
