"""Reunir representaciones medidas, conservando las conversiones compactas."""
from pathlib import Path
import json,shutil,tempfile,time


def elegible(payload):
 result=payload.get('resultado',{});q=result.get('calidad',{});p=payload.get('preprocesamiento',{})
 return (result.get('reconstruccion_medida',{}).get('aplicado') is True and not p.get('reparado') and
         80<=int(q.get('caras_step',0))<=1500 and q.get('tipos_caras',{}).get('GeomAbs_BSplineSurface',0)>=2)


def intentar(source,destination,payload,validar,log):
 if not elegible(payload):return None
 from perfeccion_calidad import ejecutar_subproceso,sha,NUCLEO,EntradaCambiada
 from preprocesador_stl import cargar_exacto
 from prueba_cad import desde_trabajador
 from avance_conversion import avance
 source,destination=map(Path,(source,destination));original=cargar_exacto(source)
 if len(original.faces)>30000:return None
 source_hash,base_hash=sha(source),sha(destination)
 if payload['preprocesamiento'].get('original_sha256')!=source_hash:raise EntradaCambiada('La fuente de la reunión ha cambiado')
 def immutable():
  if sha(source)!=source_hash or sha(destination)!=base_hash:raise EntradaCambiada('Cambió una entrada durante la reunión de superficies')
 with tempfile.TemporaryDirectory(prefix='visor_reunion_verificada_',dir=destination.parent) as directory:
  directory=Path(directory);candidate=directory/'candidato.step';report=directory/'informe.json';start=time.monotonic()
  avance(78,'Reuniendo superficies medidas; comprobando contornos y agujeros')
  peak=ejecutar_subproceso(NUCLEO/'reunir_resultado.py',[source,destination,candidate,report],900,log)
  record=json.loads(report.read_text(encoding='utf-8'))
  if (record.get('ok') is not True or record.get('original_sha256')!=source_hash or record.get('base_sha256')!=base_hash or not candidate.is_file() or record.get('step_sha256')!=sha(candidate)):raise ValueError('La reunión no coincide con sus archivos verificados')
  immutable();quality=validar(source,candidate,original,control_avanzado=True,prueba_cad=desde_trabajador(record,candidate));immutable()
  prior=payload['resultado']['calidad']
  limit=prior['desviacion_max_verificada_mm']+1e-6
  projected=False
  if quality['desviacion_max_verificada_mm']>limit:
   if quality['inspeccion_densa']['stl_a_cad']['max_mm']>limit:raise ValueError('La reunión empeora la desviación máxima respecto al STEP anterior; se conserva la conversión validada')
   # Los centroides de teselación son aproximaciones. Exigir su contraste
   # sobre el recorte CAD exacto con un límite MÁS ESTRICTO que el perfil.
   from validacion_densa import inspeccionar_denso
   from calidad_topologica import leer_solido_step_estricto
   comparison=inspeccionar_denso(original,leer_solido_step_estricto(candidate),limite_p95=prior['inspeccion_densa']['limite_p95_mm'],limite_max=limit)
   if not comparison['aceptado']:raise ValueError('La reunión empeora la desviación máxima incluso tras contrastar las muestras con el CAD exacto')
   quality['inspeccion_densa_previa']=quality['inspeccion_densa'];quality['inspeccion_densa']=comparison
   quality['desviacion_max_previa_muestreo_aproximado_mm']=quality['desviacion_max_verificada_mm']
   quality['desviacion_max_verificada_mm']=round(max(comparison['stl_a_cad']['max_mm'],comparison['cad_a_stl']['max_mm']),6)
   projected=True
  quality['comparacion_no_regresion']=dict(aceptado=True,max_anterior_mm=prior['desviacion_max_verificada_mm'],max_actual_mm=quality['desviacion_max_verificada_mm'],margen_numerico_mm=1e-6,contraste_cad_adicional=projected,limites_perfil_modificados=False)
  if quality['caja_error_mm']>prior['caja_error_mm']+1e-6 or quality['volumen_error_pct']>prior['volumen_error_pct']+1e-6:raise ValueError('La reunión empeora la caja o el volumen respecto al STEP anterior')
  if sha(candidate)!=record['step_sha256']:raise EntradaCambiada('El candidato reunido cambió después de validarse')
  proof=dict(aplicado=True,metodo=record['metodo'],antes=record['antes'],despues=record['despues'],original_sha256=source_hash,base_sha256=base_hash,step_sha256=record['step_sha256'],segundos=time.monotonic()-start,ram_pico_mb=peak,grupos=record['grupos'],cilindros_reunidos=record.get('cilindros_reunidos'),topologia_material=record['topologia_material'],mallado_fino=record['mallado_fino'],limites_aceptacion_modificados=False)
  proof['comparacion_no_regresion']=quality['comparacion_no_regresion']
  shutil.copyfile(report,destination.with_suffix('.calidad_nucleo.json'));candidate.replace(destination)
  return quality,proof
