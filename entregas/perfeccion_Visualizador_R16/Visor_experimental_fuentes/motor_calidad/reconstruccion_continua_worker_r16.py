"""Propuesta aislada R16, comprobada contra el STL y el resultado R15.

El trabajador no sobrescribe el resultado base. Toda propuesta rechazada se
elimina y el proceso principal conserva los bytes de la conversión anterior.
"""
from pathlib import Path
import sys,os,json,time,tempfile,traceback
KERNEL=Path(__file__).resolve().parent
# A Windows launch does not need a preconfigured PYTHONPATH or an installed
# editable checkout. Keep kernel modules first, then the application's helpers.
sys.path[:0]=[str(KERNEL/'motor_superficies'),str(KERNEL),str(KERNEL.parent)]
from certificado_calidad_r15 import sha,firma_motor,identidad

def configurar_perfil(spec):
 """El lanzador antiguo inicia en precisión; restaurar el perfil firmado."""
 from perfiles_precision import obtener_perfil
 profile=spec['perfil']
 if profile.get('id') not in ('precision','impresion'):raise ValueError('Perfil solicitado no reconocido')
 os.environ['VISOR_PERFIL']=profile['id']
 if obtener_perfil()!=profile or spec['previous_quality']['perfil_validacion']!=profile:raise ValueError('El perfil no coincide con sus límites aprobados')

def ejecutar(source,base,destination,spec_path,report_path):
 source,base,destination,report_path,spec_path=map(Path,(source,base,destination,report_path,spec_path))
 paths=(source,base,destination,report_path,spec_path)
 if len({p.resolve() for p in paths})!=5 or any(a.exists() and b.exists() and a.samefile(b) for i,a in enumerate(paths) for b in paths[i+1:]):raise ValueError('Las rutas del trabajador deben ser distintas')
 if destination.exists() or report_path.exists():raise ValueError('La propuesta y su informe deben ser nuevos')
 record=dict(ok=False);start=time.monotonic();source_hash=sha(source);base_hash=sha(base);code=firma_motor(Path(__file__).parent)
 def phase(name):
  record.setdefault('fases',[]).append(dict(fase=name,segundos=time.monotonic()-start));report_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print('[R16]',name,round(time.monotonic()-start,2),flush=True)
 try:
  spec=json.loads(spec_path.read_text(encoding='utf-8'))
  if (spec['source_sha256'],spec['base_sha256'],spec['motor_sha256'])!=(source_hash,base_hash,code):raise ValueError('La petición no corresponde al original, base o motor')
  configurar_perfil(spec)
  from preprocesador_stl import cargar_exacto,diagnosticar
  from calidad_topologica import leer_solido_step_estricto
  from exportacion_solida import exportar
  from motor_v2 import _calidad
  from invariantes_material import InvariantesMaterial
  from validacion_reconstruccion import certificar_topologia_step
  from reconstruccion_curvas import certificar_mallado,InterseccionesMalladoFino
  from verificar_original_calidad import comprobar_material_original
  from cilindros_contiguos import certificar_recortes
  from reparador_exacto_aislado import ControlExacto
  from reconstruccion_paredes_r16 import proponer,corresponde_firma
  from mejora_regional_aislada import comparar_calidad
  phase('estructura_original_y_base');mesh=cargar_exacto(source);diag=diagnosticar(mesh);previous=leer_solido_step_estricto(base)
  if not 1<=len(mesh.faces)<=50000 or diag['ruta']!='paso_directo' or len(mesh.split(only_watertight=False))!=1:raise ValueError('Se conserva la ruta anterior para esta estructura de STL')
  if spec['previous_quality']['perfil_validacion']['id']!=os.environ.get('VISOR_PERFIL','precision'):raise ValueError('El perfil cambió desde la conversión anterior')
  with tempfile.TemporaryDirectory(prefix='visor_r16_control_') as tmp:
   tmp=Path(tmp)
   if ControlExacto(mesh,tmp/'original.off').pares():raise ValueError('El STL original contiene autointersecciones')
   blocked=set();retractions=[]
   for attempt in range(3):
    phase('construccion_de_paredes_y_bandas_continuas');shape,proof=proponer(previous,reference_volume=abs(mesh.volume),blocked_faces=blocked)
    if len(shape.Faces())>.95*len(previous.Faces()):raise ValueError('La propuesta no aporta una reducción suficiente de fragmentación')
    phase('exportacion_y_relectura_fria');record['exportacion_solida']=exportar(shape,destination);shape=leer_solido_step_estricto(destination)
    record['cilindros_preservados']=certificar_recortes(previous,shape)
    os.environ['VISOR_VERIFICAR_INTERFERENCIAS_CAD']='1';phase('CAD_exacto_BOP_y_geometria_original');quality=_calidad(source,destination,mesh,control_avanzado=True)
    record['comparacion_no_regresion']=comparar_calidad(spec['previous_quality'],quality)
    topology=certificar_topologia_step(shape,mesh,InvariantesMaterial(mesh));phase('tres_mallados_finos')
    try:fine=certificar_mallado(shape,mesh,tmp/'frontera.off',quality,referencia_superficie=mesh)
    except InterseccionesMalladoFino as exc:
     import numpy as np
     affected=set();read_faces=shape.Faces()
     for i in exc.caras_cad:
      f=read_faces[i]
      matches=[p for p in proof if p.get('ok') and 'new_face_signature' in p and corresponde_firma(f,p['new_face_signature'])]
      if len(matches)==1:affected.update(matches[0]['faces'])
     if not affected-blocked or attempt==2:raise
     retractions.append(dict(caras_cad=exc.caras_cad,caras_fuente_retiradas=sorted(affected),pares=exc.pares,resolucion_mm=exc.resolucion_mm,step_sha256=sha(destination)))
     blocked.update(affected);destination.unlink();continue
    record.update(construccion=proof,calidad=quality,topologia_material=topology,mallado_fino=fine,retroacciones_cgal=retractions);break
   else:raise ValueError('No se obtiene una propuesta aprobada')
   phase('material_del_STL_original');record['material_original']=comprobar_material_original(mesh,shape)
  if (source_hash,base_hash,code)!=(sha(source),sha(base),firma_motor(Path(__file__).parent)):raise ValueError('Una entrada o el motor cambió durante el control')
  record.update(original_sha256=source_hash,base_sha256=base_hash,step_sha256=sha(destination),limites_aceptacion_modificados=False,caras_antes=len(previous.Faces()),caras_despues=len(shape.Faces()),brep_exacto=True)
  record['certificado']=identidad(source,destination,spec['nonce'],Path(__file__).parent);record['ok']=True;phase('validacion_completa')
 except Exception as exc:
  record['error']=str(exc);destination.unlink(missing_ok=True);traceback.print_exc()
  for name in ('caras_cad','resolucion_mm','pares'):
   if hasattr(exc,name):record[name]=getattr(exc,name)
 record['seconds']=time.monotonic()-start;report_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');return 0 if record['ok'] else 2

if __name__=='__main__':raise SystemExit(ejecutar(*sys.argv[1:]))
