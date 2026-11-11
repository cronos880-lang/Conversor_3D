# Hoja de ruta del Visor

Trabajo autorizado el 11 de noviembre de 2026. Rama de desarrollo independiente
sin reescribir historial, cambiar visibilidad, licencias ni sistema de ZIP.
R19, R18 y sus validadores permanecen congelados. El desarrollo vive en `visor/`.
No se anuncia una nueva versión ni se integra una propuesta sin aprobación fría.

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

Estado de las fases posteriores: 2–3 en preparación inmediata como soporte del
punto 1; 4–12 pendientes. Los resultados exactos de pruebas se anotan al cerrar
cada fase. Windows sólo se considera validado cuando termina su ejecución nativa.

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
