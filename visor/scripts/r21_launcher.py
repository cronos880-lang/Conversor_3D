"""Arranque ligero R21: código independiente y entorno R20 reutilizado sin instalar."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime

ROOT = Path(__file__).resolve().parent
NATIVE_MODULES = ('OCP', 'vtk', 'cadquery', 'trimesh', 'scipy', 'CGAL',
                  'gpytoolbox', 'igl', 'fastapi', 'uvicorn', 'manifold3d')
RUNTIME_PROBE = """import json,sys,struct
print('Comprobando Python 3.12 x64...', flush=True)
assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8, 'Se necesita Python 3.12 x64'
print('Comprobando versiones bloqueadas (sin cargar bibliotecas CAD)...', flush=True)
from conversor3d.dependencies import runtime_identity
from conversor3d._version import APPLICATION_LABEL
runtime=runtime_identity()
print('R21_PROBE_RESULT='+json.dumps({'ok':True,'version':APPLICATION_LABEL,'runtime':runtime}), flush=True)
"""


def stop_probe(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        taskkill = Path(os.environ['SystemRoot']) / 'System32/taskkill.exe'
        try:
            subprocess.run([str(taskkill), '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            pass
        finally:
            if process.poll() is None:
                process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=15)


def run_probe(python, code, env, label, status=print, *, timeout=90, heartbeat=10):
    """Sondeo aislado, con salida visible, límite propio y cierre de descendientes."""
    status('R21: ' + label)
    started = time.monotonic()
    process = subprocess.Popen([str(python), '-B', '-u', '-c', code], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8', errors='replace',
                               start_new_session=True)
    output = queue.Queue()
    def read_output():
        try:
            for line in process.stdout:
                output.put(line.rstrip())
        finally:
            output.put(None)
    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    result, lines = None, []
    try:
        while True:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError(label + ': superó ' + str(timeout) +
                                   ' s. El sondeo se ha detenido; consulta datos/arranque_R21.log.')
            try:
                line = output.get(timeout=min(heartbeat, remaining))
            except queue.Empty:
                status('R21: ' + label + ' sigue en curso (' +
                       str(int(time.monotonic() - started)) + ' s)')
                continue
            if line is None:
                break
            if line.startswith('R21_PROBE_RESULT='):
                result = json.loads(line.partition('=')[2])
            else:
                lines.append(line)
                status(line)
        code = process.wait(timeout=max(.1, timeout - (time.monotonic() - started)))
        if code or not isinstance(result, dict) or result.get('ok') is not True:
            raise ValueError(label + ': fallo (código ' + str(code) + '). ' + '\n'.join(lines[-12:]))
        return result
    except subprocess.TimeoutExpired as error:
        raise TimeoutError(label + ': el proceso no terminó dentro del plazo.') from error
    finally:
        stop_probe(process)
        reader.join(timeout=2)
        process.stdout.close()


def diagnose_native(python, env, status, *, modules=NATIVE_MODULES, timeout=90):
    results = []
    for module in modules:
        started = time.monotonic()
        code = ('import importlib,json\nimportlib.import_module(' + repr(module) + ')\n'
                "print('R21_PROBE_RESULT='+json.dumps({'ok':True}), flush=True)\n")
        try:
            run_probe(python, code, env, 'Importando ' + module, status, timeout=timeout)
            item = {'module': module, 'ok': True}
            status('R21: ' + module + ' OK')
        except (OSError, ValueError, TimeoutError) as error:
            item = {'module': module, 'ok': False, 'error': str(error)}
            status('R21: ' + module + ' ERROR: ' + str(error))
        item['seconds'] = round(time.monotonic() - started, 3)
        results.append(item)
    return {'ok': all(item['ok'] for item in results), 'modules': results,
            'separate_process_per_module': True}


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
    candidates = []
    if os.environ.get('CONVERSOR3D_BASE_R20'):
        candidates.append(Path(os.environ['CONVERSOR3D_BASE_R20']))
    for parent in (root.parent, root.parent.parent):
        candidates.append(parent)
        for child in parent.iterdir():
            if child.is_dir():
                candidates.extend((child, child / 'Conversor_3D_R20_experimental'))
    config = root / 'datos/base_r20.json'
    if config.is_file():
        try:
            candidates.insert(0, Path(json.loads(config.read_text())['base_r20']))
        except (OSError, ValueError, KeyError, TypeError):
            pass
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


def prepare(root, base, status=print):
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
    result = run_probe(base_python(base), RUNTIME_PROBE, env,
                       'Comprobación de Python y versiones bloqueadas', status)
    data.mkdir(parents=True, exist_ok=True)
    (data / 'base_r20.json').write_text(json.dumps({'base_r20': str(base)}, indent=2), encoding='utf-8')
    return env, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-r20', type=Path)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--diagnostico', action='store_true')
    parser.add_argument('--port', type=int, default=8785)
    args = parser.parse_args()
    log = ROOT / 'datos/arranque_R21.log'
    def status(message):
        print(message, flush=True)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('a', encoding='utf-8') as stream:
            stream.write(datetime.now().isoformat(timespec='seconds') + ' ' + message + '\n')
    try:
        status('R21: comprobando la actualización...')
        verify_update(ROOT)
        base = choose_base(ROOT, args.base_r20, interactive=not args.no_browser)
        status('R21: entorno localizado en ' + str(base))
        status('R21: verificando los 357 archivos R19 y las versiones instaladas...')
        env, result = prepare(ROOT, base, status)
        status('R21: integridad y versiones comprobadas. R20 se conserva sin modificaciones.')
        if args.diagnostico:
            diagnostic = diagnose_native(base_python(base), env, status)
            diagnostic['runtime'] = result
            path = ROOT / 'datos' / ('diagnostico_R21_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
            path.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding='utf-8')
            status('R21: diagnóstico guardado en ' + str(path))
            return 0 if diagnostic['ok'] else 2
        command = [str(base_python(base)), '-B', '-m', 'conversor3d', 'serve', '--port', str(args.port)]
        if args.no_browser:
            command.append('--no-browser')
        status('R21: iniciando el servidor; dirección local http://127.0.0.1:' + str(args.port))
        with subprocess.Popen(command, env=env, cwd=ROOT, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                              errors='replace', bufsize=1) as process:
            for line in process.stdout:
                status(line.rstrip())
            code = process.wait()
        if code:
            status('ERROR R21: el servidor terminó con código ' + str(code))
        return code
    except Exception as error:
        try:
            status('ERROR R21: ' + str(error))
        except OSError:
            print('ERROR R21: ' + str(error), flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
