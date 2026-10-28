"""Propuestas acotadas de bandas circulares, sin modificar la malla original.

Solo se ensayan como alternativa a un STEP ya válido y muy fragmentado.
Una propuesta no es una conversión: el B-Rep exportado debe volver a pasar
todos los controles geométricos y topológicos del motor.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import least_squares
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def conviene(calidad, triangulos):
    tipos=calidad.get('tipos_caras',{})
    n=calidad.get('caras_step',0)
    return (triangulos<=5000 and n>=150 and
            tipos.get('GeomAbs_Plane',0)>=.90*n and
            tipos.get('GeomAbs_Cylinder',0)>0 and
            not any(v for k,v in tipos.items() if 'BSpline' in k))


def proponer(result, mesh):
    """Bandas conexas >=300°, vértices y centroides a <=0,011 mm.

    Las aristas con diedro >=30° y los cambios de inclinación delimitan
    bandas diferentes. Se protege así un hexágono y los escalones reales.
    Los ejes provienen de las primitivas existentes y de la base del STL.
    No se redondean centros ni radios a medidas nominales.
    """
    axes=list(np.eye(3))
    for p in result['primitives']:
        if p.get('type') not in ('cone','cylinder'):continue
        a=np.asarray(p['axis'],float);a/=np.linalg.norm(a)
        if not any(abs(np.dot(a,b))>1-1e-6 for b in axes):axes.append(a)
        if len(axes)>=12:break
    F=np.asarray(mesh.faces);V=np.asarray(mesh.vertices)
    C=np.asarray(mesh.triangles_center);N=np.asarray(mesh.face_normals)
    adj=mesh.face_adjacency;patches=[]
    # No superar tampoco la tolerancia local original del constructor.
    tol=min(.011,max(.006,6e-4*float(np.linalg.norm(mesh.extents))))
    for axis in axes:
        ref=np.eye(3)[int(np.argmin(np.abs(axis)))]
        u=np.cross(axis,ref);u/=np.linalg.norm(u);v=np.cross(axis,u)
        basis=np.column_stack((u,v));comp=N@axis
        allowed=((np.abs(comp[adj[:,0]]-comp[adj[:,1]])<.015)&
                 (mesh.face_adjacency_angles<np.radians(30))&
                 (np.abs(comp[adj[:,0]])<.99)&(np.abs(comp[adj[:,1]])<.99))
        links=adj[allowed]
        graph=coo_matrix((np.ones(2*len(links)),
            (np.r_[links[:,0],links[:,1]],np.r_[links[:,1],links[:,0]])),
            shape=(len(F),len(F))).tocsr()
        _,labels=connected_components(graph,directed=False)
        ids,counts=np.unique(labels,return_counts=True)
        for label in ids[counts>=24]:
            faces=np.where(labels==label)[0]
            # Una región plana puede producir un círculo algebraico lejano y
            # un cono casi plano. Exigir giro real de las normales impide ese
            # falso positivo, también en tapas y hexágonos subdivididos.
            nn=N[faces]@basis
            if np.min(np.linalg.norm(nn,axis=1))<.05:continue
            angles=np.sort(np.arctan2(nn[:,1],nn[:,0])%(2*np.pi))
            normal_arc=2*np.pi-np.diff(np.r_[angles,angles[0]+2*np.pi]).max()
            if normal_arc<np.radians(300):continue
            pts=V[np.unique(F[faces])];z=pts@axis;span=float(np.ptp(z))
            if span<.005:continue
            xy=pts@basis
            cx,cy,_=np.linalg.lstsq(np.c_[2*xy,np.ones(len(xy))],
                                   (xy*xy).sum(axis=1),rcond=None)[0]
            center=np.array([cx,cy]);t0=float(z.mean())
            radius=np.linalg.norm(xy-center,axis=1)
            slope,rad=np.polyfit(z-t0,radius,1)
            cc=C[faces]@basis-center
            phi=np.sort(np.arctan2(cc[:,1],cc[:,0])%(2*np.pi))
            arc=2*np.pi-np.diff(np.r_[phi,phi[0]+2*np.pi]).max()
            if arc<np.radians(300):continue
            samples=np.vstack((pts,C[faces]));zz=samples@axis-t0
            projected=samples@basis
            def residual(x):
                return (np.linalg.norm(projected-x[:2],axis=1)-x[2]-x[3]*zz)/np.sqrt(1+x[3]**2)
            fit=least_squares(residual,[cx,cy,rad,slope],max_nfev=100,
                              xtol=1e-12,ftol=1e-12,gtol=1e-12)
            if not fit.success:continue
            x=fit.x;error=residual(x)
            x[2]+=(error.min()+error.max())/2*np.sqrt(1+x[3]**2)
            # A slope rounded to zero must be checked again as a cylinder.
            if abs(x[3])<1e-4:x[3]=0.
            maximum=float(np.max(np.abs(residual(x))))
            if (not np.isfinite(x).all() or maximum>tol or x[2]<.15 or
                    x[2]>3*float(np.linalg.norm(mesh.extents))):continue
            if np.min(x[2]+x[3]*(z-t0))<=.05:continue
            radial=C[faces]@basis-x[:2]
            radial/=np.linalg.norm(radial,axis=1)[:,None]
            normal=(radial@basis.T-x[3]*axis)/np.sqrt(1+x[3]**2)
            if np.min(np.abs((normal*N[faces]).sum(axis=1)))<np.cos(np.radians(10)):continue
            origin=basis@x[:2]+axis*t0;a=axis.copy()
            if x[3]==0:
                p={'type':'cylinder','point':origin.tolist(),'axis':a.tolist(),'radius':float(x[2])}
            else:
                if x[3]<0:a=-a
                t=(pts-origin)@a
                p={'type':'cone','axis':a.tolist(),'origin':origin.tolist(),
                   'b':float(x[2]),'slope':float(abs(x[3])),
                   'half_angle':float(np.arctan(abs(x[3]))),
                   'r_base':float(x[2]+abs(x[3])*t.min()),
                   'r_top':float(x[2]+abs(x[3])*t.max())}
            t=(pts-origin)@a
            p.update(faces=faces.tolist(),n_faces=len(faces),tmin=float(t.min()),
                     tmax=float(t.max()),rms=maximum,max=maximum)
            patches.append(p)
    accepted=[];used=set()
    for p in sorted(patches,key=lambda p:(p['max'],-p['n_faces'])):
        if used.intersection(p['faces']):continue
        accepted.append(p);used.update(p['faces'])
    return accepted


def incorporar(result, mesh):
    patches=proponer(result,mesh)
    if not patches:return []
    used=set(f for p in patches for f in p['faces']);remaining=[]
    for p in result['primitives']:
        faces=set(p['faces'])-used
        if faces:remaining.append(dict(p,faces=sorted(faces),n_faces=len(faces)))
    result['primitives']=patches+remaining
    result['freeform_regions']=[sorted(set(r)-used) for r in result.get('freeform_regions',[]) if set(r)-used]
    result['freeform_faces']=sum(map(len,result['freeform_regions']))
    return [{'tipo':p['type'],'triangulos':p['n_faces'],'max_vertices_centroides_mm':p['max']} for p in patches]


def mejora(antes, despues):
    """Comparar STEP ya validados; conservar precisión y error superficial global.

    Se limita el cambio de volumen a 0,04 puntos porcentuales y el de caja a
    0,003 mm, además de los límites originales. El peor p95 y máximo de ambas
    direcciones densas NO pueden aumentar; no basta con reducir caras.
    """
    if despues['precision_alcanzada']!=antes['precision_alcanzada']:
        return False,'Se conserva el nivel de precisión del STEP inicial.'
    if despues['caras_step']>.85*antes['caras_step']:
        return False,'Reducción de caras inferior al 15 %.'
    if despues['volumen_error_pct']>antes['volumen_error_pct']+.04:
        return False,'Cambio de volumen excesivo respecto al candidato inicial.'
    if despues['caja_error_mm']>antes['caja_error_mm']+.003:
        return False,'Cambio de caja excesivo respecto al candidato inicial.'
    a,b=antes['integridad_cad'],despues['integridad_cad']
    if b['tolerancia_max_mm']>a['tolerancia_max_mm']+.001 or b['tolerancia_p95_mm']>a['tolerancia_p95_mm']+.003:
        return False,'Las tolerancias de las aristas empeoran demasiado.'
    for metric in ('p95_mm','max_mm'):
        old=max(antes['inspeccion_densa'][d][metric] for d in ('stl_a_cad','cad_a_stl'))
        new=max(despues['inspeccion_densa'][d][metric] for d in ('stl_a_cad','cad_a_stl'))
        if new>old+1e-6:return False,'Empeora la desviación superficial densa global.'
    return True,'Menos caras, precisión conservada y errores superficiales globales no mayores.'
