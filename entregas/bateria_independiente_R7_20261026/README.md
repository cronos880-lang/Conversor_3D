# Pruebas externas de R7: veinte geometrías nuevas

[Descargar 20 piezas para probar (8,2 MB)](./Piezas_para_probar_R7.zip?raw=true) · [Informe completo](./INFORME_CAPACIDAD_R7.md) · [Kit reproducible y evidencias (95,4 MB)](./Bateria_independiente_R7.zip?raw=true).

**Se detectó un falso positivo de R7:** el barrido spline 17 recibe aprobación en la interfaz, pero su STEP tiene autointersección CAD. El kit conserva esa salida en NO_APROBADOS. El control de interferencias ya incluido en R7 consigue una alternativa comprobada, con más tiempo; la configuración predeterminada sigue fallando.

De los veinte intentos iniciales se aprueban dieciocho, falla uno y se excluye la placa 20 por discretización insuficiente. Una repetición más fina de esa placa supera los controles; contiene 44 pares de triángulos intersectados en la entrada y cero al teselar su STEP. En conjunto se obtuvieron salidas verificadas para diecinueve geometrías distintas. Los seis defectos deliberados y las tres rotaciones se documentan aparte. El informe distingue las entradas sanas, la repetición problemática y los rechazos que no reparan.

El ZIP ligero contiene veinte STL y sus CAD esperados: 01–19 más la variante fina de 20, con CSV de esos archivos concretos. Extraer y cargar los STL en la R7 que ya tengas, perfil Precisión. **No es una actualización:** no copiar archivos sobre el programa. Las piezas se normalizaron a 40 mm antes del ensayo.

El kit completo contiene los 31 ensayos de motor, el flujo de navegador del falso positivo, fuentes y licencias, salidas, registros y código de reproducción. Los 96 archivos del motor coinciden con la R7 publicada. No se modifican las tolerancias del motor ni la web WebAssembly de main. Se ha probado Linux; Windows nativo y otros CAD quedan fuera de esta batería.

[SHA-256 de las descargas](./DESCARGAS_SHA256.json) · [Instrucciones técnicas](./LEEME.md) · [Comprobación del ZIP extraído](./VALIDACION_DESCARGA.json).
