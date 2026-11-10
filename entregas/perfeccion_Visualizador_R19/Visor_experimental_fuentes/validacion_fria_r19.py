"""Repite los controles del núcleo R18 en un proceso frío, sin cambiar límites."""
from pathlib import Path
import sys,os,json,tempfile,time,traceback
ROOT=Path(__file__).parent;KERNEL=ROOT/'motor_calidad'
sys.path[:0]=[str(KERNEL),str(KERNEL/'motor_superficies'),str(ROOT)]

def run(source,step,baseline_run,nonce,report):
 source,step,baseline_run,report=map(Path,(source,step,baseline_run,report));record=dict(ok=False);start=time.monotonic()
 try:
  from certificado_calidad_r15 import sha,identidad,verificar
  from auditoria_step_crudo import auditar_archivo
  from preprocesador_stl import cargar_exacto
  from calidad_topologica import leer_solido_step_estricto
  from motor_v2 import _calidad
  from invariantes_material import InvariantesMaterial
  from validacion_reconstruccion import certificar_topologia_step
  from reconstruccion_curvas import certificar_mallado
  from verificar_original_calidad import comprobar_material_original
  hashes=(sha(source),sha(step),sha(baseline_run));original=cargar_exacto(source)
  raw=auditar_archivo(step)
  if not raw.get('ok') or not raw.get('complete'):raise ValueError('El STEP serializado no supera la auditoría original')
  shape=leer_solido_step_estricto(step);os.environ['VISOR_VERIFICAR_INTERFERENCIAS_CAD']='1'
  quality=_calidad(source,step,original,control_avanzado=True)
  topology=certificar_topologia_step(shape,original,InvariantesMaterial(original))
  with tempfile.TemporaryDirectory() as tmp:boundary=certificar_mallado(shape,original,Path(tmp)/'frontera.off',quality,referencia_superficie=original)
  material=comprobar_material_original(original,shape)
  # Conservar también los controles detallados de la ruta de referencia.
  prior=json.loads(baseline_run.read_text())['payload']['resultado'].get('reconstruccion_fuente',{})
  details=None
  if prior.get('metodo')=='nucleo_axial_y_detalles_originales':
   from reconstruccion_axial_compuesta_r18 import comprobar_detalles_compuestos
   details=comprobar_detalles_compuestos(original,shape,prior['construccion'])
  elif prior.get('metodo')=='revolucion_y_detalles_medidos_del_STL':
   from reconstruccion_axial_medida_r17 import comprobar_detalles
   details=comprobar_detalles(original,shape,prior['construccion'])
  if hashes!=(sha(source),sha(step),sha(baseline_run)):raise ValueError('Una entrada cambió durante el control')
  record.update(ok=True,calidad=quality,topologia_material=topology,mallado_fino=boundary,material_original=material,detalles_original=details,auditoria_step_crudo=raw,certificado=identidad(source,step,nonce,ROOT))
  verificar(record,source,step,nonce,ROOT)
 except Exception as e:record['ok']=False;record['error']=str(e);traceback.print_exc()
 record['seconds']=time.monotonic()-start;report.write_text(json.dumps(record,indent=2))
 return 0 if record['ok'] else 2
if __name__=='__main__':raise SystemExit(run(*sys.argv[1:]))
