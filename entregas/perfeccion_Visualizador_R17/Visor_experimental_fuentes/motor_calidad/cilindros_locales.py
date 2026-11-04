"""Propuestas locales de cilindros completos sobre una frontera CAD facetada.

No cambia el STL ni los umbrales del validador. Cada pared exige dos anillos
cerrados, planos y coaxiales, apoyo en TODAS sus facetas y una cota radial
global de 0,008 mm. Las operaciones CAD se validan después contra el original.
"""
from __future__ import annotations
import numpy as np

CONTROL_RADIAL_MM = .008


def _boolean_local(shape,tool,*,unir=False):
    """Un intento rechazado no puede modificar el B-Rep que se conserva."""
    import cadquery as cq
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut,BRepAlgoAPI_Fuse
    from OCP.TopTools import TopTools_ListOfShape
    arguments=TopTools_ListOfShape();arguments.Append(shape.wrapped)
    tools=TopTools_ListOfShape();tools.Append(tool.wrapped)
    operation=BRepAlgoAPI_Fuse() if unir else BRepAlgoAPI_Cut()
    operation.SetArguments(arguments);operation.SetTools(tools)
    operation.SetNonDestructive(True);operation.SetRunParallel(False);operation.SetFuzzyValue(0.)
    operation.Build()
    if not operation.IsDone():raise ValueError('El booleano local no se ha completado')
    return cq.Shape.cast(operation.Shape())


def _consolidar_seguro(shape):
    import cadquery as cq
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    operation=ShapeUpgrade_UnifySameDomain(shape.wrapped,True,True,True)
    operation.SetSafeInputMode(True);operation.AllowInternalEdges(False);operation.Build()
    return cq.Shape.cast(operation.Shape())


def _anillos(mesh, ids):
    """Dos ciclos de borde, sin ranuras, bifurcaciones ni caras no manifold."""
    edges=mesh.faces[ids][:,[0,1,1,2,2,0]].reshape(-1,2)
    edges,counts=np.unique(np.sort(edges,axis=1),axis=0,return_counts=True)
    if np.any(counts>2):raise ValueError('Pared no manifold')
    boundary=edges[counts==1];neighbors={}
    for a,b in boundary:
        neighbors.setdefault(int(a),[]).append(int(b));neighbors.setdefault(int(b),[]).append(int(a))
    if not neighbors or any(len(n)!=2 for n in neighbors.values()):raise ValueError('Borde no cíclico')
    unseen=set(neighbors);loops=[]
    while unseen:
        seed=min(unseen);todo=[seed];component=set()
        while todo:
            v=todo.pop()
            if v in component:continue
            component.add(v);todo.extend(neighbors[v])
        unseen-=component;loops.append(np.asarray(sorted(component),int))
    if len(loops)!=2 or min(map(len,loops))<24:raise ValueError('No hay dos anillos suficientemente resueltos')
    return loops


def confirmar(mesh, primitive):
    """Medir el intervalo radial de todas las facetas, incluidos sus interiores."""
    if primitive.get('type')!='cylinder':raise ValueError('No es una propuesta cilíndrica')
    ids=np.asarray(primitive['faces'],int)
    if len(ids)<48:raise ValueError('Apoyo insuficiente')
    loops=_anillos(mesh,ids);V=np.asarray(mesh.vertices);F=np.asarray(mesh.faces)
    normals=[]
    for loop in loops:
        points=V[loop];center=points.mean(0)
        _,singular,vh=np.linalg.svd(points-center,full_matrices=False)
        normal=vh[-1]
        if np.max(np.abs((points-center)@normal))>1e-6:raise ValueError('Extremo no plano')
        normals.append(normal)
    if abs(normals[0]@normals[1])<1-1e-9:raise ValueError('Extremos no paralelos')
    axis=normals[0]
    if axis[np.argmax(np.abs(axis))]<0:axis=-axis
    helper=np.eye(3)[np.argmin(np.abs(axis))];u=np.cross(axis,helper);u/=np.linalg.norm(u);v=np.cross(axis,u)
    basis=np.column_stack((u,v));vertices=np.unique(F[ids]);points=V[vertices]
    origin=points.mean(0);xy=(points-origin)@basis
    x,y,c=np.linalg.lstsq(np.c_[2*xy,np.ones(len(xy))],np.sum(xy*xy,axis=1),rcond=None)[0]
    center=origin+basis@np.array([x,y]);projected=(V-center)@basis
    radial=np.linalg.norm(projected[vertices],axis=1);radius=radial.mean()
    if radius<.25 or np.max(np.abs(radial-radius))>1e-5:raise ValueError('Anillos no circulares o no coaxiales')
    z=(V-center)@axis;lo=float(z[vertices].min());hi=float(z[vertices].max())
    if hi-lo<.01:raise ValueError('Pared demasiado corta')
    for loop in loops:
        zz=z[loop]
        if min(np.max(abs(zz-lo)),np.max(abs(zz-hi)))>1e-6:raise ValueError('El anillo no delimita la pared')
        phi=np.sort(np.arctan2(projected[loop,1],projected[loop,0])%(2*np.pi))
        if np.max(np.diff(np.r_[phi,phi[0]+2*np.pi]))>np.radians(16):raise ValueError('Anillo incompleto o polígono poco resuelto')
    # Una pared cilíndrica no puede dar una vuelta doble ni invertir material.
    normals3=mesh.face_normals[ids]
    if np.max(np.abs(normals3@axis))>1e-5:raise ValueError('Pared cónica o deformada')
    centers=(mesh.triangles_center[ids]-center)@basis
    sign=np.sign(np.sum((normals3@basis)*centers,axis=1))
    if not np.all(sign==sign[0]) or sign[0]==0:raise ValueError('Orientación radial inconsistente')
    if abs(float(mesh.area_faces[ids].sum())/(2*np.pi*radius*(hi-lo))-1)>.01:
        raise ValueError('Cobertura superficial incompleta')
    # Cada triángulo tiene normales perpendiculares al eje: su proyección
    # radial es un segmento. El mínimo está en ese segmento, no en su centroide.
    triangles=projected[F[ids]];a=triangles;b=np.roll(triangles,-1,axis=1);d=b-a
    t=np.clip(-np.sum(a*d,axis=2)/np.maximum(np.sum(d*d,axis=2),1e-300),0.,1.)
    rmin=float(np.linalg.norm(a+t[:,:,None]*d,axis=2).min());rmax=float(radial.max())
    # Radio exterior envolvente: una sola unión/resta elimina las facetas sin
    # desmontar y volver a pegar paredes que delimitan cavidades cerradas.
    # El margen es numérico, se incluye entero en la cota de 0,008 mm.
    target=rmax+2e-6;bound=target-rmin
    if bound>CONTROL_RADIAL_MM:raise ValueError('El cilindro supera la cota radial local')
    return {'eje':axis,'centro':center,'radio':target,'radio_min':rmin,'radio_max':rmax,
            'lo':lo,'hi':hi,'signo':int(sign[0]),'caras_fuente':len(ids),'cota_radial_mm':bound,
            'vertices_fuente':vertices,'caras_indices':ids}


def propuestas(mesh, result):
    import trimesh
    from invariantes_material import InvariantesMaterial
    groups=list(trimesh.graph.connected_components(mesh.face_adjacency,nodes=np.arange(len(mesh.faces)),min_len=1))
    owner=np.empty(len(mesh.faces),int)
    for index,group in enumerate(groups):owner[group]=index
    accepted=[]
    for region,prim in enumerate(result['primitives']):
        try:p=confirmar(mesh,prim)
        except ValueError:continue
        p['region_fuente']=region
        if any(len(np.intersect1d(p['caras_indices'],q['caras_indices'])) for q in accepted):continue
        p['vaciado_completo']=False
        if p['signo']<0:
            group=np.asarray(groups[owner[p['caras_indices'][0]]],int)
            remaining=np.setdiff1d(group,p['caras_indices'])
            if len(remaining) and InvariantesMaterial.volumen(mesh.vertices,mesh.faces[group])<0:
                # Un vacío independiente completamente cilíndrico: el resto
                # de su envolvente son exclusivamente los dos discos planos.
                points=mesh.vertices[mesh.faces[remaining]]
                zz=(points-p['centro'])@p['eje']
                axial=np.abs(mesh.face_normals[remaining]@p['eje'])
                planes=np.minimum(np.max(abs(zz-p['lo']),axis=1),np.max(abs(zz-p['hi']),axis=1))
                if np.all(axial>1-1e-10) and np.all(planes<1e-6):p['vaciado_completo']=True
        accepted.append(p)
    return accepted


def reconstruir(shape, patches):
    """Sustituir sólo la banda radial confirmada y conservar el resto del CAD."""
    import cadquery as cq
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_IN,TopAbs_OUT
    from OCP.gp import gp_Pnt
    classifier=BRepClass3d_SolidClassifier(shape.wrapped)
    operations=[]
    for index,p in enumerate(patches,1):
        print('[Cilindros locales] contrastando pared',index,'/',len(patches),flush=True)
        axis=p['eje'];center=p['centro'];lo=p['lo'];hi=p['hi']
        inner=p['radio_min']-.01;outer=p['radio_max']+.01
        if inner<=0:continue
        helper=np.eye(3)[np.argmin(abs(axis))];u=np.cross(axis,helper);u/=np.linalg.norm(u);v=np.cross(axis,u)
        # Rechazar bandas que alcancen una pared vecina, ranura o isla real.
        valid=True
        for fraction in (.01,.5,.99):
            for theta in np.linspace(0,2*np.pi,24,endpoint=False):
                direction=np.cos(theta)*u+np.sin(theta)*v
                for radius,expected in [(inner,TopAbs_IN if p['signo']>0 else TopAbs_OUT),
                                        (outer,TopAbs_OUT if p['signo']>0 else TopAbs_IN)]:
                    point=center+axis*(lo+(hi-lo)*fraction)+radius*direction
                    classifier.Perform(gp_Pnt(*map(float,point)),1e-9)
                    if classifier.State()!=expected:valid=False;break
                if not valid:break
            if not valid:break
        if not valid:continue
        start=center+axis*lo
        def cylinder(radius):return cq.Solid.makeCylinder(float(radius),hi-lo,cq.Vector(*start),cq.Vector(*axis))
        band=cylinder(p['radio']) if p.get('vaciado_completo') else _boolean_local(cylinder(p['radio']),cylinder(inner))
        record={k:(value.tolist() if isinstance(value,np.ndarray) else value) for k,value in p.items() if k not in ('vertices_fuente','caras_indices')}
        operations.append((p['signo'],band,record))
    if not operations:raise ValueError('No hay paredes cilíndricas locales verificables')
    print('[Cilindros locales] paredes a reconstruir:',len(operations),flush=True)
    result=shape;records=[]
    for index,(sign,band,record) in enumerate(operations,1):
        print('[Cilindros locales] operación',index,'/',len(operations),flush=True)
        raw=_boolean_local(result,band,unir=sign>0)
        candidate=_consolidar_seguro(raw)
        if (len(candidate.Solids())!=1 or not candidate.isValid()) and len(raw.Solids())==1 and raw.isValid():
            print('[Cilindros locales] se conserva el booleano sin consolidación opcional',flush=True)
            candidate=raw
        if len(candidate.Solids())!=1 or not candidate.isValid():
            print('[Cilindros locales] operación descartada; se conserva el sólido previo',flush=True)
            continue
        result=candidate;records.append(record)
    if not records:raise ValueError('Ninguna sustitución local produce un sólido válido')
    return result,records
