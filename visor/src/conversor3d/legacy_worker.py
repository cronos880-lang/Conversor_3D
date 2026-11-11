"""Un solo adaptador de imports para el motor histórico, en un proceso aislado."""
from pathlib import Path
import json
import secrets
import sys
import traceback
from .legacy import FROZEN, FINGERPRINT, sha


def execute(job):
    # Única modificación deliberada de sys.path: dependencia histórica aislada.
    sys.path.insert(0, str(FROZEN))
    from contratos_r19 import ROOT
    from certificado_calidad_r15 import firma_motor, verificar
    if ROOT.resolve() != FROZEN.resolve() or firma_motor(ROOT) != FINGERPRINT:
        raise ValueError('La dependencia R19 no coincide con su firma congelada: '
                         + firma_motor(ROOT) + '; esperada ' + FINGERPRINT)
    job = {key: Path(value) if key in {'source', 'baseline', 'candidate', 'baseline_run', 'evidence'} else value
           for key, value in job.items()}
    action = job['action']
    if action == 'assess_baseline':
        from motor_v2 import _calidad
        from preprocesador_stl import cargar_exacto
        quality = _calidad(job['source'], job['baseline'], cargar_exacto(job['source']), control_avanzado=True)
        value = {'returncode': 0, 'source_sha256': sha(job['source']),
                 'step_sha256': sha(job['baseline']),
                 'payload': {'ok': True, 'resultado': {'calidad': quality}}}
    elif action == 'validate_candidate':
        from validacion_r19 import validar
        value = validar(job['source'], job['candidate'], job['baseline'], job['baseline_run'], job['evidence'])
        verificar(value['final_validation'], job['source'], job['candidate'], value['nonce'], ROOT)
    else:
        raise ValueError('Acción no reconocida: ' + action)
    if firma_motor(ROOT) != FINGERPRINT:
        raise ValueError('La dependencia cambió durante el trabajo')
    return {'ok': True, 'value': value, 'frozen_fingerprint': FINGERPRINT}


def main():
    path = Path(sys.argv[1])
    try:
        result = execute(json.loads(path.read_text(encoding='utf-8')))
    except Exception as error:
        traceback.print_exc()
        result = {'ok': False, 'error': str(error)}
    (path.parent / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
