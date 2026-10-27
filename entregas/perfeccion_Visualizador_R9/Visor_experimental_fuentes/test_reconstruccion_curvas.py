"""Fronteras de aceptación: una comprobación OCC favorable no demuestra mallabilidad."""
from pathlib import Path
import json,hashlib
import pytest
import trimesh
import cadquery as cq
from reconstruccion_curvas import certificar_mallado,trabajador

LIMITS={'limites_validacion':{'desviacion_max_observada_mm':.060,'p95_superficie_max_mm':.020}}

def test_frontera_fina_de_cubo_cerrado(tmp_path):
    mesh=trimesh.creation.box(extents=(2,4,6));shape=cq.Workplane('XY').box(2,4,6).val()
    result=certificar_mallado(shape,mesh,tmp_path/'control.off',LIMITS)
    assert all(x['cerrado'] and x['orientado'] and x['euler']==2 for x in result['resoluciones'])
    assert all(x['intersecciones_cgal']==0 and x['superficie']['max_mm']<1e-8 for x in result['resoluciones'])

def test_cara_no_mallable_se_rechaza_aunque_occ_no_vea_interferencias(tmp_path):
    from saneamiento_cad import comprobar_interferencias
    fixture=Path(__file__).parent/'fixtures_cad/Bancada_104_NO_APROBADO.step'
    shape=cq.importers.importStep(str(fixture)).val()
    assert shape.isValid() and comprobar_interferencias(shape)==(True,0)
    # El rechazo debe ser la cara ausente, antes de cualquier comparación con el cubo.
    with pytest.raises(ValueError,match='cara que no se puede mallar'):
        certificar_mallado(shape,trimesh.creation.box(),tmp_path/'control.off',LIMITS)

def test_rescate_no_cierra_hueco_real_ni_modifica_entrada(tmp_path):
    mesh=trimesh.creation.box();mesh.update_faces(range(len(mesh.faces)-1))
    source=tmp_path/'abierto.stl';mesh.export(source);before=source.read_bytes()
    destination=tmp_path/'salida.step';report=tmp_path/'informe.json'
    assert trabajador(source,destination,report)==2
    assert not destination.exists() and source.read_bytes()==before
    assert not json.loads(report.read_text())['ok']

def test_conservacion_exige_cilindro_real_y_su_extension():
    import numpy as np
    from reconstruccion_curvas import comprobar_cilindros
    angles=np.linspace(0,2*np.pi,64,endpoint=False)
    points=np.vstack([np.column_stack([2*np.cos(angles),2*np.sin(angles),np.full(len(angles),z)]) for z in (0.,5.)])
    required=[{'puntos':points,'radio':2.,'eje':np.array([0.,0.,1.]),'centro':np.zeros(3),'max_entrada_mm':0.}]
    good=cq.Workplane('XY').circle(2).extrude(5).val()
    assert comprobar_cilindros(required,good)['preservados']==1
    truncated=cq.Workplane('XY').circle(2).extrude(2).val()
    with pytest.raises(ValueError,match='recorta o desplaza'):
        comprobar_cilindros(required,truncated)
    with pytest.raises(ValueError,match='pierde un cilindro'):
        comprobar_cilindros(required,cq.Workplane('XY').box(4,4,5).val())


def test_proyeccion_acotada_resuelve_borde_sin_extender_el_recorte():
    import numpy as np
    from reconstruccion_curvas import distancia_proyectada_acotada
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    shape=cq.Workplane('XY').circle(2).extrude(3).val()
    face=next(f for f in shape.Faces() if BRepAdaptor_Surface(f.wrapped).GetType()==GeomAbs_Cylinder)
    for theta in np.linspace(0,2*np.pi,33):
        p=[2*np.cos(theta),2*np.sin(theta),3.]
        assert distancia_proyectada_acotada(p,face)<1e-8
    assert not np.isfinite(distancia_proyectada_acotada([2,0,4],face))


def test_proyeccion_acotada_respeta_ventana_taladrada():
    import numpy as np
    from reconstruccion_curvas import distancia_proyectada_acotada
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    body=cq.Workplane('XY').circle(2).extrude(3).val()
    tool=cq.Workplane('YZ').center(0,1.5).circle(.4).extrude(5,both=True).val()
    shape=body.cut(tool)
    faces=[f for f in shape.Faces() if BRepAdaptor_Surface(f.wrapped).GetType()==GeomAbs_Cylinder
           and abs(BRepAdaptor_Surface(f.wrapped).Cylinder().Radius()-2)<1e-8]
    assert faces
    assert all(not np.isfinite(distancia_proyectada_acotada([2,0,1.5],face)) for face in faces)
    assert min(distancia_proyectada_acotada([2,0,.5],face) for face in faces)<1e-8


def test_proyeccion_acotada_con_cilindro_girado_y_desplazado():
    from reconstruccion_curvas import distancia_proyectada_acotada
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    shape=cq.Workplane('XY').circle(2).extrude(3).val().rotate((0,0,0),(1,0,0),90).translate((7,8,9))
    face=next(f for f in shape.Faces() if BRepAdaptor_Surface(f.wrapped).GetType()==GeomAbs_Cylinder)
    assert distancia_proyectada_acotada([9,6.5,9],face)<1e-8
