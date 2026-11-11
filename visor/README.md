# Visor R20 experimental

Este directorio contiene R20, el desarrollo incremental del Visor completo para
Windows. El conversor estático del navegador permanece en la raíz y es otro
producto. Las entregas históricas de `entregas/` no se modifican.

El proponente de geometría produce candidatos; no puede aprobarlos. La validación
usa R19 congelada en un proceso independiente. No se aumentan tolerancias y un
fallo conserva la referencia validada. No se promete recuperar un historial CAD
paramétrico a partir del STL.

Desarrollo con Python 3.12 de 64 bits en un entorno propio:

```
python visor/scripts/install_dependencies.py
python -m pytest visor/tests
python visor/scripts/run_legacy_tests.py --xml resultado_legacy.xml
```

Para abrir el desarrollo: `python -m conversor3d serve`. Usa su puerto propio
definido en `_version.py`; consulta los ajustes con `python -m conversor3d config`.
Para convertir por línea de comandos:

```console
python -m conversor3d convert entrada.stl salida_nueva.step
```

La salida y su directorio de evidencias deben ser nuevos. Se conservan el STEP,
el certificado `.r19_nucleo.json` y el informe `.r19_pipeline.json`; los datos de
trabajo se mantienen por defecto. No reutilizar un certificado de otra pieza.

La batería histórica requiere cuatro raíces de importación; el script las
configura en su proceso aislado. No sustituir módulos con igual nombre de las
copias congeladas ni ejecutar pytest sobre todas las entregas a la vez.

`python -m conversor3d propose referencia.step candidato_nuevo.step` sólo
construye un candidato pendiente de validación. No sustituye el STEP final.
La hoja de ruta y sus comprobaciones están en `ROADMAP.md`.

Las fuentes históricas son una dependencia deliberada y firmada. Consulta
[FROZEN_DEPENDENCY.md](docs/FROZEN_DEPENDENCY.md) antes de interpretar una copia
como duplicado prescindible. El evaluador congelado no se refactoriza.

La entrega R20 autorizada incluye los lanzadores y un instalador con hashes,
que crea su entorno propio. Véase [la guía de uso](docs/R20_USUARIO.md),
[el informe](docs/R20_INFORME.md) y [la guía de revisión externa](docs/R20_REVISION_EXTERNA.md).
El constructor del punto 7 prepara además una carpeta de prueba con runtime
incluido; sus condiciones son distintas de las del ZIP en fuentes. Véase
`docs/PORTABLE_WINDOWS.md`.

La procedencia de las dependencias y las condiciones pendientes para una
redistribución están documentadas en [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
