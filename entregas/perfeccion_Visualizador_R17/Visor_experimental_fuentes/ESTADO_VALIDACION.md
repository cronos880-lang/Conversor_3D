# R17 experimental — estado real de validación

Body: 11.667 caras planas de R16 pasan a 426 caras (5 cilindros, 3 conos y 418 planos); se conservan los nueve rebajes inferiores. Máximo observado: 0,005650 mm. Los planos restantes incluyen las paredes de los grabados originales.

La guía ranurada conserva las 248 caras planas y el DATA STEP de R16. Su reconstrucción compacta fue rechazada; este caso sigue pendiente.

405 pruebas aprobadas y cuatro omitidas con motivo identificado. 23 conversiones CLI y dos conversiones completas desde Chromium, incluida descarga y lectura del STEP. Las 19 conversiones de regresión conservan la geometría R16 y no empeoran sus métricas. El cubo-carrito y tres giros pasan la conversión completa. Se convierten 13 de las 14 geometrías originales: el embudo sigue aplazado por petición del usuario. El preprocesamiento de las 14 conserva los bytes de las entradas sanas.

Perfiles, función de calidad y 16 archivos de validación sin cambios respecto a R16. La sustitución de facetas por curvas añade una aproximación medida en Body, dentro del perfil Precisión existente; no equivale al error cero de una copia facetada.

Pruebas ejecutadas en Linux, CadQuery 2.8 / OCP 7.9.3.1. Windows nativo, importación en Onshape y prueba física K1C pendientes. Consulte INFORME_RESULTADOS.md en la carpeta superior y Resultados_Pruebas para las evidencias completas. No se promete reconstrucción universal de STL.
