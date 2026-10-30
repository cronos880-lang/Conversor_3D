"""Descomposición local de contactos de una frontera orientada.

No rellena agujeros, no elimina caras ni decide qué volumen es material.
La entrada debe ser una frontera previamente clasificada. Se separan sus
abanicos e incidencias múltiples; la geometría todavía puede tocarse y debe
regularizarse y validarse antes de aceptar una reparación.
"""
from __future__ import annotations
from collections import defaultdict
import numpy as np
import trimesh


def descomponer_contactos(mesh):
    """Emparejar las caras que delimitan cada cuña de material.

    Al recorrer una arista orientada, el material queda entre una incidencia
    inversa y la siguiente directa en el giro positivo. Una arista que une
    varias cuñas se subdivide por separado para cada pareja; así no se vuelven
    a identificar dos aristas distintas que tengan extremos coincidentes.
    La subdivisión conserva exactamente el plano y la orientación de la cara.
    """
    F=np.asarray(mesh.faces,dtype=np.int64);V=np.asarray(mesh.vertices,float)
    incident=defaultdict(list)
    for fi,face in enumerate(F):
        for k in range(3):
            a,b=int(face[k]),int(face[(k+1)%3])
            if a==b:raise ValueError('Cara con arista de longitud topológica cero.')
            incident[tuple(sorted((a,b)))].append((fi,k,a<b))
    parent=np.arange(3*len(F));rank=np.zeros(len(parent),np.int8)
    def find(a):
        while parent[a]!=a:
            parent[a]=parent[parent[a]];a=int(parent[a])
        return a
    def union(a,b):
        a,b=find(a),find(b)
        if a==b:return
        if rank[a]<rank[b]:a,b=b,a
        parent[b]=a
        if rank[a]==rank[b]:rank[a]+=1
    special={};details=[]
    for edge,items in incident.items():
        if len(items)<2 or len(items)%2:
            raise ValueError('La frontera contiene una abertura o incidencia impar.')
        positive=[item for item in items if item[2]]
        negative=[item for item in items if not item[2]]
        if len(positive)!=len(negative):
            raise ValueError('La orientación no equilibra las caras en una arista.')
        if len(items)==2:pairs=[(negative[0],positive[0])]
        else:
            a,b=edge;axis=V[b]-V[a];length=np.linalg.norm(axis)
            if length<1e-15:raise ValueError('Arista geométrica colapsada: no se infiere una cuña.')
            axis/=length;ref=np.eye(3)[int(np.argmin(np.abs(axis)))]
            x=np.cross(axis,ref);x/=np.linalg.norm(x);y=np.cross(axis,x)
            def angle(item):
                fi,k,_=item;radial=V[F[fi,(k+2)%3]]-(V[a]+V[b])/2
                return float(np.arctan2(radial@y,radial@x)%(2*np.pi))
            remaining=list(positive);pairs=[]
            for neg in sorted(negative,key=angle):
                start=angle(neg)
                pos=min(remaining,key=lambda p:((angle(p)-start)%(2*np.pi),p[0]))
                pairs.append((neg,pos));remaining.remove(pos)
            details.append({'arista':list(edge),'incidencias':len(items),
                            'parejas':[[n[0],p[0]] for n,p in pairs]})
        for pair_id,(neg,pos) in enumerate(pairs):
            nf,nk,_=neg;pf,pk,_=pos
            # Negative halfedge b->a; positive halfedge a->b.
            union(3*nf+(nk+1)%3,3*pf+pk)
            union(3*nf+nk,3*pf+(pk+1)%3)
            if len(items)>2:
                token=(edge,pair_id)
                special[(nf,nk)]=token;special[(pf,pk)]=token
    roots={};vertices=[];corner=np.empty_like(F)
    for fi,face in enumerate(F):
        for k,v in enumerate(face):
            root=find(3*fi+k)
            if root not in roots:
                roots[root]=len(vertices);vertices.append(V[v].tolist())
            corner[fi,k]=roots[root]
    mids={};faces=[];sources=[]
    for fi,face in enumerate(F):
        if not any((fi,k) in special for k in range(3)):
            faces.append(corner[fi].tolist());sources.append(fi);continue
        center=len(vertices);vertices.append(V[face].mean(axis=0).tolist())
        for k in range(3):
            a,b=int(corner[fi,k]),int(corner[fi,(k+1)%3])
            token=special.get((fi,k))
            if token is None:
                faces.append([a,b,center]);sources.append(fi)
            else:
                if token not in mids:
                    mids[token]=len(vertices)
                    vertices.append(((V[face[k]]+V[face[(k+1)%3]])/2).tolist())
                mid=mids[token]
                faces.extend(([a,mid,center],[mid,b,center]));sources.extend((fi,fi))
    candidate=trimesh.Trimesh(vertices,faces,process=False)
    from topologia_vertices import inspeccionar_vertices
    report=inspeccionar_vertices(candidate)
    if not candidate.is_watertight or not candidate.is_winding_consistent or report['vertices_no_manifold']:
        raise ValueError('La descomposición no produce superficies cerradas regulares.')
    # Mantener información geométrica para el control independiente posterior.
    geometry_error=abs(candidate.volume-mesh.volume)
    if geometry_error>max(1e-9,abs(mesh.volume)*1e-10):
        raise ValueError('La subdivisión no conserva el volumen orientado.')
    proof={'caras_antes':len(F),'caras_despues':len(candidate.faces),
           'aristas_de_contacto':details,'superficies_fuente':sources,
           'diferencia_volumen_mm3':float(geometry_error),
           'geometria':'Mismas caras, o subdivisiones dentro de sus planos; sin desplazar ni borrar superficies.',
           'requiere_regularizacion_geometrica':True}
    return candidate,proof


def compactar_aristas_cortas(mesh, *, limite_mm=1e-6, validar=None, max_colapsos=2000,
                           probar_punto_medio=False):
    """Colapsos sujetos a la condición de enlace, sin borrar cavidades.

    Solo se suprimen las dos caras incidentes en una arista más corta que el
    límite. Sus puntos quedan a esa distancia de las caras resultantes. La
    condición de enlace y el rechazo de caras duplicadas preservan la
    topología. El validador opcional puede vetar cada propuesta geométrica.
    """
    original=mesh.copy();candidate=mesh.copy();records=[]
    for _ in range(max_colapsos):
        F=candidate.faces;V=candidate.vertices
        edges=np.unique(np.sort(candidate.edges,axis=1),axis=0)
        lengths=np.linalg.norm(V[edges[:,0]]-V[edges[:,1]],axis=1)
        choices=np.where(lengths<limite_mm)[0]
        if not len(choices):break
        incident=[set() for _ in V]
        for fi,face in enumerate(F):
            for v in face:incident[v].add(fi)
        applied=False
        for ei in choices[np.argsort(lengths[choices])]:
            a,b=map(int,edges[ei]);shared=incident[a]&incident[b]
            if len(shared)!=2:continue
            na=set(F[list(incident[a])].ravel())-{a,b}
            nb=set(F[list(incident[b])].ravel())-{a,b}
            opposite=set(F[list(shared)].ravel())-{a,b}
            if len(opposite)!=2 or na&nb!=opposite:continue
            placements=[(a,b,False),(b,a,False)]
            if probar_punto_medio:placements.append((a,b,True))
            for keep,remove,midpoint in placements:
                new=F.copy();new[new==remove]=keep
                retained=np.ones(len(new),bool);retained[list(shared)]=False
                new=new[retained]
                if (np.any(np.diff(np.sort(new,axis=1),axis=1)==0) or
                        len(np.unique(np.sort(new,axis=1),axis=0))!=len(new)):continue
                vertices=V.copy()
                if midpoint:vertices[keep]=(V[a]+V[b])/2
                proposal=trimesh.Trimesh(vertices,new,process=False)
                proposal.remove_unreferenced_vertices()
                if (not proposal.is_watertight or not proposal.is_winding_consistent or
                        proposal.euler_number!=candidate.euler_number):continue
                if validar is not None and not validar(proposal):continue
                records.append({'longitud_mm':float(lengths[ei]),'caras_antes':len(F),
                                'caras_despues':len(new)})
                candidate=proposal;applied=True;break
            if applied:break
        if not applied:break
    return candidate,{'colapsos':records,'limite_mm':limite_mm,
                      'euler_antes':int(original.euler_number),
                      'euler_despues':int(candidate.euler_number),
                      'principio':'Condición de enlace y validación geométrica por propuesta.'}


def contraer_microaristas_generadas(mesh, *, limite_mm=1e-7, validar=None):
    """Regularizar aristas nuevas inferiores a la resolución CAD.

    Uso exclusivo sobre una frontera reconstruida; no es una limpieza general
    de STL. La contracción puede cancelar pares opuestos y microciclos. Debe
    comprobarse después la geometría contra la referencia independiente y
    conservarse cada componente de material. No cambia ningún umbral CAD.
    """
    candidate=mesh.copy();records=[]
    for iteration in range(500):
        F,V=candidate.faces,candidate.vertices
        edges=np.unique(np.sort(candidate.edges,axis=1),axis=0)
        lengths=np.linalg.norm(V[edges[:,0]]-V[edges[:,1]],axis=1)
        choices=np.where(lengths<limite_mm)[0];changed=False
        if not len(choices):break
        positive_before=sum(p.volume>0 for p in candidate.split(only_watertight=False))
        for ei in choices[np.argsort(lengths[choices])]:
            for keep,remove in (edges[ei],edges[ei][::-1]):
                faces=F.copy();faces[faces==remove]=keep
                regular=np.all(np.diff(np.sort(faces,axis=1),axis=1)!=0,axis=1)
                faces=faces[regular]
                keys,inverse,counts=np.unique(np.sort(faces,axis=1),axis=0,
                                             return_inverse=True,return_counts=True)
                retained=np.ones(len(faces),bool);consistent=True;cancelled=0
                for bucket in np.where(counts>1)[0]:
                    ids=np.where(inverse==bucket)[0];tri=faces[ids]
                    sign=np.sign((tri[:,1]-tri[:,0])*(tri[:,2]-tri[:,1])*(tri[:,0]-tri[:,2]))
                    plus,minus=ids[sign>0],ids[sign<0];n=min(len(plus),len(minus))
                    if abs(len(plus)-len(minus))>1:consistent=False;break
                    retained[plus[:n]]=False;retained[minus[:n]]=False;cancelled+=2*n
                if not consistent:continue
                proposal=trimesh.Trimesh(V.copy(),faces[retained],process=False)
                proposal.remove_unreferenced_vertices()
                if not len(proposal.faces) or not proposal.is_watertight or not proposal.is_winding_consistent:continue
                from topologia_vertices import inspeccionar_vertices
                if inspeccionar_vertices(proposal)['vertices_no_manifold']:continue
                if sum(p.volume>0 for p in proposal.split(only_watertight=False))!=positive_before:continue
                if validar is not None and not validar(proposal):continue
                records.append({'longitud_mm':float(lengths[ei]),'pares_cancelados':cancelled//2,
                                'euler_antes':int(candidate.euler_number),
                                'euler_despues':int(proposal.euler_number)})
                candidate=proposal;changed=True;break
            if changed:break
        if not changed:break
    return candidate,{'limite_mm':limite_mm,'contracciones':records,
                      'nota':'Exige contraste geométrico posterior; la topología de una entrada defectuosa no es referencia válida.'}


def regiones_planas_protegidas(mesh, radio_mm=.03):
    """Proteger el entorno de microaristas y las paredes de cavidades.

    El motor conserva su ajuste de superficies fuera de estas zonas. Dentro
    se usan planos de los propios triángulos, agrupados por coincidencia; no
    se proyecta una cavidad microscópica a un cilindro situado a centésimas.
    """
    from OCP.Geom import Geom_Plane
    from OCP.gp import gp_Pln,gp_Pnt,gp_Dir
    edges=mesh.edges_unique;length=mesh.edges_unique_length
    short=edges[length<.002]
    points=mesh.vertices[np.unique(short)] if len(short) else np.empty((0,3))
    if len(points):
        _,ids=np.unique(np.round(points/.005).astype(np.int64),axis=0,return_index=True)
        points=points[ids]
    triangles=mesh.triangles;low=triangles.min(axis=1);high=triangles.max(axis=1)
    selected=np.zeros(len(mesh.faces),bool)
    for point in points:
        selected|=np.all(low<=point+radio_mm,axis=1)&np.all(high>=point-radio_mm,axis=1)
    for part in mesh.split(only_watertight=False):
        if part.volume<0:
            selected|=np.all(low<=part.bounds[1]+radio_mm,axis=1)&np.all(high>=part.bounds[0]-radio_mm,axis=1)
    groups=defaultdict(list)
    normals=mesh.face_normals;centers=mesh.triangles_center
    for fi in range(len(mesh.faces)):
        n=normals[fi]
        if np.linalg.norm(n)<.9:raise ValueError('Triángulo colapsado en la zona protegida.')
        key=tuple(np.round(n,10))+(round(float(centers[fi]@n),9),)
        groups[key].append(int(fi))
    regions=[]
    for ids in groups.values():
        if not np.any(selected[ids]):continue
        selected[ids]=True
        n=normals[ids[0]];origin=mesh.vertices[mesh.faces[ids[0],0]]
        error=np.max(np.abs((mesh.vertices[np.unique(mesh.faces[ids])]-origin)@n))
        if error>1e-8:
            for fi in ids:
                n=normals[fi];origin=mesh.vertices[mesh.faces[fi,0]]
                regions.append(([fi],Geom_Plane(gp_Pln(gp_Pnt(*map(float,origin)),gp_Dir(*map(float,n))))))
        else:
            regions.append((ids,Geom_Plane(gp_Pln(gp_Pnt(*map(float,origin)),gp_Dir(*map(float,n))))))
    return regions,{'triangulos_protegidos':int(selected.sum()),'regiones_planas':len(regions),
                    'radio_mm':radio_mm,'microarista_mm':.002}
