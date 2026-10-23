# Reproducir y continuar el trabajo

Primero leer `ESTADO_VALIDACION.md` y `../INFORME_RESULTADOS.md`.
No sobrescribir una instalación estable. La carpeta `Visor_experimental_fuentes`
contiene la aplicación completa; no incluye un Python preinstalado.

## Entorno

Windows: ejecutar `Instalar_Entorno.bat`. Para las pruebas, instalar además:

```bat
.venv\Scripts\python.exe -m pip install -r requirements_pruebas.txt
set VISOR_MATERIAL_PRUEBAS=..\material_pruebas
.venv\Scripts\python.exe -m pytest -q
```

Linux de referencia (Python 3.12, 64 bits):

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements_pruebas.txt
VISOR_MATERIAL_PRUEBAS=../material_pruebas .venv/bin/python -m pytest -q --junitxml=../nuevas_pruebas/pruebas.xml
```

El TestClient de FastAPI necesita sockets locales permitidos por el entorno.
Los tests no envían piezas a servicios remotos. El freeze completo del entorno
de referencia está en las evidencias; el instalador Windows usa las dependencias
principales fijadas de R1, Manifold/psutil fijados y networkx 3.6.1, que la ruta
de perfiles ya utilizaba pero la R1 no declaraba.

## Diagnóstico y reparación independientes

```sh
python diagnosticar_stl.py original.stl --completo --salida diagnostico.json
python preparar_stl.py original.stl preparado.stl
python preparar_stl.py abierto.stl cerrado.stl --referencia-cierre referencia_cerrada.stl
```

El cierre local requiere la referencia explícita, los mismos vértices, entre 1 y
4 triángulos faltantes y un defecto de diámetro máximo 1 mm / 5 % de diagonal.
Sin referencia se rechaza la ambigüedad, también en agujeros pequeños de escáner.
Una abertura funcional no se sella por el hecho de que sea pequeña.

Las uniones se limitan a 20.000 triángulos y 8 cuerpos cerrados. Se conservan los
componentes pequeños. Los contactos por punto/arista y cuerpos separados se
rechazan. Una interfaz plana que ya comparte aristas puede normalizarse dentro
de 0,000020 mm para corregir redondeo STL; no se unen cuerpos por proximidad.
La malla serializada vuelve a contrastarse con la unión poliédrica independiente
OCC: caja y máximo superficial observado 0,002 mm, volumen 0,001 %. Son límites
adicionales: los controles CAD originales no cambian.

## Conversión y batería

```sh
python motor_v2.py preparado.stl salida.step
python bateria_reparacion.py --motor . --stl ../material_pruebas/stl_regresion_14 --salida ../nuevas_pruebas/experimental
python bateria_reparacion.py --motor . --stl ../material_pruebas/caso_cubo_carrito --solo cubo-carrito.stl --salida ../nuevas_pruebas/cubo
```

Para obtener una nueva referencia, extraer el ZIP original de R1 a otra carpeta
y ejecutar la misma batería con `--motor` apuntando a esa carpeta intacta. Usar
el mismo entorno y los mismos STL, comprobar SHA-256 y evitar carga concurrente
para comparar tiempos de forma representativa.

```sh
python evaluar_aceptacion.py --referencia ../nuevas_pruebas/referencia --experimental ../nuevas_pruebas/experimental --cubo ../nuevas_pruebas/cubo/cubo-carrito.resultado.json --pruebas ../nuevas_pruebas/pruebas.xml --salida ../nuevas_pruebas/aceptacion.json
```

La puerta exige las 14 conversiones, comparación de calidad, reimportación de
cada STEP y conversión válida del cubo-carrito. Mantiene Windows pendiente hasta
aportar evidencia nativa; no lo deduce del sistema donde se preparan los paquetes.
Las pruebas unitarias y rotaciones son puertas adicionales documentadas en el
informe: una ejecución correcta de la app no sustituye esas pruebas.

## Evidencias del servidor

`Registros_Conversion/<id>.entrada.json` conserva el diagnóstico. Si se repara,
también conserva `<id>.original.stl` y `<id>.reparado.stl`, incluso si el CAD falla.
El diagnóstico incluye rutas `/reparacion/<id>/informe`, `/original` y `/reparado`.
El proceso CAD y sus descendientes se supervisan por tiempo/RAM y se detienen al
cancelar con Nuevo. La evidencia Windows de taskkill sigue pendiente.

## Trabajo que requiere otra puerta de calidad

No sustituir el núcleo para sortear un rechazo. Si se desarrolla una corrección
del exportador B-Rep/STEP, probarla solo en una rama separada, reimportar el STEP,
comparar contra la unión de referencia y repetir las 14 piezas con los mismos
límites. No usar `_close_mesh` ni suavizado como atajo. No entregar un STEP
facetado de auditoría como si fuese el CAD editable final del Visor.

## Repetir la fase cubo-carrito de esta entrega

Desde `Visor_experimental_fuentes`, preparar una carpeta que contenga solo los
cuatro `cubo-carrito*.stl` de prueba (excluir `cubo-carrito_REPARADO.stl`, que es
una referencia aportada). Sus tres giros están definidos en `verificar_cubo_step.py`.
Después ejecutar:

```sh
python bateria_reparacion.py --stl ../casos_cubo --salida ../nuevas_pruebas/cubo
python verificar_cubo_step.py --corpus ../casos_cubo --resultados ../nuevas_pruebas/cubo
```

La primera orden usa el mismo punto de entrada que el servidor. La segunda
reimporta los archivos escritos, comprueba sus huellas, autointerferencias,
volumen adaptativo convergente, todos los vértices y centroides del STL más
4.000 puntos de área, y una teselación CAD fina con centroides y aristas.
También comprueba puntos del canal central y del material de sus paredes.

Los STEP incluyen superficies analíticas y B-splines; algunas esquinas siguen
representadas por parches planos. No incluyen un historial de operaciones CAD.
La edición concreta en Onshape debe comprobarse allí.

La ruta CAD precisa se activa únicamente tras una reparación verificada y
para entradas de hasta 12.000 triángulos. Si falla el intento directo, prueba un
marco rígido local inferido de normales de caras grandes. El STEP se restaura
y vuelve a pasar el validador histórico en coordenadas originales; el pequeño
error de serialización local no amplía ninguna tolerancia.


## Casos nuevos R2 y regresiones de rechazo

Los STEP en `material_pruebas/regresiones_cad_no_aceptados` son defectuosos
por diseño de la prueba: NO son resultados aprobados.

Desde `Visor_experimental_fuentes`, en Linux:

```sh
VISOR_MATERIAL_PRUEBAS=../material_pruebas VISOR_CASOS_R2=../material_pruebas/casos_usuario_r2 VISOR_FIXTURE_CACHE_R2=../material_pruebas/regresiones_cad_no_aceptados/4600_fixed.step VISOR_FIXTURE_DENSO_R2="../material_pruebas/regresiones_cad_no_aceptados/Pieza ambigua.step" python -m pytest -q --junitxml=../nuevas_pruebas.xml
python bateria_reparacion.py --stl ../material_pruebas/casos_usuario_r2 --salida ../nuevos_resultados
python verificar_casos_usuario.py --casos ../material_pruebas/casos_usuario_r2 --resultados ../nuevos_resultados
```

La batería y el verificador devuelven código 1 si algún caso no pasa; es el
resultado esperado mientras sigan pendientes dos piezas. Los informes JSON
individuales permiten distinguir un rechazo real de una interrupción por recursos.
En Windows definir las mismas cuatro variables con `set VARIABLE=valor` antes
de ejecutar `.venv\Scripts\python.exe -m pytest`; no se ha probado allí.

El nuevo muestreo denso automático cubre 3.000 puntos STL, incluidos puntos
interiores de triángulos con semilla fija. En sentido inverso mide vértices y
centroides de teselación fina CAD y puntos de aristas. Mantiene los umbrales
originales de p95 y máximo. Un BRepCheck válido y cero interferencias no
sustituyen este control geométrico.

Para certificar la identidad de los STEP del cubo con los ensayados en la entrega
anterior, sin repetir las mismas mediciones sobre geometría idéntica:

```sh
python comparar_regresion_cubo.py --referencia ../evidencias/cubo_referencia_previa --resultados ../evidencias/entrega_cubo
```

La prueba exige identidad binaria de DATA, de los STL y de las métricas; no
acepta una comparación visual. Los ficheros de referencia están incluidos.
