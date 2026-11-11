# Conversor 3D: aplicación web y Visor para Windows

Este repositorio contiene dos productos distintos y un desarrollo incremental
del Visor. Sus motores y sus comprobaciones no son intercambiables.

| Componente | Ubicación | Alcance |
| --- | --- | --- |
| Conversor web | [index.html](index.html), `static/` | HTML, JavaScript y WebAssembly. Trabaja en el navegador; las curvas conservan las facetas del STL. |
| Visor completo R19 experimental | [Entrega histórica](entregas/perfeccion_Visualizador_R19/LEEME_PRIMERO.txt) | Aplicación con interfaz local y motor Python/OCP. Fuentes y validadores congelados. |
| Desarrollo sobre R19 | [visor/](visor/README.md) | Reconstrucción opcional con contornos compartidos, evaluación independiente y certificado final completo. No es una nueva entrega publicada. |

## Visor R19 ya publicado

[ZIP histórico R19 completo](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R19/entregas/perfeccion_Visualizador_R19/perfeccion_Visualizador_R19_EXPERIMENTAL_COMPLETA.zip?raw=true)
· [Resultados de R19](entregas/perfeccion_Visualizador_R19/INFORME_RESULTADOS.md)
· [Arquitectura R19](entregas/perfeccion_Visualizador_R19/ARQUITECTURA_R19.md)

Descomprimir en una carpeta independiente y seguir su `LEEME_PRIMERO.txt`.
La entrega histórica requiere su entorno CAD; no incluye un runtime portable.
El trabajo actual conserva ese ZIP, sus lanzadores y la instalación anterior.
R18 y las demás entregas se mantienen en sus directorios y ramas.

## Desarrollo actual del Visor

Rama `desarrollo/hoja-ruta-visor`, código en `visor/`. La identidad de desarrollo
se define en un único módulo; no se anuncia otra versión R numerada.

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

No se crean ZIPs, etiquetas, releases ni nuevas publicaciones de producto durante
este desarrollo. El constructor sólo prepara una carpeta nueva de prueba; una
entrega futura requiere acuerdo y cumplir las condiciones de sus componentes.
