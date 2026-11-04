"""Refinamiento R16 posterior a una conversión completa y aprobada de R15."""
from pathlib import Path
import sys,os,json,time,tempfile,secrets,shutil,contextlib
from certificado_calidad_r15 import sha,firma_motor,verificar

class RutasIncompatibles(ValueError):pass

def comprobar_rutas(source,step):
 from respaldo_conversion import rutas
 source,step=map(Path,(source,step));backup,report=rutas(step,etapa='r16')
 outputs=[step,backup,report,step.with_suffix('.r16_nucleo.json'),step.with_suffix('.r16_propuesta.json'),step.with_suffix('.motor.log')]
 if any(source.resolve()==p.resolve() or (source.exists() and p.exists() and source.samefile(p)) for p in outputs):raise RutasIncompatibles('El STL y los archivos de resultado R16 deben ser distintos')

def elegible(payload):
 from respaldo_conversion import calidad_aprobada
 if not calidad_aprobada(payload) or payload.get('preprocesamiento',{}).get('reparado'):return False
 q=payload['resultado']['calidad'];t=q.get('tipos_caras',{});count=q.get('caras_step',0)
 return (80<=count<=800 and t.get('GeomAbs_BSplineSurface',0)>=6 and t.get('GeomAbs_Plane',0)>=2 and t.get('GeomAbs_Cylinder',0)>=1 and t.get('GeomAbs_SurfaceOfExtrusion',0)>=1)

def intentar(source,step,payload,log):
 from perfeccion_calidad import ejecutar_subproceso,NUCLEO,EntradaCambiada
 from mejora_regional_aislada import comparar_calidad
 from respaldo_conversion import guardar
 from avance_conversion import avance
 from perfiles_precision import obtener_perfil
 source,step=map(Path,(source,step));comprobar_rutas(source,step)
 if not elegible(payload):return None
 if source.stat().st_size>30*1024**2:raise ValueError('Fuera del presupuesto de entrada')
 source_hash,base_hash=sha(source),sha(step);nonce=secrets.token_hex(24);start=time.monotonic();prior=payload['resultado']['calidad']
 if payload.get('preprocesamiento',{}).get('original_sha256')!=source_hash:raise EntradaCambiada('El resultado no corresponde al STL original')
 profile=obtener_perfil()
 if prior.get('perfil_validacion')!=profile:raise EntradaCambiada('El perfil cambió desde la conversión anterior')
 guardar(source,step,payload,etapa='r16')
 with tempfile.TemporaryDirectory(prefix='visor_r16_verificado_',dir=step.parent) as tmp:
  tmp=Path(tmp);candidate=tmp/'candidato.step';report=tmp/'control.json';spec=tmp/'peticion.json'
  spec.write_text(json.dumps(dict(source_sha256=source_hash,base_sha256=base_hash,motor_sha256=firma_motor(Path(__file__).parent),nonce=nonce,perfil=profile,previous_quality=prior)),encoding='utf-8')
  avance(78,'Reconstruyendo paredes y redondeos continuos; comprobando geometría y material')
  try:peak=ejecutar_subproceso(NUCLEO/'reconstruccion_continua_worker_r16.py',[source,step,candidate,spec,report],420,log)
  except Exception as exc:
   if report.is_file():shutil.copyfile(report,step.with_suffix('.r16_propuesta.json'))
   try:unchanged=(sha(source),sha(step))==(source_hash,base_hash)
   except OSError:unchanged=False
   if not unchanged:raise EntradaCambiada('Cambió una entrada durante una propuesta rechazada') from exc
   raise
  record=json.loads(report.read_text(encoding='utf-8'))
  if (sha(source),sha(step))!=(source_hash,base_hash):raise EntradaCambiada('Cambió una entrada durante la reconstrucción continua')
  if record.get('base_sha256')!=base_hash:raise ValueError('El control no corresponde al STEP anterior')
  quality=verificar(record,source,candidate,nonce,Path(__file__).parent);comparison=comparar_calidad(prior,quality)
  proof=dict(aplicado=True,metodo='paredes_y_bandas_continuas_con_frontera_fija',original_sha256=source_hash,step_anterior_sha256=base_hash,step_sha256=sha(candidate),caras_antes=prior['caras_step'],caras_despues=quality['caras_step'],comparacion_no_regresion=comparison,construccion=record['construccion'],cilindros_preservados=record['cilindros_preservados'],topologia_material=record['topologia_material'],mallado_fino=record['mallado_fino'],material_original=record['material_original'],retroacciones_cgal=record.get('retroacciones_cgal',[]),seconds=time.monotonic()-start,ram_pico_mb=peak,limites_aceptacion_modificados=False)
  shutil.copyfile(report,step.with_suffix('.r16_nucleo.json'))
  if sha(source)!=source_hash or sha(step)!=base_hash or sha(candidate)!=record['certificado']['step_sha256']:raise EntradaCambiada('Un archivo cambió después del control completo')
  candidate.replace(step);return quality,proof

def ejecutar(legacy,output_type):
 if len(sys.argv)!=3:return legacy()
 source,step=map(Path,sys.argv[1:])
 try:comprobar_rutas(source,step)
 except RutasIncompatibles as exc:print(json.dumps(dict(ok=False,error=str(exc)),ensure_ascii=True));return 2
 output=output_type(sys.stdout)
 with contextlib.redirect_stdout(output):code=legacy()
 try:payload=json.loads(output.getvalue().splitlines()[-1])
 except (ValueError,IndexError):raise RuntimeError('El motor anterior no emitió un resultado verificable')
 if code==0 and os.environ.get('VISOR_RECONSTRUCCION_CONTINUA_R16','1')=='1' and os.environ.get('VISOR_PREPROCESADOR','1')!='0' and elegible(payload):
  try:
   with step.with_suffix('.motor.log').open('a',encoding='utf-8',buffering=1) as log:changed=intentar(source,step,payload,log)
   if changed is not None:
    quality,proof=changed;result=payload['resultado'];result['calidad']=quality;result['reconstruccion_continua']=proof
    if 'calidad_original' in result:result['calidad_original']=quality
    result.update(estrategia='superficies_continuas_verificadas_r16',motor='Superficies CAD continuas verificadas',modo='superficies')
  except Exception as exc:
   from perfeccion_calidad import EntradaCambiada
   if isinstance(exc,EntradaCambiada):payload.update(ok=False,error=str(exc));code=2
   else:payload['reconstruccion_continua']=dict(aplicado=False,motivo=str(exc),conservado_resultado_anterior=True)
 print(json.dumps(payload,ensure_ascii=True));return code
