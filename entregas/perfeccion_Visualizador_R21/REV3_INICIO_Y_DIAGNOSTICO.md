# R21 revisión 3: bloqueo del sondeo de bibliotecas

## Fallo comunicado

El registro del PC Windows confirma que se localiza R20 y se llega a la comprobación
de Python. El proceso auxiliar que importaba juntas `OCP`, `vtk`, `CGAL`,
`gpytoolbox`, `igl`, `fastapi`, `uvicorn` y `manifold3d` no terminaba en 90 s.
La revisión 2 mejoró la detección del entorno, pero conservaba ese sondeo conjunto.

El registro no permite saber qué módulo tarda, si hay una inicialización nativa
bloqueada o si se acumulan tiempos de carga. No se atribuye el fallo a una DLL,
antivirus o biblioteca concreta sin evidencia del equipo.

## Corrección

El inicio normal mantiene los 357 hashes R19, Python 3.12 x64 y la coincidencia
exacta de versiones. Esa comprobación lee metadatos sin importar el conjunto
nativo. Después arranca el servidor existente, que carga las bibliotecas que
necesita para servir el Visor. Se muestran el comienzo y final de esa carga y la
dirección local del servidor.

`Diagnostico_R21.bat` realiza la comprobación completa: once importaciones,
**cada una en un proceso nuevo**, incluyendo CadQuery, Trimesh y SciPy además de
los ocho módulos originales. Muestra el módulo, actividad cada diez segundos y
tiempo de carga. Si uno falla o excede su propio plazo, se detiene su proceso y
descendientes y continúa con el siguiente. Guarda un JSON fechado en `datos`.

No se aumenta el antiguo plazo global para dejar que el mismo sondeo siga
esperando. Se separan la preparación ligera, la carga del servidor y el
diagnóstico nativo aislado. El diagnóstico no es una aprobación de geometría.

Las conversiones siguen usando el motor, las dependencias bloqueadas y los
validadores congelados. No cambian los presupuestos de error, el control frío,
material, mallado ni tolerancia B-Rep `1e-7 mm`. La interfaz se conserva.

## Entrega

**ACTUALIZACIÓN R21, revisión de lanzadores 3**, para R20 preparada. No es una R22.
Los ZIP anteriores permanecen intactos.

[Descargar revisión 3](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R21/entregas/perfeccion_Visualizador_R21/Conversor_3D_R21_ACTUALIZACION_REV3.zip?raw=true)

- Tamaño: 88.118 bytes, 38 archivos.
- SHA-256: `177eb75b7632a05f564430954457f44a5d00f6a8d5d9e1794a1668b79e6ff518`.
- [Fuentes](https://github.com/cronos880-lang/Conversor_3D/commit/097f5aa653bf1646c37dc7d3abb43ab9a17f932d).
- El manifiesto registra ese commit y árbol limpio al construir.

Extraer todo en una carpeta nueva y abrir `Iniciar_R21.bat`, conservando R20.
Para diagnosticar un fallo, abrir `Diagnostico_R21.bat`; el resultado completo
queda en `datos/diagnostico_R21_*.json` y los mensajes en `datos/arranque_R21.log`.
Para volver a la copia anterior, cerrar esta y abrir su lanzador, sin desinstalar.

## Verificación realizada

- Suite local: **61 aprobadas, una omitida exclusiva de Windows**.
- Integridad R19: 357 archivos verificados, sin errores.
- Prueba de proceso bloqueado: se informa el módulo, se detiene al vencer el
  plazo y se continúa; también se identifica un `ImportError` con su mensaje.
- Prearranque con módulos nativos inaccesibles simulados: las versiones se
  comprueban sin importarlos.
- Prueba funcional local con una importación `gpytoolbox` bloqueada artificialmente:
  el Visor HTTP real abrió en 3,483 s sin cargarla. Esto reproduce un mecanismo
  posible; **no demuestra que gpytoolbox sea el módulo bloqueado del PC**. En esa
  prueba no se hicieron conversiones ni se presentaron geometrías simuladas como válidas.
- ZIP final sin alterar bibliotecas: dos conversiones HTTP reales, STEP reimportados
  válidos de seis caras y 120 mm³, certificados nuevos, material sin discrepancias,
  tres mallados y R20 conservada. Diagnóstico real de las once bibliotecas aprobado
  en Linux, con tiempo individual registrado para cada una.
- [Pruebas nativas Windows y Linux](https://github.com/cronos880-lang/Conversor_3D/actions/runs/43829031544).

**Resultado nativo final aprobado en Windows y Linux** para el commit indicado.
Windows: 62 pruebas actuales y 426 históricas aprobadas, 16 históricas omitidas.
Linux: 61 actuales aprobadas y una exclusiva de Windows omitida, 427 históricas
aprobadas y 15 omitidas. Se conservan las condiciones de omisión anteriores.

Windows comprobó también el `.bat` sin Python global, dos conversiones con STEP
válidos y certificados nuevos, R20 intacta y el diagnóstico real de las once
bibliotecas en procesos separados. El log confirma ambas fases:

```text
R21 LIGERA: ARRANQUE, DOS CONVERSIONES Y STEP VALIDOS; R20 INTACTA
R21: DIAGNOSTICO REAL DE 11 BIBLIOTECAS EN PROCESOS SEPARADOS OK
```

Las pruebas en un runner no equivalen a probar el PC del usuario ni identifican
por sí solas su problema nativo. Si el servidor aún no puede cargar una dependencia necesaria,
su fallo no se convierte en una conversión aprobada: debe investigarse mediante
el diagnóstico por módulo.

REA y Craft Anything siguen siendo herramientas de desarrollo locales y no se
añaden al Visor. Se conserva su configuración y documentación de conexión.
