# Datos mínimos de regresión R5

`r5_regression.zip` conserva sólo las seis entradas utilizadas por dos pruebas
del reparador histórico: dos STL de entrada, sus resultados y sus diagnósticos.
Cada archivo es idéntico byte a byte al de la entrega R5 original; no hay piezas
nuevas ni cambios de tolerancias. El manifiesto registra tamaños, SHA-256 y
el commit del que se recuperó la procedencia completa.

El ejecutor `visor/scripts/run_legacy_tests.py` comprueba los hashes y extrae
únicamente esas entradas a un directorio temporal. Ya no necesita mantener la
entrega completa R5 en la rama activa. El original sigue recuperable en Git.

Esta carpeta queda fuera del ZIP de producto: el constructor sólo empaqueta
las carpetas fuente declaradas. Los fixtures se utilizan desde el repositorio
completo y no se duplican en las entregas de R20.
