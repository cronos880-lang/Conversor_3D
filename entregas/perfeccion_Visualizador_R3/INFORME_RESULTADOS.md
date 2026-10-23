# R3 — avance de desarrollo, no versión estable

Cierre parcial: 2026-10-23T22:40:31.959554+02:00.

Implementados un perfil opcional de impresión de 0,08 mm (precisión por defecto),
control de tiempo por triángulos y actividad CPU, mensajes con medida/límite,
reutilización de las consultas exactas de OpenCascade y prevención de reintentos
idénticos. Las recuperaciones CAD repiten el control avanzado de interferencias.

57 pruebas automáticas aprobadas; 3 verificaciones adicionales tras el ajuste
de actividad CPU. Chromium Linux completó importación, selección de impresión,
conversión y descarga. El STEP descargado se reimportó como un sólido válido.
La verificación densa conserva los límites del perfil y contrasta los puntos
teselados sospechosos con el B-Rep exacto antes de atribuir un error al CAD.

El cubo-carrito y tres giros: 4/4 conversiones aprobadas y DATA STEP idéntico
al de los archivos previamente verificados independientemente, incluyendo canal.

Regresión histórica: 10/12 aceptadas. Sus indicadores históricos no cambian.
El chasis queda rechazado al descubrir 0,071166 mm frente a su máximo de
0,062873 mm (incluye su preparación medida). Pinza queda rechazada por
interferencias que una recuperación anterior no comprobaba. No se afirma 14/14:
el embudo continúa aplazado y conector no se ha vuelto a ejecutar.

Las cuatro piezas nuevas no se consideran resueltas. La primera se aceptaba
antes con 32 avisos avanzados; ahora ese candidato se rechaza. Dimensiones
presenta una desviación de 0,145013 mm y las alternativas probadas no la han
resuelto. Las pruebas finales de 6558 y Pieza ambigua se estaban cerrando al
guardar este avance; ningún resultado pendiente se contabiliza como aprobado.

El entorno de ejecución perdió conexión temporalmente y se recuperó sin perder
los archivos. Se guarda ahora el progreso para conservarlo. Windows nativo y
Onshape siguen pendientes. Estas pruebas corresponden al Visor Python local,
no a la aplicación WebAssembly de GitHub Pages.
