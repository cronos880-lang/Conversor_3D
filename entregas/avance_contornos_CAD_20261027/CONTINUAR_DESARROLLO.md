# Continuar desde las pruebas de esta entrega

La copia principal M3 tiene 111 archivos congelados y la nueva API optativa `contornos_compartidos=True`. La ruta de uso, el servidor y la interfaz no la activan. Su pinza de 447 caras está comprobada con lectura exacta, BOP, evaluador R7 y tres mallados CGAL. Repetida desde la copia del paquete, conserva exactamente el bloque geométrico `DATA`.

El candidato posterior añade prioridad a los cilindros que el detector respalda con todos sus vértices y centroides. Está separado en `variante_prioridad_cilindros`, con fuentes completas y manifiesto propio. No trasladar automáticamente a él la batería de 21 conversiones ejecutada con M3. Su suite completa y sus casos específicos se registran aparte.

## Siguiente fallo concreto de Bancada

La variante conserva los quince cilindros y pasa exactitud, BOP, volumen, caja y contraste geométrico denso. El primer mallado bruto, a 0,00025 mm y 0,04 rad, deja **tres aristas de borde**; Euler resulta −15 frente a −14 de la fuente. No hay triángulos de área cero, aristas de más de dos caras ni vértices no manifold en ese diagnóstico. Eso sigue siendo un rechazo.

Se preservan el STEP rechazado en `NO_APROBADOS/bancada_prioridad_cilindros.step`, las medidas y los propietarios de triángulos en `evidencias/intentos/bancada_mallado_fallo_localizado.json` y el NPZ del mismo nombre. Los tres vecinos CAD son 697, 1024 y 1209 en esa exportación; son datos del diagnóstico, no reglas que deban incorporarse al motor. El archivo permite investigar el encuentro sin repetir antes todo el control BOP.

Investigar la coherencia de los extremos 3D, sus pcurvas y el mallado del encuentro; corregir la construcción geométrica/topológica. No cerrar el mallado de validación a posteriori, retirar triángulos, ampliar su soldadura ni cambiar el validador para convertir este fallo en éxito. El control inmutable M1 está en `herramientas/control_frontera_M1_inmutable.py`.

## Lego 4×2

La entrada conserva ocho cavidades verificadas y no se deben rellenar. M3 construye 940 caras sin bordes CAD libres, pero el sólido es inválido. Las variantes de booleanos, representación local de cónicas, círculos canónicos y división de caras periódicas no lo resolvieron. No están incorporadas a las fuentes principales.

El diagnóstico de contención entre shells reproduce puntos que utiliza OpenCascade y muestra clasificaciones contradictorias entre cavidades separadas. Se efectuó sobre el candidato anterior v24 de 662 caras, conservado en `NO_APROBADOS`; no demuestra por sí solo la causa del rechazo del candidato posterior de 940 caras. Véase `evidencias/intentos/lego_puntos_contencion.json`. La referencia consultada fue [BRepCheck_Solid de OCCT 7.8.1](https://github.com/Open-Cascade-SAS/OCCT/blob/V7_8_1/src/BRepCheck/BRepCheck_Solid.cxx). La fórmula del punto de comprobación en el script de diagnóstico procede de esa implementación. Reordenar entidades sólo para que el clasificador elija otro punto no demuestra una reparación robusta y no se ha adoptado.

## Puertas antes de activar la ruta en el programa

Conservar la fuente original y sus huellas. Exigir importación estricta, BRep exacto, BOP sin incidencias, geometría con límites originales, cilindros respaldados, topología/material y los tres mallados brutos cerrados y sin cruces. Integrar después como recuperación vigilada tras un rechazo concreto, con presupuesto de tiempo y memoria; las conversiones que ya pasan deben conservar su resultado.

La integración completa aún necesita pruebas en navegador y de los STEP exportados. Windows nativo, Onshape y WebAssembly siguen sin validarse en esta fase. Embudo permanece aplazado por indicación del usuario.
