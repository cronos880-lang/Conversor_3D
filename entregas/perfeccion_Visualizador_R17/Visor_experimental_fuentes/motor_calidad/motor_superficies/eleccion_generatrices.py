"""Elegir una única rama nativa para la cadena fuente completa."""
import numpy as np


def elegir(candidates,points):
    points=np.asarray(points,float)
    if not len(points) or not np.isfinite(points).all():raise ValueError('Cadena fuente no finita o vacía')
    scores=[]
    for index,line in enumerate(candidates):
        origin,axis,_=line;origin=np.asarray(origin,float);axis=np.asarray(axis,float)
        if not np.isfinite(origin).all() or not np.isfinite(axis).all() or abs(np.linalg.norm(axis)-1)>1e-12:
            raise ValueError('Generatriz no finita o no normalizada')
        distances=np.linalg.norm(np.cross(points-origin,axis),axis=1)
        scores.append((float(distances.max()),float(np.sum(distances*distances)),index))
    if not scores:raise ValueError('No hay generatrices nativas')
    maximum,_,index=min(scores)
    return candidates[index],dict(rama=index,error_max_cadena_mm=maximum,vertices=len(points))
