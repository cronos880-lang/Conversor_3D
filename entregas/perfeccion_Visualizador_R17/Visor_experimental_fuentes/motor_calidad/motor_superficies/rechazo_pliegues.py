"""Rechazar pliegues observados; la aceptación final CAD/BOP/CGAL sigue obligatoria."""
import numpy as np
from OCP.gp import gp_Pnt,gp_Vec


def exigir_regular(surface,reference):
    varying=callable(reference)
    if not varying:
        normal=np.asarray(reference,float);length=np.linalg.norm(normal)
        if length==0:raise ValueError('No se confirma la orientación del campo libre')
        normal/=length
    u0,u1,v0,v1=surface.Bounds()
    def values(first,last,axis):
        knots=[first,last]
        if hasattr(surface,'NbUKnots'):
            count=surface.NbUKnots() if axis==0 else surface.NbVKnots()
            knot=surface.UKnot if axis==0 else surface.VKnot
            knots.extend(knot(i) for i in range(1,count+1) if first<knot(i)<last)
        breaks=sorted(set(knots));out=[]
        for a,b in zip(breaks[:-1],breaks[1:]):out.extend(a+(b-a)*np.array([.01,.15,.5,.85,.99]))
        return np.unique(out)
    U,V=values(u0,u1,0),values(v0,v1,1)
    if len(U)*len(V)>65536:raise ValueError('El campo libre excede el presupuesto de comprobación de orientación')
    normal_vec=None if varying else gp_Vec(*map(float,normal))
    signs=set();count=0
    for u in U:
        for v in V:
            p=gp_Pnt();du=gp_Vec();dv=gp_Vec();surface.D1(float(u),float(v),p,du,dv)
            cross=du.Crossed(dv);scale=cross.Magnitude()
            if scale<=1e-24:raise ValueError('El campo libre presenta una parametrización colapsada')
            if varying:
                result=reference(np.asarray(p.Coord()))
                if result is None:raise ValueError('No se confirma la normal fuente local')
                normal=np.asarray(result,float);length=np.linalg.norm(normal)
                if not np.isfinite(normal).all() or length==0:raise ValueError('Normal fuente local no finita o nula')
                normal=normal/length;normal_vec=gp_Vec(*map(float,normal))
            dot=float(cross.Dot(normal_vec)/scale);count+=1
            if abs(dot)>1e-8:signs.add(1 if dot>0 else -1)
            if len(signs)>1:raise ValueError('El campo libre cambia de orientación y se pliega; subdividir la región fuente')
    if not signs:raise ValueError('No se confirma una orientación regular del campo libre')
    return dict(muestras=count,signo=next(iter(signs)),nota='Rechazo de pliegues observados; no sustituye BOP ni CGAL')
