# Dependencias reproducibles y servidor local

Los locks completos cubren CPython 3.12 x64: 77 paquetes en Linux y 78 en
Windows, con hashes de wheels compatibles. El instalador exige los hashes,
prohíbe compilaciones desde sdists y comprueba las dependencias instaladas.
Los requisitos directos tienen una sola fuente dentro de los recursos del
paquete. Los archivos de R19 congelada no se modifican.

```
python visor/scripts/install_dependencies.py
```

`python-multipart` pasa de 0.0.29 a 0.0.31 en el desarrollo. PyPI confirma los
avisos CVE-2026-53538/53539/53540. El parser de formularios de FastAPI/Starlette
puede interpretar cuerpos urlencoded antes de rechazar un archivo ausente; se
comprueba que `a=1;b=2` conserva el punto y coma como dato. No se afirma que el
uso directo de parse_form de otro aviso forme parte de esta aplicación.

Cada salida registra también las versiones de las 16 dependencias directas,
Python/plataforma y el hash de su especificación. Una versión instalada distinta
se rechaza con una causa clara; no se cambian presupuestos CAD para compensarla.
El entorno R19 anterior permanece intacto; las pruebas nuevas usan otro entorno.

## Peticiones al servidor

El servidor sigue ligado exclusivamente a 127.0.0.1. Comprueba Host y puerto,
Origin y peticiones cross-site antes de leer formularios o arrancar trabajos.
CORS sólo permite las dos URLs locales de esta instancia (127.0.0.1/localhost),
sin comodines. Los clientes locales de línea de comandos sin Origin conservan
su acceso. La interfaz del Visor usa su mismo origen y no cambia sus botones.

## Conservación

`CONVERSOR3D_RETENTION_DAYS=0` conserva los registros por defecto. Un valor
positivo activa la limpieza periódica sólo de grupos de archivos propios de
trabajos terminados y más antiguos que el plazo. El diagnóstico marca propiedad
y finalización. Se excluyen trabajos activos, datos sin esa marca, enlaces y
directorios desconocidos. Los originales externos al directorio de registros
no se recorren ni se eliminan. Un diagnóstico incompleto se conserva.

La caché es local y puede contener geometría; se controla con
CONVERSOR3D_CACHE_ENABLED y su directorio explícito. La limpieza de registros
no borra ciegamente todo el directorio de datos ni las fuentes originales.
