"""Bind a completed isolated validation to exact source, STEP, code and profile.

This certificate only removes repeated measurements of unchanged files within
one invocation. It is not a persistent conversion cache or a replacement for
cold CAD, dense distance, all three fine meshes, or original-material checks.
"""
from pathlib import Path
import hashlib,json,importlib.metadata
REVISION='R15_CONTROL_COMPLETO_INMUTABLE_V1'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def firma_motor(root):
 root=Path(root)
 # Same identity in root caller and kernel worker. Include every shipped Python
 # implementation, but avoid logs and user conversions inside nested folders.
 if root.name=='motor_calidad':root=root.parent
 folders=[root,root/'motor_superficies',root/'motor_original_amigo',root/'motor_calidad',root/'motor_calidad/motor_superficies',root/'motor_calidad/motor_original_amigo']
 files=sorted(p for folder in folders for p in folder.glob('*.py') if not p.name.startswith('test_'))
 h=hashlib.sha256()
 for p in files:h.update(p.relative_to(root).as_posix().encode());h.update(bytes.fromhex(sha(p)))
 return h.hexdigest()

def dependencias():
 return {name:importlib.metadata.version(name) for name in ('cadquery','cadquery-ocp','numpy','trimesh','vtk','libigl','cgal')}

def identidad(source,step,nonce,root):
 from perfiles_precision import obtener_perfil
 return dict(revision=REVISION,source_sha256=sha(source),step_sha256=sha(step),nonce=nonce,
             motor_sha256=firma_motor(root),dependencias=dependencias(),perfil=obtener_perfil())

def verificar(record,source,step,nonce,root):
 from respaldo_conversion import calidad_aprobada
 if record.get('ok') is not True or record.get('certificado')!=identidad(source,step,nonce,root):
  raise ValueError('El control completo no coincide con archivos, petición, perfil o motor')
 q=record['calidad']
 if not calidad_aprobada(dict(ok=True,resultado=dict(calidad=q))):raise ValueError('Falta calidad CAD completa')
 if q.get('perfil_validacion')!=record['certificado']['perfil']:raise ValueError('El perfil no coincide')
 fine=record.get('mallado_fino',{}).get('resoluciones',[])
 if len(fine)!=3 or [r.get('deflexion_mm') for r in fine]!=[.00025,.0005,.001]:raise ValueError('Falta un mallado fino')
 for r in fine:
  if not r.get('cerrado') or not r.get('orientado') or r.get('intersecciones_cgal')!=0:raise ValueError('Frontera fina no aprobada')
  limits=q['limites_validacion'];surface=r['superficie']
  if surface['max_mm']>limits['desviacion_max_observada_mm'] or surface['p95_mm']>limits['p95_superficie_max_mm']:raise ValueError('Fidelidad fina no aprobada')
 material=record.get('material_original',{})
 if material.get('discrepancias')!=0 or material.get('puntos',0)<2900 or material.get('banda_excluida_mm')!=.002:raise ValueError('Falta contraste de material original')
 topology=record.get('topologia_material',{})
 if not isinstance(topology.get('euler_malla'),int) or topology.get('euler_brep')!=topology['euler_malla'] or topology.get('shells')!=1:raise ValueError('Topología no conservada')
 if any(r.get('euler')!=topology['euler_malla'] for r in fine):raise ValueError('Topología fina no conservada')
 return q
