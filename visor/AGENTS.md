# Instrucciones técnicas del Visor completo para Windows

Estas instrucciones complementan la V2.2 íntegra de `../AGENTS.md`, que se debe
leer y aplicar. No sustituyen sus reglas de autonomía, publicación, consulta,
licencias ni aprobación de versiones. Su ámbito es el Visor Python/OCP;
el conversor web estático de la raíz es un producto distinto.

## Desarrollo y entregas históricas

El código incremental está en `src/conversor3d/` dentro de este directorio,
en la rama de trabajo `perfeccion_Visualizador_R20`. La rama
`desarrollo/hoja-ruta-visor` conserva el desarrollo previo. Utilizar las fuentes
R19 congeladas sin modificar sus validadores, tolerancias ni hashes.

La entrega R20 ya autorizada se conserva con su ZIP completo en fuentes e
instalador independiente. Esa autorización histórica no ordena crear otra
versión ni otro ZIP. Cuando el usuario solicite una entrega R20, el constructor
existente es `scripts/build_r20.py` (ruta desde la raíz:
`visor/scripts/build_r20.py`); no modifica las fuentes ni los ZIPs históricos.

- Cuando el usuario pida el Visor completo como R7 y sus versiones experimentales, trabajar en esa aplicación de escritorio con interfaz local. Las instrucciones iniciales sobre la aplicación estática corresponden al conversor web separado.
- Conservar la copia instalada y entregar cada versión experimental en una carpeta independiente, con su lanzador y su identidad de versión.
- Distinguir las pruebas reales de conversión en navegador sobre Linux de Windows nativo y de la importación en Onshape; indicar las comprobaciones pendientes.

## Geometría y puerta de aceptación

- Conservar las funciones, la interfaz, los cuatro botones, los contratos HTTP,
  los perfiles Precisión e Impresión y las conversiones aprobadas.
- Mantener la tolerancia B-Rep de `1e-7 mm` y los presupuestos de error vigentes.
  No confundir esa tolerancia topológica con una distancia global STL/STEP.
- No modificar `validacion_r19.validar`, los límites del evaluador congelado
  `evaluar_candidato_externo.py` ni sus manifiestos para aceptar candidatos.
- Mantener la separación entre el proponente y el evaluador independiente.
  Un candidato sólo se acepta si supera la puerta congelada: núcleo frío,
  geometría, material, mallado y contraste de puntos comunes. Un rechazo
  conserva la referencia validada; un informe del proponente no la aprueba.
- Verificar el STEP final y su certificado completo, incluida la trazabilidad
  STL/STEP/perfil/motor y la huella del código de desarrollo. No presentar
  timeouts, cancelaciones ni resultados parciales como conversiones válidas.
- No usar `fillupHoles`, redondeo destructivo de vértices ni healing agresivo
  que altere aberturas o volumen. Demostrar geometría conservada y STEP válido
  mediante pruebas reales; no prometer reconstrucción paramétrica perfecta
  para STL arbitrarios.
- En el trabajo incremental sobre los residuos de Bancada R19/R20, conservar
  las 53 caras planas y las 18 cilíndricas ya validadas. No generalizar una
  mejora a otras piezas sin pruebas representativas.

## Integridad, datos y pruebas

- Conservar R18, R19, R20 y la corrección del instalador R19. Las versiones
  retiradas se recuperan desde Git según `../MANTENIMIENTO_VERSIONES.md`.
- Conservar los 357 archivos del manifiesto `frozen-r19.sha256.json`, los
  evaluadores congelados y los checksums de las entregas históricas. No
  refactorizar copias deliberadas, normalizar fuentes ni fusionar módulos
  históricos por compartir nombre. Consultar `docs/FROZEN_DEPENDENCY.md`.
- Las pruebas históricas utilizan los seis archivos originales con hashes de
  `test-data/r5_regression.zip`; no dependen de la entrega completa R5. Sus datos
  quedan fuera de los ZIP de producto. No modificar los datos para aprobar pruebas.
- Mantener el proceso legacy aislado y la arquitectura de `docs/ARCHITECTURE.md`.
  No intercambiar variantes de módulos ni ejecutar pytest sobre todas las
  entregas a la vez. Un cambio de arquitectura o motor requiere consulta
  conforme a la V2.2.
- Ejecutar las comprobaciones aplicables al cambio y documentar los resultados
  reales. Para cambios del motor o su integración, comprobar la integridad con
  `python visor/scripts/audit_frozen.py`, las pruebas actuales de `visor/tests`
  y la batería congelada mediante `python visor/scripts/run_legacy_tests.py`;
  ejecutar estos comandos desde la raíz del repositorio con el entorno declarado.
- Diferenciar la validación del Visor de las pruebas del conversor web; las
  pruebas del backend no validan la conversión WebAssembly. Diferenciar también
  Linux, Windows nativo/CI, el PC del usuario e importaciones en programas CAD.
- Conservar los datos y las salidas anteriores: usar rutas nuevas para los STEP
  candidatos/finales y sus evidencias, sin sobrescribir certificados de otra pieza.

## Autonomía y publicación

Los cambios ordinarios de un encargo se comprueban y se publican mediante
commit y push en su rama conforme a la V2.2. Esa autonomía no permite relajar
validadores, sustituir motores ni comprometer datos o versiones protegidas.
No generar versiones, etiquetas, releases ni ZIP nuevos sin una solicitud
expresa del usuario; publicar código no equivale a aprobar una versión oficial.
Cuando se solicite una entrega, aplicar el formato de ZIP y enlace directo
visible de `../AGENTS.md`, indicando COMPLETA o ACTUALIZACIÓN, compatibilidad,
instalación y recuperación sin pérdida de datos.
