from pathlib import Path
import json,sys,pytest,trimesh
import perfeccion_calidad as p
from motor_v2 import _SalidaCad


def fixture_job(tmp_path,monkeypatch,faces=100,extra=None):
    source=tmp_path/'original.stl';source.write_bytes(trimesh.creation.box().export(file_type='stl'))
    destination=tmp_path/'modelo.step';baseline=b'STEP R11 conservado';destination.write_bytes(baseline)
    repaired=destination.with_suffix('.reparado.stl');repaired.write_bytes(source.read_bytes())
    payload={'ok':True,'resultado':{'calidad':{'caras_step':faces,'integridad_cad':{'brep_valido':True,'brep_exacto':True,'solidos':1},'autointerferencias_occ':False,'sin_objetos_sueltos_en_step':True,'inspeccion_densa':{'aceptado':True},'perfil_validacion':{'id':'precision'}},**(extra or {})},'preprocesamiento':dict(reparado=True,ruta_seleccionada='contactos_locales_exactos_verificados',original_sha256=p.sha(source),reparado_sha256=p.sha(repaired))}
    monkeypatch.setattr(sys,'argv',['motor',str(source),str(destination)])
    def legacy():print(json.dumps(payload));return 0
    return source,destination,baseline,legacy,payload


def test_rechazo_nuevo_conserva_bytes_resultado_r11(tmp_path,monkeypatch,capsys):
    source,dst,before,legacy,_=fixture_job(tmp_path,monkeypatch)
    original=source.read_bytes()
    monkeypatch.setattr(p,'mejorar',lambda *a:(_ for _ in ()).throw(ValueError('rechazo geométrico real')))
    assert p.ejecutar(legacy,_SalidaCad,None)==0
    row=json.loads(capsys.readouterr().out.splitlines()[-1])
    assert row['ok'] and row['mejora_superficies']['conservado_resultado_R11']
    assert dst.read_bytes()==before and source.read_bytes()==original


def test_entrada_cambiada_no_se_publica_como_conversion_correcta(tmp_path,monkeypatch,capsys):
    source,dst,before,legacy,_=fixture_job(tmp_path,monkeypatch)
    monkeypatch.setattr(p,'mejorar',lambda *a:(_ for _ in ()).throw(p.EntradaCambiada('entrada alterada')))
    assert p.ejecutar(legacy,_SalidaCad,None)==2
    assert json.loads(capsys.readouterr().out.splitlines()[-1])['ok'] is False
    assert dst.read_bytes()==before


def test_no_sustituye_reconstruccion_medida_ya_aprobada_por_r11(tmp_path,monkeypatch):
    source,dst,before,_,payload=fixture_job(tmp_path,monkeypatch,faces=239,extra={'reconstruccion_medida':{'aplicado':True}})
    monkeypatch.setattr(p,'ejecutar_subproceso',lambda *a:pytest.fail('No debe ejecutar otro núcleo'))
    assert p.mejorar(source,dst,payload,None,None) is None
    assert dst.read_bytes()==before


def test_no_reconstruye_resultado_compacto(tmp_path,monkeypatch):
    source,dst,before,_,payload=fixture_job(tmp_path,monkeypatch,faces=36)
    monkeypatch.setattr(p,'ejecutar_subproceso',lambda *a:pytest.fail('No debe ejecutar otro núcleo'))
    assert p.mejorar(source,dst,payload,None,None) is None
    assert dst.read_bytes()==before


def test_una_union_booleana_ya_aceptada_se_conserva(tmp_path,monkeypatch):
    source,dst,before,_,payload=fixture_job(tmp_path,monkeypatch)
    payload['preprocesamiento']['ruta_seleccionada']='union_booleana_verificada'
    monkeypatch.setattr(p,'ejecutar_subproceso',lambda *a:pytest.fail('No debe cambiar esta ruta'))
    assert p.mejorar(source,dst,payload,None,None) is None and dst.read_bytes()==before


def test_no_omite_la_mejora_por_lentitud_de_la_fase_anterior(tmp_path,monkeypatch):
    source,dst,before,_,payload=fixture_job(tmp_path,monkeypatch)
    def called(*a):raise ValueError('Se intentó la mejora con respaldo')
    monkeypatch.setattr(p,'ejecutar_subproceso',called)
    with pytest.raises(ValueError,match='intentó la mejora'):
        p.mejorar(source,dst,payload,None,None,tiempo_base_s=241)
    assert dst.read_bytes()==before


def test_reparacion_con_huella_incorrecta_se_rechaza_sin_tocar_archivos(tmp_path):
    source=tmp_path/'a.stl';source.write_bytes(b'original');dst=tmp_path/'a.step';prepared=dst.with_suffix('.reparado.stl');prepared.write_bytes(b'reparado')
    with pytest.raises(ValueError,match='vinculada'):p.entrada_preparada(source,dst,{'original_sha256':'otra','reparado_sha256':p.sha(prepared)})
    assert source.read_bytes()==b'original' and prepared.read_bytes()==b'reparado'


def test_informe_de_candidato_con_sha_falso_no_llega_al_validador(tmp_path,monkeypatch):
    source,dst,before,_,payload=fixture_job(tmp_path,monkeypatch)
    def fake_worker(script,args,timeout,log):
        if script.name=='preparar_calidad.py':
            original,prepared,destination,report=map(Path,args);destination.write_bytes(prepared.read_bytes())
            report.write_text(json.dumps(dict(ok=True,original_sha256=p.sha(original),entrada_reparada_sha256=p.sha(prepared),salida_sha256=p.sha(destination))))
            return 1
        active,base,candidate,report=map(Path,args);candidate.write_bytes(b'no es STEP certificado')
        report.write_text(json.dumps(dict(ok=True,original_sha256=p.sha(active),base_sha256=p.sha(base),step_sha256='no coincide')))
        return 1
    monkeypatch.setattr(p,'ejecutar_subproceso',fake_worker)
    with (tmp_path/'log').open('w') as log:
        with pytest.raises(ValueError,match='no coincide'):
            p.mejorar(source,dst,payload,lambda *a,**kw:pytest.fail('No debe validar un candidato cambiado'),log)
    assert dst.read_bytes()==before


def test_worker_no_puede_cambiar_original_y_publicar_otro_step(tmp_path,monkeypatch):
    source,dst,before,_,payload=fixture_job(tmp_path,monkeypatch)
    def fake_worker(script,args,timeout,log):
        if script.name=='preparar_calidad.py':
            original,prepared,destination,report=map(Path,args);destination.write_bytes(prepared.read_bytes())
            report.write_text(json.dumps(dict(ok=True,original_sha256=p.sha(original),entrada_reparada_sha256=p.sha(prepared),salida_sha256=p.sha(destination))))
            return 1
        active,base,candidate,report=map(Path,args);original=p.sha(active);candidate.write_bytes(b'candidato')
        report.write_text(json.dumps(dict(ok=True,original_sha256=original,base_sha256=p.sha(base),step_sha256=p.sha(candidate))))
        source.write_bytes(b'entrada cambiada');return 1
    monkeypatch.setattr(p,'ejecutar_subproceso',fake_worker)
    with (tmp_path/'log').open('w') as log:
        with pytest.raises(p.EntradaCambiada):p.mejorar(source,dst,payload,None,log)
    assert dst.read_bytes()==before
