# Procedencia y licencias del Visor

Auditoría técnica del 11 de noviembre de 2026, desarrollo sobre R19. No asigna
una licencia global al proyecto ni autoriza una publicación. Se refiere al
Visor Python/OCP; el conversor web de la raíz es otro producto.

## Resultado y alcance

El constructor Windows conserva los archivos instalados de las dependencias,
incluidos sus metadatos y avisos. Ahora incorpora este documento, los textos de
OpenCascade y un inventario de los paquetes realmente incluidos, con hashes de
sus archivos de licencia. No se han publicado binarios, ZIPs ni artefactos de CI.

La selección actual del runtime contiene 70 distribuciones en Linux. El cierre
exacto depende de la plataforma: Windows genera su propio inventario en CI y
dentro de la carpeta portable de prueba. Los 77/78 paquetes de los locks incluyen
también herramientas de pruebas; no son el número de componentes del portable.

**La redistribución del conjunto queda pendiente de aclarar el permiso del motor
Easymeshfit y su compatibilidad con los componentes copyleft utilizados.** No se
deduce que esté prohibida ni que una autorización fuera del repositorio no
exista. Tampoco se considera que ejecutar una biblioteca en otro proceso elimine
automáticamente sus condiciones de licencia.

## Motor original y código del proyecto

La evidencia disponible es
[CREDITOS_MOTOR.txt](../entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes/CREDITOS_MOTOR.txt):

> Motor geométrico basado en el código Easymeshfit compartido con autorización
> para este proyecto.

El mismo documento identifica Easymeshfit V2.2, aportado por el usuario y
conservado en `motor_original_amigo/`. No se encontró en esos módulos un texto
que especifique permiso de redistribución en fuentes/binarios o sublicencia.
La auditoría conserva la autorización declarada; falta documentar su alcance.

Antes de declarar distribuible un paquete completo hay que confirmar con el
titular qué permite esa autorización y bajo qué condiciones. No se cambia la
licencia del motor ni se impone GPL al resto del repositorio para resolverlo.
Las copias históricas y sus créditos se mantienen intactos.

## Dependencias directas fijadas

Las versiones proceden de
[runtime-requirements.txt](src/conversor3d/resources/runtime-requirements.txt).
La tabla resume los textos encontrados; no sustituye sus condiciones completas.

| Componente | Versión | Textos y condición de redistribución |
| --- | --- | --- |
| CadQuery | 2.8.0 | Apache-2.0: conservar licencia, avisos aplicables y señalar modificaciones. |
| cadquery-ocp | 7.9.3.1.1 | Enlace Python Apache-2.0; el núcleo OCCT tiene licencia propia, descrita abajo. |
| trimesh | 4.11.1 | MIT: conservar copyright y permiso. |
| NumPy | 2.3.5 | BSD-3-Clause y avisos de bibliotecas incluidas en el wheel. |
| SciPy | 1.17.0 | BSD-3-Clause y avisos de componentes incluidos, entre ellos Qhull. |
| VTK | 9.6.2 | BSD; conservar sus avisos y los de los componentes que incluye el wheel. |
| Shapely | 2.1.2 | BSD-3-Clause; también incluye GEOS, LGPL-2.1, con condiciones propias. |
| FastAPI | 0.128.2 | MIT. |
| Uvicorn | 0.48.0 | BSD-3-Clause. |
| python-multipart | 0.0.31 | Apache-2.0. |
| manifold3d | 3.4.0 | Apache-2.0 en su archivo de licencia, aunque metadata no lo declare. |
| psutil | 7.2.2 | BSD-3-Clause. |
| NetworkX | 3.6.1 | BSD-3-Clause. |
| gpytoolbox | 0.3.8 | Metadata MIT, pero el wheel contiene MIT, MPL-2.0 y GPL. No clasificar todo como MIT. |
| CGAL Python bindings | 6.0.1.post202410241521 | El wheel declara GPLv3+ y contiene `LICENSE.GPL`. `LICENSE.COMMERCIAL` ofrece obtener otra licencia; no acredita que se haya adquirido. |
| libigl | 2.6.3 | Metadata MPL-2.0; contiene textos MPL-2.0, GPL y avisos adicionales. Revisar los componentes usados y conservar todos los avisos. |

### OpenCascade y OCP

Este programa hace uso de las prestaciones de **Open CASCADE Technology**.
El núcleo OCCT 7.9.3 se ofrece bajo LGPL-2.1 con la excepción Open CASCADE 1.0.
La excepción permite determinadas incorporaciones de cabeceras en código objeto
bajo condiciones propias; no convierte todas las bibliotecas de OCCT en Apache
ni suprime las obligaciones LGPL sobre ellas.

Se incluyen sin modificar
[LICENSE_LGPL_21.txt](licenses/LICENSE_LGPL_21.txt) y
[OCCT_LGPL_EXCEPTION.txt](licenses/OCCT_LGPL_EXCEPTION.txt), recuperados de
[OCCT V7_9_3, commit a016080bf6738d6aeae020badee4e888ad1540a5](https://github.com/Open-Cascade-SAS/OCCT/tree/a016080bf6738d6aeae020badee4e888ad1540a5).
En una distribución se deben conservar los avisos y atender las obligaciones
de fuentes de la biblioteca y de modificación/reemplazo o reenlace aplicables
a la forma concreta de empaquetarla. La licencia Apache del enlace se conserva
en `cadquery_ocp/LICENSE`.

### CGAL, gpytoolbox y libigl: uso real

El reparador congelado declara expresamente sus componentes copyleft. Además,
CGAL participa en la validación obligatoria: `validacion_fria_r19.py` llama a
`certificar_mallado`, que usa `ControlExacto` y
`CGAL_Polygon_mesh_processing.self_intersections` para comprobar el mallado.
No es correcto afirmar que CGAL sólo interviene en una reparación opcional.
La reparación opcional usa también `gpytoolbox_bindings_copyleft`.

Distribuir esos componentes bajo GPL requiere cumplir sus condiciones, incluidas
las obligaciones de fuentes correspondientes y los permisos necesarios sobre
el código que forme un trabajo combinado sujeto a ellas. El alcance concreto
sobre el motor y el conjunto necesita revisión según la autorización de sus
titulares. Separar procesos por STL/JSON es un dato de arquitectura, no una
conclusión automática de compatibilidad jurídica.

No se desactivan controles CGAL ni se reduce la validación para eludir este
punto. Tampoco se presupone una licencia comercial: el texto del wheel indica
que se puede obtener de GeometryFactory, sin concederla al proyecto.

## Dependencias transitivas y runtime

El [inventario Linux](licenses/runtime-linux.json) incluye los 70 componentes,
sus versiones, declaraciones de licencia, URLs y todos los avisos encontrados
en los archivos registrados por los wheels, con SHA-256. Los hashes de los
wheels completos están en los locks y manifiestos `visor/requirements-*-py312.*`.
La licencia declarada por un paquete no describe necesariamente todas sus DLLs
o bibliotecas estáticas internas.

Casos que requieren conservar condiciones adicionales:

- CPython 3.12: PSF y avisos de bibliotecas del runtime; se copia su `LICENSE`.
- GEOS, incluido por Shapely: LGPL-2.1, con su `LICENSE_GEOS` y obligaciones
  aplicables a la biblioteca distribuida.
- CasADi 3.8.2: LGPLv3+ y numerosos solvers/bibliotecas con licencias propias,
  incluidos textos EPL. Se conservan los archivos de `casadi/include/licenses/`.
  El archivo BQPD de este wheel concede redistribución tipo BSD; su nombre por sí
  solo no demuestra una restricción comercial.
- llvmlite 0.50.0: BSD-2-Clause y Apache-2.0 con excepción LLVM; Numba 0.68.1
  incorpora también avisos de terceros.
- NLopt 2.11.0: el texto de esta versión es MIT; no se aplica por suposición la
  licencia de otras versiones.
- setuptools 80.9.0: MIT y licencias de sus módulos incorporados.
- cadquery-ocp-proxy 7.9.3.1.1 declara Apache-2.0 en metadata, pero el wheel no
  incluye un archivo de licencia independiente. El inventario señala esta falta;
  no la oculta ni la interpreta como ausencia de restricciones.

Los demás componentes conservan sus avisos MIT, BSD, Apache, PSF, MPL u otros
registrados en el inventario. Antes de una redistribución externa debe completarse
la revisión de bibliotecas nativas incorporadas y prepararse la disponibilidad de
fuentes que corresponda; copiar un archivo de licencia no cumple por sí solo
todas esas obligaciones.

## Reproducir y preparar una entrega futura

Después de instalar el lock de la plataforma:

```console
python visor/scripts/audit_licenses.py --output inventario_nuevo.json
```

El script sólo lee el entorno e inventaría el cierre usado por el constructor;
no recoge piezas, rutas personales, tokens ni paquetes exclusivos de tests.
Rechaza sobrescribir un informe existente. No determina automáticamente si un
trabajo combinado puede distribuirse bajo una licencia concreta.

Antes de autorizar una entrega externa quedan estos puntos verificables:

1. Documentar el alcance del permiso Easymeshfit y resolver su compatibilidad
   con las condiciones copyleft del conjunto que se pretenda distribuir.
2. Revisar el inventario del Windows exacto que se entregaría, conservar los
   avisos y atender las obligaciones de fuentes/reemplazo de bibliotecas.
3. Resolver el aviso ausente de `cadquery-ocp-proxy` y comprobar los componentes
   nativos incluidos en cada wheel, no sólo su metadata.
4. Acordar expresamente la entrega. Esta auditoría no crea una versión, ZIP,
   publicación, cambio de visibilidad ni nueva política de licencias.
