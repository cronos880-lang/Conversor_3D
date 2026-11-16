"""Instalar la R21 completa desde cero, abrirla y convertir sin usar R20."""
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


def smoke(output, archive=None):
    import httpx
    import psutil
    import trimesh
    from build_r21_full import build, PREFIX
    output = Path(output).resolve()
    output.mkdir(exist_ok=False)
    if archive is None:
        archive = output / 'r21-full-candidate.zip'
        build(archive)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert all(n.startswith(PREFIX + '/') and '..' not in Path(n).parts for n in z.namelist())
        z.extractall(output / 'Instalacion independiente con espacios')
    root = output / 'Instalacion independiente con espacios' / PREFIX
    own_python = root / '.venv_r21' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    assert not own_python.exists()
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1',
           'CONVERSOR3D_SIN_PAUSA': '1', 'CONVERSOR3D_BASE_R20': str(output / 'R20_inexistente'),
           'CONVERSOR3D_DATA_DIR': str(output / 'datos_ajenos_no_usar'),
           'PYTHONPATH': str(output / 'codigo_ajeno_no_usar')}

    def command(action, *options):
        if os.name == 'nt':
            names = {'start': 'Iniciar_R21.bat', 'install': 'Reparar_Entorno_R21.bat',
                     'diagnose': 'Diagnostico_R21.bat'}
            return ['cmd.exe', '/d', '/c', names[action], *options]
        return [sys.executable, '-B', str(root / 'visor/scripts/manage_environment_r21.py'), action, *options]

    with (output / 'primera_apertura.log').open('xb') as log:
        process = subprocess.Popen(command('start', '--no-browser', '--port', str(port)),
            cwd=root, env=env, stdout=log, stderr=log, start_new_session=True)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=15, trust_env=False) as client:
                deadline = time.monotonic() + 1200
                while True:
                    try:
                        response = client.get('/version')
                        response.raise_for_status()
                        break
                    except (httpx.TransportError, httpx.HTTPStatusError):
                        if process.poll() is not None or time.monotonic() > deadline:
                            raise RuntimeError('La R21 completa no llegó a abrir; consultar primera_apertura.log')
                        time.sleep(.5)
                assert response.json()['compilacion'] == '21.0.0'
                assert own_python.is_file() and 'R21 experimental' in client.get('/').text
                source = trimesh.creation.box(extents=[4, 5, 6]).export(file_type='stl')
                hashes, nonces = [], []
                for i in range(2):
                    started = client.post('/iniciar-conversion',
                        files={'archivo': ('caja independiente.stl', source, 'application/octet-stream')},
                        data={'perfil': 'precision'})
                    started.raise_for_status()
                    job = started.json()['id']
                    deadline = time.monotonic() + 300
                    while True:
                        state = client.get('/estado-conversion/' + job).json()
                        if state['estado'] not in ('ejecutando', 'cancelando'):
                            break
                        if time.monotonic() > deadline:
                            raise TimeoutError('La conversión R21 completa no terminó')
                        time.sleep(.3)
                    assert state['estado'] == 'terminado', state
                    step = client.get('/descargar-conversion/' + job)
                    step.raise_for_status()
                    target = output / ('resultado_' + str(i) + '.step')
                    target.write_bytes(step.content)
                    sha = hashlib.sha256(step.content).hexdigest()
                    proof = client.get('/reparacion/' + job + '/r19_nucleo')
                    proof.raise_for_status()
                    cert = proof.json()
                    assert cert['ok'] and cert['step_sha256'] == sha
                    assert cert['material_original']['discrepancias'] == 0
                    assert len(cert['mallado_fino']['resoluciones']) == 3
                    assert cert['calidad']['integridad_cad']['tolerancia_max_mm'] <= 1e-7
                    hashes.append(sha)
                    nonces.append(cert['certificado']['nonce'])
                assert hashes[0] == hashes[1] and nonces[0] != nonces[1]
        finally:
            try:
                parent = psutil.Process(process.pid)
                for child in reversed(parent.children(recursive=True)):
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                parent.terminate()
                process.wait(timeout=15)
            except psutil.NoSuchProcess:
                pass
    code = ('import cadquery as cq,sys;from OCP.BRepCheck import BRepCheck_Analyzer;'
            'from pathlib import Path;assert Path(sys.prefix).name==".venv_r21";'
            's=cq.importers.importStep(sys.argv[1]).val();'
            'assert len(s.Solids())==1 and len(s.Faces())==6;'
            'assert BRepCheck_Analyzer(s.wrapped,True,False,True).IsValid();'
            'assert abs(s.Volume()-120)<1e-7;print(s.Volume())')
    subprocess.run([str(own_python), '-B', '-c', code, str(target)], env=env,
                   cwd=root, check=True, timeout=60)
    # Reproducir en este entorno desechable una extracción parcial de un paquete.
    subprocess.run([str(own_python), '-B', '-c',
        "from importlib.metadata import distribution;distribution('typing-inspection').locate_file('typing_inspection/introspection.py').unlink()"],
        cwd=root, env=env, check=True, timeout=30)
    with (output / 'reparacion.log').open('xb') as log:
        subprocess.run(command('install'), cwd=root, env=env, stdout=log, stderr=log, check=True, timeout=600)
    assert 'reparando' in (output / 'reparacion.log').read_text(encoding='utf-8', errors='replace')
    with (output / 'diagnostico.log').open('xb') as log:
        subprocess.run(command('diagnose', '--no-browser'), cwd=root, env=env,
                       stdout=log, stderr=log, check=True, timeout=300)
    diagnostic = json.loads(next((root / 'datos').glob('diagnostico_R21_*.json')).read_text(encoding='utf-8'))
    assert diagnostic['ok'] and diagnostic['separate_process_per_module']
    assert len(diagnostic['modules']) == 11
    assert not (output / 'R20_inexistente').exists() and not (output / 'datos_ajenos_no_usar').exists()
    report = {'ok': True, 'platform': sys.platform, 'archive_sha256': hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
              'first_start_installed_own_environment': True, 'requires_r20': False,
              'fresh_nonces': nonces[0] != nonces[1], 'step_hashes': hashes,
              'valid_reimported_step_own_environment': True, 'material_discrepancies': 0,
              'mesh_checks': 3, 'max_brep_mm': cert['calidad']['integridad_cad']['tolerancia_max_mm'],
              'repaired_missing_package_file': True, 'native_diagnostic': diagnostic}
    (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('R21 COMPLETA: INSTALACION PROPIA, ARRANQUE, DOS CONVERSIONES, REPARACION Y DIAGNOSTICO OK; SIN R20', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    try:
        smoke(args.output, args.archive)
    except Exception:
        for name in ('primera_apertura.log', 'reparacion.log', 'diagnostico.log'):
            path = args.output / name
            if path.is_file():
                print(name + ':\n' + path.read_text(encoding='utf-8', errors='replace')[-7000:], flush=True)
        raise
