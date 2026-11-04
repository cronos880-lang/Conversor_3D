"""Try certified dense axial construction before the unchanged R14 pipeline."""
from pathlib import Path
import sys,os,json,time,tempfile,secrets,shutil
from certificado_calidad_r15 import sha,firma_motor,verificar

class RutasIncompatibles(ValueError):pass

def comprobar_rutas(source,destination):
 source,destination=map(Path,(source,destination))
 outputs=[destination]+[destination.with_suffix(s) for s in ('.motor.log','.entrada.json','.r15_nucleo.json','.r15_propuesta.json')]
 if any(source.resolve()==p.resolve() or (p.exists() and source.exists() and source.samefile(p)) for p in outputs):raise RutasIncompatibles('La entrada y todos los archivos de salida deben ser distintos')

def elegible(source):
 from politica_conversion import presupuesto_conversion
 p=Path(source)
 return p.is_file() and p.stat().st_size<=30*1024**2 and 50000<=presupuesto_conversion(p.read_bytes())['triangulos']<=200000

def intentar(source,destination,log):
 from perfeccion_calidad import ejecutar_subproceso,NUCLEO,EntradaCambiada
 from avance_conversion import avance
 source,destination=map(Path,(source,destination))
 comprobar_rutas(source,destination)
 if source.resolve()==destination.resolve() or (destination.exists() and source.samefile(destination)):raise ValueError('No se sobrescribe el STL original')
 source_hash=sha(source);previous=sha(destination) if destination.exists() else None;nonce=secrets.token_hex(24);start=time.monotonic()
 with tempfile.TemporaryDirectory(prefix='visor_r15_directo_',dir=destination.parent) as tmp:
  tmp=Path(tmp);candidate=tmp/'candidato.step';report=tmp/'control.json';spec=tmp/'peticion.json'
  spec.write_text(json.dumps(dict(source_sha256=source_hash,motor_sha256=firma_motor(Path(__file__).parent),nonce=nonce)),encoding='utf-8')
  avance(20,'Reconstruyendo perfiles CAD completos desde el STL')
  try:peak=ejecutar_subproceso(NUCLEO/'conversion_directa_worker_r15.py',[source,candidate,report,spec],600,log)
  except Exception:
   if report.is_file():shutil.copyfile(report,destination.with_suffix('.r15_propuesta.json'))
   raise
  record=json.loads(report.read_text(encoding='utf-8'))
  if sha(source)!=source_hash or (sha(destination) if destination.exists() else None)!=previous:raise EntradaCambiada('Cambió una entrada antes de publicar la construcción directa')
  quality=verificar(record,source,candidate,nonce,Path(__file__).parent)
  proof=dict(aplicado=True,metodo='CAD_directo_desde_perfiles_del_STL',original_sha256=source_hash,step_sha256=sha(candidate),
             construccion=record['construccion'],topologia_material=record['topologia_material'],mallado_fino=record['mallado_fino'],
             material_original=record['material_original'],validacion_completa_ejecutada_una_vez=True,limites_aceptacion_modificados=False,
             segundos=time.monotonic()-start,ram_pico_mb=peak)
  shutil.copyfile(report,destination.with_suffix('.r15_nucleo.json'))
  prep=record['preprocesamiento'];destination.with_suffix('.entrada.json').write_text(json.dumps(prep,ensure_ascii=False,indent=2),encoding='utf-8')
  if sha(candidate)!=record['certificado']['step_sha256'] or sha(source)!=source_hash:raise EntradaCambiada('Cambió un archivo tras la validación completa')
  if (sha(destination) if destination.exists() else None)!=previous:raise EntradaCambiada('La salida previa cambió durante la validación')
  candidate.replace(destination)
  return dict(ok=True,preprocesamiento=prep,resultado=dict(motor='CAD directo desde perfiles medidos, verificado',modo='superficies',
      estrategia='construccion_axial_directa_r15',caras_stl=prep['entrada']['caras'],calidad=quality,reconstruccion_directa=proof))

def ejecutar(legacy):
 if len(sys.argv)!=3 or os.environ.get('VISOR_CONSTRUCCION_DIRECTA_R15','1')!='1' or os.environ.get('VISOR_PREPROCESADOR','1')=='0':return legacy()
 source,destination=map(Path,sys.argv[1:])
 try:
  comprobar_rutas(source,destination)
  if not elegible(source):return legacy()
  with destination.with_suffix('.motor.log').open('a',encoding='utf-8',buffering=1) as log:payload=intentar(source,destination,log)
  print(json.dumps(payload,ensure_ascii=True));return 0
 except Exception as exc:
  from perfeccion_calidad import EntradaCambiada
  if isinstance(exc,(EntradaCambiada,RutasIncompatibles)):print(json.dumps(dict(ok=False,error=str(exc)),ensure_ascii=True));return 2
  # No previous conversion is touched by a failed proposal. Run the same R14
  # repair and conversion pipeline, with its original acceptance limits.
  print('[R15] Se conserva el motor anterior: '+str(exc),flush=True)
  return legacy()
