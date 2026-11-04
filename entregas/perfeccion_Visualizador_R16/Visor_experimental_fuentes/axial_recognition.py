"""Experimental evidence-based extraction of near-perfect cylindrical mesh patches.

Never changes vertices; only proposes groups of existing mesh triangles.
The construction/validation phase must still accept any proposal.
"""
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components


def candidates(mesh, min_faces=60, tol=0.008, max_trials=2800, allowed_faces=None):
    V=np.asarray(mesh.vertices,dtype=float)
    F=np.asarray(mesh.faces,dtype=int)
    C=np.asarray(mesh.triangles_center,dtype=float)
    N=np.asarray(mesh.face_normals,dtype=float)
    A=np.asarray(mesh.area_faces,dtype=float)
    out=[]
    rng=np.random.default_rng(83)
    axes=np.eye(3)
    for ai,axis in enumerate(axes):
        ids=np.where(np.abs(N[:,ai]) < .06)[0]
        if allowed_faces is not None:
            ids=np.intersect1d(ids,np.asarray(allowed_faces,dtype=int),assume_unique=False)
        if len(ids) < min_faces:continue
        ij=[i for i in range(3) if i!=ai]
        p=C[ids][:,ij]; n=N[ids][:,ij]
        n=n/(np.linalg.norm(n,axis=1)[:,None]+1e-12)
        # Proposals from normal-line pair intersections.
        # Weight random seeds by area, ensuring both broad and fine tessellations.
        probs=np.sqrt(A[ids]);probs/=probs.sum()
        samples=rng.choice(len(ids), size=(max_trials,2), replace=True, p=probs)
        candidates0=[]
        for ii,jj in samples:
            dn=n[ii]-n[jj]
            if np.dot(dn,dn) < .4:continue
            rr=float(np.dot(p[ii]-p[jj],dn)/np.dot(dn,dn))
            if abs(rr)<.2 or abs(rr)>5000:continue
            ctr=p[ii]-rr*n[ii]
            if np.linalg.norm((p[jj]-rr*n[jj])-ctr)>max(tol*4,0.015):continue
            candidates0.append((ctr,abs(rr),np.sign(rr)))
        # Group near-identical hypotheses to avoid hundreds of expensive rescores.
        uniq={}
        for ctr,r,sgn in candidates0:
            key=tuple(np.round(np.r_[ctr,r,sgn]/np.r_[.04,.04,.04,1]).astype(int))
            if key not in uniq:uniq[key]=(ctr,r,sgn)
        for ctr,r,sgn in uniq.values():
            rad=(p-ctr)
            norm=np.linalg.norm(rad,axis=1)
            nd=np.sum(rad*n,axis=1)/(norm+1e-12)*sgn
            rough=(np.abs(norm-r)<.018)&(nd>.993)
            ix=np.where(rough)[0]
            if len(ix)<min_faces:continue
            pts=V[F[ids[ix]]][:,:,ij]
            err=np.max(np.abs(np.linalg.norm(pts-ctr,axis=2)-r),axis=1)
            ok=err<=tol
            accepted=ids[ix[ok]]
            if len(accepted)<min_faces:continue
            # Only connected patches, no jumping to unrelated faces on the same radius.
            active=np.zeros(len(F),bool);active[accepted]=True
            links=mesh.face_adjacency
            links=links[active[links[:,0]]&active[links[:,1]]]
            from scipy.sparse import coo_matrix
            graph=coo_matrix((np.ones(2*len(links)),(np.r_[links[:,0],links[:,1]],np.r_[links[:,1],links[:,0]])),shape=(len(F),len(F))).tocsr()
            cc,lab=connected_components(graph,directed=False)
            for lid in np.unique(lab[accepted]):
                subset=accepted[lab[accepted]==lid]
                if len(subset)<min_faces: continue
                # radial support of at least 20 deg and an actual axial span.
                angles=np.arctan2(C[subset][:,ij[1]]-ctr[1],C[subset][:,ij[0]]-ctr[0])
                a=np.sort((angles+2*np.pi)%(2*np.pi))
                angular=2*np.pi-np.diff(np.r_[a,a[0]+2*np.pi]).max()
                height=np.ptp(V[np.unique(F[subset])][:,ai])
                if angular<np.radians(20) or height<max(.3, r*.025):continue
                strength=float(A[subset].sum())
                out.append(dict(axis=ai,center=ctr,radius=r,faces=subset,area=strength,
                                angular=float(np.degrees(angular)),height=float(height)))
    out.sort(key=lambda d:-d['area'])
    unique=[]
    for o in out:
        if any(p['axis']==o['axis'] and abs(p['radius']-o['radius'])<.025 and np.linalg.norm(p['center']-o['center'])<.025 for p in unique):continue
        unique.append(o)
    return unique

def verified_axial_patches(mesh, faces, *, tol=.008):
    """Propose axially cylindrical patches with real triangle interior verification.
    Candidate initialization uses normals; the circle is refitted using actual mesh
    vertices; acceptance uses all triangle corners AND centroids. No STL editing.
    """
    V=np.asarray(mesh.vertices); F=np.asarray(mesh.faces)
    C=np.asarray(mesh.triangles_center); N=np.asarray(mesh.face_normals)
    Fselect=np.asarray(faces,dtype=int)
    if len(Fselect)<140:return []
    proposals=candidates(mesh,allowed_faces=Fselect,tol=tol)
    done=[]
    for proposal in proposals:
        ai=proposal['axis'];ij=[j for j in range(3) if j!=ai]
        ctr0,r0=proposal['center'],proposal['radius']
        if any(q['axis']==ai and abs(q['radius']-r0)<.15 and np.linalg.norm(q['center']-ctr0)<.15 for q in done):continue
        current=np.asarray(proposal['faces'],dtype=int)
        if len(current)<60:continue
        for _ in range(4):
            xy=V[np.unique(F[current].ravel())][:,ij]
            A=np.c_[2*xy,np.ones(len(xy))]; b=np.sum(xy*xy,axis=1)
            (cx,cy,off),*_ = np.linalg.lstsq(A,b,rcond=None)
            center=np.array([cx,cy]);r=np.sqrt(max(0,off+cx*cx+cy*cy))
            if r<.25:break
            pts=V[F[Fselect]][:,:,ij]
            dv=np.abs(np.linalg.norm(pts-center,axis=2)-r)
            dc=np.abs(np.linalg.norm(C[Fselect][:,ij]-center,axis=1)-r)
            rc=C[Fselect][:,ij]-center
            rc=rc/(np.linalg.norm(rc,axis=1)[:,None]+1e-15)
            n=N[Fselect][:,ij]
            good=(dv.max(axis=1)<tol)&(dc<max(.004,tol))&(np.abs((rc*n).sum(axis=1))>.998)
            refined=np.asarray(Fselect[good],dtype=int)
            if len(refined)<60:break
            # Keep a connected component only -- avoid unrelated symmetric radii.
            if len(refined)==len(current) and set(refined)==set(current):break
            current=refined
        if len(current)<60 or r<.25:continue
        # Require a circumferential range as evidence of genuine curvature.
        phi=np.arctan2(C[current][:,ij[1]]-center[1],C[current][:,ij[0]]-center[0])
        phi=np.sort((phi+2*np.pi)%(2*np.pi));ang=2*np.pi-np.diff(np.r_[phi,phi[0]+2*np.pi]).max()
        if np.degrees(ang)<35 or np.ptp(V[np.unique(F[current].ravel())][:,ai])<.3:continue
        a=np.zeros(3);a[ai]=1
        point=np.zeros(3);point[ij]=center
        z=V[np.unique(F[current].ravel())][:,ai]
        point[ai]=float(z.mean())
        prim={'type':'cylinder','axis':a,'point':point,'radius':float(r),
              'tmin':float(z.min()),'tmax':float(z.max()),'faces':current.tolist(),
              'n_faces':len(current),'rms':0.0,'max':tol}
        done.append({'axis':ai,'center':center,'radius':r,'prim':prim,'faces':current})
    return done


def inject_verified_cylinders(res,mesh):
    """Only invoke in an explicitly experimental alternative conversion pass."""
    original=list(res['primitives'])
    # Look for grossly mixed analytic regions that a single primitive cannot fit.
    possible=[]
    for p in original:
        if p.get('type') in ('sphere','plane') and p.get('n_faces',0)>1000 and p.get('rms',0)>.025:
            possible.extend(p['faces'])
    if len(possible)<400:return []
    patches=verified_axial_patches(mesh,possible)
    if not patches:return []
    taken=set()
    added=[]
    for patch in patches:
        subset=set(map(int,patch['faces']))-taken
        if len(subset)<250:continue
        taken.update(subset)
        prim=dict(patch['prim'],faces=sorted(subset),n_faces=len(subset))
        added.append(prim)
    if not added:return []
    # Preserve the coverage invariant; any disconnected leftovers are handled
    # by meshfit_brep's free-region partitioner.
    rebuilt=[]
    for p in res['primitives']:
        kept=set(p['faces'])-taken
        if kept:
            p=dict(p,faces=sorted(kept),n_faces=len(kept));rebuilt.append(p)
    for p in added:rebuilt.append(p)
    res['primitives']=rebuilt
    res['cylindros_verificados']=[{'radio':p['radius'],'caras_malla':p['n_faces']} for p in added]
    return res['cylindros_verificados']
