# Guía para contrastar R20 mediante otro informe

Objetivo: evaluar el código y las pruebas de R20 frente a R19, diferenciando
mejoras implementadas, ensayos medidos, límites y recomendaciones futuras.
No es necesario modificar el motor para realizar esta revisión.

## Fuentes y procedencia

- Repositorio: https://github.com/cronos880-lang/Conversor_3D
- Rama de entrega: `perfeccion_Visualizador_R20`.
- Base anterior: `8cd2656`; base R19: `e105759`.
- Identidad: `visor/src/conversor3d/_version.py`.
- `R20_MANIFEST.json` del ZIP identifica commit fuente y hashes del paquete.
- `visor/frozen-r19.sha256.json` identifica los 357 archivos R19 inalterados.

## Módulos que conviene revisar

1. `geometry.py`: propuesta de planos, envolvente de curvas recortadas, protección
   de caras analíticas, intersecciones y unificación restringida.
2. `reconstruction_worker.py`, `validation.py` y `pipeline.py`: separación de
   propuesta/aceptación, conservación de referencia, certificado completo final
   y comprobación de hashes después de copiar el STEP.
3. `legacy_worker.py` y `resources/evaluator/`: frontera con R19 y evaluador
   preservado; comprobar que no se relajan límites ni se reemplaza la autoridad.
4. `cache.py`: claves por bytes y versiones, sin aceptar geometría desde caché.
5. `server.py`, `security.py` y `retention.py`: ambos endpoints, CORS/Host/Origin,
   conservación y exclusión de trabajos activos/datos ajenos.
6. Locks, instalador y `manage_environment.py`: reproducibilidad y entorno propio.
7. `THIRD_PARTY_LICENSES.md`: alcance de permisos y componentes incluidos.

Las rutas Python anteriores están dentro de `visor/src/conversor3d/` salvo donde
se indica otra ubicación. El conversor web `index.html/static/` es otro producto.

## Pruebas reproducibles

Desde el repositorio completo y su entorno Python 3.12 x64:

```console
python visor/scripts/install_dependencies.py
python -m pytest -q visor/tests
python visor/scripts/run_legacy_tests.py --xml legacy.xml
python visor/scripts/run_benchmarks.py --output resultados_nuevos --cases cylinder thin_wall small_hole
python visor/scripts/smoke_native.py --development --output smoke_nuevo
```

La batería histórica utiliza fixtures de un ZIP R5 existente en el repositorio;
esos modelos no se duplican en la entrega R20. Para esa batería hay que usar el
repositorio completo. Las pruebas nuevas, las fuentes del núcleo y el programa
sí están en el ZIP. Los directorios de salida deben ser nuevos.

## Preguntas para el informe

- ¿Las mejoras del motor están conectadas al flujo que usa la interfaz?
- ¿El STEP descargado tiene control completo y trazabilidad verificable?
- ¿Se conservan taladros, paredes finas, material y caras analíticas protegidas?
- ¿La caché o los filtros rápidos pueden aprobar una salida por sí solos?
- ¿Se distinguen tolerancia B-Rep y error respecto al STL?
- ¿Las afirmaciones coinciden con los resultados, incluyendo que Bancada sigue
  en 101 caras y que las superficies libres generales no están resueltas?
- ¿La instalación se prueba desde el ZIP extraído en Windows con espacios?

Para comparar piezas propias, emplear los mismos STL, unidades y perfil; adjuntar
conteos de caras, tiempos, certificados y lectura del STEP en el CAD de destino.
No valorar la mejora sólo por el tamaño del STEP ni por una captura de pantalla.
