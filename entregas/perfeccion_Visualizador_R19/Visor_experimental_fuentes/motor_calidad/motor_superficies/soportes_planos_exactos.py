"""Reconocer un plano por TODOS los polos de un soporte; sin mover el contorno."""
import numpy as np
from OCP.Geom import Geom_BSplineSurface,Geom_BezierSurface,Geom_Plane
from OCP.gp import gp_Ax3,gp_Pnt,gp_Dir


def reconocer(surface):
    if not isinstance(surface,(Geom_BSplineSurface,Geom_BezierSurface)):return None
    P=np.array([surface.Pole(i,j).Coord() for i in range(1,surface.NbUPoles()+1) for j in range(1,surface.NbVPoles()+1)])
    W=np.array([surface.Weight(i,j) for i in range(1,surface.NbUPoles()+1) for j in range(1,surface.NbVPoles()+1)])
    if not np.isfinite(P).all() or not np.isfinite(W).all() or np.any(W<=0):return None
    center=P.mean(0);_,singular,axes=np.linalg.svd(P-center,full_matrices=False)
    if len(singular)<3 or singular[1]<1e-10:return None
    bound=float(abs((P-center)@axes[-1]).max())
    if bound>1e-10:return None
    plane=Geom_Plane(gp_Ax3(gp_Pnt(*center),gp_Dir(*axes[-1]),gp_Dir(*axes[0])))
    return plane,dict(cota_convexa_todos_polos_mm=bound,polos=len(P),contornos_3D_modificados=False)
