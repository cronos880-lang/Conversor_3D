# perfeccion_Visualizador R2 — avance experimental

La primera de las tres piezas nuevas, Fallo_Dimensional.stl, se repara y convierte
con verificación independiente. Pieza ambigua.stl y 4600_fixed.stl siguen pendientes
de un STEP que supere todas las puertas. No es una versión estable terminada.
Consultar ../INFORME_RESULTADOS.md y las evidencias reales de esta entrega.

Se conservan los límites geométricos: caja 0,020 mm, volumen 0,5 %, p95
0,020–0,030 mm según la escala histórica, máximo observado 0,060 mm.
La inspección densa y la comprobación avanzada de interferencias añaden motivos
de rechazo; no autorizan un resultado porque simplemente abra en un programa.
Los resultados son muestreados, no una garantía Hausdorff global.

La unión de cuerpos se contrasta con una referencia poliédrica OCC independiente.
La cancelación plana solo elimina superficies opuestas que coinciden exactamente,
sin inventar ni mover vértices. No rellena cavidades ni agujeros funcionales.
La normalización numérica de contactos exige contacto/solapamiento preexistente;
no une cuerpos separados por cercanía.

La ruta de construcción precisa se permite tras reparación verificada y hasta
12.000 triángulos. Las entradas históricas sanas conservan sus estrategias.
Se han repetido las 12 piezas que ya convertían y los cuatro cubo-carrito.
El embudo queda aplazado por indicación del propietario. El conector agotaba
900 segundos en la referencia y no se repite aquí. No se afirma 14/14.

Windows nativo, Onshape Move face y el conversor WebAssembly no están validados
por estas pruebas del Visor Python. El HTML del Visor permanece idéntico.
Usar esta carpeta independiente; puerto experimental 8766. No sobrescribir R1.
