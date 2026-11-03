"""Geometric and fallback regressions for R14, independent of part filenames."""
from pathlib import Path
import copy,hashlib,json
import numpy as np
import pytest,trimesh,cadquery as cq
from operaciones_cilindricas_medidas import medir,proponer
from mejora_regional_aislada import comparar_calidad,elegible
from respaldo_conversion import guardar,recuperar


def test_native_identity_index_has_exact_is_same_semantics():
    from OCP.TopTools import TopTools_IndexedMapOfShape
    from OCP.TopoDS import TopoDS
    original=cq.Workplane('XY').box(2,3,4).val();faces=original.Faces();index=TopTools_IndexedMapOfShape()
    for face in faces:index.Add(face.wrapped)
    candidates=faces+[cq.Face(TopoDS.Face_s(faces[0].wrapped.Reversed())),faces[0].translate((.001,0,0)),cq.Workplane('XY').box(2,3,4).val().Faces()[0]]
    for face in candidates:
        assert index.Contains(face.wrapped)==any(face.wrapped.IsSame(other.wrapped) for other in faces)


def test_orienting_with_index_preserves_all_faces_edges_and_tolerances():
    from solidificacion_exacta import solidificar
    from OCP.BRep import BRep_Tool
    from OCP.TopTools import TopTools_IndexedMapOfShape
    source=cq.Workplane('XY').box(10,10,10).faces('>Z').workplane().hole(2).val()
    before=[(e.wrapped,BRep_Tool.Tolerance_s(e.wrapped)) for e in source.Edges()]
    result=cq.Shape.cast(solidificar(source.wrapped));index=TopTools_IndexedMapOfShape()
    for edge in result.Edges():index.Add(edge.wrapped)
    assert len(result.Faces())==len(source.Faces()) and result.isValid()
    assert all(index.Contains(edge) and BRep_Tool.Tolerance_s(edge)==tol for edge,tol in before)


def test_material_points_are_checked_against_original_not_only_euler():
    from verificar_original_calidad import comprobar_material_original
    original=trimesh.creation.box(extents=[2,2,2]);solid=cq.Workplane('XY').box(2,2,2).val()
    seen=[]
    proof=comprobar_material_original(original,solid,progress=lambda done,total:seen.append((done,total)))
    assert seen[0][0]==0 and seen[-1]==(proof['puntos'],proof['puntos'])
    assert proof['puntos']>2900 and proof['discrepancias']==0
    wrong=cq.Workplane('XY').box(2,2,2).faces('>Z').workplane().hole(.4).val()
    with pytest.raises(ValueError,match='material'):comprobar_material_original(original,wrong)


def cylinder_mesh(sections=96,radius=2.5):
    m=trimesh.creation.cylinder(radius=radius,height=6.,sections=sections)
    ids=np.flatnonzero(abs(m.face_normals[:,2])<1e-6)
    return m,dict(type='cylinder',faces=ids.tolist())


@pytest.mark.parametrize('rotated',[False,True])
def test_profile_is_source_backed_volume_preserving_and_rotation_invariant(rotated):
    mesh,p=cylinder_mesh()
    if rotated:
        mesh.apply_transform(trimesh.transformations.rotation_matrix(.71,[1,3,5]));mesh.apply_translation([145.,-83.,204.])
    before=mesh.triangles.copy();proof=medir(mesh,p)
    volume=np.pi*proof['radius']**2*(proof['hi']-proof['lo'])
    assert abs(volume-mesh.volume)<1e-8
    assert proof['radial_bound_mm']<=.008 and np.array_equal(mesh.triangles,before)
    assert abs(proof['nominal_fit_radius']-2.5)<1e-10


def test_no_rounding_a_coarse_polygon():
    mesh,p=cylinder_mesh(sections=24,radius=10.)
    with pytest.raises(ValueError):medir(mesh,p)


def test_no_reconstruction_across_a_functional_slot():
    mesh,p=cylinder_mesh();p['faces']=p['faces'][2:]
    with pytest.raises(ValueError):medir(mesh,p)


def test_taper_is_not_replaced_by_cylinder():
    mesh,p=cylinder_mesh();points=np.asarray(mesh.vertices).copy();points[points[:,2]>0,:2]*=1.01;mesh.vertices=points
    with pytest.raises(ValueError):medir(mesh,p)


def test_true_cad_boolean_replaces_facets_without_changing_volume():
    n=96;angles=np.linspace(0,2*np.pi,n,endpoint=False);points=np.c_[2.5*np.cos(angles),2.5*np.sin(angles),np.zeros(n)]
    outer=cq.Wire.makePolygon([cq.Vector(-5,-5,0),cq.Vector(5,-5,0),cq.Vector(5,5,0),cq.Vector(-5,5,0)],close=True)
    inner=cq.Wire.makePolygon([cq.Vector(*p) for p in points],close=True)
    source=cq.Solid.extrudeLinear(outer,[inner],cq.Vector(0,0,6))
    vv,ff=source.tessellate(.0001,.04);mesh=trimesh.Trimesh(np.array([p.toTuple() for p in vv]),np.asarray(ff),process=True)
    radial=np.linalg.norm(mesh.vertices[mesh.faces][:,:,:2],axis=2)
    walls=np.flatnonzero(np.max(abs(radial-2.5),axis=1)<1e-8)
    primitive=dict(type='cylinder',faces=walls.tolist())
    result,proof=proponer(source,mesh,[primitive])
    assert result.isValid() and len(result.Solids())==1
    assert len(result.Faces())<len(source.Faces())/2
    assert sum(f.geomType()=='CYLINDER' for f in result.Faces())==1
    assert abs(result.Volume()-source.Volume())<1e-7
    assert proof[0]['previous_solid_volume_preserved']


def reference_quality():return dict(desviacion_max_verificada_mm=.0034,caja_error_mm=.0005,volumen_error_pct=.024,caras_step=190)


@pytest.mark.parametrize('key,value',[('desviacion_max_verificada_mm',.035),('caja_error_mm',.001),('volumen_error_pct',.025),('caras_step',190)])
def test_rejects_a_prettier_but_worse_result(key,value):
    previous=reference_quality();candidate=dict(previous,caras_step=134);candidate[key]=value
    with pytest.raises(ValueError):comparar_calidad(previous,candidate)


def test_compact_known_good_conversions_are_preserved():
    for faces in [22,36,53]:
        assert elegible({'resultado':{'calidad':dict(caras_step=faces,tipos_caras={'GeomAbs_BSplineSurface':8})}}) is None


def test_repaired_cube_is_not_sent_to_boolean_reconstruction():
    assert elegible({'preprocesamiento':{'reparado':True},'resultado':{'calidad':dict(caras_step=1152,tipos_caras={'GeomAbs_Plane':1152})}}) is None


def test_r14_backup_preserves_previous_stage_and_is_preferred(tmp_path):
    source=tmp_path/'source.stl';source.write_bytes(b'bound source');step=tmp_path/'result.step';step.write_bytes(b'R12 validated')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    quality=dict(integridad_cad=dict(brep_valido=True,brep_exacto=True,solidos=1),autointerferencias_occ=False,sin_objetos_sueltos_en_step=True,inspeccion_densa={'aceptado':True},perfil_validacion={'id':'precision'})
    payload=dict(ok=True,resultado={'calidad':quality},preprocesamiento={'original_sha256':sha(source)})
    guardar(source,step,payload)
    step.write_bytes(b'R13 validated');guardar(source,step,payload,etapa='r14')
    step.write_bytes(b'failed proposal')
    assert recuperar(source,step,perfil='precision',motivo='worker timeout') is not None
    assert step.read_bytes()==b'R13 validated'
    assert (tmp_path/'result.step.base_validada.step').read_bytes()==b'R12 validated'
    assert recuperar(source,step,perfil='precision',motivo='cancel',cancelado=True) is None
