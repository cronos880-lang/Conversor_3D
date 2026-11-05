"""Propuestas locales desde TODOS los vértices; aceptación global externa intacta.

Un campo de alturas conserva su parametrización PCA. Se mide con evaluación
real de la superficie, sin aceptar un fallo de proyección como distancia cero.
"""
import numpy as np
from OCP.Geom import Geom_Plane
from OCP.gp import gp_Ax3,gp_Pnt,gp_Dir,gp_Pln

def componentes(mesh, ids):
    ids=np.asarray(ids,int)
    if not len(ids):return []
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    index=np.full(len(mesh.faces),-1,int);index[ids]=np.arange(len(ids))
    adj=index[mesh.face_adjacency];adj=adj[np.all(adj>=0,axis=1)]
    graph=coo_matrix((np.ones(2*len(adj)),(np.r_[adj[:,0],adj[:,1]],np.r_[adj[:,1],adj[:,0]])),shape=(len(ids),len(ids)))
    _,labels=connected_components(graph,directed=False)
    return [ids[labels==k] for k in np.unique(labels)]

def plano_exacto(mesh,ids):
    P=mesh.vertices[np.unique(mesh.faces[ids])];c=P.mean(0)
    _,sv,vt=np.linalg.svd(P-c,full_matrices=False)
    if len(sv)<3 or sv[1]<1e-10:return None
    n=vt[2];n*=1 if mesh.face_normals[ids].mean(0)@n>=0 else -1
    if np.max(abs((P-c)@n))>1e-5:return None
    if np.min(mesh.face_normals[ids]@n)<np.cos(np.radians(.1)):return None
    return Geom_Plane(gp_Pln(gp_Ax3(gp_Pnt(*map(float,c)),gp_Dir(*map(float,n)),gp_Dir(*map(float,vt[0])))))

def altura_medida(mesh,ids):
    import meshfit_brep as base
    ids=np.asarray(ids,int)
    if len(ids)<3 or len(ids)>10000:return None
    adj=mesh.face_adjacency;inside=np.zeros(len(mesh.faces),bool);inside[ids]=True;adj=adj[np.all(inside[adj],axis=1)]
    if len(adj) and np.min(np.sum(mesh.face_normals[adj[:,0]]*mesh.face_normals[adj[:,1]],axis=1))<np.cos(np.radians(15)):return None
    P=mesh.vertices[np.unique(mesh.faces[ids])]
    if len(P)<6:return None
    c=P.mean(0);_,sv,vt=np.linalg.svd(P-c,full_matrices=False)
    if sv[1]<1e-8:return None
    n=vt[2];n*=1 if mesh.face_normals[ids].mean(0)@n>=0 else -1
    x=vt[0];y=np.cross(n,x)
    existed=hasattr(mesh,'precision_reparacion');old=getattr(mesh,'precision_reparacion',None)
    try:
        mesh.precision_reparacion=True
        surface,ok=base._fit_bspline(mesh,ids,.001)
    except Exception:return None
    finally:
        if existed:mesh.precision_reparacion=old
        else:delattr(mesh,'precision_reparacion')
    if not ok or surface is None:return None
    probes=np.vstack([P,mesh.triangles_center[ids]])
    uv=np.column_stack([(probes-c)@x,(probes-c)@y])
    values=np.array([surface.Value(float(u),float(v)).Coord() for u,v in uv])
    errors=np.linalg.norm(values-probes,axis=1)
    if not np.isfinite(values).all() or errors.max()>.003:return None
    return surface,dict(triangulos=len(ids),testigos=len(probes),max_testigos_mm=float(errors.max()),control_propuesta_mm=.003)
