"""Arranque ligero R21: código independiente y entorno R20 reutilizado sin instalar."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def verify_update(root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads((root / 'R21_MANIFEST.json').read_text(encoding='utf-8'))
    if manifest['identity']['release'] != 'R21':
        raise ValueError('El manifiesto no corresponde a R21')
    for name, expected in manifest['files'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Archivo de actualización ausente o fuera de R21: ' + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Archivo R21 modificado o incompleto: ' + name)
    return manifest


def base_python(base):
    return Path(base) / '.venv_r20' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def valid_base(base):
    base = Path(base)
    return (base_python(base).is_file() and
            (base / 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes/motor_r19.py').is_file())


def choose_base(root, explicit=None, interactive=True):
    root = Path(root).resolve()
    if explicit:
        path = Path(explicit).resolve()
        if not valid_base(path):
            raise ValueError('La carpeta elegida no contiene R20 con su entorno preparado')
        return path
    candidates = [root.parent / 'Conversor_3D_R20_experimental', root.parent]
    config = root / 'datos/base_r20.json'
    if config.is_file():
        try:
            candidates.insert(0, Path(json.loads(config.read_text())['base_r20']))
        except (OSError, ValueError, KeyError, TypeError):
            pass
    candidates.extend(root.parent.glob('*R20*'))
    for path in candidates:
        if valid_base(path):
            return path.resolve()
    if interactive:
        import tkinter as tk
        from tkinter import filedialog
        window = tk.Tk()
        window.withdraw()
        try:
            folder = filedialog.askdirectory(title='Selecciona la carpeta de R20 ya instalada')
        finally:
            window.destroy()
        if folder and valid_base(folder):
            return Path(folder).resolve()
    raise ValueError('No se localizó R20. Selecciona su carpeta o ejecuta --base-r20 RUTA. No se ha instalado nada.')


def prepare(root, base):
    root, base = Path(root).resolve(), Path(base).resolve()
    verify_update(root)
    engine = base / 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes'
    expected = json.loads((root / 'R19_FROZEN_SHA256.json').read_text(encoding='utf-8'))
    for name, digest in expected.items():
        path = engine / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('La fuente R19 requerida falta o está modificada: ' + name)
    data = root / 'datos'
    env = {key: value for key, value in os.environ.items()
           if key.upper() not in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV', 'CONVERSOR3D_PROFILE_DIR')}
    env.update(PYTHONPATH=str(root / 'visor/src'), PYTHONDONTWRITEBYTECODE='1',
               PYTHONUTF8='1', PYTHONUNBUFFERED='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
               CONVERSOR3D_PROJECT_ROOT=str(base), CONVERSOR3D_FROZEN_ROOT=str(engine),
               CONVERSOR3D_DATA_DIR=str(data), CONVERSOR3D_CACHE_DIR=str(data / 'cache'),
               CONVERSOR3D_PORT='8785', CONVERSOR3D_RETENTION_DAYS='0',
               CONVERSOR3D_CACHE_ENABLED='1', VISOR_PERFIL='precision')
    probe = """import json,sys,struct
assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8, 'Se necesita Python 3.12 x64'
from conversor3d.dependencies import runtime_identity
from conversor3d._version import APPLICATION_LABEL
runtime_identity()
import OCP,vtk,CGAL,gpytoolbox,igl,fastapi,uvicorn,manifold3d
print(json.dumps({'ok':True,'version':APPLICATION_LABEL}))
"""
    result = subprocess.run([str(base_python(base)), '-B', '-c', probe], env=env,
                            capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise ValueError('El entorno R20 no está preparado. Ejecuta Reparar_Entorno_R20.bat en R20.\n'
                         + result.stderr[-1600:])
    data.mkdir(parents=True, exist_ok=True)
    (data / 'base_r20.json').write_text(json.dumps({'base_r20': str(base)}, indent=2), encoding='utf-8')
    return env, json.loads(result.stdout.splitlines()[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-r20', type=Path)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--diagnostico', action='store_true')
    parser.add_argument('--port', type=int, default=8785)
    args = parser.parse_args()
    try:
        verify_update(ROOT)
        base = choose_base(ROOT, args.base_r20, interactive=not args.no_browser)
        env, result = prepare(ROOT, base)
        print('R21 preparada. R20 y su entorno se conservan sin modificaciones.', flush=True)
        if args.diagnostico:
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return 0
        command = [str(base_python(base)), '-B', '-m', 'conversor3d', 'serve', '--port', str(args.port)]
        if args.no_browser:
            command.append('--no-browser')
        return subprocess.call(command, env=env, cwd=ROOT)
    except Exception as error:
        print('ERROR R21: ' + str(error), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
