"""Reconocer la carta afín de un campo de alturas sin proyectar iterativamente.

La identidad UV se contrasta en TODOS los polos por precisión lineal de
B-splines. Sólo se usa para elegir esquinas y la normal de referencia;
la frontera CAD y la superficie final se verifican independientemente.
"""
import numpy as np
from OCP.Geom import Geom_BSplineSurface
from OCP.gp import gp_Pnt,gp_Vec


class CartaAltura:
    def __init__(self,surface,center,target,coefficients,bound):
        self.surface=surface;self.center=center;self.target=target;self.coefficients=coefficients;self.cota_uv=bound
    def uv(self,point):return self.target+(np.asarray(point)-self.center)@self.coefficients
    def __call__(self,point):
        uv=self.uv(point)
        return np.asarray(self.surface.Value(*map(float,uv)).Coord()),tuple(map(float,uv))
    def normal(self,point):
        u,v=self.uv(point);u0,u1,v0,v1=self.surface.Bounds();u=float(np.clip(u,u0,u1));v=float(np.clip(v,v0,v1))
        p=gp_Pnt();du=gp_Vec();dv=gp_Vec();self.surface.D1(u,v,p,du,dv);n=du.Crossed(dv);length=n.Magnitude()
        if length<1e-20:return None
        return np.asarray(n.Coord())/length


def reconocer(surface):
    if not isinstance(surface,Geom_BSplineSurface) or surface.IsURational() or surface.IsVRational():return None
    def greville(axis):
        degree=surface.UDegree() if axis==0 else surface.VDegree()
        count=surface.NbUKnots() if axis==0 else surface.NbVKnots();knot=surface.UKnot if axis==0 else surface.VKnot;mult=surface.UMultiplicity if axis==0 else surface.VMultiplicity
        expanded=np.repeat([knot(i) for i in range(1,count+1)],[mult(i) for i in range(1,count+1)])
        n=surface.NbUPoles() if axis==0 else surface.NbVPoles()
        return np.array([np.mean(expanded[i+1:i+degree+1]) for i in range(n)])
    U,V=greville(0),greville(1)
    points=np.array([surface.Pole(i,j).Coord() for i in range(1,len(U)+1) for j in range(1,len(V)+1)])
    target=np.array([(u,v) for u in U for v in V]);center=points.mean(0);middle=target.mean(0)
    coefficients=np.linalg.lstsq(points-center,target-middle,rcond=1e-13)[0]
    residual=float(np.linalg.norm((points-center)@coefficients-(target-middle),axis=1).max())
    singular=np.linalg.svd(coefficients,compute_uv=False)
    if not np.isfinite(coefficients).all() or residual>1e-9 or singular[1]<1e-12:return None
    return CartaAltura(surface,center,middle,coefficients,residual)
