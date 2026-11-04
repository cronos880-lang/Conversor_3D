"""Prototipo: ajuste conjunto propuesto y contrastado con los vértices STL."""
import numpy as np
from scipy.optimize import least_squares
from OCP.Geom import Geom_CylindricalSurface,Geom_ToroidalSurface
from OCP.gp import gp_Ax3,gp_Pnt,gp_Dir

def circle(points):
    origin=points.mean(0);p=points-origin
    x,y,c=np.linalg.lstsq(np.c_[2*p,np.ones(len(p))],np.sum(p*p,axis=1),rcond=None)[0]
    center=origin+np.array([x,y]);radius=np.linalg.norm(points-center,axis=1).mean()
    fit=least_squares(lambda q:np.linalg.norm(points-q[:2],axis=1)-q[2],np.r_[center,radius],loss='soft_l1',f_scale=2e-6,xtol=1e-13,ftol=1e-13,gtol=1e-13,max_nfev=200)
    return fit.x[:2],fit.x[2]

def robust_circle(points,triangles,weights,hint):
    rng=np.random.default_rng(20261027);best=None
    candidates=[]
    for _ in range(60):
        ids=rng.choice(len(points),3,replace=False);p=points[ids];mat=2*(p[1:]-p[0])
        if abs(np.linalg.det(mat))<max(1e-15,hint*hint*1e-7):continue
        center=np.linalg.solve(mat,np.sum(p[1:]**2,axis=1)-np.sum(p[0]**2));radius=np.linalg.norm(center-p[0])
        if abs(radius-hint)>.008:continue
        residual=abs(np.linalg.norm(points-center,axis=1)-radius);good=residual[triangles].max(axis=1)<2e-5;area=float(weights[good].sum())
        if best is None or area>best[0]:best=(area,center,radius,good)
    if best is None:raise ValueError('No se verifica un núcleo circular')
    _,center,radius,good=best
    vertices=np.unique(triangles[good]);center,radius=circle(points[vertices])
    return center,radius

def fit_native(faces,surfaces,mesh):
    out=list(surfaces);records=[];support={}
    for i,s in enumerate(surfaces):
        if not isinstance(s,Geom_CylindricalSurface):continue
        a=np.array(s.Axis().Direction().Coord());q=np.array(s.Location().Coord());bb=faces[i].BoundingBox();C=mesh.triangles_center
        radial=C-q-np.outer((C-q)@a,a);rho=np.linalg.norm(radial,axis=1)
        mask=(abs(rho-s.Radius())<.008)&(abs(mesh.face_normals@a)<.1)
        vertex_rho=np.linalg.norm(np.cross(mesh.vertices-q,a),axis=1)
        mask &= np.all(abs(vertex_rho[mesh.faces]-s.Radius())<.008,axis=1)
        mask &= np.all((C>=np.array([bb.xmin,bb.ymin,bb.zmin])-.001)&(C<=np.array([bb.xmax,bb.ymax,bb.zmax])+.001),axis=1)
        ids=np.flatnonzero(mask)
        if len(ids)<12:continue
        vertices=np.unique(mesh.faces[ids]);V=mesh.vertices[vertices]
        def residual_cyl(params,points):
            axis=params[3:6]/np.linalg.norm(params[3:6]);return np.r_[np.linalg.norm(np.cross(points-params[:3],axis),axis=1)-params[6],((params[:3]-q)@a)*.001]
        fit=least_squares(lambda p:residual_cyl(p,V),np.r_[q,a,s.Radius()],loss='soft_l1',f_scale=2e-6,xtol=1e-13,ftol=1e-13,gtol=1e-13,max_nfev=200)
        newq=fit.x[:3];axis=fit.x[3:6]/np.linalg.norm(fit.x[3:6]);radius=fit.x[6]
        if axis@a<0:axis=-axis
        if radius<=0 or abs(radius-s.Radius())>.008 or np.linalg.norm(np.cross(axis,a))>.001:continue
        error=np.abs(np.linalg.norm(np.cross(mesh.vertices[mesh.faces[ids]]-newq,axis),axis=2)-radius).max(axis=1)
        good=error<2e-5
        if mesh.area_faces[ids[good]].sum()<.5*faces[i].Area():continue
        ids=ids[good];V=mesh.vertices[np.unique(mesh.faces[ids])]
        fit=least_squares(lambda p:residual_cyl(p,V),fit.x,loss='soft_l1',f_scale=2e-6,xtol=1e-13,ftol=1e-13,gtol=1e-13,max_nfev=200)
        newq=fit.x[:3];axis=fit.x[3:6]/np.linalg.norm(fit.x[3:6]);radius=fit.x[6]
        if axis@a<0:axis=-axis
        if max(abs(np.linalg.norm(np.cross(V-newq,axis),axis=1)-radius))>2e-5:continue
        out[i]=Geom_CylindricalSurface(gp_Ax3(gp_Pnt(*map(float,newq)),gp_Dir(*map(float,axis))),float(radius))
        print('AJUSTE CILINDRO',i,'R',s.Radius(),'->',radius,'error',max(error[good]),flush=True)
        records.append(dict(cara=i,tipo='cylinder',radio=radius))
        support[i]=V
    from OCP.Geom import Geom_Plane
    for i,V in support.items():
        for _ in range(2):
            for plane in out:
                if not isinstance(plane,Geom_Plane):continue
                cy=out[i];axis=np.array(cy.Axis().Direction().Coord());q=np.array(cy.Location().Coord());radius=cy.Radius()
                n=np.array(plane.Axis().Direction().Coord());p=np.array(plane.Location().Coord());d=(q-p)@n
                if abs(axis@n)>1e-4 or abs(abs(d)-radius)>2e-5:continue
                a=axis-n*(axis@n);a/=np.linalg.norm(a);newq=q+n*(np.copysign(radius,d)-d)
                error=abs(np.linalg.norm(np.cross(V-newq,a),axis=1)-radius).max()
                if error<=2e-5:
                    out[i]=Geom_CylindricalSurface(gp_Ax3(gp_Pnt(*map(float,newq)),gp_Dir(*map(float,a))),radius)
                    print('TANGENCIA MEDIDA',i,'error fuente',error,flush=True)
    return out,records
