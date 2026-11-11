"""Construir R20 en fuentes, con fixtures históricos y sin runtimes/modelos nuevos."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import subprocess
import zipfile

REPO = Path(__file__).resolve().parents[2]
PREFIX = 'Conversor_3D_R20_experimental'


def release_identity():
    spec = importlib.util.spec_from_file_location('release_identity',
        REPO / 'visor/src/conversor3d/_version.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {'release': module.RELEASE_NAME, 'version': module.__version__,
            'label': module.APPLICATION_LABEL, 'port': module.DEFAULT_PORT,
            'base_engine': module.BASE_ENGINE}


def launcher(action):
    pause_success = ('if not "%CONVERSOR3D_SIN_PAUSA%"=="1" pause\n'
                     if action != 'start' else '')
    text = f'''@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONNOUSERSITE=1"
set "PYTHONHOME="
set "PYTHONPATH="
if exist ".venv_r20\\Scripts\\python.exe" goto propio
py -3.12 -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 goto lanzador_py
python -c "import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,12) and struct.calcsize('P')==8 else 1)" >nul 2>&1
if not errorlevel 1 goto lanzador_python
echo R20 requiere Python 3.12 de 64 bits. Comprueba la instalacion usada por R19.
echo Puedes instalarlo desde https://www.python.org/downloads/windows/
goto error
:propio
".venv_r20\\Scripts\\python.exe" -B "visor\\scripts\\manage_environment.py" {action} %*
goto resultado
:lanzador_py
py -3.12 -B "visor\\scripts\\manage_environment.py" {action} %*
goto resultado
:lanzador_python
python -B "visor\\scripts\\manage_environment.py" {action} %*
:resultado
if errorlevel 1 goto error
{pause_success}exit /b 0
:error
echo ERROR R20. Consulta datos\\instalacion_R20.log o ejecuta Diagnostico_R20.bat.
if not "%CONVERSOR3D_SIN_PAUSA%"=="1" pause
exit /b 2
'''
    return text.replace('\n', '\r\n').encode('ascii')


def payload():
    files = {}
    files['.github/workflows/visor-ci.yml'] = (REPO / '.github/workflows/visor-ci.yml').read_bytes()
    visor = REPO / 'visor'
    for folder in ('src', 'scripts', 'tests', 'docs', 'licenses'):
        for path in (visor / folder).rglob('*'):
            if (not path.is_file() or '__pycache__' in path.parts
                    or path.suffix in ('.pyc', '.pyo') or any(part.endswith('.egg-info') for part in path.parts)):
                continue
            files[path.relative_to(REPO).as_posix()] = path.read_bytes()
    for pattern in ('*.md', 'requirements*', 'pyproject.toml', 'frozen-r19.sha256.json'):
        for path in visor.glob(pattern):
            if path.is_file():
                files[path.relative_to(REPO).as_posix()] = path.read_bytes()
    frozen = Path('entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes')
    expected = json.loads((visor / 'frozen-r19.sha256.json').read_text(encoding='utf-8'))
    for relative, digest in expected.items():
        data = (REPO / frozen / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('La fuente congelada cambió: ' + relative)
        files[(frozen / relative).as_posix()] = data
    for name, action in [('Iniciar_R20.bat', 'start'), ('Instalar_Entorno_R20.bat', 'install'),
                         ('Diagnostico_R20.bat', 'diagnose')]:
        files[name] = launcher(action)
    for source, target in [('R20_USUARIO.md', 'LEEME_PRIMERO.md'),
                           ('R20_INFORME.md', 'INFORME_R20.md'),
                           ('R20_REVISION_EXTERNA.md', 'GUIA_REVISION_EXTERNA.md')]:
        files[target] = (visor / 'docs' / source).read_bytes()
    files['R20_VERSION.json'] = json.dumps(release_identity(), ensure_ascii=False, indent=2).encode('utf-8')
    return files


def build(output: Path):
    output = Path(output)
    if output.exists():
        raise ValueError('El ZIP de salida debe ser nuevo')
    files = payload()
    prohibited = {'.zip', '.exe', '.dll', '.pyd', '.so'}
    frozen = 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes/'
    historical = json.loads((REPO / 'visor/frozen-r19.sha256.json').read_text(encoding='utf-8'))
    for name in files:
        suffix = Path(name).suffix.lower()
        if suffix in prohibited:
            raise ValueError('El paquete fuente contiene un binario o ZIP ajeno: ' + name)
        if suffix in {'.stl', '.step', '.stp'} and (
                not name.startswith(frozen) or name[len(frozen):] not in historical):
            raise ValueError('El paquete contiene un modelo que no es fixture histórico: ' + name)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    manifest = {'schema': 1, 'identity': release_identity(), 'source_commit': commit,
                'source_tree_clean': not subprocess.check_output(
                    ['git', 'status', '--porcelain', '--', 'visor', '.github/workflows/visor-ci.yml'],
                    cwd=REPO, text=True).strip(),
                'bundled_third_party_binaries': False,
                'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files['R20_MANIFEST.json'] = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(PREFIX + '/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=9)
    summary = {'zip': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
               'bytes': output.stat().st_size, 'files': len(files), 'source_commit': commit,
               'source_tree_clean': manifest['source_tree_clean'], 'identity': release_identity()}
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    build(parser.parse_args().output)
