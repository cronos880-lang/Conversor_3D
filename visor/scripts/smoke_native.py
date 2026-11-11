"""Instalación nativa, arranque HTTP, conversión real y lectura STEP en Windows/Linux."""
from pathlib import Path
import argparse
import importlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time

repo = Path(__file__).resolve().parents[2]
frozen = repo / 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes'


def smoke(output: Path, development=False):
    import httpx
    import cadquery as cq
    import trimesh
    from OCP.BRepCheck import BRepCheck_Analyzer
    if sys.version_info[:2] != (3, 12) or platform.architecture()[0] != '64bit':
        raise ValueError('Se requiere Python 3.12 de 64 bits')
    for module in ('OCP', 'vtk', 'CGAL', 'gpytoolbox', 'igl'):
        importlib.import_module(module)
        print('IMPORT OK', module, flush=True)
    output.mkdir(exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='visor prueba nativa ') as temporary:
        root = Path(temporary) / 'aplicacion'
        shutil.copytree(frozen, root, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '.venv', 'Registros_Conversion'))
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        env = {**os.environ, 'CONVERSOR3D_DATA_DIR': str(output.resolve() / 'logs'), 'VISOR_PORT': str(port), 'VISOR_NO_ABRIR_NAVEGADOR': '1',
               'PYTHONDONTWRITEBYTECODE': '1', 'OPENBLAS_NUM_THREADS': '1',
               'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
        command = [sys.executable, str(root / 'arrancar.py'), '--entorno-listo']
        if development:
            command = [sys.executable, '-m', 'conversor3d', 'serve', '--port', str(port), '--no-browser']
            env['PYTHONPATH'] = str(repo / 'visor/src')
        with (output / 'server.log').open('xb') as log:
            process = subprocess.Popen(command, cwd=repo if development else root, env=env, stdout=log, stderr=log)
            try:
                url = f'http://127.0.0.1:{port}'
                with httpx.Client(base_url=url, timeout=30, trust_env=False) as client:
                    deadline = time.monotonic() + 60
                    while True:
                        try:
                            version = client.get('/version'); version.raise_for_status()
                            break
                        except (httpx.TransportError, httpx.HTTPStatusError):
                            if time.monotonic() > deadline or process.poll() is not None:
                                raise RuntimeError('El servidor nativo no arrancó')
                            time.sleep(.2)
                    page = client.get('/')
                    assert page.status_code == 200
                    if development:
                        from conversor3d._version import APPLICATION_LABEL
                        assert APPLICATION_LABEL in page.text
                        assert version.json()['version'] == APPLICATION_LABEL
                        assert client.get('/version', headers={'Host': 'foreign.invalid'}).status_code == 400
                        assert client.post('/iniciar-conversion', headers={'Origin': 'https://foreign.invalid'},
                                           content=b'unparsed body').status_code == 403
                    source = trimesh.creation.box(extents=[4, 5, 6]).export(file_type='stl')
                    response = client.post('/iniciar-conversion',
                                           files={'archivo': ('caja con espacios.stl', source, 'application/octet-stream')},
                                           data={'perfil': 'precision'})
                    response.raise_for_status(); job = response.json()['id']
                    deadline = time.monotonic() + 300
                    while True:
                        state = client.get('/estado-conversion/' + job).json()
                        if state['estado'] not in ('ejecutando', 'cancelando'):
                            break
                        if time.monotonic() > deadline:
                            client.post('/cancelar-conversion/' + job)
                            raise TimeoutError('Conversión nativa agotó su tiempo')
                        time.sleep(.3)
                    if state['estado'] != 'terminado':
                        raise RuntimeError(json.dumps(state))
                    response = client.get('/descargar-conversion/' + job)
                    response.raise_for_status()
                    step = output / 'resultado.step'; step.write_bytes(response.content)
                    shape = cq.importers.importStep(str(step)).val()
                    assert len(shape.Solids()) == 1
                    assert BRepCheck_Analyzer(shape.wrapped, True, False, True).IsValid()
                    assert abs(shape.Volume() - 120.) < 1e-7
                    report = {'platform': platform.platform(), 'python': sys.version,
                              'version': version.json(), 'state': state, 'volume_mm3': shape.Volume(),
                              'faces': len(shape.Faces()), 'exact_valid': True}
                    (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
                    if development:
                        proof = client.get(f'/reparacion/{job}/r19_nucleo')
                        proof.raise_for_status()
                        assert proof.json()['ok'] is True
                        assert proof.json()['development_sha256']
                    print('CONVERSION NATIVA OK', shape.Volume(), flush=True)
            finally:
                if process.poll() is None:
                    import psutil
                    for child in psutil.Process(process.pid).children(recursive=True):
                        try:child.kill()
                        except psutil.NoSuchProcess:pass
                    process.kill(); process.wait(timeout=15)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--development', action='store_true')
    args = p.parse_args()
    smoke(args.output, args.development)
