"""Cilindros reales, rechazo de ambigüedades y conservación de la base CAD."""
from pathlib import Path
import io,sys
import numpy as np
import pytest
import trimesh
from cilindros_locales import confirmar,propuestas,reconstruir


def primitive(mesh,ids=None):
    if ids is None:ids=np.flatnonzero(abs(mesh.face_normals[:,2])<.1)
    return {'type':'cylinder','faces':ids,'axis':np.array([0.,0.,1.]),'point':np.zeros(3),'radius':1.}


def test_pared_completa_se_convierte_en_cilindro_sin_modificar_base(tmp_path):
    from brep_poliedrico_indices import construir
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    mesh=trimesh.creation.cylinder(radius=1,height=2,sections=64)
    vertices=mesh.vertices.copy();faces=mesh.faces.copy()
    base=construir(mesh);before=tmp_path/'antes.brep';after=tmp_path/'despues.brep';base.exportBrep(str(before))
    patches=propuestas(mesh,{'primitives':[primitive(mesh)]});rebuilt,records=reconstruir(base,patches)
    base.exportBrep(str(after))
    assert before.read_bytes()==after.read_bytes()
    assert np.array_equal(mesh.vertices,vertices) and np.array_equal(mesh.faces,faces)
    assert len(records)==1 and records[0]['cota_radial_mm']<=.008
    assert len(rebuilt.Faces())<len(base.Faces())/2
    assert any(BRepAdaptor_Surface(f.wrapped).GetType()==GeomAbs_Cylinder for f in rebuilt.Faces())
    assert BRepCheck_Analyzer(rebuilt.wrapped,True,False,True).IsValid()


def test_confirmacion_es_invariante_bajo_giro_y_traslacion():
    mesh=trimesh.creation.cylinder(radius=1.5,height=3,sections=96);p=primitive(mesh)
    expected=confirmar(mesh,p)
    matrix=trimesh.transformations.rotation_matrix(.73,[1,2,3]);matrix[:3,3]=[100,-40,9];mesh.apply_transform(matrix)
    actual=confirmar(mesh,p)
    assert abs(actual['radio']-expected['radio'])<1e-10
    assert abs(actual['cota_radial_mm']-expected['cota_radial_mm'])<1e-10
    assert abs(actual['hi']-actual['lo']-3)<1e-10


def test_no_redondea_hexagono_intencional():
    mesh=trimesh.creation.cylinder(radius=1,height=2,sections=6)
    with pytest.raises(ValueError):confirmar(mesh,primitive(mesh))


def test_no_supera_cota_radial_con_poligono_insuficiente():
    mesh=trimesh.creation.cylinder(radius=10,height=2,sections=24)
    with pytest.raises(ValueError,match='cota radial'):confirmar(mesh,primitive(mesh))


def test_una_ranura_abierta_no_se_reconstruye_como_anillo_completo():
    mesh=trimesh.creation.cylinder(radius=1,height=2,sections=64);p=primitive(mesh)
    ids=np.asarray(p['faces']);p['faces']=ids[4:]
    with pytest.raises(ValueError):confirmar(mesh,p)


def test_no_transformar_conicidad_real_en_cilindro():
    mesh=trimesh.creation.cylinder(radius=1,height=2,sections=64);p=primitive(mesh)
    top=mesh.vertices[:,2]>.5;mesh.vertices[top,:2]*=1.004
    with pytest.raises(ValueError):confirmar(mesh,p)


def test_banda_no_invade_una_pared_delgada():
    from brep_poliedrico_indices import construir
    mesh=trimesh.creation.annulus(r_min=.995,r_max=1,height=2,sections=64)
    radii=np.linalg.norm(mesh.triangles_center[:,:2],axis=1)
    ids=np.flatnonzero((abs(mesh.face_normals[:,2])<.1)&(radii>.996))
    patches=propuestas(mesh,{'primitives':[primitive(mesh,ids)]})
    assert patches
    with pytest.raises(ValueError,match='verificables'):reconstruir(construir(mesh),patches)


def test_reconstruccion_de_cavidad_cilindrica_preserva_el_vacio():
    from brep_poliedrico_indices import construir
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_OUT
    from OCP.gp import gp_Pnt
    box=trimesh.creation.box(extents=(6,6,6));void=trimesh.creation.cylinder(radius=1,height=2,sections=64);void.invert()
    mesh=trimesh.util.concatenate([box,void]);ids=np.flatnonzero((abs(mesh.face_normals[:,2])<.1)&(np.linalg.norm(mesh.triangles_center[:,:2],axis=1)<1.1))
    patches=propuestas(mesh,{'primitives':[primitive(mesh,ids)]})
    assert len(patches)==1 and patches[0]['vaciado_completo']
    rebuilt,records=reconstruir(construir(mesh),patches)
    assert records and len(rebuilt.Shells())==2
    check=BRepClass3d_SolidClassifier(rebuilt.wrapped);check.Perform(gp_Pnt(0,0,0),1e-9)
    assert check.State()==TopAbs_OUT


def test_trabajador_no_sobrescribe_una_entrada():
    from recuperacion_cilindros import trabajador
    # El rechazo por rutas precede a cualquier lectura o borrado de archivos.
    assert trabajador(Path('original.stl'),Path('base.step'),Path('original.stl'),Path('informe.json'))==2


def test_timeout_opcional_conserva_step_y_stl(tmp_path):
    import cadquery as cq
    from control_recursos import LimiteRecursos
    from recuperacion_cilindros import intentar
    source=tmp_path/'original.stl';trimesh.creation.box().export(source)
    base=tmp_path/'base.step';cq.Workplane('XY').box(1,1,1).val().exportStep(str(base))
    inputs=(source.read_bytes(),base.read_bytes())
    with pytest.raises(LimiteRecursos):intentar(source,base,trimesh.creation.box(),io.StringIO(),timeout=.01)
    assert inputs==(source.read_bytes(),base.read_bytes())


def test_rechazo_opcional_conserva_step_valido(tmp_path):
    import cadquery as cq
    from recuperacion_cilindros import intentar
    source=tmp_path/'original.stl';trimesh.creation.box().export(source)
    base=tmp_path/'base.step';cq.Workplane('XY').box(1,1,1).val().exportStep(str(base))
    inputs=(source.read_bytes(),base.read_bytes())
    with pytest.raises(ValueError):intentar(source,base,trimesh.creation.box(),io.StringIO(),timeout=60)
    assert inputs==(source.read_bytes(),base.read_bytes())
