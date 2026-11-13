"""Construir actualización R21 solicitada, sin motor histórico ni runtime duplicados."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import subprocess
import zipfile

REPO = Path(__file__).resolve().parents[2]
PREFIX = 'Conversor_3D_R21_actualizacion'


def release_identity():
    spec = importlib.util.spec_from_file_location('r21_identity', REPO / 'visor/src/conversor3d/_version.py')
    version = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(version)
    if version.RELEASE_NAME != 'R21':
        raise ValueError('R21 sólo se construye tras aprobar el avance y actualizar su identidad')
    return {'release': version.RELEASE_NAME, 'version': version.__version__,
            'label': version.APPLICATION_LABEL, 'port': version.DEFAULT_PORT,
            'base_release': 'R20', 'base_engine': version.BASE_ENGINE,
            'kind': 'ACTUALIZACION', 'bundled_runtime': False, 'bundled_historical_engine': False}


def build(output):
    identity = release_identity()
    files = {}
    for path in (REPO / 'visor/src/conversor3d').rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.pyo'):
            files[path.relative_to(REPO).as_posix()] = path.read_bytes()
    files['r21_launcher.py'] = (REPO / 'visor/scripts/r21_launcher.py').read_bytes()
    files['R19_FROZEN_SHA256.json'] = (REPO / 'visor/frozen-r19.sha256.json').read_bytes()
    files['LEEME_R21.txt'] = (REPO / 'visor/docs/R21_USUARIO.txt').read_bytes()
    files['INFORME_R21.md'] = (REPO / 'visor/docs/R21_INFORME.md').read_bytes()
    files['THIRD_PARTY_LICENSES.md'] = (REPO / 'visor/THIRD_PARTY_LICENSES.md').read_bytes()
    files['AGENTS.md'] = (REPO / 'AGENTS.md').read_bytes()
    files['visor/AGENTS.md'] = (REPO / 'visor/AGENTS.md').read_bytes()
    for name, options in [('Iniciar_R21.bat', ''), ('Diagnostico_R21.bat', '--diagnostico')]:
        text = '''@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
if exist "..\\Conversor_3D_R20_experimental\\.venv_r20\\Scripts\\python.exe" (
  "..\\Conversor_3D_R20_experimental\\.venv_r20\\Scripts\\python.exe" -B "r21_launcher.py" OPTIONS %*
) else (
  py -3.12 -B "r21_launcher.py" OPTIONS %*
)
if errorlevel 1 pause
'''.replace('OPTIONS', options)
        files[name] = text.replace('\n', '\r\n').encode('ascii')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    manifest = {'schema': 1, 'source_commit': commit, 'identity': identity,
                'source_tree_clean': not subprocess.check_output(
                    ['git', 'status', '--porcelain'], cwd=REPO, text=True).strip(),
                'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files['R21_MANIFEST.json'] = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
    with zipfile.ZipFile(output, 'x') as archive:
        for name, data in sorted(files.items()):
            item = zipfile.ZipInfo(PREFIX + '/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            item.create_system = 0
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, data, compresslevel=9)
    result = {'zip': str(output), 'bytes': Path(output).stat().st_size,
              'sha256': hashlib.sha256(Path(output).read_bytes()).hexdigest(),
              'files': len(files), 'identity': identity, 'source_commit': commit}
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    build(parser.parse_args().output)
