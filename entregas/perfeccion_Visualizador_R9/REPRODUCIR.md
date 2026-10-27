# Reproducir las pruebas de R9

Extrae el programa y la auditoría uno junto a otro, como carpetas `programa` y `auditoria`. Usa Python 3.12 con las dependencias del Visor; para los tests instala además `pytest` y `httpx` de `requirements_pruebas.txt`.

```
python auditoria/herramientas/reproducir_pruebas.py --motor programa/Visor_experimental_fuentes --material-r7 auditoria/material_pruebas --banco-r7 auditoria/banco_negativo_R7 --xml pruebas.xml
python auditoria/herramientas/reproducir_regresion.py --motor programa/Visor_experimental_fuentes --auditoria auditoria --salida resultados_repetidos
```

El protocolo comprueba las huellas de las fuentes y de cada entrada. La repetición por CLI no se presenta como prueba de interfaz; el registro de esta entrega identifica qué conversiones se ejecutaron mediante Chromium. Los evaluadores R7 y M1 son copias inmutables para contrastes independientes.

Los STL recientes están en `entradas_recientes`. Octogon y Barrera_Lego sólo se recibieron como STEP y no se han vuelto a convertir. La inspección de los nueve STEP de R8 está separada de las pruebas de R9. El intento de compactar la llanta a38 caras fue descartado por topología; no forma parte de los resultados aprobados.

Windows nativo, Onshape y K1C permanecen pendientes de prueba en esos entornos.
