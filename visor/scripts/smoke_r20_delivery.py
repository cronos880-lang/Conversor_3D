"""Instalar el ZIP R20 extraído y usar sus .bat reales en Windows con espacios."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
import zipfile

from build_r20 import PREFIX, REPO, build, release_identity


def smoke(output: Path, archive=None):
    if os.name != 'nt':
        raise ValueError('Esta comprobación de los lanzadores .bat requiere Windows')
    import httpx
    import trimesh
    from conversor3d.processes import stop_tree
    output = Path(output).resolve()
    output.mkdir(exist_ok=False)
    if archive is None:
        delivery = REPO / 'entregas/perfeccion_Visualizador_R20'
        for name in ('perfeccion_Visualizador_R20_EXPERIMENTAL_COMPLETA_CORREGIDA.zip',
                     'perfeccion_Visualizador_R20_EXPERIMENTAL_COMPLETA.zip'):
            published = delivery / name
            if published.is_file():
                with zipfile.ZipFile(published) as bundle:
                    identity = json.loads(bundle.read(PREFIX + '/R20_VERSION.json'))
                if identity == release_identity():
                    archive = published
                    break
        if archive is None:
            archive = output / 'candidato_R20.zip'
            build(archive)
    archive = Path(archive).resolve()
    with tempfile.TemporaryDirectory(prefix='R20 prueba con espacios ') as temporary:
        destination = Path(temporary)
        with zipfile.ZipFile(archive) as bundle:
            if bundle.testzip() is not None:
                raise ValueError('CRC del ZIP incorrecto')
            for item in bundle.namelist():
                relative = PurePosixPath(item)
                if relative.is_absolute() or '..' in relative.parts or relative.parts[0] != PREFIX:
                    raise ValueError('Ruta ajena en el ZIP: ' + item)
            bundle.extractall(destination)
        root = destination / PREFIX
        manifest = json.loads((root / 'R20_MANIFEST.json').read_text(encoding='utf-8'))
        if manifest['identity'] != release_identity():
            raise ValueError('La identidad del ZIP no coincide con R20')
        for relative, digest in manifest['files'].items():
            if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
                raise ValueError('Hash de la entrega incorrecto: ' + relative)
        env = {k: v for k, v in os.environ.items()
               if k.upper() not in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV')}
        env.update(CONVERSOR3D_SIN_PAUSA='1', PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        with (output / 'instalacion.log').open('wb') as log:
            subprocess.run(['cmd.exe', '/d', '/c', 'Instalar_Entorno_R20.bat'], cwd=root,
                           env=env, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
        own_python = root / '.venv_r20/Scripts/python.exe'
        if not own_python.is_file():
            raise ValueError('El instalador no preparó su entorno independiente')
        installed_log = (output / 'instalacion.log').read_text(encoding='utf-8', errors='replace')
        assert '[PAQUETE 1/' in installed_log and 'Paquetes verificados:' in installed_log
        # Reproducir una extracción interrumpida: versión instalada, archivo ausente.
        subprocess.run([str(own_python), '-B', '-c',
            "from importlib.metadata import distribution; distribution('typing-inspection').locate_file('typing_inspection/introspection.py').unlink()"],
            cwd=root, env=env, check=True, timeout=30)
        with (output / 'reparacion.log').open('wb') as log:
            subprocess.run(['cmd.exe', '/d', '/c', 'Reparar_Entorno_R20.bat'], cwd=root,
                           env=env, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=600)
        repaired_log = (output / 'reparacion.log').read_text(encoding='utf-8', errors='replace')
        assert 'typing-inspection' in repaired_log and 'incompleta' in repaired_log
        print('ZIP R20: REPARACIÓN DE PAQUETE INCOMPLETO OK', flush=True)
        with (output / 'diagnostico.log').open('wb') as log:
            subprocess.run(['cmd.exe', '/d', '/c', 'Diagnostico_R20.bat'], cwd=root,
                           env=env, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        diagnosis = json.loads((root / 'Diagnostico_Entorno_R20.json').read_text(encoding='utf-8'))
        if not diagnosis['ok'] or not diagnosis['payload_verified']:
            raise ValueError('El diagnóstico del paquete no es correcto')
        print('ZIP R20: INSTALACIÓN Y DIAGNÓSTICO OK', flush=True)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        env['CONVERSOR3D_PORT'] = str(port)
        with (output / 'arranque.log').open('wb') as log:
            process = subprocess.Popen(['cmd.exe', '/d', '/c', 'Iniciar_R20.bat', '--no-browser'],
                                       cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=30) as client:
                    deadline = time.monotonic() + 120
                    while True:
                        try:
                            version = client.get('/version')
                            version.raise_for_status()
                            break
                        except (httpx.TransportError, httpx.HTTPStatusError):
                            if process.poll() is not None or time.monotonic() > deadline:
                                raise RuntimeError('El lanzador R20 no arrancó el servidor')
                            time.sleep(.3)
                    assert version.json()['version'] == release_identity()['label']
                    assert release_identity()['label'] in client.get('/').text
                    source = trimesh.creation.box(extents=[4, 5, 6]).export(file_type='stl')
                    response = client.post('/iniciar-conversion',
                        files={'archivo': ('caja de prueba.stl', source, 'application/octet-stream')},
                        data={'perfil': 'precision'})
                    response.raise_for_status()
                    job = response.json()['id']
                    deadline = time.monotonic() + 300
                    while True:
                        state = client.get('/estado-conversion/' + job).json()
                        if state['estado'] not in ('ejecutando', 'cancelando'):
                            break
                        if time.monotonic() > deadline:
                            raise TimeoutError('La conversión desde el ZIP agotó su tiempo')
                        time.sleep(.3)
                    if state['estado'] != 'terminado':
                        raise ValueError('La conversión del ZIP no terminó: ' + json.dumps(state))
                    response = client.get('/descargar-conversion/' + job)
                    response.raise_for_status()
                    target = output / 'resultado.step'
                    target.write_bytes(response.content)
                    proof = client.get(f'/reparacion/{job}/r19_nucleo')
                    proof.raise_for_status()
                    certificate = proof.json()
                    if (not certificate['ok'] or certificate['material_original']['discrepancias']
                            or len(certificate['mallado_fino']['resoluciones']) != 3):
                        raise ValueError('Falta validación completa en la salida del ZIP')
                    assert certificate['step_sha256'] == hashlib.sha256(response.content).hexdigest()
                    code = ('import cadquery as cq,sys; from OCP.BRepCheck import BRepCheck_Analyzer; '
                            's=cq.importers.importStep(sys.argv[1]).val(); '
                            'assert len(s.Solids())==1 and BRepCheck_Analyzer(s.wrapped,True,False,True).IsValid(); '
                            'assert abs(s.Volume()-120)<1e-7; print(s.Volume())')
                    checked = subprocess.run([str(own_python), '-B', '-c', code, str(target)], cwd=root,
                        env=env, check=True, capture_output=True, text=True, encoding='utf-8', timeout=60)
                    report = {'ok': True, 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                              'identity': version.json(), 'new_venv': True, 'real_bat_launchers': True,
                              'extracted_with_spaces': True, 'volume_mm3': float(checked.stdout.strip()),
                              'certificate': certificate}
                    (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
                    print('ZIP R20: LANZADOR, CONVERSIÓN Y STEP CERTIFICADO OK', flush=True)
            finally:
                stop_tree(process)
        # R21 reutiliza este entorno R20 real: no se prepara otro runtime para la prueba.
        from conversor3d._version import RELEASE_NAME
        if RELEASE_NAME == 'R21':
            from smoke_r21_update import smoke as smoke_update
            smoke_update(output / 'r21-light', root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    try:
        smoke(args.output, args.archive)
    except Exception:
        for name in ('instalacion.log', 'reparacion.log', 'diagnostico.log', 'arranque.log'):
            log = args.output / name
            if log.is_file():
                print(name + ':\n' + log.read_text(encoding='utf-8', errors='replace')[-5000:], flush=True)
        raise
