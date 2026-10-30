"""Proyección de una esquina al corte afín exacto plano/extrusión."""
import numpy as np
from OCP.Geom import Geom_Plane,Geom_SurfaceOfLinearExtrusion
from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
from OCP.gp import gp_Pnt

def proponer(surfaces,point):
 planes=[s for s in surfaces if isinstance(s,Geom_Plane)];sweeps=[s for s in surfaces if isinstance(s,Geom_SurfaceOfLinearExtrusion)]
 if len(surfaces)!=2 or len(planes)!=1 or len(sweeps)!=1:return []
 plane,surface=planes[0],sweeps[0];axis=np.array(surface.Direction().Coord());n=np.array(plane.Axis().Direction().Coord());q=np.array(plane.Location().Coord());dot=float(n@axis)
 if abs(dot)<1e-10:return []
 source=surface.BasisCurve()
 if not hasattr(source,'NbPoles'):return []
 curve=source.Copy()
 for j in range(1,curve.NbPoles()+1):
  p=np.array(curve.Pole(j).Coord());p+=axis*float(n@(q-p)/dot);curve.SetPole(j,gp_Pnt(*map(float,p)))
 projection=GeomAPI_ProjectPointOnCurve(gp_Pnt(*map(float,point)),curve);parameters=[curve.FirstParameter(),curve.LastParameter()]
 if projection.NbPoints():parameters.extend(projection.Parameter(i) for i in range(1,projection.NbPoints()+1))
 result=[]
 for u in parameters:
  p=np.array(source.Value(float(u)).Coord());p+=axis*float(n@(q-p)/dot)
  if np.isfinite(p).all():result.append(p)
 return sorted(result,key=lambda p:float(np.linalg.norm(p-point)))
