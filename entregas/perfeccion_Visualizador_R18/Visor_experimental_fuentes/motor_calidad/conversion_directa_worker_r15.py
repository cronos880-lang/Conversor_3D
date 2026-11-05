"""Isolated compact source construction with one complete cold final validation."""
from pathlib import Path
import sys,os,json,time,tempfile,traceback
sys.path.insert(0,str(Path(__file__).parent/'motor_superficies'))
from certificado_calidad_r15 import sha,firma_motor,identidad

def ejecutar(source,destination,report_path,spec_path):
 source,destination,report_path,spec_path=map(Path,(source,destination,report_path,spec_path))
 if len({p.resolve() for p in (source,destination,report_path,spec_path)})!=4 or destination.exists() or report_path.exists():raise ValueError('Las salidas deben ser nuevas y distintas')
 record=dict(ok=False);start=time.monotonic();source_hash=sha(source);code=firma_motor(Path(__file__).parent)
 def phase(name):
  record.setdefault('fases',[]).append(dict(fase=name,segundos=time.monotonic()-start))
  report_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print('[R15]',name,round(time.monotonic()-start,2),flush=True)
 try:
  spec=json.loads(spec_path.read_text(encoding='utf-8'))
  if spec['source_sha256']!=source_hash or spec['motor_sha256']!=code:raise ValueError('La petición no coincide con entrada y motor')
  from preprocesador_stl import cargar_exacto,diagnosticar
  from construccion_axial_r15 import construir,marco_axial
  from exportacion_solida import exportar
  from calidad_topologica import leer_solido_step_estricto
  from motor_v2 import _calidad
  from invariantes_material import InvariantesMaterial
  from validacion_reconstruccion import certificar_topologia_step
  from reconstruccion_curvas import certificar_mallado
  from verificar_original_calidad import comprobar_material_original
  from reparador_exacto_aislado import ControlExacto
  phase('estructura_fuente');mesh=cargar_exacto(source)
  if not 50000<=len(mesh.faces)<=200000:raise ValueError('Fuera de la familia densa acotada')
  marco_axial(mesh);diag=diagnosticar(mesh)
  if diag['ruta']!='paso_directo':raise ValueError('Se conserva la reparación y conversión anterior para esta topología')
  if len(mesh.split(only_watertight=False))!=1:raise ValueError('Se requiere una única componente')
  with tempfile.TemporaryDirectory(prefix='visor_r15_') as tmp:
   if ControlExacto(mesh,Path(tmp)/'fuente.off').pares():raise ValueError('La fuente contiene autointersecciones')
   phase('construccion_CAD_desde_perfiles');shape,record['construccion']=construir(mesh)
   phase('exportacion_y_lectura_fria');record['exportacion']=exportar(shape,destination)
   shape=leer_solido_step_estricto(destination)
   phase('CAD_exacto_interferencias_y_geometria_original');record['calidad']=_calidad(source,destination,mesh,control_avanzado=True)
   record['topologia_material']=certificar_topologia_step(shape,mesh,InvariantesMaterial(mesh))
   phase('tres_mallados_finos');record['mallado_fino']=certificar_mallado(shape,mesh,Path(tmp)/'frontera.off',record['calidad'],referencia_superficie=mesh)
   phase('material_del_STL_original');record['material_original']=comprobar_material_original(mesh,shape)
  if source_hash!=sha(source) or code!=firma_motor(Path(__file__).parent):raise ValueError('Cambió la entrada o el motor durante el control')
  record['preprocesamiento']=dict(version=1,original_sha256=source_hash,habilitado=True,reparado=False,original_conservado=True,
                                 entrada=diag,ruta_seleccionada='paso_directo',resultado='mismo STL; construcción CAD directa verificada')
  record['certificado']=identidad(source,destination,spec['nonce'],Path(__file__).parent)
  record['step_sha256']=sha(destination);record['original_sha256']=source_hash
  record['ok']=True;phase('validacion_completada')
 except Exception as exc:
  record['error']=str(exc);destination.unlink(missing_ok=True);traceback.print_exc()
 record['seconds']=time.monotonic()-start;report_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
 return 0 if record['ok'] else 2

if __name__=='__main__':raise SystemExit(ejecutar(*sys.argv[1:]))
