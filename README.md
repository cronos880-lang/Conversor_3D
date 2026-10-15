# Conversor 3D · STL → STEP

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

Las pruebas de navegador están en `tests/`. Requieren herramientas de desarrollo; no son necesarias para usar la web. El motor se ejecuta en un Worker independiente que se destruye al terminar o cancelar para liberar memoria.

## Componentes de terceros

- Three.js 0.180.0, licencia MIT incluida en `static/vendor/THREE-LICENSE`.
- replicad-opencascadejs 1.1.0, licencia LGPL-2.1 incluida en `static/vendor/OPENCASCADE-LICENSE`. Distribución original: https://www.npmjs.com/package/replicad-opencascadejs . El JavaScript y el WebAssembly se conservan como archivos separados y reemplazables, sin modificaciones.
