# Reproducir R6 y continuar la reparación

Leer `ESTADO_VALIDACION.md` y `../INFORME_RESULTADOS.md`. Esta es una copia de
investigación con aceptación global pendiente. Conservar la instalación anterior.

## Entorno y pruebas

Python 3.12, 64 bits. En Windows, ejecutar `Instalar_Entorno.bat` y luego
`Iniciar.bat`; esa instalación nativa no se ha ejecutado en esta sesión Linux.
En Linux, crear un venv e instalar `requirements_pruebas.txt`.

Desde `Visor_experimental_fuentes`:

```sh
VISOR_MATERIAL_PRUEBAS=../material_pruebas VISOR_CASOS_R2=../material_pruebas/casos_usuario_r2 VISOR_CASOS_R3=../material_pruebas/casos_usuario_r3 VISOR_CASOS_R4=../material_pruebas/casos_usuario_r4 VISOR_CASOS_R5=../material_pruebas/casos_usuario_r5 VISOR_RESULTADOS_R5=../evidencias/referencia_R5/reparador_integrado VISOR_FIXTURE_CACHE_R2=../material_pruebas/regresiones_cad_no_aceptados/4600_fixed.step VISOR_FIXTURE_DENSO_R2="../material_pruebas/regresiones_cad_no_aceptados/Pieza ambigua.step" VISOR_FIXTURE_RESCATE_R3="../material_pruebas/regresiones_cad_no_aceptados/Con fallos pero si step.step" python -m pytest -q --junitxml=../pruebas_repetidas.xml
```

En Windows definir estas mismas nueve variables con `set "VARIABLE=valor"` y
usar `.venv\Scripts\python.exe`. El test Linux de cancelación se omite en Windows;
se necesita evidencia nativa independiente del árbol de procesos/taskkill.

Los fixtures marcados NO ACEPTADOS son resultados defectuosos intencionales.
La prueba debe rechazarlos; no son ejemplos de conversiones aprobadas.

## Perfiles y límites

```sh
VISOR_PERFIL=precision python motor_v2.py entrada.stl salida.step
VISOR_PERFIL=impresion python motor_v2.py entrada.stl salida_impresion.step
```

En Windows usar `set "VISOR_PERFIL=impresion"` antes de llamar al motor.
El servidor pasa el perfil por trabajo al proceso, sin cambiar el entorno de
otros trabajos. La API acepta `perfil=precision` o `perfil=impresion` como campo
multipart adicional; rechaza nombres desconocidos.

El máximo 0,08 mm de impresión incluye la preparación. Las tolerancias de
volumen, integridad y reparación de entrada conservan sus controles. Los STL
originales se conservan y no se escalan para cumplir un perfil.

## Baterías y evidencia

```sh
python bateria_reparacion.py --stl ../material_pruebas/casos_usuario_r4 --salida ../resultados_nuevos --limite 900
python bateria_reparacion.py --stl ../material_pruebas/stl_regresion_14 --salida ../regresion_completa
python bateria_reparacion.py --stl ../material_pruebas/casos_cubo --salida ../cubo_repetido
python comparar_regresion_cubo.py --referencia ../evidencias/referencia_R5/cubo_referencia_previa --resultados ../cubo_repetido
```

Las baterías devuelven código 1 cuando algún caso falla. Los timeouts explícitos
de la batería son límites de ensayo; el servidor tiene su política adaptativa
propia en `politica_conversion.py`. No llamar fallo geométrico a un timeout.

El comparador del cubo certifica identidad binaria de DATA STEP y de los STL con
archivos previamente ensayados de forma independiente; no reejecuta esa batería.
Para repetirla desde cero, usar `verificar_cubo_step.py` con `--corpus` y `--resultados`.

La inspección densa usa puntos interiores STL y muestras de caras/aristas CAD.
Si una muestra teselada provocaría rechazo, se contrasta con la superficie B-Rep
exacta y se vuelve a medir el punto proyectado. No se modifica el STEP para ello.
Las distancias siguen siendo muestreadas, no una cota Hausdorff global.

## Navegador

El registro y la captura de Chromium Linux están en `evidencias/navegador_r6_sano.* (la prueba con rechazo reparado de R5 se conserva como referencia)`.
El STEP descargado se vuelve a importar y comprobar. Esa prueba corresponde al
servidor Python local. No demuestra que funcione Windows ni el conversor WASM.

## Reparación exacta aislada

```sh
python reparador_exacto_aislado.py entrada.stl regularizado.stl informe.json
```

Código 0: malla regularizada y verificada; no certifica STEP. Código 2: rechazo.
El Visor llama a esta herramienta automáticamente solo para la clase compatible.
`VISOR_REPARADOR_EXACTO=0` permite repetir el rechazo previo de R4 como referencia.
El informe conserva huellas del original y del STL ASCII generado.
Python 3.12 es necesario para los wheels Windows de CGAL de esta versión.
Las licencias del componente exacto están en LICENCIAS_REPARADOR.

## Investigación R6

Los ensayos separados están en laboratorio_r6. Sus STEP fueron rechazados y no se distribuyen como resultados aceptados. Los scripts conservan rutas del entorno de investigación; requieren adaptarlas para repetirlos. No son una ruta integrada del Visor.
