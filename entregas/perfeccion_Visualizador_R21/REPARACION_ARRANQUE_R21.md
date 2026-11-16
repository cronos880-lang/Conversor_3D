# R21: corrección de arranque y herramientas conectadas

## Entrega solicitada

**ACTUALIZACIÓN para R20 con su entorno ya preparado.** Mantiene la identidad R21
experimental, revisión de lanzadores 2. No es R22 ni una nueva reconstrucción del
motor. El ZIP original R21 y las entregas R18/R19/R20 se conservan.

[Descargar ZIP corregido](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R21/entregas/perfeccion_Visualizador_R21/Conversor_3D_R21_ACTUALIZACION_LIGERA_CORREGIDA.zip?raw=true)

- 86.476 bytes; 38 archivos.
- SHA-256: `77581e99a8ac97c9da06d684c1728fed7b20eff06da5e16c58eb63d581fab3d9`.
- [Fuentes probadas](https://github.com/cronos880-lang/Conversor_3D/commit/1bf36ab9c5746b7669abc24b980b4eba47ab9c14).
- El manifiesto registra ese commit, árbol limpio y hashes de cada archivo.

Extraer TODO el ZIP en una carpeta nueva y abrir `Iniciar_R21.bat`. Conservar R20;
si se solicita localizarla, elegir la carpeta que contiene `.venv_r20`. Si el
entorno R20 no está preparado, usar su `Reparar_Entorno_R20.bat`. No extraer encima
de R20 ni de la R21 anterior. La recuperación consiste en cerrar esta copia y
abrir el lanzador anterior; no se desinstala ni se modifica R20.

## Qué se corrigió

El usuario comunicó que R21 no llegaba a abrirse, sin aportar todavía un mensaje
concreto. Al revisar el paquete se encontró una dependencia frágil: fuera de la
carpeta hermana de nombre exacto, el `.bat` exigía `py -3.12`, aunque el Python
válido de R20 existiese en otra ubicación. Las pruebas anteriores usaban esa
disposición prevista o indicaban la base explícitamente.

Los lanzadores corregidos utilizan Windows PowerShell incluido en el sistema
para localizar el entorno R20 **antes de ejecutar Python**. Buscan configuración
guardada, `CONVERSOR3D_BASE_R20` y carpetas cercanas, incluyendo nombres distintos
y la carpeta adicional que crea «Extraer todo». Si no lo encuentran, ofrecen un
selector. No necesitan `py` ni `python` globales.

La opción de ejecución de PowerShell afecta sólo al proceso que abre el lanzador;
no cambia la política de scripts de la máquina. Se verifican los mismos 357 hashes
R19 y las bibliotecas bloqueadas antes de arrancar. Los mensajes aparecen desde
el comienzo y se añaden a `datos/arranque_R21.log`; el diagnóstico mantiene abierta
la ventana. Si el servidor falla, su código de salida se conserva.

Esta corrección resuelve las condiciones de arranque descritas y probadas. Sin el
error concreto del PC no se atribuyen al mismo causas adicionales ni se garantiza
que una instalación R20 incompleta funcione.

## Validación

- Suite local: **58 aprobadas y una omitida**, esta última exclusiva de Windows.
- Integridad: 357 archivos congelados comprobados, sin errores.
- ZIP corregido final: CRC, manifiesto y hashes comprobados.
- Dos conversiones HTTP reales con el entorno R20 existente en Linux: STEP válidos
  reimportados, un sólido de 120 mm³, seis caras, material sin discrepancias, tres
  mallados y certificados con nonces distintos. R20 conserva sus bytes de versión.
- [Pruebas nativas del commit corregido](https://github.com/cronos880-lang/Conversor_3D/actions/runs/43823752713).

**Resultado nativo final: aprobado en Windows y Linux**, para el commit de fuentes
indicado. Windows: 59 pruebas actuales y 426 históricas aprobadas, 16 históricas
omitidas por sus condiciones existentes. Linux: 58 actuales aprobadas y una
omitida exclusiva de Windows, 427 históricas aprobadas y 15 omitidas.

La nueva prueba Windows pasó con extracción anidada y R20 renombrada, PATH
limitado a System32 y sin Python global. La prueba funcional del `.bat` real
también pasó con PATH limitado y la ruta R20 guardada en la configuración propia
de R21: arranque, dos conversiones, STEP reimportados válidos, certificados con
nonces nuevos y R20 intacta. El registro termina con
`R21 LIGERA: ARRANQUE, DOS CONVERSIONES Y STEP VALIDOS; R20 INTACTA`.

Estas pruebas nativas no equivalen a ejecutar el programa en el PC del usuario.
Si el servidor está abierto y el navegador no aparece, se puede abrir
`http://127.0.0.1:8785`; los errores quedan en `datos/arranque_R21.log`.

No se modifican motores, interfaz, dependencias CAD, evaluadores ni tolerancias.
Las limitaciones geométricas y los resultados de rendimiento de la primera R21
siguen descritos en [el informe original](INFORME_RESULTADOS.md).

## REA y ArtCraft / Craft Anything

**REA 6.8.0:** recuperado de la instalación local existente y conectado mediante
MCP stdio. Diagnóstico real de identidad e inventario correcto: 229 herramientas,
llamada `binary_session` e inspección del paquete R21.

**Craft Anything 0.6.1**, el repositorio ArtCraft indicado por el usuario:
descargado de su publicación oficial con SHA-256 contrastado. Se instaló aislado,
con sus licencias y avisos, sin añadir dependencias al Visor. Servidor MCP real
conectado: 323 herramientas, llamadas `core_session_show` y
`core_archives_compare` completadas. No requiere una cuenta de generación de
imágenes para estas inspecciones ni se activan servicios de pago.

La comparación de ambos ZIP con Craft Anything encontró un archivo añadido,
cinco modificados, ninguno eliminado y **32 archivos idénticos**, incluido el
código del conversor. El nuevo archivo es el bootstrap de Windows.

Estas conexiones son locales en **Linux Cloud**, mediante clientes MCP
programáticos: no se han añadido plugins nativos al catálogo del chat ni se ha
establecido acceso remoto al Windows del usuario. Instalarlas en Cloud no instala
nada en su PC. La guía describe cómo localizar y registrar los ejecutables en un
Codex CLI local, sin inventar rutas Windows.

- [Guía de conexiones y continuidad](../../visor/docs/HERRAMIENTAS_DESARROLLO.md).
- [Resumen de las conexiones verificadas](HERRAMIENTAS_CONECTADAS.json).
