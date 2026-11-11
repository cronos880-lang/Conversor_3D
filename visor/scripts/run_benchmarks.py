"""Conversiones reales sobre catálogo sintético, distinguiendo rechazo de éxito."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time

import cadquery as cq
import psutil
from OCP.BRepCheck import BRepCheck_Analyzer
from conversor3d.benchmarks import generate
from conversor3d.legacy import FROZEN, native_env, sha


def run(output, names):
    output = Path(output)
    specs = generate(output)
    results = []
    for spec in specs:
        name = spec['name']
        if names and name not in names:
            continue
        source = output / (name + '.stl')
        target = output / (name + '.converted.step')
        start = time.monotonic()
        with (output / (name + '.stdout.txt')).open('xb') as out, (output / (name + '.stderr.txt')).open('xb') as err:
            proc = subprocess.Popen([sys.executable, str(FROZEN / 'motor_r19.py'), str(source.resolve()), str(target.resolve())], cwd=FROZEN, env=native_env(), stdout=out, stderr=err)
            try:
                code = proc.wait(timeout=300)
            except subprocess.TimeoutExpired:
                for child in psutil.Process(proc.pid).children(recursive=True):
                    try:child.kill()
                    except psutil.NoSuchProcess:pass
                proc.kill(); proc.wait()
                code = -9
        payload = None
        for line in (output / (name + '.stdout.txt')).read_text(encoding='utf-8', errors='replace').splitlines()[::-1]:
            try:
                value = json.loads(line)
                if isinstance(value, dict) and 'ok' in value:
                    payload = value; break
            except ValueError:
                continue
        if sha(source) != spec['stl_sha256']:
            raise ValueError('Se modificó un STL de entrada')
        if payload is None:
            payload = {'ok': False, 'error': 'Tiempo de ensayo agotado o trabajador interrumpido sin resultado completo'}
        row = {'name': name, 'seconds': time.monotonic() - start, 'ok': code == 0 and payload['ok'], 'source_sha256': sha(source)}
        if row['ok']:
            shape = cq.importers.importStep(str(target)).val()
            if len(shape.Solids()) != 1 or not BRepCheck_Analyzer(shape.wrapped, True, False, True).IsValid():
                raise ValueError('STEP nativo inválido: ' + name)
            if abs(shape.Volume() - spec['volume_mm3']) / spec['volume_mm3'] > .005:
                raise ValueError('Volumen distinto de la referencia conocida: ' + name)
            if 'void_point_mm' in spec and shape.isInside(cq.Vector(*spec['void_point_mm'])):
                raise ValueError('Se perdió una abertura conocida: ' + name)
            row.update(faces=len(shape.Faces()), volume_mm3=shape.Volume(), step_sha256=sha(target), quality=payload['resultado']['calidad'])
        else:
            row['error'] = payload.get('error', 'Rechazo sin detalle')
            if name in {'cylinder', 'thin_wall', 'small_hole'}:
                raise ValueError('Regresión en caso obligatorio: ' + name + ': ' + row['error'])
        results.append(row)
        (output / 'conversions.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(name, 'OK' if row['ok'] else 'RECHAZADO', round(row['seconds'], 2), flush=True)
    return results


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--cases', nargs='*', default=[])
    args = p.parse_args()
    run(args.output, args.cases)
