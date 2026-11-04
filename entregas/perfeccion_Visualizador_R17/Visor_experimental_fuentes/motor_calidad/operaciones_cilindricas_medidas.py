"""Rebuild complete source-backed cylindrical bands using two CAD booleans.

The initial circular profile preserves the source wall's enclosed volume; a
bounded correction also preserves the previously accepted CAD solid's volume.
No nominal dimensions or printer tolerances are imposed. The maximum
radial error of every triangle remains bounded by the existing .008 mm limit.
Full downstream CAD, source, material and non-regression validation is required.
"""
import numpy as np
import cadquery as cq
from cilindros_locales import _anillos, _boolean_local, _consolidar_seguro


def consolidar_local(shape,previous):
    """Do not rewrite unrelated faces/edges while simplifying a local Boolean."""
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    from OCP.TopTools import TopTools_IndexedMapOfShape
    old=TopTools_IndexedMapOfShape()
    for f in previous.Faces():old.Add(f.wrapped)
    unify=ShapeUpgrade_UnifySameDomain(shape.wrapped,True,True,False)
    unify.SetSafeInputMode(True);unify.AllowInternalEdges(False)
    for face in shape.Faces():
        if old.Contains(face.wrapped):
            for edge in face.Edges():unify.KeepShape(edge.wrapped)
    unify.Build();return cq.Shape.cast(unify.Shape())




def medir(mesh, primitive):
    if primitive['type']!='cylinder':raise ValueError('No es cilindro')
    ids=np.asarray(primitive['faces'],int);loops=_anillos(mesh,ids)
    V=np.asarray(mesh.vertices);F=np.asarray(mesh.faces);vertices=np.unique(F[ids])
    directions=[]
    for loop in loops:
        p=V[loop];_,_,vh=np.linalg.svd(p-p.mean(0),full_matrices=False);a=vh[-1]
        if np.max(abs((p-p.mean(0))@a))>1e-6:raise ValueError('Anillo no plano')
        directions.append(a)
    if abs(directions[0]@directions[1])<1-1e-9:raise ValueError('Anillos no paralelos')
    a=directions[0]
    if a[np.argmax(abs(a))]<0:a=-a
    e=np.eye(3)[np.argmin(abs(a))];u=np.cross(a,e);u/=np.linalg.norm(u);v=np.cross(a,u);basis=np.column_stack((u,v))
    origin=V[vertices].mean(0);xy=(V[vertices]-origin)@basis
    x,y,off=np.linalg.lstsq(np.c_[2*xy,np.ones(len(xy))],(xy*xy).sum(1),rcond=None)[0]
    center=origin+basis@np.array([x,y]);P=(V-center)@basis;z=(V-center)@a
    radius=float(np.linalg.norm(P[vertices],axis=1).mean());lo=float(z[vertices].min());hi=float(z[vertices].max())
    if radius<.25 or hi-lo<.01:raise ValueError('Pared insuficiente')
    # This test, on actual source vertices, replaces dependence on noisy
    # normals of extremely thin triangles. It is not a looser geometry gate.
    if np.max(abs(np.linalg.norm(P[vertices],axis=1)-radius))>3e-5:raise ValueError('La fuente no confirma una pared circular uniforme')
    areas=[]
    for loop in loops:
        if min(np.max(abs(z[loop]-lo)),np.max(abs(z[loop]-hi)))>1e-6:raise ValueError('Extremo no constante')
        points=P[loop];angles=np.arctan2(points[:,1],points[:,0]);order=np.argsort(angles);p=points[order];angles=angles[order]
        if np.max(np.diff(np.r_[angles,angles[0]+2*np.pi]))>np.radians(16):raise ValueError('Anillo poco resuelto')
        areas.append(abs(float(np.sum(p[:,0]*np.roll(p[:,1],-1)-p[:,1]*np.roll(p[:,0],-1))*.5)))
    # Different polygon sampling at each end is not a conical feature when
    # every ring/source vertex already confirms the same radius above.
    # Exact signed volume of the source wall closed with its two planar rings.
    # Using the bottom-axis origin makes the bottom-cap volume zero and avoids
    # cancellation from large world coordinates. This also handles different
    # angular tessellation at the two ends, unlike averaging their areas.
    local=V[F[ids]]-(center+a*lo)
    radial=(mesh.triangles_center[ids]-center)@basis
    signs=np.sign(np.sum((mesh.face_normals[ids]@basis)*radial,axis=1))
    if np.any(signs!=signs[0]) or signs[0]==0:raise ValueError('Orientación radial inconsistente')
    top_index=int(np.argmax([z[loop].mean() for loop in loops]))
    wall_volume=float(np.einsum('ij,ij->i',local[:,0],np.cross(local[:,1],local[:,2])).sum()/6.)*float(signs[0])
    source_volume=wall_volume+areas[top_index]*(hi-lo)/3.
    if source_volume<=0:raise ValueError('Volumen cerrado del perfil no positivo')
    target=float(np.sqrt(source_volume/((hi-lo)*np.pi)))
    T=P[F[ids]];D=np.roll(T,-1,axis=1)-T;t=np.clip(-np.sum(T*D,axis=2)/np.maximum(np.sum(D*D,axis=2),1e-300),0,1)
    rmin=float(np.linalg.norm(T+t[:,:,None]*D,axis=2).min());rmax=float(np.linalg.norm(T,axis=2).max())
    cross=T[:,:,0]*np.roll(T[:,:,1],-1,axis=1)-T[:,:,1]*np.roll(T[:,:,0],-1,axis=1)
    if np.any(np.all(cross>1e-14,axis=1)|np.all(cross<-1e-14,axis=1)):raise ValueError('Una faceta cruza el eje')
    bound=max(abs(target-rmin),abs(target-rmax))
    if bound>.008:raise ValueError('Supera la cota radial histórica de .008 mm')
    radial=(mesh.triangles_center[ids]-center)@basis;sign=np.sign(np.sum((mesh.face_normals[ids]@basis)*radial,axis=1))
    if np.any(sign!=sign[0]) or sign[0]==0:raise ValueError('Orientación radial inconsistente')
    expected=2*np.pi*radius*(hi-lo)
    if abs(float(mesh.area_faces[ids].sum())/expected-1)>.01:raise ValueError('Cobertura incompleta')
    return dict(axis=a,center=center,radius=target,nominal_fit_radius=radius,lo=lo,hi=hi,
                rmin=rmin,rmax=rmax,sign=int(sign[0]),radial_bound_mm=bound,source_facets=len(ids),profile_areas_mm2=areas,source_profile_volume_mm3=source_volume)


def proponer(shape, mesh, primitives):
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN, TopAbs_OUT
    from OCP.gp import gp_Pnt
    patches=[]
    for primitive in primitives:
        try:p=medir(mesh,primitive)
        except ValueError:continue
        if any(abs(p['axis']@q['axis'])>1-1e-8 and np.linalg.norm(np.cross(p['center']-q['center'],p['axis']))<.001 and abs(p['radius']-q['radius'])<.001 and
               np.linalg.norm(p['center']+p['axis']*p['lo']-q['center']-q['axis']*q['lo'])<.001 and np.linalg.norm(p['center']+p['axis']*p['hi']-q['center']-q['axis']*q['hi'])<.001 for q in patches):continue
        patches.append(p)
    if not patches:raise ValueError('No se han confirmado anillos completos')
    current=shape;records=[]
    for p in patches:
        axis=p['axis'];center=p['center'];lower=p['rmin']-.02;upper=p['rmax']+.02
        if lower<=0:continue
        e=np.eye(3)[np.argmin(abs(axis))];u=np.cross(axis,e);u/=np.linalg.norm(u);v=np.cross(axis,u)
        classifier=BRepClass3d_SolidClassifier(current.wrapped);safe=True
        for h in (.01,.25,.5,.75,.99):
            for theta in np.linspace(0,2*np.pi,48,endpoint=False):
                radial=np.cos(theta)*u+np.sin(theta)*v
                for r,wanted in [(lower,TopAbs_IN if p['sign']>0 else TopAbs_OUT),(upper,TopAbs_OUT if p['sign']>0 else TopAbs_IN)]:
                    point=center+axis*(p['lo']+(p['hi']-p['lo'])*h)+radial*r
                    classifier.Perform(gp_Pnt(*map(float,point)),1e-9)
                    if classifier.State()!=wanted:safe=False;break
                if not safe:break
            if not safe:break
        if not safe:continue
        def cylinder(r):return cq.Solid.makeCylinder(float(r),p['hi']-p['lo'],cq.Vector(*(center+axis*p['lo'])),cq.Vector(*axis))
        outer=cylinder(upper);band=_boolean_local(outer,cylinder(lower));replacement=_boolean_local(outer,cylinder(p['radius']))
        volume_before=current.Volume()
        print('[Operaciones CAD] reconstruyendo perfil',p['radius'],'sobre',len(current.Faces()),'caras',flush=True)
        erased=_boolean_local(current,band,unir=p['sign']>0)
        rebuilt=_boolean_local(erased,replacement,unir=p['sign']<0)
        candidate=consolidar_local(rebuilt,current)
        if len(candidate.Solids())!=1 or not candidate.isValid():continue
        initial_radius=p['radius'];delta=volume_before-candidate.Volume()
        if abs(delta)>max(1e-8,abs(volume_before)*1e-10):
            r2=p['radius']**2+delta/(p['sign']*np.pi*(p['hi']-p['lo']))
            if r2<=0:continue
            corrected=float(np.sqrt(r2));bound=max(abs(corrected-p['rmin']),abs(corrected-p['rmax']))
            if bound>.008:continue
            replacement=_boolean_local(outer,cylinder(corrected))
            candidate=consolidar_local(_boolean_local(erased,replacement,unir=p['sign']<0),current)
            if len(candidate.Solids())!=1 or not candidate.isValid():continue
            p=dict(p,radius=corrected,radial_bound_mm=bound)
        volume_delta=candidate.Volume()-volume_before
        if abs(volume_delta)>max(1e-8,abs(volume_before)*1e-10):continue
        if len(candidate.Faces())>=len(current.Faces()):continue
        record={k:(x.tolist() if hasattr(x,'tolist') else x) for k,x in p.items()}
        record.update(faces_before=len(current.Faces()),faces_after=len(candidate.Faces()),operation='reconstruccion_banda_mediante_dos_booleanos',volume_delta_mm3=volume_delta,initial_source_volume_radius_mm=initial_radius,previous_solid_volume_preserved=True)
        current=candidate;records.append(record);print('[Operaciones CAD]',record,flush=True)
    if not records:raise ValueError('No hay operaciones locales CAD aprobadas')
    return current,records
