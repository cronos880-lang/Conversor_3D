"""Entrega R21 completa en fuentes, instalador propio y 357 fuentes protegidas."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import subprocess
import zipfile

REPO = Path(__file__).resolve().parents[2]
PREFIX = 'Conversor_3D_R21_COMPLETA'


def identity():
    spec = importlib.util.spec_from_file_location('r21_identity', REPO / 'visor/src/conversor3d/_version.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.RELEASE_NAME != 'R21':
        raise ValueError('Las fuentes no corresponden a R21')
    return {'release': 'R21', 'version': module.__version__, 'kind': 'COMPLETA',
            'format': 'fuentes con instalador', 'requires_r20': False,
            'own_environment': '.venv_r21', 'bundled_third_party_binaries': False}


def launcher(action):
    content = '''@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONNOUSERSITE=1"
set "PYTHONHOME="
set "PYTHONPATH="
set "VIRTUAL_ENV="
echo R21 COMPLETA - entorno propio, independiente de R20.
"%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0r21_full_bootstrap.ps1" ACTION %*
if errorlevel 1 goto error
if not "%CONVERSOR3D_SIN_PAUSA%"=="1" if not "ACTION"=="start" pause
exit /b 0
:error
echo Consulta datos\\arranque_R21.log y datos\\instalacion_R21.log.
if not "%CONVERSOR3D_SIN_PAUSA%"=="1" pause
exit /b 2
'''.replace('ACTION', action)
    return content.replace('\n', '\r\n').encode('ascii')


def build(output):
    output = Path(output)
    files = {}
    for folder in ('src', 'scripts', 'docs', 'licenses'):
        for path in (REPO / 'visor' / folder).rglob('*'):
            if (path.is_file() and '__pycache__' not in path.parts
                    and not any(part.endswith('.egg-info') for part in path.parts)
                    and path.suffix not in ('.pyc', '.pyo')):
                files[path.relative_to(REPO).as_posix()] = path.read_bytes()
    for pattern in ('requirements*', '*.md', 'pyproject.toml', 'frozen-r19.sha256.json'):
        for path in (REPO / 'visor').glob(pattern):
            if path.is_file():
                files[path.relative_to(REPO).as_posix()] = path.read_bytes()
    frozen = Path('entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes')
    hashes = json.loads((REPO / 'visor/frozen-r19.sha256.json').read_text())
    for name, expected in hashes.items():
        path = frozen / name
        data = (REPO / path).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Ha cambiado una fuente protegida: ' + name)
        files[path.as_posix()] = data
    files['AGENTS.md'] = (REPO / 'AGENTS.md').read_bytes()
    files['LEEME_PRIMERO.txt'] = (REPO / 'visor/docs/R21_COMPLETA_USUARIO.txt').read_bytes()
    files['r21_full_bootstrap.ps1'] = (REPO / 'visor/scripts/r21_full_bootstrap.ps1').read_bytes()
    for name, action in [('Iniciar_R21.bat', 'start'), ('Instalar_Entorno_R21.bat', 'install'),
                         ('Reparar_Entorno_R21.bat', 'install'), ('Diagnostico_R21.bat', 'diagnose')]:
        files[name] = launcher(action)
    release = identity()
    files['R21_VERSION.json'] = json.dumps(release, indent=2).encode()
    for name in files:
        suffix = Path(name).suffix.lower()
        if suffix in {'.zip', '.exe', '.dll', '.so', '.pyd'}:
            raise ValueError('Archivo ajeno al paquete en fuentes: ' + name)
        if suffix in {'.stl', '.step', '.stp'} and (
                not name.startswith(frozen.as_posix() + '/') or name[len(frozen.as_posix()) + 1:] not in hashes):
            raise ValueError('Modelo ajeno al manifiesto histórico: ' + name)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    manifest = {'schema': 1, 'identity': release, 'source_commit': commit,
                'source_tree_clean': not subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO, text=True).strip(),
                'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files['R21_MANIFEST.json'] = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
    with zipfile.ZipFile(output, 'x') as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(PREFIX + '/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 0
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=9)
    result = {'zip': str(output), 'bytes': output.stat().st_size,
              'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'files': len(files),
              'identity': release, 'source_commit': commit}
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    build(parser.parse_args().output)
