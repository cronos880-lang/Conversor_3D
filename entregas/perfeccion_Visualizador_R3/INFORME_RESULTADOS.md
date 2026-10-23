# R3 — mejora implementada, validación global pendiente

Cierre de evidencia: 2026-10-23T22:49:04.261485+02:00 (Europe/Madrid). Trabajo de esta fase iniciado a las
21:52 del 23/10/2026. Entorno Linux, Python 3.12. **No sustituir R2 con esta copia
como si fuera una actualización estable.** Es una entrega del progreso solicitado.

## Qué cambia en el motor y el flujo

- Perfil Precisión predeterminado con límites anteriores; perfil opcional
  Impresión con caja 0,040 mm, p95 0,040 mm y máximo superficial 0,080 mm.
  El máximo de impresión incluye el error de preparación; no se le añade margen.
  Volumen 0,5 % y controles de reparación e integridad se conservan. No se escala
  el STL para cumplir un perfil. Los 0,08 mm no certifican la precisión de la K1C.
- Consultas STL→B-Rep reutilizan los índices del mismo shell de OpenCascade.
  Se midieron 200 puntos con ambos métodos: 1,611 s frente a 0,350 s y resultados
  iguales dentro de 10^-10 mm. Es una microprueba, no una promesa de acelerar toda
  conversión por ese factor ni una medición del ordenador del propietario.
- Las recuperaciones CAD repiten el control avanzado de interferencias; se cierra
  una vía que aceptaba un candidato alternativo sin ese control. El primer STL
  nuevo proporciona un caso reproducible: 32 avisos que antes no se comprobaban.
- Inspección densa en todos los candidatos que superan la medición histórica.
  Incluye interiores de triángulos STL y caras/aristas CAD. Antes de rechazar por
  un punto del teselado CAD, ese punto se contrasta y proyecta al B-Rep exacto.
  Esto evita atribuir al STEP un triángulo de medición que atraviesa un recorte.
  El STEP no se altera durante esa operación. El caso real pinza tenía muestras
  teseladas hasta 0,216 mm fuera del B-Rep; su contraste devuelve 0,0397 mm, pero
  las interferencias topológicas de su recuperación siguen siendo un problema.
- Diagnóstico con valor, umbral y unidad; el mensaje acusa solo los criterios
  incumplidos. Una cota de 0,0075 mm que pasa no figura como motivo de rechazo
  si lo que falla es el volumen. Los registros conservan todos los criterios.
- Tiempo inicial por triángulos, común a ambas API del servidor: 7 min hasta
  5.000 triángulos; 10 min hasta 20.000; 15 min hasta 100.000; 20 min por encima.
  Si el proceso mantiene actividad CPU, puede ampliarse hasta el doble, con
  máximo absoluto de 40 min. La memoria y la cancelación del árbol se vigilan.
  Esto concede margen a equipos lentos; no garantiza resolver una geometría mala.
- El estado publica actividad CPU y plazo; el 78 % sigue indicando una fase y
  no una estimación lineal del tiempo. Nuevo sigue cancelando los descendientes.
- Tras dos intentos rápidos fallidos se prueba el motor habitual. Las variantes
  restantes quedan para el rescate, y los intentos idénticos ya fallidos no se
  repiten con la misma malla, parámetros y perfil. En 6558 se omitieron dos
  reconstrucciones repetidas; el ensayo completo terminó con un rechazo real.

El núcleo `motor_superficies` conserva exactamente el código R2. Se modifican
la coordinación, comprobación, diagnóstico y flujo de perfiles, sin reemplazar
el motor completo. Los 47 archivos de la R1 original conservan su contenido.

## Cuatro piezas nuevas: resultado de pruebas completas en Precisión

| Archivo | Resultado real | Segundos | Límite de ensayo s |
|---|---|---:|---:|
| Con fallos pero si step.stl | Rechazada: interferencias en los candidatos | 248.883 | 600 |
| Dimensiones.stl | Rechazada: máximo inicial 0,145013 mm; rescates no aprobados | 77.367 | 600 |
| Pieza ambigua.stl | Rechazada: reconstrucciones no superan geometría/integridad | 508.248 | 900 |
| 6558_fixed.stl | Rechazada: reconstrucciones no superan geometría/integridad | 587.323 | 900 |

Los cuatro procesos finalizaron con un rechazo del motor y código 2; no fueron
interrumpidos por los límites de estos ensayos. No se cuentan como conversiones
resueltas. Dar más tiempo no produjo un STEP aprobado en estas ejecuciones.
El ensayo intermedio de 6558 de 391,925 s fue cancelado deliberadamente para
ensayar el nuevo orden; no se usa como rechazo geométrico ni como resultado final.

Dimensiones no falla por 0,0075 mm: el primer candidato tiene un máximo de
0,145013 mm. Pieza ambigua conserva la reparación de entrada verificada, pero
sigue sin un B-Rep aceptable. No se ha repetido la batería completa de las cuatro
en Impresión ni se afirma que seleccionar ese perfil las resuelva.

## Regresión y cubo-carrito

**10 de 12 históricos aceptados**, con las mismas huellas de STL y los mismos
indicadores históricos comparados. La nueva comprobación descubre dos defectos
que la muestra anterior no detectaba o no controlaba en la recuperación:

- chasis - Part 2: máximo denso 0,071166 mm frente a 0,062873 mm; este límite
  incluye sus 0,002873 mm de preparación medida. El mismo STEP R2 se revalida en
  Impresión y pasa ese perfil sin modificar su geometría. Esto es revalidación
  de un archivo existente, no una nueva conversión ni un certificado de cero
  interferencias avanzadas. Se conserva como referencia claramente etiquetada.
- pinza: la recuperación aceptada antes conserva 173 avisos avanzados OCC.
  El nuevo rescate no puede aceptarla sin superar ese control. Resolver el
  teselado de medición evita un falso rechazo superficial, pero no esos avisos.

La R3 no supera todavía la puerta de no regresión. Los 10 aceptados mantienen
sus métricas; no se presenta este resultado como 12/12 ni como 14/14. El embudo
sigue aplazado por indicación del propietario y el conector no se ha repetido.
Los avisos avanzados no equivalen por sí solos a una medida de error dimensional;
los candidatos se tratan conforme a su ruta y el diagnóstico conserva las causas.

Los cuatro cubo-carrito vuelven a convertir y sus métricas históricas y secciones
DATA STEP coinciden exactamente con las de la referencia independientemente
verificada, incluyendo volumen adaptativo y el canal/paredes. Se certifican
huellas y datos; el verificador independiente no se repitió sobre geometría
binariamente idéntica. Ver `cubo_precision/identidad_geometria_previamente_verificada.json`.

| Cubo-carrito | Segundos | Aprobado |
|---|---:|---|
| cubo-carrito.stl | 129.088 | Sí |
| cubo-carrito_giro_1.stl | 97.481 | Sí |
| cubo-carrito_giro_2.stl | 47.966 | Sí |
| cubo-carrito_giro_3.stl | 239.208 | Sí |

Los tiempos incluyen carga concurrente del entorno. No son una comparación
controlada de rendimiento ni predicen el tiempo en el ordenador del propietario.

## Pruebas y límites de la evidencia

La ejecución de cierre da **57 tests aprobados, cero fallos, cero omitidos**.
Incluye los STL reales y fixtures defectuosos, perfiles, preservación de aberturas,
identidad de distancias exactas, rechazo de rescates, memoria, tiempo y cancelación.
Hubo tres avisos NumPy esperados de mallas degeneradas negativas. Se repitieron
además tres comprobaciones al ajustar la actividad CPU y se midió un proceso
real que comunicó actividad y terminó normalmente.

Chromium Linux completó importación de Grapa, elección de Impresión, conversión,
descarga, cambio de perfil e invalidación del STEP anterior, y Nuevo. El STEP
realmente descargado se reimportó como un sólido válido de 18 caras y sin
interferencias OCC. Hay captura, registro del servidor y huellas. Un ensayo de
navegador con plazo de 60 s resultó corto bajo carga; la prueba final permitió
120 s y completó el flujo. Es un plazo del test, no el del motor.

La prueba de perfiles acepta un STEP analítico de calibración desplazado 0,03 mm
solo en Impresión; no se presenta como una conversión completa de ese STL de
calibración. La conversión completa de impresión comprobada es la de Grapa.
Las medidas son muestreadas, no una cota Hausdorff global. No se ha probado
Windows nativo, Onshape Move face ni impresión física en K1C. Estos ensayos no
validan la conversión WebAssembly de GitHub Pages.

## Entrega y siguiente trabajo

El ZIP contiene la aplicación Python completa, código modificado, fuentes STL,
pruebas, referencias y resultados reales. Los STEP de regresiones NO ACEPTADAS
son fixtures defectuosos; no se ofrecen como piezas corregidas. El código suelto
y el patch están junto al ZIP. La rama principal y las entregas R2 se conservan.

Para experimentar, extraer en carpeta nueva, ejecutar Instalar_Entorno.bat una
vez y luego Iniciar.bat. Puerto R3 8767, separado de R2 8766. Leer primero este
informe y ESTADO_VALIDACION.md. La instalación nativa Windows no está validada.

Falta corregir la construcción de contornos/intersecciones de las cuatro piezas,
resolver las dos regresiones de precisión y repetir las puertas antes de una
actualización estable. El marco de reparación, perfiles, diagnósticos y procesos
queda implementado y ampliable. El entorno perdió conexión temporalmente, se
recuperó con los archivos conservados y el avance se guardó en GitHub antes del
empaquetado final; los resultados pendientes no se sustituyeron por éxito.
