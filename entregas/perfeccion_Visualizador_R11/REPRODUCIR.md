# Reproducción de R11

Extraer el programa completo como `programa` y la auditoría como `auditoria`, en la misma carpeta.
Usar Python 3.12 y las dependencias bloqueadas del programa. Añadir `requirements_pruebas.txt` para pytest.

```
python auditoria/herramientas/reproducir_pruebas.py --motor programa/Visor_experimental_fuentes --material-r7 auditoria/material_pruebas --banco-r7 auditoria/banco_negativo_R7 --xml pruebas.xml
python auditoria/herramientas/reproducir_regresion.py --motor programa/Visor_experimental_fuentes --auditoria auditoria --salida resultados
```

El primer comando ejecuta la batería completa, incluidos los nuevos perfiles medidos.
El segundo reproduce los 24 casos por CLI. Los registros de la entrega distinguen 15 conversiones
CLI y nueve conversiones reales por navegador. Las rutas absolutas de `registro_ejecucion` documentan
la ejecución original; no son dependencias del programa. El programa genera su hipótesis desde
el STL: no necesita los STEP de referencia. El evaluador R10 congelado se conserva para contrastar
los dos objetivos de forma independiente. Los evaluadores R7 se conservan para pruebas negativas.
Para repetir el contraste independiente de los objetivos (STL y STEP de la comparación):

```
python auditoria/herramientas/validar_objetivo_R10.py --auditoria auditoria --stl STEP_PARA_PROBAR/maneta_original.stl --step STEP_PARA_PROBAR/maneta_R11.step --informe maneta_control_R10.json
python auditoria/herramientas/validar_objetivo_R10.py --auditoria auditoria --stl STEP_PARA_PROBAR/Bancada_Motor_original.stl --step STEP_PARA_PROBAR/Bancada_Motor_R11.step --informe bancada_control_R10.json
```

La carpeta de investigación rechazada nunca se instala. Embudo continúa aplazado.
Windows nativo, Onshape y K1C siguen pendientes de verificación externa.
