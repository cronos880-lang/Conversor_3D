"""Rescate analítico posterior al rechazo de las estrategias aprobadas R9.

Trabajador aislado y acotado. Ningún cambio en los límites geométricos,
la lectura exacta, BOP, material, cilindros o tres mallados finos CGAL.
"""
from __future__ import annotations
import hashlib,json,os,subprocess,sys,tempfile,traceback
from pathlib import Path
from reconstruccion_curvas import (inventario,cilindros_respaldados,validar_cilindros_y_frontera)
MAX_FACES=20_000
_RECHAZOS_TRABAJADOR={}
def presupuesto_recuperacion(triangulos):return 450

def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def exigir_elegible(shape):
    from OCP.BRep import BRep_Tool
    from OCP.Geom import Geom_Plane,Geom_CylindricalSurface,Geom_SurfaceOfRevolution
    if len(shape.Faces())>192:raise ValueError('El rescate analítico supera el presupuesto de 192 caras.')
    allowed=(Geom_Plane,Geom_CylindricalSurface,Geom_SurfaceOfRevolution)
    if any(not isinstance(BRep_Tool.Surface_s(f.wrapped),allowed) for f in shape.Faces()):
        raise ValueError('Esta reconstrucción conserva superficies analíticas; las superficies libres siguen la estrategia anterior.')

def trabajador(source,base,destination,report):
    source,base,destination,report=map(Path,(source,base,destination,report))
    paths=(source,base,destination,report)
    if len({p.resolve() for p in paths})!=4 or any(a.exists() and b.exists() and a.samefile(b) for i,a in enumerate(paths) for b in paths[i+1:]):
        raise ValueError('Las cuatro rutas del trabajador deben ser distintas.')
    record={'ok':False}
    try:
        sys.path.insert(0,str(Path(__file__).resolve().parent/'motor_superficies'))
        from preprocesador_stl import cargar_exacto
        from reparador_exacto_aislado import ControlExacto
        from topologia_vertices import inspeccionar_vertices
        from calidad_topologica import leer_solido_step_estricto
        from meshfit_detect import detect
        from encuentros_analiticos import reconstruir,normalizar_circulos
        import cadquery as cq
        if not source.is_file() or source.stat().st_size>30*1024**2:raise ValueError('Entrada ausente o mayor de 30 MB.')
        source_hash,base_hash=_sha(source),_sha(base)
        original=cargar_exacto(source)
        if (len(original.faces)>MAX_FACES or not original.is_watertight or not original.is_winding_consistent
                or inspeccionar_vertices(original)['vertices_no_manifold'] or len(original.split(only_watertight=False))!=1):
            raise ValueError('El rescate requiere una única componente cerrada, orientada y sin contactos ambiguos.')
        shape=leer_solido_step_estricto(base);exigir_elegible(shape)
        with tempfile.TemporaryDirectory(prefix='visor_analitico_entrada_') as tmp:
            if ControlExacto(original,Path(tmp)/'entrada.off').pares():raise ValueError('La entrada contiene intersecciones.')
        os.environ['VISOR_STL_DIGITAL']='0'
        result,working=detect(str(source),angle_tol_deg=32.,rms_tol_rel=.01,flat_tol_deg=8.,scan_mode=False)
        required=cilindros_respaldados(result,working)
        if not required:raise ValueError('No hay cilindros confirmados por el STL.')
        with tempfile.TemporaryDirectory(prefix='visor_analitico_construccion_') as tmp:
            new=reconstruir(shape,Path(tmp),original)
        canonical=normalizar_circulos(new)
        cq.exporters.export(new,str(destination))
        shape,cylinders,quality,topology,boundary=validar_cilindros_y_frontera(source,destination,original,required)
        if source_hash!=_sha(source) or base_hash!=_sha(base):raise ValueError('La entrada o candidato base ha cambiado.')
        from prueba_cad import REVISION
        record.update(ok=True,original_sha256=source_hash,base_sha256=base_hash,step_sha256=_sha(destination),
                      calidad=quality,topologia_material=topology,mallado_fino=boundary,cilindros_respaldados=cylinders,
                      inventario=inventario(shape),metodo='encuentros_analiticos_certificados',brep_exacto=True,
                      revision_cad=REVISION,circulos_canonicos=canonical)
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
    key=(_sha(source),_sha(step),os.environ.get('VISOR_PERFIL','precision'))
    if key in _RECHAZOS_TRABAJADOR:
        raise ValueError('No se repite el mismo rescate rechazado con la misma entrada, perfil y parámetros: '+_RECHAZOS_TRABAJADOR[key])
    shape=leer_solido_step_estricto(step)
    exigir_elegible(shape)
    before=inventario(shape)
    base_hash=_sha(step)
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
        avance(78,'Reconstruyendo encuentros analíticos; verificando cilindros, geometría y material')
        env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1',
             'PYTHONUNBUFFERED':'1','PYTHONIOENCODING':'utf-8'}
        with subprocess.Popen([sys.executable,str(Path(__file__).resolve()),str(source),str(step),str(candidate),str(report)],
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
        if record.get('base_sha256')!=base_hash or _sha(step)!=base_hash or record['original_sha256']!=_sha(source) or source_hash!=_sha(source) or record['step_sha256']!=_sha(candidate):
            raise ValueError('El resultado no coincide con los archivos comprobados.')
        after=inventario(leer_solido_step_estricto(candidate))
        if validar_con_prueba is not None:
            from prueba_cad import desde_trabajador
            quality=validar_con_prueba(source,candidate,original,desde_trabajador(record,candidate))
        else:quality=validar(source,candidate,original)
        proof={'aplicado':True,'metodo':'encuentros_analiticos_certificados','antes':before,'despues':after,
               'ajuste_planos_fuente_mm':.00002,'desacuerdo_pcurva_maximo_mm':.00000005,
               'movimiento_propuesta_maximo_mm':.06,'topologia_material':record['topologia_material'],
               'mallado_fino':record['mallado_fino'],'cilindros_respaldados':record['cilindros_respaldados'],
               'original_sha256':source_hash,'step_sha256':record['step_sha256'],'ram_pico_mb':peak,
               'limites_aceptacion_modificados':False,'brep_exacto':record['brep_exacto'],
               'presupuesto_s':presupuesto_recuperacion(len(original.faces))}
        proof['normalizacion_ciclos']=record.get('normalizacion_ciclos',{})
        proof['intentos_contornos']=record.get('intentos_contornos',[])
        if record.get('normalizacion_referencia_material'):
            proof['normalizacion_referencia_material']=record['normalizacion_referencia_material']
        payload=candidate.read_bytes()
        if hashlib.sha256(payload).hexdigest()!=record['step_sha256'] or _sha(source)!=source_hash or _sha(step)!=base_hash:
            raise ValueError('El archivo cambió después de ser validado; no se publica.')
        # La propuesta permanece en la misma partición y sólo sustituye al
        # candidato después de superar TODOS los controles y huellas.
        candidate.replace(step)
        return quality,proof

if __name__=='__main__':
    if len(sys.argv)!=5:raise SystemExit('Uso: reconstruccion_analitica.py entrada.stl base.step salida.step informe.json')
    raise SystemExit(trabajador(*sys.argv[1:]))
