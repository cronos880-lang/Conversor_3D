# Visor R10 experimental: resultados reales

La mejora demostrada de esta entrega está en el tirante: **13.122 caras planas en R9 → 22 caras en R10**, con diez caras cilíndricas, diez planas y dos superficies de revolución. Se obtiene desde el STL mediante el motor completo, sin seleccionar un caso por su nombre. La bancada y la maneta todavía necesitan otra mejora; no se presentan como resueltas.

## Qué cambia y cómo se protege lo que funciona

Se añade una reconstrucción acotada de los encuentros entre planos, cilindros y superficies de revolución, únicamente después del rechazo de las estrategias R9. Se reconstruyen vértices y aristas compartidas, se prolonga el perfil cúbico de revolución sin alterar su intervalo original y se verifica la correspondencia de las curvas 3D con sus curvas UV. Las elipses de radios iguales a menos de 1e-12 mm se escriben como círculos, con el mismo eje, parametrización y tolerancia; las elipses reales se conservan.

La nueva ruta requiere una sola componente STL sana, cerrada y orientada, hasta 20.000 triángulos y hasta 192 caras CAD compactas. Rechaza superficies libres y toroidales que esta entrega no verifica. No rellena huecos ni cambia automáticamente la intención geométrica. Tiene trabajador aislado, vigilancia de recursos y un plazo de 450 s adicional para esta propuesta. Si falla, no sustituye el candidato. La nueva ruta no garantiza que el motor sea más rápido.

**23/24 resultados conservan el bloque DATA de R9 idéntico byte a byte.** Resultados distintos: Tirante. Las huellas del núcleo de 84 archivos ejecutado y entregado coinciden. Las correcciones posteriores a la primera instantánea afectan a pruebas, documentación y saltos de línea del instalador; no cambian el núcleo CAD de esas conversiones.

## Geometría del tirante

| Medida | Resultado R10 | Límite original de Precisión |
|---|---:|---:|
| Error relativo de volumen | 0.113342 % | 0,5 % |
| Diferencia de caja | 0.000951 mm | 0,02 mm |
| p95 denso máximo | 0.00436514 mm | 0,02 mm |
| Distancia máxima observada | 0.027430 mm | 0,06 mm |
| Tolerancia máxima de aristas CAD | 0,0000001 mm | Sin aumento |

El STEP reimportado contiene un único sólido válido, supera el control CAD exacto y BOP no encuentra interferencias. Conserva Euler −10. Los seis grupos cilíndricos confirmados por el detector sobre el STL se mantienen dentro de las caras recortadas, con el control previo de 0,008 mm. No se sustituye ese control por distancia a un cilindro infinito.

| Deflexión de mallado | Triángulos | Cerrado y orientado | Intersecciones CGAL |
|---|---:|---|---:|
| 0.00025 mm | 105860 | Sí | 0 |
| 0.0005 mm | 97114 | Sí | 0 |
| 0.001 mm | 84710 | Sí | 0 |

Las distancias se contrastan con muestras deterministas y con los tres mallados de frontera; no constituyen una demostración de distancia Hausdorff global para STL arbitrarios.

## Batería completa

**249 pruebas automáticas aprobadas, sin omisiones.** 21 conversiones principales y tres recientes aprobadas; 15 por CLI y nueve mediante Chromium, con carga, conversión y descarga real. Se comprueba la identidad del servidor, el perfil Precisión, los bytes descargados y la conservación del STL original. La lectura fría independiente de los 24 STEP y la caja posterior a la cancelación también pasa.

Los 21 casos principales incluyen cubo-carrito y tres giros, las doce piezas históricas restantes y cinco regresiones adicionales. En total se conservan trece de las catorce históricas: **Embudo continúa aplazado por indicación del usuario; no se declara 14/14**. Los tres recientes son Lego 4×2, soporte móvil y Technic PEGS.

| Pieza | Caras STEP | Máximo observado (mm) | DATA igual a R9 |
|---|---:|---:|---|
| Tirante | 22 | 0.027430 | No |
| 1x1-lego-brick | 2672 | 0.000000 | Sí |
| Estefi | 1769 | 0.000000 | Sí |
| Grapa | 622 | 0.000677 | Sí |
| Spoiler_arrière_Porsche_-_5 | 28 | 0.002827 | Sí |
| chasis - Part 2 | 13803 | 0.006785 | Sí |
| maneta | 9351 | 0.000000 | Sí |
| spur | 1405 | 0.004738 | Sí |
| cubo-carrito_giro_1 | 1838 | 0.000000 | Sí |
| cubo-carrito_giro_2 | 1195 | 0.000000 | Sí |
| cubo-carrito_giro_3 | 1853 | 0.000000 | Sí |
| conector | 19998 | 0.010826 | Sí |
| Dimensiones | 1100 | 0.000005 | Sí |
| Con fallos pero si step | 2567 | 0.000592 | Sí |
| Pieza_Nueva_Detenida | 8892 | 0.020334 | Sí |
| LLanta_Trasera | 53 | 0.002138 | Sí |
| V_legoBrick4x2 | 1149 | 0.005932 | Sí |
| M3 PClip - 2mm | 1484 | 0.000000 | Sí |
| cubo-carrito | 1152 | 0.000000 | Sí |
| Bancada_Motor | 1896 | 0.000730 | Sí |
| pinza | 448 | 0.003787 | Sí |
| 6558_fixed | 8713 | 0.016360 | Sí |
| Soporte_movil_2 | 493 | 0.018513 | Sí |
| Technic_PEGS_Cross_x6_A | 2044 | 0.000050 | Sí |

Los tiempos individuales y las huellas constan en RESULTADOS_REGRESION.csv y en los registros JSON. Se ejecutaron colas concurrentes en un entorno Linux limitado a dos CPU y 8 GiB; sus tiempos no se presentan como referencia del ordenador del usuario.

## Lo descartado y lo que falta

Las variantes compactas de la maneta llegaron a superar comprobaciones CAD y algunas medidas, pero fallaron la frontera fina CGAL y la conservación de dos grupos cilíndricos. Se descartaron. Las variantes de la bancada fallaron encuentros o parches interiores verificables y también se descartaron. La propuesta toroidal de Lego 1×1 no alcanzó la coherencia exigida en los vértices. Ninguna de esas variantes ni sus atajos forman parte de la ruta activa.

La llanta conserva la mejora ya aprobada de R9. La bancada, maneta y las zonas aún facetadas siguen pendientes; una conversión correcta no equivale a recuperar todas las superficies analíticas. Octogon y Barrera_Lego sólo se habían recibido como STEP en el lote anterior y no se declaran reconvertidos.

La primera ejecución de pytest se lanzó sin el directorio de dependencias CGAL de este entorno Linux y produjo fallos de preparación; además se corrigió una aserción de derivadas para medir el error físico de Taylor y se aislaron los tests de caché R9 de la estrategia nueva. Se conserva el registro rechazado. La batería válida se repitió con las dependencias explícitas; no se rebajaron los controles geométricos ni se ocultaron pruebas.

**No ejecutado aquí:** Windows nativo, importación en Onshape y prueba física en Creality K1C. La entrega incluye el Visor completo preparado para Windows y las dependencias fijadas, pero necesita esa validación en su sistema. La inspección visual de Onshape no se declara resuelta por el control OCC.

## Uso y reproducción

Extrae el ZIP completo en una carpeta nueva y abre Iniciar.bat. Incluye Visor_experimental_fuentes; puede reutilizar el entorno CAD de R7, R8 o R9 sin modificarlo. Encabezado R10 experimental, puerto 8776. Mantén Automático (precisión). El perfil 0,08 permite otro error geométrico; no fuerza más cilindros ni mejora por sí solo la topología.

La auditoría separada incluye entradas, referencias, evaluadores anteriores, scripts de reproducción, hashes, pruebas, incidencias y registros. Los archivos modificados y el parche desde R9 se entregan por separado. Las versiones anteriores y la web de main permanecen intactas.
