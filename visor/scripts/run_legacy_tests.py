"""Ejecuta la batería congelada con sus cuatro raíces de importación explícitas."""
from pathlib import Path
import argparse
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
         root / 'motor_calidad/motor_superficies']
env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1',
       'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
       'PYTHONPATH': os.pathsep.join(map(str, paths))}
command = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
           '--junitxml=' + str(Path(args.xml).resolve())]
command.extend(str(path) for path in sorted(root.glob('test_*.py')))
# Dos pruebas históricas necesitan archivos que YA están en el ZIP R5.
# Se leen entradas concretas, sin extractall ni publicar copias de modelos.
with tempfile.TemporaryDirectory(prefix='visor legacy fixtures ') as temporary:
    fixtures = Path(temporary)
    sources, results = fixtures / 'sources', fixtures / 'results'
    sources.mkdir(); results.mkdir()
    archive = repo / 'entregas/perfeccion_Visualizador_R5/perfeccion_Visualizador_R5_EXPERIMENTAL.zip'
    with zipfile.ZipFile(archive) as bundle:
        for name in ('6558_fixed', 'Pieza_Nueva_Detenida'):
            for member, target in [
                (f'material_pruebas/casos_usuario_r5/{name}.stl', sources / (name + '.stl')),
                (f'evidencias/reparador_integrado/{name}.json', results / (name + '.json')),
                (f'evidencias/reparador_integrado/{name}.reparado.stl', results / (name + '.reparado.stl')),
            ]:
                with target.open('xb') as output:
                    output.write(bundle.read(member))
    env.setdefault('VISOR_CASOS_R5', str(sources))
    env.setdefault('VISOR_RESULTADOS_R5', str(results))
    raise SystemExit(subprocess.run(command, cwd=root, env=env, timeout=1800).returncode)
