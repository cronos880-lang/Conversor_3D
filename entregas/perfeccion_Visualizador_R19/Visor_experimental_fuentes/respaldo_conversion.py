"""Respaldo atómico de una conversión ya validada, antes de mejoras opcionales.

Nunca rescata una malla todavía no convertida ni permite convertir una
cancelación en éxito. El servidor decide si corresponde recuperar el respaldo.
"""
from pathlib import Path
import copy,hashlib,json,os

REVISION='BASE_R12_VALIDADA_SHA256_V1'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rutas(destination,etapa=None):
 destination=Path(destination)
 if etapa=='r16':return destination.with_name(destination.name+'.r16_base_validada.step'),destination.with_name(destination.name+'.r16_base_validada.json')
 if etapa=='r14':return destination.with_name(destination.name+'.r14_base_validada.step'),destination.with_name(destination.name+'.r14_base_validada.json')
 if etapa is not None:raise ValueError('Etapa de respaldo no reconocida')
 return destination.with_name(destination.name+'.base_validada.step'),destination.with_name(destination.name+'.base_validada.json')

def calidad_aprobada(payload):
 if payload.get('ok') is not True:return False
 quality=payload.get('resultado',{}).get('calidad',{})
 integrity=quality.get('integridad_cad',{})
 return (integrity.get('brep_valido') is True and integrity.get('brep_exacto') is True and
         integrity.get('solidos')==1 and quality.get('autointerferencias_occ') is False and
         quality.get('sin_objetos_sueltos_en_step') is True and quality.get('inspeccion_densa',{}).get('aceptado') is True)

def guardar(source,destination,payload,*,etapa=None):
 source,destination=map(Path,(source,destination));step,report=rutas(destination,etapa)
 if len({p.resolve() for p in (source,destination,step,report)})!=4:raise ValueError('El respaldo debe ser distinto de las entradas')
 if not calidad_aprobada(payload):raise ValueError('No hay una conversión aprobada para respaldar')
 source_hash=sha(source);step_hash=sha(destination)
 if payload.get('preprocesamiento',{}).get('original_sha256')!=source_hash:raise ValueError('El respaldo no está vinculado al STL original')
 profile=payload['resultado']['calidad'].get('perfil_validacion',{}).get('id')
 if profile not in ('precision','impresion'):raise ValueError('El perfil validado no está identificado')
 body=destination.read_bytes()
 if hashlib.sha256(body).hexdigest()!=step_hash:raise ValueError('El STEP cambió antes del respaldo')
 temporary=step.with_name(step.name+'.tmp')
 if step.exists() or report.exists():raise ValueError('Ya existe un respaldo; no se sobrescribe')
 with temporary.open('xb') as stream:stream.write(body)
 if sha(temporary)!=step_hash:temporary.unlink();raise ValueError('No se conserva la copia del STEP')
 temporary.replace(step)
 record=dict(revision=REVISION,original_sha256=source_hash,step_sha256=step_hash,perfil=profile,payload=copy.deepcopy(payload))
 temporary=report.with_name(report.name+'.tmp')
 with temporary.open('x',encoding='utf-8') as stream:stream.write(json.dumps(record,ensure_ascii=False))
 if sha(source)!=source_hash or sha(destination)!=step_hash:temporary.unlink();raise ValueError('Una entrada cambió durante el respaldo')
 temporary.replace(report)
 return record

def _recuperar_etapa(source,destination,*,perfil,motivo,cancelado=False,etapa=None):
 if cancelado:return None
 source,destination=map(Path,(source,destination));step,report=rutas(destination,etapa)
 try:
  if not step.is_file() or not report.is_file():return None
  record=json.loads(report.read_text(encoding='utf-8'));payload=record['payload']
  if (record.get('revision')!=REVISION or record.get('perfil')!=perfil or not calidad_aprobada(payload) or
      record.get('original_sha256')!=sha(source) or record.get('step_sha256')!=sha(step) or
      payload.get('preprocesamiento',{}).get('original_sha256')!=record['original_sha256'] or
      payload['resultado']['calidad'].get('perfil_validacion',{}).get('id')!=perfil):return None
  body=step.read_bytes()
  if hashlib.sha256(body).hexdigest()!=record['step_sha256']:return None
  temporary=destination.with_name(destination.name+'.recuperando.tmp')
  with temporary.open('xb') as stream:stream.write(body)
  if sha(source)!=record['original_sha256'] or sha(temporary)!=record['step_sha256']:
   temporary.unlink();return None
  temporary.replace(destination)
  recovered=copy.deepcopy(payload)
  recovered['mejora_superficies']=dict(aplicado=False,estado='conservada_conversion_validada',motivo=str(motivo),conservado_resultado_R11=True,step_sha256=record['step_sha256'],original_sha256=record['original_sha256'])
  recovered['recuperacion_respaldo']=dict(aplicado=True,revision=REVISION,step_sha256=record['step_sha256'],perfil=perfil)
  return recovered
 except (OSError,ValueError,KeyError,TypeError):return None

def recuperar(source,destination,*,perfil,motivo,cancelado=False):
 if cancelado:return None
 for etapa in ('r16','r14',None):
  result=_recuperar_etapa(source,destination,perfil=perfil,motivo=motivo,etapa=etapa)
  if result is not None:return result
 return None
