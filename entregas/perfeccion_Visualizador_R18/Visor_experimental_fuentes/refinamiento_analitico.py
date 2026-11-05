"""Laboratorio: recuperar caras cilíndricas verificadas en mallas CAD digitales.

No ajusta STL ni idealiza radios. Las propuestas deben validar vértices,
centroides y normales. Cualquier STEP se evalúa externamente con el validador
original; este algoritmo NO implica por sí solo una conversión aceptable.
"""
from __future__ import annotations
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from axial_recognition import verified_axial_patches


def _conectadas(mesh, faces):
    faces=np.asarray(faces,dtype=int)
    if not len(faces):return []
    active=np.zeros(len(mesh.faces),dtype=bool);active[faces]=True
    links=mesh.face_adjacency
    links=links[active[links[:,0]] & active[links[:,1]]]
    mat=coo_matrix((np.ones(len(links)*2,dtype=np.int8),
      (np.r_[links[:,0], links[:,1]],np.r_[links[:,1],links[:,0]])),
      shape=(len(mesh.faces),len(mesh.faces))).tocsr()
    _,labels=connected_components(mat,directed=False)
    return sorted((faces[labels[faces]==j] for j in np.unique(labels[faces])),key=len,reverse=True)


def recuperar_cilindros(result, mesh, *, tol=.008, min_faces=120):
    """Inyecta solo regiones conexas con evidencia de curvatura real.

    Se protegen las caras previamente identificadas como cilindros/conos
    evitando modificar una reconstrucción ya buena y se requiere soporte
    radial >=35°. Relevante para pivotes triangulados omitidos por segmentación.
    """
    claimed=np.zeros(len(mesh.faces), dtype=bool)
    for p in result['primitives']:
        if p['type'] in ('cylinder','cone'):
            claimed[np.asarray(p['faces'],dtype=int)]=True
    allowed=np.where(~claimed)[0]
    patches=verified_axial_patches(mesh,allowed,tol=tol)
    accepted=[];occupied=np.zeros(len(mesh.faces),bool)
    for proposal in patches:
        faces=np.asarray(proposal['faces'],dtype=int)
        if len(faces)<min_faces:continue
        for comp in _conectadas(mesh,faces):
            if len(comp)<min_faces:continue
            if occupied[comp].any(): continue
            # Veto explícito a grupos sin recorrido circular significativo.
            axis=int(proposal['axis']);ij=[k for k in range(3) if k!=axis]
            ctr=np.asarray(proposal['center'])
            centers=mesh.triangles_center[comp][:,ij]
            phi=np.arctan2(centers[:,1]-ctr[1],centers[:,0]-ctr[0]);phi=np.sort((phi+2*np.pi)%(2*np.pi))
            arc=360*(1-(np.diff(np.r_[phi,phi[0]+2*np.pi]).max()/(2*np.pi)))
            if arc<35: continue
            pp=dict(proposal['prim']);pp['faces']=comp.tolist();pp['n_faces']=len(comp)
            accepted.append(pp);occupied[comp]=True
    if not accepted:return []
    preserved=[]
    for p in result['primitives']:
        kept=np.asarray(p['faces'],dtype=int)
        kept=kept[~occupied[kept]]
        if len(kept)>=2:
            pp=dict(p);pp['faces']=kept.tolist();pp['n_faces']=len(kept)
            preserved.append(pp)
    free=[]
    for region in result.get('freeform_regions',[]):
        kept=np.asarray(region,dtype=int)
        kept=kept[~occupied[kept]]
        for comp in _conectadas(mesh,kept):
            if len(comp)>=2:free.append(comp.tolist())
    result['primitives']=preserved+accepted
    result['freeform_regions']=free
    result['freeform_faces']=sum(map(len,free))
    return [{'radio':round(float(p['radius']),6),'triangulos':p['n_faces']} for p in accepted]
