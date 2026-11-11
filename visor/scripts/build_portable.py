"""Construir carpeta Windows autocontenida, sin ZIP ni publicación automática."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import sys

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

REPO = Path(__file__).resolve().parents[2]


def requirement_lines(path, seen=None):
    seen = set() if seen is None else seen
    path = Path(path).resolve()
    if path in seen:
        raise ValueError('Inclusión cíclica de requisitos')
    seen.add(path)
    lines = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('-r '):
            lines.extend(requirement_lines(path.parent / line[3:].strip(), seen))
        else:
            lines.append(line)
    return lines


def distributions(requirements: Path):
    queue = [Requirement(line) for line in requirement_lines(requirements)]
    queue.append(Requirement('setuptools==80.9.0'))
    visited, result = set(), {}
    while queue:
        requirement = queue.pop()
        marker_key = (canonicalize_name(requirement.name), tuple(sorted(requirement.extras)))
        if marker_key in visited:
            continue
        visited.add(marker_key)
        dist = importlib.metadata.distribution(requirement.name)
        if requirement.specifier and dist.version not in requirement.specifier:
            raise ValueError('Dependencia instalada no coincide: ' + str(requirement))
        result[canonicalize_name(dist.metadata['Name'])] = dist
        extras = requirement.extras or {''}
        for text in dist.requires or []:
            dependency = Requirement(text)
            if not dependency.marker or any(dependency.marker.evaluate({'extra': extra}) for extra in extras):
                queue.append(dependency)
    return result


def copy_distribution(dist, target: Path):
    """Sólo archivos de la distribución dentro de su raíz de paquetes."""
    site_root = Path(dist.locate_file('')).resolve()
    for file in dist.files or []:
        source = Path(dist.locate_file(file)).resolve()
        if (not source.is_file() or not source.is_relative_to(site_root)
                or '__pycache__' in source.parts or source.suffix == '.pyc'):
            continue
        relative = source.relative_to(site_root)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def build(output: Path):
    if os.name != 'nt' or sys.version_info[:2] != (3, 12) or platform.architecture()[0] != '64bit':
        raise ValueError('La carpeta portable debe construirse en Windows con Python 3.12 x64')
    output = Path(output).resolve()
    output.mkdir(exist_ok=False)
    runtime, packages = output / 'runtime', output / 'runtime/Lib/site-packages'
    runtime.mkdir(); packages.mkdir(parents=True)
    base = Path(sys.base_prefix)
    for pattern in ('python.exe', 'pythonw.exe', 'python*.dll', 'vcruntime*.dll', 'LICENSE*'):
        for path in base.glob(pattern):
            if path.is_file():
                shutil.copy2(path, runtime / path.name)
    if not (runtime / 'python.exe').is_file() or not (runtime / 'python312.dll').is_file():
        raise ValueError('El intérprete no contiene el runtime CPython completo')
    for folder in ('DLLs', 'Lib'):
        shutil.copytree(base / folder, runtime / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('site-packages', '__pycache__', 'test', 'tests'))
    requirements = REPO / 'visor/requirements-runtime.txt'
    selected = distributions(requirements)
    inventory = []
    for name, dist in sorted(selected.items()):
        print('COPIANDO', name, dist.version, flush=True)
        copy_distribution(dist, packages)
        inventory.append({'name': name, 'version': dist.version,
                          'license': dist.metadata.get('License-Expression') or dist.metadata.get('License', '')})
    shutil.copytree(REPO / 'visor/src/conversor3d', output / 'app/conversor3d',
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(REPO / 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes', output / 'engine',
                    ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '.venv', 'Registros_Conversion'))
    (runtime / 'python312._pth').write_text(
        'python312.zip\n.\nDLLs\nLib\nLib/site-packages\n../app\n../engine\n'
        '../app/conversor3d/resources/profiling\nimport site\n', encoding='utf-8')
    launcher = ('@echo off\r\nsetlocal\r\n'
                'set "CONVERSOR3D_PROJECT_ROOT=%~dp0"\r\n'
                'set "CONVERSOR3D_FROZEN_ROOT=%~dp0engine"\r\n'
                'set "CONVERSOR3D_DATA_DIR=%~dp0datos"\r\n'
                'set "CONVERSOR3D_CACHE_DIR=%~dp0datos\\cache"\r\n'
                'set "PYTHONDONTWRITEBYTECODE=1"\r\n'
                '"%~dp0runtime\\python.exe" -B -m conversor3d serve\r\n'
                'if errorlevel 1 pause\r\n')
    (output / 'Iniciar_Visor.bat').write_bytes(launcher.encode('ascii'))
    (output / 'DEPENDENCIES.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    (output / 'LEEME.txt').write_text(
        'Carpeta de prueba autocontenida para Windows. Ejecutar Iniciar_Visor.bat.\n'
        'No requiere instalar Python ni descargar paquetes al abrirla.\n'
        'No es una nueva entrega publicada. La redistribucion debe respetar la auditoria de licencias.\n', encoding='utf-8')
    hashes = {str(path.relative_to(output)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in output.rglob('*') if path.is_file()}
    (output / 'SHA256.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
    print(json.dumps({'output': str(output), 'distributions': len(inventory), 'files': len(hashes),
                      'python': sys.version, 'published': False}), flush=True)
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    build(p.parse_args().output)
