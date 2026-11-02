"""Rescate analítico posterior al rechazo de las estrategias aprobadas R9.

Trabajador aislado y acotado. Ningún cambio en los límites geométricos,
la lectura exacta, BOP, material, cilindros o tres mallados finos CGAL.
"""
from __future__ import annotations
import hashlib,json,os,subprocess,sys,tempfile,traceback
from pathlib import Path
from reconstruccion_curvas import (inventario,cilindros_respaldados,validar_cilindros_y_frontera)
MAX_FACES=100_000
_RECHAZOS_TRABAJADOR={}
def presupuesto_recuperacion(triangulos):return 450

def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def exigir_elegible(shape):
    if len(shape.Faces())<80:raise ValueError('Se conserva la reconstrucción compacta anterior.')

def trabajador(source,base,destination,report):
    source,base,destination,report=map(Path,(source,base,destination,report));paths=(source,base,destination,report)
    if len({p.resolve() for p in paths})!=4 or any(a.exists() and b.exists() and a.samefile(b) for i,a in enumerate(paths) for b in paths[i+1:]):
        raise ValueError('Las cuatro rutas del trabajador deben ser distintas.')
    record={'ok':False}
    try:
        sys.path.insert(0,str(Path(__file__).resolve().parent/'motor_superficies'))
        import numpy as np,cadquery as cq
        from OCP.BRep import BRep_Tool
        from OCP.Geom import Geom_SurfaceOfRevolution
        from preprocesador_stl import cargar_exacto
        from reparador_exacto_aislado import ControlExacto
        from topologia_vertices import inspeccionar_vertices
        from calidad_topologica import leer_solido_step_estricto
        from meshfit_detect import detect
        from generar_semilla import generar
        from perfiles_medidos import proponer
        from barridos_medidos import propuestas as barridos
        from extension_cilindros import propuestas as cilindros
        from extension_planos import propuestas as planos
        from geometria_medida import extend_profile,normalizar_circulos
        from constructor_barridos import construir
        from meshfit_brep import build_solid
        if not source.is_file() or source.stat().st_size>30*1024**2:raise ValueError('Entrada ausente o mayor de 30 MB.')
        source_hash,base_hash=_sha(source),_sha(base);original=cargar_exacto(source)
        if (len(original.faces)>MAX_FACES or not original.is_watertight or not original.is_winding_consistent
                or inspeccionar_vertices(original)['vertices_no_manifold'] or len(original.split(only_watertight=False))!=1):
            raise ValueError('La mejora requiere una única componente cerrada, orientada y sin contactos ambiguos.')
        previous=leer_solido_step_estricto(base);exigir_elegible(previous)
        with tempfile.TemporaryDirectory(prefix='visor_perfiles_fuente_') as tmp:
            tmp=Path(tmp)
            if ControlExacto(original,tmp/'entrada.off').pares():raise ValueError('La entrada contiene intersecciones.')
            os.environ['VISOR_STL_DIGITAL']='0'
            result,working=detect(str(source),angle_tol_deg=32.,rms_tol_rel=.01,flat_tol_deg=8.,scan_mode=False,mesh_input=original.copy())
            required=cilindros_respaldados(result,working)
            seed=None
            cached=os.environ.get('PILOTO_HIPOTESIS_STEP')
            if cached:
                saved=Path(cached);identity=json.loads(saved.with_suffix('.json').read_text())
                if identity['stl_sha256']!=source_hash or identity['step_sha256']!=_sha(saved):raise ValueError('La hipótesis guardada no corresponde a la entrada')
                seed=cq.importers.importStep(str(saved)).val();record['hipotesis_cache_investigacion']=identity
            elif result['primitives']:
                try:seed=generar(source,result,working,tmp/'hipotesis_no_aprobada.step')
                except ValueError as exc:record['hipotesis_descartada']=str(exc)
            if seed is not None:
                from cilindros_guiados import confirmar
                required,record['cilindros_adicionales_fuente']=confirmar(seed.Faces(),working,required)
            from esferas_guiadas import propuestas as esferas
            sphere_extras,sphere_proof=esferas(seed.Faces(),working,required) if seed is not None else ([],[])
            record['esferas_fuente']=sphere_proof
            surfaces,profiles=proponer(seed.Faces(),[BRep_Tool.Surface_s(f.wrapped) for f in seed.Faces()],working,required) if seed is not None else ([],[])
            plane_extras=planos(result,working) if not any(p['tipo']=='revolucion_medida' for p in profiles) else []
            surfaces,sweep_extras,sweep_proof=barridos(seed.Faces() if seed is not None else [],surfaces,working,required,plane_extras)
            extras=sphere_extras+cilindros(working,required,surfaces if sweep_extras else ())+ (plane_extras if sweep_extras or seed is None else [])+sweep_extras
            for proof in profiles:
                if proof['tipo']=='revolucion_medida':
                    s=surfaces[proof['caras'][0]];extras.append((np.array(proof['indices_fuente']),Geom_SurfaceOfRevolution(extend_profile(s.BasisCurve()),s.Axis())))
            if sweep_extras or seed is None:
                from barridos_medidos import restos_fuente
                additional,remaining_proof=restos_fuente(result,working,extras,required);extras+=additional;sweep_extras+=additional;sweep_proof+=remaining_proof
                from barridos_medidos import fusionar_continuaciones
                extras,merge_proof=fusionar_continuaciones(working,extras);sweep_proof+=merge_proof
            if seed is None and not sweep_extras and not any(p['tipo']=='revolucion_medida' for p in profiles):raise ValueError('No hay perfiles medidos para mejorar el resultado.')
            os.environ['VISOR_PLANOS_MEDIDOS']='1';os.environ['VISOR_MEDIAS_CANAS_COMPLETAS']='1';os.environ.pop('VISOR_DEPURAR_CONTORNOS',None)
            rebuilt,info=build_solid(result,working,organic=False,max_rounds=1,extra_regions=extras,ajuste_ia=False,
                precision_reparacion=True,refinar_curvas=True,contornos_compartidos=True,constructor_medidos=construir)
            if rebuilt is None or not info.get('valid') or not info.get('solid'):raise ValueError('La construcción medida no forma un sólido válido: '+str(info))
            new=cq.Shape.cast(rebuilt)
            from realimentacion_bop import resolver as resolver_conjunto
            new,record['realimentacion_bop']=resolver_conjunto(new)
            # Reunir sólo dominios cilíndricos idénticos; no ajustar radios.
            # La aceptación final en frío, fuente y tres mallados sigue después.
            try:
                from cilindros_contiguos import proponer as reunir_cilindros
                new,record['reunion_cilindros_postconstruccion']=reunir_cilindros(new)
            except ValueError as exc:record['reunion_cilindros_omitida']=str(exc)
            if len(new.Faces())>.75*len(previous.Faces()):raise ValueError('La propuesta no reduce al menos un 25% las caras.')
            from constructor_barridos import ULTIMA_SUBDIVISION
            record['subdivisiones_contorno']=ULTIMA_SUBDIVISION
            from constructor_barridos import RETIRADAS_HIPOTESIS
            record['hipotesis_retiradas']=RETIRADAS_HIPOTESIS
            from constructor_barridos import REFINAMIENTOS_LIBRES
            record['refinamiento_regiones_libres']=REFINAMIENTOS_LIBRES
            from exportacion_solida import exportar
            canonical=normalizar_circulos(new);record['exportacion_solida']=exportar(new,destination)
        shape,cylinders,quality,topology,boundary=validar_cilindros_y_frontera(source,destination,original,required)
        if source_hash!=_sha(source) or base_hash!=_sha(base):raise ValueError('La entrada o candidato base ha cambiado.')
        from prueba_cad import REVISION
        record.update(ok=True,original_sha256=source_hash,base_sha256=base_hash,step_sha256=_sha(destination),
            calidad=quality,topologia_material=topology,mallado_fino=boundary,cilindros_respaldados=cylinders,
            inventario=inventario(shape),metodo='perfiles_medidos_certificados',brep_exacto=True,
            revision_cad=REVISION,circulos_canonicos=canonical,perfiles_fuente=[{k:v for k,v in p.items() if k!='indices_fuente'} for p in profiles],barridos_fuente=sweep_proof)
    except Exception as exc:
        if hasattr(exc,'diagnostico'):record['diagnostico_exportacion']=exc.diagnostico
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
        avance(78,'Reconstruyendo perfiles medidos del STL; verificando geometría, material y cilindros')
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
        if after['caras']>.75*before['caras']:raise ValueError('La propuesta no reduce al menos un 25% las caras.')
        if validar_con_prueba is not None:
            from prueba_cad import desde_trabajador
            quality=validar_con_prueba(source,candidate,original,desde_trabajador(record,candidate))
        else:quality=validar(source,candidate,original)
        proof={'aplicado':True,'metodo':'perfiles_medidos_certificados','antes':before,'despues':after,
               'ajuste_planos_fuente_mm':.0001,'desacuerdo_pcurva_maximo_mm':.00000005,
               'movimiento_propuesta_maximo_mm':.012,'topologia_material':record['topologia_material'],
               'mallado_fino':record['mallado_fino'],'cilindros_respaldados':record['cilindros_respaldados'],
               'original_sha256':source_hash,'step_sha256':record['step_sha256'],'ram_pico_mb':peak,
               'limites_aceptacion_modificados':False,'brep_exacto':record['brep_exacto'],
               'presupuesto_s':presupuesto_recuperacion(len(original.faces))}
        proof['subdivisiones_contorno']=record.get('subdivisiones_contorno',[])
        proof['perfiles_fuente']=record.get('perfiles_fuente',[])
        proof['barridos_fuente']=record.get('barridos_fuente',[])
        proof['planos_fuente_max_mm']=.0001
        proof['desviacion_perfil_fuente_max_mm']=.003
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

def ejecutar_principal(main,output_type,validar):
    import contextlib
    if len(sys.argv)!=3:return main()
    source,destination=map(Path,sys.argv[1:]);output=output_type(sys.stdout)
    with contextlib.redirect_stdout(output):code=main()
    lines=output.getvalue().splitlines()
    try:payload=json.loads(lines[-1])
    except (ValueError,IndexError):raise RuntimeError('El motor no emitió un resultado verificable.')
    if code==0 and payload.get('ok') and os.environ.get('VISOR_PERFILES_MEDIDOS','1')=='1' and not payload.get('preprocesamiento',{}).get('reparado'):
        try:
            from preprocesador_stl import cargar_exacto
            original=cargar_exacto(source)
            with destination.with_suffix('.motor.log').open('a',encoding='utf-8',buffering=1) as log:
                quality,proof=intentar_refinar(source,destination,original,
                    lambda s,d,m:validar(s,d,m,control_avanzado=True),log,
                    validar_con_prueba=lambda s,d,m,p:validar(s,d,m,control_avanzado=True,prueba_cad=p))
            result=payload['resultado'];result['calidad']=quality;result['reconstruccion_medida']=proof
            result['modo']='superficies';result['estrategia']='perfiles_medidos_certificados';result['motor']='Reconstrucción de perfiles medidos del STL, verificada'
        except Exception as exc:
            payload['mejora_perfiles_medidos']={'aplicado':False,'motivo':str(exc),'conservado_resultado_anterior':True}
    print(json.dumps(payload,ensure_ascii=True));return code

if __name__=='__main__':
    if len(sys.argv)!=5:raise SystemExit('Uso: reconstruccion_medida.py entrada.stl base.step salida.step informe.json')
    raise SystemExit(trabajador(*sys.argv[1:]))
