"""Caché local de geometría R19, nunca de certificados ni de aprobaciones.

Cada lectura requiere un control frío completo nuevo antes de usar la referencia.
Los hashes detectan daños; por sí solos no autorizan la geometría.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import tempfile

from .legacy import FINGERPRINT, sha

MAX_REFERENCE_BYTES = 64 * 1024 * 1024
MAX_CACHE_BYTES = 256 * 1024 * 1024


def identity(source, profile, runtime):
    return {'schema': 1, 'source_sha256': sha(source), 'profile': profile,
            'frozen_fingerprint': FINGERPRINT, 'runtime': runtime,
            'cache_code_sha256': sha(Path(__file__))}


def location(cache_dir, expected):
    key = hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
    return Path(cache_dir) / 'references' / key


def load(cache_dir, expected, baseline, baseline_run):
    """Copia bytes íntegros a salidas nuevas; aún NO son una referencia aprobada."""
    entry = location(cache_dir, expected)
    try:
        paths = [entry / name for name in ('manifest.json', 'reference.step', 'result.json')]
        if entry.is_symlink() or any(p.is_symlink() for p in paths):
            raise ValueError('La caché de referencia contiene enlaces simbólicos')
        manifest = json.loads(paths[0].read_text(encoding='utf-8'))
        if manifest['identity'] != expected:
            raise ValueError('Identidad de caché distinta')
        payload = paths[2].read_bytes()
        if sha(paths[1]) != manifest['step_sha256'] or hashlib.sha256(payload).hexdigest() != manifest['result_sha256']:
            raise ValueError('Caché de referencia dañada')
        result = json.loads(payload)
        if result.get('ok') is not True:
            raise ValueError('Resultado de referencia incompleto')
    except (OSError, ValueError, KeyError, TypeError):
        return None
    # Lectura y copia separadas: contrastar de nuevo tras copiar frente a escrituras concurrentes.
    with paths[1].open('rb') as src, Path(baseline).open('xb') as dst:
        shutil.copyfileobj(src, dst)
    if sha(baseline) != manifest['step_sha256']:
        Path(baseline).unlink()
        return None
    record = {'returncode': 0, 'payload': result, 'source_sha256': expected['source_sha256'],
              'step_sha256': manifest['step_sha256']}
    with Path(baseline_run).open('x', encoding='utf-8') as stream:
        json.dump(record, stream)
    return result


def store(cache_dir, expected, baseline, result):
    """Guardar sólo una referencia cuya ejecución ya terminó con certificado nuevo."""
    entry = location(cache_dir, expected)
    entry.parent.mkdir(parents=True, exist_ok=True)
    if entry.exists():
        return {'stored': False, 'reason': 'already_present'}
    size = Path(baseline).stat().st_size
    used = sum(p.stat().st_size for p in entry.parent.rglob('*') if p.is_file() and not p.is_symlink())
    if size > MAX_REFERENCE_BYTES or used + size > MAX_CACHE_BYTES:
        return {'stored': False, 'reason': 'local_cache_budget'}
    with tempfile.TemporaryDirectory(prefix='reference-', dir=entry.parent) as directory:
        stage = Path(directory) / 'entry'
        stage.mkdir()
        with Path(baseline).open('rb') as src, (stage / 'reference.step').open('xb') as dst:
            shutil.copyfileobj(src, dst)
        (stage / 'result.json').write_text(json.dumps(without_certificates(result)), encoding='utf-8')
        record = {'identity': expected, 'step_sha256': sha(stage / 'reference.step'),
                  'result_sha256': sha(stage / 'result.json'),
                  'contains_certificate': False, 'requires_fresh_cold_validation': True}
        (stage / 'manifest.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        try:
            os.rename(stage, entry)
        except OSError:
            if not entry.exists():
                raise
    return {'stored': True}


def without_certificates(value):
    """Retirar también certificados de diagnósticos históricos anidados."""
    if isinstance(value, dict):
        forbidden = {'certificado', 'certificate', 'final_validation', 'nonce', 'certificados'}
        return {key: without_certificates(item) for key, item in value.items() if key not in forbidden}
    if isinstance(value, list):
        return [without_certificates(item) for item in value]
    return value
