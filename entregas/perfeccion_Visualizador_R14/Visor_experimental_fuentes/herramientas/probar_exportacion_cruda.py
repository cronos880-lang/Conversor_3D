"""Run the small export regression suite using this copy's CAD environment."""
from pathlib import Path
import os
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
env = dict(os.environ)
paths = [str(root/'motor_calidad'), str(root/'motor_calidad/motor_superficies')]
if env.get('PYTHONPATH'):
    paths.append(env['PYTHONPATH'])
env['PYTHONPATH'] = os.pathsep.join(paths)
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    env[key] = '1'
raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest', '-q',
                                  'test_auditoria_step_crudo.py'], cwd=root, env=env))
