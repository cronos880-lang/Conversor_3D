# Auditoría completa, en dos partes

El programa completo se descarga en un único ZIP y no necesita estas partes para funcionar.

Para revisar toda la auditoría, descarga en la misma carpeta los dos archivos terminados en `.zip.001` y `.zip.002`, `UNIR_AUDITORIA.py` y `AUDITORIA_EN_PARTES.json`. Ejecuta:

```
py -3.12 UNIR_AUDITORIA.py
```

En Linux o con Python en PATH también sirve `python UNIR_AUDITORIA.py`. Se genera el ZIP completo y se verifican los SHA-256 de ambas partes y del resultado. El script conserva los originales y no sobrescribe un ZIP diferente. Extrae después el ZIP y sigue `auditoria/REPRODUCIR.md`.

La separación responde al límite de transferencia del servicio de publicación. El contenido de la auditoría original permanece idéntico.
