# Textos e inventario de licencias

Los dos textos OCCT se conservan literalmente desde el commit upstream
`a016080bf6738d6aeae020badee4e888ad1540a5` de OpenCascade 7.9.3.
Su procedencia y alcance están en [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md).

`runtime-linux.json` es la lectura de los 70 paquetes instalados desde el lock
Linux el 11 de noviembre de 2026; incluye hashes de los avisos encontrados.
No contiene los textos completos de todas las licencias ni concede permisos.
Windows genera su informe propio en CI y al construir la carpeta de prueba.
La carpeta incluye estos documentos, el inventario Windows y los avisos
originales dentro de sus respectivas distribuciones instaladas.
