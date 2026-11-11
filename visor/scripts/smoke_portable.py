"""Verificar el runtime portable con PATH sin Python externo y STEP certificado."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import tempfile
import trimesh

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('folder', type=Path)
args = p.parse_args(); folder = args.folder.resolve()
if os.name != 'nt':
    raise SystemExit('Esta prueba requiere Windows nativo')
env = {k: v for k, v in os.environ.items() if k.upper() not in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV')}
windows = Path(os.environ['SystemRoot'])
env.update(PATH=os.pathsep.join(map(str, [folder / 'runtime', windows / 'System32', windows])),
           CONVERSOR3D_PROJECT_ROOT=str(folder), CONVERSOR3D_FROZEN_ROOT=str(folder / 'engine'),
           CONVERSOR3D_DATA_DIR=str(folder / 'datos'), CONVERSOR3D_CACHE_DIR=str(folder / 'datos/cache'),
           PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
python = folder / 'runtime/python.exe'
subprocess.run([str(python), '-B', '-c', 'import OCP,vtk,CGAL,gpytoolbox,igl; print("IMPORTS PORTABLE OK")'],
               env=env, check=True, timeout=90)
with tempfile.TemporaryDirectory(prefix='portable prueba ') as temporary:
    source, target = Path(temporary) / 'input.stl', Path(temporary) / 'output.step'
    trimesh.creation.box(extents=[4, 5, 6]).export(source)
    process = subprocess.run([str(python), '-B', '-m', 'conversor3d', 'convert', str(source), str(target)],
                             env=env, check=True, capture_output=True, text=True, encoding='utf-8', timeout=300)
    result = json.loads(process.stdout.strip().splitlines()[-1])
    proof = json.loads(target.with_suffix('.r19_nucleo.json').read_text(encoding='utf-8'))
    if result.get('ok') is not True or proof.get('ok') is not True or not target.is_file():
        raise ValueError('El portable no entrega un STEP certificado')
    if proof['calidad']['integridad_cad']['brep_exacto'] is not True:
        raise ValueError('STEP portable no exacto valido')
    measured = subprocess.run([str(python), '-B', '-c',
        'import cadquery as cq,sys; print(cq.importers.importStep(sys.argv[1]).val().Volume())', str(target)],
        env=env, check=True, capture_output=True, text=True, encoding='utf-8', timeout=60)
    volume = float(measured.stdout.strip().splitlines()[-1])
    if abs(volume - 120.) > 1e-7 or len(proof['mallado_fino']['resoluciones']) != 3:
        raise ValueError('Volumen o controles completos del portable incorrectos')
    (folder / 'SMOKE_RESULT.json').write_text(json.dumps({'ok': True, 'volume_mm3': volume,
        'certificate': proof['certificado'], 'isolated_runtime': True}, indent=2), encoding='utf-8')
    print('PORTABLE CONVERSION OK', flush=True)
