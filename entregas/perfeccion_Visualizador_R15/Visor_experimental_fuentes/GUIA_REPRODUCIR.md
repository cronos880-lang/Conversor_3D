# Reproducir R15

Extrae el ZIP completo en una carpeta nueva, abre `Iniciar.bat` y comprueba el
encabezado **R15 experimental** y el puerto **8779**. Puedes seleccionar el entorno
CAD de tu R14 o instalar otro con `Instalar_Entorno.bat` y Python 3.12 x64.

Conserva R14 en otra carpeta. Usa el mismo STL y **Automático (precisión)** en ambas
versiones. Descarga cada STEP y consulta el diagnóstico desde el Visor o abre
`Abrir_Registros.bat`. Para la nueva ruta, el diagnóstico conserva la evidencia
`r15_nucleo`, la geometría medida, tres resoluciones y la prueba de material.
El informe principal enumera qué resultados se esperan en cada pieza de referencia.

Para reproducir por consola con el Python del entorno CAD preparado:

```text
python motor_v2.py "entrada.stl" "resultado.step"
```

La última línea es el resultado JSON; conserva también el registro `.motor.log`.
El informe `.r15_nucleo.json` sólo acredita el STEP cuyo SHA-256 contiene. Cambiar
entrada, STEP, perfil, petición, código o dependencias impide reutilizar el control.

Para las pruebas de desarrollo se necesitan `requirements_pruebas.txt` y las
muestras externas indicadas en `Resultados_pruebas/PROTOCOLO.json`. Los tests
nuevos del índice, ajuste de perfiles y certificados se incluyen en las fuentes.
Las pruebas del núcleo se ejecutan con su carpeta `motor_superficies` en la ruta
Python; no se mezclan sus módulos con el motor histórico ya cargado.

Los STEP deben reabrirse en frío. Arrancar la interfaz no demuestra una conversión.
No se afirma validación de Windows nativo, Onshape o K1C desde Linux.
