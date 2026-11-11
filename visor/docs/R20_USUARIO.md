# Visor STL a STEP — R20 experimental

Esta es la entrega R20 que has autorizado para probar y contrastar mediante un
informe externo. Mantiene los cuatro botones y los perfiles Precisión/Impresión.
No modifica tu R19 ni reutiliza su entorno para instalar paquetes encima.

## Abrir en Windows

1. Extrae TODO el ZIP en una carpeta nueva. Entra en `Conversor_3D_R20_experimental`.
2. Abre `Iniciar_R20.bat`. Si falta su entorno, lo preparará automáticamente.
3. La primera instalación necesita Python 3.12 de 64 bits y conexión a Internet.
   Puede tardar varios minutos: verás cuatro etapas y mensajes de progreso.
4. Al terminar se abre el Visor R20. Su dirección inicial es
   `http://127.0.0.1:8784`; R19 puede seguir usando su propio puerto.
5. Carga tu STL, convierte y exporta el STEP. Conserva también sus diagnósticos.

`Instalar_Entorno_R20.bat` permite preparar el entorno antes de abrir el programa.
`Diagnostico_R20.bat` genera `Diagnostico_Entorno_R20.json` con identidad y versiones.
La ventana indica expresamente si la instalación termina o encuentra un error;
los registros quedan en `datos/instalacion_R20.log`.

El ZIP contiene el programa completo en fuentes, sus lanzadores y los requisitos
con hashes. Las librerías se descargan desde PyPI al entorno propio `.venv_r20`.
No incluye Python, DLLs de terceros ni piezas privadas nuevas. Conserva los
fixtures de regresión que ya estaban publicados dentro de las fuentes R19;
no son resultados nuevos del conversor. No es la carpeta portable
con runtime incorporado; el constructor de esa carpeta permanece como herramienta
de desarrollo, sujeto a las condiciones de redistribución de sus componentes.
Usa los lanzadores de la raíz R20: los lanzadores R19 de los subdirectorios son
parte de la dependencia congelada y no preparan el flujo R20.

## Qué probar y guardar

- Usa las mismas piezas y el mismo perfil al comparar R19 con R20.
- Comprueba que se conserva la abertura de agujeros, paredes finas y vacíos.
- Guarda el STEP final y su diagnóstico con certificados/hashes; la validación
  completa sigue siendo obligatoria y mantiene la tolerancia B-Rep de 1e-7 mm.
- Si falla algo, conserva el texto del error y ejecuta `Diagnostico_R20.bat`.
  No borres tu instalación anterior para intentar repararlo.

La conservación predeterminada mantiene los resultados de `datos/`. Los modelos
se procesan localmente: este paquete no los sube a GitHub ni a otros servicios.
No incluye telemetría del proyecto ni requiere REA para funcionar.

## Expectativas verificadas

La mejora nueva reduce un control sintético de 11 a 6 caras y conserva el taladro
del control complementario. La Bancada continúa en 101 caras, con sólido válido
y validación completa; no hay una reducción adicional aceptada en esa pieza.
Los redondeos y superficies libres generales siguen teniendo limitaciones.
Consulta `INFORME_R20.md` y `GUIA_REVISION_EXTERNA.md` antes de valorar el alcance.
