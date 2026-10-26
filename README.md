# Avance del motor después de R7 · 26/10/2026

[Informe, código y STEP verificados](./entregas/avance_motor_post_R7_20261026/README.md).

El preprocesador ya convierte Lego 4×2, soporte móvil y PEGS con controles geométricos independientes y sin ampliar tolerancias. No se publica una nueva versión: Bancada_Motor pierde sus superficies CAD al pasar a recuperación facetada. Las 21 conversiones de regresión terminan, con 20 DATA STEP idénticos a R7; el cubo conserva sus cuatro variantes. Hay 144 pruebas distintas aprobadas. El informe distingue pruebas aprobadas, entradas fuera de calibración y límites de recursos.

R7 continúa siendo la última entrega del programa. Las líneas de 6558 en Onshape siguen pendientes y main no se modifica. El estudio externo anterior queda como antecedente: la medición corregida contra la frontera completa detecta que los STL 11 y 16 exceden la calibración de entrada. Consultar el nuevo informe para los resultados actuales.

---

# Batería externa de R7 · 26/10/2026

[Descargar 20 piezas para probar](./entregas/bateria_independiente_R7_20261026/Piezas_para_probar_R7.zip?raw=true) · [Resultados y fallos encontrados](./entregas/bateria_independiente_R7_20261026/INFORME_CAPACIDAD_R7.md) · [Kit reproducible completo](./entregas/bateria_independiente_R7_20261026/Bateria_independiente_R7.zip?raw=true).

Se han contrastado veinte geometrías externas con su CAD original: dieciocho entradas sanas pasan, una placa requiere repetir su discretización y después pasa como entrada problemática, y el barrido spline 17 revela un falso positivo: R7 aprueba un STEP con autointersección CAD. No se debe dar esa salida por correcta. El informe conserva los intentos excluidos, las reparaciones y los rechazos por separado.

Este material sirve para probar la R7 que ya tienes. **El motor y sus tolerancias siguen intactos; no es una actualización del programa.** El siguiente desarrollo debe cerrar el falso positivo y reducir las salidas con miles de facetas. La batería no valida Windows nativo ni la web WebAssembly de main.

---

# Entrega experimental del Visor R7

[Descargar el ZIP completo de R7](./entregas/perfeccion_Visualizador_R7/perfeccion_Visualizador_R7_EXPERIMENTAL.zip?raw=true) · [Resultados reales y límites](./entregas/perfeccion_Visualizador_R7/INFORME_RESULTADOS.md).

Este ZIP incluye `Visor_experimental_fuentes`, los lanzadores, las pruebas y el material. Extraer todo en una carpeta nueva; ejecutar `Instalar_Entorno.bat` y después `Iniciar.bat`. Requiere Python 3.12 de 64 bits. Encabezado R7 experimental, puerto 8771; Windows nativo pendiente de prueba.

La entrega recupera 6558, Pieza Nueva, Dimensiones y Con fallos pero si step. También desbloquea el conector en el motor completo: 461 s frente al timeout previo de 2300 s. La nueva ruta mantiene las curvas facetadas y conserva la prioridad del motor CAD anterior. Cubo 4/4, regresión 12/12 y 123 pruebas aprobadas, sin relajar las tolerancias. El informe detalla los casos aún rechazados y las pruebas pendientes. Esta aplicación experimental Python es independiente del conversor WebAssembly descrito a continuación y no modifica la web de main.

---

# Conversor 3D · STL → STEP

[Abrir el conversor en el navegador](https://cronos880-lang.github.io/Conversor_3D/) · [Estado del despliegue](https://github.com/cronos880-lang/Conversor_3D/actions/workflows/pages.yml)

El enlace público requiere que el despliegue de GitHub Pages termine correctamente. No se ha podido confirmar ese estado desde el entorno de desarrollo.

Interfaz HTML y conversión CAD **íntegramente en el navegador**. Sin instalaciones, Python, cuentas adicionales ni subida de archivos a un servidor. Abre el enlace de GitHub Pages que aparece en **Deployments → github-pages** cuando el despliegue esté completado.

1. Abre la web y selecciona tu STL.
2. Gira arrastrando, acerca con la rueda y desplaza con el botón derecho.
3. Selecciona las unidades y pulsa **Convertir y descargar STEP**.

El motor CAD descarga unos 22 MB al convertir por primera vez. Los archivos permanecen en el navegador. Puedes cancelar una conversión.

## Alcance real

Genera sólidos B-rep STEP con Open CASCADE compilado a WebAssembly. Valida la malla, une caras coplanares, exporta STEP, vuelve a abrirlo y comprueba validez y volumen antes de descargar.

**No reconstruye el historial paramétrico, las cotas ni las curvas originales.** Las superficies curvas conservan las facetas del STL. No se garantiza una conversión perfecta de cualquier malla ni se ha validado la importación en Onshape o Autodesk.

Límites: 20 MB, 20.000 triángulos; malla cerrada y con orientación coherente, sin caras degeneradas. Se rechazan componentes con cajas envolventes superpuestas, incluidas envolventes anidadas, para evitar rellenar cavidades por error. Esto puede rechazar algunas piezas válidas. Las comprobaciones no detectan necesariamente todas las autointersecciones. El STL no declara unidades: elige las correctas. El STEP se exporta en milímetros; el visor no altera las coordenadas.

## Publicación

Cada push a `main` ejecuta `.github/workflows/pages.yml` para publicar `index.html` y `static/` en GitHub Pages. El workflow intenta habilitar Pages. Si GitHub no permite activarlo con el token de Actions, un administrador debe elegir **Settings → Pages → Source: GitHub Actions**. La disponibilidad de Pages para repositorios privados depende del plan de GitHub. Un archivo guardado en GitHub no es por sí solo una web publicada; el enlace solo funciona tras un despliegue correcto.

## Desarrollo

No hay compilación ni dependencias npm para ejecutar la aplicación. Sirve este directorio con cualquier servidor HTTP estático; por ejemplo, `python -m http.server 8010`. Abrir el HTML mediante `file://` no permite cargar los módulos y el motor WebAssembly.

Las pruebas de navegador están en `tests/`. Se verificaron 11 casos del motor WebAssembly: caja, cilindro, esfera, varias piezas, toro, unidades en centímetros y pulgadas, repetición, y rechazo de malla abierta, envolventes anidadas y datos inválidos. Los STEP se reimportan con Open CASCADE independiente y se comprueba volumen y validez. Requieren herramientas de desarrollo; no son necesarias para usar la web. El motor se ejecuta en un Worker independiente que se destruye al terminar o cancelar para liberar memoria.

## Componentes de terceros

- Three.js 0.180.0, licencia MIT incluida en `static/vendor/THREE-LICENSE`.
- replicad-opencascadejs 1.1.0, licencia LGPL-2.1 incluida en `static/vendor/OPENCASCADE-LICENSE`. Distribución original: https://www.npmjs.com/package/replicad-opencascadejs . El JavaScript y el WebAssembly se conservan como archivos separados y reemplazables, sin modificaciones.
