# Interfaces del flujo de desarrollo

El motor R19 congelado es una dependencia explícita; sólo el trabajador legacy
configura sus imports. El servidor conserva el HTML y los contratos HTTP y usa
un adaptador local de comandos para llamar al nuevo coordinador. No se modifica
subprocess globalmente ni ninguna fuente de la entrega histórica.

1. La referencia se obtiene mediante la conversión R19 completa original.
2. Un trabajador proponente sólo puede escribir un STEP candidato y su informe.
3. El evaluador previo se conserva byte a byte como recurso inmutable. Su CLI
   recibe explícitamente la ruta del motor congelado. Conserva los mismos
   filtros, límites, certificado frío, material y puntos comunes. El informe del
   proponente no es una autorización.
4. Un candidato rechazado conserva la referencia. El STEP elegido pasa control
   frío completo y se verifica otra vez tras copiarlo al archivo final nuevo.
5. La salida tiene certificado con hashes de STL/STEP, perfil, dependencias,
   motor congelado y huella del código de desarrollo. Los sidecars compatibles
   con R19 permiten al servidor conservarlo al eliminar el temporal del trabajo.
6. Un timeout o cancelación detiene el árbol nativo; no convierte una salida
   parcial en éxito. La recuperación histórica no sustituye el certificado final.

`propose` construye solamente. `convert` obtiene una salida validada completa.
`serve` abre el flujo de desarrollo en un puerto independiente; el Visor R19
existente conserva su lanzador y comportamiento. La UI y los cuatro botones no
se reemplazan. Los perfiles Precisión e Impresión se conservan.

Las copias de los dos archivos del evaluador son deliberadas: constituyen la
puerta congelada autorizada, tienen manifiesto SHA-256 y no se refactorizan ni
se cambian sus presupuestos. No son otra implementación de validación.
