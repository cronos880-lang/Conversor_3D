# R9 experimental

Esta copia corrige costuras entre mitades del mismo cilindro y añade reconstrucción local de paredes cilíndricas completas después de una recuperación facetada. Si la mejora local no supera todos los controles, se conserva el STEP previo validado. Las rutas que ya pasan mantienen prioridad. Se exige comprobación CAD exacta, geometría frente al STL y las verificaciones adicionales de la recuperación.

Los resultados de la copia entregada están en `INFORME_RESULTADOS.md`, en la raíz del ZIP. No confundir una prueba del servidor Python con validación WebAssembly. Windows nativo, Onshape y la impresora K1C necesitan comprobación en esos entornos.

Embudo permanece aplazado por indicación del propietario. Un STEP de recuperación facetada se identifica como tal. No se reconstruye el historial paramétrico original.
