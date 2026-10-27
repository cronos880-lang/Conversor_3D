from pathlib import Path
import numpy as np
import pytest,trimesh


def geometria(tmp_path):
    import cadquery as cq
    outer=cq.Solid.makeBox(10,10,10,cq.Vector(-5,-5,-5))
    inner=cq.Solid.makeBox(1,1,1,cq.Vector(-.5,-.5,-.5))
    mesh=trimesh.creation.box(extents=[10]*3)
    cavity=trimesh.creation.box(extents=[1]*3);cavity.invert()
    reference=trimesh.util.concatenate([mesh,cavity])
    path=tmp_path/'original.stl';path.write_text(trimesh.exchange.stl.export_stl_ascii(reference))
    return outer,outer.cut(inner),reference,path


def test_cavidad_correcta_pasa_la_validacion_completa(tmp_path,monkeypatch):
    monkeypatch.setenv('VISOR_PERFIL','precision')
    from motor_v2 import _calidad
    from validacion_local import _distancias_cad
    _,solid,mesh,source=geometria(tmp_path)
    assert len(solid.Shells())==2
    d=_distancias_cad(solid,np.array([[.5,0,0],[5,0,0]]))
    assert max(d)<1e-10
    target=tmp_path/'cavidad.step';solid.exportStep(str(target))
    report=_calidad(source,target,mesh,control_avanzado=True)
    assert report['autointerferencias_occ'] is False
    assert report['inspeccion_densa']['aceptado']


def test_no_acepta_rellenar_cavidad_aunque_el_volumen_este_en_tolerancia(tmp_path,monkeypatch):
    monkeypatch.setenv('VISOR_PERFIL','precision')
    from motor_v2 import _calidad
    outer,_,mesh,source=geometria(tmp_path)
    assert abs(outer.Volume()-mesh.volume)/mesh.volume<.005
    target=tmp_path/'rellenado.step';outer.exportStep(str(target))
    with pytest.raises(ValueError,match='fidelidad superficial'):
        _calidad(source,target,mesh,control_avanzado=True)
