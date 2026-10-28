# Visor completo para Windows · R11 experimental

[**Descargar R11 completa**](./perfeccion_Visualizador_R11_EXPERIMENTAL_COMPLETA.zip?raw=true) · [**Comparar las tres mejoras R10/R11**](./R11_BANCADA_MANETA_Y_GRAPA_PARA_COMPARAR.zip?raw=true)

Extrae todo en una carpeta nueva y abre **Iniciar.bat**. Incluye `Visor_experimental_fuentes`. Si descargas el repositorio entero, entra en `entregas/perfeccion_Visualizador_R11` y abre allí Iniciar.bat. Puede reutilizar un entorno compatible de R7, R8, R9 o R10 sin modificarlo. Python 3.12 x64. Encabezado **R11 experimental**, puerto **8777**. Mantén **Automático (precisión)**.

La **maneta pasa de 9.351 a 36 caras**, con cinco cilindros y dos superficies de revolución. La **bancada pasa de 1.896 a 239**, con 25 cilindros y 14 superficies de extrusión. Se miden los perfiles sobre el STL original; sólo se reemplaza el resultado anterior después de superar los controles geométricos y CAD originales. La bancada conserva 50 caras B-spline. No se promete recuperar el diseño paramétrico ni mejorar todos los STL.

**280 pruebas automáticas y 24 conversiones aprobadas**, incluidas nueve conversiones reales por navegador. Sobre el paquete extraído pasan además **52 pruebas** y una conversión/descarga real. El cubo-carrito y sus giros están incluidos. Los dos objetivos y Grapa pasan también el evaluador R10 congelado. Grapa mejora de 622 a 20 caras, con dos cilindros y ocho extrusiones. Embudo continúa aplazado; no se declara 14/14. **Windows nativo, Onshape y K1C no se han ejecutado aquí.**

[Informe de resultados reales](./INFORME_RESULTADOS.md) · [Tabla CSV](./RESULTADOS_REGRESION.csv) · [Verificación del paquete](./VERIFICACION_PAQUETE.json)

- [STEP de bancada](./STEP_PARA_PROBAR/Bancada_Motor_R11.step?raw=true), [maneta](./STEP_PARA_PROBAR/maneta_R11.step?raw=true) y [Grapa](./STEP_PARA_PROBAR/Grapa_R11.step?raw=true).
- [Archivos modificados](./perfeccion_Visualizador_R11_ARCHIVOS_MODIFICADOS.zip?raw=true) y [parche desde R10](./CAMBIOS_DESDE_R10.patch).
- [Auditoría y reproducción](./perfeccion_Visualizador_R11_AUDITORIA.zip?raw=true).
- [Todos los STEP y registros](./perfeccion_Visualizador_R11_RESULTADOS_STEP.zip?raw=true).

R11 es una copia experimental independiente. Las versiones anteriores y la web de main se conservan.
