# Bancada · avance R16 · entrega publicada

**La desconexión quedó resuelta y los dos ZIP están publicados y verificados.**

[Descargar programa R16 completo](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R16/entregas/perfeccion_Visualizador_R16/perfeccion_Visualizador_R16_EXPERIMENTAL_COMPLETA.zip?raw=true) · [Archivos modificados](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R16/entregas/perfeccion_Visualizador_R16/perfeccion_Visualizador_R16_ARCHIVOS_MODIFICADOS.zip?raw=true) · [Informe de resultados](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R16/entregas/perfeccion_Visualizador_R16/INFORME_RESULTADOS.md).

El registro siguiente documenta el estado anterior y las limitaciones de la mejora. Sus avisos de publicación pendiente son históricos; la entrega se completó en la rama `perfeccion_Visualizador_R16`.

---

# Bancada · avance R16 · entrega pendiente

El entorno de ejecución se desconectó el 4 de noviembre de 2026 durante la subida. No se ha publicado una versión R16 utilizable ni un ZIP completo en GitHub. Esta rama conserva el registro del avance y las partes ya transferidas; el código del programa heredado sigue siendo R15.

Resultados observados antes de la desconexión:
- Bancada: 134 → 108 caras; 409 → 363 aristas. Treinta parches de paredes interiores y apoyos se reúnen en cuatro superficies.
- Desviación máxima verificada: 0,003438 mm, igual a R15; error de caja 0,000561 mm; error de volumen 0,019909 %.
- STEP reabierto: un sólido válido, BOP cero, Euler −14, 25 recortes cilíndricos conservados.
- Tres mallados finos (0,00025 / 0,0005 / 0,001 mm): cerrados, orientados y sin intersecciones CGAL. 2.998 muestras de material: cero discrepancias.
- 19 conversiones completas aprobadas: 17 con DATA STEP literalmente idéntico a R15, conector con dos redondeos de 1,341519488088 × 10⁻¹⁶ mm y bancada mejorada. Los cuatro controles del cubo-carrito conservan el resultado R15. Corpus original: 13/14; embudo aplazado por indicación del usuario.
- Batería final: 382 pruebas aprobadas y 15 omitidas por fixtures externos no parametrizados.
- Perfil impresión 0,08 mm, postproceso aislado: aprobado, 108 caras y máximo 0,003438 mm.
- Bancada girada y renombrada, postproceso aislado: no aprobado; agotó 420 s tras detectar cruces y reintentar. Se comprobó SHA-256 idéntico del STEP base después del rechazo.
- Los perfiles, 16 archivos de validación y AST de la función principal de calidad permanecen iguales a R15.

No se declara la bancada al 100 %. Quedan seis grupos candidatos con trece caras originales que no se han unido con garantías. Windows nativo, Onshape y K1C física pendientes. El tiempo de bancada desde interfaz fue 18:53,6; no se afirma mejora de rendimiento.

Archivos preparados y comprobados localmente antes de perder el acceso:
- Completa: perfeccion_Visualizador_R16_EXPERIMENTAL_COMPLETA.zip; 3.959.447 bytes; SHA-256 fa0f7503404d580c757b04e4158df314ff40e1850841e360fd701abd54527e4a.
- Modificados: perfeccion_Visualizador_R16_ARCHIVOS_MODIFICADOS.zip; 70.376 bytes; SHA-256 0245d4dab62364a59144c8f0fc03b19737d952c8a1fcb13413b92ac9c0491241.
- 333 archivos de producto, 15 nuevos o modificados. CRC, extracción con espacios, huellas y AST Python comprobados. Esto no equivale a una prueba nativa de Windows.
- STEP R16 descargado: SHA-256 d53b92c85dcb755ec42f5244f9f6485310604c1d37e898ebfc15f5cbb35e685b.

Para continuar se necesita recuperar el acceso al entorno con /workspace/entregas_R16 y /workspace/work/bancada_objetivo_20261104. Las partes de esta rama son incompletas y no deben presentarse como una descarga del programa.

Se han rescatado de las partes ya transferidas el informe original, la comparación visual y el manifiesto de los 333 archivos del producto, verificando CRC de cada entrada. El blob Git del informe coincide exactamente con el previsto antes de la desconexión.

[Informe original de pruebas](INFORME_RESULTADOS.md) · [Comparación visual](Bancada_R15_R16.png) · [Huellas de los archivos preparados](FUENTES_PRODUCTO_R16_SHA256.json).
