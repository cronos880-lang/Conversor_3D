"""Reconstrucción aislada desde STL, con todos los controles finales originales."""
from pathlib import Path
import sys,os,json,time,tempfile,traceback
KERNEL=Path(__file__).resolve().parent
sys.path[:0]=[str(KERNEL/'motor_superficies'),str(KERNEL),str(KERNEL.parent)]
from certificado_calidad_r15 import sha,firma_motor,identidad

def ejecutar(source,destination,spec_path,report_path):
 source,destination,spec_path,report_path=map(Path,(source,destination,spec_path,report_path));paths=(source,destination,spec_path,report_path)
 if len({p.resolve()for p in paths})!=4 or destination.exists() or report_path.exists() or any(a.exists() and b.exists() and a.samefile(b)for i,a in enumerate(paths)for b in paths[i+1:]):raise ValueError('Las rutas deben ser nuevas y distintas')
 start=time.monotonic();record=dict(ok=False);source_hash=sha(source);code=firma_motor(KERNEL)
 def phase(name):
  record.setdefault('fases',[]).append(dict(fase=name,segundos=time.monotonic()-start));report_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print('[R18]',name,round(time.monotonic()-start,2),flush=True)
 try:
  spec=json.loads(spec_path.read_text(encoding='utf-8'))
  from perfiles_precision import obtener_perfil
  profile=spec['perfil'];os.environ['VISOR_PERFIL']=profile['id']
  if profile!=obtener_perfil() or (source_hash,code)!=(spec['source_sha256'],spec['motor_sha256']):raise ValueError('La petición no corresponde al STL, código o perfil')
  from preprocesador_stl import cargar_exacto,diagnosticar
  from reconstruccion_axial_compuesta_r18 import proponer,comprobar_detalles_compuestos as comprobar_detalles
  from reparador_exacto_aislado import ControlExacto
  from exportacion_solida import exportar
  from calidad_topologica import leer_solido_step_estricto
  from motor_v2 import _calidad
  from invariantes_material import InvariantesMaterial
  from validacion_reconstruccion import certificar_topologia_step
  from reconstruccion_curvas import certificar_mallado
  from verificar_original_calidad import comprobar_material_original
  phase('estructura_fuente');mesh=cargar_exacto(source);diag=diagnosticar(mesh)
  if not 64<=len(mesh.faces)<=50000 or diag['ruta']!='paso_directo' or mesh.euler_number not in (0,2) or len(mesh.split(only_watertight=False))!=1:raise ValueError('Se conserva la ruta anterior para esta estructura de STL')
  with tempfile.TemporaryDirectory(prefix='visor_r18_fuente_')as tmp:
   if ControlExacto(mesh,Path(tmp)/'fuente.off').pares():raise ValueError('El STL original presenta autointersecciones')
  attempts=[]
  for strategy in ('marco_centrado','cortes_previos'):
   record=dict(ok=False,intentos=attempts,estrategia_construccion=strategy)
   attempt_start=time.monotonic()
   try:
    if source_hash!=sha(source)or code!=firma_motor(KERNEL):raise ValueError('Una entrada o el motor cambió durante el control')
    phase('propuesta_CAD_con_detalles_del_original');shape,record['construccion']=proponer(mesh,estrategia=strategy)
    with tempfile.TemporaryDirectory(prefix='visor_r18_control_')as tmp:
     tmp=Path(tmp)
     phase('exportacion_y_lectura_fria');record['exportacion']=exportar(shape,destination);shape=leer_solido_step_estricto(destination)
     os.environ['VISOR_VERIFICAR_INTERFERENCIAS_CAD']='1';phase('CAD_exacto_BOP_y_geometria_original');record['calidad']=_calidad(source,destination,mesh,control_avanzado=True)
     record['topologia_material']=certificar_topologia_step(shape,mesh,InvariantesMaterial(mesh));phase('tres_mallados_finos');record['mallado_fino']=certificar_mallado(shape,mesh,tmp/'frontera.off',record['calidad'],referencia_superficie=mesh)
     phase('material_y_detalles_del_original');record['material_original']=comprobar_material_original(mesh,shape);record['detalles_original']=comprobar_detalles(mesh,shape,record['construccion'])
    attempts.append(dict(estrategia=strategy,aceptada=True,segundos=time.monotonic()-attempt_start))
    break
   except Exception as exc:
    destination.unlink(missing_ok=True)
    attempts.append(dict(estrategia=strategy,aceptada=False,error=str(exc),segundos=time.monotonic()-attempt_start,fases=record.get('fases',[])))
    if source_hash!=sha(source)or code!=firma_motor(KERNEL):raise ValueError('Una entrada o el motor cambió durante el control')from exc
    if strategy=='cortes_previos':raise
    print('[R18] Candidato descartado; se comprueba otra construcción:',str(exc),flush=True)
  if source_hash!=sha(source) or code!=firma_motor(KERNEL):raise ValueError('Una entrada o el motor cambió durante el control')
  record['preprocesamiento']=dict(version=1,original_sha256=source_hash,habilitado=True,reparado=False,original_conservado=True,entrada=diag,ruta_seleccionada='paso_directo',resultado='STL original; reconstrucción CAD medida y validada')
  record['certificado']=identidad(source,destination,spec['nonce'],KERNEL);record.update(ok=True,original_sha256=source_hash,step_sha256=sha(destination),limites_aceptacion_modificados=False);phase('validacion_completada')
 except Exception as exc:record['error']=str(exc);destination.unlink(missing_ok=True);traceback.print_exc()
 record['seconds']=time.monotonic()-start;report_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');return 0 if record['ok'] else 2

if __name__=='__main__':raise SystemExit(ejecutar(*sys.argv[1:]))
