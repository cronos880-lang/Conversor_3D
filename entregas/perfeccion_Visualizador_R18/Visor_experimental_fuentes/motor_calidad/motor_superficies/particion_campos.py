"""Agrupar triángulos fuente en dominios simples; nunca rellenar su contorno.

La convexidad aproximada sólo selecciona propuestas. Se conservan todos
los triángulos, sus coordenadas y los agujeros de la región original.
La aceptación CAD, superficial y de material permanece independiente.
"""
import numpy as np
from scipy.spatial import ConvexHull,QhullError


def particionar(mesh,ids,*,soporte_medido=None,max_triangulos=64):
    ids=np.asarray(ids,int);triangles=np.asarray(mesh.faces[ids]);keys,inverse=np.unique(triangles,return_inverse=True);F=inverse.reshape(-1,3)
    P=np.asarray(mesh.vertices[keys]);uv=None
    if soporte_medido is not None:
        from OCP.Geom import Geom_SurfaceOfLinearExtrusion
        if isinstance(soporte_medido,Geom_SurfaceOfLinearExtrusion):
            from proyeccion_barridos import uv_exacta
            uv=uv_exacta(soporte_medido,P)
    if uv is None:
        center=P.mean(0);_,sv,axes=np.linalg.svd(P-center,full_matrices=False)
        if sv[1]<1e-12:return [np.array([i]) for i in ids]
        uv=(P-center)@axes[:2].T
    span=np.ptp(uv,axis=0)
    if not np.isfinite(uv).all() or np.min(span)<1e-12:return [np.array([i]) for i in ids]
    uv=(uv-uv.min(0))/span
    t=uv[F];a=t[:,1]-t[:,0];b=t[:,2]-t[:,0];signed=a[:,0]*b[:,1]-a[:,1]*b[:,0];orientation=1. if signed.sum()>=0 else -1.;areas=signed*orientation*.5
    # Las facetas que no admiten la carta quedan aparte, sin descartarlas.
    groups={i:{i} for i in range(len(ids))};owner=np.arange(len(ids));adj=set()
    source_edges={}
    for i,tri in enumerate(F):
        for a,b in zip(tri,np.roll(tri,-1)):source_edges.setdefault(tuple(sorted((int(a),int(b)))),[]).append(i)
    for neighbors in source_edges.values():
        if len(neighbors)==2:adj.add(tuple(sorted(neighbors)))
    def valid(part):
        if len(part)>max_triangulos:return False
        selected=np.array(sorted(part),int)
        if np.any(areas[selected]<=1e-20):return False
        faces=F[selected];verts=np.unique(faces);edges,counts=np.unique(np.sort(np.vstack([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0,return_counts=True)
        if counts.max()>2 or len(verts)-len(edges)+len(faces)!=1:return False
        border=edges[counts==1];nodes,degree=np.unique(border,return_counts=True)
        if np.any(degree!=2):return False
        # Conectividad heredada de una unión por arista. Euler1 + frontera
        # regular impide absorber un agujero completo en una sola propuesta.
        try:hull=float(ConvexHull(uv[verts]).volume)
        except QhullError:return False
        area=float(areas[selected].sum())
        # Margen para elegir dominios casi convexos; no cambia la superficie
        # fuente ni tolerancia alguna del STEP.
        return hull>0 and -.0000000001<=1-area/hull<=.02
    versions={i:0 for i in groups};cache={}
    while True:
        choices=set(tuple(sorted((int(owner[a]),int(owner[b])))) for a,b in adj if owner[a]!=owner[b])
        merged=False
        for a,b in sorted(choices,key=lambda pair:-float(areas[list(groups[pair[0]]|groups[pair[1]])].sum())):
            union=groups[a]|groups[b]
            key=(a,versions[a],b,versions[b])
            if key not in cache:cache[key]=valid(union)
            if not cache[key]:continue
            groups[a]=union;del groups[b]
            versions[a]+=1
            for i in union:owner[i]=a
            merged=True;break
        if not merged:break
    result=[ids[np.array(sorted(part),int)] for part in groups.values()]
    assert np.array_equal(np.sort(np.concatenate(result)),np.sort(ids))
    return result
