# R5 experimental: reparación de mallas demostrada; STEP de las dos piezas pendiente

Cierre de evidencia: 2026-10-24T18:07:19.579569+02:00. Fase iniciada el 24/10/2026 a las 13:50 aproximadamente (Europe/Madrid). Se entrega implementación completa sobre copia experimental, archivos modificados y resultados reales. **No es una actualización estable: las dos piezas se regularizan, pero ninguna obtiene un STEP aprobado.** No se modifica GitHub Pages/WebAssembly.

## Resultado concreto

R4 detenía 6558_fixed y Pieza_Nueva_Detenida al detectar respectivamente 33 y 54 vértices no manifold. R5 incorpora un reparador general de esa clase de contactos, sin seleccionar nombres de piezas ni retocar sus STL manualmente. Ambos archivos regularizados se guardan, se vuelven a leer y presentan **cero vértices no manifold y cero autointersecciones con el control exacto CGAL**, un cuerpo positivo de material y las cavidades indicadas abajo. Los originales permanecen intactos por SHA256.

| Pieza | Cavidades cerradas | Máx. frente a frontera extraída mm | Máx. frente a STL completo mm | Probes de material, 0 diferencias | Reparación s | Flujo completo s |
|---|---:|---:|---:|---:|---:|---:|
| 6558_fixed.stl | 1 | 0.000077211 | 0.058964083 | 3110 | 61.508 | 678.186 |
| Pieza_Nueva_Detenida.stl | 4 | 0.000086603 | 0.020334158 | 3384 | 415.929 | 643.826 |

**Estas cifras prueban la reparación de malla; no prueban una conversión STEP.** Los dos intentos CAD por pieza fallan al reconstruir un sólido aceptable. La aplicación informa `cad_pendiente_tras_reparacion`, mantiene deshabilitada la descarga STEP y ofrece «Descargar malla regularizada (STL)». Las evidencias conservan también esos rechazos y los registros. No se adjunta un STEP defectuoso de estas piezas como si estuviera resuelto.

## Implementación y conservación geométrica

1. Un proceso aislado obtiene por unión exacta la frontera del dominio orientado de material. Se usa el número de giro positivo como interpretación explícita del STL; una malla defectuosa puede admitir otras intenciones de diseño.
2. Se separan abanicos de vértices y cuñas de aristas conservando las superficies. Se ensayan desplazamientos locales acotados y se acepta cada uno solo si baja el recuento exacto de interferencias.
3. Los contactos de material preexistentes reciben micro-uniones o micro-aperturas de vacío, según la orientación y el anidamiento. No se unen objetos por proximidad ni se eliminan cuerpos pequeños. El semiancho local es 0,000050 mm; el presupuesto final se vuelve a medir.
4. Se verifican topología, autointersecciones, cotas, volumen, superficie y material. El STL se escribe ASCII con doble precisión, se reimporta y se repiten topología e intersecciones. No convertirlo a STL binario de precisión simple y suponer que conserva estos contactos microscópicos.
5. La reconstrucción CAD conserva coordenadas exactas y shells de cavidades únicamente en esta ruta. Se prueba con y sin protección local. Cualquier STEP candidato debe superar de nuevo las comprobaciones CAD y la comparación con el **STL original**, sin margen añadido por esta reparación.

La extracción de frontera sí retira superficies internas contradictorias. Por eso no se afirma que cada triángulo original permanezca: la separación máxima original/frontera es aproximadamente 0,058964 mm en 6558 y 0,020334 mm en Pieza Nueva. Se mide y publica, no se oculta usando solo una referencia ya reparada. El máximo y p95 frente al STL completo se comprueban además con límites 0,060 y 0,020 mm. Frente a la frontera extraída se exigen máximo 0,002 mm, cotas 0,002 mm y volumen 0,001 %. El error de volumen medido en esta última comparación es aproximadamente 0,000000499 % y 0,000002245 % respectivamente; error de caja cero.

Los controles de material toman más de 3000 puntos por pieza y puntos adicionales cerca de los contactos, fuera de una banda superficial de 0,002 mm. No encuentran discrepancias. Son muestreos reproducibles, no una demostración global Hausdorff ni un certificado de intención de diseño.

El cambio no relaja los límites CAD existentes ni activa 0,08 mm silenciosamente. Automático sigue siendo precisión; Impresión 3D conserva su opción explícita. El reparador se llama solo para entradas cerradas y orientadas con la clase compatible de contactos, con límites de tamaño y tiempo. `VISOR_REPARADOR_EXACTO=0` reproduce el rechazo previo. Las entradas sanas mantienen su ruta.

## Pruebas realizadas

- **90 pruebas automáticas distintas aprobadas, cero omitidas:** batería final de 90 sobre el código de entrega, incluidas las dos pruebas de cavidades y cuatro de protección de archivos. Se incluyen XML y salidas. Se conservan también las ejecuciones previas de 84 y las pruebas por separado, sin contarlas dos veces. Los cuatro controles de archivos verifican que ni las rutas coincidentes ni los temporales puedan borrar o sobrescribir la entrada.
- **Cubo-carrito 4/4.** Se repite la conversión y la inspección densa. DATA STEP, STL reparados y métricas coinciden exactamente con la referencia ya verificada de forma independiente. Se adjuntan su prueba previa y el certificado de identidad; no se afirma haber reejecutado el verificador independiente completo.
- **Regresión histórica 10/12, igual que R4.** Las diez piezas aceptadas conservan DATA STEP idéntico. Chasis y pinza siguen rechazados. **Las 14 originales no están superadas:** embudo continúa aplazado por indicación del usuario; conector no se repite en esta fase.
- **Dos piezas nuevas:** reparación y relectura exacta aprobadas en ambas; conversión STEP rechazada en ambas. No son fallos de cotas ni pruebas superadas por arrancar el programa.
- **Chromium Linux, servidor Python R5:** conversión real de 30383 en Automático, 182 caras, descarga, cambio de perfil y Nuevo. El STEP descargado se reimporta con un sólido válido, cero interferencias y DATA idéntico al R4 verificado independientemente. El mensaje de consola del script conserva la etiqueta antigua «R4»; el encabezado, puerto y registro del servidor corresponden a R5.
- **Chromium con 6558:** carga y conversión reales, rechazo CAD visible, exportación STEP deshabilitada y descarga efectiva del STL regularizado. Se contrasta su huella y se vuelve a comprobar CGAL. El primer script de prueba confundió el diagnóstico de texto con JSON; se corrigió el script y se repitió el flujo, sin alterar el endpoint para hacer pasar la prueba.
- Los 47 archivos de la R1 original permanecen intactos. Las versiones anteriores y la rama main no se sustituyen. Los tiempos son del entorno Linux con pruebas concurrentes; no caracterizan el ordenador del usuario.

## Ensayos descartados y límite actual

Se investigaron cierres B-Rep facetados, simplificaciones, protección de microaristas y una reconstrucción analítica por celdas. No se aceptaron resultados por mero cierre o validez aparente: algunos presentaban interferencias, otras alternativas excedían volumen o no separaban regiones con material distinto. La última alternativa por celdas se detuvo precisamente por clasificación contradictoria; no se integra como solución. Las bibliotecas de evaluación MeshLib y PyMeshLab no forman parte de las dependencias de producción.

La barrera pendiente es transformar una frontera con contactos microscópicos regularizados en un B-Rep robusto para el kernel CAD. El siguiente desarrollo debe reconstruir esas regiones con superficies y límites coherentes, preservando cavidades y material, y superar los mismos controles tras exportar e importar STEP. No basta volver a coser ni aumentar tolerancias. R5 establece y prueba la base de reparación, pero **no cierra todavía ese objetivo CAD**.

## Entrega y uso

Extraer todo el ZIP en una carpeta nueva. En la raíz ejecutar `Instalar_Entorno.bat` y luego `Iniciar.bat`. Las fuentes completas están en `Visor_experimental_fuentes`; puerto 8769, encabezado R5 experimental. Requiere Python **3.12 de 64 bits** por los wheels Windows de CGAL de esta versión. No instalar archivos aislados sobre la versión anterior. Se incluyen fuentes, patch respecto de R4, material de prueba, pruebas, registros, capturas, STL regularizados y manifiesto SHA256.

El reparador incorpora gpytoolbox/CGAL con componentes GPL y libigl; avisos y licencias en `LICENCIAS_REPARADOR`. Se distribuyen fuentes del componente y dependencias fijadas; no una licencia comercial de herramientas de laboratorio.

**Pendiente de prueba:** instalación y ejecución nativas en Windows, WebAssembly, Move face en Onshape y laminado/impresión física en K1C. El STL regularizado no se presenta como validación de impresión. No se certifica esta versión como actualización estable ni como solución completa de STL arbitrarios.
