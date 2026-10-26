# Batería externa del Visor R7

Este paquete sirve para conocer los aciertos y límites de **R7 experimental**. No es una actualización y no debes copiar sus archivos sobre tu programa.

## Probar las piezas en tu Visor

1. Extrae el ZIP completo en una carpeta nueva.
2. Abre tu R7 habitual y deja el perfil **Precisión**.
3. Carga los STL de `stl_sanos/` en orden: 01–05 básicos, 06–10 taladros y paredes, 11–15 perfiles y mecanizado, 16–20 superficies más complejas. Los grupos son orientativos.
4. Para la placa 20 utiliza `stl_complementarios/C20_remallado_fino.stl` como prueba adicional problemática: su calibración pasa, pero contiene 44 pares de triángulos con intersección CGAL. Su STEP supera el contraste CAD. La entrada 20 inicial tiene una discretización que supera el límite de calibración del ensayo y se conserva para auditoría.
5. Compara con `referencias/` y consulta `INFORME_CAPACIDAD_R7.md` y los CSV. El número de caras y la calidad de edición se registran aparte de la precisión geométrica.

**El caso 17 demuestra un fallo de R7 predeterminada:** el programa aprueba un STEP con autointersección CAD. Su salida está en `NO_APROBADOS/`. No la uses como conversión correcta. El control adicional de interferencias ya existente en R7 consigue otra salida comprobada, con mayor tiempo; no constituye una nueva versión del programa.

## Contenido

- `stl_sanos/`, `referencias/`: veinte entradas iniciales y su CAD esperado.
- `stl_secundarios/`, `referencias_secundarios/`: seis defectos, tres rotaciones y una configuración diagnóstica.
- `stl_complementarios/`: una discretización más fina de la placa 20, misma geometría CAD.
- `STEP_APROBADOS/`: salidas que superan el contraste muestreado contra el CAD. Las variantes adicionales se distinguen en su nombre.
- `NO_APROBADOS/`: STEP del falso positivo 17, conservado para reproducirlo.
- `SIN_VERIFICAR/`: salida del ensayo 20 inicial, excluido por calibración de entrada; no es una pérdida dimensional del conversor demostrada.
- `resultados_sanos/`, `resultados_secundarios/`, `oraculos/`, `oraculos_secundarios/`, `complementario_20/`: informes y registros originales. Los STEP se localizan mediante `indice_step.json`.
- `motor_R7_inmutable/`: copia del código R7 usado, con sus 96 archivos cotejados. No incluye un entorno Python instalado.
- `fuentes_cadquery/`, `fuentes_mfcad/`: fuentes externas seleccionadas y licencias completas.
- `MANIFIESTO_SHA256.json`: huellas de los archivos del kit.

«Aprobado» se limita a las comprobaciones descritas en el informe. Las distancias y la clasificación de material se muestrean: no es una prueba matemática de igualdad global ni una certificación de importación en todos los CAD.

## Verificar que la descarga está completa

Con Python, desde la carpeta extraída:

```text
python verificar_integridad.py
```

Este comando no instala dependencias ni convierte piezas.

## Repetir una conversión y su contraste CAD

La reproducción técnica necesita Python 3.12 de 64 bits y las dependencias CAD. No hace falta instalar nada de esto para cargar las piezas en tu Visor ya instalado. Se ha probado esta reproducción en Linux; Windows nativo sigue pendiente.

En un entorno nuevo, instala `requirements_bateria.txt`; contiene las versiones de los paquetes principales observadas en el ensayo. `entorno_ensayado.json` registra la plataforma y la cuota de recursos.

```text
python -m pip install -r requirements_bateria.txt
python reproducir.py 02_taladro --salida ensayo_taladro
python reproducir.py C20_remallado_fino --salida ensayo_placa_fina
```

La carpeta de salida debe ser nueva. El comando verifica las huellas del motor, convierte sin modificarlo y ejecuta el contraste en otro proceso. Usa el perfil Precisión, hasta 4.096 MiB para el motor y 3.000 MiB para el evaluador. Los tiempos máximos de conversión son los del protocolo; el contraste dispone de 600 s, o 1.200 s para la entrada 20 inicial. Si el evaluador no termina, se informa **SIN VERIFICAR**.

Para contrastar otra vez la salida histórica del falso positivo, sin volver a convertir:

```text
python reproducir.py 17_barrido_spline --solo-contraste --salida contraste_17
```

Este último comando debe terminar con **CONTRASTE NO APROBADO** y código de salida 2. Los códigos 0, 3 y 4 significan contraste aprobado, conversión rechazada/interrumpida y contraste inconcluso, respectivamente. Una salida 3 no demuestra por sí sola un rechazo geométrico deliberado: hay que consultar el registro.

Las variantes `D01_caras_duplicadas`, `R_09_pared_delgada` y `G17_control_interferencias` también se pueden ejecutar por su identificador. Sólo G17 activa una bandera adicional; no se cuenta como la configuración predeterminada de R7.

Los scripts `ejecutar_corpus.py`, `ejecutar_secundarios.py` y sus controladores de oráculos son los usados durante la sesión del 26/10/2026 y conservan su fecha límite histórica. **Para repetir después utiliza `reproducir.py`**, que no depende de esa fecha. No vuelvas a generar el corpus encima de los resultados entregados: las cabeceras STEP pueden incluir fechas y cambiar sus huellas.

## Procedencia y licencias

CadQuery/cadquery, commit `8178185a24a035c9af7f4679033be14267f6a6ef`, licencia Apache-2.0; hducg/MFCAD, commit `ef6d58a40164d5192666821ce98d0cc90e379fac`, licencia MIT. Las fuentes originales seleccionadas se conservan sin modificar. La normalización, generación de STL y parámetros usados se documentan en `preparar_corpus.py` y `corpus.json`. Las variantes dañadas y rotadas son transformaciones deliberadas del ensayo.

Se redistribuyen las licencias completas. No se encontró archivo NOTICE en el árbol del commit CadQuery utilizado. El código del Visor conserva sus avisos y licencias de terceros. Este kit no distribuye los binarios de las dependencias Python.
