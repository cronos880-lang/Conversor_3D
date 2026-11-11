# R20: reparación del instalador, revisión 2

## Si ya tienes R20 extraída

[Descargar reparación pequeña](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R20/entregas/perfeccion_Visualizador_R20/Reparacion_Instalador_R20.zip?raw=true)

1. Cierra la ventana del instalador anterior.
2. Extrae el contenido del ZIP **dentro de tu carpeta R20**, donde está
   `Iniciar_R20.bat`, aceptando sustituir archivos.
3. Abre `Reparar_Entorno_R20.bat`. Al terminar, abre `Iniciar_R20.bat`.

No hay que borrar `.venv_r20` ni `datos`. El paquete sólo actualiza fuentes y
metadatos del instalador; no contiene tus modelos ni un entorno de reemplazo.
Retoma los paquetes que falten y repara los incompletos. No sirve para R19.

## Instalación nueva

[Descargar R20 completa corregida](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R20/entregas/perfeccion_Visualizador_R20/perfeccion_Visualizador_R20_EXPERIMENTAL_COMPLETA_CORREGIDA.zip?raw=true)

Extraer en una carpeta nueva y abrir `Iniciar_R20.bat`. Requiere Python 3.12 x64
e Internet, igual que la entrega original. Incluye el instalador revisión 2.

## Qué se ha corregido

La captura mostraba `Installing collected packages` sin error visible. El
instalador anterior redirigía la salida de una instalación masiva y esperaba
líneas nuevas sin mostrar actividad; la compilación de bytecode de pip seguía
habilitada. La captura sola no permite afirmar que pip se hubiera bloqueado.

La corrección instala/verifica cada pin con sus hashes, imprime `PAQUETE N/TOTAL`,
desactiva esa compilación y muestra actividad con tiempo real durante silencios.
Cada operación tiene un plazo; al agotarse se detiene su árbol y se informa del
paquete afectado. El registro se escribe inmediatamente en
`datos/instalacion_R20.log`. Un bloqueo de exclusión evita instalaciones dobles
sobre el mismo entorno y se libera al cerrar el proceso.

Se verifica el RECORD original de cada distribución, incluyendo presencia y
tamaño de archivos. La API de metadatos puede filtrar archivos ausentes; por
eso no se utiliza su lista filtrada para decidir si un paquete está completo.
Se conserva cada paquete correcto y se reinstala desde el wheel con hashes
solamente el afectado. Al final se exige pip check y los imports nativos.

## Evidencia

[CI Windows/Linux en verde](https://github.com/cronos880-lang/Conversor_3D/actions/runs/43108213969),
commit fuente `e839c5d`: 49 pruebas del desarrollo en ambos sistemas, 427
históricas/15 omitidas en Linux y 426/16 en Windows.

La prueba Windows extrajo el ZIP en una ruta con espacios, instaló un entorno
nuevo, eliminó un archivo de un paquete para simular una extracción interrumpida,
ejecutó `Reparar_Entorno_R20.bat` y comprobó su recuperación. Después pasaron
el diagnóstico, el arranque por su `.bat`, la conversión HTTP, la lectura del
STEP con su Python y el certificado completo (sólido de 120 mm³).

El ZIP completo publicado tiene exactamente el mismo SHA-256 que el probado
por Windows. La reparación por superposición también se prueba sobre la R20
original, comprobando todo el manifiesto corregido y conservando archivos de
usuario en datos y entorno. Los dos checksums están en SHA256SUMS_REPARACION.txt.

El código CAD y los 357 archivos R19 permanecen idénticos; los pins, hashes,
perfiles y tolerancias no se relajan. El programa sigue siendo R20. Se conserva
el ZIP original como registro histórico; para instalar se recomienda el corregido.
