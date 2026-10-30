# R12 experimental — resultados reales

La mejora nueva demostrada es **Technic: 2.044 → 845 caras (58.66% menos)**. Se genera desde el STL original, sin usar un STEP precalculado. Conserva un sólido CAD válido y supera los controles contra el original. **Bancada y maneta mantienen los resultados de R11**: los intentos nuevos sobre esas piezas no superaron la puerta de calidad. Tampoco se declara una mejora nueva de soporte muelle o conector.

## Qué cambia

El Visor obtiene primero el resultado completo R11. Una fase aislada intenta mejorar los contactos ya reparados de entradas moderadas: hasta 6.000 triángulos, al menos 80 caras, fase R11 de hasta 240 s y sin mejora medida R11 ya aplicada. Son criterios generales de topología y recursos; no se seleccionan piezas por nombre ni por hash. Si la propuesta falla, se conserva el STEP R11. No se reemplaza el motor general.

El núcleo nuevo elimina microaristas por debajo de la resolución CAD en una copia certificada, escoge generatrices coherentes por contorno, recorta curvas sin desplazar sus extremos y construye campos locales conservando la frontera. No cambia el STL original. Conserva los cilindros respaldados por la fuente; en este Technic no se han certificado cilindros nuevos. El resultado todavía contiene numerosos planos y no equivale al diseño paramétrico original.

## Prueba real de Technic en el Visor

- Conversión y descarga desde Chromium: **936.6 s**, perfil predeterminado Precisión, sin errores JavaScript. Descarga idéntica al archivo validado del servidor.
- Un sólido, B-Rep exacto válido al releer el STEP en frío; sin interferencias OCC detectadas y sin objetos sueltos. Tolerancia máxima de aristas: **1e-07 mm**.
- Diferencia de caja: **5.9e-05 mm**. Error de volumen: **0.000392%**.
- Tres mallados finos contra el STL original, deflexiones 0,00025 / 0,0005 / 0,001 mm: cerrados, orientados y **0 intersecciones CGAL** cada uno. Máxima separación observada: **0.00120182446 mm**.
- Material contra el original: **3074 puntos**, **0 discrepancias**, fuera de la banda de 0,002 mm junto a la superficie. Son comprobaciones por muestreo, no una garantía matemática global de Hausdorff.
- Las evidencias de reparación y calidad se conservan y descargan desde el diagnóstico. Los hashes vinculan original, preparado, trabajador y STEP final.

## Regresión completa de esta entrega

**18 conversiones aprobadas**: 13 históricas, cubo-carrito y tres giros, más Technic. **17 bloques DATA idénticos a R11**: la geometría CAD de esas salidas se conserva exactamente. El único bloque distinto es la mejora validada de Technic. Se han usado los originales; sus hashes se comprueban antes y después. Embudo continúa aplazado y **no se declara 14/14**.

| Pieza | Caras | Geometría | Segundos |
|---|---:|---|---:|
| 1x1-lego-brick | 2672 | idéntica a R11 | 104.1 |
| Bancada_Motor | 239 | idéntica a R11 | 558.3 |
| Estefi | 1769 | idéntica a R11 | 292.8 |
| Grapa | 20 | idéntica a R11 | 281.5 |
| LLanta_Trasera | 53 | idéntica a R11 | 49.4 |
| M3 PClip - 2mm | 1484 | idéntica a R11 | 181.9 |
| Spoiler_arrière_Porsche_-_5 | 28 | idéntica a R11 | 5.5 |
| Technic_PEGS_Cross_x6_A | 845 | mejora validada | 936.6 |
| Tirante | 22 | idéntica a R11 | 625.6 |
| chasis - Part 2 | 13803 | idéntica a R11 | 593.6 |
| conector | 19998 | idéntica a R11 | 463.5 |
| cubo-carrito | 1152 | idéntica a R11 | 101.2 |
| cubo-carrito_giro_1 | 1838 | idéntica a R11 | 79.5 |
| cubo-carrito_giro_2 | 1195 | idéntica a R11 | 70.4 |
| cubo-carrito_giro_3 | 1853 | idéntica a R11 | 96.0 |
| maneta | 36 | idéntica a R11 | 316.4 |
| pinza | 448 | idéntica a R11 | 139.3 |
| spur | 1405 | idéntica a R11 | 96.4 |

Los tiempos son de este entorno de referencia Linux, con dos CPU disponibles, 8 GiB de memoria y tareas simultáneas; no son una comparación de rendimiento entre ordenadores. La nueva verificación encarece Technic respecto a R11. Esta entrega mejora calidad, no velocidad.

## Tolerancias y conservación

Los evaluadores de precisión, reparación y distancia de R11 no cambian: caja 0,02 mm, P95 0,02 mm, máximo muestreado 0,06 mm y error de volumen 0,5% en Precisión. La limpieza numérica de la copia requiere una variación geométrica de hasta 0,0000001 mm y sus propios controles topológicos. No se sustituye Precisión por 0,08 mm automáticamente.

Se preserva la reconstrucción medida R11 de bancada, maneta y Grapa. La ampliación del presupuesto sólo afecta al tiempo concedido a procesos con actividad CPU: máximo de 1.800 a 2.400 s según el caso, dentro del límite absoluto anterior de 2.400 s. La fase nueva también tiene límites propios de tiempo y memoria. Esto no amplía ningún límite geométrico.

## Pruebas del programa y del paquete

- **291 pruebas del Visor**, **380 del núcleo experimental**, todas aprobadas. Son baterías parcialmente compartidas: no se suman como pruebas únicas. Los registros conservan tres avisos en cada batería completa, sin fallos ni omisiones.
- Cancelación real durante la nueva mejora: estado cancelado, descarga HTTP 404 y siguiente conversión correcta.
- ZIP extraído en una ruta con espacios: **63 pruebas aprobadas**, arranque y conversión/descarga real de una caja. Lectura CAD independiente: seis caras, volumen y caja idénticos al STL.
- Los 150 archivos del manifiesto R11 congelado permanecen intactos. El programa entregado conserva los mismos archivos ejecutados, salvo la documentación de uso actualizada. Los manifiestos SHA-256 y el inventario de cambios permiten comprobarlo.

## Qué falta

**No se ha ejecutado Windows nativo**, ni importación en Onshape, ni impresión en la K1C. La validación real del motor y del navegador se realizó en Linux; no demuestra por sí sola que Onshape acepte la importación. Tampoco se han resuelto todos los STL defectuosos ni todas las líneas interiores de la bancada. Los intentos rechazados se documentan como investigación y no se activan sobre esas piezas.

## Cómo probarla

Descarga `perfeccion_Visualizador_R12_EXPERIMENTAL_COMPLETA.zip`, extrae todo en una carpeta nueva y abre **Iniciar.bat**. Dentro está **Visor_experimental_fuentes**. Necesita Python 3.12 x64; puede reutilizar un entorno compatible de R7 a R11. Comprueba el encabezado **R12 experimental** y mantén **Automático (precisión)**. Conserva R11 para comparar. El ZIP de comparación contiene Technic R11, R12, el STL original y las evidencias; la auditoría contiene las entradas y herramientas para repetir las pruebas.
