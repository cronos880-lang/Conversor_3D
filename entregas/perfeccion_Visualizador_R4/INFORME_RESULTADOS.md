# R4 experimental — progreso demostrado y reparaciones pendientes

Evidencia cerrada: 2026-10-24T12:47:18.620543+02:00 (Europe/Madrid). Trabajo de esta fase iniciado aproximadamente a las 11:15 del 24/10/2026. Entorno Linux, Python 3.12. **No es una actualización estable certificada ni una solución completa de todas las piezas.** Se entrega la aplicación completa y los cambios implementados.

## Resultado que motivó esta revisión

El usuario indicó que 30383 genera STEP pero muestra muchas caras, aristas o parches. En la referencia R3 ya pasaba las medidas: eso no demostraba que su fragmentación estuviera solucionada. R4 incorpora una alternativa general de reconstrucción de bandas circulares con evidencia geométrica, sin inspeccionar nombres ni dibujar piezas específicas.

30383 pasa de **227 a 182 caras (19,82 % menos)** y de **547 a 460 aristas (15,90 % menos)**. R4 tiene 173 planos, 6 cilindros y 3 conos. **Siguen quedando muchos parches**, especialmente donde el propio STL representa curvas con pocos segmentos. No se presenta como reconstrucción paramétrica completa ni como defecto visual totalmente resuelto. La imagen `evidencias/30383_R3_R4_caras.png` permite revisar la reducción parcial; es una representación teselada ilustrativa.

El primer B-Rep alternativo produjo un aviso de interferencia. No se aceptó así: pasó por el saneamiento CAD ya existente, se reexportó y revalidó. El archivo final sí supera la comprobación avanzada con cero avisos. La comprobación independiente vuelve a leer **ese mismo STEP**, contrastando su SHA256.

| Control de 30383 | Resultado real R4 |
|---|---:|
| Sólidos cerrados y B-Rep válido tras reimportar | 1 |
| Interferencias avanzadas detectadas | 0 |
| Error máximo de cotas | 0.002590 mm |
| Máximo denso STL → CAD, 2679 puntos | 0.012768 mm |
| Máximo denso CAD → STL, 20651 puntos | 0.015036 mm |
| Peor p95 superficial denso | 0.010498 mm |
| Error de volumen, integración adaptativa independiente | 0.010701 % |
| Controles de ocupación de material | 1870; 0 discrepancias |
| Puntos adicionales de cavidades y paredes | 31; todos correctos |

El máximo denso anterior era 0,016800 mm; ahora es 0,015036 mm. El p95 global también disminuye. Algunas métricas individuales sí cambian: el error volumétrico estándar del motor pasa de 0.001961 % a 0.035851 %, y el p95 STL→CAD de 0,001809 a 0,007245 mm, ambos dentro de sus límites originales. Por tanto no se afirma que cada indicador mejore. La integración adaptativa usa dos precisiones (10^-6 y 10^-8), converge en 388,428679 mm³ frente a 388,387119 mm³ de referencia; es una comprobación independiente más robusta del volumen.

El STL tiene **dos cavidades laterales y un tabique central**; no se debe inventar un agujero pasante. Los 31 controles específicos verifican las cavidades, ese tabique y las paredes. Los 1870 puntos distribuidos contrastan material con una referencia OCC obtenida de los componentes STL originales. Son controles muestreados, no una garantía Hausdorff global ni una prueba de edición Move face en Onshape.

## Cambios implementados

- `revolucion_verificada.py`: bandas conexas con giro real de normales y cobertura angular mínima de 300°, verificadas contra vértices y centroides con máximo local ≤0,011 mm y sin superar el límite local previo del constructor. Se preservan escalones y cambios de inclinación. Una prueba girada comprueba el reconocimiento desde un eje detectado; un hexágono subdividido verifica que no se redondean polígonos mecánicos.
- Solo se intenta esta alternativa en STEP ya aceptados, muy fragmentados en planos, sin B-splines y con malla moderada. Se exige reducción de caras ≥15 %, controles completos y máximos/p95 densos globales no mayores. Se acotan también las diferencias de caja, volumen y tolerancias CAD respecto al STEP inicial. Si falla cualquier control se conserva el resultado anterior. El núcleo `motor_superficies` sigue idéntico a R3.
- `topologia_vertices.py`: examina el enlace de cada vértice. Un STL cerrado por aristas puede unir abanicos incompatibles en un punto. 6558, Dimensiones tambien y Pieza_Nueva_Detenida contienen respectivamente 33, 14 y 54 vértices no manifold; ahora se rechazan en aproximadamente 1,2 s antes de gastar minutos en CAD. **Diagnóstico temprano no equivale a reparación.** Los bordes abiertos se distinguen de esos pinzamientos para conservar la compatibilidad del preprocesado histórico.
- Se permite la recuperación ya validada hasta 60000 triángulos de entrada, utilizando los mismos controles de reducción y referencia original. Antes un salto apenas por encima de 20000 podía excluir estrategias; ampliar esa elegibilidad no arregla una topología defectuosa.
- La medición histórica CAD→STL contrasta y proyecta al B-Rep exacto las muestras teseladas sospechosas antes de acusar un defecto del STEP. No se desplazan las muestras del STL original ni se modifica el STEP; el control denso obligatorio se mantiene.
- Interfaz R4 y modo predeterminado **Automático (precisión)**. El programa escoge estrategias y alternativas dentro del presupuesto estricto. Impresión 3D es opcional; busca mayor precisión cuando puede e informa del nivel realmente alcanzado y del máximo muestreado. Cambiar de modo invalida el STEP anterior.

## Precisión y modo automático

Se mantienen los límites originales del modo estricto: cotas 0,020 mm, p95 superficial original según escala, máximo 0,060 mm más el margen de preparación medido cuando existe, y error de volumen ≤0,5 %. La reparación de entrada conserva sus límites mucho menores. No se cambian escala, unidades, centros ni radios a valores nominales para hacer pasar una pieza.

Impresión 3D sigue siendo una elección explícita: cotas 0,040 mm, p95 0,040 mm y máximo total 0,080 mm incluyendo preparación. **Automático nunca activa 0,08 mm silenciosamente ante un fallo.** La precisión física declarada de una impresora no justifica aceptar agujeros cerrados, tabiques eliminados o interferencias. Para uso habitual puede dejarse Automático; Impresión expresa un presupuesto permitido distinto, no la precisión que el programa deba agotar.

## Siete STL del RAR

Se extrajeron siete STL. Se confirmó por SHA256 que cinco repiten casos previos, aunque 4600 ahora se llama Dimensiones tambien. 30383 y Pieza_Nueva_Detenida son entradas nuevas. Los originales se conservan; no se distribuyen versiones STL retocadas manualmente como solución del motor.

| STL | Resultado final | Tiempo s |
|---|---|---:|
| 30383_alternate_fixed.stl | Aceptado; fragmentación reducida parcialmente | 59.304 |
| 6558_fixed.stl | Rechazo temprano: vértices no manifold | 1.003 |
| Con fallos pero si step.stl | Rechazado; reparación CAD pendiente | 188.718 |
| Dimensiones tambien.stl | Rechazo temprano: vértices no manifold | 1.206 |
| Dimensiones.stl | Rechazado; reparación CAD pendiente | 91.383 |
| Pieza ambigua.stl | Rechazado; reparación CAD pendiente | 266.740 |
| Pieza_Nueva_Detenida.stl | Rechazo temprano: vértices no manifold | 1.208 |

Solo 1/7 tiene STEP aprobado. Esa pieza también pasaba geométricamente en R3; la mejora es la reducción parcial de fragmentación. Las otras seis siguen pendientes. Con fallos pero si step conserva interferencias CAD; Dimensiones excede desviación superficial (aprox. 0,145 mm); Pieza ambigua falla distintas alternativas por volumen, interferencias o detalle geométrico. Los tres casos de vértices incompatibles se diagnostican antes del CAD. No se atribuyen esos rechazos a un ordenador lento.

Se ensayaron uniones, separación de abanicos, el motor EasyMeshFit original aislado, escritura STEP sin p-curvas y PyMeshFix de laboratorio. No resolvieron los casos dentro de los controles. Por ejemplo, dos salidas cerradas de PyMeshFix alteraban el volumen un 8,4 % y un 30,7 %, y la tercera no produjo una malla útil. **Se descartaron**; ni la biblioteca ni sus STL forman parte del motor R4. Los JSON de esos ensayos están marcados como descartados.

## Regresión y pruebas reales

- **75 pruebas automáticas aprobadas, cero omitidas**, incluidos los fixtures reales y controles del servidor. XML y salida completos adjuntos.
- **Cubo-carrito: 4/4** en las cuatro orientaciones. La comparación certifica identidad binaria de la sección DATA STEP y de los STL reparados con la referencia previamente verificada de forma independiente; los indicadores históricos coinciden y vuelve a pasar el control denso. No se afirma haber reejecutado el verificador independiente del cubo: se aporta su prueba anterior para la misma geometría y el certificado de identidad.
- **Regresión histórica repetida: 10/12**, igual que R3, sin nuevas pérdidas respecto a las diez piezas que R3 aceptaba. Chasis y pinza siguen rechazados por los controles reforzados. La comparación R3/R4 se adjunta. **No se han superado las 14 originales**: embudo sigue aplazado por petición del usuario y conector no se ha repetido en esta fase.
- Chromium Linux: dos conversiones completas de 30383, una en Automático y otra en Impresión. Ambas alcanzan precisión estricta y producen 182 caras. Se prueba carga, progreso, resultado, descarga, invalidación al cambiar modo y Nuevo; cero errores JavaScript. El STEP descargado en impresión tiene sección DATA idéntica al STEP verificado independientemente, y se reimporta con sólido válido y cero interferencias.
- R1 original permanece intacta (47 archivos) y el núcleo de superficies no se sustituye. Las entregas anteriores permanecen disponibles. Los tiempos son del entorno Linux bajo carga de pruebas; no certifican el rendimiento del ordenador del usuario.

No se ha comprobado Windows nativo, Move face en Onshape ni impresión física K1C. El ensayo de navegador corresponde al servidor Python local; **no valida WebAssembly ni actualiza GitHub Pages**.

## Uso de la entrega y trabajo pendiente

Extraer el ZIP completo en una carpeta nueva. Ejecutar `Instalar_Entorno.bat` y luego `Iniciar.bat` en la raíz. Se abre `http://127.0.0.1:8768`, encabezado R4. El programa completo está en `Visor_experimental_fuentes`; leer `LEEME.txt` y `GUIA_REPRODUCIR.md`. Windows requiere Python de 64 bits y continúa pendiente de ensayo nativo.

Se entregan fuentes completas, archivos modificados respecto de R3, patch, material de prueba, STEP validados, registros, capturas y manifiesto SHA256. No instalar archivos aislados sobre R2/R3 como actualización estable. Falta reparar las seis entradas rechazadas, reducir más los parches sin perder detalle, resolver chasis/pinza y completar las puertas pendientes antes de certificar una versión estable.
