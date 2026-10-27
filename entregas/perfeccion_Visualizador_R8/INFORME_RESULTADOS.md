# Visor STL → STEP R8 experimental completa

Esta entrega integra en el Visor para Windows la recuperación automática de encuentros entre superficies CAD y la normalización conservadora de ciclos circulares/elípticos. Se usa una copia independiente; se mantiene la prioridad de las conversiones anteriores y el perfil Precisión. No modifica R7 ni la web de main.

## Avance demostrado

- **Bancada_Motor:** el STEP de referencia R7 tenía 89 caras y no superaba la comprobación CAD exacta. R8 entrega 1.896 caras, con 15 cilindros respaldados por el STL, coherencia exacta y BOP aprobado. El ajuste de tres ciclos partidos elimina tres aristas redundantes sin desplazar vértices, elevar tolerancias ni quitar superficies. El nuevo resultado también genera fronteras cerradas y orientadas en tres discretizaciones finas, sin autointersecciones CGAL. No se afirma una reducción de caras frente a R7 en esta pieza.
- **Pinza:** pasa de 2.144 caras planas en la referencia R7 a 448 caras con 10 cilindros respaldados por el STL. STEP exacto, BOP aprobado y tres fronteras finas comprobadas. Es reconstrucción de superficies; no recupera el historial paramétrico original.
- **Cubo-carrito y tres giros:** las cuatro conversiones completas aprueban ahora también la comprobación CAD exacta. La referencia R7 del cubo tenía 255 caras y fallaba ese nuevo control; la recuperación conservadora entrega 1.152 caras facetadas, regenerando y contrastando primero la unión desde los componentes originales. No se presenta como reconstrucción analítica de sus curvas. La prueba del cubo desde la interfaz también descarga el STEP y contrasta su huella con el archivo validado por el servidor.
- **Control de reintentos y memoria:** tras un rechazo CAD exacto y un rescate de contornos agotado se pasa a la recuperación conservadora aislada, sin repetir ajustes incompatibles. Esto corrige el agotamiento de memoria observado en M3 PClip con límites de 4.500 y 5.500 MiB; la fila de interfaz y su diagnóstico registran el consumo de esta copia. No se amplía el límite del programa.
- Se exige coherencia CAD exacta además del control ordinario. Un resultado ya sometido a BOP en el trabajador sólo evita repetir ese mismo control cuando coincide el SHA-256 completo del STEP. El padre vuelve a abrir el archivo y repite geometría y coherencia exacta; cualquier cambio de bytes invalida esa prueba. No es una caché entre conversiones.

## Pruebas de esta copia

**213 pruebas automáticas aprobadas, cero fallos, errores u omisiones.** Incluyen negativos de objetos sueltos, autointerferencias, STEP ordinariamente válidos pero incoherentes en el control exacto, cuerpos pequeños independientes, soportes cónicos distintos, prueba BOP alterada y cancelación/arranque.

**21/21 conversiones de regresión aprobadas:** cuatro cubos, trece de las catorce históricas y cuatro adicionales de usuario. M3 PClip, Bancada, pinza, cubo y 6558 se ejecutaron desde la interfaz real con Playwright/Chromium: importar, convertir y exportar. Las otras dieciséis usaron el mismo motor completo por CLI. Pieza Nueva se ejecutó en una segunda cola, una vez terminadas la interfaz y sus contrastes, con las mismas fuentes, perfil y límites; se conserva su registro y la huella del STEP copiado. Cada STEP descargado coincide byte a byte con el validado por el servidor. Se hizo además una nueva lectura fría estricta de los resultados, exigiendo un único sólido positivo y coherencia CAD exacta.

**Embudo permanece aplazado por instrucción del propietario. No se declara 14/14.** Los SHA-256 de entradas y de las 126 fuentes congeladas se conservan. Los originales no se modifican.

Se contrastaron además los STEP realmente descargados de Bancada y pinza con el evaluador geométrico R7 y el control de frontera M1 inmutables. Ambos conservan todos los cilindros confirmados y pasan geometría, topología de material y tres discretizaciones sin intersecciones CGAL. El BOP obligatorio es el ejecutado por el motor R8; el contraste independiente no lo sustituye.

Se probó cancelar mediante Nuevo durante una conversión, negar la descarga del trabajo cancelado y convertir/exportar después una caja. Se comprobó la reapertura de la misma instancia y el rechazo de otra aplicación que ocupe el puerto. Los registros y capturas se incluyen en la auditoría.

### Medidas reales de regresión

Los tiempos pertenecen a un entorno Linux de referencia con dos CPU y trabajos de prueba concurrentes. No son una predicción del tiempo en Windows. «DATA igual R7» compara la sección de datos STEP omitiendo el encabezado; una diferencia requiere revisar los controles, no demuestra por sí sola una regresión.

| Pieza | Ruta real | Tiempo (s) | Caras STEP | Máx. mm | Caja mm | Volumen % | DATA igual R7 |
|---|---|---:|---:|---:|---:|---:|---|
| cubo-carrito | Visor | 142.6 | 1152 | 0 | 0 | 0 | no |
| cubo-carrito_giro_1 | CLI | 90.9 | 1838 | 0.0 | 0.0 | 0.0 | no |
| cubo-carrito_giro_2 | CLI | 116.8 | 1195 | 0.0 | 0.0 | 0.0 | no |
| cubo-carrito_giro_3 | CLI | 118.7 | 1853 | 0.0 | 0.0 | 0.0 | no |
| 1x1-lego-brick | CLI | 229.7 | 2672 | 0.0 | 0.0 | 0.0 | no |
| Bancada_Motor | Visor | 338.1 | 1896 | 0.00073 | 0.000561 | 0.003693 | no |
| Estefi | CLI | 319.7 | 1769 | 0.0 | 0.0 | 0.0 | no |
| Grapa | CLI | 144.6 | 622 | 0.000677 | 1e-06 | 0.01304 | no |
| LLanta_Trasera | CLI | 158.0 | 4195 | 0.0 | 0.0 | 0.0 | no |
| M3 PClip - 2mm | Visor | 118.2 | 1484 | 0 | 0 | 0 | no |
| Spoiler_arrière_Porsche_-_5 | CLI | 9.3 | 28 | 0.002827 | 5.1e-05 | 0.012459 | sí |
| Tirante | CLI | 431.4 | 13122 | 0.0 | 0.0 | 0.0 | no |
| chasis - Part 2 | CLI | 509.1 | 13803 | 0.006785 | 1e-05 | 0.000133 | sí |
| maneta | CLI | 204.5 | 9351 | 0.0 | 0.0 | 0.0 | no |
| pinza | Visor | 194.0 | 448 | 0.003787 | 0.000495 | 0.036855 | no |
| spur | CLI | 85.5 | 1405 | 0.004738 | 0.0 | 0.007408 | sí |
| conector | CLI | 543.9 | 19998 | 0.010826 | 0.0 | 0.002912 | sí |
| 6558_fixed | Visor | 556.0 | 8713 | 0.01636 | 0 | 0.000107 | sí |
| Dimensiones | CLI | 264.9 | 1100 | 5e-06 | 0.0 | 0.0 | sí |
| Con fallos pero si step | CLI | 349.1 | 2567 | 0.000592 | 0.0 | 0.0 | sí |
| Pieza_Nueva_Detenida | CLI | 966.4 | 8892 | 0.020334 | 0.0 | 3e-06 | sí |

### Representación comparada

| Pieza | Caras R7 | CAD exacto R7 | Caras R8 | Representación R8 |
|---|---:|---|---:|---|
| cubo-carrito | 255 | no | 1152 | Recuperación facetada |
| cubo-carrito_giro_1 | 239 | no | 1838 | Recuperación facetada |
| cubo-carrito_giro_2 | 324 | no | 1195 | Recuperación facetada |
| cubo-carrito_giro_3 | 272 | no | 1853 | Recuperación facetada |
| 1x1-lego-brick | 33 | no | 2672 | Recuperación facetada |
| Bancada_Motor | 89 | no | 1896 | CAD validado |
| Estefi | 228 | no | 1769 | Recuperación facetada |
| Grapa | 18 | no | 622 | CAD validado |
| LLanta_Trasera | 42 | no | 4195 | Recuperación facetada |
| M3 PClip - 2mm | 54 | no | 1484 | Recuperación facetada |
| Spoiler_arrière_Porsche_-_5 | 28 | sí | 28 | CAD validado |
| Tirante | 22 | no | 13122 | Recuperación facetada |
| chasis - Part 2 | 13803 | sí | 13803 | Recuperación facetada |
| maneta | 42 | no | 9351 | Recuperación facetada |
| pinza | 2144 | sí | 448 | CAD validado |
| spur | 1405 | sí | 1405 | CAD validado |
| conector | 19998 | sí | 19998 | Recuperación facetada |
| 6558_fixed | 8713 | sí | 8713 | Recuperación facetada |
| Dimensiones | 1100 | sí | 1100 | Recuperación facetada |
| Con fallos pero si step | 2567 | sí | 2567 | Recuperación facetada |
| Pieza_Nueva_Detenida | 8892 | sí | 8892 | Recuperación facetada |

## Entradas recientes adicionales

- **V_legoBrick4x2**: aprobado, 156.8 s. STEP de recuperación · curvas facetadas · Precisión alcanzada · máx. medido 0 mm · 1692 caras
- **Soporte_movil_2**: aprobado, 23.4 s. STEP CAD generado · Precisión alcanzada · máx. medido 0,018513 mm · 493 caras
- **Technic_PEGS_Cross_x6_A**: aprobado, 78.3 s. STEP de recuperación · curvas facetadas · Precisión alcanzada · máx. medido 0,00005 mm · 2044 caras

## Representación y equivalencia de las fuentes

La regresión acredita conversión, validez y geometría. **En algunas piezas aumentan las caras o se usa recuperación facetada frente al STEP antiguo**, porque el nuevo control rechaza ajustes que R7 aceptaba sin coherencia CAD exacta. No se declara mejor editabilidad para todas las piezas ni una reducción general de caras. La interfaz identifica la recuperación facetada.

La aplicación y las pruebas de esta entrega se validan sobre una copia congelada de 126 archivos. Sus huellas se comprueban en la batería y al extraer los ZIP. Los ensayos anteriores se conservan separados; no se suman como conversiones aprobadas de esta copia.

La recuperación de referencias con costuras reproduce las correcciones certificadas existentes o la lectura heredada `process=True`. Esta última exige conservar cada faceta y limitar el cambio de coordenadas al redondeo original de Trimesh, 1e-8 mm; también comprueba cierre, orientación y contactos entre abanicos. No autoriza tapar un agujero. En el Lego histórico el desplazamiento medido fue de 3,524e-16 mm.

La discrepancia dimensional imprimible y la coherencia interna de un B-Rep son controles distintos. Una separación de unas milésimas puede quedar por debajo de la precisión de la impresora y aun así incumplir la correspondencia de curvas y superficies del STEP. R8 exige ambos controles, con los límites geométricos originales.

## Tolerancias y alcance

Los archivos de perfiles, holgura geométrica, validación densa y política de tiempos permanecen byte a byte iguales a R7. La auditoría AST de constantes confirma: caja 0,020 mm; volumen 0,5 %; p95 base 0,020 mm, con las condiciones originales; máximo observado 0,060 mm. El perfil opcional Impresión 0,08 mm sigue existiendo y no se selecciona automáticamente. Todas las pruebas de esta entrega usaron Precisión.

Se amplía únicamente el presupuesto acotado del trabajador de reconstrucción según triángulos, de 300 a 900 s. Se conservan los límites de recursos de la aplicación. La comprobación BOP puede tardar minutos; se añaden mensajes de fase y se evita duplicarla sobre los mismos bytes validados. No se promete una aceleración general del conversor.

## Uso y pendientes

Extraer el ZIP completo en una carpeta nueva y abrir **Iniciar.bat** en la raíz. Contiene la carpeta **Visor_experimental_fuentes** y todos sus módulos. Puede reutilizar, en lectura, el entorno de R7 mediante el selector de carpeta. Si no hay entorno compatible, ejecutar **Instalar_Entorno.bat** con Python 3.12 de 64 bits. R8 se abre en **http://127.0.0.1:8772** y muestra su versión; R7 puede permanecer en 8771. La identidad de instancia evita abrir otra copia por error.

**Windows nativo no se ha ejecutado en este entorno Linux.** Se han comprobado lanzadores, rutas con espacios, selección de entorno, saltos CRLF y disponibilidad de ruedas Windows CPython 3.12 de los componentes CAD críticos. Esto no sustituye tu prueba real en Windows. **Onshape tampoco se ha ejecutado**: las líneas que observabas en 6558 requieren nueva comprobación visual allí; no se declara corregido ese defecto por el solo hecho de pasar los controles locales. La K1C no se ha probado.

No se garantiza reparación de STL arbitrarios ni recuperación analítica de cualquier curva. Los STEP de recuperación facetada se identifican en la interfaz. El modo de superficies sigue requiriendo validación y puede ceder a una recuperación conservadora o rechazar la pieza. Las pruebas negativas defectuosas y los intentos de desarrollo descartados se conservan separados de los resultados aprobados.

La auditoría separada incluye materiales, referencias R7, fuentes del evaluador, XML de pruebas, protocolo portable, registros, huellas y herramientas de reproducción. Los resultados STEP se entregan en un ZIP separado para que el programa sea ligero de descargar. `archivos_modificados` y el parche registran los cambios acumulados desde la R7 entregada.
