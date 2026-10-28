"""Imagen exacta de un segmento UV en un perfil polinómico extruido."""
import numpy as np
from OCP.Geom import Geom_SurfaceOfLinearExtrusion,Geom_TrimmedCurve,Geom_Line
from OCP.GeomConvert import GeomConvert
from OCP.gp import gp_Pnt,gp_Ax1,gp_Dir

def segmento(surface,a,b):
 if not isinstance(surface,Geom_SurfaceOfLinearExtrusion):return None
 axis=np.array(surface.Direction().Coord());du=float(b[0]-a[0]);dv=float(b[1]-a[1])
 if abs(du)<1e-11:
  p=np.array(surface.Value(*map(float,a)).Coord());direction=axis if dv>0 else -axis
  return GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(Geom_Line(gp_Ax1(gp_Pnt(*map(float,p)),gp_Dir(*map(float,direction)))),0.,abs(dv)))
 lo,hi=sorted((float(a[0]),float(b[0])));curve=GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(surface.BasisCurve(),lo,hi))
 if curve.IsRational():raise ValueError('No se certifica el segmento racional extruido')
 knots=[]
 for i in range(1,curve.NbKnots()+1):knots.extend([curve.Knot(i)]*curve.Multiplicity(i))
 degree=curve.Degree()
 for i in range(curve.NbPoles()):
  parameter=float(np.mean(knots[i+1:i+degree+1]));offset=a[1]+dv*(parameter-a[0])/du
  point=np.array(curve.Pole(i+1).Coord())+axis*offset;curve.SetPole(i+1,gp_Pnt(*map(float,point)))
 maximum=max(curve.Value(float(u)).Distance(surface.Value(float(u),float(a[1]+dv*(u-a[0])/du))) for u in np.linspace(lo,hi,129))
 if maximum>1e-10:raise ValueError('El segmento exacto extruido no conserva su soporte')
 if du<0:curve.Reverse()
 return curve
