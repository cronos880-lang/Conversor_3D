"""Proyección sobre la CURVA medida, evitando óptimos de una superficie infinita."""
import numpy as np
from OCP.Geom import Geom_SurfaceOfLinearExtrusion
from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
from OCP.ShapeAnalysis import ShapeAnalysis_Surface
from OCP.gp import gp_Pnt,gp_Pnt2d
_CACHE={}
def uv_exacta(surface,points):
 key=id(surface)
 if key not in _CACHE:
  curve=surface.BasisCurve();axis=np.array(surface.Direction().Coord());origin=np.array(curve.Value(curve.FirstParameter()).Coord());_CACHE[key]=(surface,curve,axis,origin)
 _,curve,axis,origin=_CACHE[key];result=[]
 for p in points:
  target=p-axis*((p-origin)@axis);point=gp_Pnt(*map(float,target));projection=GeomAPI_ProjectPointOnCurve(point,curve);choices=[curve.FirstParameter(),curve.LastParameter()]
  if projection.NbPoints():choices.append(projection.LowerDistanceParameter())
  u=min(choices,key=lambda t:curve.Value(float(t)).Distance(point));base=np.array(curve.Value(float(u)).Coord());v=float((p-base)@axis);result.append((float(u),v))
 return np.asarray(result)
class AnalizadorBarrido:
 def __init__(self,surface):self.surface=surface
 def ValueOfUV(self,point,tolerance):return gp_Pnt2d(*map(float,uv_exacta(self.surface,np.asarray([point.Coord()]))[0]))
def analizador(surface):return AnalizadorBarrido(surface) if isinstance(surface,Geom_SurfaceOfLinearExtrusion) else ShapeAnalysis_Surface(surface)
def residual(surface,points,sas):
 if not isinstance(surface,Geom_SurfaceOfLinearExtrusion):return None
 uv=uv_exacta(surface,points);curve=surface.BasisCurve();axis=np.array(surface.Direction().Coord());P=np.array([curve.Value(float(u)).Coord() for u,v in uv]);D=np.array([curve.DN(float(u),1).Coord() for u,v in uv]);normal=np.cross(D,axis);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-30)
 return np.sum((points-P)*normal,axis=1),normal
