# Avance del motor: uniones y calidad

**Investigación, sin nueva versión del Visor para Windows. No instalar estas fuentes sobre el programa de uso. R11 permanece intacta.**

Se ha implementado una herramienta general para reunir divisiones cilíndricas y se ha reforzado la reconstrucción de parches. Las dos piezas siguientes tienen un nuevo STEP de estudio aprobado contra sus STL originales; la mejora visual es incremental y no resuelve todas las líneas interiores.

| Pieza | Caras antes → ahora | Caras cilíndricas antes → ahora | Caja, error mm | Volumen, error % |
|---|---:|---:|---:|---:|
| Bancada | 201 → 192 (R11 original: 239) | 25 → 16 | 0,000561 | 0,027432 |
| Maneta | 36 → 34 | 5 → 3 | 0,000057 | 0,022273 |

La reducción de caras cilíndricas reúne divisiones de los mismos cilindros: se comprueban radios/ejes y la intersección de cada dominio recortado con los dominios anteriores en ambos sentidos. No representa agujeros eliminados. También se verifican los dominios de las otras caras. La bancada conserva 15 cilindros confirmados en el STL, sus 14 caras de extrusión y sus 27 caras B-spline.

Ambos STEP superan reimportación estricta, CAD exacto, coherencia de curvas, BOP en frío, un sólido sin objetos sueltos, material/Euler y los tres mallados a 0,00025/0,0005/0,001 mm: cerrados, orientados y cero cruces CGAL. Se comparan contra los STL originales, no sólo contra otro STEP.

En la bancada, el máximo denso observado STL→CAD es 0,035239486 mm y CAD→STL 0,003965092 mm; los mallados finos dan un máximo de 0,003437434 mm. En la maneta, los máximos densos son 0,002665157/0,016032882 mm y el máximo entre los tres mallados finos es 0,023579074 mm. Se publican todos estos valores, sin sustituirlos por el más favorable. Son muestreos, no una demostración de Hausdorff global.

Los límites de producción se conservan: caja 0,02 mm, p95 0,02 mm, máximo observado 0,06 mm y volumen 0,5 %. Tampoco se amplían los presupuestos internos de geometría ni la tolerancia CAD de 1e-7 mm. La reconstrucción general mantiene su requisito de reducir al menos el 25 % las caras; no se ha rebajado para aceptar la bancada. La herramienta de reunión sólo cambia representaciones de dominios certificados y tiene su propia auditoría completa.

## Technic: resultado real

**Todavía no hay STEP de Technic aprobado.** Resultado del último ensayo: Persisten interferencias del conjunto tras las reconstrucciones acotadas: 51

Última secuencia BOP bruta (antes de exportar): 840 caras / 44 interferencias, 881 caras / 39 interferencias, 913 caras / 51 interferencias. La reconstrucción automática adicional no ha mejorado el resultado hasta hacerlo aceptable y no se incorpora a la aplicación.

Los ensayos anteriores muestran la diferencia entre tener un sólido CAD válido y tener un STEP correcto:

| Ensayo | Caras | BOP en frío | Resultado |
|---|---:|---:|---|
| Solidificación con caras exactas | 743 | 57 interferencias | Rechazado |
| Anclaje físico y planos certificados | 739 | 42 interferencias | Rechazado |
| Rechazo de campos plegados | 817 | 34 interferencias | Rechazado |
| Colapsos y autointerferencias por cara | 840 | 27 interferencias | Rechazado |

El último ensayo y sus tiempos/RAM están en `evidencias/M63_technic`. Los STEP rechazados no se distribuyen como piezas para probar. La reparación booleana con tolerancia cero devolvió nueve sólidos inválidos: descartada. La división por continuidad produjo errores y aumentó tolerancias: descartada. Su posterior reparametrización no alcanzó los 5e-8 mm exigidos: tampoco se aceptó.

El ensayo final usa también una reconstrucción local guiada por las interferencias del conjunto, con un máximo de dos correcciones y trazabilidad de las regiones del STL. Los diagnósticos BOP brutos se guardan separados del BOP en frío: sus recuentos no son intercambiables. Si no queda una acción local verificable, se rechaza el candidato.

La ruta experimental sigue partiendo de la malla reparada ya usada por R11. El certificado incluido enlaza los SHA de la entrada original y la reparación; no sustituye la nueva comprobación original→STEP ni una prueba en Onshape.

## Cambios implementados

- Encuentros entre planos calculados en un espacio afín coherente para vértices y curvas, también cuando los planos son casi paralelos.
- Conciliación de contactos nativos y conservación de semillas geométricas; retirada acotada de hipótesis incompatibles sin aumentar tolerancias ni retirar cilindros confirmados.
- Parches con contornos compuestos y dominio triangular regular, registro UV con referencias a sus propietarios y comprobación completa UV/3D de 5e-8 mm.
- Protección de planos respaldados por el STL; anclaje físico para evitar abombar una superficie sólo por imponer un punto UV interior; reconocimiento de planos por todos los polos con pesos positivos.
- Rechazo de pliegues observados en campos libres y subdivisión de la región fuente. Esta detección muestreada sirve para rechazar: no sustituye BOP ni los tres controles CGAL finales.
- Comprobación de colapsos nuevos entre vértices distintos y de autointerferencias de cada cara curva antes de ensamblar el sólido.
- Corrección sólo de orientación cuando conserva las mismas caras/aristas/tolerancias. Un salto numérico UV se conserva sin añadir aristas sólo cuando se demuestra su cota física mediante derivadas y la cara ya supera CAD exacto.
- Reanudación de la reconstrucción a partir de las regiones implicadas en BOP, sin volver a empezar por el STL ni retirar cilindros confirmados. Los límites de recursos de hipótesis/regiones son 64/32, manteniendo el máximo total de 65 intentos, el límite de caras y los mismos límites geométricos.
- Proyección ortogonal mínima en encuentros de planos cuando cumple todos los contactos a 1e-12 mm; evita conservar desplazamientos tangenciales de una semilla antigua sólo porque el optimizador ya no los corrige.
- Diagnósticos de rechazo y conservación de las entradas; las propuestas que fallan no reemplazan los resultados previos.

## Pruebas y límites de esta entrega

Batería final real: **348 passed, 3 warnings in 353.64s (0:05:53)**. No se suman las ejecuciones repetidas ni los subconjuntos como pruebas distintas. El control de conversión del cilindro sintético y el control CAD de cinco caras con contorno compuesto pasan también; el segundo no es una conversión de una pieza del usuario.

La primera batería de esta línea pasó 342 pruebas y falló una prueba temporal: confundía el arranque de Python con actividad durante la fase de espera. Se conserva el registro. La prueba se sincronizó con un mensaje de inicio del hijo, sin modificar el código ni los plazos de supervisión del producto; la batería posterior pasa.

No se ha integrado una nueva aplicación, ni repetido una nueva matriz de las 14 piezas y el cubo-carrito con ella. No hay un nuevo resultado aprobado para soporte de muelle ni conector en este bloque. Embudo sigue aplazado por indicación del usuario. Windows nativo, Onshape y K1C no se han ejecutado aquí. Los 150 archivos congelados de R11 conservan sus SHA originales.

## Archivos y reproducción

`STEP_DE_ESTUDIO_VALIDADOS` contiene únicamente las piezas aprobadas indicadas. Son archivos CAD de comparación, no una actualización del Visor. `fuentes_motor_NO_INSTALAR` contiene fuentes del motor experimental y pruebas; `CAMBIOS_DESDE_M37.patch` y `ARCHIVOS_MODIFICADOS.json` facilitan revisar los cambios. No se entrega un lanzador Windows.

Con las dependencias del entorno de desarrollo R11 y los bindings CGAL/gpytoolbox configurados como en su auditoría, desde la raíz de este paquete:

```text
python fuentes_motor_NO_INSTALAR/cilindros_contiguos.py reproducir_cilindros/Bancada_Motor_original.stl reproducir_cilindros/Bancada_base_201.step bancada_nueva.step bancada_informe.json
python fuentes_motor_NO_INSTALAR/cilindros_contiguos.py reproducir_cilindros/maneta_original.stl reproducir_cilindros/maneta_base_36.step maneta_nueva.step maneta_informe.json
```

Las salidas deben ser nuevas. Cada comando ejecuta las comprobaciones completas y borra su candidato si falla. No basta con que genere un archivo o arranque.

Las pruebas completas requieren además el material de auditoría R11: casos R2–R5, batería externa y fixtures indicados en su guía. Los dos STL y las bases de las reproducciones anteriores sí están incluidos aquí. La referencia de código base es la continuación M37 publicada en la misma rama de investigación; la aplicación de uso no se modifica.
