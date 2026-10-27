from pathlib import Path
import io,json
from fastapi.testclient import TestClient
import arrancar,servidor
from version_programa import identidad,PUERTO,VERSION

def test_puerto_experimental_distinto_de_r7():
    assert PUERTO==8775

def test_pagina_e_identidad_son_de_esta_copia():
    with TestClient(servidor.app) as client:
        response=client.get('/');assert response.status_code==200
        assert VERSION in response.text and response.headers['cache-control']=='no-store'
        assert client.get('/version').json()==identidad(servidor.ROOT)

def test_otra_carpeta_o_compilacion_no_es_la_misma_instancia(tmp_path,monkeypatch):
    wrong=identidad(tmp_path)
    monkeypatch.setattr(arrancar,'version_local',lambda *a,**k:wrong)
    assert not arrancar.misma_instancia('http://127.0.0.1:8772')

def test_instancia_correcta_se_reconoce(monkeypatch):
    expected=identidad(arrancar.ROOT)
    monkeypatch.setattr(arrancar,'version_local',lambda *a,**k:expected)
    assert arrancar.misma_instancia('http://127.0.0.1:8772')

def test_descarga_identifica_curvas_reconstruidas_y_conserva_facetadas():
    assert servidor._metodo_resultado({'modo':'recuperacion_facetada'})=='recuperacion_facetada'
    assert servidor._metodo_resultado({'modo':'superficies','saneamiento_cad':{'metodo':'contornos_compatibles_ciclos_analiticos'}})=='contornos_compatibles'

def test_puerto_invalido_no_arranca_servidor(monkeypatch):
    monkeypatch.setenv('VISOR_PORT','mal')
    monkeypatch.setattr(arrancar.runpy,'run_path',lambda *a,**k:(_ for _ in ()).throw(AssertionError('No arrancar')))
    assert arrancar.main()==2

def test_un_servidor_distinto_en_el_puerto_no_abre_su_pagina(monkeypatch):
    from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
    import threading
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            data=json.dumps({'version':'R7'}).encode();self.send_response(200);self.end_headers();self.wfile.write(data)
        def log_message(self,*args):pass
    with ThreadingHTTPServer(('127.0.0.1',0),Handler) as server:
        thread=threading.Thread(target=server.serve_forever);thread.start()
        monkeypatch.setenv('VISOR_PORT',str(server.server_port));opened=[]
        monkeypatch.setattr(arrancar,'abrir',lambda url:opened.append(url))
        monkeypatch.setattr(arrancar.runpy,'run_path',lambda *a,**k:(_ for _ in ()).throw(AssertionError('No arrancar')))
        try:assert arrancar.main()==2 and not opened
        finally:server.shutdown();thread.join()

def test_lanzadores_windows_conservan_saltos_y_comillas():
    root=Path(__file__).parent
    for name in ['Iniciar.bat','Instalar_Entorno.bat']:
        data=(root/name).read_bytes();assert b'\r\n' in data and b'\\r\\n' not in data
        assert b'cd /d "%~dp0"' in data
    assert b'arrancar.py' in (root/'Iniciar.bat').read_bytes()
