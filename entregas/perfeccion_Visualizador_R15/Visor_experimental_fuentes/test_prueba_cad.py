from pathlib import Path
import copy
import cadquery as cq
import pytest,trimesh
from prueba_cad import desde_trabajador,valida,sha,REVISION

@pytest.fixture
def box(tmp_path,monkeypatch):
    monkeypatch.setenv('VISOR_PERFIL','precision')
    step=tmp_path/'modelo.step';cq.exporters.export(cq.Workplane('XY').box(1,2,3).val(),str(step))
    mesh=trimesh.creation.box(extents=[1,2,3]);source=tmp_path/'original.stl';source.write_bytes(mesh.export(file_type='stl'))
    report={'ok':True,'revision_cad':REVISION,'brep_exacto':True,'step_sha256':sha(step),
            'calidad':{'interferencias_comprobadas_en_frio':True,'autointerferencias_occ':False,
                       'control_cad_reutilizado_por_sha256':False}}
    return source,mesh,step,report

def test_se_reutiliza_solo_sobre_los_mismos_bytes(box,tmp_path):
    _,_,step,report=box;proof=desde_trabajador(report,step)
    same=tmp_path/'copia.step';same.write_bytes(step.read_bytes());assert valida(proof,same)
    same.write_bytes(same.read_bytes()+b'\n');assert not valida(proof,same)

@pytest.mark.parametrize('field',['ok','brep_exacto','revision_cad'])
def test_resultado_incompleto_o_rechazado_no_acredita_cad(box,field):
    _,_,step,report=box;report[field]=False
    with pytest.raises(ValueError):desde_trabajador(report,step)

def test_no_se_encadenan_certificados_sin_nuevo_control(box):
    _,_,step,report=box;report['calidad']['control_cad_reutilizado_por_sha256']=True
    with pytest.raises(ValueError):desde_trabajador(report,step)

def test_se_miden_geometria_y_exactitud_sin_repetir_bop(box,monkeypatch):
    from motor_v2 import _calidad
    import saneamiento_cad
    source,mesh,step,report=box;proof=desde_trabajador(report,step)
    def fail(shape):raise AssertionError('No repetir el BOP ya verificado sobre estos bytes')
    monkeypatch.setattr(saneamiento_cad,'comprobar_interferencias',fail)
    quality=_calidad(source,step,mesh,prueba_cad=proof)
    assert quality['control_cad_reutilizado_por_sha256'] and quality['integridad_cad']['brep_exacto']
    assert quality['limites_precision_originales']['max_mm']==.060

def test_cambio_del_archivo_obliga_a_comprobar_bop_de_nuevo(box,monkeypatch):
    from motor_v2 import _calidad
    import saneamiento_cad
    source,mesh,step,report=box;proof=desde_trabajador(report,step);step.write_bytes(step.read_bytes()+b'\n')
    calls=[];monkeypatch.setattr(saneamiento_cad,'comprobar_interferencias',lambda shape:(calls.append(True) or True,0))
    quality=_calidad(source,step,mesh,prueba_cad=proof)
    assert calls and not quality['control_cad_reutilizado_por_sha256']

def test_prueba_cad_no_autoriza_cambiar_la_geometria_stl(box):
    from motor_v2 import _calidad
    source,mesh,step,report=box;proof=desde_trabajador(report,step)
    with pytest.raises(ValueError,match='volumen'):
        _calidad(source,step,trimesh.creation.box(extents=[10,10,10]),prueba_cad=proof)
