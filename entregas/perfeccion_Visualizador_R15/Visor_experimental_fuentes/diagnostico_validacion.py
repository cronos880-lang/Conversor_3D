"""Registrar valores y límites sin confundir una medición con la causa del error."""
import json
import os
import time


class ErrorGeometrico(ValueError):
    def __init__(self, contexto, criterios):
        self.criterios = criterios
        self.codigo = 'geometria_fuera_de_limites'
        failures = [c for c in criterios if not c['cumple']]
        message = '; '.join(f"{c['nombre']}: {c['medido']:.6f} {c['unidad']} > "
                            f"{c['limite']:.6f} {c['unidad']}" for c in failures)
        super().__init__(contexto + ': ' + message + '.')
        path = os.environ.get('VISOR_RECHAZOS_PATH')
        if path:
            row = {'instante': time.time(), 'codigo': self.codigo,
                   'perfil': os.environ.get('VISOR_PERFIL','precision'),
                   'mensaje': str(self), 'criterios': criterios}
            try:
                with open(path,'a',encoding='utf-8') as f:
                    f.write(json.dumps(row,ensure_ascii=False)+'\n')
            except OSError:pass


def criterio(nombre, medido, limite, unidad='mm'):
    return {'nombre': nombre, 'medido': float(medido), 'limite': float(limite),
            'unidad': unidad, 'cumple': bool(medido <= limite)}
