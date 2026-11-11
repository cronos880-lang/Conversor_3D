"""Instalar pins con hashes, progreso por paquete y recuperación de instalaciones parciales."""
from pathlib import Path
import csv
import importlib.metadata
import io
import os
import platform
import re
import subprocess
import sys
import tempfile

from installation_progress import run_progress

ROOT = Path(__file__).resolve().parents[1]


def locked_packages(lock):
    """Conservar íntegros los hashes de cada entrada del lock ya resuelto."""
    result = []
    for block in re.split(r'\n\s*\n', Path(lock).read_text(encoding='utf-8')):
        lines = [line for line in block.splitlines() if line.strip() and not line.lstrip().startswith('#')]
        if not lines:
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s\\;]+)\s*\\?', lines[0])
        requirement = '\n'.join(lines) + '\n'
        if not match or not re.search(r'--hash=sha256:[a-f0-9]{64}(?:\s|$)', requirement):
            raise ValueError('Entrada sin pin/hash completo en ' + str(lock))
        result.append((match[1], match[2], requirement))
    if not result:
        raise ValueError('El lock no contiene paquetes')
    return result


def complete_distribution(distribution, version):
    """Un número de versión solo no demuestra que una extracción haya terminado."""
    if distribution.version != version:
        return False
    record = distribution.read_text('RECORD')
    if not record:
        return False
    # Distribution.files puede filtrar los archivos ausentes. Leer el RECORD
    # original permite detectar precisamente una instalación interrumpida.
    rows = list(csv.reader(io.StringIO(record)))
    if not rows:
        return False
    for row in rows:
        if len(row) != 3 or not row[0]:
            return False
        if Path(row[0]).suffix in ('.pyc', '.pyo'):
            continue
        file = Path(distribution.locate_file(row[0]))
        if not file.is_file():
            return False
        if row[2] and (not row[2].isdigit() or file.stat().st_size != int(row[2])):
            return False
    return True


def install(root=ROOT):
    root = Path(root)
    if sys.version_info[:2] != (3, 12) or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise ValueError('Se requiere CPython 3.12 x64 para estos locks comprobados')
    if sys.platform not in ('win32', 'linux'):
        raise ValueError('Los locks actuales cubren Windows y Linux')
    lock = root / ('requirements-windows-py312.lock' if os.name == 'nt' else 'requirements-linux-py312.lock')
    packages = locked_packages(lock)
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1',
           'PYTHONDONTWRITEBYTECODE': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1'}
    with tempfile.TemporaryDirectory(prefix='R20 requisitos ') as temporary:
        one_package = Path(temporary) / 'paquete.lock'
        for index, (name, version, requirement) in enumerate(packages, 1):
            label = f'[PAQUETE {index}/{len(packages)}] {name} {version}'
            print(label + ' — verificando archivos...', flush=True)
            try:
                distribution = importlib.metadata.distribution(name)
            except importlib.metadata.PackageNotFoundError:
                distribution = None
            if distribution is not None and complete_distribution(distribution, version):
                print(label + ' — completo, se conserva', flush=True)
                continue
            repair = distribution is not None and distribution.version == version
            print(label + (' — reparando extracción incompleta' if repair else ' — instalando'), flush=True)
            one_package.write_text(requirement, encoding='utf-8')
            command = [sys.executable, '-u', '-m', 'pip', 'install', '--require-hashes',
                       '--only-binary=:all:', '--no-deps', '--no-compile', '-r', str(one_package)]
            if repair:
                command.append('--ignore-installed')
            run_progress(command, env=env, label=label, timeout=600)
            importlib.invalidate_caches()
            installed = importlib.metadata.distribution(name)
            if not complete_distribution(installed, version):
                raise RuntimeError(label + ': siguen faltando archivos después de instalar')
        print(f'Paquetes verificados: {len(packages)}/{len(packages)}.', flush=True)
    print('Preparando el programa R20...', flush=True)
    run_progress([sys.executable, '-u', '-m', 'pip', 'install', '--no-compile', '-e', str(root),
                  '--no-deps', '--no-build-isolation'], env=env, label='Programa R20', timeout=300)
    print('Comprobando la coherencia completa de dependencias...', flush=True)
    run_progress([sys.executable, '-u', '-m', 'pip', 'check'], env=env,
                 label='Coherencia de dependencias', timeout=120)


if __name__ == '__main__':
    try:
        install()
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        print('ERROR DE INSTALACIÓN: ' + str(error), file=sys.stderr, flush=True)
        raise SystemExit(2)
