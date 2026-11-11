# Visor en desarrollo sobre R19

Este directorio contiene el desarrollo incremental del Visor completo para
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

La batería histórica requiere cuatro raíces de importación; el script las
configura en su proceso aislado. No sustituir módulos con igual nombre de las
copias congeladas ni ejecutar pytest sobre todas las entregas a la vez.

`python -m conversor3d propose referencia.step candidato_nuevo.step` sólo
construye un candidato pendiente de validación. No sustituye el STEP final.
La hoja de ruta y sus comprobaciones están en `ROADMAP.md`.

Para el usuario Windows, el constructor del punto 7 prepara una carpeta con
Python y sus dependencias, sin configuración manual al abrirla. Véase
`docs/PORTABLE_WINDOWS.md`. No se ha publicado una nueva versión.
