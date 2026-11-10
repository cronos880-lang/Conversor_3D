"""Instalación visible y diagnóstico acotado; no importa ni modifica el motor CAD.

--comprobar sólo lee el entorno y registra sus pruebas. --instalar actúa
exclusivamente sobre la .venv independiente de esta carpeta R19.
"""
from pathlib import Path
import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'Visor_experimental_fuentes'
MODULES = ('gpytoolbox_bindings_copyleft', 'CGAL.CGAL_Kernel',
           'CGAL.CGAL_Polygon_mesh_processing', 'igl', 'OCP', 'cadquery',
           'numpy', 'scipy', 'trimesh', 'vtk', 'shapely', 'uvicorn',
           'fastapi', 'multipart', 'manifold3d', 'psutil', 'networkx')


class Runner:
    def __init__(self, log, *, heartbeat=5.):
        self.log = Path(log)
        self.heartbeat = heartbeat
        self.results = []

    def say(self, message):
        print(message, flush=True)
        with self.log.open('a', encoding='utf-8') as stream:
            stream.write(message + '\n')

    def step(self, label, args, *, timeout, cwd=None):
        self.say('\n' + label + ' (maximo ' + str(timeout) + ' s)')
        started = time.monotonic()
        env = {**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8',
               'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1',
               'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
        record = dict(etapa=label, ok=False)
        with self.log.open('ab') as stream:
            offset = stream.tell()
            try:
                with subprocess.Popen(args, stdout=stream, stderr=stream, cwd=cwd, env=env,
                                      start_new_session=os.name != 'nt') as child:
                    try:
                        last = started
                        while child.poll() is None:
                            now = time.monotonic()
                            if now - started >= timeout:
                                stop(child)
                                record['tipo'] = 'tiempo_agotado'
                                break
                            if now - last >= self.heartbeat:
                                self.say('  Sigue trabajando: ' + str(int(now - started)) + ' s. Registro: ' + str(self.log))
                                last = now
                            time.sleep(.1)
                        code = child.wait(timeout=10)
                    finally:
                        if child.poll() is None:
                            stop(child)
                    record.update(codigo=code, codigo_hex=f'0x{code & 0xffffffff:08X}')
                    record['ok'] = code == 0 and record.get('tipo') != 'tiempo_agotado'
                    if code and 'tipo' not in record:
                        record['tipo'] = 'proceso_fallido'
            except OSError as exc:
                record.update(tipo='no_se_pudo_ejecutar', error=str(exc))
        record['segundos'] = round(time.monotonic() - started, 2)
        self.results.append(record)
        if record['ok']:
            self.say('  OK (' + str(record['segundos']) + ' s)')
        else:
            # Mostrar el mensaje real (incluido un error DLL o de pip), no
            # sustituirlo por una recomendación genérica de reinstalar.
            with self.log.open('rb') as stream:
                stream.seek(offset)
                detail = stream.read().decode('utf-8', errors='replace')
            self.say('  FALLO: ' + record.get('tipo', 'desconocido'))
            if record.get('error'):
                self.say(record['error'])
            if detail.strip():
                self.say('\n'.join(detail.splitlines()[-18:]))
            self.say('  Registro completo: ' + str(self.log))
        return record['ok']


def stop(child):
    """Detener también hijos de pip si se agota el presupuesto."""
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(child.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if child.poll() is None:
        child.kill()
    child.wait(timeout=10)


def check(runner, python, *, timeout=90):
    python = str(python)
    identity = 'import sys,struct; print(sys.version); assert sys.version_info[:2]==(3,12) and struct.calcsize("P")==8, "Se requiere Python 3.12 de 64 bits"'
    if not runner.step('Python 3.12 de 64 bits', [python, '-u', '-c', identity], timeout=30):
        return False
    if not runner.step('Coherencia de dependencias (pip check)', [python, '-m', 'pip', 'check'], timeout=90):
        return False
    for index, name in enumerate(MODULES, 1):
        code = 'import importlib; importlib.import_module(' + repr(name) + '); print("Importacion correcta")'
        if not runner.step(f'[{index}/{len(MODULES)}] Cargando {name}', [python, '-u', '-c', code], timeout=timeout):
            return False
    # Los imports separados localizan el bloqueo; esta segunda prueba conserva
    # el orden original y detecta conflictos de DLL al cargar conjuntamente.
    code = 'import gpytoolbox_bindings_copyleft,CGAL,igl,cadquery,numpy,scipy,trimesh,vtk,shapely,uvicorn,fastapi,manifold3d,psutil,networkx; print("Importacion conjunta correcta")'
    if not runner.step('Comprobacion conjunta de librerias CAD', [python, '-u', '-c', code], timeout=timeout):
        return False
    native = 'import cadquery as cq; s=cq.Solid.makeBox(1,1,1); assert s.isValid() and abs(s.Volume()-1)<1e-9; print("Solido CAD de prueba correcto")'
    return runner.step('Prueba basica del nucleo CAD', [python, '-u', '-c', native], timeout=timeout)


def main(argv=None):
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--comprobar', action='store_true')
    mode.add_argument('--instalar', action='store_true')
    args = parser.parse_args(argv)
    logs = ROOT / 'Diagnosticos_Instalacion'
    logs.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    runner = Runner(logs / ('Entorno_' + stamp + '.txt'))
    python = SOURCE / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    runner.say('R19 - ' + ('Instalacion y comprobacion' if args.instalar else 'Comprobacion sin reinstalar'))
    runner.say('Entorno: ' + str(python))
    ok = False
    try:
        if not (SOURCE / 'requirements_bloqueadas.txt').is_file() or not (ROOT / 'Iniciar_R19.bat').is_file():
            raise ValueError('El parche esta en otra carpeta. Copia su contenido en la carpeta R19 donde esta Iniciar_R19.bat; no lo ejecutes desde una carpeta de parche separada')
        if args.instalar:
            if sys.version_info[:2] != (3, 12) or sys.maxsize <= 2 ** 32:
                raise ValueError('Ejecuta este instalador con Python 3.12 de 64 bits')
            if not python.is_file():
                if not runner.step('Creando entorno independiente R19', [sys.executable, '-m', 'venv', str(SOURCE / '.venv')], timeout=180):
                    return 2
            if not runner.step('Instalando dependencias; las ya instaladas se reutilizan',
                               [str(python), '-m', 'pip', 'install', '--disable-pip-version-check',
                                '--no-input', '--progress-bar', 'off', '--timeout', '60', '--retries', '2',
                                '-r', str(SOURCE / 'requirements_bloqueadas.txt')], timeout=1800):
                return 2
        if not python.is_file():
            raise ValueError('No existe la .venv de R19. Ejecuta Instalar_Entorno_R19.bat o reutiliza el entorno anterior con Iniciar_R19.bat')
        ok = check(runner, python)
        if ok:
            runner.say('\nENTORNO CORRECTO.')
        else:
            runner.say('\nNo se ha confirmado el entorno. El registro indica la etapa que falla.')
        return 0 if ok else 2
    except (OSError, ValueError) as exc:
        runner.say('ERROR: ' + str(exc))
        return 2
    finally:
        runner.log.with_suffix('.json').write_text(json.dumps(dict(ok=ok, modo='instalar' if args.instalar else 'comprobar',
                python=str(python), pruebas=runner.results), ensure_ascii=False, indent=2), encoding='utf-8')
        runner.say('Registro: ' + str(runner.log))


if __name__ == '__main__':
    raise SystemExit(main())
