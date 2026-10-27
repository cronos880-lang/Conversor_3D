# Reproducir el avance de contornos CAD

Esta entrega es de desarrollo. La mejora está en la API experimental; no se activa al abrir el Visor ni sustituye la instalación actual.

## Contenido

Extrae **los dos ZIP en la misma carpeta nueva**. Ambos contienen la raíz `avance_contornos_CAD_NO_ACTUALIZACION`; sus contenidos se complementan. Las fuentes completas están en `fuentes_experimentales_NO_ACTUALIZAR`; los once archivos nuevos/modificados están también en `archivos_modificados`. `CAMBIOS_RESPECTO_M2.patch` permite revisar sólo esta fase.

El entorno de referencia fue Linux x86_64 con CPython 3.12. Consulta `ENTORNO.json` y los `requirements.txt` de las fuentes. Se necesitan las dependencias CAD y CGAL indicadas allí; para pytest, además `pytest` y `httpx`. La disponibilidad y ejecución en Windows nativo siguen pendientes de prueba. No se incluye una instalación binaria ni se afirma que los siguientes comandos hayan sido probados en Windows.

Los ejemplos usan `python` del entorno con esas dependencias instaladas y se ejecutan desde la raíz extraída.

## Pinza: API real y todas las comprobaciones

```bash
python herramientas/reproducir_ruta_nueva.py \
  --paquete . \
  --entrada entradas/pinza.stl \
  --salida prueba_nueva/pinza.step
```

El trabajador llama a `meshfit_step.export_step(..., precision_reparacion=True, refinar_curvas=True, contornos_compartidos=True)`. Comprueba el STEP mediante importación estricta, exactitud y BOP; después usa el evaluador R7 inmutable, confirma los cilindros, topología y los tres mallados con el control M1 inmutable. El límite por cada proceso es de 300 segundos; `--limite` permite fijar otro presupuesto de ejecución, sin modificar tolerancias geométricas. La salida debe ser una ruta nueva.

El resultado se registra en `pinza.aceptacion.json`. Sólo `caso_verificado: true` indica que ese caso concreto pasó todas las puertas. `actualizacion_aprobada` permanece falso porque un caso aprobado no convierte toda la aplicación en una actualización aprobada. Si falla, se conserva el diagnóstico y el STEP, si existe, se renombra con `_NO_APROBADO.step`.

El wrapper se ha ejecutado sobre la copia del paquete: volvió a pasar todas las puertas y el bloque `DATA` del STEP fue idéntico al primer ensayo API. Las huellas completas de los archivos difieren por los metadatos de cabecera del STEP; se conservan ambas.

## Suite completa con fixtures

```bash
python herramientas/reproducir_pruebas.py \
  --motor fuentes_experimentales_NO_ACTUALIZAR \
  --material-r7 material_pruebas \
  --banco-r7 fixtures_banco_R7 \
  --xml pruebas_repetidas.xml
```

Resultado de referencia de esta fase: **170 pasadas, 0 fallidas, 0 omitidas**. Los fixtures negativos son intencionalmente defectuosos; no deben sustituirse por STEP de candidatos corregidos. Una ejecución sin esas rutas no equivale a la suite completa.

## Regresión de conversiones completas

```bash
python herramientas/reproducir_regresion.py \
  --paquete . \
  --salida regresion_repetida
```

Este comando ejecuta los 21 casos del protocolo con los límites de cada pieza y registra salida, RAM, tiempo, huellas y comparaciones con R7/M1. Se conservan completos los STEP R7 y los resultados M3; la comparación M1 usa la huella SHA256 exacta de su bloque `DATA` para evitar duplicar otros 157 MB de STEP del paquete anterior. Las ejecuciones originales hicieron la comparación directa de bytes y se han comprobado también las huellas frente a los 21 resultados nuevos. Puede tardar considerablemente. Usa la ruta habitual con perfil Precisión; no activa la nueva construcción. La carpeta de salida debe ser nueva. Los casos no ejecutados en la ventana original de trabajo, si los hay, constan como tales en el informe entregado.

Embudo sigue aplazado por el usuario; esta batería no demuestra 14/14 históricos. Las pruebas Python tampoco validan el flujo WebAssembly, Windows nativo ni Onshape.

## Continuidad de desarrollo

Los ensayos auxiliares de `investigacion` documentan intentos positivos y negativos y algunos conservan rutas absolutas del entorno original. Las tres herramientas anteriores son las entradas portables para repetir las comprobaciones principales. Los archivos `evidencias/pytest/pruebas_completas_congeladas.*` contienen el primer intento sin fixtures y sus fallos; `pruebas_completas_configuradas.*` contiene la suite completa correcta.

No cambies los evaluadores, los fixtures negativos ni las tolerancias para aprobar piezas. La siguiente integración debe ejecutar la nueva construcción en un proceso vigilado, tras un rechazo concreto, y mantener todos los controles antes de publicar un STEP como resultado válido.


## Candidato separado de prioridad cilíndrica

Para comprobar la variante posterior en el mismo entorno, usa la herramienta de la raíz e indica sus fuentes y su manifiesto explícitamente:

```bash
python herramientas/reproducir_ruta_nueva.py   --paquete .   --motor variante_prioridad_cilindros/fuentes   --manifiesto variante_prioridad_cilindros/FUENTES_SHA256.json   --entrada entradas/Bancada_Motor.stl   --salida prueba_variante/bancada.step   --limite 600
```

Es una comprobación de desarrollo, no una actualización de la aplicación. La regresión de 21 casos corresponde a M3; no se atribuye a esta variante. Los tiempos de ejecución dependen de la concurrencia y del equipo; cambiar el presupuesto no cambia tolerancias geométricas.
