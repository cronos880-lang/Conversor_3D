"""Proyección exacta sobre extrusiones de perfiles planos mediante su curva 1D."""
import numpy as np
from proyeccion_barridos import uv_exacta

class ProyectorPerfil:
 def __init__(self,surface):
  from proyeccion_barridos import analizador
  self.s=surface;self.sas=analizador(surface);self.kind=None
  self.surface=surface;self.curve=surface.BasisCurve();self.axis=np.array(surface.Direction().Coord());self.cache={}
  if hasattr(self.curve,'NbPoles'):points=np.array([self.curve.Pole(i).Coord() for i in range(1,self.curve.NbPoles()+1)])
  else:points=np.array([self.curve.Value(float(u)).Coord() for u in np.linspace(self.curve.FirstParameter(),self.curve.LastParameter(),33)])
  if np.ptp(points@self.axis)>1e-9:raise ValueError('El perfil no es perpendicular a su dirección de extrusión')
 def _record(self,point,u,v):
  base=np.array(self.curve.Value(float(u)).Coord());projected=base+self.axis*v;derivative=np.array(self.curve.DN(float(u),1).Coord());normal=np.cross(derivative,self.axis);length=np.linalg.norm(normal)
  if length<1e-14:raise ValueError('No se define la normal del perfil')
  value=(projected,(float(u),float(v)),normal/length);self.cache[tuple(point)]=value;return value
 def batch(self,points):
  points=np.asarray(points,float)
  if not len(points):return np.empty((0,3),float)
  uv=uv_exacta(self.surface,points)
  if not np.isfinite(uv).all():raise ValueError('Proyección de perfil no finita')
  self.cache={};return np.asarray([self._record(p,u,v)[0] for p,(u,v) in zip(points,uv)])
 def __call__(self,point):
  point=np.asarray(point,float);value=self.cache.get(tuple(point))
  if value is None:
   u,v=uv_exacta(self.surface,point[None,:])[0];value=self._record(point,u,v)
  return value[0],value[1]
 def normal(self,point):
  self(point);return self.cache[tuple(point)][2]
