# Pipeline B-Rep R19

R19 conserva la reconstrucción analítica de R18 y la rodea de contratos de
entrada, propuestas aisladas y aprobación del STEP serializado. Los archivos
originales del motor geométrico, el núcleo de calidad y los perfiles se mantienen.
El servidor de esta copia ejecuta `motor_r19.py` en sus dos rutas HTTP.

## Módulos implementados

| Módulo | Responsabilidad |
| --- | --- |
| `ingesta_r19.py` | Lee `Poly_Triangulation` con `RWStl`; contrasta triángulos, conectividad, bordes, orientación, degenerados y hash con el STL original. No confunde malla cerrada con sólido CAD. |
| `motor_v2.py` y constructores R18 | Segmentación, ajuste de superficies y reconstrucción analítica existente. Conservan sus estrategias, reparaciones y controles de detalles. |
| `reconocimiento_r19.py` | Inventario de soportes CAD y adyacencias por identidad topológica. Coplanaridad exige normales paralelas y posición coincidente; la mera proximidad no crea una conexión. |
| `topologia_r19.py` | `BRepBuilderAPI_Sewing`, comprobación de bordes libres y múltiples, `BRepBuilderAPI_MakeSolid`, orientación y `BRepCheck_Analyzer` exacto. CadQuery envuelve el `TopoDS_Solid` construido. |
| `optimizacion_r19.py` | Propone consolidación de planos con `ShapeUpgrade_UnifySameDomain` en modo seguro, protegiendo todas las aristas incidentes a soportes curvos. |
| `costuras_r19.py` | Agrupa cilindros por soporte y conectividad, conserva contornos, reconstruye pcurves y costuras con `ShapeFix_Face` y contexto `ShapeBuild_ReShape`, certifica los dominios y vuelve a coser. |
| `exportacion_r19.py` | STEP AP214 en mm con `STEPControl_Writer`, estados de transferencia/escritura y reimportación obligatoria. Incluye alternativa CadQuery probada. |
| `validacion_fria_r19.py` | Ejecuta el núcleo original en proceso frío: auditoría del STEP, B-Rep exacto, interferencias, cotas, volumen, distancias, topología, tres mallados CGAL, material y detalles reconstruidos. |
| `validacion_r19.py` | Verifica el certificado original y la comparación original de candidatos; añade no empeorar máximos ni tolerancias y contraste en puntos comunes. |
| `pipeline_r19.py` | Orquesta, conserva la referencia y selecciona una propuesta aprobada. Los cambios de perfil y los errores de procesos no se convierten en una aprobación. |
| `procesos_r19.py`, `trabajador_r19.py` | Aíslan ingesta, construcción y controles nativos, acotan su tiempo, registran stdout/stderr y detienen el árbol de hijos ante timeout. |
| `respaldo_r19.py`, `contratos_r19.py` | Copias con hashes, informes atómicos y respaldo de la conversión R18 completa antes de optimizar. La cancelación explícita nunca se convierte en éxito. |

## Manipulación OCP / CadQuery

Las formas CadQuery exponen el objeto OCP en `.wrapped`. `cq.Shape.cast(...)`
envuelve la topología ya construida; no crea por sí solo un sólido válido.

La ingesta conserva el STL como referencia inmutable. No genera sistemáticamente
una cara B-Rep por triángulo: R18 reconstruye primero los soportes y sus regiones.
Así la ruta principal conserva superficies analíticas, contornos y taladros.

Las propuestas se construyen sobre copias profundas de la geometría. En una
costura cilíndrica, las caras comparten curvas físicas de borde y pcurves sobre
el soporte. La costura periódica y el dominio recortado se controlan antes y
después de exportar. No se suprimen caras pequeñas por defecto ni se aumenta
automáticamente la tolerancia para cerrar una pieza.

Los dos métodos de optimización parten de la misma referencia aprobada. Se
selecciona la propuesta con menos caras entre las que superan todos los
controles. No se encadenan transformaciones sin validar ni se afirma una
optimización global del número de caras.

## Contratos geométricos

- Costura: 0,0000001 mm. Proyección de bordes: error máximo 0,00000005 mm.
- Un único sólido, sin bordes libres, con B-Rep exacto y volumen positivo. La
  conservación de cavidades y material requiere además el núcleo original.
- Propuestas inicialmente acotadas a 1.200 caras CAD y STL cerrado, orientado y
  manifold de hasta 50.000 triángulos. Las entradas reparadas mantienen la ruta
  original. Fuera de alcance se conserva R18.
- La selección original exige una reducción suficiente; se mantiene incluso
  cuando una propuesta geométricamente válida reduce sólo dos caras.
- Se rechazan incrementos del máximo verificado superiores a 0,000001 mm y
  aumentos de tolerancia B-Rep superiores al margen numérico de 0,000000001 mm.
- El contraste suplementario usa todos los vértices, centros de triángulos y
  1.000 muestras de área con semilla fija. Rechaza aumentos locales superiores
  a 0,0001 mm. No sustituye las medidas bidireccionales ni constituye una prueba
  de distancia Hausdorff global.
- Los tres mallados conservan deflexiones de 0,00025 / 0,0005 / 0,001 mm y deben
  estar cerrados, orientados y sin autointersecciones CGAL. La banda de material
  original sigue en 0,002 mm; no se amplía.

## Integración y evidencias

La interfaz conserva sus cuatro botones y perfiles. Cambian la identidad R19,
la fecha y el puerto 8782. `/convertir` e `/iniciar-conversion` usan el mismo
pipeline. Los diagnósticos guardan el informe de R19 y el certificado del STEP
seleccionado antes de eliminar el temporal del trabajo.

Una interrupción durante las propuestas puede recuperar el respaldo R19, que
contiene la conversión R18 ya terminada. Si la interrupción sucede antes, se
conserva el mecanismo de respaldos anterior. Los hashes del original, el STEP y
el perfil deben coincidir. Una cancelación impide recuperación y descarga.

`VISOR_PIPELINE_R19=0` permite aislar la referencia en pruebas técnicas sin
desactivar la calidad de R18. No es necesario modificar ajustes para el uso
normal del Visor.

`Herramientas_Pruebas/ensayar_referencia.py` permite evaluar una referencia CAD
existente y conserva el origen del ensayo. Su resultado no se presenta como
una conversión completa nueva desde STL.

Las herramientas y tests de desarrollo requieren también
`Visor_experimental_fuentes/requirements_pruebas.txt`. `preparar_controles.py`
genera tres referencias CAD sintéticas independientes en una carpeta nueva;
`ensayar_referencia.py` las evalúa con el mismo trabajador y la misma selección
del programa. La ejecución normal del Visor conserva sus dependencias R18.

## Alcance y trabajo posterior

La reconstrucción de cilindros parciales y encuentros conserva las capacidades
ya existentes de R18. Los prototipos UV y de recorte que no demostraron mejora
no se activan. Tampoco se atribuye la consolidación de costuras a nuevas
detecciones Efficient RANSAC: utiliza OCP y verificaciones CGAL.

La reconstrucción nueva de superficies libres, la combinación de propuestas y
la ampliación del contrato a otras topologías requieren más desarrollos y sus
pruebas. La exportación AP214 y la relectura OCP no garantizan por sí solas
compatibilidad total con todos los editores CAD; los ensayos nativos en Windows,
Onshape, SolidWorks e Inventor se distinguen de los ejecutados en Linux.
