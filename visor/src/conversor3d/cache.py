"""Reutilización no autoritativa del análisis de un STL idéntico; nunca certificados."""
from pathlib import Path
import hashlib
import importlib.metadata
import io
import json
import os
import tempfile
import time

import numpy as np
from .legacy import FINGERPRINT, FROZEN, run_worker, sha


def input_summary(source: Path, cache_dir: Path, profile: str) -> dict:
    source, cache_dir = Path(source), Path(cache_dir)
    start = time.monotonic()
    identity = {'schema': 1, 'source_sha256': sha(source), 'profile': profile,
                'frozen_fingerprint': FINGERPRINT,
                'parser_sha256': sha(FROZEN / 'preprocesador_stl.py'),
                'cache_code_sha256': sha(Path(__file__)),
                'dependencies': {name: importlib.metadata.version(name) for name in ('numpy', 'trimesh')}}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest, arrays = cache_dir / (key + '.json'), cache_dir / (key + '.npz')
    try:
        record = json.loads(manifest.read_text(encoding='utf-8'))
        payload = arrays.read_bytes()
        if record['identity'] != identity or hashlib.sha256(payload).hexdigest() != record['arrays_sha256']:
            raise ValueError('Entrada de caché no íntegra')
        with np.load(io.BytesIO(payload), allow_pickle=False) as cached:
            vertices, faces = cached['vertices'], cached['faces']
            if vertices.ndim != 2 or vertices.shape[1] != 3 or faces.ndim != 2 or faces.shape[1] != 3:
                raise ValueError('Arrays de caché inválidos')
            if not np.isfinite(vertices).all() or not np.issubdtype(faces.dtype, np.integer):
                raise ValueError('Datos de caché inválidos')
        if sha(source) != identity['source_sha256']:
            raise ValueError('El STL cambió durante la lectura')
        return {'identity': identity, 'summary': record['summary'], 'cache_hit': True,
                'seconds': time.monotonic() - start, 'authorizes_geometry': False}
    except (OSError, ValueError, KeyError, TypeError):
        pass  # Entrada inexistente/corrupta: siempre recalcular a partir del STL.
    with tempfile.TemporaryDirectory(prefix='input-', dir=cache_dir) as temporary:
        scratch = Path(temporary)
        result = run_worker({'action': 'describe_input', 'source': str(source.resolve()),
                             'arrays': str(scratch / 'input.npz')}, scratch / 'worker')['value']
        if sha(source) != identity['source_sha256']:
            raise ValueError('El STL cambió durante el análisis')
        payload = (scratch / 'input.npz').read_bytes()
        record = {'identity': identity, 'summary': result,
                  'arrays_sha256': hashlib.sha256(payload).hexdigest()}
        staged_arrays, staged_manifest = scratch / 'arrays.tmp', scratch / 'manifest.tmp'
        staged_arrays.write_bytes(payload)
        staged_manifest.write_text(json.dumps(record, indent=2), encoding='utf-8')
        os.replace(staged_arrays, arrays)
        os.replace(staged_manifest, manifest)
    return {'identity': identity, 'summary': result, 'cache_hit': False,
            'seconds': time.monotonic() - start, 'authorizes_geometry': False}
