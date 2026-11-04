"""Ajustar un campo CAD sin modificar las curvas de su perímetro.

La frontera de una superficie B-spline clamped depende sólo de la primera y
última fila de polos. Se fijan ambas y se mide el resto contra las caras de
entrada. La aceptación global contra el STL sigue siendo obligatoria.
"""
import numpy as np
from scipy.interpolate import BSpline
from scipy.sparse import csr_matrix,coo_matrix,vstack,eye
from scipy.sparse.linalg import lsqr
from OCP.Geom import Geom_BSplineSurface
from OCP.ShapeAnalysis import ShapeAnalysis_Surface
from OCP.gp import gp_Pnt

def _knots(surface,direction):
    count=surface.NbUKnots() if direction==0 else surface.NbVKnots()
    k=surface.UKnot if direction==0 else surface.VKnot;m=surface.UMultiplicity if direction==0 else surface.VMultiplicity
    return np.repeat([k(i) for i in range(1,count+1)],[m(i) for i in range(1,count+1)])

def _basis(surface,uv):
    a=BSpline.design_matrix(uv[:,0],_knots(surface,0),surface.UDegree()).tocsr()
    b=BSpline.design_matrix(uv[:,1],_knots(surface,1),surface.VDegree()).tocsr()
    rows=[];cols=[];data=[];nv=surface.NbVPoles()
    for row in range(len(uv)):
        ai=a.indices[a.indptr[row]:a.indptr[row+1]];av=a.data[a.indptr[row]:a.indptr[row+1]]
        bi=b.indices[b.indptr[row]:b.indptr[row+1]];bv=b.data[b.indptr[row]:b.indptr[row+1]]
        rows.extend([row]*(len(ai)*len(bi)));cols.extend((ai[:,None]*nv+bi).ravel());data.extend((av[:,None]*bv).ravel())
    return coo_matrix((data,(rows,cols)),shape=(len(uv),surface.NbUPoles()*nv)).tocsr()

def testigos(faces,count=2000):
    all_points=[]
    for f in faces:
        vs,ts=f.tessellate(.0005,angularTolerance=.035)
        P=np.array([p.toTuple() for p in vs]);tri=P[np.array(ts)];all_points.extend(P);all_points.extend(tri.mean(axis=1))
    points=np.unique(np.round(all_points,11),axis=0)
    if len(points)>count:
        # Deterministic spatial coverage, rather than relying on tessellation
        # order; extrema along the support's axes are kept by the endpoints.
        from scipy.spatial import cKDTree
        span=np.ptp(points,axis=0);active=span>1e-8;scaled=(points[:,active]-points[:,active].min(0))/span[active]
        selected=[int(np.lexsort(scaled.T)[0])];dist=np.full(len(points),np.inf)
        for _ in range(count-1):
            dist=np.minimum(dist,np.sum((scaled-scaled[selected[-1]])**2,axis=1));selected.append(int(np.argmax(dist)))
        points=points[selected]
    return points

def ajustar(surface,faces,*,spans=10,rows_fixed=1,limit=.03,normal_only=True):
    if not isinstance(surface,Geom_BSplineSurface) or surface.IsURational() or surface.IsVRational():raise ValueError('Se requiere soporte polinómico')
    from rechazo_pliegues import exigir_regular
    anchor=max(faces,key=lambda face:face.Area());normal=np.array(anchor.normalAt(anchor.Center()).toTuple());normal/=np.linalg.norm(normal)
    regular_before=exigir_regular(surface,normal)
    s=surface.Copy();s.IncreaseDegree(max(3,s.UDegree()),max(3,s.VDegree()))
    u0,u1,v0,v1=s.Bounds()
    for u in np.linspace(u0,u1,spans+1)[1:-1]:s.InsertUKnot(float(u),1,1e-12,False)
    for v in np.linspace(v0,v1,spans+1)[1:-1]:s.InsertVKnot(float(v),1,1e-12,False)
    if s.NbUPoles()*s.NbVPoles()>6000:raise ValueError('Presupuesto de polos')
    nu,nv=s.NbUPoles(),s.NbVPoles();free=np.array([i*nv+j for i in range(rows_fixed,nu-rows_fixed) for j in range(rows_fixed,nv-rows_fixed)])
    initial=np.array([s.Pole(i+1,j+1).Coord() for i in range(nu) for j in range(nv)])
    points=testigos(faces);proof=[]
    import vtk
    vp=vtk.vtkPoints();vp.SetDataTypeToDouble();cells=vtk.vtkCellArray();offset=0
    for face in faces:
        vs,ts=face.tessellate(.00025,angularTolerance=.035)
        for p in vs:vp.InsertNextPoint(*p.toTuple())
        for tri in ts:
            cells.InsertNextCell(3)
            for k in tri:cells.InsertCellPoint(int(k)+offset)
        offset+=len(vs)
    data=vtk.vtkPolyData();data.SetPoints(vp);data.SetPolys(cells);locator=vtk.vtkStaticCellLocator();locator.SetDataSet(data);locator.BuildLocator()
    us=np.unique(np.r_[np.linspace(u0,u1,45),np.concatenate([np.linspace(s.UKnot(i),s.UKnot(i+1),9) for i in range(1,s.NbUKnots())])])
    vs=np.unique(np.r_[np.linspace(v0,v1,45),np.concatenate([np.linspace(s.VKnot(i),s.VKnot(i+1),9) for i in range(1,s.NbVKnots())])])
    if len(us)*len(vs)>80000:raise ValueError('La carta supera el presupuesto de testigos inversos')
    grid=np.array([(u,v) for u in us for v in vs]);grid_basis=_basis(s,grid)
    for iteration in range(8):
        projection=ShapeAnalysis_Surface(s)
        uv=np.array([projection.ValueOfUV(gp_Pnt(*map(float,p)),1e-10).Coord() for p in points]);uv[:,0]=np.clip(uv[:,0],u0,u1);uv[:,1]=np.clip(uv[:,1],v0,v1)
        basis=_basis(s,uv);poles=np.array([s.Pole(i+1,j+1).Coord() for i in range(nu) for j in range(nv)])
        current=grid_basis@poles;nearest=[]
        for p in current:
            q=[0.,0.,0.];cid=vtk.reference(0);sub=vtk.reference(0);d=vtk.reference(0.);locator.FindClosestPoint(p,q,cid,sub,d);nearest.append(q)
        reverse=np.array(nearest);combined=vstack([basis,grid_basis]).tocsr();targets=np.r_[points,reverse];rhs=targets-combined@poles;A=combined[:,free]
        fit=vstack([A,eye(len(free))*.05]).tocsr()
        if normal_only:
            scalar=lsqr(fit,np.r_[rhs@normal,np.zeros(len(free))],atol=1e-12,btol=1e-12,iter_lim=1500)[0];change=np.outer(scalar,normal)
        else:change=np.column_stack([lsqr(fit,np.r_[rhs[:,dim],np.zeros(len(free))],atol=1e-12,btol=1e-12,iter_lim=1500)[0] for dim in range(3)])
        if not np.isfinite(change).all():raise ValueError('El ajuste interior no tiene coeficientes finitos')
        poles[free]+=change;bound=float(np.linalg.norm(poles-initial,axis=1).max())
        if bound>limit:raise ValueError('El ajuste interior supera la cota de polos: '+str(bound))
        for k in free:s.SetPole(int(k//nv+1),int(k%nv+1),gp_Pnt(*map(float,poles[k])))
        delta=targets-combined@poles;residual=np.linalg.norm(delta,axis=1);normal_error=float(abs(delta@normal).max());proof.append(dict(iteracion=iteration,testigos=len(points),testigos_inversos=len(grid),max_residual_mm=float(residual.max()),max_residual_normal_mm=normal_error,p95_mm=float(np.quantile(residual,.95)),desplazamiento_max_polos_mm=bound))
        print('AJUSTE INTERIOR',proof[-1],flush=True)
        if normal_error<.0001 or (len(proof)>=3 and abs(proof[-2]['max_residual_normal_mm']-normal_error)<max(1e-8,normal_error*.001)):break
    regular_after=exigir_regular(s,normal)
    if regular_before['signo']!=regular_after['signo']:raise ValueError('El ajuste invierte la orientación de la carta')
    return s,dict(metodo='loft_con_interior_medido_y_frontera_fija',ajuste_solo_normal=normal_only,normal=normal.tolist(),regularidad_antes=regular_before,regularidad_despues=regular_after,polos=[nu,nv],filas_fijas=rows_fixed,iteraciones=proof)
