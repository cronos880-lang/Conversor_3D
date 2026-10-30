# Visor completo para Windows — R12 experimental

[**Descargar R12 completa**](./entregas/perfeccion_Visualizador_R12/perfeccion_Visualizador_R12_EXPERIMENTAL_COMPLETA.zip?raw=true) · [Informe de resultados reales](./entregas/perfeccion_Visualizador_R12/INFORME_RESULTADOS.md) · [Comparar Technic](./entregas/perfeccion_Visualizador_R12/R12_TECHNIC_PARA_COMPARAR.zip?raw=true)

Extrae todo y abre **Iniciar.bat**. Incluye **Visor_experimental_fuentes**. Python 3.12 x64; puede reutilizar un entorno compatible anterior. Encabezado **R12 experimental**. Mantén **Automático (precisión)** y conserva R11.

Technic pasa de **2.044 a 845 caras**, con validación CAD y contra el STL original. Las 13 piezas históricas probadas y el cubo con sus tres giros conservan exactamente la geometría R11. Bancada y maneta mantienen R11; no se declara una mejora nueva en ellas. Embudo continúa aplazado. Windows nativo y Onshape siguen pendientes de prueba externa.

La auditoría incluye fuentes, entradas, registros y reproducción. Los archivos modificados se entregan aparte; usa el ZIP completo para probar el programa.

[Descargar y reunir la auditoría completa](./entregas/perfeccion_Visualizador_R12/DESCARGAR_AUDITORIA.md). El programa completo continúa en un único ZIP.

Si descargas el repositorio entero de esta rama, entra en **entregas/perfeccion_Visualizador_R12** y abre allí **Iniciar.bat**. La web y las versiones anteriores se conservan.

---

# Visor completo para Windows · R11 experimental

[**Descargar R11 completa**](./entregas/perfeccion_Visualizador_R11/perfeccion_Visualizador_R11_EXPERIMENTAL_COMPLETA.zip?raw=true) · [**Comparar las tres mejoras R10/R11**](./entregas/perfeccion_Visualizador_R11/R11_BANCADA_MANETA_Y_GRAPA_PARA_COMPARAR.zip?raw=true)

Extrae todo en una carpeta nueva y abre **Iniciar.bat**. Incluye `Visor_experimental_fuentes`. Si descargas el repositorio entero, entra en `entregas/perfeccion_Visualizador_R11` y abre allí Iniciar.bat. Puede reutilizar un entorno compatible de R7, R8, R9 o R10 sin modificarlo. Python 3.12 x64. Encabezado **R11 experimental**, puerto **8777**. Mantén **Automático (precisión)**.

La **maneta pasa de 9.351 a 36 caras**, con cinco cilindros y dos superficies de revolución. La **bancada pasa de 1.896 a 239**, con 25 cilindros y 14 superficies de extrusión. Se miden los perfiles sobre el STL original; sólo se reemplaza el resultado anterior después de superar los controles geométricos y CAD originales. La bancada conserva 50 caras B-spline. No se promete recuperar el diseño paramétrico ni mejorar todos los STL.

**280 pruebas automáticas y 24 conversiones aprobadas**, incluidas nueve conversiones reales por navegador. Sobre el paquete extraído pasan además **52 pruebas** y una conversión/descarga real. El cubo-carrito y sus giros están incluidos. Los dos objetivos y Grapa pasan también el evaluador R10 congelado. Grapa mejora de 622 a 20 caras, con dos cilindros y ocho extrusiones. Embudo continúa aplazado; no se declara 14/14. **Windows nativo, Onshape y K1C no se han ejecutado aquí.**

[Informe de resultados reales](./entregas/perfeccion_Visualizador_R11/INFORME_RESULTADOS.md) · [Tabla CSV](./entregas/perfeccion_Visualizador_R11/RESULTADOS_REGRESION.csv) · [Verificación del paquete](./entregas/perfeccion_Visualizador_R11/VERIFICACION_PAQUETE.json)

- [STEP de bancada](./entregas/perfeccion_Visualizador_R11/STEP_PARA_PROBAR/Bancada_Motor_R11.step?raw=true), [maneta](./entregas/perfeccion_Visualizador_R11/STEP_PARA_PROBAR/maneta_R11.step?raw=true) y [Grapa](./entregas/perfeccion_Visualizador_R11/STEP_PARA_PROBAR/Grapa_R11.step?raw=true).
- [Archivos modificados](./entregas/perfeccion_Visualizador_R11/perfeccion_Visualizador_R11_ARCHIVOS_MODIFICADOS.zip?raw=true) y [parche desde R10](./entregas/perfeccion_Visualizador_R11/CAMBIOS_DESDE_R10.patch).
- [Auditoría y reproducción](./entregas/perfeccion_Visualizador_R11/perfeccion_Visualizador_R11_AUDITORIA.zip?raw=true).
- [Todos los STEP y registros](./entregas/perfeccion_Visualizador_R11/perfeccion_Visualizador_R11_RESULTADOS_STEP.zip?raw=true).

R11 es una copia experimental independiente. Las versiones anteriores y la web de main se conservan.

---

# Visor completo para Windows · R10 experimental

[**Descargar R10 completa**](./entregas/perfeccion_Visualizador_R10/perfeccion_Visualizador_R10_EXPERIMENTAL_COMPLETA.zip?raw=true) · [**Comparar el tirante R9/R10**](./entregas/perfeccion_Visualizador_R10/R10_TIRANTE_PARA_COMPARAR.zip?raw=true)

Extrae todo en una carpeta nueva y abre **Iniciar.bat**. Incluye `Visor_experimental_fuentes`. Si descargas todo el repositorio con Code → Download ZIP, entra en `entregas/perfeccion_Visualizador_R10` y abre allí Iniciar.bat. Puede reutilizar el entorno de R7, R8 o R9 sin modificarlo. Encabezado **R10 experimental**, puerto **8776**. Python 3.12 de 64 bits.

El tirante pasa de **13.122 caras planas a 22 caras**, con diez cilíndricas y dos superficies de revolución. La nueva reconstrucción sólo se intenta tras el rechazo de las rutas anteriores; mantiene los mismos controles geométricos, CAD exacto, BOP, material, cilindros y tres fronteras finas CGAL. La bancada y la maneta conservan su resultado R9 y siguen pendientes de mejora. No se promete una mejora en todas las piezas ni mayor velocidad.

[Informe de resultados reales](./entregas/perfeccion_Visualizador_R10/INFORME_RESULTADOS.md) · [Tabla CSV](./entregas/perfeccion_Visualizador_R10/RESULTADOS_REGRESION.csv) · [Verificación del paquete](./entregas/perfeccion_Visualizador_R10/VERIFICACION_PAQUETE.json) · [STEP del tirante](./entregas/perfeccion_Visualizador_R10/STEP_PARA_PROBAR/Tirante_R10.step?raw=true)

24 conversiones y 249 pruebas automáticas aprobadas; 64 pruebas adicionales pasan sobre la copia extraída, con arranque, conversión y exportación reales. Incluye cubo-carrito y sus tres giros; Embudo continúa aplazado, por lo que no se declara 14/14. **Windows nativo, Onshape y K1C no se han ejecutado aquí.**

Material para desarrollo y revisión:

- [Auditoría y reproducción](./entregas/perfeccion_Visualizador_R10/perfeccion_Visualizador_R10_AUDITORIA.zip?raw=true).
- [Todos los STEP y registros](./entregas/perfeccion_Visualizador_R10/perfeccion_Visualizador_R10_RESULTADOS_STEP.zip?raw=true).
- [Archivos modificados](./entregas/perfeccion_Visualizador_R10/archivos_modificados), [parche desde R9](./entregas/perfeccion_Visualizador_R10/CAMBIOS_DESDE_R9.patch) y [reproducción](./entregas/perfeccion_Visualizador_R10/REPRODUCIR.md).

R10 es una copia experimental independiente; las versiones anteriores y la web de main se conservan.

---

# Visor completo para Windows · R9 experimental · 27/10/2026

[**Descargar R9 completa**](./entregas/perfeccion_Visualizador_R9/perfeccion_Visualizador_R9_EXPERIMENTAL_COMPLETA.zip?raw=true) · [**STEP de llanta y Lego para comparar**](./entregas/perfeccion_Visualizador_R9/R9_CILINDROS_PARA_COMPARAR.zip?raw=true) · [Informe real](./entregas/perfeccion_Visualizador_R9/INFORME_RESULTADOS.md)

Extrae todo en una carpeta nueva y abre **Iniciar.bat**. Incluye `Visor_experimental_fuentes` y puede reutilizar el entorno de R7 o R8 sin modificarlo. Si descargas el repositorio entero mediante Code → Download ZIP, entra en `entregas/perfeccion_Visualizador_R9` y abre allí Iniciar.bat. Encabezado **R9 experimental**, puerto **8775**. Python 3.12 de 64 bits.

La llanta pasa de **4.195 caras planas a 53 caras** y conserva sus quince regiones cilíndricas confirmadas. Lego4×2 pasa de **1.692 a 1.149 caras**, con doce caras cilíndricas y ocho cavidades conservadas; otras zonas siguen facetadas. La reconstrucción mantiene los límites geométricos originales y exige CAD exacto, BOP y tres mallados finos en sus rutas adicionales.

**233 pruebas automáticas, 21/21 conversiones principales y tres recientes adicionales aprobadas.** Cubo-carrito y sus tres giros incluidos; trece de las catorce históricas, con Embudo aplazado por el usuario. [Auditoría, fuentes y todos los STEP](./entregas/perfeccion_Visualizador_R9/README.md).

**Windows nativo, Onshape y K1C siguen pendientes de prueba.** No se declara resuelto el defecto visual de 6558 en Onshape ni una reconstrucción analítica para todas las piezas. Se conserva R8, R7 y la web de main.

---

# Visor completo para Windows · R8 experimental · 27/10/2026

[**Descargar R8 completa**](./entregas/perfeccion_Visualizador_R8/perfeccion_Visualizador_R8_EXPERIMENTAL_COMPLETA.zip?raw=true) · [Resultados reales y límites](./entregas/perfeccion_Visualizador_R8/INFORME_RESULTADOS.md) · [Auditoría y STEP](./entregas/perfeccion_Visualizador_R8/README.md)

Extrae todo en una carpeta nueva y abre **Iniciar.bat**. Incluye `Visor_experimental_fuentes`. Si descargas el repositorio entero mediante **Code → Download ZIP**, entra en `entregas/perfeccion_Visualizador_R8` y abre allí **Iniciar.bat**. Puede reutilizar el entorno de R7 sin modificarlo; si necesitas instalar uno, ejecuta `Instalar_Entorno.bat` con Python 3.12 de 64 bits. Encabezado R8, puerto 8772.

21/21 conversiones de regresión y 213 pruebas automáticas aprobadas, sin relajar tolerancias. Incluye el cubo-carrito y tres giros; se probaron trece de las catorce piezas históricas, con Embudo aplazado por petición del usuario. Pinza conserva diez cilindros y reduce caras de 2.144 a 448; Bancada conserva quince cilindros y corrige encuentros de contornos. Se exige control CAD exacto del STEP exportado, además de geometría y BOP.

En algunas piezas la recuperación genera más caras; no se promete menor triangulación ni mayor velocidad en todos los casos. **Windows nativo y la revisión visual de 6558 en Onshape siguen pendientes.** La validación real se ejecutó en Linux y Chromium. Esta copia experimental no modifica R7 ni el conversor web de main.

---

# Avance del motor después de R7 · 26/10/2026

[Informe, código y STEP verificados](./entregas/avance_motor_post_R7_20261026/README.md).

El preprocesador ya convierte Lego 4×2, soporte móvil y PEGS con controles geométricos independientes y sin ampliar tolerancias. No se publica una nueva versión: Bancada_Motor pierde sus superficies CAD al pasar a recuperación facetada. Las 21 conversiones de regresión terminan, con 20 DATA STEP idénticos a R7; el cubo conserva sus cuatro variantes. Hay 144 pruebas distintas aprobadas. El informe distingue pruebas aprobadas, entradas fuera de calibración y límites de recursos.

En ese avance R7 seguía siendo la última entrega del programa. Las líneas de 6558 en Onshape siguen pendientes y main no se modifica. El estudio externo anterior queda como antecedente: la medición corregida contra la frontera completa detecta que los STL 11 y 16 exceden la calibración de entrada. Consultar el nuevo informe para los resultados actuales.

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
