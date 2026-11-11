# Informe de entrega R20 experimental

Autorizada el 11 de noviembre de 2026. Desarrollo de partida: commit `8cd2656`
de la rama `desarrollo/hoja-ruta-visor`. El manifiesto del ZIP identifica el
commit fuente de esta entrega y los hashes de todos sus archivos.

## Cambios respecto a R19

| Área | R20 |
| --- | --- |
| Propuesta geométrica | Planos residuales ajustados a sus contornos completos; contraste con vecinos analíticos; caras planas/cilíndricas protegidas. |
| Aceptación | Proponente separado; evaluador previo intacto y certificado frío completo del STEP final. Un rechazo conserva la referencia. |
| Pruebas | Catálogo sintético con cilindros, redondeos, pared fina, taladro, superficies libres y rotaciones; CI real Windows/Linux. |
| Instalación | Lanzadores propios y entorno `.venv_r20`, versiones y hashes bloqueados; imports OCP/VTK/CGAL comprobados. |
| Rendimiento | Tiempos por etapas, perfilado optativo y caché de análisis para bytes idénticos; validación final completa. No se anuncia una aceleración global. |
| Seguridad local | Control de Host/Origin antes de leer formularios; multipart actualizado; conservación configurable y prudente. |
| Diagnóstico | Versión centralizada, errores con causa, trazabilidad STL/STEP/perfil/motor y diagnóstico del entorno. |
| Procedencia | Inventario de dependencias, licencias y permiso del motor del colaborador documentados. |

La interfaz y los perfiles se conservan. R18/R19, sus fuentes y validadores no
se modifican: R20 consume una copia de los 357 archivos congelados R19, comprobada
por hashes. No se fuerza una licencia global ni se cambia la visibilidad.

## Resultados ya medidos del motor entregado

- Control de parches B-Spline planos: **11 → 6 caras**, sólido válido y control
  frío completo; el ensayo con taladro conserva su abertura cilíndrica.
- Bancada real: **101 caras**, 53 planas, 18 cilíndricas, 18 B-Spline y 12 de
  extrusión. Un sólido B-Rep exacto válido, tolerancia máxima 1e-7 mm; cero
  discrepancias en 2.998 puntos de material y tres mallados cerrados/orientados
  sin autointersecciones CGAL. La propuesta adicional se rechaza por el contrato
  de reducción: no se atribuye una mejora nueva de caras en Bancada.
- Ejecución Bancada de referencia antes de cambiar la identidad a R20:
  764 s en Linux; 691 s corresponden a la generación R19 y 63 s al certificado
  final. Es una medición de ese entorno, no una promesa para Windows.
- Base de pruebas anterior al empaquetado: 41 pruebas del desarrollo; 427
  históricas/15 omitidas en Linux y 426/16 en Windows. La matriz de la entrega
  vuelve a comprobar el código, el arranque y las conversiones reales.

Los valores de tolerancia B-Rep describen el CAD, no una distancia global de
1e-7 mm entre el STL y el STEP. Los presupuestos geométricos de los perfiles y
la validación del material se conservan por separado, sin relajarlos.

## Límites y comprobaciones pendientes del usuario

El caso sintético de redondeos puede quedar con 19.891 caras; un sondeo de loft
libre agotó 300 s. No se promete reconstrucción paramétrica universal ni historial
de operaciones. Faltan tus ensayos en el PC concreto y la importación en los CAD
de destino; las pruebas del runner Windows no los sustituyen.

Esta entrega en fuentes no redistribuye los binarios de CGAL, CasADi, METIS u
otras librerías. Su instalación local respeta los locks y conserva sus avisos.
La distribución de una carpeta con todos esos binarios requiere la revisión
concreta descrita en `visor/THIRD_PARTY_LICENSES.md`.
