# perfeccion_Visualizador R3 — AVANCE NO ESTABLE

R3 añade perfiles explícitos, diagnósticos con valores/límites, consultas CAD
más eficientes y vigilancia de tiempo según triángulos y actividad del proceso.
El perfil predeterminado sigue siendo Precisión; Impresión debe seleccionarse.

No sustituir R2 con esta copia como si hubiera superado todas las regresiones.
La comprobación ampliada descubre dos problemas en STEP históricos que antes
pasaban el muestreo: chasis - Part 2 supera el máximo superficial del perfil de
precisión; pinza presenta interferencias avanzadas en una ruta de recuperación.
En la batería repetida pasan 10 de los 12 casos antes aceptados. Las métricas
históricas de esos diez no cambian. El cubo-carrito y sus tres giros pasan y
conservan idéntica geometría STEP a la referencia independientemente verificada.

Las cuatro piezas nuevas siguen en investigación; consultar los resultados
individuales y el informe actualizado junto al ZIP. No interpretar 57 tests
unitarios aprobados como 57 conversiones ni como una validación global 14/14.
El embudo continúa aplazado por indicación del propietario; no se repite conector.

Precisión: caja 0,020 mm, p95 0,020–0,030 mm, máximo superficial 0,060 mm más
únicamente el margen histórico de preparación medido cuando corresponda.
Impresión: caja 0,040 mm, p95 0,040 mm, máximo superficial 0,080 mm incluyendo
el posible error de preparación. Volumen 0,5 % en ambos perfiles. La verificación
de unión conserva 0,002 mm y 0,001 %. Ningún perfil autoriza cierres ambiguos.

Puerto R3: 8767. R2 usa 8766. Windows nativo y Onshape Move face pendientes.
Las pruebas de navegador son del Visor Python local, no del conversor WebAssembly.
