from pathlib import Path
import io,hashlib
import pytest,trimesh,cadquery as cq
from preprocesador_stl import preparar,ReparacionRechazada
from recuperacion_union_certificada import ejecutar

def entradas(tmp_path):
    a=trimesh.creation.box(extents=(2,2,2));b=a.copy();b.apply_translation((2,0,0))
    source=tmp_path/'original.stl';source.write_bytes(trimesh.util.concatenate([a,b]).export(file_type='stl'))
    prepared,proof=preparar(source,tmp_path/'preparado.stl')
    assert proof['ruta_seleccionada']=='union_booleana_verificada'
    return source,prepared

def test_union_regenerada_y_step_exacto_conservan_original(tmp_path):
    source,prepared=entradas(tmp_path);before=source.read_bytes();out=tmp_path/'resultado.step'
    result=ejecutar(source,prepared,out,io.StringIO())
    assert out.is_file() and source.read_bytes()==before
    assert result['modo']=='recuperacion_facetada'
    assert result['calidad']['union_original_verificada']['original_sha256']==hashlib.sha256(before).hexdigest()
    assert result['calidad']['integridad_cad']['brep_exacto']
    assert result['calidad']['autointerferencias_occ'] is False

def test_preparado_arbitrario_no_autoriza_tapar_huecos(tmp_path,monkeypatch):
    import recuperacion_numerica
    monkeypatch.setattr(recuperacion_numerica,'ejecutar_aislado',lambda *a:pytest.fail('No se debe ejecutar el CAD'))
    box=trimesh.creation.box();source=tmp_path/'abierto.stl';source.write_bytes(trimesh.Trimesh(box.vertices,box.faces[:-1],process=False).export(file_type='stl'))
    prepared=tmp_path/'cerrado.stl';prepared.write_bytes(box.export(file_type='stl'))
    with pytest.raises(ReparacionRechazada):ejecutar(source,prepared,tmp_path/'no.step',io.StringIO())
    assert not (tmp_path/'no.step').exists()

def test_union_preparada_distinta_rechazada_antes_del_cad(tmp_path,monkeypatch):
    import recuperacion_numerica
    source,prepared=entradas(tmp_path);prepared.write_bytes(trimesh.creation.box(extents=(8,8,8)).export(file_type='stl'))
    monkeypatch.setattr(recuperacion_numerica,'ejecutar_aislado',lambda *a:pytest.fail('No se debe ejecutar el CAD'))
    with pytest.raises(ValueError,match='no coincide'):ejecutar(source,prepared,tmp_path/'no.step',io.StringIO())

def test_original_cambiado_durante_cad_no_se_publica(tmp_path,monkeypatch):
    import recuperacion_numerica
    source,prepared=entradas(tmp_path)
    def fake(a,b,out,log):
        cq.Workplane('XY').box(4,2,2).val().exportStep(str(out));source.write_bytes(source.read_bytes()+b' ')
        return {'calidad':{},'modo':'recuperacion_facetada'}
    monkeypatch.setattr(recuperacion_numerica,'ejecutar_aislado',fake)
    with pytest.raises(ValueError,match='cambió'):ejecutar(source,prepared,tmp_path/'no.step',io.StringIO())
    assert not (tmp_path/'no.step').exists()

def test_enlace_duro_al_original_no_se_sobrescribe(tmp_path):
    import os
    source,prepared=entradas(tmp_path);before=source.read_bytes();out=tmp_path/'enlace.step';os.link(source,out)
    with pytest.raises(ValueError,match='distinta'):ejecutar(source,prepared,out,io.StringIO())
    assert source.read_bytes()==before
