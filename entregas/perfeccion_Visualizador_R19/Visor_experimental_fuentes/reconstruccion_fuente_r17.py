"""Construcción CAD inicial para una familia geométrica acotada, con retorno a R16."""
from pathlib import Path
import os,sys,json,time,tempfile,secrets,shutil
from certificado_calidad_r15 import sha,firma_motor,verificar

class RutasIncompatibles(ValueError):pass

def comprobar_rutas(source,destination):
 source,destination=map(Path,(source,destination))
 outputs=[destination]+[destination.with_suffix(s)for s in ('.r17_nucleo.json','.r17_propuesta.json','.motor.log','.entrada.json')]
 if any(source.resolve()==p.resolve() or (source.exists() and p.exists() and source.samefile(p))for p in outputs):raise RutasIncompatibles('El STL y las salidas R17 deben ser distintos')

def elegible(source):
 from politica_conversion import presupuesto_conversion
 p=Path(source)
 if not p.is_file() or p.stat().st_size>30*1024**2:return False
 count=presupuesto_conversion(p.read_bytes())['triangulos']
 if not 400<=count<=50000:return False
 from preprocesador_stl import cargar_exacto
 mesh=cargar_exacto(p)
 return bool(mesh.euler_number==0 and mesh.is_watertight and mesh.is_winding_consistent)

def intentar(source,destination,log):
 from perfeccion_calidad import ejecutar_subproceso,NUCLEO,EntradaCambiada
 from perfiles_precision import obtener_perfil
 from avance_conversion import avance
 source,destination=map(Path,(source,destination));comprobar_rutas(source,destination)
 source_hash=sha(source);old_hash=sha(destination)if destination.exists()else None;nonce=secrets.token_hex(24);profile=obtener_perfil();start=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='visor_r17_fuente_',dir=destination.parent)as tmp:
  tmp=Path(tmp);candidate=tmp/'candidato.step';spec=tmp/'peticion.json';report=tmp/'control.json';spec.write_text(json.dumps(dict(source_sha256=source_hash,motor_sha256=firma_motor(Path(__file__).parent),nonce=nonce,perfil=profile)),encoding='utf-8')
  avance(17,'Buscando superficies de revolución y conservando los detalles originales')
  try:peak=ejecutar_subproceso(NUCLEO/'reconstruccion_fuente_worker_r17.py',[source,candidate,spec,report],420,log)
  except Exception as exc:
   if report.is_file():shutil.copyfile(report,destination.with_suffix('.r17_propuesta.json'))
   if sha(source)!=source_hash or (sha(destination)if destination.exists()else None)!=old_hash:raise EntradaCambiada('Cambió una entrada durante una propuesta rechazada')from exc
   raise
  record=json.loads(report.read_text(encoding='utf-8'))
  if sha(source)!=source_hash or (sha(destination)if destination.exists()else None)!=old_hash:raise EntradaCambiada('Cambió una entrada durante la reconstrucción')
  quality=verificar(record,source,candidate,nonce,Path(__file__).parent);detail=record['detalles_original'];expected=2*sum(g['faces']for g in record['construccion']['rebajes'])
  if detail.get('discrepancias')!=0 or detail.get('puntos')!=expected:raise ValueError('Falta comprobar cada cara de los rebajes originales')
  proof=dict(aplicado=True,metodo='revolucion_y_detalles_medidos_del_STL',original_sha256=source_hash,step_sha256=sha(candidate),construccion=record['construccion'],topologia_material=record['topologia_material'],mallado_fino=record['mallado_fino'],material_original=record['material_original'],detalles_original=detail,segundos=time.monotonic()-start,ram_pico_mb=peak,limites_aceptacion_modificados=False)
  shutil.copyfile(report,destination.with_suffix('.r17_nucleo.json'))
  if sha(source)!=source_hash or (sha(destination)if destination.exists()else None)!=old_hash or sha(candidate)!=record['certificado']['step_sha256']:raise EntradaCambiada('Cambió un archivo después del control completo')
  candidate.replace(destination);prep=record['preprocesamiento'];destination.with_suffix('.entrada.json').write_text(json.dumps(prep,ensure_ascii=False,indent=2),encoding='utf-8')
  return dict(ok=True,preprocesamiento=prep,resultado=dict(motor='CAD medido con detalles originales verificados',modo='superficies',estrategia='reconstruccion_fuente_verificada_r17',caras_stl=prep['entrada']['caras'],calidad=quality,reconstruccion_fuente=proof))

def ejecutar(legacy):
 if len(sys.argv)!=3 or os.environ.get('VISOR_RECONSTRUCCION_FUENTE_R17','1')!='1' or os.environ.get('VISOR_PREPROCESADOR','1')=='0':return legacy()
 source,destination=map(Path,sys.argv[1:])
 try:
  comprobar_rutas(source,destination)
  if not elegible(source):return legacy()
  with destination.with_suffix('.motor.log').open('a',encoding='utf-8',buffering=1)as log:payload=intentar(source,destination,log)
  print(json.dumps(payload,ensure_ascii=True));return 0
 except Exception as exc:
  from perfeccion_calidad import EntradaCambiada
  if isinstance(exc,(EntradaCambiada,RutasIncompatibles))or getattr(exc,'codigo',None)=='cancelado':print(json.dumps(dict(ok=False,error=str(exc)),ensure_ascii=True));return 2
  print('[R17] Se conserva la ruta R16: '+str(exc),flush=True);return legacy()
