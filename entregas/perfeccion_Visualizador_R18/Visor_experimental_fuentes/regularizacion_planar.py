"""Cancelar exclusivamente superficies planas coincidentes de sentidos opuestos.

Un fondo de cavidad de espesor cero puede coincidir con una cara exterior.
La carcasa es estanca topológicamente, pero se interseca consigo misma. Aquí
se resta la cobertura opuesta en el mismo plano; no se rellenan aberturas,
no se inventan vértices y se exige la misma frontera orientada del parche.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import numpy as np

PLANO_EPS_MM = 5e-10


def _frontera(faces):
    edges = Counter()
    for tri in faces:
        for a,b in zip(tri,np.roll(tri,-1)):
            a,b=int(a),int(b)
            edges[(min(a,b),max(a,b))] += 1 if a<b else -1
    return {key:value for key,value in edges.items() if value}


def regularizar_cancelaciones_planas(mesh):
    import shapely
    import trimesh
    from scipy.spatial import cKDTree
    groups=defaultdict(list)
    normals=mesh.face_normals
    for i,n in enumerate(normals):
        canonical=n.copy()
        if canonical[np.argmax(abs(canonical))]<0:canonical=-canonical
        offset=float(mesh.triangles_center[i]@canonical)
        key=tuple(np.round(canonical,10))+ (round(offset,9),)
        groups[key].append(i)
    tree=cKDTree(mesh.vertices)
    replacements={}; details=[]
    for ids in groups.values():
        ids=np.asarray(ids,int)
        if len(ids)<4:continue
        n=normals[ids[0]].copy()
        if n[np.argmax(abs(n))]<0:n=-n
        signs=normals[ids]@n
        if not ((signs>0).any() and (signs<0).any()):continue
        points=mesh.vertices[np.unique(mesh.faces[ids])]
        origin=points.mean(0)
        if np.max(abs((points-origin)@n))>PLANO_EPS_MM:continue
        if np.min(abs(signs))<1-1e-12:continue
        ref=np.eye(3)[np.argmin(abs(n))]
        x=np.cross(n,ref);x/=np.linalg.norm(x);y=np.cross(n,x)
        uv=np.column_stack(((mesh.vertices-origin)@x,(mesh.vertices-origin)@y))
        positive=[shapely.Polygon(uv[mesh.faces[i]]) for i in ids[signs>0]]
        negative=[shapely.Polygon(uv[mesh.faces[i]]) for i in ids[signs<0]]
        pos,neg=shapely.union_all(positive),shapely.union_all(negative)
        area_eps=max(1e-10,(pos.area+neg.area)*1e-10)
        overlap=pos.intersection(neg).area
        if overlap<=area_eps:continue
        if (abs(sum(p.area for p in positive)-pos.area)>area_eps or
                abs(sum(p.area for p in negative)-neg.area)>area_eps):
            raise ValueError('Cobertura plana con multiplicidad del mismo sentido: no se regulariza.')
        new_faces=[]
        for region,sign in ((pos.difference(neg),1),(neg.difference(pos),-1)):
            if region.is_empty:continue
            for tri in shapely.constrained_delaunay_triangles(region).geoms:
                coords=np.asarray(tri.exterior.coords)[:3]
                xyz=origin+coords[:,0,None]*x+coords[:,1,None]*y
                distance,indices=tree.query(xyz)
                if np.max(distance)>1e-9:
                    raise ValueError('La cancelación requeriría inventar vértices; entrada ambigua.')
                verts=mesh.vertices[indices]
                direction=float(np.cross(verts[1]-verts[0],verts[2]-verts[0])@n)
                if direction*sign<0:indices=indices[::-1]
                new_faces.append(indices)
        if _frontera(mesh.faces[ids]) != _frontera(new_faces):
            raise ValueError('La regularización altera la frontera orientada del parche.')
        signed_before=float(mesh.area_faces[ids]@np.sign(signs))
        signed_after=pos.area-neg.area
        if abs(signed_before-signed_after)>area_eps:
            raise ValueError('La cancelación plana no conserva el área orientada.')
        replacements[int(ids[0])]=(ids,np.asarray(new_faces,dtype=int).reshape(-1,3))
        details.append({'normal':n.tolist(),'punto_plano':origin.tolist(),
                        'caras_antes':len(ids),'caras_despues':len(new_faces),
                        'area_coincidente_cancelada_mm2':float(overlap),
                        'frontera_orientada_identica':True,'vertices_nuevos':0,'vertices_movidos':0})
    if not replacements:return mesh,{'aplicado':False}
    removed=set(int(i) for ids,_ in replacements.values() for i in ids)
    faces=[f for i,f in enumerate(mesh.faces) if i not in removed]
    for _,new in replacements.values():faces.extend(new)
    candidate=trimesh.Trimesh(mesh.vertices.copy(),np.asarray(faces),process=False)
    candidate.remove_unreferenced_vertices()
    difference=abs(candidate.volume-mesh.volume)
    if (not candidate.is_watertight or not candidate.is_winding_consistent or candidate.volume<=0
            or difference>max(1e-8,abs(mesh.volume)*1e-10)
            or np.max(abs(candidate.bounds-mesh.bounds))>1e-9):
        raise ValueError('La cancelación no conserva volumen, caja o cierre; descartada.')
    return candidate,{'aplicado':True,'parches':details,'diferencia_volumen_mm3':float(difference),
                      'limite_coplanaridad_mm':PLANO_EPS_MM,
                      'principio':'misma frontera orientada, mismo plano y mismos vértices; cancelación de cobertura opuesta'}
