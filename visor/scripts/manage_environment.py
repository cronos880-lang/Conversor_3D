"""Preparar y arrancar la entrega R20 en su propio entorno, sin tocar otro Visor."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import venv

from installation_progress import installation_lock, run_progress

INSTALLER_REVISION = 2
ROOT = Path(__file__).resolve().parents[2]
VENV = ROOT / '.venv_r20'
PYTHON = VENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
LOCK = ROOT / 'visor' / ('requirements-windows-py312.lock' if os.name == 'nt'
                         else 'requirements-linux-py312.lock')


def verify_payload(root=ROOT):
    """Comprobar los bytes entregados; los registros y el entorno son posteriores."""
    root = Path(root).resolve()
    manifest = root / 'R20_MANIFEST.json'
    if not manifest.is_file():
        return  # Checkout de desarrollo; la entrega ZIP siempre incluye manifiesto.
    for relative, expected in json.loads(manifest.read_text(encoding='utf-8'))['files'].items():
        file = (root / relative).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            raise ValueError('Archivo de entrega ausente o fuera de la carpeta: ' + relative)
        if hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError('Archivo de entrega modificado: ' + relative)


def expected_versions():
    return dict(re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\]+)',
                           LOCK.read_text(encoding='utf-8'), flags=re.MULTILINE))


def environment():
    data = ROOT / 'datos'
    return {**os.environ, 'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1', 'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONPATH': str(ROOT / 'visor/src'),
            'CONVERSOR3D_PROJECT_ROOT': str(ROOT),
            'CONVERSOR3D_FROZEN_ROOT': str(ROOT / 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes'),
            'CONVERSOR3D_DATA_DIR': str(data), 'CONVERSOR3D_CACHE_DIR': str(data / 'cache'),
            'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}


def probe():
    if not PYTHON.is_file():
        return {'ok': False, 'reason': 'El entorno propio aún no existe'}
    code = '''import importlib.metadata as m,json,sys
from pathlib import Path
expected=json.loads(sys.argv[1])
assert Path(sys.prefix).resolve()==Path(sys.argv[2]).resolve(), 'Entorno ajeno a R20'
for name,version in expected.items():
    assert m.version(name)==version, name+' no coincide con el lock'
import OCP,vtk,CGAL,gpytoolbox,igl,fastapi,uvicorn,manifold3d
from conversor3d.dependencies import runtime_identity
from conversor3d._version import __version__,APPLICATION_LABEL
assert m.version('conversor3d-visor')==__version__, 'Identidad de paquete inconsistente'
print(json.dumps({'ok':True,'version':APPLICATION_LABEL,'runtime':runtime_identity()}))
'''
    try:
        output = run_progress([str(PYTHON), '-u', '-B', '-c', code,
                               json.dumps(expected_versions()), str(VENV)],
                              env=environment(), label='Comprobando versiones y bibliotecas',
                              timeout=90, echo=False)
        return json.loads(output.strip().splitlines()[-1])
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        return {'ok': False, 'reason': str(error)}


def run_logged(command):
    log_path = ROOT / 'datos/instalacion_R20.log'
    log_path.parent.mkdir(exist_ok=True)
    try:
        run_progress(command, cwd=ROOT, env=environment(), log_path=log_path,
                     label='Preparación de dependencias R20', timeout=3600, heartbeat=15)
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(str(error) + f'\nConsulta {log_path}') from error


def install_locked():
    if sys.version_info[:2] != (3, 12) or platform.architecture()[0] != '64bit':
        raise ValueError('R20 requiere CPython 3.12 de 64 bits')
    print('[1/4] Verificando archivos R20...', flush=True)
    verify_payload()
    print('[2/4] Preparando el entorno propio .venv_r20...', flush=True)
    if not VENV.exists():
        venv.EnvBuilder(with_pip=True).create(VENV)
    if not PYTHON.is_file():
        raise ValueError('El directorio .venv_r20 existe pero no contiene un Python válido')
    print('[3/4] Instalando/verificando paquete por paquete, con hashes y sin compilar bytecode.', flush=True)
    run_logged([str(PYTHON), '-u', '-B', str(ROOT / 'visor/scripts/install_dependencies.py')])
    print('[4/4] Comprobando versiones y bibliotecas nativas OCP/VTK/CGAL...', flush=True)
    ready = probe()
    if not ready['ok']:
        raise RuntimeError('La comprobación del entorno no ha pasado: ' + ready['reason'])
    print('INSTALACIÓN R20 TERMINADA. Ya puedes abrir Iniciar_R20.bat.', flush=True)
    return ready


def install():
    print(f'R20 — instalador corregido, revisión {INSTALLER_REVISION}.', flush=True)
    with installation_lock(ROOT / 'datos/instalacion_R20.lock'):
        return install_locked()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'start', 'diagnose'))
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        verify_payload()
        if args.action == 'diagnose':
            report = probe()
            report['payload_verified'] = True
            report['installer_revision'] = INSTALLER_REVISION
            output = ROOT / 'Diagnostico_Entorno_R20.json'
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print('Diagnóstico guardado en ' + str(output), flush=True)
            print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
            return 0 if report['ok'] else 2
        if args.action == 'install':
            install()
            print('Entorno R20 preparado. Ejecuta Iniciar_R20.bat.', flush=True)
            return 0
        print('Comprobando el entorno R20 antes de abrir el Visor...', flush=True)
        ready = probe()
        if not ready['ok']:
            install()
        command = [str(PYTHON), '-B', '-m', 'conversor3d', 'serve']
        if args.no_browser:
            command.append('--no-browser')
        return subprocess.call(command, cwd=ROOT, env=environment())
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print('ERROR R20: ' + str(error), file=sys.stderr, flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
