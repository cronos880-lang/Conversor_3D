# Identidad y ajustes del Visor

La versión del paquete y su etiqueta se definen en `_version.py`; pyproject
obtiene la versión de ese mismo módulo. Los lanzadores llaman al paquete y no
copian un número de versión. La UI conserva sus botones y sólo muestra la
identidad del desarrollo. R19 publicada conserva sus propios metadatos.

`python -m conversor3d --version` muestra la identidad.
`python -m conversor3d config` muestra valores y unidades sin iniciar conversiones.

| Variable | Significado | Valor inicial |
| --- | --- | --- |
| CONVERSOR3D_PORT | Puerto TCP del servidor local | Definido en _version.py; --port tiene prioridad |
| VISOR_PERFIL | precision o impresion | precision; también se conserva la selección de la UI |
| CONVERSOR3D_DATA_DIR | Directorio de registros/resultados propios | visor/data en el proyecto; datos en portable |
| CONVERSOR3D_CACHE_DIR | Directorio del análisis auxiliar del STL | cache dentro de datos |
| CONVERSOR3D_CACHE_ENABLED | 1/0 o true/false | 1; desactivarlo no elimina controles finales |
| CONVERSOR3D_RETENTION_DAYS | Días de conservación, 0 conserva | 0; política de limpieza del punto 9 |
| CONVERSOR3D_PROFILE_DIR | Directorio del perfilador optativo | Desactivado |
| CONVERSOR3D_PROJECT_ROOT | Raíz explícita para runtime portable | Proyecto actual |
| CONVERSOR3D_FROZEN_ROOT | Fuentes del motor histórico | R19 del proyecto; siempre exige la misma firma |

Las tolerancias B-Rep, proyección de bordes y límites del evaluador no son
ajustes editables. Los interruptores expertos VISOR_* del motor congelado se
preservan como compatibilidad; no se renombran ni se modifica su lógica.

Los rechazos del proponente guardan cara y causa. Los fallos nativos y de
validación final incluyen tipo de error y detalle del control frío cuando existe.
Una causa de rechazo nunca se convierte en bandera de aprobación.
