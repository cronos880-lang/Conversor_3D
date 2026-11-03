from pathlib import Path
import json,pytest,trimesh
from saneamiento_cad import IncoherenciaCAD

@pytest.mark.parametrize('etapa',[1.3,4.0])
def test_coherencia_rechazada_no_repite_ajustes_que_acumulan_memoria(tmp_path,monkeypatch,capsys,etapa):
    import motor_v2 as motor
    source=tmp_path/'pieza_nueva.stl';source.write_bytes(trimesh.creation.box().export(file_type='stl'));out=tmp_path/'no.step';calls=[]
    for key in ['VISOR_RUTA_RAPIDA','VISOR_RECUPERACION_CURVAS','VISOR_RECUPERACION_CAD','VISOR_CENTROID_GATE']:
        monkeypatch.setenv(key,'0' if key in ['VISOR_RUTA_RAPIDA','VISOR_CENTROID_GATE'] else '1')
    def reject(source,destination,log,**kwargs):
        angle=kwargs.get('flat_tol_deg',8.0);calls.append(angle)
        if angle==etapa:raise IncoherenciaCAD()
        raise ValueError('El motor B-Rep no ha reconstruido un sólido CAD válido.')
    monkeypatch.setattr(motor,'convertir',reject);monkeypatch.setattr(motor.sys,'argv',['motor_v2.py',str(source),str(out)])
    assert motor._main_cad()==2
    assert calls==([8.0,1.3] if etapa==1.3 else [8.0,1.3,4.0])
    assert not out.exists() and not json.loads(capsys.readouterr().out.splitlines()[-1])['ok']
