# Análisis de los STEP aportados después de R9

Se han examinado **los siete STEP y los seis STL enviados por el propietario**, sin modificar el motor ni preparar una nueva versión. Se contrastaron además cuatro STEP iniciales conservados en el proyecto. Las conclusiones se refieren a estos archivos concretos, identificados por SHA-256.

La observación del propietario se confirma: la llanta ha recuperado superficies cilíndricas, mientras que maneta y tirante siguen convertidos como superficies planas. La bancada conserva agujeros cilíndricos, pero mantiene una fragmentación elevada.

## Contenido real de los STEP recibidos

| Pieza | Caras actuales | Superficies actuales | Resultado de lectura |
|---|---:|---|---|
| LLanta_Trasera | 53 | 30 Cylinder, 23 Plane | Un sólido, CAD exacto válido, sin objetos sueltos |
| Bancada_Motor | 1896 | 1140 Plane, 741 BSplineSurface, 15 Cylinder | Un sólido, CAD exacto válido, sin objetos sueltos |
| maneta | 9351 | 9351 Plane | Un sólido, CAD exacto válido, sin objetos sueltos |
| Tirante | 13122 | 13122 Plane | Un sólido, CAD exacto válido, sin objetos sueltos |
| 1x1-lego-brick | 2672 | 2672 Plane | Un sólido, CAD exacto válido, sin objetos sueltos |
| Estefi | 1769 | 1769 Plane | Un sólido, CAD exacto válido, sin objetos sueltos |
| Soporte_Muelle | 19563 | 19563 Plane | Un sólido, CAD exacto válido, sin objetos sueltos |

Los recuentos indican caras CAD, no cantidad de agujeros ni operaciones paramétricas. Las treinta caras cilíndricas de la llanta pueden dividir sus quince paredes cilíndricas físicas por costuras. En bancada, las 741 superficies B-spline sólo representan aproximadamente el 2,47 % del área total: son numerosos parches pequeños, no 741 grandes superficies de diseño.

## Comparación con las salidas iniciales

| Pieza | Caras iniciales → recibidas | Cilindros iniciales → recibidos | Otras curvas iniciales |
|---|---:|---:|---|
| Bancada_Motor | 89 → 1896 | 25 → 15 | 5 BSplineSurface |
| maneta | 42 → 9351 | 5 → 0 | 4 Torus, 2 BSplineSurface |
| Tirante | 22 → 13122 | 10 → 0 | 2 SurfaceOfRevolution |

Los STL de bancada, maneta, tirante y llanta son byte a byte los mismos del banco histórico. La comparación no mezcla geometrías de entrada diferentes. Los archivos actuales de maneta, tirante, Estefi y brick 1×1 tienen su sección DATA exactamente igual a las referencias ya probadas en R9, aun cuando algunos llevan el sufijo «impresion». El nombre del archivo no acredita qué perfil se eligió.

**Los STEP iniciales se veían más limpios, pero los tres fallan el control CAD exacto actual.** Una lectura normal los acepta; el modo exacto detecta curvas de aristas incoherentes con las curvas 2D sobre sus superficies (`InvalidCurveOnSurface`, `InvalidSameParameterFlag`) y fallos de orientación de contornos (`UnorientableShape`). Se localizaron aristas afectadas, no sólo un rechazo genérico:

- Bancada_Motor: 19 aristas afectadas; índices internos 45, 76, 77, 78, 79, 81, 84, 87, 88, 146, 147, 148, 189, 191, 215, 216, 219, 227, 235.
- maneta: 8 aristas afectadas; índices internos 3, 5, 7, 30, 32, 60, 61, 65.
- Tirante: 6 aristas afectadas; índices internos 5, 13, 14, 15, 36, 44.

Esto no contradice que el propietario los viera bien. La limpieza visual, la proximidad dimensional al STL y la coherencia interna CAD son condiciones distintas. Tampoco demuestra que cualquier superficie analítica antigua sea correcta: no se debe imponer ciegamente su antiguo recuento de cilindros.

## Geometría y límites de esta inspección

Se han medido cotas y volumen y se han realizado contrastes locales deterministas en ambos sentidos, con hasta 240 puntos característicos del STL y 360 puntos sobre aristas genuinas CAD por archivo. Es un diagnóstico muestreado: no una cota global Hausdorff ni una nueva ejecución de toda la batería de aceptación.

| Pieza | Error máximo de caja mm | Error de volumen % | Máximo local observado mm |
|---|---:|---:|---:|
| LLanta_Trasera | 0.000058 | 0.032699 | 0.002045 |
| Bancada_Motor | 0.000561 | 0.003693 | 0.000578 |
| maneta | 0.000000 | 0.000000 | 0.000000 |
| Tirante | 0.000000 | 0.000000 | 0.000000 |
| 1x1-lego-brick | 0.000000 | 0.000000 | 0.000000 |
| Estefi | 0.000000 | 0.000000 | 0.000000 |
| Soporte_Muelle | 0.000100 | 0.000903 | 0.000755 |

Cero impreso significa por debajo de la resolución de redondeo de esta tabla. En estas medidas no se han encontrado desviaciones que expliquen la pérdida visual; el problema principal observado es la representación de las superficies. No se han cambiado tolerancias ni se ha usado un perfil más permisivo para aprobar los archivos.

Los seis STL tienen una sola componente, aristas cerradas y orientación coherente. Esto es un control topológico básico y no demuestra por sí solo ausencia de autointersecciones. `Eje.stl` no tiene STEP correspondiente en el RAR: sólo se inspeccionó su malla. Para los STEP de Estefi y brick 1×1, ausentes del RAR de STL, se usaron los originales históricos identificados en el JSON.

## Comprobación adicional de interferencias

Se ha ejecutado `BRepAlgoAPI_Check(shape, False, True)` en los siete STEP recibidos. Resultado: 7/7 sin interferencias detectadas. Véase `bop_resultados.json` para los resultados y tiempos de cada archivo.

## Causa identificada en el motor

Los registros de R9 muestran que maneta y tirante generan primero candidatas compactas, pero se rechazan por incoherencia CAD exacta. Después se intenta la recuperación de curvas y finalmente se conserva el sólido facetado. Ese proceso explica tanto la presencia de miles de caras planas como parte del trabajo adicional; en esta inspección no se han vuelto a medir tiempos de conversión ni se ha hecho una comparación controlada entre ordenadores.

La mejora local de R9 tampoco cubre automáticamente esos casos: está acotada a entradas de hasta 12.000 triángulos y recuperaciones facetadas de 150 a 3.500 caras, sin cilindros previos. Maneta supera el límite de caras CAD; tirante supera ambos límites; Soporte_Muelle tiene 59.456 triángulos y 19.563 caras CAD. Bancada ya tiene cilindros y recorre otra vía. **Aumentar esos presupuestos no corregiría por sí solo las uniones defectuosas.**

## Próximo desarrollo recomendado

1. Empezar por maneta y tirante como regresiones de calidad. Conservar los ajustes de superficies aprovechables del motor inicial y reconstruir de forma coherente las aristas compartidas, las curvas 2D de recorte y sus orientaciones. La maneta también requiere superficies toroidales; mejorar únicamente los cilindros completos no basta.
2. Validar cada candidata después de exportar y volver a leer: sólido único, coherencia CAD exacta, interferencias, geometría frente al STL y conservación de material y huecos. Exigir además conservación o mejora de las superficies CAD; completar la conversión no es un criterio suficiente de calidad.
3. Reducir en bancada los parches de transición preservando los agujeros ya recuperados. Mantener la llanta como regresión obligatoria.
4. Ampliar la recuperación por regiones y con presupuestos medidos para piezas como Soporte_Muelle, en vez de desactivar las protecciones globales o sustituir toda la pieza por facetas tras un fallo local.

No se ha implementado este desarrollo en esta tarea de análisis. No se entrega R10 ni un motor modificado. Windows nativo, Onshape y operaciones de edición en CAD externo no se han ejecutado aquí.

## Evidencias

Los JSON incluyen huellas de los archivos, tipos y áreas de las caras, cilindros, volúmenes, controles, puntos sospechosos y fallos exactos localizados. Las rutas absolutas son las utilizadas en el entorno de auditoría; no son enlaces de descarga. Los RAR originales se conservan sin reescribir.
