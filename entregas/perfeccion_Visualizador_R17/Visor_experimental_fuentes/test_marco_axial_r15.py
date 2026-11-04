from types import SimpleNamespace
import numpy as np,pytest
from construccion_axial_r15 import marco_axial

@pytest.mark.parametrize('noise',[0.,-8e-36,8e-36,1e-15,-1e-15])
def test_roundoff_cannot_select_another_meridian(noise):
 normals=np.tile([noise,1.,0.],(4,1));mesh=SimpleNamespace(face_normals=normals,area_faces=np.ones(4),area=4.)
 before=normals.copy();axis,u,v=marco_axial(mesh)
 assert np.array_equal(axis,[0.,1.,0.])
 assert np.array_equal(u,[1.,0.,0.])
 assert np.array_equal(v,[0.,0.,1.])
 assert np.array_equal(normals,before)


def test_actual_oblique_axis_keeps_full_source_precision():
 axis=np.array([.173456789123,.936725331123,.283756291123]);axis/=np.linalg.norm(axis)
 normals=np.array([axis,-axis,axis,-axis]);mesh=SimpleNamespace(face_normals=normals,area_faces=np.ones(4),area=4.)
 actual,u,v=marco_axial(mesh)
 assert np.linalg.norm(actual-axis)<1e-15
 assert np.linalg.norm(actual-np.round(axis,6))>1e-8
 R=np.column_stack([u,actual,v]);assert np.max(abs(R.T@R-np.eye(3)))<1e-14
 assert abs(np.linalg.det(R)-1)<1e-14
