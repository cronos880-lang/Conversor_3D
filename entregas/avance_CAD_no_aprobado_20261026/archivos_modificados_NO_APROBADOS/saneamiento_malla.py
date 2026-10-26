"""Correcciones certificadas de representación, sin rellenar huecos.

Las caras exactamente colapsadas y los pares coincidentes de orientación
opuesta aportan cero al campo de material; sólo se admiten si sus vértices
pertenecen a la superficie retenida (10 nm). Otras redundancias requieren
cobertura superficial. Las costuras se resuelven subdividiendo la arista larga.
Nunca se seleccionan componentes por su tamaño ni se retira un sólido pequeño.
"""
from __future__ import annotations
import numpy as np,trimesh

LIMITE_LOCAL_MM=1e-5

def quitar_redundancias(mesh):
    faces=mesh.faces;T=mesh.triangles;zero=np.linalg.norm(np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]),axis=1)==0
    _,inverse,counts=np.unique(np.sort(faces,axis=1),axis=0,return_inverse=True,return_counts=True)
    keep=~zero;cancelled=0;duplicates=0;null_chain=zero.copy()
    for group in np.flatnonzero(counts>1):
        ids=np.flatnonzero((inverse==group)&~zero)
        if len(ids)<2:continue
        orientation=[]
        for f in faces[ids]:
            orientation.append(1 if sum(int(f[i]>f[j]) for i in range(3) for j in range(i+1,3))%2==0 else -1)
        net=sum(orientation);keep[ids]=False
        if net:
            chosen=ids[next(i for i,s in enumerate(orientation) if s*np.sign(net)>0)];keep[chosen]=True;duplicates+=len(ids)-1
        else:cancelled+=len(ids);null_chain[ids]=True
    removed=np.flatnonzero(~keep)
    if not len(removed):return mesh,{'aplicado':False}
    if not keep.any():raise ValueError('Las redundancias no dejan ninguna superficie material verificable')
    candidate=trimesh.Trimesh(mesh.vertices.copy(),faces[keep].copy(),process=False)
    from verificacion_reparacion import distancia_malla
    auxiliary=np.flatnonzero(~keep&null_chain);geometric=np.flatnonzero(~keep&~null_chain)
    if len(auxiliary):
        positions=mesh.vertices[np.unique(faces[auxiliary])];distance=distancia_malla(candidate,positions)
        if not np.isfinite(distance).all() or distance.max()>LIMITE_LOCAL_MM:
            raise ValueError('La lámina sin material contiene vértices ajenos a la frontera retenida; no se descarta')
    retained={tuple(sorted(map(int,f))) for f in candidate.faces}
    if any(tuple(sorted(map(int,faces[i]))) not in retained for i in geometric):
        raise ValueError('Una duplicada no tiene una faceta idéntica retenida')
    bound=0.;proof={'caras_duplicadas_con_soporte_identico':len(geometric),'cota_mm':0.}
    # Ningún vértice se mueve; no se retira una isla de volumen positivo.
    return candidate,{'aplicado':True,'caras_retiradas':len(removed),'degeneradas_exactas':int(zero.sum()),
      'duplicadas_redundantes':duplicates,'caras_opuestas_canceladas':cancelled,'vertices_movidos':0,
      'cota_superficie_redundancias_cubiertas_mm':bound,'limite_mm':LIMITE_LOCAL_MM,'cobertura_convexa':proof,
      'caras_cadena_orientada_nula':len(auxiliary),'preservacion_material_cadena_nula':'Área exactamente cero o par de triángulos idénticos con orientaciones opuestas: contribución orientada neta nula en todo el espacio.',
      'superficie_bruta':'Las láminas internas pueden distar de la frontera material; el STEP debe superar además la validación geométrica contra el STL original.'}

def resolver_costuras(mesh):
    V=mesh.vertices.copy();F=mesh.faces.copy();base=V.copy();records=[]
    for _ in range(128):
        directed=F[:,[0,1,1,2,2,0]].reshape(-1,2);sorted_edges=np.sort(directed,axis=1);E,inv,count=np.unique(sorted_edges,axis=0,return_inverse=True,return_counts=True)
        boundary=E[count==1]
        if not len(boundary):break
        adjacent={}
        for a,b in boundary:adjacent.setdefault(int(a),set()).add(int(b));adjacent.setdefault(int(b),set()).add(int(a))
        found=None
        for b,neighbours in adjacent.items():
            if len(neighbours)!=2:continue
            a,c=sorted(neighbours)
            if c not in adjacent.get(a,set()) or len(adjacent[a])!=2 or len(adjacent[c])!=2:continue
            u=V[c]-V[a];length=float(u@u)
            if length==0:continue
            t=float((V[b]-V[a])@u/length)
            if not 1e-8<t<1-1e-8:continue
            projection=V[a]+t*u;distance=float(np.linalg.norm(V[b]-projection))
            if distance>LIMITE_LOCAL_MM or np.linalg.norm(projection-base[b])>LIMITE_LOCAL_MM:continue
            candidates=np.where(np.any(F==a,axis=1)&np.any(F==c,axis=1))[0]
            if len(candidates)!=1:continue
            i=int(candidates[0]);face=F[i];j=next(j for j in range(3) if set((int(face[j]),int(face[(j+1)%3])))==set((a,c)))
            x,y,z=map(int,(face[j],face[(j+1)%3],face[(j+2)%3]));found=(i,x,y,z,b,projection,distance);break
        if found is None:break
        i,a,c,z,b,point,distance=found;V[b]=point;F=np.vstack((F[:i],F[i+1:],[[a,b,z],[b,c,z]]))
        records.append({'arista_subdividida':[a,c],'vertice_intermedio':b,'desplazamiento_mm':distance,
                        'sin_cara_de_tapa':True})
    if not records:return mesh,{'aplicado':False}
    # Tras proyectar B sobre AC, los dos triángulos subdividen exactamente la
    # faceta anterior. Las demás caras sólo sufren el movimiento de vértices.
    bound=float(np.linalg.norm(V-base,axis=1).max())
    candidate=trimesh.Trimesh(V,F,process=False)
    if not candidate.is_watertight or not candidate.is_winding_consistent:
        raise ValueError('La corrección de costura no produce una frontera cerrada y orientada')
    return candidate,{'aplicado':True,'costuras':records,'cota_global_superficie_mm':bound,
      'limite_mm':LIMITE_LOCAL_MM,'fundamento':'Subdivisión exacta tras proyectar el nodo sobre su arista; movimiento baricéntrico acotado. No se añade ninguna tapa.'}

def verificar_envolventes(mesh,control_path):
    """Un exterior positivo y cavidades negativas disjuntas, todas contenidas."""
    import igl
    from reparador_exacto_aislado import ControlExacto
    from invariantes_material import InvariantesMaterial
    from topologia_vertices import inspeccionar_vertices
    if not mesh.is_watertight or not mesh.is_winding_consistent or inspeccionar_vertices(mesh)['vertices_no_manifold']:
        raise ValueError('Envolventes no cerradas, no orientadas o no manifold')
    inv=InvariantesMaterial(mesh)
    if not inv.negative:raise ValueError('No hay cavidades negativas que verificar')
    if ControlExacto(mesh,control_path).pares():raise ValueError('Las envolventes se cruzan o presentan contactos ambiguos')
    outer=inv.body_faces;records=[]
    for i in inv.negative:
        f=mesh.faces[inv.groups[i]];points=mesh.vertices[np.unique(f)]
        w=igl.winding_number(np.asarray(mesh.vertices,dtype=np.float64),outer,np.asarray(points,dtype=np.float64))
        if not np.all(w>.75):raise ValueError('La envolvente negativa no queda dentro del material exterior')
        for j in inv.negative:
            if i==j:continue
            other=mesh.faces[inv.groups[j]];q=igl.winding_number(np.asarray(mesh.vertices,dtype=np.float64),other,points[:1])
            if np.any(abs(q)>.25):raise ValueError('Cavidades anidadas o superpuestas: material ambiguo')
        records.append({'componente':int(i),'vertices_contenidos':len(points),'volumen_firmado_mm3':float(inv.volumen(mesh.vertices,f))})
    return {'cavidades_cerradas':len(inv.negative),'envolventes':len(inv.groups),'euler':int(mesh.euler_number),
      'material':'Un exterior positivo; cavidades negativas contenidas, disjuntas y sin intersecciones CGAL',
      'coordenadas_y_caras_intactas':True,'componentes':records}
