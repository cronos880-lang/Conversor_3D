"""Un solo adaptador de imports para el motor histórico, en un proceso aislado."""
from pathlib import Path
import json
import secrets
import sys
import traceback
import time
from .legacy import FROZEN, FINGERPRINT, sha


def execute(job):
    # Única modificación deliberada de sys.path: dependencia histórica aislada.
    sys.path.insert(0, str(FROZEN))
    from contratos_r19 import ROOT
    from certificado_calidad_r15 import firma_motor, verificar
    trace_start = time.monotonic()
    observed_fingerprint = firma_motor(ROOT)
    trace_seconds = time.monotonic() - trace_start
    if ROOT.resolve() != FROZEN.resolve() or observed_fingerprint != FINGERPRINT:
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
    elif action == 'describe_input':
        import numpy as np
        from preprocesador_stl import cargar_exacto, diagnosticar
        original_hash = sha(job['source'])
        mesh = cargar_exacto(job['source'])
        value = diagnosticar(mesh)
        np.savez_compressed(job['arrays'], vertices=mesh.vertices, faces=mesh.faces)
        if sha(job['source']) != original_hash:
            raise ValueError('Cambió el STL durante la lectura')
    elif action == 'certify_final':
        import subprocess
        from .legacy import native_env
        nonce = secrets.token_hex(24)
        report = job['evidence'] / 'cold.json'
        code = subprocess.run([
            sys.executable, str(FROZEN / 'validacion_fria_r19.py'), str(job['source']),
            str(job['candidate']), str(job['baseline_run']), nonce, str(report),
        ], cwd=FROZEN, env=native_env(), timeout=450).returncode
        if code or not report.is_file():
            from .errors import FinalValidationError
            detail = json.loads(report.read_text(encoding='utf-8')).get('error') if report.is_file() else None
            raise FinalValidationError('El entregable no supera el control frío completo: ' + str(detail or 'proceso interrumpido'))
        record = json.loads(report.read_text(encoding='utf-8'))
        quality = verificar(record, job['source'], job['candidate'], nonce, ROOT)
        value = {'record': record, 'quality': quality, 'nonce': nonce}
    elif action == 'serve':
        from .server import serve_in_legacy
        serve_in_legacy(int(job['port']), bool(job['open_browser']))
        value = {'stopped': True}
    elif action == 'verify_final':
        record = json.loads(Path(job['certificate']).read_text(encoding='utf-8'))
        quality = verificar(record['record'], job['source'], job['candidate'], record['nonce'], ROOT)
        value = {'verified': True, 'quality': quality}
    else:
        raise ValueError('Acción no reconocida: ' + action)
    trace_start = time.monotonic()
    if firma_motor(ROOT) != FINGERPRINT:
        raise ValueError('La dependencia cambió durante el trabajo')
    trace_seconds += time.monotonic() - trace_start
    return {'ok': True, 'value': value, 'frozen_fingerprint': FINGERPRINT,
            'traceability_seconds': trace_seconds}


def main():
    path = Path(sys.argv[1])
    try:
        result = execute(json.loads(path.read_text(encoding='utf-8')))
    except Exception as error:
        traceback.print_exc()
        result = {'ok': False, 'error': str(error),
                  'tipo_error': getattr(error, 'code', type(error).__name__)}
    (path.parent / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
