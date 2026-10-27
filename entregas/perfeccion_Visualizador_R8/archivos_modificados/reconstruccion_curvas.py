"""Rescate aislado de encuentros CAD, conservando los cilindros respaldados por el STL.

Sólo sigue a un candidato rechazado por interferencias. No repara huecos de
entrada, no idealiza medidas y no cambia tolerancias de aceptación.
"""
from __future__ import annotations
import hashlib,json,os,subprocess,sys,tempfile,traceback
from pathlib import Path

MAX_FACES=20_000
# Sólo rechazos del trabajador y sólo durante este proceso de conversión.
# La reconstrucción interna usa siempre8grados; repetirla tras cada ángulo
# exterior no aporta una estrategia nueva. No almacenar resultados aprobados.
_RECHAZOS_TRABAJADOR={}
_FLAGS_RECONSTRUCCION=('VISOR_CENTROID_GATE','VISOR_REFINAMIENTO_BREP','VISOR_EXPERIMENTAL_CILINDROS')
def presupuesto_recuperacion(triangulos):
    return min(900,max(300,120+int(triangulos)*7//100))
def _clave_intento(source):
    return (_sha(source),os.environ.get('VISOR_PERFIL','precision'),
            tuple((name,os.environ.get(name,'0')) for name in _FLAGS_RECONSTRUCCION))

def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def inventario(shape):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    faces=[f for f in shape.Faces() if BRepAdaptor_Surface(f.wrapped).GetType()==GeomAbs_Cylinder]
    return {'caras':len(shape.Faces()),'cilindros':len(faces),'area_cilindrica_mm2':sum(f.Area() for f in faces)}

def cilindros_respaldados(result,mesh,tol=.008):
    import numpy as np
    from meshfit_brep import _prim_surface,_Proj
    required=[]
    for prim in result['primitives']:
        if prim['type']!='cylinder':continue
        ids=np.asarray(prim['faces'],dtype=int)
        points=np.vstack((mesh.vertices[np.unique(mesh.faces[ids])],mesh.triangles_center[ids]))
        error=float(np.linalg.norm(_Proj(_prim_surface(prim)).batch(points)-points,axis=1).max())
        if error<=tol:
            required.append({'puntos':points,'radio':float(prim['radius']),
                'eje':np.asarray(prim['axis'],float),'centro':np.asarray(prim['point'],float),
                'max_entrada_mm':error})
    return required

def comprobar_cilindros(required,shape,tol=.008):
    import numpy as np
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    if not required:raise ValueError('No se han confirmado cilindros en la entrada.')
    faces=[f for f in shape.Faces() if BRepAdaptor_Surface(f.wrapped).GetType()==GeomAbs_Cylinder]
    records=[]
    for cylinder_index,req in enumerate(required,1):
        from avance_conversion import avance
        avance(78,f'Contrastando cilindro {cylinder_index}/{len(required)} con el STL original')
        axis=req['eje']/np.linalg.norm(req['eje']);matches=[]
        for face in faces:
            cyl=BRepAdaptor_Surface(face.wrapped).Cylinder();direction=np.asarray(cyl.Axis().Direction().Coord())
            center=np.asarray(cyl.Location().Coord())
            if (abs(cyl.Radius()-req['radio'])<=tol and abs(direction@axis)>=.99999
                    and np.linalg.norm(np.cross(center-req['centro'],axis))<=tol):matches.append(face)
        if not matches:raise ValueError('El rescate pierde un cilindro respaldado por el STL.')
        points=req['puntos'];ids=set(np.linspace(0,len(points)-1,min(32,len(points))).astype(int))
        for dim in range(3):ids.update([int(points[:,dim].argmin()),int(points[:,dim].argmax())])
        maximum=0.
        for index in sorted(ids):
            vertex=BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float,points[index]))).Vertex();distances=[]
            for face in matches:
                d=BRepExtrema_DistShapeShape(vertex,face.wrapped)
                if not d.IsDone():raise ValueError('No se verifica el contorno de un cilindro.')
                distances.append(float(d.Value()))
            maximum=max(maximum,min(distances))
        if maximum>tol:raise ValueError('El rescate recorta o desplaza un cilindro confirmado.')
        records.append({'radio_entrada_mm':req['radio'],'max_ajuste_entrada_mm':req['max_entrada_mm'],
                        'max_control_cara_recortada_mm':maximum,'muestras':len(ids)})
    return {'confirmados':len(required),'preservados':len(records),'control_mm':tol,'cilindros':records}

def certificar_mallado(shape,original,control,quality):
    """Una validez B-Rep muestreada no basta: contrastar su frontera mallada."""
    import numpy as np,trimesh
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRepTools import BRepTools
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopAbs import TopAbs_REVERSED
    from reparador_exacto_aislado import ControlExacto,medidas_superficie
    from topologia_vertices import inspeccionar_vertices
    from avance_conversion import avance
    records=[]
    # Las TRES resoluciones deben conservar una frontera cerrada y sin cruces.
    for resolution_index,resolution in enumerate((.00025,.0005,.001),1):
        avance(78,f'Verificando cierre y geometría del mallado fino {resolution_index}/3')
        work=shape.copy();BRepTools.Clean_s(work.wrapped)
        BRepMesh_IncrementalMesh(work.wrapped,resolution,False,.04,False).Perform()
        owners=[];vertices=[];faces=[]
        for i,face in enumerate(work.Faces()):
            tri=BRep_Tool.Triangulation_s(face.wrapped,TopLoc_Location())
            if tri is None or tri.NbTriangles()==0:
                raise ValueError('El STEP contiene una cara que no se puede mallar; descartado.')
            loc=TopLoc_Location();tri=BRep_Tool.Triangulation_s(face.wrapped,loc)
            offset=len(vertices)
            vertices.extend([tri.Node(j).Transformed(loc.Transformation()).Coord() for j in range(1,tri.NbNodes()+1)])
            for triangle in tri.Triangles():
                a,b,c=triangle.Get()
                faces.append((a+offset-1,c+offset-1,b+offset-1) if face.wrapped.Orientation()==TopAbs_REVERSED else (a+offset-1,b+offset-1,c+offset-1))
                owners.append(i)
        # Leer la triangulación absoluta ya calculada. Shape.tessellate() llama
        # de nuevo al mallador con opciones relativas y puede alterar su caché.
        V=np.asarray(vertices);F=np.asarray(faces)
        _,first,inverse=np.unique(np.round(V/1e-10).astype(np.int64),axis=0,return_index=True,return_inverse=True)
        mesh=trimesh.Trimesh(V[first],inverse[F],process=False)
        closed=mesh.is_watertight
        if not mesh.is_winding_consistent or inspeccionar_vertices(mesh)['vertices_no_manifold']:
            raise ValueError('El mallado fino del STEP es ambiguo; descartado.')
        if not closed or mesh.euler_number!=original.euler_number:
            raise ValueError('El mallado fino del STEP cambia la frontera o deja zonas abiertas; descartado.')
        avance(78,'Contrastando la frontera CAD a varias resoluciones, sin cambiar tolerancias')
        control_path=Path(control).with_name(f'frontera_{resolution}.off')
        pairs=ControlExacto(mesh,control_path).pares()
        if pairs:
            raise ValueError('El mallado fino del STEP contiene intersecciones; descartado.')
        surface=medidas_superficie(original,mesh);limits=quality['limites_validacion']
        margin=0.
        if surface['max_mm']+margin>limits['desviacion_max_observada_mm'] or surface['p95_mm']+margin>limits['p95_superficie_max_mm']:
            raise ValueError('El mallado fino del STEP supera los límites geométricos del perfil; descartado.')
        records.append({'cerrado':bool(closed),'orientado':True,'euler':int(mesh.euler_number),
            'intersecciones_cgal':0,'caras':len(mesh.faces),'deflexion_mm':resolution,'angulo_rad':.04,
            'superficie':surface,'margen_microbucles_mm':margin})
    return {'resoluciones':records,'step_modificado':False,
            'limites_geometricos_modificados':False}

def trabajador(source,destination,report):
    source,destination,report=map(Path,(source,destination,report));record={'ok':False}
    if (len({p.resolve() for p in (source,destination,report)})!=3
        or any(a.exists() and b.exists() and a.samefile(b) for a,b in [(source,destination),(source,report),(destination,report)])):
        raise ValueError('Las rutas de entrada y salida deben ser distintas.')
    try:
        sys.path.insert(0,str(Path(__file__).resolve().parent/'motor_superficies'))
        from preprocesador_stl import cargar_exacto
        from reparador_exacto_aislado import ControlExacto
        from invariantes_material import InvariantesMaterial
        from validacion_reconstruccion import certificar_topologia_step
        from calidad_topologica import leer_solido_step_estricto
        from motor_v2 import _calidad
        from meshfit_detect import detect
        from meshfit_step import export_step
        if not source.is_file() or source.stat().st_size>30*1024**2:raise ValueError('Entrada ausente o mayor de 30 MB.')
        original=cargar_exacto(source);source_hash=_sha(source)
        if len(original.faces)>MAX_FACES:raise ValueError('El rescate analítico supera el presupuesto de 20.000 triángulos.')
        if not original.is_watertight or not original.is_winding_consistent:
            from normalizacion_referencia import normalizar_cierre
            original,record['normalizacion_referencia_material']=normalizar_cierre(original)
        with tempfile.TemporaryDirectory(prefix='visor_curvas_control_') as tmp:
            if ControlExacto(original,Path(tmp)/'entrada.off').pares():
                raise ValueError('La entrada tiene intersecciones; el rescate CAD no las ocultará.')
        # Misma detección histórica de 8 grados; sólo se ciñen los encuentros.
        os.environ['VISOR_STL_DIGITAL']='0'
        result,working=detect(str(source),angle_tol_deg=32.,rms_tol_rel=.01,flat_tol_deg=8.,scan_mode=False)
        required=cilindros_respaldados(result,working)
        if not required:
            raise ValueError('No se han confirmado cilindros en la entrada; se omite la reconstrucción que no podría superar ese control.')
        export_step(result,working,str(destination),organic=True,solid=True,organic_smooth=0.,
                    ajuste_ia=False,require_solid=True,precision_reparacion=True,refinar_curvas=True,
                    contornos_compartidos=True,cavidades_verificadas=bool(InvariantesMaterial(original).negative))
        shape=leer_solido_step_estricto(destination)
        from saneamiento_cad import exigir_coherencia_exacta
        exigir_coherencia_exacta(shape)
        cylinders=comprobar_cilindros(required,shape)
        quality=_calidad(source,destination,original,control_avanzado=True)
        topology=certificar_topologia_step(shape,original,InvariantesMaterial(original))
        with tempfile.TemporaryDirectory(prefix='visor_curvas_frontera_') as tmp:
            boundary=certificar_mallado(shape,original,Path(tmp)/'frontera.off',quality)
        if source_hash!=_sha(source):raise ValueError('La entrada cambió durante la comprobación.')
        record.update(ok=True,original_sha256=source_hash,step_sha256=_sha(destination),
                      calidad=quality,topologia_material=topology,mallado_fino=boundary,cilindros_respaldados=cylinders,inventario=inventario(shape),
                      metodo='contornos_compatibles_ciclos_analiticos',brep_exacto=True)
        from prueba_cad import REVISION
        record['revision_cad']=REVISION
        import meshfit_step
        record['normalizacion_ciclos']=meshfit_step.LAST_INFO.get('normalizacion_ciclos',{})
    except Exception as exc:
        record['error']=str(exc);destination.unlink(missing_ok=True);traceback.print_exc()
    report.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
    return 0 if record['ok'] else 2

def intentar_refinar(source,step,original,validar,log,*,validar_con_prueba=None):
    import psutil
    from control_recursos import comunicar_vigilado
    from calidad_topologica import leer_solido_step_estricto
    from avance_conversion import avance
    if len(original.faces)>MAX_FACES or not original.is_watertight or not original.is_winding_consistent:
        raise ValueError('La entrada no es apta para el rescate de curvas acotado.')
    key=_clave_intento(source)
    if key in _RECHAZOS_TRABAJADOR:
        raise ValueError('No se repite el mismo rescate rechazado con la misma entrada, perfil y parámetros: '+_RECHAZOS_TRABAJADOR[key])
    before=inventario(leer_solido_step_estricto(step))
    if before['cilindros']<1:raise ValueError('No hay cilindros que preservar en este candidato.')
    source_hash=_sha(source)
    def stop(proc):
        try:
            parent=psutil.Process(proc.pid)
            for child in parent.children(recursive=True):
                try:child.kill()
                except psutil.NoSuchProcess:pass
            parent.kill()
        except psutil.NoSuchProcess:pass
    with tempfile.TemporaryDirectory(prefix='visor_refinar_curvas_',dir=Path(step).parent) as directory:
        candidate=Path(directory)/'candidato.step';report=Path(directory)/'informe.json'
        avance(78,'Reconstruyendo contornos compatibles y comprobando los cilindros frente al STL')
        env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1',
             'PYTHONUNBUFFERED':'1','PYTHONIOENCODING':'utf-8'}
        with subprocess.Popen([sys.executable,str(Path(__file__).resolve()),str(source),str(candidate),str(report)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env) as proc:
            out,_,peak=comunicar_vigilado(proc,presupuesto_recuperacion(len(original.faces)),stop)
        if out:print(out,file=log,flush=True)
        if proc.returncode!=0 or not report.exists():
            reason='El rescate de curvas no produjo un STEP aprobado.'
            if report.exists():
                try:reason=json.loads(report.read_text(encoding='utf-8')).get('error') or reason
                except (ValueError,OSError):pass
            _RECHAZOS_TRABAJADOR[key]=reason
            raise ValueError(reason)
        record=json.loads(report.read_text(encoding='utf-8'))
        if not record.get('ok') or not candidate.is_file():
            reason=record.get('error','Rescate de curvas rechazado.')
            _RECHAZOS_TRABAJADOR[key]=reason
            raise ValueError(reason)
        if record['original_sha256']!=_sha(source) or source_hash!=_sha(source) or record['step_sha256']!=_sha(candidate):
            raise ValueError('El resultado no coincide con los archivos comprobados.')
        after=inventario(leer_solido_step_estricto(candidate))
        if validar_con_prueba is not None:
            from prueba_cad import desde_trabajador
            quality=validar_con_prueba(source,candidate,original,desde_trabajador(record,candidate))
        else:quality=validar(source,candidate,original)
        proof={'aplicado':True,'metodo':'contornos_compatibles_ciclos_analiticos','antes':before,'despues':after,
               'ajuste_regiones_mm':.006,'ajuste_bspline_mm':.003,'ajuste_aristas_mm':.001,
               'movimiento_maximo_mm':.012,'topologia_material':record['topologia_material'],
               'mallado_fino':record['mallado_fino'],'cilindros_respaldados':record['cilindros_respaldados'],
               'original_sha256':source_hash,'step_sha256':record['step_sha256'],'ram_pico_mb':peak,
               'limites_aceptacion_modificados':False,'brep_exacto':record['brep_exacto'],
               'presupuesto_s':presupuesto_recuperacion(len(original.faces))}
        proof['normalizacion_ciclos']=record.get('normalizacion_ciclos',{})
        if record.get('normalizacion_referencia_material'):
            proof['normalizacion_referencia_material']=record['normalizacion_referencia_material']
        payload=candidate.read_bytes()
        if hashlib.sha256(payload).hexdigest()!=record['step_sha256'] or _sha(source)!=source_hash:
            raise ValueError('El archivo cambió después de ser validado; no se publica.')
        Path(step).write_bytes(payload)
        return quality,proof

if __name__=='__main__':
    if len(sys.argv)!=4:raise SystemExit('Uso: reconstruccion_curvas.py entrada.stl salida.step informe.json')
    raise SystemExit(trabajador(*sys.argv[1:]))
