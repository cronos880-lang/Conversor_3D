"""Herramienta independiente de reparación de fronteras orientadas.

Componente opcional que usa los bindings copyleft de gpytoolbox y CGAL
(GPL-3.0-or-later). Se ejecuta en otro proceso y comunica STL y JSON.
No sustituye al motor CAD ni certifica un STEP por reparar la malla.
"""
from __future__ import annotations
import argparse,hashlib,itertools,json,os,time,traceback
from pathlib import Path
import numpy as np
import trimesh


def cargar(path):
    m=trimesh.load(str(path),force='mesh',process=False)
    vertices,inverse=np.unique(m.vertices,axis=0,return_inverse=True)
    return trimesh.Trimesh(vertices,inverse[m.faces],process=False)


def normales(mesh):
    t=mesh.vertices[mesh.faces]
    n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);length=np.linalg.norm(n,axis=1)
    if np.any(length==0):raise ValueError('Hay triángulos exactamente colapsados.')
    return n/length[:,None]


def escribir_off(mesh,path):
    path.write_text('OFF\n'+f'{len(mesh.vertices)} {len(mesh.faces)} 0\n'+
        ''.join(' '.join(format(float(x),'.17g') for x in v)+'\n' for v in mesh.vertices)+
        ''.join('3 '+' '.join(map(str,f))+'\n' for f in mesh.faces),encoding='ascii')


class ControlExacto:
    def __init__(self,mesh,path):
        from CGAL import CGAL_Polyhedron_3 as pp
        escribir_off(mesh,path);self.poly=pp.Polyhedron_3(str(path))
        if (not self.poly.is_valid() or not self.poly.is_closed() or
                self.poly.size_of_facets()!=len(mesh.faces) or
                self.poly.size_of_vertices()!=len(mesh.vertices)):
            raise ValueError('CGAL no ha leído la malla completa como superficie cerrada válida.')
        self.handles=list(self.poly.vertices())
        for i,handle in enumerate(self.handles):
            p=handle.point();xyz=np.array([p.x(),p.y(),p.z()])
            if np.max(np.abs(xyz-mesh.vertices[i]))>1e-12:
                raise ValueError('La numeración de vértices no coincide con el control exacto.')
        for i,face in enumerate(self.poly.facets()):face.set_id(i)

    def pares(self):
        from CGAL import CGAL_Polygon_mesh_processing as pmp
        pairs=[];pmp.self_intersections(self.poly,pairs)
        return [(p[0].id(),p[1].id()) for p in pairs]

    def mover(self,index,point):
        from CGAL.CGAL_Kernel import Point_3
        self.handles[index].set_point(Point_3(*map(float,point)))


def publicar(fase,**info):
    print(json.dumps({'fase_reparacion':fase,**info},ensure_ascii=True),flush=True)
    destination=os.getenv('VISOR_AVANCE_PATH')
    if destination:
        try:
            with open(destination,'a',encoding='utf-8') as f:
                f.write(json.dumps({'porcentaje':15,'fase':fase[:180],'instante':time.time()})+'\n')
        except OSError:pass


def desenredar(mesh,control_path,deadline,*,solo_contactos=True,permitir_parcial=False):
    """Búsqueda local acotada; solo se aceptan descensos del recuento exacto."""
    m=mesh.copy();base=m.vertices.copy();n=normales(m);area=m.area_faces
    incident=[[] for _ in m.vertices]
    for fi,face in enumerate(m.faces):
        for v in face:incident[v].append(fi)
    if solo_contactos:
        _,inverse,counts=np.unique(base,axis=0,return_inverse=True,return_counts=True)
        indices=np.where(counts[inverse]>1)[0].tolist()
    else:indices=list(range(len(base)))
    checker=ControlExacto(m,control_path);pairs=checker.pares();initial=len(pairs)
    rng=np.random.default_rng(20261024);changes=[]
    for iteration in range(4):
        improved=False
        for index in indices:
            if not pairs:break
            if time.monotonic()>deadline:raise TimeoutError('Tiempo de reparación local agotado.')
            fan=incident[index];touch=set(fan)
            if not any(a in touch or b in touch for a,b in pairs):continue
            normal=np.average(n[fan],axis=0,weights=np.maximum(area[fan],1e-30))
            norm=np.linalg.norm(normal)
            if norm<1e-10:normal=np.array([1.,0.,0.]);norm=1.
            normal/=norm
            centroid=base[np.unique(m.faces[fan])].mean(axis=0)-base[index]
            directions=[normal,-normal]
            if np.linalg.norm(centroid)>1e-15:
                centroid/=np.linalg.norm(centroid);directions.extend((centroid,-centroid))
            directions.extend(np.eye(3));directions.extend(-np.eye(3))
            directions.extend(v/np.linalg.norm(v) for v in rng.normal(size=(8,3)))
            original=m.vertices[index].copy();old_count=len(pairs);accepted=False
            for eps in (2e-6,2e-5,1e-4):
                for direction in directions:
                    point=base[index]+eps*direction;checker.mover(index,point)
                    new=checker.pares()
                    if len(new)<old_count:
                        m.vertices[index]=point;pairs=new;accepted=True;improved=True
                        changes.append({'vertice':index,'desplazamiento_mm':float(np.linalg.norm(point-base[index])),
                                        'pares_antes':old_count,'pares_despues':len(new)})
                        break
                if accepted:break
            if not accepted:checker.mover(index,original)
            if len(changes)%10==0:publicar('Regularizando contactos verificados',pares_restantes=len(pairs))
        if not pairs or not improved:break
    if pairs and not permitir_parcial:raise ValueError(f'Persisten {len(pairs)} intersecciones; no se acepta la reparación.')
    return m,{'pares_iniciales':initial,'pares_finales':len(pairs),'cambios':changes,
              'max_desplazamiento_mm':float(np.linalg.norm(m.vertices-base,axis=1).max(initial=0.))}


def medidas_superficie(reference,candidate):
    # Consulta independiente de las operaciones CGAL/Manifold.
    from verificacion_reparacion import distancia_malla,puntos_superficie
    a=distancia_malla(reference,puntos_superficie(candidate))
    b=distancia_malla(candidate,puntos_superficie(reference))
    return {'max_mm':float(max(a.max(),b.max())),
            'p95_mm':float(max(np.percentile(a,95),np.percentile(b,95))),
            'muestras':[len(a),len(b)]}


def validar_material(original,candidate,contactos):
    import igl
    from verificacion_reparacion import distancia_malla
    rng=np.random.default_rng(20261024)
    points=rng.uniform(original.bounds[0],original.bounds[1],size=(3000,3))
    if contactos:
        extra=[]
        for contact in contactos:
            center=np.asarray(contact['xyz_mm'])
            for distance in (.002,.004,.01):
                extra.extend(center+sign*distance*axis for axis in np.eye(3) for sign in (-1,1))
        points=np.vstack((points,extra))
    distances=distancia_malla(original,points)
    points=points[distances>.002]
    before=igl.winding_number(original.vertices,original.faces,points)
    after=igl.winding_number(candidate.vertices,candidate.faces,points)
    mismatch=(before>.5)!=(after>.5)
    if np.any(mismatch):raise ValueError(f'El material cambia en {int(mismatch.sum())} puntos fuera de la banda de reparación.')
    return {'puntos':len(points),'discrepancias':0,'banda_excluida_mm':.002,
            'referencia':'Número de giro orientado positivo del STL original.',
            'nota':'Muestreo reproducible; no demostración global del campo de material.'}


def regularizar_material(base,mesh):
    """Tratar solo contactos geométricos preexistentes, sin borrar cuerpos.

    Una cuña de material se conecta mediante una micro-unión. Una cuña de
    vacío se abre mediante una micro-sustracción. Se conserva el resto de la
    frontera y se comprueban después todos los límites dimensionales.
    """
    import igl,manifold3d as mf
    from preprocesador_stl import _manifold
    groups=list(trimesh.graph.connected_components(base.face_adjacency,
               nodes=np.arange(len(base.faces)),min_len=1))
    parts=list(mesh.submesh(groups,repair=False));depth=[]
    for i,part in enumerate(parts):
        points=part.vertices[:min(3,len(part.vertices))];containers=[]
        for j,other in enumerate(parts):
            if i==j:continue
            w=igl.winding_number(other.vertices,other.faces,points)
            if np.median(np.abs(w))>.5:containers.append(j)
        depth.append(len(containers))
    labels=np.full(len(base.faces),-1)
    for i,ids in enumerate(groups):labels[list(ids)]=i
    points,inverse,counts=np.unique(base.vertices,axis=0,return_inverse=True,return_counts=True)
    operations=[];adds=[];cuts=[];eps=.000050
    for bucket in np.where(counts>1)[0]:
        ids=np.where(inverse==bucket)[0]
        touched=np.where(np.isin(base.faces,ids).any(axis=1))[0]
        components=np.unique(labels[touched])
        deepest=max(components,key=lambda i:(depth[i],-abs(parts[i].volume)))
        positive=parts[deepest].volume>0
        (adds if positive else cuts).append(points[bucket])
        operations.append({'xyz_mm':points[bucket].tolist(),'tipo':'micro_union_material' if positive else 'micro_apertura_vacio',
                           'semiancho_mm':eps,'componentes':components.tolist()})
    result=_manifold(mesh)
    if adds:
        result=result+mf.Manifold.batch_boolean([mf.Manifold.cube([2*eps]*3,True).translate(p) for p in adds],mf.OpType.Add)
    if cuts:
        result=result-mf.Manifold.batch_boolean([mf.Manifold.cube([2*eps]*3,True).translate(p) for p in cuts],mf.OpType.Add)
    result=result.simplify(1e-9)
    if result.status()!=mf.Error.NoError:raise ValueError('No se pudo regularizar el contacto de material.')
    data=result.to_mesh64();m=trimesh.Trimesh(data.vert_properties[:,:3],data.tri_verts,process=False)
    vertices,inverse=np.unique(m.vertices,axis=0,return_inverse=True)
    m=trimesh.Trimesh(vertices,inverse[m.faces],process=False)
    from topologia_vertices import inspeccionar_vertices
    if not m.is_watertight or not m.is_winding_consistent or inspeccionar_vertices(m)['vertices_no_manifold']:
        raise ValueError('La regularización pierde la topología; se descarta.')
    return m,{'operaciones':operations,'radio_max_modificacion_mm':float(np.sqrt(3)*eps),
              'cuerpos_descartados':0}


def ejecutar(source,destination,report_path):
    # Rechazar antes de crear, limpiar o escribir cualquier salida: tampoco
    # el bloque de error puede borrar o sobrescribir la entrada original.
    paths=(source,destination,report_path,destination.with_suffix('.control.off'),
           destination.with_suffix('.pendiente.stl'))
    if len({p.resolve() for p in paths})!=len(paths):
        print('La entrada, la salida y el informe deben ser archivos distintos.',flush=True)
        return 2
    from reparacion_contactos_locales import descomponer_contactos
    from topologia_vertices import inspeccionar_vertices
    start=time.monotonic();deadline=start+600
    report={'version_reparador':1,'original_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'original_conservado':True,'cad_certificado':False,'reparado':False}
    try:
        from gpytoolbox_bindings_copyleft import _mesh_union_cpp_impl
        if source.resolve()==destination.resolve():raise ValueError('La salida no puede sobrescribir el STL original.')
        original=cargar(source)
        if not original.is_watertight or not original.is_winding_consistent or original.volume<=0:
            raise ValueError('Esta reparación requiere una frontera cerrada y orientada.')
        publicar('Resolviendo intersecciones de la frontera orientada')
        vertices,faces=_mesh_union_cpp_impl(original.vertices.copy(),original.faces.astype(np.int32),
                                           original.vertices.copy(),original.faces.astype(np.int32))
        reference=trimesh.Trimesh(vertices,faces,process=False)
        # Frontera del dominio de número de giro positivo; no relleno de huecos.
        report['frontera_orientada']={'caras':len(faces),'regla':'Unión exacta del dominio orientado positivo consigo mismo.',
                                    'caja_error_mm':float(np.abs(reference.bounds-original.bounds).max()),
                                    'volumen_error_original_pct':float(abs(reference.volume-original.volume)/original.volume*100)}
        base,report['descomposicion']=descomponer_contactos(reference)
        mesh,report['separacion']=desenredar(base,destination.with_suffix('.control.off'),deadline,permitir_parcial=True)
        if report['separacion']['pares_finales']:
            mesh,report['separacion_complementaria']=desenredar(mesh,destination.with_suffix('.control.off'),deadline,solo_contactos=False)
        mesh,report['regularizacion_material']=regularizar_material(base,mesh)
        mesh,report['desenredo_final']=desenredar(mesh,destination.with_suffix('.control.off'),deadline,solo_contactos=False)
        from normalizacion_microcaras import normalizar
        mesh,report['normalizacion_microcaras']=normalizar(mesh)
        proof=medidas_superficie(reference,mesh)
        volume_error=100*abs(mesh.volume-reference.volume)/max(reference.volume,1e-30)
        box_error=float(np.abs(mesh.bounds-reference.bounds).max())
        if proof['max_mm']>.002 or volume_error>.001 or box_error>.002:
            raise ValueError('La reparación excede los límites de superficie, volumen o cotas de la frontera de referencia.')
        parts=mesh.split(only_watertight=False);positive=int(sum(p.volume>0 for p in parts))
        if positive!=1:raise ValueError(f'Quedan {positive} cuerpos de material; no se elimina ninguno para forzar un sólido.')
        report['material_original']=validar_material(original,mesh,report['regularizacion_material']['operaciones'])
        report['validacion_original']=medidas_superficie(original,mesh)
        if report['validacion_original']['max_mm']>.060 or report['validacion_original']['p95_mm']>.020:
            raise ValueError('La malla reparada no conserva los límites superficiales estrictos del STL original.')
        temporary=destination.with_suffix('.pendiente.stl')
        temporary.write_text(trimesh.exchange.stl.export_stl_ascii(mesh),encoding='ascii')
        reread=cargar(temporary);control=ControlExacto(reread,destination.with_suffix('.control.off'))
        topology=inspeccionar_vertices(reread)
        if (control.pares() or not reread.is_watertight or not reread.is_winding_consistent or
                topology['vertices_no_manifold']):raise ValueError('El STL guardado no conserva la reparación verificada.')
        report.update(reparado=True,resultado='Malla regularizada; STEP pendiente de validación independiente.',
            validacion_frontera={**proof,'volumen_error_pct':volume_error,'caja_error_mm':box_error,
                                'limites':{'max_superficie_mm':.002,'volumen_pct':.001,'caja_mm':.002}},
            salida={'caras':len(reread.faces),'vertices':len(reread.vertices),'solidos_material':positive,
                    'cavidades_cerradas':len(parts)-positive,'microcaras':int((reread.area_faces<=1e-14).sum()),
                    'topologia_vertices':topology,'autointersecciones_exactas':0},
            requiere_lectura_exacta=True,requiere_verificar_cavidades=True,
            tolerancias_step_sin_cambios=True)
        temporary.replace(destination)
        report['reparado_sha256']=hashlib.sha256(destination.read_bytes()).hexdigest()
        report['source_a_frontera_original_mm']=medidas_superficie(original,reference)
        if hashlib.sha256(source.read_bytes()).hexdigest()!=report['original_sha256']:
            raise ValueError('La entrada original ha cambiado durante la reparación.')
    except Exception as exc:
        report.update(reparado=False,error=str(exc));destination.unlink(missing_ok=True)
        traceback.print_exc()
    finally:
        report['segundos']=round(time.monotonic()-start,3)
        report_path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        destination.with_suffix('.control.off').unlink(missing_ok=True)
        destination.with_suffix('.pendiente.stl').unlink(missing_ok=True)
    return 0 if report['reparado'] else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('entrada',type=Path);parser.add_argument('salida',type=Path);parser.add_argument('informe',type=Path)
    args=parser.parse_args()
    raise SystemExit(ejecutar(args.entrada,args.salida,args.informe))
