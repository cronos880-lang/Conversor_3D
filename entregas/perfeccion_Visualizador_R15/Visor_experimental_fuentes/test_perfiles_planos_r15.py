import numpy as np,cadquery as cq,pytest
from perfiles_planos_r15 import sketch


def distance_segments(point,poly):
 D=np.diff(poly,axis=0);A=poly[:-1];t=np.clip(np.sum((point-A)*D,axis=1)/np.sum(D*D,axis=1),0,1)
 return np.linalg.norm(point-(A+t[:,None]*D),axis=1).min()


def test_sparse_meridian_cannot_hide_bowed_arc_between_vertices():
 # Vertex-only circle fitting used to accept an arc whose middle strayed far
 # from these long, nearly straight source segments.
 p=np.array([[0,0],[24,0],[26,2],[26.00001,5],[25.99998,16],[26,19],[0,19],[0,0]],float)
 wire,proof=sketch(p,lambda q:[q[0],q[1],0],tol=.002,mandatory=[p[1],p[-3]])
 for edge in wire.Edges():
  for t in np.linspace(0,1,101):
   q=np.array(edge.positionAt(float(t)).toTuple())[:2]
   assert distance_segments(q,p)<.00201


def test_source_cap_joints_stay_exactly_planar():
 p=np.array([[0,0],[24,0],[24.03,.0004],[24.1,.003],[25,1],[26,2],[26,19],[0,19]],float)
 wire,_=sketch(p,lambda q:[q[0],q[1],0],tol=.002,mandatory=[p[1],p[-2]])
 for joint in [p[1],p[-2]]:assert min(np.linalg.norm(np.array(v.Center().toTuple())[:2]-joint) for v in wire.Vertices())<1e-10
 # The radial cap itself is a native straight edge at its source height.
 assert any(e.geomType()=='LINE' and all(abs(v.Center().y)<1e-12 for v in e.Vertices()) and e.Length()>23 for e in wire.Edges())
