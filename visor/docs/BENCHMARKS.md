# Casos de prueba del Visor

Todos se generan con referencia CAD, sin publicar piezas nuevas del usuario:
cilindro, dos redondeos, pared de 0,15 mm, taladro de 0,3 mm, loft libre, pieza
girada y caja con seis parches B-Spline residuales. El catálogo distingue una
referencia CAD de una conversión nueva desde STL y registra el hash del STL.

Las pruebas comprueban sólidos exactos, volumen, aberturas conocidas, topología
de la malla y comportamiento bajo movimientos rígidos. El volumen del cilindro,
las paredes, el taladro y los redondeos procede de fórmulas geométricas; el loft
usa la referencia CAD y contraste independiente del volumen de su teselación.

`run_benchmarks.py` ejecuta conversiones reales con el motor congelado y separa
éxitos, rechazos y tiempos agotados. Los casos básicos cilindro/pared/taladro son
obligatorios. Los redondeos, el loft y su variante girada son sondeos de capacidad:
un rechazo se conserva como limitación, nunca se cuenta como conversión válida.
No se aumentan presupuestos para hacerlos pasar. Cada STEP escrito como éxito
se reimporta y se contrasta con el volumen y aberturas de la referencia.

El nuevo proponente también se prueba con superficies residuales atravesadas
por un cilindro: debe consolidar los parches sin cerrar el taladro, preservando
los cilindros y pasando el validador frío original, material y puntos comunes.

Ejecución (salida nueva):

```
python visor/scripts/run_benchmarks.py --output resultados --cases cylinder thin_wall small_hole
```

Las pruebas detalladas del paquete usan `pytest visor/tests`. Las piezas
reales conservadas del proyecto siguen siendo controles locales adicionales;
no forman parte de estos archivos sintéticos ni de una publicación nueva.
