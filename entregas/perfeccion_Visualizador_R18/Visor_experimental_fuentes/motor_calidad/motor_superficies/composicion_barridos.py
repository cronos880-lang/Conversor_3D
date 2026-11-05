"""Composición polinómica de C(u(t))+a*v(t), sin aproximar la curva espacial.

u es afín y cada tramo está dentro de un único tramo cúbico de C. Se suman
los polos Bézier de C y de a*v. La coherencia se contrasta contra OCC.
"""
import numpy as np
from OCP.Geom import Geom_SurfaceOfLinearExtrusion,Geom_TrimmedCurve,Geom_BSplineCurve
from OCP.GeomConvert import GeomConvert
from OCP.TColgp import TColgp_Array1OfPnt
from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
from OCP.gp import gp_Pnt

def componer(surface,parts):
 if not isinstance(surface,Geom_SurfaceOfLinearExtrusion):return None
 source=surface.BasisCurve();axis=np.array(surface.Direction().Coord());all_poles=[]
 for lo,hi,uv in parts:
  ua,ub=float(uv[0,0]),float(uv[-1,0])
  if np.max(abs(uv[:,0]-np.linspace(ua,ub,4)))>1e-12:return None
  if ua==ub:poles=np.repeat(np.array(source.Value(ua).Coord())[None,:],4,axis=0)
  else:
   if isinstance(source,Geom_BSplineCurve):
    piece=source.Copy();piece.Segment(min(ua,ub),max(ua,ub),1e-14)
   else:piece=GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(source,min(ua,ub),max(ua,ub)))
   if piece.IsRational() or piece.Degree()>3:return None
   piece.IncreaseDegree(3)
   if piece.NbPoles()!=4 or piece.NbKnots()!=2:return None
   poles=np.array([piece.Pole(i).Coord() for i in range(1,5)])
   if ub<ua:poles=poles[::-1].copy()
  poles=poles+uv[:,1,None]*axis
  if all_poles and np.linalg.norm(all_poles[-1]-poles[0])>1e-8:return None
  all_poles.extend(poles if not all_poles else poles[1:])
 P=TColgp_Array1OfPnt(1,len(all_poles));K=TColStd_Array1OfReal(1,len(parts)+1);M=TColStd_Array1OfInteger(1,len(parts)+1)
 for j,p in enumerate(all_poles,1):P.SetValue(j,gp_Pnt(*map(float,p)))
 for j,(lo,hi,uv) in enumerate(parts,1):K.SetValue(j,float(lo));M.SetValue(j,4 if j==1 else 3)
 K.SetValue(len(parts)+1,float(parts[-1][1]));M.SetValue(len(parts)+1,4)
 curve=Geom_BSplineCurve(P,K,M,3,False);maximum=0.
 for lo,hi,uv in parts:
  for t in np.linspace(0,1,17):
   q=uv[0]*(1-t)**3+3*uv[1]*(1-t)**2*t+3*uv[2]*(1-t)*t*t+uv[3]*t**3
   maximum=max(maximum,curve.Value(float(lo+(hi-lo)*t)).Distance(surface.Value(float(q[0]),float(q[1]))))
 if maximum>2e-8:raise ValueError('La composición polinómica no conserva el soporte: '+str(maximum))
 print('COMPOSICION POLINOMICA DE BARRIDO',len(parts),'tramos error',maximum,flush=True)
 return curve
