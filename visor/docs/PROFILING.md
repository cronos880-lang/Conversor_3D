# Tiempos y reutilización sin cambiar calidad

El informe del pipeline registra tiempos de análisis de entrada, conversión R19
completa, propuesta/puerta, certificado final y copia/verificación. La propuesta
separa reconocimiento, ajuste de bordes, intersecciones y exportación. El tiempo
R19 total incluye sus controles: no se etiqueta como tiempo puro de reconocimiento.
Los trabajadores miden además el coste de comprobar la firma del núcleo.

Para medir también las funciones internas de los procesos históricos, establecer
`CONVERSOR3D_PROFILE_DIR` en una carpeta local nueva. El hook optativo activa
cProfile en cada proceso sin cambiar fuentes congeladas. Los procesos terminados
normalmente escriben su perfil; uno abortado puede no escribirlo. El perfilador
añade coste, por lo que sus tiempos no se comparan directamente con una ejecución
normal. Resumen:

```
python visor/scripts/summarize_profiles.py carpeta_perfiles
```

La caché sólo reutiliza el análisis de lectura exacta de un STL con igual hash,
perfil, lector, núcleo y versiones de numpy/trimesh. Los arrays no usan pickle,
se verifican por hash y una entrada corrupta se recalcula. No autoriza geometría,
no amplía tolerancias y la validación final vuelve a leer el original. Los datos
de caché pueden contener la geometría del usuario; son locales y no se publican.

Dentro de una selección puede reutilizarse el control frío completo que la
puerta acaba de realizar sobre exactamente los mismos bytes. Coinciden STL,
STEP, perfil y nonce; después de copiar se verifica de nuevo el certificado con
motor y dependencias actuales. Esto evita repetir el mismo control completo,
no permite una salida sin él ni reutiliza certificados entre conversiones.

Referencia observada: el caso de redondeos teselado por OCP tardó unos 259 s y
conservó 19.891 caras; el loft libre agotó el sondeo de 300 s. La caché del lector
no resuelve esa limitación de reconstrucción. Se requiere analizar esas rutas
antes de prometer una aceleración geométrica general.
