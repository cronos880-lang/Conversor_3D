"""R19 como referencia, propuesta aislada y certificado final obligatorio."""
from pathlib import Path
import copy
import hashlib
import json
import os
import shutil
import sys
import time

from .legacy import FROZEN, native_env, run_worker, sha
from .processes import execute
from .validation import evaluate


def code_fingerprint():
    """Identificar fuentes y recursos del desarrollo; no sustituye el certificado."""
    root = Path(__file__).parent
    digest = hashlib.sha256()
    files = [path for path in root.rglob('*') if path.is_file() and path.suffix in {'.py', '.json', '.txt', '.html', '.js'}]
    for path in sorted(files, key=lambda p: p.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(bytes.fromhex(sha(path)))
    return digest.hexdigest()


def _last_result(path):
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines()[::-1]:
        try:
            value = json.loads(line)
            if isinstance(value, dict) and 'ok' in value:
                return value
        except ValueError:
            continue
    raise ValueError('El motor no emitió un resultado completo')


def optimize_reference(
    source: Path, baseline: Path, baseline_run: Path, evidence: Path
) -> dict:
    """Proponer en otro proceso y aceptar exclusivamente mediante el evaluador.

    Un rechazo de construcción o presupuesto conserva los bytes de referencia.
    El coordinador todavía debe certificar completamente el archivo final.
    """
    source, baseline, baseline_run, evidence = map(
        Path, (source, baseline, baseline_run, evidence)
    )
    evidence.mkdir(exist_ok=False)
    candidate = evidence / 'candidate.step'
    job = evidence / 'proposal-job.json'
    job.write_text(json.dumps({'baseline': str(baseline), 'candidate': str(candidate)}), encoding='utf-8')
    status = execute([sys.executable, '-m', 'conversor3d.reconstruction_worker', str(job)],
                     evidence, 'proposal', env=native_env(), timeout=120)
    proposal = json.loads((evidence / 'proposal.json').read_text(encoding='utf-8'))
    if status['returncode'] or proposal.get('ok') is not True:
        return {'accepted': False, 'selected': str(baseline),
                'selected_sha256': sha(baseline),
                'reason': proposal.get('error', 'Proponente interrumpido'),
                'proposal_error_code': proposal.get('error_code', 'proposal_rejected')}
    return evaluate(source, baseline, baseline_run, candidate, evidence / 'validation')


def certify_selection(selection, source, selected, baseline_run, evidence):
    """Reutiliza sólo el control completo ya realizado en ESTA selección."""
    approval = selection.get('validation', {})
    record = approval.get('final_validation', {})
    identity = record.get('certificado', {})
    if (selection.get('accepted') is True and approval.get('validated') is True
            and identity.get('source_sha256') == sha(source)
            and identity.get('step_sha256') == sha(selected)
            and identity.get('perfil', {}).get('id') == os.environ.get('VISOR_PERFIL', 'precision')
            and approval.get('nonce') == identity.get('nonce')):
        # La copia final volverá a pasar verificar() con sus bytes, perfil,
        # dependencias y núcleo actuales. Nunca se acepta un certificado antiguo
        # por nombre de archivo o por una bandera del proponente.
        return {'record': record, 'quality': approval['calidad'], 'nonce': approval['nonce']}, True
    certified = run_worker({'action': 'certify_final', 'source': str(source),
                            'candidate': str(selected), 'baseline_run': str(baseline_run),
                            'evidence': str(evidence)}, evidence)
    return certified['value'], False


def convert(source: Path, destination: Path):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    evidence = destination.with_name(destination.name + '.development')
    cold_sidecar = destination.with_suffix('.r19_nucleo.json')
    pipeline_sidecar = destination.with_suffix('.r19_pipeline.json')
    if (not source.is_file() or source == destination or destination.exists() or evidence.exists()
            or cold_sidecar.exists() or pipeline_sidecar.exists()):
        raise ValueError('Entrada existente y salida nueva e independiente obligatorias')
    if not destination.parent.is_dir():
        raise ValueError('El directorio de salida debe existir')
    from .dependencies import runtime_identity
    runtime = runtime_identity()
    evidence.mkdir()
    started = time.monotonic()
    fingerprint, source_hash = code_fingerprint(), sha(source)
    timings = {'traceability_start_seconds': time.monotonic() - started}
    from .cache import input_summary
    from .settings import Settings
    configuration = Settings.read()
    if configuration.cache_enabled:
        summary = input_summary(source, configuration.cache_dir, configuration.profile)
    else:
        summary = {'enabled': False, 'seconds': 0., 'authorizes_geometry': False}
    timings['input_analysis_seconds'] = summary['seconds']
    report = {'state': 'baseline', 'source_sha256': source_hash, 'development_sha256': fingerprint, 'input_analysis': summary, 'timings': timings,
              'configuration': configuration.describe(), 'runtime': runtime}
    baseline = evidence / 'baseline.step'
    status = execute([sys.executable, str(FROZEN / 'motor_r19.py'), str(source), str(baseline)],
                     evidence, 'baseline', cwd=FROZEN, env=native_env(), timeout=3600)
    timings['baseline_total_seconds'] = status['seconds']
    result = _last_result(evidence / 'baseline.stdout.txt')
    if status['returncode'] or result.get('ok') is not True:
        raise ValueError(result.get('error', 'Referencia R19 interrumpida'))
    baseline_run = evidence / 'baseline-run.json'
    baseline_run.write_text(json.dumps({'returncode': 0, 'payload': result,
                                       'source_sha256': source_hash, 'step_sha256': sha(baseline)}), encoding='utf-8')
    optimization_start = time.monotonic()
    try:
        selection = optimize_reference(source, baseline, baseline_run, evidence / 'optimization')
    except Exception as error:
        selection = {'accepted': False, 'selected': str(baseline),
                     'selected_sha256': sha(baseline), 'reason': str(error)}
    timings['proposal_and_gate_seconds'] = time.monotonic() - optimization_start
    selected = Path(selection['selected']) if selection.get('selected') else None
    if selected is None or sha(selected) != selection['selected_sha256']:
        raise ValueError('No hay selección íntegra')
    report.update(state='final_validation', selection=selection)
    (evidence / 'pipeline.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    final_start = time.monotonic()
    certificate_value, reused = certify_selection(selection, source, selected, baseline_run, evidence / 'final')
    timings['final_certificate_seconds'] = time.monotonic() - final_start
    report['reused_full_validation_for_identical_bytes'] = reused
    certificate = evidence / 'certificate.json'
    certificate.write_text(json.dumps(certificate_value, indent=2), encoding='utf-8')
    if sha(source) != source_hash or code_fingerprint() != fingerprint:
        raise ValueError('La entrada o el programa cambió durante la conversión')
    copy_start = time.monotonic()
    with selected.open('rb') as src, destination.open('xb') as dst:
        shutil.copyfileobj(src, dst)
    try:
        verified = run_worker({'action': 'verify_final', 'source': str(source),
                               'candidate': str(destination), 'certificate': str(certificate)}, evidence / 'verify')
        if (sha(destination) != selection['selected_sha256'] or sha(source) != source_hash
                or code_fingerprint() != fingerprint or runtime_identity() != runtime):
            raise ValueError('El archivo final no corresponde a la selección')
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    timings['copy_and_verify_seconds'] = time.monotonic() - copy_start
    timings['total_seconds'] = time.monotonic() - started
    final = copy.deepcopy(result)
    final['resultado']['calidad'] = verified['value']['quality']
    if selection['accepted']:
        improvement = copy.deepcopy(final['resultado'].get('mejora_superficies', {}))
        improvement.update(aplicado=True, caras_despues=verified['value']['quality']['caras_step'],
                           step_sha256=sha(destination), etapa_extra='contornos_compartidos')
        final['resultado']['mejora_superficies'] = improvement
        final['mejora_superficies'] = improvement
    final['development'] = {'selected_candidate': selection['accepted'],
                            'reason': selection['reason'], 'development_sha256': fingerprint,
                            'step_sha256': sha(destination), 'certificate': str(certificate)}
    report.update(state='finished', step_sha256=sha(destination))
    (evidence / 'pipeline.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    cold_record = copy.deepcopy(certificate_value['record'])
    cold_record.update(development_sha256=fingerprint, step_sha256=sha(destination),
                       original_sha256=source_hash, runtime=runtime)
    # Nombres compatibles con el servidor: conserva los certificados tras borrar temporales.
    for path, payload in [(cold_sidecar, cold_record), (pipeline_sidecar, report)]:
        with path.open('x', encoding='utf-8') as stream:
            json.dump(payload, stream, indent=2)
    return final
