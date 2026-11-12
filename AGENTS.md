# Instrucciones del proyecto

## Ámbito de los productos

El conversor web de `index.html` y `static/` es distinto del Visor completo
Python/OCP para Windows. El desarrollo incremental del Visor vive en `visor/`,
en la rama `desarrollo/hoja-ruta-visor`; utiliza las fuentes R19 congeladas sin
modificar sus validadores, tolerancias ni hashes. Las instrucciones estáticas
del apartado siguiente corresponden al producto web.

La entrega R20 está autorizada en la rama `perfeccion_Visualizador_R20`, con su
ZIP completo en fuentes e instalador independiente. El constructor de entrega
es `visor/scripts/build_r20.py`; no modifica las fuentes ni los ZIPs históricos.

## Versiones y fixtures conservados

Tras la limpieza autorizada, el árbol activo conserva R18, R19, R20 y la
corrección del instalador R19. Las versiones anteriores se recuperan desde Git
y sus ramas; el inventario está en `MANTENIMIENTO_VERSIONES.md`.
Las pruebas históricas usan los seis archivos originales con hashes en
`visor/test-data/r5_regression.zip`, no la entrega completa R5. Esta carpeta de
datos queda fuera de los ZIP de producto. Conservar los 357 archivos R19 y
los checksums de los paquetes R18/R19/R20 que siguen publicados.

## Conversor web y reglas de trabajo

- La aplicación debe abrirse mediante un enlace web, sin instalar programas. Mantener el flujo completamente estático con HTML, JavaScript y WebAssembly.
- El usuario autoriza guardar y publicar los cambios terminados y probados en GitHub sin confirmación adicional. No forzar pushes ni sobrescribir trabajo ajeno.
- Probar el flujo real en navegador y la lectura de los STEP exportados. No describir pruebas del antiguo backend como validación de la conversión WebAssembly.
- Mantener la interfaz en español y un uso simple.
- No presentar STEP facetado como reconstrucción paramétrica ni prometer perfección para STL arbitrarios.
- Utilizar el checkout existente; no crear worktrees salvo petición explícita.

- Entregar todas las versiones y actualizaciones solicitadas como archivos ZIP guardados en este repositorio. Dar en el chat un enlace directo con el formato `https://github.com/USUARIO/REPOSITORIO/blob/RAMA/RUTA/ARCHIVO.zip?raw=true` y comprobar que el ZIP está disponible antes de afirmar que está publicado.

## Entregas del Visor completo para Windows

- Cuando el usuario pida el Visor completo como R7 y sus versiones experimentales, trabajar en esa aplicación de escritorio con interfaz local. Las instrucciones iniciales sobre la aplicación estática corresponden al conversor web separado.
- Conservar la copia instalada y entregar cada versión experimental en una carpeta independiente, con su lanzador y su identidad de versión.
- Distinguir las pruebas reales de conversión en navegador sobre Linux de Windows nativo y de la importación en Onshape; indicar las comprobaciones pendientes.


- Mostrar la URL completa del ZIP de forma visible en el chat, terminada en `?raw=true`; es una premisa fija del proyecto reiterada por el usuario.

