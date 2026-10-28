# Reproducción de R10

Extrae el programa y la auditoría como carpetas hermanas `programa` y `auditoria`.
Usa Python 3.12 y las dependencias bloqueadas del Visor; para pytest instala además `requirements_pruebas.txt`.

```
python auditoria/herramientas/reproducir_pruebas.py --motor programa/Visor_experimental_fuentes --material-r7 auditoria/material_pruebas --banco-r7 auditoria/banco_negativo_R7 --xml pruebas.xml
python auditoria/herramientas/reproducir_regresion.py --motor programa/Visor_experimental_fuentes --auditoria auditoria --salida resultados
```

La herramienta repite las conversiones por CLI; el registro entregado distingue CLI y navegador reales. No implica una prueba de Windows nativo ni de WebAssembly. Los evaluadores previos se conservan para los contrastes independientes. Embudo está aplazado.
