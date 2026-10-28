"""Publica hitos comprobables de las etapas de conversión.

Los porcentajes indican fases completadas (estimación, NO tiempo restante),
por eso no se incrementan automáticamente durante una operación larga.
Se escribe en un fichero independiente: no cambia el código CAD del amigo.
"""
import json
import os
import time


def avance(porcentaje, fase):
    destino = os.environ.get('VISOR_AVANCE_PATH')
    if not destino:
        return
    evento = {'porcentaje': max(0, min(99, int(porcentaje))),
              'fase': str(fase)[:180], 'instante': time.time()}
    try:
        with open(destino, 'a', encoding='utf-8') as fichero:
            fichero.write(json.dumps(evento, ensure_ascii=False) + '\n')
            fichero.flush()
    except OSError:
        # El indicador es accesorio; nunca debe provocar un fallo CAD.
        pass
