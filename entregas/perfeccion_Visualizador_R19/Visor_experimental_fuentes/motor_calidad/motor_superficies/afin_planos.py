"""Resolver contactos dentro del espacio afín exacto de los planos incidentes.

Las distancias normales pequeñas no bastan entre planos casi paralelos.
Se elimina ese mal condicionamiento sin ampliar tolerancias ni mover soportes.
"""
import numpy as np
from OCP.Geom import Geom_Plane
from scipy.optimize import least_squares
from types import SimpleNamespace

def espacio(surfaces,reference):
    planes=[s for s in surfaces if isinstance(s,Geom_Plane)]
    if not planes:return None
    reference=np.asarray(reference,float)
    A=np.array([s.Axis().Direction().Coord() for s in planes])
    b=np.array([np.dot(n,np.asarray(s.Location().Coord())-reference) for n,s in zip(A,planes)])
    U,S,V=np.linalg.svd(A,full_matrices=True);rank=int(np.sum(S>S[0]*1e-12))
    delta=V[:rank].T@((U[:,:rank].T@b)/S[:rank]);origin=reference+delta
    error=float(np.max(abs(A@(origin-reference)-b)))
    if not np.isfinite(origin).all() or error>1e-10:raise ValueError('Los planos incidentes no comparten un espacio afín verificable: '+str(error))
    return origin,V[rank:].T,dict(planos=len(planes),rango=rank,residual_planos_mm=error)

def resolver(surfaces,point,seed,residual):
    point=np.asarray(point,float);seed=np.asarray(seed,float);affine=espacio(surfaces,point)
    if affine is None:
        return least_squares(lambda q:np.r_[residual(q),(q-point)*1e-6],seed,xtol=1e-13,ftol=1e-13,gtol=1e-13,max_nfev=160)
    origin,basis,proof=affine
    if basis.shape[1]==0:return SimpleNamespace(x=origin,afin=proof)
    if all(isinstance(s,Geom_Plane) for s in surfaces) and np.max(np.abs(residual(origin)),initial=0.)<=1e-12:
        # Proyección ortogonal exacta: minimiza el desplazamiento, incluso
        # cuando la penalización numérica es demasiado pequeña para LS.
        return SimpleNamespace(x=origin,afin=proof)
    def value(z):
        q=origin+basis@z
        return np.r_[residual(q),(q-point)*1e-6]
    fit=least_squares(value,basis.T@(seed-origin),xtol=1e-13,ftol=1e-13,gtol=1e-13,max_nfev=160)
    return SimpleNamespace(x=origin+basis@fit.x,afin=proof)


class ContornoPlanoIncompatible(ValueError):
    """El corte de dos planos no puede conservar la cadena fuente."""
