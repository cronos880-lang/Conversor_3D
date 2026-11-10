"""Ampliar cilindros sólo sobre facetas completas dentro de la cota previa."""
import numpy as np
from OCP.Geom import Geom_CylindricalSurface
from OCP.gp import gp_Ax3,gp_Pnt,gp_Dir

def propuestas(mesh,required,surfaces=()):
 out=[]
 for req in required:
  a=req['eje'];q=req['centro'];radius=req['radio']
  for s in surfaces:
   if not isinstance(s,Geom_CylindricalSurface):continue
   sa=np.array(s.Axis().Direction().Coord());sq=np.array(s.Location().Coord())
   if abs(s.Radius()-radius)<=.008 and abs(sa@a)>.99999 and np.linalg.norm(np.cross(sq-q,a))<=.008:
    if np.max(abs(np.linalg.norm(np.cross(req['puntos']-sq,sa),axis=1)-s.Radius()))<=.008:
     a,q,radius=sa,sq,s.Radius();break
  D=mesh.vertices-q;radial=D-np.outer(D@a,a);rho=np.linalg.norm(radial,axis=1)
  radial_centers=radial[mesh.faces].mean(axis=1)
  unit=radial_centers/np.maximum(np.linalg.norm(radial_centers,axis=1)[:,None],1e-300)
  agreement=abs(np.sum(unit*mesh.face_normals,axis=1))
  mask=np.all(abs(rho[mesh.faces]-radius)<=.008,axis=1)&(agreement>np.cos(np.radians(15)))
  T=radial[mesh.faces];A=T;B=np.roll(T,-1,axis=1);d=B-A;t=np.clip(-np.sum(A*d,axis=2)/np.maximum(np.sum(d*d,axis=2),1e-300),0,1);rmin=np.linalg.norm(A+t[:,:,None]*d,axis=2).min(axis=1)
  # Veto explícito al origen dentro del triángulo proyectado (no sólo aristas).
  cross=np.sum(np.cross(A,B)*a,axis=2);inside=(np.all(cross>1e-14,axis=1)|np.all(cross<-1e-14,axis=1));rmin[inside]=0.
  mask &= (radius-rmin<=.008)
  ids=np.flatnonzero(mask);surface=Geom_CylindricalSurface(gp_Ax3(gp_Pnt(*map(float,q)),gp_Dir(*map(float,a))),float(radius));out.append((ids,surface))
 return out
