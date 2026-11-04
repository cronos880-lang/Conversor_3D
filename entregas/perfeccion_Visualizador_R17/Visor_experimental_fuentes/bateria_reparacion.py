"""Batería reproducible: proceso aislado, huellas, RAM y resultados reales.

Uso: python bateria_reparacion.py --motor CARPETA --stl CARPETA --salida CARPETA
No sustituye errores por éxito ni omite piezas ausentes. Una conversión a la vez.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import psutil


def ejecutar(motor, source, destination, *, limite=None, memoria_mb=5500, extra_env=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    limit = limite or (420 if source.stat().st_size < 1_000_000 else
                      600 if source.stat().st_size < 5_000_000 else 900)
    env = {**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8',
           'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
           **(extra_env or {})}
    row = {'archivo': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
           'limite_s': limit, 'limite_ram_mb': memoria_mb}
    start, peak = time.monotonic(), 0
    with destination.with_suffix('.stdout.txt').open('w', encoding='utf-8') as out, \
         destination.with_suffix('.stderr.txt').open('w', encoding='utf-8') as err:
        p = subprocess.Popen([sys.executable, str(motor/'motor_v2.py'), str(source), str(destination)],
                             cwd=motor, env=env, stdout=out, stderr=err,
                             start_new_session=os.name != 'nt',
                             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0)
        proc = psutil.Process(p.pid)
        while p.poll() is None:
            try:
                ram = sum(c.memory_info().rss for c in [proc, *proc.children(recursive=True)]
                          if c.is_running())
                peak = max(peak, ram)
            except psutil.Error:
                pass
            why = ('tiempo_agotado' if time.monotonic()-start > limit else
                   'memoria_agotada' if peak > memoria_mb*1024**2 else None)
            if why:
                row['interrupcion'] = why
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(p.pid)], capture_output=True)
                else:
                    os.killpg(p.pid, signal.SIGKILL)
                break
            time.sleep(.2)
        p.wait()
    row.update(segundos=round(time.monotonic()-start, 3), ram_pico_mb=round(peak/1024**2, 2),
               codigo=p.returncode)
    try:
        row['informe_motor'] = json.loads(destination.with_suffix('.stdout.txt').read_text(
            encoding='utf-8').strip().splitlines()[-1])
    except (ValueError, IndexError):
        row['informe_motor'] = {'ok': False, 'error': row.get('interrupcion', 'Sin informe JSON')}
    row['ok'] = bool(p.returncode == 0 and row['informe_motor'].get('ok') and destination.exists())
    if row['ok']:
        row['sha256_step'] = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.resultado.json').write_text(json.dumps(row, indent=2, ensure_ascii=False), encoding='utf-8')
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--motor', type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument('--stl', type=Path, required=True)
    ap.add_argument('--salida', type=Path, required=True)
    ap.add_argument('--solo', nargs='*')
    ap.add_argument('--limite', type=int)
    a = ap.parse_args()
    a.motor, a.stl, a.salida = a.motor.resolve(), a.stl.resolve(), a.salida.resolve()
    sources = sorted(a.stl.glob('*.stl'))
    if a.solo:
        sources = [p for p in sources if any(s.lower() in p.name.lower() for s in a.solo)]
    if not sources:
        ap.error('No hay STL; la batería no se considera superada.')
    a.salida.mkdir(parents=True, exist_ok=True)
    report = {'plataforma': platform.platform(), 'python': sys.version,
              'dependencias': {n: importlib.metadata.version(n) for n in
                               ('cadquery', 'cadquery-ocp', 'trimesh', 'numpy', 'scipy', 'vtk', 'shapely', 'manifold3d', 'psutil', 'networkx')},
              'resultados': []}
    for i, source in enumerate(sources):
        print(f'[{i+1}/{len(sources)}] {source.name}', flush=True)
        row = ejecutar(a.motor, source, a.salida/(source.stem+'.step'), limite=a.limite)
        report['resultados'].append(row)
        (a.salida/'bateria.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'  ok={row["ok"]} segundos={row["segundos"]} RAM={row["ram_pico_mb"]} MB', flush=True)
    return 0 if all(r['ok'] for r in report['resultados']) else 1


if __name__ == '__main__':
    sys.exit(main())
