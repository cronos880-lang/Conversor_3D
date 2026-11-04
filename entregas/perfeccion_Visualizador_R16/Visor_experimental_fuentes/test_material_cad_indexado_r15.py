"""Compare CAD index against unchanged native reference, without expected hints."""
import numpy as np
import cadquery as cq
import pytest
from material_cad_indexado import ClasificadorMaterial


def examples():
 box=cq.Workplane().box(10,8,6).val()
 yield 'box',box
 yield 'bore',cq.Workplane().box(10,8,6).faces('>Z').workplane().hole(3).val()
 yield 'cavity',box.cut(cq.Workplane().box(2,2,2).val())
 yield 'sphere',cq.Solid.makeSphere(4,angleDegrees1=-90)
 yield 'torus',cq.Solid.makeTorus(5,1)
 yield 'cone',cq.Solid.makeCone(4,1,8)
 yield 'thin',cq.Workplane().box(12,12,.00001).val()
 yield 'fillet',cq.Workplane().box(10,8,6).edges().fillet(.3).val()


@pytest.mark.parametrize('name,shape',list(examples()))
@pytest.mark.parametrize('rotation',[False,True])
def test_index_matches_native_reference(name,shape,rotation):
 if rotation:shape=shape.rotate((0,0,0),(1,3,7),37).translate((13,-27,6))
 b=shape.BoundingBox();lo=np.array([b.xmin,b.ymin,b.zmin]);hi=np.array([b.xmax,b.ymax,b.zmax]);span=np.maximum(hi-lo,1e-6)
 points=np.random.default_rng(15).uniform(lo-.15*span,hi+.15*span,(1000,3))
 boundary=np.array([v.Center().toTuple() for v in shape.Vertices()]+[f.Center().toTuple() for f in shape.Faces()])
 points=np.vstack([points,boundary]);index=ClasificadorMaterial(shape)
 expected=np.array([index.reference_state(p) for p in points]);actual=index.classify(points)
 assert np.array_equal(actual,expected)
 assert index.tol==1e-7


def test_ambiguous_hits_use_original_classifier(monkeypatch):
 index=ClasificadorMaterial(cq.Workplane().box(4,4,4).val());monkeypatch.setattr(index,'_ray',lambda p,d:None)
 assert index.classify([[0,0,0],[4,0,0]]).tolist()==[True,False]
 assert index.fallbacks==2


def test_expected_material_cannot_override_native_cad():
 index=ClasificadorMaterial(cq.Workplane().box(4,4,4).val())
 assert index.classify([[0,0,0],[4,0,0]],expected=[False,True]).tolist()==[True,False]
 assert index.fallbacks==2
