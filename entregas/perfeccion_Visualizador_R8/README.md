# Visor completo Windows · R8 experimental

[**Descargar el programa completo R8**](./perfeccion_Visualizador_R8_EXPERIMENTAL_COMPLETA.zip?raw=true)

Extrae todo en una carpeta nueva y abre **Iniciar.bat**. Si descargaste el repositorio entero con Code → Download ZIP, entra en `entregas/perfeccion_Visualizador_R8` y abre allí `Iniciar.bat`; también incluye las fuentes completas sin comprimir. Incluye `Visor_experimental_fuentes`. Si aparece un selector, elige la carpeta de R7 para reutilizar su entorno sin modificarlo; también puedes ejecutar `Instalar_Entorno.bat`. Python 3.12 de 64 bits. Encabezado R8 y puerto **8772**.

[Resultados reales y límites](./INFORME_RESULTADOS.md) · [Resultados CSV](./RESULTADOS_REGRESION.csv) · [Huellas de los ZIP](./PAQUETES_SHA256.json)

21/21 conversiones de regresión, cubo y tres giros, 213 pruebas automáticas. Bancada y pinza recuperan encuentros entre superficies y conservan los cilindros confirmados, con control CAD exacto y contraste independiente. Las tolerancias de Precisión siguen iguales a R7. Embudo permanece aplazado: no se declara 14/14.

**Windows nativo y Onshape siguen pendientes de prueba en esos entornos.** La validación real de esta entrega se ejecutó en Linux y navegador Chromium. No se declara resuelto el defecto visual de 6558 en Onshape.

Para revisar o reproducir, sin necesidad de descargarlos para usar el programa:

- [Kit de auditoría y materiales](./perfeccion_Visualizador_R8_AUDITORIA.zip?raw=true).
- [STEP, registros y reparaciones realmente obtenidos](./perfeccion_Visualizador_R8_RESULTADOS_STEP.zip?raw=true).
- [Reproducción](./REPRODUCIR.md), [fuentes modificadas](./archivos_modificados), [parche acumulado desde R7](./CAMBIOS_DESDE_R7.patch).

Esta es una copia experimental independiente del conversor web de main. No sustituye R7 ni recupera el historial paramétrico original.
