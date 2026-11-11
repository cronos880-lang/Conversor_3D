# Reparación del instalador R20 — revisión 2

La captura aportada queda en `Installing collected packages`, sin error visible.
Ese mensaje por sí solo no permite distinguir trabajo lento de un bloqueo. El
instalador anterior agrupaba todos los paquetes, ocultaba el indicador de pip al
redirigir la salida y esperaba líneas nuevas sin informar durante los silencios.

## Aplicar la reparación a tu R20

1. Cierra la ventana del instalador anterior.
2. Extrae `Reparacion_Instalador_R20.zip` **dentro de tu carpeta R20 existente**,
   donde está `Iniciar_R20.bat`. Acepta sustituir los archivos del programa.
3. Ejecuta `Reparar_Entorno_R20.bat`.
4. Al aparecer `INSTALACIÓN R20 TERMINADA`, abre `Iniciar_R20.bat`.

La reparación conserva `.venv_r20`, `datos`, tus STL/STEP y los resultados. Usa
las mismas versiones y hashes: retoma lo que falta y verifica los archivos de
los paquetes ya instalados. No hace falta borrar el entorno para reintentarlo.
La revisión aparece en consola y en `Diagnostico_Entorno_R20.json`.

También se ofrece el ZIP completo corregido para una instalación nueva. El
programa sigue siendo R20; su motor CAD, tolerancias y validadores no cambian.

## Comportamiento corregido

- Muestra `PAQUETE N/TOTAL`, nombre, versión y operación en curso.
- Instala wheels con los pins y todos los hashes del lock original. Al completar
  la lista verifica la coherencia de dependencias y las bibliotecas nativas.
- Desactiva la compilación masiva de bytecode de pip.
- Comprueba presencia y tamaño de archivos a partir del `RECORD` original para
  detectar extracciones incompletas; vuelve a instalar sólo el paquete afectado.
- Durante un silencio emite actividad cada diez segundos con el tiempo real.
  No inventa un porcentaje de avance. Cada operación tiene un plazo acotado y
  un error explícito si se agota; detiene sus procesos descendientes.
- Guarda el registro al instante en `datos/instalacion_R20.log`.
- Evita dos instalaciones simultáneas sobre el mismo entorno; un cierre
  interrumpido libera el bloqueo del sistema operativo y permite reintentar.

La prueba Windows extrae el paquete en una ruta con espacios, instala y luego
simula una extracción incompleta eliminando un archivo de un paquete del entorno
temporal. Ejecuta el reparador, comprueba su recuperación y prueba arranque,
conversión HTTP, lectura STEP y certificado completo con el Python de R20.
