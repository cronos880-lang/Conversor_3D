"""API real local: mismo HTML, conversión, evidencias y cancelación del árbol."""
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import pytest
import psutil
import trimesh
from fastapi.testclient import TestClient
import servidor


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(servidor, 'LOG_DIR', tmp_path)
    with servidor.JOBS_LOCK:
        servidor.JOBS.clear()
    with TestClient(servidor.app) as c:
        yield c


def stl_bytes(mesh):
    return mesh.export(file_type='stl')


def test_api_no_sella_abertura_y_guarda_diagnostico(client, tmp_path):
    mesh = trimesh.creation.box()
    mesh.update_faces(list(range(2, 12)))
    r = client.post('/convertir', files={'archivo': ('abierto.stl', stl_bytes(mesh))})
    assert r.status_code == 422 and 'Borde abierto' in r.json()['detail']
    reports = list(tmp_path.glob('*.entrada.json'))
    assert len(reports) == 1
    data = json.loads(reports[0].read_text())
    assert data['entrada']['aristas_1_cara'] > 0 and not data['reparado']


def test_api_union_asincrona_step_y_evidencias(client, tmp_path):
    a = trimesh.creation.box(extents=[10, 10, 10])
    b = a.copy().apply_translation([8, 0, 0])
    r = client.post('/iniciar-conversion', files={'archivo': ('union.stl', stl_bytes(trimesh.util.concatenate([a, b])))})
    assert r.status_code == 200
    job = r.json()['id']
    deadline = time.monotonic()+60
    while time.monotonic() < deadline:
        state = client.get('/estado-conversion/'+job).json()
        if state['estado'] != 'ejecutando':
            break
        time.sleep(.1)
    assert state['estado'] == 'terminado', state
    assert client.get('/descargar-conversion/'+job).content.startswith(b'ISO-10303-21;')
    import cadquery as cq
    solids = cq.importers.importStep(str(tmp_path/(job+'.step'))).solids().vals()
    assert len(solids) == 1 and solids[0].isValid()
    assert abs(solids[0].Volume()-1800) < .001
    for kind in ['informe', 'original', 'reparado']:
        assert client.get(f'/reparacion/{job}/{kind}').status_code == 200
    data = json.loads((tmp_path/(job+'.json')).read_text())
    assert data['preprocesamiento']['reparado'] and data['ram_pico_mb'] > 0


def test_html_conservado_y_rutas_restringidas(client):
    assert client.get('/').content == (servidor.ROOT/'Visor_STL_STEP.html').read_bytes()
    assert client.get('/reparacion/0123456789ab/otro').status_code == 404
    assert client.get('/reparacion/mal/original').status_code == 404


def test_api_conserva_stl_de_costura_saneada_con_su_hash(client,tmp_path):
    import hashlib
    from preprocesador_stl import preparar
    from test_saneamiento_verificado import costura
    source=tmp_path/'entrada.stl';source.write_text(trimesh.exchange.stl.export_stl_ascii(costura()),encoding='ascii')
    target=tmp_path/'salida.step';selected,report=preparar(source,target.with_suffix('.reparado.stl'))
    target.with_suffix('.entrada.json').write_text(json.dumps(report));meta={};ident='0123456789ab'
    servidor._guardar_preproceso(ident,target,source,meta)
    saved=client.get(meta['archivos_reparacion']['reparado'])
    assert saved.status_code==200 and saved.content==selected.read_bytes()
    assert hashlib.sha256(saved.content).hexdigest()==report['reparado_sha256']
    assert client.get(meta['archivos_reparacion']['original']).content==source.read_bytes()


def test_un_saneamiento_sin_certificado_no_se_ofrece_como_reparado(client,tmp_path):
    source=tmp_path/'entrada.stl';source.write_bytes(stl_bytes(trimesh.creation.box()));target=tmp_path/'salida.step'
    target.with_suffix('.reparado.saneado.stl').write_bytes(source.read_bytes())
    target.with_suffix('.entrada.json').write_text(json.dumps({'reparado':False,'error':'La reparación no se ha podido verificar'}))
    meta={};servidor._guardar_preproceso('0123456789ab',target,source,meta)
    assert 'reparado' not in meta['archivos_reparacion']
    assert client.get('/reparacion/0123456789ab/reparado').status_code==404


@pytest.mark.skipif(os.name == 'nt', reason='variante Windows taskkill requiere ejecución nativa Windows')
def test_nuevo_cancelacion_detiene_arbol_real():
    child = subprocess.Popen([sys.executable, '-c',
        'import subprocess,sys,time; p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);print(p.pid,flush=True);time.sleep(60)'],
        start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    descendant = int(child.stdout.readline())
    servidor._detener_arbol(child)
    child.communicate(timeout=5)
    assert child.poll() is not None
    # SIGKILL puede quedar pendiente hasta el siguiente turno del descendiente.
    # Exigir que todo el árbol cese en un plazo acotado, no en el mismo ciclo.
    deadline = time.monotonic()+3
    while time.monotonic() < deadline:
        try:
            process = psutil.Process(descendant)
            if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
                return
        except psutil.NoSuchProcess:
            return
        time.sleep(.01)
    process.kill()
    pytest.fail('La cancelación dejó un descendiente ejecutándose más de 3 segundos.')
