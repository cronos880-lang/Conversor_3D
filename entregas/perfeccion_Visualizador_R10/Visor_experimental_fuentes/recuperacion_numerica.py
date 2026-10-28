"""Recuperación CAD de una frontera regularizada, con triangulación conservada.

Las superficies curvas se conservan facetadas. Esta ruta no reconstruye un
historial paramétrico ni amplía límites de aceptación. El núcleo analítico
existente conserva prioridad; la recuperación sigue a sus intentos fallidos.
"""
from __future__ import annotations
import hashlib,json,os,subprocess,sys,tempfile,time,traceback
from pathlib import Path

MAX_FACES=25_000

def _sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def _rutas_seguras(source,prepared,destination,report):
 reads=[source,prepared];writes=[destination,report]
 if len({p.resolve() for p in writes})!=len(writes):return False
 for a in writes:
  for b in reads:
   if a.resolve()==b.resolve() or (a.exists() and b.exists() and a.samefile(b)):return False
 if all(p.exists() for p in writes) and writes[0].samefile(writes[1]):return False
 return True

def _chi(shape):
 from validacion_reconstruccion import euler_brep
 return euler_brep(shape)

def _nodos_singulares(shape,mesh,*,todos=False):
 import numpy as np
 from scipy.spatial import cKDTree
 from collections import Counter
 tree=cKDTree(mesh.vertices);keep=set()
 for face in shape.Faces():
  if len(face.Wires())<2:continue
  loops=[]
  for wire in face.Wires():
   points=np.asarray([v.Center().toTuple() for v in wire.Vertices()]);dist,idx=tree.query(points)
   if np.max(dist)>1e-8:raise ValueError('No se puede preservar la correspondencia de un contorno CAD')
   loops.append(set(map(int,idx)))
  counts=Counter(v for loop in loops for v in loop)
  keep.update(v for v,n in counts.items() if todos or n>1)
 return keep

def reconstruir(source,prepared,destination,report,*,segundos=900):
 source,prepared,destination,report=map(Path,[source,prepared,destination,report])
 if not _rutas_seguras(source,prepared,destination,report):
  print('La entrada y sus archivos de salida deben ser distintos.',flush=True);return 2
 start=time.monotonic();record={'ok':False,'tipo_cad':'recuperacion_facetada','version_recuperacion':1,'aceptacion_sin_relajar':True}
 try:
  import numpy as np,trimesh,cadquery as cq
  from OCP.ShapeFix import ShapeFix_Shape
  from preprocesador_stl import cargar_exacto
  from invariantes_material import InvariantesMaterial
  from holgura_geometrica import acoplar
  from brep_poliedrico_indices import construir
  from validacion_reconstruccion import certificar_malla,certificar_topologia_step
  from reparador_exacto_aislado import ControlExacto,validar_material
  from motor_v2 import _calidad
  from avance_conversion import avance
  for input_path in (source,prepared):
   if not input_path.is_file() or input_path.stat().st_size>30*1024**2:raise ValueError('No se encuentra la entrada o supera 30 MB')
  hashes=[_sha(source),_sha(prepared)];reference=cargar_exacto(prepared)
  if len(reference.faces)>250_000:raise ValueError('La entrada supera el límite de 250.000 caras')
  if not reference.is_watertight or not reference.is_winding_consistent:
   from normalizacion_referencia import normalizar_cierre
   reference,record['normalizacion_preparado']=normalizar_cierre(reference)
  original=cargar_exacto(source);original_bruto=original;normalizacion=None
  if not original.is_watertight or not original.is_winding_consistent:
   # Reproducir el certificado a partir del ORIGINAL dentro del trabajador.
   # Un archivo preparado cerrado, por sí solo, nunca autoriza tapar un hueco.
   from normalizacion_referencia import normalizar_cierre
   original,normalizacion=normalizar_cierre(original)
   record['normalizacion_referencia_material']=normalizacion
  destination.parent.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(prefix='visor_numerico_',dir=destination.parent) as tmp:
   tmp=Path(tmp)
   if len(reference.faces)>MAX_FACES:
    from motor_v2 import _preparar_trabajo
    failures=[];reduced=None
    for target_faces in (20_000,25_000):
     try:
      preparation=_preparar_trabajo(prepared,tmp/'trabajo.stl',reference,sys.stdout,work_face_limit=target_faces)
      proposal=cargar_exacto(tmp/'trabajo.stl')
      if proposal.euler_number!=reference.euler_number:raise ValueError('La preparación altera túneles o cavidades')
      if len(proposal.faces)>MAX_FACES:raise ValueError('La preparación excede el presupuesto de caras')
      reduced=proposal;record['preparacion_verificada']=preparation;break
     except Exception as exc:failures.append(str(exc))
    if reduced is None:raise ValueError('No existe una reducción segura para la recuperación: '+'; '.join(failures))
    reference=reduced
   try:needs_repair=bool(ControlExacto(reference,tmp/'entrada.off').pares())
   except ValueError:needs_repair=True
   if needs_repair:
    avance(76,'Resolviendo intersecciones de la frontera cerrada')
    from reparador_exacto_aislado import ejecutar
    fixed=tmp/'frontera.stl';repair_report=tmp/'frontera.json'
    repair_input=prepared
    if record.get('preparacion_verificada'):
     repair_input=tmp/'trabajo_exacto.stl';repair_input.write_text(trimesh.exchange.stl.export_stl_ascii(reference),encoding='ascii')
    code=ejecutar(repair_input,fixed,repair_report)
    repair=json.loads(repair_report.read_text(encoding='utf-8'));record['reparacion_previa']=repair
    if code!=0 or not repair.get('reparado'):raise ValueError(repair.get('error','La frontera original no se puede regularizar conservando geometría'))
    reference=cargar_exacto(fixed)
    if len(reference.faces)>MAX_FACES:raise ValueError('La frontera reparada supera el límite de 25.000 caras')
   invariants=InvariantesMaterial(reference)
   avance(79,'Preparando la recuperación geométrica del STEP')
   mesh,optimization=acoplar(reference,tmp/'control.off',deadline=start+segundos,max_vueltas=20,objetivo_altura=2e-6,validar_extra=invariants.comprobar)
   record['estabilizacion']=optimization;record['geometria_local']=certificar_malla(reference,mesh)
   if not invariants.comprobar(mesh.vertices) or ControlExacto(mesh,tmp/'control_final.off').pares():raise ValueError('No se conservan el material o la validez exacta')
   record['material_original']=validar_material(original,mesh,[])
   candidate=tmp/'candidato.step';keep=set();failures=[];approved=None
   for attempt in range(4):
    avance(92,'Construyendo el STEP de recuperación y conservando sus contornos')
    use_unify=attempt<3
    if not use_unify and len(mesh.faces)>=len(original.faces):continue
    shape=construir(mesh,unificar=use_unify,proteger_micro=True,conservar_nodos=keep);fix=ShapeFix_Shape(shape.wrapped);fix.SetPrecision(1e-8);fix.SetMinTolerance(1e-10);fix.SetMaxTolerance(1e-7);fix.Perform();shape=cq.Shape.cast(fix.Shape());shape.exportStep(str(candidate));back=cq.importers.importStep(str(candidate)).val()
    if _chi(back)!=mesh.euler_number or len(back.Shells())!=len(invariants.groups):
     more=_nodos_singulares(back,mesh,todos=attempt>0)-keep
     if not more:
      failures.append({'intento':attempt,'motivo':'No se conserva la topología; se prueba otra representación'});continue
     keep.update(more);failures.append({'intento':attempt,'motivo':'Contornos con vértices compartidos requieren protección','nodos_protegidos':len(keep)});continue
    topology=certificar_topologia_step(back,mesh,invariants)
    quality=_calidad(source,candidate,original,control_avanzado=True)
    if normalizacion is not None:
     normalized_quality=quality
     quality=_calidad(source,candidate,original_bruto,control_avanzado=True)
     quality['control_referencia_material']=normalized_quality
    quality['recuperacion_numerica']={'original_sha256':hashes[0],'preparado_sha256':hashes[1],'geometria_local':record['geometria_local'],'topologia':topology,'material_original':record['material_original'],'reparacion_previa':record.get('reparacion_previa'),'preparacion_verificada':record.get('preparacion_verificada')}
    approved=quality;record['topologia']=topology;break
   if approved is None:raise ValueError('No se ha obtenido una consolidación topológica segura')
   local=None
   if (len(original.faces)<=12000 and 150<=approved['caras_step']<=3500
       and os.environ.get('VISOR_CILINDROS_LOCALES','1')=='1' and start+900-time.monotonic()>=180):
    try:
     from recuperacion_cilindros import intentar
     approved,local=intentar(source,candidate,original,sys.stdout,timeout=min(360,start+900-time.monotonic()-60))
     record['cilindros_locales']=local
     record['geometria_local_aplica_a_base_facetada']=True
    except Exception as exc:
     record['cilindros_locales']={'aplicado':False,'error':str(exc)}
     print('[Cilindros locales] Se conserva el STEP facetado ya validado:',exc,flush=True)
   if hashes!=[_sha(source),_sha(prepared)]:raise ValueError('La referencia de entrada ha cambiado durante la conversión')
   candidate.replace(destination)
   result={'caras_stl':int(len(original.faces)),'modo':'recuperacion_facetada','estrategia':'recuperacion_numerica_verificada','motor':'Recuperación B-Rep facetada verificada; las curvas conservan las facetas del STL','calidad':approved,'diagnostico':{'consolidaciones_rechazadas':failures,'nodos_protegidos':len(keep)},'reconstruccion_parametrica':False}
   if local is not None:
    result.update(modo='cilindros_locales_y_facetas',estrategia='cilindros_locales_verificados',
                  motor='Cilindros reconstruidos y otras zonas facetadas, con geometría y CAD verificados',
                  cilindros_locales=local)
    record['tipo_cad']='cilindros_locales_y_facetas'
   record.update(ok=True,resultado=result,original_sha256=hashes[0],preparado_sha256=hashes[1],step_sha256=_sha(destination))
 except Exception as exc:
  record.update(error=str(exc),tipo_error='recuperacion_numerica_rechazada');traceback.print_exc()
 finally:
  record['segundos']=round(time.monotonic()-start,3);report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
 print(json.dumps({'ok':record['ok'],'error':record.get('error'),'segundos':record['segundos']},ensure_ascii=True),flush=True)
 return 0 if record['ok'] else 2

def ejecutar_aislado(source,prepared,destination,log):
 from control_recursos import comunicar_vigilado,LimiteRecursos
 import psutil
 report=destination.with_suffix('.recuperacion.json')
 def stop(proc):
  try:
   parent=psutil.Process(proc.pid)
   for child in parent.children(recursive=True):
    try:child.kill()
    except psutil.NoSuchProcess:pass
   parent.kill()
  except psutil.NoSuchProcess:pass
 with subprocess.Popen([sys.executable,str(Path(__file__).resolve()),str(source),str(prepared),str(destination),str(report)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONUNBUFFERED':'1','PYTHONIOENCODING':'utf-8'}) as proc:
  try:out,_,peak=comunicar_vigilado(proc,1000,stop)
  except LimiteRecursos as exc:
   if exc.stdout:print(exc.stdout,file=log,flush=True)
   raise
 if out:print(out,file=log,flush=True)
 if proc.returncode!=0 or not report.exists():raise ValueError('La recuperación numérica no ha producido un STEP aprobado')
 data=json.loads(report.read_text(encoding='utf-8'))
 if not data.get('ok') or not destination.is_file():raise ValueError(data.get('error','Recuperación numérica rechazada'))
 if data.get('step_sha256')!=_sha(destination) or data.get('original_sha256')!=_sha(Path(source)) or data.get('preparado_sha256')!=_sha(Path(prepared)):raise ValueError('El resultado no coincide con la referencia verificada')
 data['resultado']['ram_numerica_pico_mb']=peak
 return data['resultado']

if __name__=='__main__':
 if len(sys.argv)!=5:raise SystemExit('Uso: recuperacion_numerica.py original.stl preparado.stl salida.step informe.json')
 raise SystemExit(reconstruir(*map(Path,sys.argv[1:])))
