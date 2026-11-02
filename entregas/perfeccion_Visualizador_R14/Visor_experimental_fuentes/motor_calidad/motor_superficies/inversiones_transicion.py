"""Rechazo preventivo de inversiones del esqueleto de transición.

Sólo examina triángulos libres cuyos tres vértices forman parte del
contorno compartido. No convierte este control en prueba de validez CAD,
ni cambia la fuente o los límites de aceptación posteriores.
"""
import numpy as np


def detectar(original,caras,etiquetas,posiciones,primarias):
    original=np.asarray(original,float);caras=np.asarray(caras,int)
    projected=original.copy();keys=np.array(sorted(posiciones),int)
    if len(keys):projected[keys]=np.array([posiciones[int(v)] for v in keys])
    if not np.isfinite(projected).all():raise ValueError('Coordenadas proyectadas no finitas')
    known=np.zeros(len(original),bool);known[keys]=True
    eligible=np.all(known[caras],axis=1)&~np.isin(etiquetas,list(primarias))
    ids=np.flatnonzero(eligible)
    a=original[caras[ids]];b=projected[caras[ids]]
    n=np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0]);m=np.cross(b[:,1]-b[:,0],b[:,2]-b[:,0])
    lengths=np.linalg.norm(n,axis=1)
    if np.any(lengths==0):raise ValueError('La fuente contiene un triángulo degenerado')
    ratios=np.sum(n*m,axis=1)/(lengths*lengths)
    rows=[]
    for k in np.flatnonzero(ratios<=0.):
        i=int(ids[k]);rows.append(dict(triangulo=i,region=int(etiquetas[i]),vertices=caras[i].tolist(),area_orientada_relativa=float(ratios[k])))
    return sorted(rows,key=lambda r:r['area_orientada_relativa'])
