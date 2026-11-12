"""Ejecuta la batería congelada con sus cuatro raíces de importación explícitas."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile

repo = Path(__file__).resolve().parents[2]
root = repo / 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes'
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--xml', required=True)
args = p.parse_args()
paths = [root, root / 'motor_superficies', root / 'motor_calidad',
         root / 'motor_calidad/motor_superficies', repo / 'visor/scripts']
env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1',
       'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
       'PYTHONPATH': os.pathsep.join(map(str, paths))}
command = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
           '-p', 'legacy_test_plugin',
           '--junitxml=' + str(Path(args.xml).resolve())]
command.extend(str(path) for path in sorted(root.glob('test_*.py')))
# Dos pruebas históricas conservan sus seis entradas R5 byte a byte, con hashes.
# El paquete de fixtures sustituye la dependencia de toda la entrega obsoleta.
with tempfile.TemporaryDirectory(prefix='visor legacy fixtures ') as temporary:
    fixtures = Path(temporary)
    sources, results = fixtures / 'sources', fixtures / 'results'
    sources.mkdir(); results.mkdir()
    archive = repo / 'visor/test-data/r5_regression.zip'
    manifest = json.loads((archive.with_suffix('.json')).read_text(encoding='utf-8'))
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest['archive_sha256']:
        raise ValueError('El paquete de regresión R5 no coincide con su hash')
    with zipfile.ZipFile(archive) as bundle:
        for name in ('6558_fixed', 'Pieza_Nueva_Detenida'):
            for member, target in [
                (f'material_pruebas/casos_usuario_r5/{name}.stl', sources / (name + '.stl')),
                (f'evidencias/reparador_integrado/{name}.json', results / (name + '.json')),
                (f'evidencias/reparador_integrado/{name}.reparado.stl', results / (name + '.reparado.stl')),
            ]:
                with target.open('xb') as output:
                    data = bundle.read(member)
                    if hashlib.sha256(data).hexdigest() != manifest['files'][member]['sha256']:
                        raise ValueError('Cambió un fixture histórico: ' + member)
                    output.write(data)
    env.setdefault('VISOR_CASOS_R5', str(sources))
    env.setdefault('VISOR_RESULTADOS_R5', str(results))
    raise SystemExit(subprocess.run(command, cwd=root, env=env, timeout=1800).returncode)
