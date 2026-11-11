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
    return {**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1',
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
import OCP,vtk,CGAL,gpytoolbox,igl
from conversor3d.dependencies import runtime_identity
from conversor3d._version import __version__,APPLICATION_LABEL
assert m.version('conversor3d-visor')==__version__, 'Identidad de paquete inconsistente'
print(json.dumps({'ok':True,'version':APPLICATION_LABEL,'runtime':runtime_identity()}))
'''
    result = subprocess.run([str(PYTHON), '-B', '-c', code,
                             json.dumps(expected_versions()), str(VENV)],
                            env=environment(), capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=90)
    if result.returncode:
        return {'ok': False, 'reason': result.stderr.strip()[-4000:]}
    return json.loads(result.stdout.strip().splitlines()[-1])


def run_logged(command):
    log_path = ROOT / 'datos/instalacion_R20.log'
    log_path.parent.mkdir(exist_ok=True)
    with log_path.open('a', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=environment(),
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='replace')
        for line in process.stdout:
            print(line, end='', flush=True)
            log.write(line)
        code = process.wait()
    if code:
        raise RuntimeError(f'La instalación terminó con código {code}. Consulta {log_path}')


def install():
    if sys.version_info[:2] != (3, 12) or platform.architecture()[0] != '64bit':
        raise ValueError('R20 requiere CPython 3.12 de 64 bits')
    print('[1/4] Verificando archivos R20...', flush=True)
    verify_payload()
    ready = probe()
    if ready['ok']:
        print('Entorno R20 ya verificado. No necesita reinstalar paquetes.', flush=True)
        return ready
    print('[2/4] Preparando el entorno propio .venv_r20...', flush=True)
    if not VENV.exists():
        venv.EnvBuilder(with_pip=True).create(VENV)
    if not PYTHON.is_file():
        raise ValueError('El directorio .venv_r20 existe pero no contiene un Python válido')
    print('[3/4] Instalando versiones con hashes. La primera vez puede tardar varios minutos.', flush=True)
    run_logged([str(PYTHON), '-B', str(ROOT / 'visor/scripts/install_dependencies.py')])
    print('[4/4] Comprobando versiones y bibliotecas nativas OCP/VTK/CGAL...', flush=True)
    ready = probe()
    if not ready['ok']:
        raise RuntimeError('La comprobación del entorno no ha pasado: ' + ready['reason'])
    print('INSTALACIÓN R20 TERMINADA. Ya puedes abrir Iniciar_R20.bat.', flush=True)
    return ready


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
            output = ROOT / 'Diagnostico_Entorno_R20.json'
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print('Diagnóstico guardado en ' + str(output), flush=True)
            print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
            return 0 if report['ok'] else 2
        ready = probe()
        if not ready['ok']:
            install()
        if args.action == 'install':
            print('Entorno R20 preparado. Ejecuta Iniciar_R20.bat.', flush=True)
            return 0
        command = [str(PYTHON), '-B', '-m', 'conversor3d', 'serve']
        if args.no_browser:
            command.append('--no-browser')
        return subprocess.call(command, cwd=ROOT, env=environment())
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print('ERROR R20: ' + str(error), file=sys.stderr, flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
