# R21 experimental COMPLETA: entorno independiente

## Qué entrega este ZIP

El usuario pidió una R21 completa al confirmar que la comprobación nativa del
instalador R20 también agotaba 90 segundos en su PC. Las actualizaciones ligeras
anteriores reutilizaban aquel entorno. Esta entrega suministra el programa,
el motor protegido y un gestor de instalación **exclusivos de R21**.

[Descargar R21 COMPLETA](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R21/entregas/perfeccion_Visualizador_R21/Conversor_3D_R21_EXPERIMENTAL_COMPLETA.zip?raw=true)

- Modalidad: **COMPLETA en fuentes con instalador**, no actualización para R20.
- Identidad: `21.0.0`, `.venv_r21` propio, `requires_r20: false`.
- Tamaño: **2.747.484 bytes**, 449 archivos.
- SHA-256: `3c2e3816ba6419dfe1749083b4ef449e87462c02964b1fd958fb37d2531bcc05`.
- [Fuentes de la entrega](https://github.com/cronos880-lang/Conversor_3D/commit/69f676f7745c73c87a4557a027d22af6c6f9b4c9).
- Manifiesto: árbol limpio al construir y hash por archivo.

Incluye las 357 fuentes R19 idénticas, sus créditos y fixtures históricos,
el código R21, sus recursos, locks, licencias e instrucciones. No incorpora
modelos privados del usuario ni ZIP históricos anidados. Los fixtures protegidos
se conservan; los marcados NO_APROBADO no se convierten en salidas aceptadas.

No contiene Python ni bibliotecas CAD de terceros redistribuidas. Usa el Python
3.12 x64 base instalado en el equipo y descarga los paquetes fijados al preparar
su entorno. El Python base no es la instalación del programa R20: las carpetas,
paquetes y datos de R20 no se consultan ni se copian. Hace falta Internet en la
primera preparación. No requiere compilar bibliotecas ni instalar REA/ArtCraft.

## Uso

1. Extraer TODO en una carpeta nueva, conservando las versiones anteriores.
2. Abrir **`Iniciar_R21.bat`**. En la primera apertura crea `.venv_r21`, instala
   y verifica sus paquetes y después abre el Visor.

Las aperturas posteriores conservan ese entorno. También se incluyen:

- `Instalar_Entorno_R21.bat`: preparar sin abrir el Visor.
- `Reparar_Entorno_R21.bat`: verificar archivos de paquetes y recuperar una
  extracción incompleta dentro de esta R21. Cerrar el Visor antes de reparar.
- `Diagnostico_R21.bat`: once bibliotecas comprobadas en procesos separados,
  con el nombre, tiempo y resultado de cada módulo.

Registros propios: `datos/arranque_R21.log`, `datos/instalacion_R21.log` y
`datos/diagnostico_R21_*.json`. Puerto: `8785`. Si no aparece el navegador,
la dirección local es `http://127.0.0.1:8785`.

La primera preparación puede tardar varios minutos: muestra cada paquete y
mensajes de actividad. No ejecuta el antiguo sondeo conjunto como condición final
de la instalación ni al iniciar. Se comprueban íntegramente versiones, hashes
de wheels y archivos de paquetes; los módulos nativos se diagnostican aislados.
Un fallo no provoca borrado automático del entorno ni cambios en R20.

## Pruebas

- Suite local: **63 aprobadas y dos omitidas exclusivas de Windows**.
- Integridad: 357 hashes R19 verificados; reglamentación general V2.3.1 literal
  conservada y complemento técnico actualizado para esta petición completa.
- Instalación local desde cero de un primer candidato y del ZIP final exacto,
  en carpetas con espacios: `.venv_r21` nuevo, versiones bloqueadas y paquete
  `conversor3d-visor-21.0.0` propio. Se suministraron rutas R20/datos/código ajenos
  deliberadamente inválidas para comprobar que no se usaban.
- Primera apertura del ZIP: instala y abre sin R20. Dos conversiones HTTP reales,
  STEP con bytes iguales y certificados nuevos con nonces distintos, material sin
  discrepancias y tres mallados completos. Reimportación con el **Python de la
  propia R21**: un sólido B-Rep válido, seis caras y volumen de 120 mm³. Tolerancia
  máxima `1e-7 mm`.
- Recuperación probada de un archivo `typing-inspection` eliminado sólo en ese
  entorno de prueba desechable; diagnóstico aislado de once bibliotecas aprobado.
- [Pruebas nativas en Windows y Linux](https://github.com/cronos880-lang/Conversor_3D/actions/runs/43838930582).

**Resultado nativo final: aprobado en Windows y Linux**, para el commit de fuentes
indicado. Windows: 65 pruebas actuales y 426 históricas aprobadas, 16 históricas
omitidas. Linux: 63 actuales aprobadas y dos exclusivas de Windows omitidas,
427 históricas aprobadas y 15 omitidas. Se conservan las condiciones de omisión.

En ambos sistemas pasó la instalación independiente completa, primera apertura,
dos conversiones, reparación de un archivo de paquete incompleto y diagnóstico
aislado de once bibliotecas. Windows usó los `.bat` reales, incluyendo la
detección del Python base y la creación inicial de `.venv_r21`. El log confirma:

```text
R21 COMPLETA: INSTALACION PROPIA, ARRANQUE, DOS CONVERSIONES, REPARACION Y DIAGNOSTICO OK; SIN R20
```

Las comprobaciones en un runner no sustituyen la ejecución en el PC del usuario. La entrega evita la
dependencia de su R20 y proporciona una preparación limpia; no se declara
identificada una biblioteca averiada de aquel equipo sin su diagnóstico.

## Conservación y alcance

Se mantienen motores, interfaz, cuatro botones, perfiles, presupuestos de error,
validadores y tolerancia B-Rep. No se anuncia una precisión nueva ni reducción
adicional de caras. El conversor web y sus automatizaciones no cambian.

Los ZIP R18/R19/R20 y las entregas ligeras R21 permanecen intactos. Esta modalidad
completa fue solicitada expresamente después; no implica una R22, una etiqueta,
un release ni aprobación oficial del usuario. Para recuperar otra versión, cerrar
esta y usar su lanzador. Las bibliotecas nativas instaladas se rigen por sus
licencias; se conserva la auditoría existente sin inventar una licencia global.

REA y Craft Anything se evaluaron como herramientas de desarrollo locales.
Python y OCP/CadQuery se utilizaron en las pruebas; no se añade Godot, Rust ni
dependencias nuevas al Visor. Las conexiones de inspección quedan fuera del ZIP.
