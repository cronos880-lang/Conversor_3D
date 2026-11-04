import numpy as np,trimesh,pytest
from normalizacion_referencia import normalizar_cierre

def costura_redondeo(epsilon=2e-10):
    mesh=trimesh.creation.box();face=mesh.faces[0];index=int(face[0]);vertices=np.vstack((mesh.vertices,mesh.vertices[index]+[epsilon,0,0]));faces=mesh.faces.copy();faces[0,0]=len(vertices)-1
    return trimesh.Trimesh(vertices,faces,process=False)

def test_redondeo_heredado_preserva_todas_las_facetas_y_original():
    mesh=costura_redondeo();before=mesh.triangles.copy();assert not mesh.is_watertight
    normalized,proof=normalizar_cierre(mesh)
    assert normalized.is_watertight and normalized.is_winding_consistent
    assert len(normalized.faces)==len(mesh.faces) and np.array_equal(mesh.triangles,before)
    assert proof['lectura_heredada']['max_movimiento_coordenada_mm']<=trimesh.constants.tol.merge
    assert proof['lectura_heredada']['caras_eliminadas']==0

def test_no_reune_un_hueco_mayor_que_el_redondeo_heredado():
    with pytest.raises(ValueError):normalizar_cierre(costura_redondeo(1e-4))

def test_no_tapa_un_agujero_real():
    mesh=trimesh.creation.box();mesh.update_faces(np.arange(1,len(mesh.faces)))
    with pytest.raises(ValueError,match='no se permite tapar'):normalizar_cierre(mesh)

def test_recuperacion_reproduce_referencia_y_preparado_ambos_con_costura(tmp_path):
    from recuperacion_numerica import reconstruir
    import json
    source=tmp_path/'original.stl';source.write_text(trimesh.exchange.stl.export_stl_ascii(costura_redondeo()),encoding='ascii');before=source.read_bytes()
    out=tmp_path/'out.step';report=tmp_path/'out.json'
    assert reconstruir(source,source,out,report)==0
    result=json.loads(report.read_text());assert result['ok'] and source.read_bytes()==before
    assert result['normalizacion_preparado']['lectura_heredada']['aplicado']
    assert result['normalizacion_referencia_material']['lectura_heredada']['aplicado']
    assert result['resultado']['calidad']['integridad_cad']['brep_exacto']

def test_sin_cilindros_confirmados_no_construye_un_cad_destinado_al_rechazo(tmp_path,monkeypatch):
    from pathlib import Path
    import json
    monkeypatch.syspath_prepend(str(Path(__file__).parent/'motor_superficies'))
    import meshfit_step
    monkeypatch.setattr(meshfit_step,'export_step',lambda *a,**k:pytest.fail('No construir un CAD que no puede superar el control de cilindros'))
    from reconstruccion_curvas import trabajador
    source=tmp_path/'plana.stl';source.write_bytes(trimesh.creation.box().export(file_type='stl'))
    out=tmp_path/'no.step';report=tmp_path/'no.json'
    assert trabajador(source,out,report)==2
    result=json.loads(report.read_text());assert not result['ok'] and 'No se han confirmado cilindros' in result['error']
    assert not out.exists()
