"""Cuatro lados compuestos sin cambiar las curvas 3D ni rellenar agujeros."""
from recorte_exacto import recortar
import numpy as np
from OCP.Geom import Geom_TrimmedCurve
from OCP.GeomConvert import GeomConvert,GeomConvert_CompCurveToBSplineCurve

def cuatro_lados(edges,*,projector=None):
 if len(edges)<5 or len(edges)>512:return None
 curves=[recortar(c,float(a),float(b)) for c,a,b in edges]
 for i,c in enumerate(curves):
  following=curves[(i+1)%len(curves)]
  if c.Value(c.LastParameter()).Distance(following.Value(following.FirstParameter()))>1e-7:return None
 scores=[]
 uv_endpoints=None
 if projector is not None:
  points=np.array([c.Value(c.FirstParameter()).Coord() for c in curves])
  try:
   uv=np.array([projector(p)[1] for p in points],float)
   span=np.ptp(uv,axis=0)
   if not np.isfinite(uv).all() or np.min(span)<1e-12:return None
   uv_endpoints=(uv-uv.min(0))/span
  except (ValueError,RuntimeError):return None
 for i,c in enumerate(curves):
  if uv_endpoints is not None:
   a=uv_endpoints[i]-uv_endpoints[i-1];b=uv_endpoints[(i+1)%len(curves)]-uv_endpoints[i]
  else:
   before=curves[i-1];a=np.array(before.DN(before.LastParameter(),1).Coord());b=np.array(c.DN(c.FirstParameter(),1).Coord())
  na=np.linalg.norm(a);nb=np.linalg.norm(b)
  if min(na,nb)<1e-14:return None
  scores.append(1-float(np.clip(a@b/na/nb,-1,1)))
 corners=sorted(np.argsort(-np.asarray(scores))[:4]);out=[]
 for j,start in enumerate(corners):
  end=corners[(j+1)%4];indices=[];k=int(start)
  while True:
   indices.append(k);k=(k+1)%len(curves)
   if k==end:break
  join=GeomConvert_CompCurveToBSplineCurve(curves[indices[0]])
  for k in indices[1:]:
   if not join.Add(curves[k],1e-10,True,True,0):return None
  out.append(join.BSplineCurve())
 return out
