from pathlib import Path
from fastapi.testclient import TestClient
import servidor


def test_conserva_las_tres_evidencias_antes_de_borrar_temporal(tmp_path,monkeypatch):
    logs=tmp_path/'logs';logs.mkdir();monkeypatch.setattr(servidor,'LOG_DIR',logs)
    source=tmp_path/'original.stl';source.write_bytes(b'STL original');destination=tmp_path/'salida.step';meta={};job='a'*12
    expected={'.calidad_nucleo.json':b'{"ok":true}', '.calidad_original.json':b'{"original":true}', '.calidad_preparado.stl':b'STL preparado certificado'}
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
