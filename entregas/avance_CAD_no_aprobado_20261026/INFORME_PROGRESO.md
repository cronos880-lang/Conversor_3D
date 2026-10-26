# Avance del motor CAD — candidato NO APROBADO

26/10/2026 21: 05 CET. **No se publica una actualización R8. No copiar estas fuentes sobre la instalación de uso.**
El código y las evidencias se conservan para continuar el desarrollo. El identificador R8 dentro del código es el nombre del candidato interno, no una versión aprobada.

## Resultado y decisión

Hay avances reales de reconstrucción, pero no se supera toda la aceptación CAD.
Bancada_Motor pasa de 6277 caras planas del avance anterior a 126 caras, con 15 cilindros respaldados por el STL.
Pinza pasa de 2144 caras planas en R7 a 50 caras, con 10 cilindros confirmados. Estos dos resultados son
**prototipos rechazados para publicación**, porque una comprobación exacta adicional detecta incoherencias
entre curvas 3D y curvas de recorte 2D/superficies. Lego 4×2 también falla esa comprobación.

Las distancias al STL, el volumen, la caja, el sólido cerrado y CGAL pueden pasar sin que las curvas CAD
sean suficientemente coherentes. Por eso no se da por terminada la mejora ni se entrega un instalador nuevo.
La versión de uso, las entregas R7 y main no se modifican.

## Pruebas reales y alcance

| Prueba | Resultado |
| --- | --- |
| Pruebas de código M1 congelado |148 pasan; 0 fallos,0 errores,0 omitidas |
| Cubo-carrito más 3 giros |4/4 conversiones completas; DATA STEP idéntico a R7 |
| Regresión seleccionada M1 |21/21 conversión y geometría; 19/21 con DATA idéntico a R7 |
| Originales históricas |12 de la suite y conector pasan: 13 originales probadas. Embudo aplazado; no 14/14 |
| Cuatro entradas recientes M1 |4/4 conversión y controles geométricos; sólo 3/4 superan también la comprobación CAD exacta |
| Banco externo, primer intento M1 |19/20 conversiones; 09 agota 480 s |
| Reintento 09 aislado M1 |Vuelve a agotar 480 s; la concurrencia no explica por sí sola el fallo |
| Pruebas nuevas de caché de rechazos |5/5 pasan |
| Suite completa M2 |153 pruebas; 0 fallos; 0 omitidas |
| Reintento 09 con M2 |Pasa en 351.668 s, con el mismo límite de 480 s. |
| Navegador Chromium |4/4 carga, conversión, descarga y DATA idéntico a CLI: Lego, soporte, PEGS y Bancada |
| **Aceptación CAD exacta** |**6 pruebas: 3 pasan y 3 fallan. Puerta de publicación cerrada.** |

Las cuatro pruebas de navegador son del servidor Python en Linux. Las capturas muestran el STL cargado y el estado
de conversión, no una prueba visual del STEP en Onshape. El éxito de la interfaz no convierte en válidos los tres
STEP que fallan la coherencia exacta. No se usan marcas xfail ni omisiones para ocultar esos fallos. El objetivo para aprobar es 6/6: los tres fallos actuales son defectos pendientes, no controles que deban seguir fallando.

## Fallo CAD localizado

| Modelo | Comprobador estándar | Comprobador exacto de curvas/superficies |
| --- | --- | --- |
|R8_Bancada|pasa|**FALLA**|
|R8_pinza|pasa|**FALLA**|
|Soporte_movil_2|pasa|pasa|
|Soportes_estante_bobinas_v0|pasa|pasa|
|Technic_PEGS_Cross_x6_A|pasa|pasa|
|V_legoBrick4x2|pasa|**FALLA**|

En Bancada, una curva presenta 0,00918695 mm de desacople paramétrico y su punto peor está a 0,00917096 mm de la
superficie más cercana. Reproyectar la curva 2D deja 0,00917097 mm: el problema no se resuelve cambiando sólo la
parametrización. Los ensayos de SameParameter, corrección de precisión numérica, precisión declarada en STEP y
exportación sin pcurves tampoco superan la lectura fría exacta. **No se adoptan esos intentos ni se amplían las
tolerancias del perfil para aprobarlos.** Los diagnósticos conservan InvalidCurveOnSurface e InvalidSameParameterFlag.

La siguiente mejora necesaria es reconstruir fronteras 3D compatibles con las dos superficies que comparten cada
arista, con control del movimiento, tangencias cuando estén respaldadas por el STL y preservación de huecos y
cavidades. Después deben pasar las seis pruebas exactas, la regresión y la importación en CAD. No basta con retocar
el mensaje de error o exportar el mismo B-Rep con otros indicadores.

La tolerancia STL–STEP controla la fidelidad a la pieza. Ese límite no sustituye la coherencia interna entre las curvas y las superficies del CAD.

## Qué está implementado

- Reparación de redundancias exactamente nulas, costuras en T y envolventes negativas anidadas, con verificación
  del original y del campo de material. No se tapan agujeros ambiguos ni se eliminan cuerpos por su tamaño.
- Lectura estricta del STEP y rechazo de interferencias en frío antes de mallar, incluyendo objetos sueltos.
- Rescate experimental de encuentros CAD más ceñido, conservando los cilindros respaldados por el STL. Exige tres
  mallados cerrados, orientados, manifold, con Euler correcto y cero intersecciones CGAL. Es un avance de geometría
  muestreada que todavía necesita superar la coherencia CAD exacta.
- Herramienta de auditoría exacta y seis pruebas de aceptación que exponen los tres fallos reales.
- En M2, evitar repetir el mismo trabajador rechazado cuando coinciden hash de entrada, perfil y parámetros
  efectivos. Los rechazos de otro perfil, otros datos o parámetros distintos no se reutilizan. No se guardan
  candidatos aprobados como fallos ni se omite la validación del STEP.

## Tolerancias sin relajar

Las cotas del encargo se conservan: bbox 0,020 mm, volumen 0,5%, p95 0,020–0,030 mm y máximo observado0,060 mm según
las condiciones originales. Las constantes del motor, perfiles, holgura, validación densa y política de recursos
se comparan con R7 en TOLERANCIAS_VERIFICADAS.json. El perfil de impresión0,080 mm sigue siendo explícito y no se
usa para aprobar estas pruebas. M2 sólo modifica la repetición de intentos; no cambia la geometría ni las cotas.

El rescate investigado usa región 0,006 mm, B-spline 0,003 mm, arista 0,001 mm y movimiento interno máximo 0,012 mm.
Bancada conserva15 cilindros confirmados y pinza10. Los diez redondeos aproximados que antes crecían como cilindros
en Bancada se representan con superficies libres, no se eliminan. Frente al STL, los máximos medidos son
0,030491 mm para Bancada y 0,007995 mm para pinza. Son medidas muestreadas, no una cota Hausdorff global del B-Rep.

## Entradas recientes

| Entrada | Resultado geométrico M1 | Reserva |
| --- | --- | --- |
| V_legoBrick4x2 |477 caras,8 cavidades,9 shells y Euler18; máximo independiente0,018360 mm |**Coherencia exacta no superada** |
| Soporte_movil_2 |493 caras; costura subdividida sin tapa; máximo independiente0,023388 mm |Supera el control exacto; Windows/Onshape sin probar |
| Technic_PEGS_Cross_x6 |2044 caras, recuperación facetada; control dirigido5040 muestras, máximo 0,026753 mm |No es reconstrucción paramétrica |
| Soportes_estante_bobinas_v0 |131 caras; DATA idéntico a R7 |Ya funcionaba en el entorno de referencia; no se demuestra mejora nueva |

Los dos archivos PEGS enviados tienen el mismo SHA256 y son una sola geometría. Para PEGS se conserva la cobertura
adaptativa de las diez caras auxiliares retiradas: se refiere a la frontera tessellada final y no a una prueba global
exacta del CAD. El muestreo ordinario de la interfaz muestra 0,00005 mm; **no debe confundirse con el máximo dirigido
0,026753 mm**. Conviene integrar esa cobertura de las caras modificadas en el resumen de calidad del motor.

## Banco externo y recursos

Se repiten las20 geometrías de dificultad creciente con límites de 300/480/720/900 s y 4096MiB. No se cambian sus
límites geométricos. En M1, pared_delgada agota 480 s dos veces, también aislada. El registro muestra que el mismo
rescate se repetía al variar ángulos exteriores, aunque su reconstrucción interna seguía siendo la misma. M2 añade
la deduplicación para ese caso general, no una regla por nombre de pieza. El resultado real del reintento figura arriba.

El caso19 sí termina en 580,537 s con el límite original de 900 s. Su STEP de recuperación tiene19998 caras planas:
se conserva esa identificación. Frente al CAD original: máximo 0,001213 mm, error de volumen 0,025410% y 1689 puntos
materiales sin discrepancias. El control pendiente del caso17 también se completa sobre los mismos STEP por SHA256:
1748 puntos,0 discrepancias; caja con margen máximo 0,001701 mm; máximo superficial0,003475 mm.

En11 y 16, los STEP superan los controles geométricos, pero el STL de entrada no alcanza la calibración de 0,005 mm
frente a su CAD original. No se cuentan como ensayos globales limpios. Tampoco se afirma que las20 geometrías hayan
superado la comprobación exacta añadida: ese control se ha ejecutado sobre los seis modelos indicados.

Las métricas independientes anteriores sólo se enlazan a salidas actuales cuando FILE_SCHEMA y todo DATA son
binariamente idénticos. No se presenta esa identidad como una nueva ejecución del oráculo. Bancada y pinza tienen
además evaluación independiente actual con utilidades R7 congeladas, sin llamar a _calidad; esa evaluación
geométrica no incluía el nuevo control exacto que falla. El evaluador externo es versión5, con distancia a todas
las envolventes de frontera, corrigiendo la antigua métrica que devolvía cero para puntos interiores del sólido.

## Regresión, pieza por pieza (M1)

| Pieza | Conversión y geometría habitual | Tiempo(s) | DATA idéntico a R7 |
| --- | --- | ---: | --- |
|cubo-carrito|pasa|43.565|sí|
|cubo-carrito_giro_1|pasa|45.168|sí|
|cubo-carrito_giro_2|pasa|64.800|sí|
|cubo-carrito_giro_3|pasa|103.729|sí|
|1x1-lego-brick|pasa|28.822|sí|
|Bancada_Motor|pasa|120.732|no; candidato nativo con coherencia exacta pendiente|
|Estefi|pasa|385.196|sí|
|Grapa|pasa|53.575|sí|
|LLanta_Trasera|pasa|17.683|sí|
|M3 PClip - 2 mm|pasa|84.997|sí|
|Spoiler_arrière_Porsche_-_5|pasa|11.668|sí|
|Tirante|pasa|50.974|sí|
|chasis - Part 2|pasa|506.874|sí|
|maneta|pasa|24.234|sí|
|pinza|pasa|80.440|no; candidato nativo con coherencia exacta pendiente|
|spur|pasa|98.053|sí|
|conector|pasa|494.950|sí|
|6558_fixed|pasa|457.824|sí|
|Dimensiones|pasa|181.513|sí|
|Con fallos pero si step|pasa|319.370|sí|
|Pieza_Nueva_Detenida|pasa|716.256|sí|

Los tiempos se midieron en este entorno con hasta dos conversiones a la vez, excepto los reintentos declarados
como aislados. No son una comparación controlada entre ordenadores ni demuestran una aceleración general.

## Versiones de código y límites de la prueba

M1 es el código congelado que ejecutó148 pruebas,21 conversiones históricas,4 entradas recientes,20 intentos externos
y 4 flujos de navegador. M2 sólo añade la corrección de repetición de rechazos y cinco pruebas; su resultado de
código y el caso09 están indicados arriba. **La regresión completa de 21 piezas no se ha repetido con M2.** Ambas
fuentes completas y sus huellas se conservan por separado. Ninguna se ofrece como actualización aprobada.

Windows nativo no se ha ejecutado en este entorno Linux. Onshape/Move face y la K1C requieren pruebas reales;
los dos trazos observados en 6558 no tienen causa confirmada ni se anuncian corregidos. WebAssembly tampoco se
ha validado: probar el servidor Python no valida la aplicación estática. Embudo continúa aplazado por el usuario.
No se promete reparar cualquier STL ni resolver en esta fase todas las superficies, roscas o canales defectuosos.

## Archivos y reproducción

El ZIP de código contiene fuentes completas M1/M2, archivos modificados frente a R7, parche para revisión,
protocolos, originales usados, STEP candidatos, registros, capturas y JSON/XML. **No es un instalador.** Los STEP
de Bancada, pinza y Lego deben tratarse como candidatos rechazados para publicación por el control exacto.
El segundo ZIP contiene el banco externo, referencias CAD y sus resultados. Los originales se conservan por SHA256.

Para repetir las seis pruebas de aceptación, instalar las dependencias del entorno de referencia, establecer
VISOR_EVIDENCIAS_R8 a la carpeta evidencias del ZIP y ejecutar pytest sobre herramientas_auditoria/test_aceptacion_cad_exacta.py.
El resultado actual esperado es3 fallos y 3 éxitos; no se omiten archivos ausentes. comprobar_step_exacto.py permite
auditar un STEP sin modificarlo. La suite completa requiere también los fixtures del paquete R7 y el banco R7
original; el reproductor falla si faltan. Los scripts originales de evidencia conservan rutas del entorno y no se
presentan como instaladores portables.
