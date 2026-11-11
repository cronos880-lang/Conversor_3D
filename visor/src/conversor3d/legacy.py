"""Frontera explícita con la dependencia congelada; no mezcla sus módulos."""
from pathlib import Path
import hashlib
import json
import os
import sys

from .settings import Settings
from .errors import NativeWorkerError

_CONFIGURATION = Settings.read()
REPO, FROZEN = _CONFIGURATION.project_root, _CONFIGURATION.frozen_root
FINGERPRINT = '96429bbba84ee5abb202198d0a769f0f32c5a91a31989e7859d8ae0cf7276006'


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_env() -> dict:
    configuration = Settings.read()
    package_root = Path(__file__).resolve().parents[1]
    paths = [str(package_root)]
    if os.environ.get('CONVERSOR3D_PROFILE_DIR'):
        paths.insert(0, str(Path(__file__).parent / 'resources/profiling'))
    return {**os.environ, **configuration.environment(), 'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1',
            'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
            'VISOR_PERFIL': os.environ.get('VISOR_PERFIL', 'precision'),
            'PYTHONPATH': os.pathsep.join(paths)}


def run_worker(job: dict, evidence: Path, timeout=540) -> dict:
    evidence = Path(evidence)
    evidence.mkdir(exist_ok=False)
    specification = evidence / 'job.json'
    specification.write_text(json.dumps(job), encoding='utf-8')
    from .processes import execute
    status = execute([sys.executable, '-m', 'conversor3d.legacy_worker', str(specification)],
                     evidence, 'worker', cwd=REPO, env=native_env(), timeout=timeout)
    result = json.loads((evidence / 'result.json').read_text(encoding='utf-8'))
    if status['returncode'] != 0 or result.get('ok') is not True:
        raise NativeWorkerError(result.get('error', 'Trabajador sin aprobación'))
    return result
