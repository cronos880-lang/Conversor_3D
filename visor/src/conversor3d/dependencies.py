"""Identidad de las dependencias directas y comprobación de versiones fijadas."""
from pathlib import Path
import hashlib
import importlib.metadata
import platform
import sys

SPECIFICATION = Path(__file__).parent / 'resources/runtime-requirements.txt'


def runtime_identity():
    versions = {}
    for line in SPECIFICATION.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, expected = line.split('==', 1)
        actual = importlib.metadata.version(name)
        if actual != expected:
            raise ValueError(f'Dependencia {name}: instalada {actual}, requerida {expected}. Usa el instalador de desarrollo.')
        versions[name] = actual
    return {'python': sys.version, 'platform': platform.platform(), 'libraries': versions,
            'specification_sha256': hashlib.sha256(SPECIFICATION.read_bytes()).hexdigest()}
