"""Arrancar el ZIP ligero con un entorno R20 real y validar dos conversiones."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import zipfile


def smoke(output, base, archive=None):
    import httpx
    import cadquery as cq
    import trimesh
    from OCP.BRepCheck import BRepCheck_Analyzer
    from conversor3d.processes import stop_tree
    from build_r21_update import build, PREFIX
    output, base = Path(output).resolve(), Path(base).resolve()
    output.mkdir(exist_ok=False)
    if archive is None:
        archive = output / 'r21-candidate.zip'
        build(archive)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(output / 'R21 prueba con espacios')
    root = output / 'R21 prueba con espacios' / PREFIX
    baseline_version = base / 'visor/src/conversor3d/_version.py'
    version_hash = hashlib.sha256(baseline_version.read_bytes()).hexdigest()
    python = base / '.venv_r20' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        raise ValueError('Se necesita el entorno real de R20 para esta prueba')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    env = {key: value for key, value in os.environ.items()
           if key.upper() not in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV')}
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', CONVERSOR3D_SIN_PAUSA='1')
    with (output / 'server.log').open('xb') as log:
        command = [str(python), '-B', str(root / 'r21_launcher.py'), '--base-r20', str(base),
                   '--no-browser', '--port', str(port)]
        if os.name == 'nt':
            command = ['cmd.exe', '/d', '/c', 'Iniciar_R21.bat', '--base-r20', str(base),
                       '--no-browser', '--port', str(port)]
        process = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=log,
                                   start_new_session=True)
        try:
            url = f'http://127.0.0.1:{port}'
            with httpx.Client(base_url=url, timeout=30, trust_env=False) as client:
                deadline = time.monotonic() + 120
                while True:
                    try:
                        response = client.get('/version')
                        response.raise_for_status()
                        break
                    except (httpx.TransportError, httpx.HTTPStatusError):
                        if process.poll() is not None or time.monotonic() > deadline:
                            raise RuntimeError('R21 no arrancó desde el entorno R20; consultar server.log')
                        time.sleep(.2)
                assert response.json()['compilacion'] == '21.0.0'
                assert 'R21 experimental' in client.get('/').text
                assert client.get('/viewer/presentation.js').status_code == 200
                source = trimesh.creation.box(extents=[4, 5, 6]).export(file_type='stl')
                records, hashes, nonces = [], [], []
                for index in range(2):
                    started = time.monotonic()
                    response = client.post('/iniciar-conversion',
                        files={'archivo': ('caja con espacios.stl', source, 'application/octet-stream')},
                        data={'perfil': 'precision'})
                    response.raise_for_status()
                    job = response.json()['id']
                    deadline = time.monotonic() + 300
                    while True:
                        state = client.get('/estado-conversion/' + job).json()
                        if state['estado'] not in ('ejecutando', 'cancelando'):
                            break
                        if time.monotonic() > deadline:
                            raise TimeoutError('La conversión de prueba R21 no terminó')
                        time.sleep(.25)
                    assert state['estado'] == 'terminado', state
                    step = client.get('/descargar-conversion/' + job)
                    step.raise_for_status()
                    path = output / f'caja-{index}.step'
                    path.write_bytes(step.content)
                    shape = cq.importers.importStep(str(path)).val()
                    assert len(shape.Solids()) == 1 and BRepCheck_Analyzer(shape.wrapped, True, False, True).IsValid()
                    assert abs(shape.Volume() - 120) < 1e-7
                    hashes.append(hashlib.sha256(step.content).hexdigest())
                    # El servidor conserva los sidecars compatibles en su carpeta propia.
                    proof = client.get('/reparacion/' + job + '/r19_nucleo')
                    proof.raise_for_status()
                    certificate = proof.json()
                    assert certificate['ok'] and certificate['material_original']['discrepancias'] == 0
                    assert len(certificate['mallado_fino']['resoluciones']) == 3
                    assert certificate['step_sha256'] == hashes[-1]
                    nonces.append(certificate['certificado']['nonce'])
                    records.append({'seconds': time.monotonic() - started, 'state': state, 'faces': len(shape.Faces())})
                assert hashes[0] == hashes[1]
                assert len(nonces) == 2 and nonces[0] != nonces[1]
                assert hashlib.sha256(baseline_version.read_bytes()).hexdigest() == version_hash
                report = {'ok': True, 'platform': sys.platform, 'version': '21.0.0',
                          'base_r20_unchanged': True, 'step_hashes': hashes, 'records': records,
                          'fresh_nonces_observed': len(nonces) == 2 and nonces[0] != nonces[1]}
                (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
                print('R21 LIGERA: ARRANQUE, DOS CONVERSIONES Y STEP VALIDOS; R20 INTACTA', flush=True)
        finally:
            stop_tree(process)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-r20', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    options = parser.parse_args()
    smoke(options.output, options.base_r20, options.archive)
