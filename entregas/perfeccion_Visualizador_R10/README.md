# Visor completo para Windows · R10 experimental

[**Descargar R10 completa**](./perfeccion_Visualizador_R10_EXPERIMENTAL_COMPLETA.zip?raw=true) · [**Comparar el tirante R9/R10**](./R10_TIRANTE_PARA_COMPARAR.zip?raw=true)

Extrae todo en una carpeta nueva y abre **Iniciar.bat**. Incluye `Visor_experimental_fuentes`. Si descargas todo el repositorio con Code → Download ZIP, entra en `entregas/perfeccion_Visualizador_R10` y abre allí Iniciar.bat. Puede reutilizar el entorno de R7, R8 o R9 sin modificarlo. Encabezado **R10 experimental**, puerto **8776**. Python 3.12 de 64 bits.

El tirante pasa de **13.122 caras planas a 22 caras**, con diez cilíndricas y dos superficies de revolución. La nueva reconstrucción sólo se intenta tras el rechazo de las rutas anteriores; mantiene los mismos controles geométricos, CAD exacto, BOP, material, cilindros y tres fronteras finas CGAL. La bancada y la maneta conservan su resultado R9 y siguen pendientes de mejora. No se promete una mejora en todas las piezas ni mayor velocidad.

[Informe de resultados reales](./INFORME_RESULTADOS.md) · [Tabla CSV](./RESULTADOS_REGRESION.csv) · [Verificación del paquete](./VERIFICACION_PAQUETE.json) · [STEP del tirante](./STEP_PARA_PROBAR/Tirante_R10.step?raw=true)

24 conversiones y 249 pruebas automáticas aprobadas; 64 pruebas adicionales pasan sobre la copia extraída, con arranque, conversión y exportación reales. Incluye cubo-carrito y sus tres giros; Embudo continúa aplazado, por lo que no se declara 14/14. **Windows nativo, Onshape y K1C no se han ejecutado aquí.**

Material para desarrollo y revisión:

- [Auditoría y reproducción](./perfeccion_Visualizador_R10_AUDITORIA.zip?raw=true).
- [Todos los STEP y registros](./perfeccion_Visualizador_R10_RESULTADOS_STEP.zip?raw=true).
- [Archivos modificados](./archivos_modificados), [parche desde R9](./CAMBIOS_DESDE_R9.patch) y [reproducción](./REPRODUCIR.md).

R10 es una copia experimental independiente; las versiones anteriores y la web de main se conservan.
