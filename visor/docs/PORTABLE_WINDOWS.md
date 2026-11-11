# Carpeta autocontenida de prueba para Windows

El constructor se ejecuta en Windows con Python 3.12 x64 y dependencias
instaladas y verificadas. El usuario de la carpeta resultante no necesita
instalar Python, editar rutas ni ejecutar pip: abre `Iniciar_Visor.bat`.

```
python visor/scripts/build_portable.py --output carpeta_portable_nueva
python visor/scripts/smoke_portable.py carpeta_portable_nueva
```

El constructor sólo escribe una carpeta nueva. No crea ZIP, etiqueta ni release.
Copia el runtime CPython y las distribuciones transitivas realmente requeridas,
con metadata y licencias presentes. No copia ciegamente todos los paquetes del
ordenador. Incluye nuestras fuentes, las fuentes R19 congeladas y un manifiesto
SHA-256 de los archivos iniciales. No incorpora modelos nuevos del usuario.

`python312._pth` aísla los imports de instalaciones externas. La prueba nativa
elimina Python del PATH y las variables PYTHONHOME/PYTHONPATH/VIRTUAL_ENV,
comprueba OCP/VTK/CGAL y ejecuta una conversión con certificado completo. Relee
el STEP mediante el Python portable y verifica el volumen conocido. Esta prueba
se ejecuta en CI Windows; no equivale a probar todos los ordenadores Windows.

Datos y caché se guardan en `datos/` junto a la carpeta. Los lanzadores definen
explícitamente la ruta de las fuentes congeladas; se sigue exigiendo su firma
original. La distribución pública de binarios queda sujeta al inventario de
licencias del punto 10. No se ha cambiado la licencia global ni el sistema de
entregas del proyecto.

La carpeta de prueba incluye `THIRD_PARTY_LICENSES.md`, los textos de OCCT y
`THIRD_PARTY_INVENTORY.json` generado desde su propio entorno Windows.
Consúltese [la auditoría](../THIRD_PARTY_LICENSES.md) para las condiciones
identificadas y el alcance de autorización del motor que falta documentar.
