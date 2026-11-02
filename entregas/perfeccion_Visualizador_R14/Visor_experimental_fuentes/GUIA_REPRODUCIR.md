# Reproducción R14

1. Extraer el paquete completo en una carpeta nueva. En Windows usar Python 3.12 de 64 bits, `Instalar_Entorno.bat` si es necesario y `Iniciar.bat`.
2. Mantener el perfil Automático (precisión). Cargar el STL original, convertir y exportar el STEP. El encabezado y `/version` deben indicar R14.
3. Conservar los archivos de `Registros_Conversion`: JSON principal, registro TXT/LOG y, si se aplicó la mejora, `.r14_nucleo.json` y `.r14_original.json` cuando proceda. El JSON contiene hashes de STL/STEP, errores, caras, material y tres mallados finos. Una propuesta descartada conserva el STEP anterior y su motivo.
4. Comparar las mismas entradas con R13. No confundir ausencia de aristas de triangulación con pérdida de una arista física; comprobar dimensiones, huecos y volumen al reabrir.
5. Para desarrollo, instalar las dependencias bloqueadas de `requirements.txt` en un entorno aislado y ejecutar `python -m pytest -q` desde esta carpeta; la auditoría incluye la batería adicional del núcleo, ejecutada mediante una copia de pruebas con los mismos archivos del núcleo de esta entrega. Las pruebas con fixtures externos requieren el material y las variables descritos en el ZIP de auditoría.

Las mediciones de la entrega identifican sistema y rutas. Windows nativo, Onshape y K1C deben comprobarse externamente. No se ha validado conversión WebAssembly: esta entrega es el Visor completo con backend local Python.
