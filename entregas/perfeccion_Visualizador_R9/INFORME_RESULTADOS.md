# Visor STL → STEP · R9 experimental completa

La R8 conseguía convertir muchas piezas recurriendo a caras planas en superficies cilíndricas. Esta copia experimental corrige encuentros y costuras de cilindros y añade reconstrucción local después de una recuperación facetada. El coordinador del motor (`motor_v2.py`), los perfiles, los límites globales y los validadores geométricos conservan sus archivos originales. R7, R8 y la web de main permanecen separados.

## Mejora demostrada en el programa completo

- **Llanta trasera:** de **4.195 caras planas y ningún cilindro** a **53 caras**, de las que 30 son cilíndricas. Se conservan los **15 cilindros confirmados en el STL**. Una superficie física puede estar dividida en dos caras para colocar su costura; treinta caras cilíndricas no significan treinta cilindros físicos. Máximo geométrico observado: **0.002138 mm**.
- **Lego 4×2:** de **1.692 caras planas y ningún cilindro** a **1149 caras**, con **12 caras cilíndricas**. El contraste independiente acredita 12 de los 21 soportes cilíndricos confirmados; los restantes siguen sin reconstrucción analítica confirmada. El inventario independiente incluye también detalles cilíndricos parciales: se distingue de las 19 paredes completas elegibles para la reconstrucción local. Se conservan **las ocho cavidades**. Máximo observado: **0.005932 mm**. Es un STEP mixto; las otras zonas conservan facetas y se indica en la interfaz.

Ambos se han importado, convertido y descargado desde la interfaz real con Chromium. Los archivos descargados coinciden byte a byte con los validados por el servidor. El contraste independiente se ejecuta sobre esos mismos archivos, identificados por SHA-256, usando la geometría R7 y el control de frontera M1 inmutables.

## Cambios del motor

1. Se distingue una costura entre mitades del **mismo cilindro** de una intersección entre cilindros diferentes. No se fusionan radios ni ejes próximos que representen superficies distintas. Se mantiene primero la reconstrucción anterior; las medias cañas adicionales sólo se ensayan después de un rechazo real.
2. Se verifica también la proyección geométrica dentro del **recorte UV real** de la cara. Esto evita un falso rechazo de OCC observado en un borde circular. No basta con estar cerca del cilindro infinito: los tests de cilindros truncados y ventanas taladradas deben seguir rechazándose.
3. En una recuperación facetada ya válida se pueden reemplazar paredes completas con dos anillos planos, circulares y coaxiales. Se comprueba el interior de las facetas, no sólo sus vértices; la cota radial local es **0,008 mm**. Se rechazan polígonos poco resueltos, ranuras, conicidad real y bandas que invadan una pared vecina. Los booleanos son no destructivos y usan fuzzy **0**.
4. La mejora local corre aislada y conserva una copia del STEP previo. Exige una reducción de caras y vuelve a validar geometría, cilindros, material y tres mallados finos. Si falla, se agota su tiempo o faltan pruebas, se conserva la recuperación anterior. La publicación de la candidata se hace mediante sustitución atómica, después de verificar sus huellas.

Se ensayó una compactación de la llanta a 38 caras. Aunque pasaba los controles generales de geometría y CAD exacto, falló el control topológico adicional y **se descartó**. No se ha rebajado ese control para aprobarla.

## Pruebas reales de esta copia congelada

**233 pruebas automáticas, cero fallos, errores u omisiones.** Incluyen negativos de costuras, radios distintos, recortes con ventanas, polígonos, conos, ranuras, paredes delgadas, preservación de una cavidad, inmutabilidad de la base, tiempo agotado y reutilización del entorno R8 sin modificarlo.

**21/21 conversiones principales aprobadas:** cubo-carrito y tres giros, trece de las catorce históricas y cuatro casos adicionales del protocolo. Se ejecutaron seis por interfaz y quince por CLI. Además aprobaron Lego4×2, soporte móvil y Technic por la interfaz: **24 conversiones distintas**, nueve de ellas mediante el flujo real del navegador. Cada STEP se volvió a abrir en frío exigiendo un único sólido positivo y coherencia CAD exacta. La batería incorpora BOP; los contrastes independientes no lo sustituyen.

**Embudo sigue aplazado por instrucción del propietario. No se declara 14/14.** Octogon y Barrera_Lego sólo se recibieron como STEP, por lo que no se han vuelto a convertir en esta entrega. Su inspección de R8 se conserva separada.

El contraste independiente de llanta y Lego comprueba geometría con R7, coherencia exacta, topología de material y tres discretizaciones finas cerradas, orientadas y sin intersecciones CGAL. En Lego se exige conservar las ocho cavidades; el inventario reconoce expresamente las paredes que siguen facetadas.

Se probó cancelar con Nuevo, bloquear la descarga cancelada y convertir/exportar después una caja. Las huellas de las 130 fuentes se verifican durante las pruebas y al extraer el paquete. Los originales STL no se modifican.

## Comparación completa con R8

Los tiempos son medidas reales en Linux, con dos CPU de cuota y colas de prueba concurrentes. No son una predicción de velocidad en Windows ni una comparación de rendimiento controlada con R8. Buscar una mejor reconstrucción puede añadir tiempo a piezas que finalmente conservan facetas. «DATA igual R8» compara la sección geométrica STEP omitiendo su encabezado; una diferencia se juzga mediante los controles, no por el texto del archivo.

| Pieza | Ruta | s | Caras R8 → R9 | Caras cilíndricas R8 → R9 | Máx. observado mm | Error volumen % | DATA igual R8 |
|---|---|---:|---:|---:|---:|---:|---|
| cubo-carrito | Visor | 97.5 | 1152 → 1152 | 0 → 0 | 0 | 0 | sí |
| cubo-carrito_giro_1 | CLI | 97.7 | 1838 → 1838 | 0 → 0 | 0.0 | 0.0 | sí |
| cubo-carrito_giro_2 | CLI | 71.1 | 1195 → 1195 | 0 → 0 | 0.0 | 0.0 | sí |
| cubo-carrito_giro_3 | CLI | 100.3 | 1853 → 1853 | 0 → 0 | 0.0 | 0.0 | sí |
| 1x1-lego-brick | CLI | 136.5 | 2672 → 2672 | 0 → 0 | 0.0 | 0.0 | sí |
| Bancada_Motor | Visor | 441.1 | 1896 → 1896 | 15 → 15 | 0.00073 | 0.003693 | sí |
| Estefi | CLI | 389.9 | 1769 → 1769 | 0 → 0 | 0.0 | 0.0 | sí |
| Grapa | CLI | 174.0 | 622 → 622 | 2 → 2 | 0.000677 | 0.01304 | sí |
| LLanta_Trasera | Visor | 64.3 | 4195 → 53 | 0 → 30 | 0.002138 | 0.032699 | no |
| M3 PClip - 2mm | Visor | 121.3 | 1484 → 1484 | 0 → 0 | 0 | 0 | sí |
| Spoiler_arrière_Porsche_-_5 | CLI | 6.8 | 28 → 28 | 2 → 2 | 0.002827 | 0.012459 | sí |
| Tirante | CLI | 655.1 | 13122 → 13122 | 0 → 0 | 0.0 | 0.0 | sí |
| chasis - Part 2 | CLI | 420.3 | 13803 → 13803 | 0 → 0 | 0.006785 | 0.000133 | sí |
| maneta | CLI | 186.8 | 9351 → 9351 | 0 → 0 | 0.0 | 0.0 | sí |
| pinza | Visor | 168.7 | 448 → 448 | 11 → 11 | 0.003787 | 0.036855 | sí |
| spur | CLI | 114.0 | 1405 → 1405 | 34 → 34 | 0.004738 | 0.007408 | sí |
| conector | CLI | 527.7 | 19998 → 19998 | 0 → 0 | 0.010826 | 0.002912 | sí |
| 6558_fixed | Visor | 498.3 | 8713 → 8713 | 0 → 0 | 0.01636 | 0.000107 | sí |
| Dimensiones | CLI | 178.1 | 1100 → 1100 | 0 → 0 | 5e-06 | 0.0 | sí |
| Con fallos pero si step | CLI | 333.7 | 2567 → 2567 | 0 → 0 | 0.000592 | 0.0 | sí |
| Pieza_Nueva_Detenida | CLI | 817.7 | 8892 → 8892 | 0 → 0 | 0.020334 | 3e-06 | sí |
| V_legoBrick4x2 | Visor | 213.5 | 1692 → 1149 | 0 → 12 | 0.005932 | 0.077806 | no |
| Soporte_movil_2 | Visor | 45.5 | 493 → 493 | 0 → 0 | 0.018513 | 0.000482 | sí |
| Technic_PEGS_Cross_x6_A | Visor | 77.7 | 2044 → 2044 | 0 → 0 | 5e-05 | 0 | sí |

## Precisión y límites que permanecen

El coordinador motor_v2.py, los perfiles, la política global de tiempo y memoria, la normalización de referencias y los validadores geométricos/topológicos permanecen byte a byte iguales a R8. Precisión mantiene caja 0,020 mm, volumen 0,5 %, p95 base 0,020 mm con sus condiciones originales, y máximo base 0,060 mm. La cota local de reconstrucción es adicional; no aumenta esos límites. Los máximos de la tabla son observados y no una garantía absoluta para cualquier punto de cualquier STL.

El perfil Impresión 3D sigue permitiendo otro presupuesto de error, pero no es un selector de suavizado ni obliga a recuperar más cilindros. Todas estas pruebas usaron Automático (precisión). No se cambia automáticamente a 0,08 para obtener una conversión.

Algunas piezas conservan superficies facetadas. No se afirma que todas recuperen cilindros, que todas tengan menos caras, ni que se haya recuperado el historial paramétrico original. La mezcla de caras analíticas y facetas se identifica en la interfaz. La geometría CAD exacta y una menor triangulación son controles distintos; superar uno no demuestra el otro.

## Uso y pruebas pendientes

Extrae el ZIP completo en una carpeta nueva y abre **Iniciar.bat**. Incluye **Visor_experimental_fuentes** y los lanzadores. Si aparece el selector, elige tu carpeta R7 o R8 para reutilizar su entorno sin modificarla. Si necesitas uno nuevo, usa Instalar_Entorno.bat con Python 3.12 de 64 bits. R9 abre **http://127.0.0.1:8775**; R8 puede seguir en 8772 y R7 en 8771. El encabezado debe mostrar **R9 experimental**.

**Windows nativo no se ha ejecutado en este entorno Linux.** Se comprobaron lanzadores, comillas, CRLF, rutas con espacios, selección del entorno y la versión servida. Las dependencias no cambian respecto a R8; la comprobación de disponibilidad de sus ruedas Windows se conserva como evidencia, y no equivale a probar Windows. **Onshape y la K1C tampoco se han probado.** El defecto visual de 6558 necesita comprobación allí; no se da por resuelto por convertir correctamente.

La entrega incluye fuentes completas y modificadas, parche desde R8, manifiestos, registros, STEP realmente obtenidos, capturas de la interfaz y materiales para repetir la batería. Las capturas del Visor muestran el STL de entrada; la calidad del STEP se acredita por la inspección CAD de los archivos exportados. Los resultados descartados se mantienen separados de los aprobados.
