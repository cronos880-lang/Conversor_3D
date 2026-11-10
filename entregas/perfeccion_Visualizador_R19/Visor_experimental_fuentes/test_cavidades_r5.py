import sys
from pathlib import Path
import numpy as np
import cadquery as cq
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Shell
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_OUT
from OCP.gp import gp_Pnt
sys.path.insert(0,str(Path(__file__).parent/'motor_superficies'))


def test_shells_internos_forman_un_solo_solido_con_cavidad():
    from meshfit_brep import _make_solid
    outer=cq.Workplane('XY').box(10,10,10).val();hole=cq.Workplane('XY').box(2,2,2).val()
    builder=BRep_Builder();shell=TopoDS_Shell();builder.MakeShell(shell)
    for face in outer.Faces():builder.Add(shell,face.wrapped)
    for face in hole.Faces():builder.Add(shell,face.wrapped.Reversed())
    shape=cq.Shape.cast(_make_solid(shell,cavidades_verificadas=True))
    assert shape.isValid() and len(shape.Solids())==1 and abs(shape.Volume()-992)<1e-8
    assert BRepClass3d_SolidClassifier(shape.wrapped,gp_Pnt(0,0,0),1e-7).State()==TopAbs_OUT


def test_detector_no_resuelda_una_entrada_exacta_verificada(tmp_path):
    import trimesh
    from meshfit_detect import detect
    mesh=trimesh.creation.box(extents=[1,1,1e-10]);before=mesh.vertices.copy()
    result,working=detect(str(tmp_path/'no_se_lee.stl'),mesh_input=mesh)
    assert len(working.vertices)==8 and len(working.faces)==12
    assert np.array_equal(working.vertices,before) and working.is_watertight
    assert np.all(np.linalg.norm(working.face_normals,axis=1)>.999)
