# R20 experimental — resultados de la entrega

Programa completo en fuentes con instalador, autorizado por el usuario para
probar y contrastar avances mediante una revisión externa. Rama:
`perfeccion_Visualizador_R20`; commit fuente: `de7afba`.

## Descargar y abrir

[ZIP completo R20](https://github.com/cronos880-lang/Conversor_3D/blob/perfeccion_Visualizador_R20/entregas/perfeccion_Visualizador_R20/perfeccion_Visualizador_R20_EXPERIMENTAL_COMPLETA.zip?raw=true)

Extrae todo en una carpeta nueva y abre `Iniciar_R20.bat` dentro de
`Conversor_3D_R20_experimental`. La primera vez prepara su entorno `.venv_r20`:
requiere Python 3.12 x64 e Internet. Al terminar abre el Visor R20 en el puerto
8784. R19 y su entorno se mantienen independientes.

Dentro del ZIP están `LEEME_PRIMERO.md`, `INFORME_R20.md` y
`GUIA_REVISION_EXTERNA.md`. Junto al ZIP se conservan el manifiesto, el checksum
SHA-256, esta comprobación y los resultados resumidos de Bancada.

## Pruebas del paquete

[CI de la fuente y del ZIP R20 en Windows/Linux](https://github.com/cronos880-lang/Conversor_3D/actions/runs/43089880586)
terminó en verde. Windows extrajo el paquete en una ruta con espacios, instaló
en un entorno nuevo y utilizó sus `.bat` reales para instalar, diagnosticar y
arrancar. Se convirtió una caja por HTTP, se descargó su certificado completo
y se releyó el STEP con el Python del propio paquete: un sólido válido de
120 mm³. También se comprobaron OCP, VTK, CGAL, el portable de desarrollo y las
conversiones de cilindro, pared fina y taladro.

| Sistema | Pruebas del desarrollo | Históricas aprobadas | Históricas omitidas |
| --- | ---: | ---: | ---: |
| Linux | 43 | 427 | 15 |
| Windows | 43 | 426 | 16 |

El ZIP distribuido tiene SHA-256 idéntico al instalado y probado por CI Windows.
Se reprodujo ese contenedor desde los mismos archivos, normalizando únicamente
el campo HostOS de las cabeceras ZIP a Windows; los contenidos y el manifiesto
no cambian. La coincidencia exacta queda registrada en `VERIFICACION_ZIP_R20.json`.
No se sustituyen estas pruebas por una comprobación sólo de compilación.

## Resultados geométricos y límites

- Control sintético de parches B-Spline planos: 11 → 6 caras con el evaluador
  original completo. El control con taladro mantiene su abertura cilíndrica.
- Bancada, repetida con identidad y código R20: 101 caras, 53 planos,
  18 cilindros, 18 B-Spline y 12 extrusiones; un sólido B-Rep exacto válido,
  tolerancia máxima 1e-7 mm, cero discrepancias en 2.998 puntos de material y
  tres mallados cerrados/orientados con cero autointersecciones CGAL.
- El hash del código dentro del ZIP coincide con el código vinculado al
  certificado de Bancada. Sus STEP/STL y certificados detallados permanecen
  locales; se publica únicamente el resumen numérico y sus hashes.
- La propuesta adicional de Bancada se rechazó por el contrato de reducción.
  No se anuncia una disminución nueva sobre sus 101 caras.
- La ejecución R20 de Bancada tardó 833 s en este Linux con otras comprobaciones
  simultáneas; 759 s en la referencia y 63 s en el control frío final. No es
  una comparación de rendimiento con R19 ni una promesa para el PC del usuario.
- Los redondeos generales pueden seguir facetados y el loft libre agotó su
  sondeo previo. R20 no recupera un historial CAD paramétrico universal.

Los presupuestos geométricos, la validación completa y la tolerancia B-Rep
se mantienen. La tolerancia del CAD no equivale al error global entre STL y STEP.
Quedan pendientes tus pruebas en el PC y las importaciones en el CAD de destino.

## Procedencia e integridad

437 entradas, con 436 hashes de contenido y el manifiesto que los vincula al
commit fuente. Los 357 archivos R19 originales siguen intactos; el paquete
conserva sus fixtures históricos ya publicados. No incorpora modelos privados
nuevos ni binarios de terceros. Las dependencias se instalan localmente desde
los locks con hashes; el portable con runtime incorporado es otra modalidad
sujeta a la auditoría de redistribución.

No se cambia la interfaz, los perfiles, el repositorio web ni la instalación
anterior. Se conserva el procedimiento de entrega mediante ZIP en el repositorio.
