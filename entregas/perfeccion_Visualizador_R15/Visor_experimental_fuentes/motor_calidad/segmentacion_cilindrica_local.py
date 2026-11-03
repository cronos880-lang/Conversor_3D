"""Grow source-backed cylinders from small local feature seeds.

Unlike global random pairs, small bores get deterministic local proposals.
Axes are measured from substantial source-supported cylinders; the final
complete-ring and all-triangle proof is independent of this proposal stage.
"""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from operaciones_cilindricas_medidas import medir


def propuestas(mesh, result, max_candidates=192):
    V=np.asarray(mesh.vertices);F=np.asarray(mesh.faces);N=np.asarray(mesh.face_normals);axes=[]
    for p in result['primitives']:
        if p['type']!='cylinder' or len(p['faces'])<100 or p.get('rms',1)>.0001:continue
        a=np.asarray(p['axis'],float);a/=np.linalg.norm(a)
        if not any(abs(a@b)>1-1e-8 for b in axes):axes.append(a)
    output=[];proofs=[];tested=set();adj=np.asarray(mesh.face_adjacency);attempts=0
    seeds=sorted(result['primitives'],key=lambda p:(p['type']!='cylinder',-len(p['faces'])))
    for a in axes:
        e=np.eye(3)[np.argmin(abs(a))];u=np.cross(a,e);u/=np.linalg.norm(u);v=np.cross(a,u);basis=np.column_stack((u,v));P=V@basis
        for seed in seeds:
            ids=np.asarray(seed['faces'],int)
            if len(ids)<4 or np.quantile(abs(N[ids]@a),.9)>.02:continue
            points=P[np.unique(F[ids])];origin=points.mean(0);xy=points-origin
            if len(points)<6:continue
            singular=np.linalg.svd(xy,compute_uv=False)
            if singular[-1]<max(1e-5,singular[0]*1e-4):continue
            x,y,k=np.linalg.lstsq(np.c_[2*xy,np.ones(len(xy))],(xy*xy).sum(1),rcond=None)[0]
            center2=origin+np.array([x,y]);radius2=k+x*x+y*y
            if radius2<.25**2 or radius2>5000**2:continue
            r=np.sqrt(radius2);key=tuple(np.round(np.r_[center2,r]/.015).astype(int))
            if key in tested:continue
            tested.add(key);attempts+=1
            if attempts>max_candidates:break
            residual=abs(np.linalg.norm(P-center2,axis=1)-r)
            mask=(residual[F].max(1)<.008)&(abs(N@a)<.02)
            selected=np.flatnonzero(mask)
            if len(selected)<48:continue
            links=adj[mask[adj[:,0]]&mask[adj[:,1]]]
            graph=coo_matrix((np.ones(2*len(links)),(np.r_[links[:,0],links[:,1]],np.r_[links[:,1],links[:,0]])),shape=(len(F),len(F))).tocsr()
            _,labels=connected_components(graph,directed=False)
            for label in np.unique(labels[selected]):
                faces=selected[labels[selected]==label]
                if len(faces)<48 or any(len(np.intersect1d(faces,p['faces']))>.95*len(faces) for p in output):continue
                candidate=dict(type='cylinder',faces=faces.tolist(),n_faces=len(faces),axis=a.tolist(),radius=float(r),point=(basis@center2).tolist())
                try:measured=medir(mesh,candidate)
                except ValueError:continue
                output.append(candidate);proofs.append(dict(source_facets=len(faces),radius_mm=measured['radius'],radial_bound_mm=measured['radial_bound_mm'],seed_local=True))
    return output,dict(axes=len(axes),local_hypotheses=attempts,complete_rings=len(output),regions=proofs)
