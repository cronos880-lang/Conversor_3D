"""Frontera explícita con la dependencia congelada; no mezcla sus módulos."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
FROZEN = REPO / 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes'
FINGERPRINT = '96429bbba84ee5abb202198d0a769f0f32c5a91a31989e7859d8ae0cf7276006'


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_env() -> dict:
    return {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1',
            'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'VISOR_PERFIL': 'precision',
            'PYTHONPATH': str(Path(__file__).resolve().parents[1])}


def run_worker(job: dict, evidence: Path, timeout=540) -> dict:
    evidence = Path(evidence)
    evidence.mkdir(exist_ok=False)
    specification = evidence / 'job.json'
    specification.write_text(json.dumps(job), encoding='utf-8')
    with (evidence / 'stdout.txt').open('xb') as out, (evidence / 'stderr.txt').open('xb') as err:
        subprocess.run([sys.executable, '-m', 'conversor3d.legacy_worker', str(specification)],
                       cwd=REPO, env=native_env(), stdout=out, stderr=err,
                       timeout=timeout, check=False)
    result = json.loads((evidence / 'result.json').read_text(encoding='utf-8'))
    if result.get('ok') is not True:
        raise ValueError(result.get('error', 'Trabajador sin aprobación'))
    return result
