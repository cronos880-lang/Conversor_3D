"""Estabilizar planos de contacto SOLO si ya existe unión volumétrica o superficial.

No une piezas separadas por proximidad. Movimiento absoluto máximo 0,000020
mm; el resultado debe contrastarse después con la referencia OCC ORIGINAL.
"""
from __future__ import annotations
import numpy as np


def normalizar_contactos_solapados(mesh):
    import shapely
    import trimesh
    from preprocesador_stl import componentes,_manifold
    parts=componentes(mesh)
    solids=[_manifold(p) for p in parts]
    original=np.asarray(mesh.vertices,float)
    vertices=original.copy()
    restore=np.eye(4)
    working=None
    epsilon=min(.000020,float(np.linalg.norm(mesh.extents))*1e-7)
    proofs=[]
    for i,a in enumerate(parts):
        for j in range(i+1,len(parts)):
            b=parts[j]
            overlap=(solids[i]^solids[j]).volume()
            united=solids[i]+solids[j]
            contact_area=(solids[i].surface_area()+solids[j].surface_area()-united.surface_area())/2
            if overlap<=1e-10 and (len(united.decompose())!=1 or contact_area<=1e-8):
                continue  # Ni solapamiento ni contacto superficial ya unido: NO aproximar.
            found=None
            # Buscar soporte plano significativo, no astillas casi degeneradas.
            ia=np.argsort(-a.area_faces)[:40];ib=np.argsort(-b.area_faces)[:80]
            for fa in ia:
                if a.area_faces[fa]<.001*a.area:continue
                n=a.face_normals[fa]
                candidates=ib[(b.face_normals[ib]@n)<-1+1e-10]
                for fb in candidates:
                    if b.area_faces[fb]<.001*b.area:continue
                    pa,pb=a.triangles[fa],b.triangles[fb]
                    if np.max(abs((pb-pa.mean(0))@n))>epsilon:continue
                    ref=np.eye(3)[np.argmin(abs(n))]
                    x=np.cross(n,ref);x/=np.linalg.norm(x);y=np.cross(n,x)
                    uv=lambda p:np.column_stack((p@x,p@y))
                    area=shapely.Polygon(uv(pa)).intersection(shapely.Polygon(uv(pb))).area
                    if area<=1e-8:continue
                    found=(n,(pa.mean(0)+pb.mean(0))/2,area)
                    break
                if found is not None:break
            if found is None:continue
            n,origin,area=found
            if working is None:
                ref=np.eye(3)[np.argmin(abs(n))]
                x=np.cross(n,ref);x/=np.linalg.norm(x)
                basis=np.column_stack((x,np.cross(n,x),n))
                restore[:3,:3]=basis;restore[:3,3]=origin
                working=(original-origin)@basis
                vertices=working.copy()
                level=0.
            else:
                if abs(n@restore[:3,2])<1-1e-10:continue
                level=float((origin-restore[:3,3])@restore[:3,2])
            mask=abs(vertices[:,2]-level)<=epsilon
            # Todos los vértices del mismo plano, incluidos otros cuerpos que
            # ya lo ocupan. La comprobación final limita el movimiento TOTAL.
            # En este marco la interfaz ES z constante, idéntica en bits:
            # reproyectar en 3D dejaba microseparaciones de redondeo en OCC.
            vertices[mask,2]=float(np.mean(vertices[mask,2])) if abs(level)>epsilon else 0.
            proofs.append({'componentes':[i,j],'interseccion_preexistente_mm3':float(overlap),
                           'area_contacto_preexistente_mm2':float(contact_area),
                           'area_soporte_mm2':float(area),'vertices_plano':int(mask.sum())})
    if not proofs:return mesh,restore,{'aplicado':False}
    movement=np.linalg.norm(vertices-working,axis=1)
    if movement.max()>epsilon:
        raise ValueError('La estabilización de contactos excede su límite nanométrico.')
    candidate=trimesh.Trimesh(vertices,mesh.faces.copy(),process=False)
    return candidate,restore,{'aplicado':True,'contactos':proofs,'max_movimiento_mm':float(movement.max()),
                      'limite_movimiento_mm':epsilon,'uniones_por_cercania':0,
                      'matriz_restauracion':restore.tolist(),
                      'condicion':'solapamiento o contacto superficial YA unido; caras planas opuestas con área común'}
