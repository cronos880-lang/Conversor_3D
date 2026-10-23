# Entrega del avance del Visor STL → STEP

**Avance no validado. No sustituir la R1 estable.**

Descarga `AVANCE_NO_VALIDADO_Visor_STL_STEP_2026-10-23.zip` con el botón **Download raw file / Descargar archivo** de GitHub. El ZIP contiene las fuentes completas, el parche, los STL de prueba y los resultados reales.

- 35 pruebas unitarias y de API superadas en Linux.
- Cubo-carrito: malla reparada y contrastada; conversión STEP final pendiente.
- 12/14 piezas convierten en la referencia y en la experimental; Embudo y Conector agotaron sus límites en ambas.
- Motor, tolerancias CAD e interfaz originales conservados.
- Windows nativo y Onshape Move face pendientes.

Consultar `INFORME_RESULTADOS.md` y los registros del ZIP antes de utilizar resultados.

Este paquete corresponde al backend Python del Visor aportado en el encargo. **No valida la conversión WebAssembly de la aplicación web Conversor_3D.** Esta rama contiene únicamente archivos de entrega; la aplicación y la rama main no se modifican.

El repositorio es privado y el paquete incluye las piezas STL y STEP del banco de pruebas. Para descargarlo debes entrar en GitHub con una cuenta que tenga acceso al repositorio. Las sumas del paquete original están en `SHA256SUMS.txt`.
