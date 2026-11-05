# Reproducir R18 experimental

Descomprime el ZIP completo en una carpeta nueva y abre `Iniciar_R18.bat` de la carpeta superior. El programa requiere Python 3.12 de 64 bits y el entorno CAD del Visor, como R7/R17. Puedes preparar otro con `Instalar_Entorno.bat`. El encabezado debe indicar **R18 experimental** y el puerto predeterminado es **8781**. Conserva las versiones anteriores en sus carpetas.

Prueba primero `Pruebas_Curvas/Flame_Base.stl` y `Base.stl`, con el perfil Precisión predeterminado. Descarga el STEP y consulta el diagnóstico o abre `Abrir_Registros.bat`. La previsualización del Visor muestra el STL original; para juzgar las superficies reconstruidas abre el STEP descargado en tu CAD. Los STEP de referencia y las comparaciones de aristas CAD están en la carpeta superior.

La evidencia `r18_nucleo` sólo corresponde al STEP cuyo SHA-256 contiene y acredita fuente, código, perfil, dependencias, relectura, CAD exacto, tres mallados finos y material original. Las rutas anteriores se conservan cuando la nueva familia no se reconoce o no supera las comprobaciones; Body conserva la ruta R17.

Conversión por consola con el Python del entorno CAD:

```text
python motor_v2.py "entrada.stl" "resultado.step"
```

La última línea contiene el resultado JSON. Conserva `.motor.log`, `.entrada.json` y `.r18_nucleo.json` cuando exista. Cambiar STL, STEP, código, petición, perfil o dependencias impide reutilizar el control. Consulta el informe principal y `Resultados_Pruebas` para los resultados reales, muestras y variables de reproducción de la batería de desarrollo.

Arrancar la interfaz no demuestra una conversión. Windows nativo, Onshape y la impresión física K1C requieren sus propias pruebas.
