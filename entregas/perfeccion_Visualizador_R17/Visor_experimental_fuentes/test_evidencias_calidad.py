from pathlib import Path
import json,hashlib
from fastapi.testclient import TestClient
import servidor


def test_conserva_las_tres_evidencias_antes_de_borrar_temporal(tmp_path,monkeypatch):
    logs=tmp_path/'logs';logs.mkdir();monkeypatch.setattr(servidor,'LOG_DIR',logs)
    source=tmp_path/'original.stl';source.write_bytes(b'STL original');destination=tmp_path/'salida.step';meta={};job='a'*12
    destination.write_bytes(b'STEP candidato verificado');prepared=b'STL preparado certificado'
    digest=lambda b:hashlib.sha256(b).hexdigest()
    expected={'.calidad_nucleo.json':json.dumps(dict(ok=True,step_sha256=digest(destination.read_bytes()),original_sha256=digest(prepared))).encode(), '.calidad_original.json':json.dumps(dict(ok=True,step_sha256=digest(destination.read_bytes()))).encode(), '.calidad_preparado.stl':prepared}
    for suffix,data in expected.items():destination.with_suffix(suffix).write_bytes(data)
    servidor._guardar_preproceso(job,destination,source,meta)
    assert len(meta['evidencias_calidad'])==3
    for suffix,data in expected.items():assert (logs/(job+suffix)).read_bytes()==data
    assert source.read_bytes()==b'STL original'


def test_descargas_de_calidad_estan_limitadas_a_tipos_conocidos(tmp_path,monkeypatch):
    monkeypatch.setattr(servidor,'LOG_DIR',tmp_path);job='b'*12
    path=tmp_path/(job+'.calidad_original.json');path.write_bytes(b'{"ok":true}')
    with TestClient(servidor.app) as client:
        response=client.get('/reparacion/'+job+'/calidad_original')
        assert response.status_code==200 and response.content==path.read_bytes()
        assert client.get('/reparacion/'+job+'/archivo_arbitrario').status_code==404
        assert client.get('/reparacion/no_es_id/calidad_original').status_code==404


def test_no_presenta_pruebas_de_otro_step_como_calidad_del_archivo_publicado(tmp_path,monkeypatch):
    logs=tmp_path/'logs';logs.mkdir();monkeypatch.setattr(servidor,'LOG_DIR',logs)
    source=tmp_path/'a.stl';source.write_bytes(b'original');destination=tmp_path/'a.step';destination.write_bytes(b'STEP base conservado')
    destination.with_suffix('.calidad_nucleo.json').write_text(json.dumps(dict(ok=True,step_sha256=hashlib.sha256(b'candidato rechazado').hexdigest())))
    meta={};servidor._guardar_preproceso('c'*12,destination,source,meta)
    assert not meta.get('evidencias_calidad') and meta['evidencias_candidato_descartado']==['calidad_nucleo']
    assert not (logs/('c'*12+'.calidad_nucleo.json')).exists()
