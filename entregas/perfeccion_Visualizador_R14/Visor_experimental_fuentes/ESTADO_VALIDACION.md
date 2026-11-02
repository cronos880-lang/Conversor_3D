# R14 experimental: alcance de validación

La aplicación conserva la conversión completa R13 y sólo acepta reconstrucción regional o de cilindros medidos después de superar los controles originales y la comparación con el resultado anterior. El informe de resultados de la carpeta principal identifica las conversiones que mejoran y las que conservan el STEP anterior.

Los perfiles geométricos, el evaluador `_calidad` y los controles CAD originales permanecen. Una forma con menos caras se rechaza si empeora la desviación, la caja o el error de volumen medidos. Los nuevos bordes CAD llevan sus tolerancias numéricas nativas de OCCT, documentadas separadamente de los límites geométricos.

Arrancar el servidor no constituye validación de conversión. La batería incluye conversión real, exportación, lectura fría y controles contra los STL originales. Linux/Chromium no demuestra ejecución nativa en Windows ni importación en Onshape. La versión es experimental; no recupera automáticamente todo diseño paramétrico. Embudo está aplazado por el usuario. Sin el STL de MediumBig no puede certificarse su geometría.
