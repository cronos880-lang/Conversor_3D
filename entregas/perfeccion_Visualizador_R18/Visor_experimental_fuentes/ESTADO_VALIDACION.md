# R18 experimental — estado real de validación

Flame: 1.099 caras planas pasan a 422 caras, con un cilindro real, vaciado profundo y nueve grabados conservados. Base: 13.609 planos de R17 reproducida pasan a 463 caras, con ocho cilindros, diez conos y cuatro refuerzos conservados. Máximos observados: 0,001484 y 0,005532 mm. Son mediciones muestreadas, no una garantía global absoluta.

Body conserva exactamente el DATA STEP del archivo aportado por el usuario. 423 pruebas aprobadas, cuatro omitidas con motivo y cero fallos. 33 conversiones CLI y tres conversiones reales con descarga desde Chromium. 25 conversiones de regresión mantienen la geometría R17 y no empeoran sus métricas; ocho controles aplican efectivamente la nueva ruta. El cubo-carrito y tres giros pasan completos; se convierten 13 de las 14 geometrías originales. El embudo sigue aplazado por petición del usuario. El preprocesamiento de los 14 STL conserva las entradas sanas.

Los perfiles, la función de calidad y 16 archivos de validación no cambian. La nueva construcción incluye resolución numérica de uniones casi coincidentes; no modifica los límites de aceptación. Se entrega una familia acotada, no reconstrucción universal.

Pruebas en Linux, CadQuery 2.8 / OCP 7.9.3.1. Windows nativo, importación en Onshape y prueba física K1C pendientes. Consulte INFORME_RESULTADOS.md en la carpeta superior y Resultados_Pruebas para las evidencias.
