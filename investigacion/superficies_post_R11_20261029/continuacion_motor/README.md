# Continuación del motor — 29/10/2026

**Investigación, sin nueva versión del Visor. R11 no se modifica.**

Se implementan dos avances genéricos sobre copias. No se declara terminado el problema de calidad de las piezas.

## Bancada: 206 → 201 caras, validado

La herramienta `planos_certificados.py` reconoce si todos los polos de un soporte B-spline pertenecen a un plano, con una cota de 2e-8 mm y pesos positivos. No se basa sólo en sus esquinas. Proyecta las curvas a coordenadas del plano conservando sus curvas 3D y comprueba el desacuerdo paramétrico de 5e-8 mm. Conserva los contornos interiores y protege los bordes de las superficies que no son planas al reunir caras coplanares.

En la bancada se certifican dos soportes planos; su sustitución y la reunión de caras reducen de 206 a 201 caras. Frente al STEP R11 original son 239 → 201. Se conservan **25 cilindros**, **14 extrusiones**, **1 sólido** y el inventario cilíndrico completo; quedan **27 caras B-spline**. Es una mejora incremental y todavía no elimina todas las líneas interiores.

`Bancada_ESTUDIO_201caras_VALIDADO.step` supera B-Rep exacto, coherencia UV/3D, BOP en frío, ausencia de objetos sueltos, comparación de material/Euler y los tres mallados finos. Se ha vuelto a comparar contra el STL original, no sólo contra el STEP anterior.

- Error de caja: 0.000561 mm; límite original 0,02 mm.
- Error de volumen: 0.026381 %; límite original 0,5 %.
- Máximo denso observado: 0.003965092 mm; límite original 0,06 mm.
- p95 denso: 0.000793623 mm; límite original 0,02 mm.
- Aristas: tolerancia máxima 1e-07 mm.
- Mallados a 0,00025 / 0,0005 / 0,001 mm: todos cerrados, orientados y con cero cruces CGAL.

Las distancias son muestreos, no una prueba de Hausdorff global. No se han aumentado las tolerancias geométricas.

SHA-256 del STEP: `670aa3a791a16797d8251a59fa3e0892d0bf1055530bc2dd8488d6b935627002`. La fuente y el STEP anterior permanecen intactos.

## Technic: recuperación de hipótesis y curvas compuestas

M35 ya no abandona directamente cuando un perfil propuesto exige subdividir una arista fuera de la cota fuente. Descarta ese perfil y permite un parche libre, sin ampliar los 0,003 mm. La prueba real recupera dos situaciones de este tipo, pero después agota el presupuesto de subdivisión y se rechaza: **no se declara resuelto Technic**.

M37 conserva directamente las curvas B-spline compuestas de los contornos. Evita forzarlas a un único Bézier y subdividir repetidamente la fuente por sus nudos. Mantiene las comprobaciones de contorno, CAD, material y geometría del motor. Resultado de la prueba real M37 (117.8 s):

No hay STEP aprobado. Resultado: La construcción medida no forma un sólido válido: {'error': "El contorno nuevo no coincide con su vértice compartido. {'regiones': [(33, 'Geom_Plane', 4), (35, 'Geom_Plane', 3)], 'cerrado': False, 'distancia': 8.06247861564607e-05, 'p_vertice': (127.13575538643174, -95.2723643709167, 1.628853713111414), 'p_curva': (127.13575263579392, -95.27235959898385, 1.6289341495384309), 'first': -0.5428077738330406, 'last': 0.5428077738331127}"}

Las pruebas de esta ruta utilizan la malla reparada de Technic que ya estaba preparada en R11. Eso no sustituye el control de la reparación contra el STL original ni la prueba de importación en Onshape.

## Pruebas

- M35: batería completa, **284 pruebas superadas**.
- M37: batería completa, **284 pruebas superadas**, y **57 pruebas del subconjunto de geometría y parches**. No se suman como pruebas distintas. La variante intermedia M36 pasó sus pruebas automáticas, pero el caso real detectó un error de importación que se corrigió en M37. La batería M37 terminó antes de aplicar la parada prevista; el resultado real sigue rechazado y no se publica una aplicación.
- Herramienta de planos: **3 pruebas superadas**. Detecta una protuberancia interior aunque las esquinas sigan coplanares; conserva un agujero y su cilindro al sustituir una cara de dos contornos; conserva las primitivas que no requieren sustitución.

La prueba del agujero compara volumen y área con la geometría analítica conocida. El cálculo de volumen por defecto sobre la cara NURBS de referencia introduce un error de integración de unos 5,4e-8 mm³; no se ha convertido ese error de la referencia numérica en una tolerancia geométrica más laxa.

## Archivos y reproducción

Este es un avance de fuentes y evidencias, no un paquete Windows. La base M34 completa y las dependencias están en el ZIP anterior de investigación. Mantener esa base en una copia de desarrollo. Aplicar los parches M35 y M37 sucesivamente a esa copia, o sustituir sólo `motor_superficies/constructor_barridos.py` en la copia por `constructor_barridos_M37.py`. No hacerlo sobre el Visor de uso.

Para la herramienta plana:

```text
python planos_certificados.py Bancada_ESTUDIO_206caras.step candidato.step propuesta.json RUTA_MOTOR/motor_superficies
```

La salida debe ser nueva. Después es obligatorio ejecutar el evaluador completo contra el STL original, como documenta la entrega anterior. El STEP de 201 caras incluido ya ha pasado ese evaluador. Para ejecutar `test_planos_certificados.py`, disponer la copia de fuentes como `motor_M35` junto al archivo de pruebas; también puede ser la copia M37 porque los módulos de control usados no cambian. Requisitos de pruebas y material completo: los mismos de la auditoría de R11.

No se ha integrado una nueva aplicación ni repetido una nueva matriz de conversiones de las 14 piezas y el cubo-carrito. Onshape, Windows nativo y K1C siguen pendientes. El soporte de muelle y el conector no tienen un nuevo resultado aprobado en esta continuación. No se publica R12.
