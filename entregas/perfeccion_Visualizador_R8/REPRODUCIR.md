# Reproducir R8

Descomprimir el ZIP del programa en `programa` y este ZIP en `auditoria`, dentro de la misma carpeta. La reproducción requiere las dependencias CAD de `requirements_bloqueadas.txt` y `pytest`. Los resultados originales se conservan aparte; usar un directorio de salida nuevo.

En la carpeta que contiene ambas, con Python 3.12 y el entorno CAD activo:

```console
python auditoria/herramientas/reproducir_pruebas.py --motor programa/Visor_experimental_fuentes --material-r7 auditoria/material_pruebas --banco-r7 auditoria/banco_negativo_R7 --xml nuevas_pruebas.xml
python auditoria/herramientas/reproducir_regresion.py --motor programa/Visor_experimental_fuentes --auditoria auditoria --salida repeticion_21
python auditoria/herramientas/contrastar_descarga.py auditoria/material_pruebas/stl_regresion_14/Bancada_Motor.stl resultados/navegador/Bancada_Motor.step contraste_bancada.json
```

El último control usa el evaluador R7 y el control de frontera M1 inmutables. Comprueba geometría, cilindros, material y mallado/CGAL a tres resoluciones; no reemplaza BOP. La aplicación R8 también exige BOP en frío y coherencia CAD exacta. Todos los casos se prueban en perfil Precisión. Embudo permanece aplazado.

`registro_ejecucion` conserva los lanzadores exactos usados en el entorno de referencia, con sus rutas originales. `PROTOCOLO_PORTABLE.json` y los scripts de `herramientas` permiten trasladar la batería. Los fixtures STEP defectuosos de R7 son controles negativos deliberados, no resultados aprobados.

El navegador real del registro se ejecutó con Playwright y Chromium en Linux. Los tests de lanzadores Windows verifican estructura, rutas y selección de entorno; no equivalen a ejecutar Windows nativo ni Onshape.
