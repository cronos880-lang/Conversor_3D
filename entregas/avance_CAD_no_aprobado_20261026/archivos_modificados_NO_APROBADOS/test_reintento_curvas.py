"""No repetir rechazos idénticos; no confundirlos con otro perfil o fuente."""
from pathlib import Path
from types import SimpleNamespace
import hashlib,io,json
import pytest
import reconstruccion_curvas as rc

@pytest.fixture
def runner(tmp_path,monkeypatch):
    import calidad_topologica,control_recursos
    rc._RECHAZOS_TRABAJADOR.clear()
    for flag in rc._FLAGS_RECONSTRUCCION:monkeypatch.delenv(flag,raising=False)
    monkeypatch.setenv('VISOR_PERFIL','precision')
    source=tmp_path/'a.stl';source.write_bytes(b'fuente exacta A')
    destination=tmp_path/'original.step';destination.write_bytes(b'candidato anterior')
    mesh=SimpleNamespace(faces=[0],is_watertight=True,is_winding_consistent=True)
    monkeypatch.setattr(calidad_topologica,'leer_solido_step_estricto',lambda p:object())
    monkeypatch.setattr(rc,'inventario',lambda s:{'cilindros':1})
    calls=[];mode={'ok':False}
    class Process:
        returncode=2
        def __enter__(self):return self
        def __exit__(self,*args):return False
    def popen(args,**kwargs):
        calls.append(args);proc=Process();report=Path(args[-1]);candidate=Path(args[-2]);src=Path(args[-3]);data={'ok':False,'error':'fallo geométrico reproducible'}
        if mode['ok']:
            candidate.write_bytes(b'nuevo candidato');proc.returncode=0
            data={'ok':True,'original_sha256':rc._sha(src),'step_sha256':rc._sha(candidate)}
        report.write_text(json.dumps(data));return proc
    monkeypatch.setattr(rc.subprocess,'Popen',popen)
    monkeypatch.setattr(control_recursos,'comunicar_vigilado',lambda *a,**k:('',None,1.))
    def invoke(src=source):
        def validar(*args):raise ValueError('rechazo del validador externo')
        with pytest.raises(ValueError):rc.intentar_refinar(src,destination,mesh,validar,io.StringIO())
    return source,invoke,calls,mode

def test_misma_fuente_copiada_no_repite_trabajador(runner,tmp_path):
    source,run,calls,_=runner;run();copy=tmp_path/'copia.stl';copy.write_bytes(source.read_bytes());run(copy)
    assert len(calls)==1

def test_fuente_cambiada_se_vuelve_a_probar(runner):
    source,run,calls,_=runner;run();source.write_bytes(b'fuente exacta B');run()
    assert len(calls)==2

def test_otro_perfil_no_hereda_rechazo(runner,monkeypatch):
    _,run,calls,_=runner;run();monkeypatch.setenv('VISOR_PERFIL','impresion');run()
    assert len(calls)==2

def test_parametros_distintos_no_heredan_rechazo(runner,monkeypatch):
    _,run,calls,_=runner;run();monkeypatch.setenv('VISOR_CENTROID_GATE','1');run()
    assert len(calls)==2

def test_rechazo_del_validador_no_se_guarda_como_fallo_del_trabajador(runner):
    _,run,calls,mode=runner;mode['ok']=True;run();run()
    assert len(calls)==2
