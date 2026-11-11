# Hoja de ruta del Visor

Trabajo autorizado el 11 de noviembre de 2026. Rama de desarrollo independiente
sin reescribir historial, cambiar visibilidad, licencias ni sistema de ZIP.
R19, R18 y sus validadores permanecen congelados. El desarrollo vive en `visor/`.
No se integra una propuesta sin aprobación fría. La solicitud posterior de
entrega R20 y sus comprobaciones se documentan al final de esta hoja de ruta.

## 1. Superficies y contornos compartidos

Proponente general de soportes residuales planares con curvas completas de
borde, pesos racionales positivos y ajuste minimax condicionado por los bordes.
Contrasta intersecciones OCP con vecinos analíticos. Conserva las caras analíticas
por identidad y hash B-Rep y sólo permite fusionar nuevos dominios residuales.
Tolerancia B-Rep 1e-7 mm, cota de construcción 5e-8 mm. Sin relleno ni healing.

Control conocido: caja con seis superficies B-Spline coplanares residuales,
11→6 caras, conserva las cinco caras analíticas originales. Se ejecuta el
validador R19 original completo, material y puntos comunes, con certificado.
No atribuir esta reducción a Bancada. Las pruebas sintéticas se generan sin
incorporar piezas privadas. La conexión al flujo de desarrollo se consolida
con las interfaces del punto 4; la entrega R19 no cambia.

Estado al cerrar inicialmente el punto 1: 2–3 en preparación inmediata y 4–12
pendientes. Los hitos posteriores se documentan a continuación. Windows sólo
se considera validado cuando termina su ejecución nativa.

Verificación del hito 1: 3 pruebas nuevas aprobadas; batería histórica 427
aprobadas y 15 omitidas por fixtures opcionales. La ejecución inicial detectó
rutas de importación incompletas y dos fixtures R5 sin configurar; el ejecutor
ahora lee esos fixtures de entradas concretas del ZIP histórico ya existente,
sin alterar código congelado ni publicar nuevas copias de modelos.

## 2. Pruebas nativas automatizadas

Workflow `visor-ci.yml` para Windows y Linux, Python 3.12 x64, acciones fijadas
por SHA y permisos de sólo lectura. Instala dependencias, ejecuta pruebas nuevas
y congeladas, arranca el servidor en un puerto libre y convierte realmente un
STL por HTTP. Reimporta el STEP, exige un sólido exacto válido y volumen conocido.
El smoke usa una copia temporal de las fuentes para no escribir registros en
las entregas. Linux: arranque y conversión 120 mm³ aprobados. El resultado de
Windows se registra por separado al terminar la ejecución de Actions.

Resultado nativo del hito 2: Windows y Linux en verde en
https://github.com/cronos880-lang/Conversor_3D/actions/runs/43029754390
(commit `ceddcd2`). La primera ejecución Windows detectó que Git cambiaba los
saltos de línea; se corrigió el checkout para conservar bytes, sin desactivar
la firma. Se verificaron instalación, pruebas nuevas, batería histórica y
conversión HTTP con relectura STEP en ambos sistemas. Esto valida esos casos
en Windows Server del runner; no se atribuye a una prueba en el PC del usuario.

## 3. Catálogo representativo

Siete referencias sintéticas conocidas: cilindro, redondeos, pared de 0,15 mm,
taladro de 0,3 mm, loft libre, variante girada y seis parches B-Spline coplanares.
Quince pruebas nuevas aprobadas, incluyendo control frío de un dominio residual
atravesado por un taladro y reconstrucción bajo tres movimientos rígidos.
Conversiones completas locales de cilindro, pared y taladro aprobadas, sin
pérdida de aberturas. Se añaden las mismas conversiones obligatorias a CI.
Los casos curvos más generales se registran como sondeos de capacidad: un
rechazo o tiempo agotado no se cuenta como STEP válido. Véase BENCHMARKS.md.

## 4. Propuesta y validación independientes

El coordinador de desarrollo está conectado a ambos endpoints mediante un
adaptador local del servidor existente. El proponente ejecuta en su proceso;
la puerta previa se conserva byte a byte como recurso con hashes. Cada salida
final tiene control frío completo y comprobación del certificado después de
copiar sus bytes; cambiar el STEP invalida el certificado. Los sidecars se
conservan también al descargar desde el servidor. Un rechazo del proponente
mantiene la referencia, sin convertir una interrupción en aprobación.

Verificación: 17 pruebas aprobadas, incluidos perfiles Precisión e Impresión,
rechazo de un certificado sobre otro STEP, control de material y tres mallados.
Smoke real de desarrollo por HTTP aprobado en Linux, incluido certificado
descargable y volumen 120 mm³. CI mantiene el smoke original y añade el nuevo.
El hito 3 también terminó en verde en Windows y Linux en la ejecución
https://github.com/cronos880-lang/Conversor_3D/actions/runs/43031074761

Límite observado del catálogo: el STL de redondeos teselado automáticamente
convierte, pero conserva 19.891 caras y tarda unos 259 s. No se presenta como
reconstrucción analítica de 5 caras. El loft libre agotó el límite de sondeo
300 s sin resultado completo. Se conservan esas limitaciones para el perfilado.

## 5. Inventario y protección de copias

Auditoría completa: 357 archivos congelados intactos; 32 nombres con variantes
divergentes y 84 grupos de contenidos idénticos. Se documenta el papel de cada
núcleo; no se fusionan implementaciones distintas ni se eliminan las copias
independientes de calidad. El desarrollo nuevo y la factoría de pruebas tienen
una sola implementación. El manifiesto se comprueba también en CI.

Dos pruebas nuevas aprobadas: integridad de los 357 archivos y detección de
modificación sin importar el código auditado. No hay cambios de lógica en esta
fase; siguen vigentes las 17 pruebas del flujo y la batería histórica anterior.

## 6. Perfilado y reutilización verificable

Se registran tiempos de reconocimiento, ajuste/intersecciones de bordes,
exportación, referencia completa, puerta, certificado final y comprobación de
trazabilidad. cProfile optativo mide también los procesos internos históricos
sin cambiar sus fuentes. Ensayo completo perfilado de cilindro aprobado,
27,9 s totales en este entorno; no se presenta como comparación de velocidad.

La caché del lector sólo usa bytes, perfil, versión del lector/núcleo y
bibliotecas idénticos; verifica arrays por hash y no usa pickle. Es análisis
auxiliar, nunca autoridad de geometría. Un control frío completo recién emitido
por la puerta puede reutilizarse para sus mismos bytes y perfil dentro de la
misma selección; el archivo copiado vuelve a verificar su certificado.

21 pruebas aprobadas: incluyen cambio de entrada/perfil, caché corrupta,
reutilización del control completo y certificado final. Se conserva el coste
de las firmas. No se amplían tolerancias ni se omite material/mallado final.

CI detectó además un test histórico que elegía el primer JSON de un directorio,
y a veces leía un sidecar en lugar del diagnóstico. El ejecutor fija el orden
sólo para ese directorio temporal y ese test, manteniendo todas sus aserciones y
sin modificar el archivo congelado. El caso vuelve a pasar sin omitirlo.

## 7. Preparación autocontenida Windows

Constructor y smoke de carpeta portable, sin ZIP ni publicación: runtimeCPython,
selección de dependencias transitivas, fuentes y manifiesto de hashes. Lanzador
usa su propio Python; imports aislados mediante _pth. El smoke comprueba OCP/VTK,
conversión real, certificado y volumen con PATH sin Python externo. El motor
congelado admite ruta explícita verificada para la carpeta portable.

Verificación local Linux: 21 pruebas aprobadas tras añadir la resolución de
rutas; construcción/ejecución portable requieren Windows y se verifican en CI.
No se afirma que el paquete haya sido probado en el ordenador del usuario ni
se autoriza redistribuir componentes sin el inventario legal posterior.

Resultado Windows del hito 7: ejecución
https://github.com/cronos880-lang/Conversor_3D/actions/runs/43036702478
en verde en ambos sistemas. Se construyó una carpeta de prueba con 70
distribuciones y 13.966 archivos, sin publicarla. El runtime aislado importó
OCP/VTK/CGAL, convirtió y certificó una caja y releyó su STEP por sí mismo.

## 8. Identidad, ajustes y causas

Una fuente de versión para paquete, CLI y UI; pyproject la obtiene del módulo
_version. Configuración validada con unidades, directorios explícitos, puerto,
perfil, caché y conservación. Las tolerancias no son parámetros editables.
El desarrollo se identifica como tal, mantiene la interfaz y los perfiles, y no
abre el navegador sobre otra instancia que ocupe el puerto.

27 pruebas generales aprobadas y siete comprobaciones de configuración
(incluyen rechazo de rutas vacías). Smoke HTTP con identidad de desarrollo,
conversión y certificado descargable aprobado en Linux. Los errores finales
incluyen código de etapa y causa del control frío cuando está disponible.

## 9. Dependencias, acceso local y conservación

Locks completos con hashes de wheels para CPython3.12 x64:77paquetesLinux,
78Windows. Instalación limpia independiente aprobada con --require-hashes,
--only-binary y pipcheck. Actualizado multipart0.0.31; probado el parser real
urlencoded y registrado el motivo de la actualización. Las versiones directas
y su especificación forman parte de la identidad del entregable.

El middleware verificaHost/Origin antes de leer cuerpos; CORS sólo permite
orígenes locales de esta instancia. La conservación predeterminada no borra.
Con plazo explícito sólo limpia registros propios terminales, nuncaactivos,
ajenos, enlaces o diagnósticos incompletos. No se recorren originales externos.

Validación con el entorno nuevo:38pruebas del desarrollo aprobadas y427pruebas
históricas aprobadas,15omitidas. SmokeHTTP real con Origin/Host, conversión y
certificado descargable aprobado enLinux. Los357archivos congelados permanecen
intactos. La matrizCI vuelve a ejecutar los mismos controles y el portable.

Resultado nativo del hito 9: Windows y Linux en verde en
https://github.com/cronos880-lang/Conversor_3D/actions/runs/43042892418
(commit `02bf18c`). Windows instaló el lock con hashes y comprobó los imports
nativos, la conversión HTTP, el certificado y el portable aislado de 70 paquetes.
No se publicó la carpeta de prueba ni se cambió la entrega R19.

## 10. Licencias y procedencia

Inventario reproducible de los 70 componentes del runtime, sus declaraciones y
todos los avisos encontrados en los wheels con SHA-256. El constructor añade el
inventario de su Windows, el resumen y los textos LGPL/excepción de OCCT.
Se distingue la licencia Apache de OCP de la LGPL del núcleo, y la metadata MIT
de gpytoolbox de sus componentes copyleft. CGAL también se usa en el control
frío obligatorio; no se elimina esa comprobación para cambiar condiciones.

La auditoría está en THIRD_PARTY_LICENSES.md. CREDITOS_MOTOR.txt sólo recogía
autorización «para este proyecto». A la pregunta expresa sobre fuentes y binarios,
el usuario confirmó «tengo permiso total, es un colaborador». Se registra esa
aclaración sin elegir una licencia global ni presumir una prohibición. La
distribución externa del conjunto sigue sujeta a las condiciones de terceros.

La aclaración solicitada conforme al punto 10 está recibida; el desarrollo
continúa con las fases 11–12. Las fuentes congeladas y las entregas se conservan.

Verificación local: 40 pruebas del desarrollo aprobadas; 427 históricas
aprobadas y 15 omitidas. Compilación de scripts y enlaces locales de la auditoría
correctos; 357 archivos congelados conservan sus hashes. El inventario registra
los avisos legales y señala el paquete proxy sin texto independiente, sin ocultarlo.

## 11. Limpieza gradual del desarrollo

Docstrings, tipos y nombres más explícitos en la propuesta y su coordinación,
sin reformatear el núcleo congelado. Los errores de la propuesta incluyen un
código estable y el motivo se conserva en la selección de referencia.

La propuesta opcional respeta ahora el mismo presupuesto de 1.200 caras que
las costuras R19. Una referencia mayor no entra en el análisis costoso y no se
reescribe. Este límite de trabajo no altera el presupuesto de error, no evita
la conversión base y no exime al STEP final de su certificado completo.
Se prueba con un prisma real de 1.203 caras, incluidos el proceso separado,
el rechazo temprano y la conservación exacta de los bytes.

Validación del hito 11: compilan las fuentes del desarrollo, 41 pruebas nuevas
aprobadas y batería histórica de 427 aprobadas/15 omitidas. No se modifican
fuentes ni validadores congelados.

## 12. Documentación, Git y entregas

README principal distingue el conversor web, R19 histórica y el desarrollo del
Visor. Se corrige el encabezado que sólo anunciaba R18 y se enlaza la R19 ya
existente, sin reconstruir su ZIP. El enlace histórico responde HTTP 200 y su
blob coincide con el árbol del commit publicado `e105759`.

Se documentan comandos, certificados y condiciones del portable. Sus enlaces
locales de créditos y requisitos se adaptan a la estructura real de la carpeta
autocontenida. Las instrucciones del repositorio aclaran el ámbito de cada
producto sin cambiar el procedimiento de entrega.

No se han identificado archivos huérfanos que se puedan borrar con seguridad:
las copias congeladas, los lanzadores antiguos y los ZIPs tienen una función
histórica deliberada. Los resultados temporales propios quedan fuera del árbol
versionado o en rutas ignoradas. No se reescribe historial ni se cambian ramas
de entrega, visibilidad, etiquetas, releases o el sistema actual de ZIPs.

Las 12 fases tienen implementación y evidencia registradas. La auditoría anota
la autorización del colaborador; las obligaciones de terceros se conservan para
cualquier entrega futura. La matriz nativa final se consulta en el workflow del
Visor, sin equipararla a ensayos en el ordenador del usuario o CADs de destino.

Verificación local de cierre: 41 pruebas del desarrollo y 427 históricas
aprobadas, 15 omisiones históricas. Compilación correcta; 13 documentos y 22
enlaces locales revisados sin ausencias. R19 conserva los 357 hashes; también
se verificaron las dos copias R18 de 342 archivos, 22 entradas y 21 selecciones
anteriores sin alteraciones. El checkout independiente del conversor web está
limpio. CI comprueba además avisos de licencia, hashes y enlaces dentro del
portable Windows real, además de su conversión certificada.

La última matriz detectó una clasificación incorrecta del inventario: el módulo
`packaging/licenses` aportaba fuentes/cachés Python como si fueran avisos legales.
Se excluyen esos archivos de código y bytecode, se regenera el inventario y se
añade el caso a la prueba de avisos mixtos. El constructor sigue conservando los
textos reales y el smoke verifica sus hashes; no se desactiva la comprobación.

Ensayo real del flujo final con Bancada: conversión completa en 764 s en Linux,
101 caras, un sólido exacto válido, tolerancia máxima 1e-7 mm y cero discrepancias
en 2.998 puntos de material. Tres mallados cerrados/orientados con cero
autointersecciones CGAL. La propuesta adicional no reduce conforme al contrato
y se rechaza, conservando la referencia. No se atribuye una nueva reducción a
Bancada. Sus archivos de prueba permanecen locales, fuera del repositorio.

## Entrega R20 autorizada

El usuario solicita crear R20 para probarla y contrastarla con otro informe.
Se prepara en la rama independiente `perfeccion_Visualizador_R20`: identidad
20.0.0, puerto propio, lanzadores, entorno `.venv_r20` y diagnóstico. El ZIP
contiene las fuentes completas y los fixtures históricos inalterados de R19;
no redistribuye runtimes ni modelos privados nuevos. Instala las dependencias
fijadas con hashes en el equipo del usuario, sin modificar su R19.

Se añaden pruebas de integridad del paquete y de rechazo de fuentes alteradas.
La comprobación Windows extrae el ZIP en una ruta con espacios, ejecuta sus
lanzadores de instalación/diagnóstico/arranque, convierte por HTTP y verifica
el STEP y su certificado usando el Python del nuevo entorno. La publicación
del ZIP se realiza después de esas comprobaciones.

Preparación local R20: 43 pruebas del desarrollo y 427 históricas aprobadas,
15 omisiones históricas; los 357 archivos congelados mantienen sus hashes.
El ZIP preliminar se ha extraído y ha arrancado/convertido por HTTP en Linux,
releyendo un sólido válido de 120 mm³ y descargando su certificado completo.

## Corrección del instalador R20

El usuario informa de espera sin mensajes en `Installing collected packages`.
La revisión 2 cambia la instalación masiva silenciosa por pins individuales con
todos sus hashes, progreso por paquete, actividad durante silencios y plazos
acotados. Se desactiva compilación de bytecode de pip y se vacía el registro en
cada línea. Se verifican los archivos usando el RECORD original: la API files
puede filtrar los ausentes y no sirve para diagnosticar una extracción parcial.

El reparador conserva entorno y datos, bloquea ejecuciones simultáneas y repara
paquetes incompletos. Se prueba explícitamente una interrupción simulada antes
del arranque/conversión Windows. No cambia ningún archivo de visor/src/conversor3d
ni del núcleo R19. La reparación se entrega como superposición sobre R20 y como
ZIP completo corregido; los archivos originales publicados se conservan.

Verificación local de la corrección: ocho pruebas de instalador/paquete
aprobadas. La prueba real retiró un archivo de un paquete de un entorno
controlado, lo recuperó desde su wheel con hashes y conservó los paquetes
correctos; después pasaron los imports de la aplicación y pip check.
