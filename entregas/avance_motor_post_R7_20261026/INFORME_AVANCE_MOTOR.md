# Avance del motor posterior a R7 — 2026-10-26T15:07:04.858066+00:00

**Estado: copia de desarrollo, sin nueva versión publicada.** Este informe se actualiza desde los JSON; una prueba pendiente o interrumpida no se cuenta como aprobada. La entrega queda condicionada a la regresión y a conservar la utilidad de los CAD anteriores.

## Mejoras implementadas

Se añaden tres tratamientos generales, sin seleccionar nombres ni huellas de piezas. El STL original se conserva como referencia final. El motor analítico existente mantiene prioridad.

1. Cavidades cerradas: distinguir un exterior positivo y envolventes negativas interiores de una orientación errónea. Se exigen superficies cerradas, enlaces de vértices regulares, cero contactos/intersecciones CGAL, contención y cavidades disjuntas. Se conservan coordenadas, caras y orientación.
2. Costuras en T: subdividir una arista larga cuando su nodo intermedio se encuentra a un máximo de 0,00001 mm. Se proyecta ese nodo, con cota baricéntrica del movimiento; no se añade una tapa. Los agujeros reales siguen rechazados. Se serializan dobles con 17 cifras significativas y se verifica su lectura.
3. Caras redundantes: retirar caras de área exactamente cero y redundancias coincidentes verificadas. Los pares opuestos aportan una cadena orientada nula al campo de material; sus vértices deben pertenecer a la frontera retenida. No se descartan cuerpos ni caras válidas por ser pequeños. Las láminas internas retiradas pueden distar de la frontera; el control superficial final sigue comparando con el STL bruto original.

La recuperación numérica reproduce por sí misma el certificado de saneamiento desde el original: un archivo preparado cerrado no basta para justificar el cierre. La API guarda el STL saneado sólo cuando su huella coincide con el certificado aprobado.

Además se comprueba el STEP completo: exactamente un sólido válido, sin aristas o caras sueltas que queden ocultas al seleccionar `.solids()`. El control OCC de interferencias se ejecuta tras una lectura fría, antes de teselar. Esta puerta detecta CAD que parecían superar el control después de crear una caché de triangulación.

## Resultados de las nuevas piezas

| STL | R7 de referencia | Candidato | Caras STEP | Máximo independiente mm | p95 independiente mm | Tiempo motor s |
|---|---|---|---:|---:|---:|---:|
| V_legoBrick4x2.stl | Rechazada | Aprobada | 477 | 0.01836 | 0.0055723 | 41.2 |
| Soporte_movil_2.stl | Rechazada | Aprobada | 493 | 0.0233872 | 4.1628e-06 | 22.032 |
| Soportes_estante_bobinas_v0.stl | Aprobada | Aprobada | 131 | 8.58407e-12 | 4.51672e-12 | 34.058 |
| Technic_PEGS_Cross_x6_A.stl | Rechazada | Aprobada | 2044 | 0.0267531 | 8.44125e-12 | 51.671 |

Los cuatro STEP superan relectura, control OCC en frío, inspección de parametrización, teselación independiente cerrada y orientada, enlaces de vértices, Euler y cero intersecciones CGAL. El Lego conserva sus ocho cavidades y nueve envolventes. PEGS es recuperación facetada, sin cilindros reconstruidos ni historial paramétrico. Los dos archivos PEGS recibidos son idénticos y cuentan como una pieza.

PEGS incluye además 5.040 muestras dirigidas sobre las diez caras auxiliares retiradas. Este control visita sus interiores incluso cuando tienen área nula y el muestreo por área no los seleccionaría. El máximo observado combinado es 0,026753 mm, en vez de los 0,000050 mm del muestreo ordinario. Ambos registros se conservan. El p95 de la tabla corresponde al muestreo ordinario; los percentiles dirigidos están separados en `verificacion_auxiliares_pegs.json`. No se afirma que retirar una cadena orientada nula conserve su soporte superficial a diez nanómetros. Una cobertura adaptativa mediante distancia al centro más radio también recorre todo el soporte de cada cara retirada, con cotas inferiores a 0,060 mm hacia la frontera teselada independiente. Esa cota se refiere a la teselación, no se presenta como una cota global exacta del B-Rep.

El máximo independiente usa vértices, centros de triángulos y muestras de área del STL original y del CAD teselado a 0,00025 mm / 0,04 rad, más el contraste dirigido indicado para PEGS. Es una medición muestreada, no una cota Hausdorff global. El evaluador usa utilidades R7 congeladas y no llama a `_calidad`; tanto el motor como el lector CAD emplean OpenCascade. CGAL aporta un control geométrico distinto sobre las mallas.

## Navegador real

| Pieza | Flujo completo y descarga | DATA STEP igual al verificado | Tiempo s |
|---|---|---|---:|
| lego | True | True | 151.346 |
| soporte | True | True | 101.357 |
| pegs | True | True | 117.984 |

Chromium Linux con renderizado por software: carga, modo «Automático (precisión)», conversión al 100 %, descarga y captura. No se selecciona 0,08 mm. Se verifica la identidad de DATA con los STEP contrastados por separado y, cuando procede, la descarga del STL reparado con su certificado SHA256. Las capturas muestran la interfaz y su vista STL; no equivalen a renderizar el STEP en Onshape. El encabezado R7 se conserva en esta copia de desarrollo porque no se ha preparado una nueva versión.

## Regresión histórica y cubo-carrito

Conversiones terminadas: **21/21**; aprobadas por el motor: **21**. El programa no se da por terminado por arrancar.

| Caso | Grupo | Motor | DATA igual a R7 | Caras STEP | Tiempo s |
|---|---|---|---|---:|---:|
| cubo-carrito | cubo4 | True | True | 255 | 78.743 |
| cubo-carrito_giro_1 | cubo4 | True | True | 239 | 118.249 |
| cubo-carrito_giro_2 | cubo4 | True | True | 324 | 67.465 |
| cubo-carrito_giro_3 | cubo4 | True | True | 272 | 200.596 |
| 1x1-lego-brick | historica12 | True | True | 33 | 32.905 |
| Bancada_Motor | historica12 | True | False | 6277 | 431.834 |
| Estefi | historica12 | True | True | 228 | 460.863 |
| Grapa | historica12 | True | True | 18 | 114.863 |
| LLanta_Trasera | historica12 | True | True | 42 | 31.574 |
| M3 PClip - 2mm | historica12 | True | True | 54 | 78.874 |
| Spoiler_arrière_Porsche_-_5 | historica12 | True | True | 28 | 8.373 |
| Tirante | historica12 | True | True | 22 | 91.151 |
| chasis - Part 2 | historica12 | True | True | 13803 | 866.364 |
| maneta | historica12 | True | True | 42 | 50.106 |
| pinza | historica12 | True | True | 2144 | 277.431 |
| spur | historica12 | True | True | 1405 | 209.059 |
| conector | otras_aceptadas_R7 | True | True | 19998 | 563.297 |
| 6558_fixed | otras_aceptadas_R7 | True | True | 8713 | 486.929 |
| Dimensiones | otras_aceptadas_R7 | True | True | 1100 | 197.326 |
| Con fallos pero si step | otras_aceptadas_R7 | True | True | 2567 | 417.197 |
| Pieza_Nueva_Detenida | otras_aceptadas_R7 | True | True | 8892 | 989.22 |

Las cuatro variantes del cubo se convierten realmente de nuevo. Si DATA es idéntico, la geometría STEP coincide con la referencia R7 ya comprobada; no se presenta esta comparación como una nueva ejecución del verificador independiente del cubo.

La serie incluye las doce conversiones históricas aceptadas, conector y cuatro casos posteriores según protocolo. El embudo sigue aplazado por petición expresa del usuario; no se afirma 14/14 conversiones. La batería unitaria sí incluye el diagnóstico y paso de entrada de los catorce originales.

### Problema que bloquea la aprobación de una versión

Bancada_Motor convierte en el candidato A, pero cambia de 89 caras CAD (25 cilindros, 59 planos y cinco B-splines) a 6.277 caras planas. El STEP R7 anterior tiene cuatro interferencias OCC en lectura fría; el nuevo recuperado no las tiene y conserva la malla original, pero la pérdida de superficies editables impide considerarlo una regresión completamente resuelta. Los ensayos ShapeFix, Wireframe, unificación, MakerVolume y autofusión aislados conservan interferencias o no producen un sólido. La protección local produce 315 caras y 148 interferencias; el ajuste preciso produce 119 caras y dos interferencias; el marco local tampoco consigue un resultado aprobado. Ninguno se integra. No se aceptan resultados por superar sólo `isValid` ni se desactiva el control para recuperar una aprobación aparente.

## Banco externo con CAD conocido

Se reutilizan las veinte geometrías públicas del banco anterior, con las mismas referencias CAD, STL, huellas, perfiles y límites. Incluye C20 remallado fino, previamente documentado; no se cambian los modelos para ocultar fallos. El oráculo proyecta muestras sobre todas las envolventes de la frontera CAD: un punto interior no tiene distancia cero a la superficie. La prueba de calibración del evaluador lo comprueba con el centro de un cubo, a 5 mm de su frontera.

| Caso | Motor | Oráculo completo | Controles de salida | Calibración entrada | Observación |
|---|---|---|---|---|---|
| 01_bloque | True | True | True | True |  |
| 02_taladro | True | True | True | True |  |
| 03_disco_hueco | True | True | True | True |  |
| 04_contorno_arcos | True | True | True | True |  |
| 05_dos_hexagonos | True | True | True | True |  |
| 06_soporte_cojinete | True | True | True | True |  |
| 07_patron_taladros | True | True | True | True |  |
| 08_taladros_inclinados | True | True | True | True |  |
| 09_pared_delgada | True | True | True | True |  |
| 10_avellanados | True | True | True | True |  |
| 11_perfil_spline | True | False | True | False | STL fuera del límite de calibración de entrada |
| 12_ladrillo_3x2 | True | True | True | True |  |
| 13_mfcad_chaflanes | True | True | True | True |  |
| 14_mfcad_mixto | True | True | True | True |  |
| 15_mfcad_combinado | True | True | True | True |  |
| 16_loft | True | False | True | False | STL fuera del límite de calibración de entrada |
| 17_barrido_spline | True | False | — | — | tiempo_evaluador |
| 18_barrido_variable | True | True | True | True |  |
| 19_helice | False | False | — | — | tiempo_agotado |
| C20_remallado_fino | True | True | True | True |  |

Límites del oráculo: volumen 0,5 %, caja 0,020 mm, p95 0,020 mm, máximo 0,060 mm, Euler/envolventes iguales, ningún desacuerdo de material fuera de la banda excluida de 0,08 mm y cero interferencias OCC. La banda de material evita clasificar puntos demasiado próximos a la frontera; no amplía los límites superficiales.

Los casos 11 (perfil spline) y 16 (loft) cumplen todos los criterios de salida frente al CAD original, pero sus STL superan la calibración de entrada de 0,005 mm: sus máximos son 0,015954 y 0,008031 mm respectivamente. No se amplía la calibración ni se cuentan como aprobaciones completas del banco. En total: dieciséis contrastes completos aprobados, dos con salida aprobada y calibración de entrada fuera de límite, uno inconcluso por recursos y una conversión interrumpida por tiempo.

El oráculo v4 usaba distancia al volumen sólido en una de sus mediciones, lo que podía devolver cero para muestras interiores. v5 mide contra la frontera completa y repite el contraste de los veinte casos. Los registros anteriores se conservan como antecedentes, no como la verificación final. La validación densa del motor ya empleaba la frontera completa y no se ha sustituido.

Los procesos interrumpidos por RAM o tiempo quedan identificados y los intentos se conservan. Una repetición por recursos mantiene los límites geométricos. El evaluador del barrido 17 agotó 4 GiB al crear el mallado fino. El intento alternativo reduce duplicaciones de memoria y comprueba convergencia de caja a 0,001 y 0,0005 mm, exige cambio <=0,00025 mm y prevé añadir el doble del cambio a la comparación con 0,020 mm. Alcanzó las medidas superficiales, topología y calibración, pero agotó 900 s durante el control de material: el contraste independiente completo de 17 queda INCONCLUSO. La hélice 19 agotó dos veces el límite de 900 s de conversión; no se cuenta como una conversión aprobada en esta batería. Las interrupciones no se describen como errores dimensionales ni se fuerzan aprobaciones.

## Pruebas automáticas y tolerancias

- `pruebas_completas.xml`: 142 pruebas, 0 fallos, 0 errores, 0 omitidas.
- `pruebas_evidencias_costura_final.xml`: 6 pruebas, 0 fallos, 0 errores, 0 omitidas.

La batería completa contiene 142 pruebas. Las seis de API del segundo XML incluyen cuatro repetidas y dos nuevas: 144 pruebas distintas en total, sin afirmar que se ejecutó una sola batería de 144. Los casos negativos cubren agujeros verdaderos, separaciones mayores, islas positivas microscópicas, cavidades exteriores o anidadas ambiguas, caras pequeñas válidas, objetos STEP sueltos y rechazo frío del CAD defectuoso 17. Además, el patch se aplicó a otra copia limpia de R7: sus nueve archivos coinciden por SHA256, las 25 pruebas afectadas pasan y el soporte móvil vuelve a convertirse con DATA idéntico al STEP previamente verificado. También pasa la herramienta independiente portátil contra ese resultado.

La primera ejecución de TestClient sin permiso de red local quedó bloqueada antes de iniciar la API; se repitió con acceso local habilitado. Se conserva el registro. No se contabiliza ese bloqueo del entorno como fallo geométrico del motor. Una prueba de caché se adapta al rechazo anticipado: sigue exigiendo la excepción de interferencias, la lectura fría y los límites intactos; no exige muestrear un CAD que ya se ha rechazado. El primer evaluador independiente encontró un tipo NumPy no serializable en su JSON; se corrigió esa salida y se repitieron las verificaciones, sin cambiar los STEP.

**No se han aumentado las tolerancias de aceptación.** Caja 0,020 mm, volumen 0,5 %, p95 0,020–0,030 mm según escala y máximo observado 0,060 mm en Precisión. No se activa 0,08 mm silenciosamente. Los perfiles, el núcleo de superficies, la validación densa, las invariantes de material y la regularización numérica R7 conservan sus bytes. `prueba_tolerancias_y_cambios.json` contiene la comparación y las huellas.

## 6558, límites y ensayos descartados

El usuario describe un par de líneas fuera del STEP al importarlo en Onshape. El archivo enviado contiene un sólido, dos envolventes, 8.713 caras y ninguna arista suelta fuera del sólido; pasa la validez B-Rep y OCC frío. Hay 863 aristas menores de 0,001 mm y 152 menores de 0,00001 mm. Esto orienta la investigación, pero no demuestra el motivo de las líneas de Onshape.

El prototipo aislado de holgura y longitud mínima para 6558 pasó la validez local, pero falló la comprobación independiente de un punto vacío de su cavidad. No se concluye si la cavidad se desplazó o desapareció; el resultado queda descartado y no se incorpora ni se distribuye como aprobado. `holgura_geometrica.py` de producción conserva R7.

**Onshape, Move face, Windows nativo, WebAssembly, laminado e impresión K1C no se han verificado aquí.** La aplicación experimental Python y su interfaz local no son una actualización de la conversión estática WebAssembly de main. No se promete reparación universal ni STEP paramétrico para una recuperación facetada.

Tiempos medidos en Linux, cuota de dos CPU y 8 GiB, con tareas concurrentes; no permiten afirmar velocidad en el PC del usuario. El tiempo máximo solicitado para esta sesión es cinco horas desde las 11:32 UTC. Se conserva la referencia R7 y no se modifica main.

## Continuidad del desarrollo

La siguiente puerta es resolver los recortes e intersecciones del CAD analítico de Bancada_Motor conservando sus superficies útiles, con la misma validación fría y los límites originales. Después debe repetirse el contraste completo de los barridos 17/19 dentro de un presupuesto de recursos documentado y conservar las nuevas reparaciones ya verificadas. Las líneas de 6558 necesitan comprobarse en Onshape; no se presentan como arregladas.

Se guarda el código modificado y su patch, los STEP nuevos verificados y las evidencias reproducibles. **No se entrega R8 ni un ZIP instalable mientras estas puertas sigan abiertas.** La última versión de uso entregada continúa siendo R7.
