"""Imagen exacta de un segmento UV en un perfil polinómico extruido."""
import numpy as np
from OCP.Geom import Geom_SurfaceOfLinearExtrusion,Geom_BSplineCurve,Geom_TrimmedCurve,Geom_Line
from OCP.GeomConvert import GeomConvert
from OCP.gp import gp_Pnt,gp_Ax1,gp_Dir
from recorte_exacto import recortar

def segmento(surface,a,b):
 if not isinstance(surface,Geom_SurfaceOfLinearExtrusion):return None
 axis=np.array(surface.Direction().Coord());du=float(b[0]-a[0]);dv=float(b[1]-a[1])
 if abs(du)<1e-11:
  p=np.array(surface.Value(*map(float,a)).Coord());direction=axis if dv>0 else -axis
  return GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(Geom_Line(gp_Ax1(gp_Pnt(*map(float,p)),gp_Dir(*map(float,direction)))),0.,abs(dv)))
 lo,hi=sorted((float(a[0]),float(b[0])));basis=surface.BasisCurve()
 curve=recortar(basis,lo,hi)
 if curve.IsRational():raise ValueError('No se certifica el segmento racional extruido')
 # El parámetro UV puede tener un intervalo diminuto. Trabajar en [0,1]
 # evita restar dos números casi iguales al añadir la componente afín.
 from OCP.TColStd import TColStd_Array1OfReal
 normalized=TColStd_Array1OfReal(1,curve.NbKnots())
 for i in range(1,curve.NbKnots()+1):normalized.SetValue(i,(curve.Knot(i)-lo)/(hi-lo))
 curve.SetKnots(normalized)
 knots=[]
 for i in range(1,curve.NbKnots()+1):knots.extend([curve.Knot(i)]*curve.Multiplicity(i))
 degree=curve.Degree();vlow=float(a[1] if du>0 else b[1]);vhigh=float(b[1] if du>0 else a[1])
 for i in range(curve.NbPoles()):
  t=float(np.mean(knots[i+1:i+degree+1]));offset=(1-t)*vlow+t*vhigh
  point=np.array(curve.Pole(i+1).Coord())+axis*offset;curve.SetPole(i+1,gp_Pnt(*map(float,point)))
 maximum=max(curve.Value(float(t)).Distance(surface.Value(float(lo+(hi-lo)*t),float((1-t)*vlow+t*vhigh))) for t in np.linspace(0,1,129))
 if maximum>1e-10:raise ValueError('El segmento exacto extruido no conserva su soporte '+str(dict(error=maximum,du=du,dv=dv,intervalo=[lo,hi])))
 if du<0:curve.Reverse()
 return curve
