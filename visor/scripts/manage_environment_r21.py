"""Instalar y abrir R21 completa en su entorno propio, sin consultar R20."""
from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys

from installation_progress import installation_lock, run_progress
from r21_launcher import RUNTIME_PROBE, diagnose_native, run_probe

ROOT = Path(__file__).resolve().parents[2]
VENV = ROOT / '.venv_r21'
PYTHON = VENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def status(message):
    print(message, flush=True)
    data = ROOT / 'datos'
    data.mkdir(parents=True, exist_ok=True)
    with (data / 'arranque_R21.log').open('a', encoding='utf-8') as log:
        log.write(datetime.now().isoformat(timespec='seconds') + ' ' + message + '\n')


def verify_payload(root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads((root / 'R21_MANIFEST.json').read_text(encoding='utf-8'))
    if manifest['identity']['kind'] != 'COMPLETA' or manifest['identity']['requires_r20']:
        raise ValueError('Esta carpeta no es la entrega R21 completa independiente')
    for name, digest in manifest['files'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Archivo de R21 incompleto o modificado: ' + name)
    return manifest


def environment(port=8785):
    result = {k: v for k, v in os.environ.items()
              if k.upper() not in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV',
                                   'CONVERSOR3D_PROFILE_DIR', 'CONVERSOR3D_BASE_R20')}
    data = ROOT / 'datos'
    result.update(PYTHONUTF8='1', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1',
                  PYTHONNOUSERSITE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                  PYTHONPATH=str(ROOT / 'visor/src'), CONVERSOR3D_PROJECT_ROOT=str(ROOT),
                  CONVERSOR3D_FROZEN_ROOT=str(ROOT / 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes'),
                  CONVERSOR3D_DATA_DIR=str(data), CONVERSOR3D_CACHE_DIR=str(data / 'cache'),
                  CONVERSOR3D_PORT=str(port), CONVERSOR3D_RETENTION_DAYS='0',
                  CONVERSOR3D_CACHE_ENABLED='1', VISOR_PERFIL='precision')
    return result


def probe():
    if not PYTHON.is_file():
        raise ValueError('El entorno propio .venv_r21 aún no está preparado')
    lock = ROOT / 'visor' / ('requirements-windows-py312.lock' if os.name == 'nt' else 'requirements-linux-py312.lock')
    expected = dict(re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\]+)', lock.read_text(), re.MULTILINE))
    code = ('import sys,importlib.metadata as m\nfrom pathlib import Path\n'
            'assert Path(sys.prefix).resolve()==Path(' + repr(str(VENV)) + ').resolve(), "Entorno ajeno a R21"\n'
            'expected=' + repr(expected) + '\n'
            'for name, version in expected.items():\n'
            ' assert m.version(name)==version, name+" no coincide con el lock"\n'
            'from conversor3d._version import __version__\n'
            'assert m.version("conversor3d-visor")==__version__, "La identidad instalada no es R21"\n' + RUNTIME_PROBE)
    return run_probe(PYTHON, code, environment(), 'Versiones del entorno propio R21', status)


def install():
    if sys.version_info[:2] != (3, 12) or struct.calcsize('P') != 8:
        raise ValueError('R21 requiere Python 3.12 x64')
    with installation_lock(ROOT / 'datos/instalacion_R21.lock'):
        status('[1/4] Verificando la entrega completa R21 y su motor protegido...')
        verify_payload()
        status('[2/4] Preparando el entorno independiente .venv_r21...')
        run_progress([sys.executable, '-B', '-m', 'venv', str(VENV)],
                     env=environment(), label='Preparando .venv_r21 sin borrar sus paquetes', timeout=180)
        if not PYTHON.is_file():
            raise ValueError('.venv_r21 existe pero no contiene Python. No se borra automáticamente.')
        status('[3/4] Verificando e instalando los paquetes bloqueados con sus hashes...')
        run_progress([str(PYTHON), '-u', '-B', str(ROOT / 'visor/scripts/install_dependencies.py')],
                     cwd=ROOT, env=environment(), log_path=ROOT / 'datos/instalacion_R21.log',
                     label='Instalación R21', timeout=3600)
        status('[4/4] Comprobando versiones e identidad R21, sin importar juntas las bibliotecas CAD...')
        result = probe()
        status('INSTALACIÓN R21 COMPLETA TERMINADA. El diagnóstico nativo se ejecuta por módulos.')
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'start', 'diagnose'))
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=8785)
    args = parser.parse_args()
    try:
        verify_payload()
        if args.action == 'install':
            install()
            return 0
        if args.action == 'diagnose':
            report = {'runtime': probe()}
            report.update(diagnose_native(PYTHON, environment(), status))
            path = ROOT / 'datos' / ('diagnostico_R21_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            status('Diagnóstico R21 guardado en ' + str(path))
            return 0 if report['ok'] else 2
        if not PYTHON.is_file():
            status('Primera apertura de R21: se preparará su entorno independiente una sola vez.')
            install()
        else:
            probe()
        command = [str(PYTHON), '-B', '-m', 'conversor3d', 'serve', '--port', str(args.port)]
        if args.no_browser:
            command.append('--no-browser')
        status('Abriendo R21 completa: http://127.0.0.1:' + str(args.port))
        with subprocess.Popen(command, cwd=ROOT, env=environment(args.port),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding='utf-8', errors='replace', bufsize=1) as process:
            for line in process.stdout:
                status(line.rstrip())
            code = process.wait()
        return code
    except Exception as error:
        status('ERROR R21: ' + str(error))
        status('Consulta datos/arranque_R21.log y datos/instalacion_R21.log. Reparar_Entorno_R21.bat actúa sólo sobre esta carpeta.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
