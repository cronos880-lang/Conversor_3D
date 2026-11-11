"""Ensayo de proponentes externos con validación R19 intacta y retorno a la base.

No cambia ni copia STEP: informa qué archivo existente puede seleccionarse.
El ok/RESULT de un conversor externo no interviene en la aprobación.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import signal
import subprocess
import sys
import time

DEFAULT_MOTOR = Path('/workspace/Conversor_3D_R18_experimental/entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes')
EXPECTED_MOTOR = '96429bbba84ee5abb202198d0a769f0f32c5a91a31989e7859d8ae0cf7276006'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_process(command, folder, name, timeout, env):
    with (folder / (name + '.stdout.txt')).open('xb') as out, (folder / (name + '.stderr.txt')).open('xb') as err:
        process = subprocess.Popen(command, stdout=out, stderr=err, env=env, start_new_session=True)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if process.poll() is None:
                    process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise TimeoutError(name + ' agotó su tiempo de evaluación')


def evaluate(source, baseline, baseline_run, candidate, evidence, motor=DEFAULT_MOTOR):
    source, baseline, baseline_run, candidate, evidence, motor = map(lambda p: Path(p).resolve(), (source, baseline, baseline_run, candidate, evidence, motor))
    if not all(p.is_file() for p in (source, baseline, baseline_run, candidate)):
        raise ValueError('Son obligatorias todas las entradas existentes')
    evidence.mkdir(exist_ok=False)
    inputs = (source, baseline, baseline_run, candidate)
    hashes = tuple(map(sha, inputs))
    report = dict(accepted=False, selected=None, source_sha256=hashes[0], baseline_sha256=hashes[1], baseline_run_sha256=hashes[2], candidate_sha256=hashes[3], motor_sha256=EXPECTED_MOTOR, stage='reference', reason=None, selected_sha256=None)
    start = time.monotonic()
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'VISOR_PERFIL': 'precision'}
    try:
        old = json.loads(baseline_run.read_text(encoding='utf-8'))
        if old['source_sha256'] != hashes[0] or old['step_sha256'] != hashes[1]:
            raise ValueError('Los hashes de la referencia no coinciden')
        report.update(selected=str(baseline), selected_sha256=hashes[1])
        before = old['payload']['resultado']['calidad']
        reference_faces = before['caras_step']
        limit = before['integridad_cad']['tolerancia_max_mm']
        if not isinstance(reference_faces, int) or reference_faces < 1 or not math.isfinite(limit) or limit < 0:
            raise ValueError('Métricas de referencia inválidas')
        report['stage'] = 'independent_step_import'
        inspection = evidence / 'inspection.json'
        code = run_process([sys.executable, str(Path(__file__).with_name('inspeccionar_step.py')), str(candidate), str(inspection)], evidence, 'inspection', 90, env)
        if code or not inspection.is_file():
            raise ValueError('El lector independiente no obtiene un objeto CAD')
        inspected = json.loads(inspection.read_text())
        report['inspection'] = inspected
        reasons = []
        if inspected.get('exact_valid') is not True:
            reasons.append('B-Rep exacto inválido')
        if inspected.get('solids') != 1 or inspected.get('shells') != 1:
            reasons.append('No contiene un único sólido y shell')
        if inspected.get('faces', 0) < 1 or inspected['faces'] >= reference_faces - max(4, int(reference_faces * .05)):
            reasons.append('No reduce las caras según el contrato R19')
        tolerance = inspected.get('max_edge_tolerance_mm', float('nan'))
        if not math.isfinite(tolerance) or tolerance > limit + 1e-9:
            reasons.append('Aumenta la tolerancia máxima de las aristas')
        if reasons:
            raise ValueError('; '.join(reasons))
        report['stage'] = 'full_r19_validation'
        validation = evidence / 'validation.json'
        code = run_process([sys.executable, str(Path(__file__).resolve()), '--worker', str(source), str(baseline), str(baseline_run), str(candidate), str(evidence), str(motor)], evidence, 'validation', 540, env)
        if not validation.is_file():
            raise ValueError('Validación R19 interrumpida sin certificado')
        validated = json.loads(validation.read_text())
        report['validation'] = validated
        if code or validated.get('accepted') is not True:
            raise ValueError(validated.get('error', 'Rechazado por R19'))
        if validated['source_sha256'] != hashes[0] or validated['baseline_sha256'] != hashes[1] or validated['candidate_sha256'] != hashes[3]:
            raise ValueError('El certificado no pertenece a estas entradas')
        if tuple(map(sha, inputs)) != hashes:
            raise ValueError('Una entrada cambió durante la evaluación')
        report.update(accepted=True, selected=str(candidate), selected_sha256=hashes[3], stage='accepted', reason=validated['selection_reason'])
    except Exception as exc:
        report['reason'] = str(exc)
    if tuple(map(sha, inputs)) != hashes:
        # Si la base cambia, tampoco es correcto presentarla como seleccionable.
        report.update(accepted=False, selected=None, selected_sha256=None, stage='integrity_failure', reason='Una entrada cambió durante la evaluación')
    report['seconds'] = time.monotonic() - start
    (evidence / 'selection.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def worker(source, baseline, baseline_run, candidate, evidence, motor):
    sys.path.insert(0, str(motor))
    from contratos_r19 import ROOT
    from certificado_calidad_r15 import firma_motor, verificar
    from validacion_r19 import validar
    result = dict(accepted=False)
    try:
        if ROOT.resolve() != Path(motor).resolve() or firma_motor(ROOT) != EXPECTED_MOTOR:
            raise ValueError('El núcleo R19 no coincide con la referencia fijada')
        result = validar(source, candidate, baseline, baseline_run, evidence)
        verificar(result['final_validation'], source, candidate, result['nonce'], ROOT)
        if firma_motor(ROOT) != EXPECTED_MOTOR:
            raise ValueError('El núcleo cambió durante la prueba')
    except Exception as exc:
        result = dict(accepted=False, error=str(exc))
    (Path(evidence) / 'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result.get('accepted') else 2


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        raise SystemExit(worker(*sys.argv[2:]))
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('source', 'baseline', 'baseline-run', 'candidate', 'evidence'):
        p.add_argument('--' + flag, required=True)
    p.add_argument('--motor', default=str(DEFAULT_MOTOR))
    report = evaluate(**vars(p.parse_args()))
    print(json.dumps({k: report[k] for k in ('accepted', 'selected', 'selected_sha256', 'stage', 'reason', 'seconds')}, ensure_ascii=False))
    raise SystemExit(0 if report['accepted'] else 2)
