"""Única puerta de selección: el evaluador previo, conservado byte a byte."""
from pathlib import Path
import json
import sys
from .legacy import FROZEN, native_env, sha
from .processes import execute

EVALUATOR = Path(__file__).parent / 'resources/evaluator'


def evaluate(source, baseline, baseline_run, candidate, evidence):
    evidence = Path(evidence)
    evidence.mkdir(exist_ok=False)
    manifest = json.loads((EVALUATOR / 'SHA256.json').read_text(encoding='utf-8'))
    for name, expected in manifest.items():
        if sha(EVALUATOR / name) != expected:
            raise ValueError('El evaluador congelado cambió: ' + name)
    audit = execute([
        sys.executable, str(EVALUATOR / 'evaluar_candidato_externo.py'),
        '--source', str(source), '--baseline', str(baseline), '--baseline-run', str(baseline_run),
        '--candidate', str(candidate), '--evidence', str(evidence / 'gate'), '--motor', str(FROZEN),
    ], evidence, 'evaluator', cwd=FROZEN, env=native_env(), timeout=720)
    report = json.loads((evidence / 'gate/selection.json').read_text(encoding='utf-8'))
    if audit['returncode'] not in (0, 2) or (audit['returncode'] == 0) != (report.get('accepted') is True):
        raise ValueError('El proceso del evaluador y su resultado no coinciden')
    if report['source_sha256'] != sha(source) or report['baseline_sha256'] != sha(baseline):
        raise ValueError('La decisión no corresponde a estas entradas')
    if report['candidate_sha256'] != sha(candidate):
        raise ValueError('El candidato cambió durante la evaluación')
    return report
