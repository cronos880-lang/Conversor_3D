# Visor completo para Windows · R9 experimental

[**Descargar R9 completa**](./perfeccion_Visualizador_R9_EXPERIMENTAL_COMPLETA.zip?raw=true) · [**STEP de llanta y Lego para comparar**](./R9_CILINDROS_PARA_COMPARAR.zip?raw=true)

Extrae todo en una carpeta nueva y abre **Iniciar.bat**. Incluye `Visor_experimental_fuentes`. Si descargas el repositorio entero con Code → Download ZIP, entra en `entregas/perfeccion_Visualizador_R9` y abre allí Iniciar.bat: también incluye las fuentes sin comprimir. Puede reutilizar el entorno de R7 o R8 sin modificarlo; si necesitas instalar uno, usa Instalar_Entorno.bat con Python 3.12 de 64 bits. Encabezado **R9 experimental**, puerto **8775**.

La llanta pasa de 4.195 caras planas a 53 caras y conserva sus 15 cilindros confirmados. Lego4×2 pasa de 1.692 caras planas a 1.149 caras, con 12 cilíndricas; mantiene ocho cavidades y otras zonas siguen facetadas. Se exige geometría, CAD exacto, BOP y las verificaciones adicionales de reconstrucción. Los límites de Precisión no se amplían.

[Informe real y limitaciones](./INFORME_RESULTADOS.md) · [Tabla CSV](./RESULTADOS_REGRESION.csv) · [Verificación del paquete](./VERIFICACION_PAQUETE.json)

21/21 conversiones principales y 3 recientes, 233 pruebas automáticas. Embudo sigue aplazado: no se declara 14/14. **Windows nativo, Onshape y K1C siguen pendientes de prueba.** La revisión visual de 6558 en Onshape no se declara resuelta. No se promete reconstrucción completa ni menos facetas en todas las piezas.

Material adicional, innecesario para usar el programa:

- [Kit de auditoría](./perfeccion_Visualizador_R9_AUDITORIA.zip?raw=true).
- [Todos los STEP y registros obtenidos](./perfeccion_Visualizador_R9_RESULTADOS_STEP.zip?raw=true).
- [Reproducción](./REPRODUCIR.md), [archivos modificados](./archivos_modificados) y [parche desde R8](./CAMBIOS_DESDE_R8.patch).
- [STEP individuales](./STEP_PARA_PROBAR).

Esta es una copia experimental independiente. No modifica R8, R7 ni la web de main. No recupera el historial paramétrico original.
