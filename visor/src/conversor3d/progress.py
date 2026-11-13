"""Hitos reales para el contrato de progreso existente; nunca un reloj estimador."""
from pathlib import Path
import json
import os
import time


def milestone(percent, phase):
    path = os.environ.get('VISOR_AVANCE_PATH')
    if not path:
        return
    event = {'porcentaje': max(0, min(99, int(percent))), 'fase': phase, 'instante': time.time()}
    try:
        with Path(path).open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
    except OSError:
        pass  # La telemetría no autoriza ni invalida una geometría.
