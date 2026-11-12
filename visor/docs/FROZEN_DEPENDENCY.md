# Copias deliberadas de R19

La fuente de desarrollo es el paquete único `visor/src/conversor3d`. No se
reescriben ni se normalizan entregas históricas. El manifiesto
`visor/frozen-r19.sha256.json` reproduce los 357 hashes de R19 y permite detectar
una modificación sin ejecutar sus módulos.

- La raíz R19 coordina la conversión y conserva los controles de su entrega.
- `motor_superficies` y `motor_original_amigo` pertenecen a la reconstrucción
  histórica y la referencia de procedencia. Sus variantes no se intercambian.
- `motor_calidad` y sus subdirectorios forman el núcleo de control independiente.
  Su aislamiento deliberado impide que el proponente reemplace los controles.
- El evaluador de `conversor3d/resources/evaluator` es otra dependencia congelada
  explícita, con hash propio. Conserva exactamente la puerta autorizada.

Hay nombres iguales con implementaciones divergentes: no son duplicados que se
puedan borrar por su nombre. Las copias idénticas dentro de los núcleos congelados
se conservan por sus contratos de importación y trazabilidad. Convertirlos en
una dependencia separada futura requiere una migración específica con pruebas;
no se hace una fusión masiva durante esta hoja de ruta.

El desarrollo utiliza un único adaptador de imports en un proceso legacy. Los
algoritmos nuevos, sus contratos y los generadores de pruebas tienen una sola
implementación. La factoría sintética compartida pasó de las pruebas al catálogo
único manteniendo los controles de geometría y aprobación fría.

Auditoría reproducible:

```
python visor/scripts/audit_frozen.py
```

El resultado distingue hashes idénticos de variantes y falla si falta o cambia
cualquier fuente del manifiesto. R18, R19 y R20 se conservan; la limpieza
autorizada de versiones anteriores se documenta en `MANTENIMIENTO_VERSIONES.md`
en la raíz. Los seis fixtures históricos utilizados por las pruebas permanecen
con hashes en `visor/test-data`. No se reescribe el historial Git.
