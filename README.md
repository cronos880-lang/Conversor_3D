# Conversor 3D: aplicación web y Visor para Windows

Este repositorio contiene dos productos distintos y un desarrollo incremental
del Visor. Sus motores y sus comprobaciones no son intercambiables.

| Componente | Ubicación | Alcance |
| --- | --- | --- |
| Conversor web | [index.html](index.html), `static/` | HTML, JavaScript y WebAssembly. Trabaja en el navegador; las curvas conservan las facetas del STL. |
| Visor completo R19 experimental | [Entrega histórica](entregas/perfeccion_Visualizador_R19/LEEME_PRIMERO.txt) | Aplicación con interfaz local y motor Python/OCP. Fuentes y validadores congelados. |
| Visor R20 experimental | [visor/](visor/README.md) | Reconstrucción opcional con contornos compartidos, evaluación independiente y certificado final completo. Entrega autorizada para pruebas. |
| Visor R21 experimental | [Actualización ligera](entregas/perfeccion_Visualizador_R21/INFORME_RESULTADOS.md) | Rendimiento y diagnóstico, con control frío nuevo y geometría conservada. Reutiliza R20 sin modificarla. |

## Probar R21 experimental — ACTUALIZACIÓN ligera

[Descargar R21 para una R20 ya instalada](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R21/entregas/perfeccion_Visualizador_R21/Conversor_3D_R21_ACTUALIZACION_LIGERA.zip?raw=true)
· [Resultados y límites de R21](entregas/perfeccion_Visualizador_R21/INFORME_RESULTADOS.md)

El ZIP ocupa 83.795 bytes y necesita R20 con su entorno preparado. Extraerlo en
una carpeta nueva junto a R20 y abrir `Iniciar_R21.bat`; si no se localiza R20,
seleccionar su carpeta. No hay otro instalador ni bibliotecas CAD duplicadas.
Los datos R21 quedan separados; para volver a R20 basta abrir su lanzador original.

La Bancada midió 891,3 s en su primera conversión con las mejoras y 77,7 s al
repetirla: STEP idéntico y certificado nuevo. Mantiene 101 caras y tolerancia
B-Rep de `1e-7 mm`. La primera conversión difícil sigue siendo lenta y esta
entrega no reduce caras ni anuncia una precisión geométrica nueva.

## Probar R20 experimental

R20 está disponible en la rama `perfeccion_Visualizador_R20`, conservando las ramas
anteriores. El paquete completo en fuentes incluye lanzadores y un instalador
para su propio entorno Python 3.12 x64. No incorpora runtimes de terceros.
Consulta [la guía de uso](visor/docs/R20_USUARIO.md),
[el informe de avances](visor/docs/R20_INFORME.md) y
[la guía para revisión externa](visor/docs/R20_REVISION_EXTERNA.md).

[Descargar R20 completa con instalador corregido](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R20/entregas/perfeccion_Visualizador_R20/perfeccion_Visualizador_R20_EXPERIMENTAL_COMPLETA_CORREGIDA.zip?raw=true)
· [Resultados de la entrega](entregas/perfeccion_Visualizador_R20/INFORME_RESULTADOS.md)

[Reparación pequeña para R20 ya instalada](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R20/entregas/perfeccion_Visualizador_R20/Reparacion_Instalador_R20.zip?raw=true)
· [Cómo aplicarla y pruebas](entregas/perfeccion_Visualizador_R20/REPARACION_INSTALADOR.md)

La revisión 2 corrige la espera sin mensajes del instalador y recupera paquetes
incompletos conservando el entorno y los datos. Véase
[reparación del instalador](visor/docs/R20_REPARACION_INSTALADOR.md).

## Visor R19 ya publicado

[ZIP histórico R19 completo](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R19/entregas/perfeccion_Visualizador_R19/perfeccion_Visualizador_R19_EXPERIMENTAL_COMPLETA.zip?raw=true)
· [Resultados de R19](entregas/perfeccion_Visualizador_R19/INFORME_RESULTADOS.md)
· [Arquitectura R19](entregas/perfeccion_Visualizador_R19/ARQUITECTURA_R19.md)

Descomprimir en una carpeta independiente y seguir su `LEEME_PRIMERO.txt`.
La entrega histórica requiere su entorno CAD; no incluye un runtime portable.
El trabajo actual conserva ese ZIP, sus lanzadores y la instalación anterior.
R18 se mantiene como respaldo. Las entregas anteriores se han retirado del árbol
activo y siguen recuperables en sus ramas y en Git. Véase
[la limpieza y el procedimiento de recuperación](MANTENIMIENTO_VERSIONES.md).

## Desarrollo actual del Visor

El desarrollo previo está en `desarrollo/hoja-ruta-visor`; R20 permanece en
`perfeccion_Visualizador_R20` y R21 en `perfeccion_Visualizador_R21`, con código
en `visor/`. La identidad
se define en un único módulo, conservando la dependencia R19 congelada.

- [Instalación y comandos](visor/README.md).
- [Hoja de ruta y resultados por fase](visor/ROADMAP.md).
- [Interfaces de reconstrucción y validación](visor/docs/ARCHITECTURE.md).
- [Pruebas representativas y límites observados](visor/docs/BENCHMARKS.md).
- [Preparación autocontenida para Windows](visor/docs/PORTABLE_WINDOWS.md).
- [Configuración](visor/docs/CONFIGURATION.md), [dependencias y conservación](visor/docs/DEPENDENCIES_AND_RETENTION.md).
- [Procedencia y licencias](visor/THIRD_PARTY_LICENSES.md).
- [Pruebas nativas en GitHub Actions](https://github.com/cronos880-lang/Conversor_3D/actions/workflows/visor-ci.yml).

La tolerancia B-Rep sigue siendo `1e-7 mm`; el STEP elegido debe superar la
validación completa de geometría, material y mallado, conservando trazabilidad
STL/STEP/perfil/motor. Una propuesta rechazada conserva la referencia validada.
Los perfiles Precisión e Impresión y los cuatro botones se mantienen.

Resultado geométrico controlado: el caso sintético de parches planos pasa de
11 a 6 caras con validación completa; el control con taladro conserva su abertura.
En Bancada no se ha aceptado una reducción adicional sobre el STEP de 101 caras.
El caso sintético con redondeos aún puede quedar muy facetado y el loft libre
agotó su sondeo de tiempo; no se presentan como problemas resueltos.

CI ejecuta instalación, tests y conversiones reales en Windows y Linux; Windows
prueba también una carpeta portable aislada. Esto no equivale a probar el PC
del usuario ni a importar en SolidWorks, Inventor u Onshape. El conversor web
tiene sus propias pruebas en `tests/`: las pruebas del Visor no lo validan.

El usuario ha autorizado R20 experimental en un ZIP de fuentes con instalador.
La carpeta portable de prueba con todos los binarios incorporados es otra
modalidad, sujeta a la auditoría de redistribución. Se mantiene el sistema actual
de entregas en el repositorio, sin cambiar visibilidad ni reescribir historial.
