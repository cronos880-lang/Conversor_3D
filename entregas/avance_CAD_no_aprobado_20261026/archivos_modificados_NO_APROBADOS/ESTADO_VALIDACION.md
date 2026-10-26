# R8 experimental: reparación conservadora y encuentros CAD verificados

Esta es una copia experimental separada de R7. Mantiene la interfaz y el perfil
Precisión. Los límites de aceptación geométrica no se amplían.

El motor anterior conserva prioridad. Las nuevas reparaciones conservan cavidades,
rechazan huecos ambiguos y vuelven a comprobar el STL bruto original. El rescate
CAD sólo sigue a candidatos rechazados por interferencias: ciñe las superficies,
verifica los cilindros respaldados por el STL y exige tres mallados cerrados,
manifold, con la misma topología y sin intersecciones CGAL.

Un STEP recuperado con facetas conserva esa identificación; no se describe como
reconstrucción paramétrica. Las superficies libres pueden seguir siendo B-splines.

Los resultados definitivos, archivos originales, huellas, diferencias respecto a
R7 y pruebas realizadas figuran en el informe de la entrega, fuera de esta carpeta.
La batería histórica excluye el embudo aplazado por el usuario: no afirmar 14/14.

Pruebas ejecutadas en Linux. Windows nativo, importación en Onshape, WebAssembly y
K1C requieren sus propias pruebas; la prueba del servidor Python no valida WASM.
