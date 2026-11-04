"""Proyección 1D por tramos polinómicos y cotas de su envolvente convexa.

Para cada cúbica se examinan los extremos y las raíces reales del gradiente
quintico de la distancia al cuadrado. No se cambia la curva ni su tolerancia.
"""
import numpy as np
from scipy.spatial import cKDTree
from OCP.Geom import Geom_BSplineCurve
from OCP.gp import gp_Pnt
_CACHE={}

def preparar(curve):
 if not isinstance(curve,Geom_BSplineCurve) or curve.IsRational() or curve.Degree()>3:return None
 key=id(curve)
 if key in _CACHE:return _CACHE[key]
 lower,upper=curve.FirstParameter(),curve.LastParameter();knots=np.unique(np.r_[lower,[curve.Knot(i) for i in range(1,curve.NbKnots()+1) if lower<curve.Knot(i)<upper],upper]);rows=[]
 for lo,hi in zip(knots[:-1],knots[1:]):
  piece=curve.Copy();piece.Segment(float(lo),float(hi),min(1e-14,float(hi-lo)*.01));piece.IncreaseDegree(3)
  if piece.NbPoles()!=4 or piece.NbKnots()!=2:return None
  B=np.array([piece.Pole(i).Coord() for i in range(1,5)]);coeff=np.array([B[0],3*(B[1]-B[0]),3*(B[2]-2*B[1]+B[0]),B[3]-3*B[2]+3*B[1]-B[0]])
  rows.append((float(lo),float(hi),coeff,B.min(0)-1e-10,B.max(0)+1e-10))
 points=np.array([curve.Value(float(u)).Coord() for u in knots]);cache=(curve,knots,points,cKDTree(points),rows,np.array([r[3] for r in rows]),np.array([r[4] for r in rows]));_CACHE[key]=cache;return cache

def parametro(curve,target,prepared=None):
 cached=prepared if prepared is not None else preparar(curve)
 if cached is None:return None
 _,knots,points,tree,rows,lower,upper=cached;target=np.asarray(target,float);distance,j=tree.query(target);best=float(distance*distance);u=float(knots[int(j)]);delta=np.maximum(np.maximum(lower-target,target-upper),0.);bounds=np.sum(delta*delta,axis=1)
 point=gp_Pnt(*map(float,target))
 for j in np.argsort(bounds):
  if bounds[j]>best+1e-20:continue
  lo,hi,coeff,_,_=rows[int(j)];D=coeff.copy();D[0]-=target;G=np.zeros(6)
  for k in range(3):G+=np.convolve(D[:,k],np.arange(1,4)*D[1:,k])
  scale=float(abs(G).max());roots=np.polynomial.polynomial.polyroots(G/scale) if scale else []
  candidates=[0.,1.]+[float(np.clip(z.real,0,1)) for z in roots if abs(z.imag)<1e-6 and -1e-10<=z.real<=1+1e-10]
  for t in candidates:
   v=float(lo+(hi-lo)*t);actual=curve.Value(v).SquareDistance(point)
   if actual<best:best=actual;u=v
 return u
