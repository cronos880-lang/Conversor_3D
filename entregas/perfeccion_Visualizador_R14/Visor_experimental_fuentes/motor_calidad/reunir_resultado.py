"""Mejorar representaciones fragmentadas después de una conversión aprobada."""
from pathlib import Path
import hashlib,json,sys,time,tempfile,traceback
import cadquery as cq
from collections import Counter
from OCP.BRepAdaptor import BRepAdaptor_Surface

def inventario_completo(shape):
 from reconstruccion_curvas import inventario
 result=inventario(shape);result['tipos_caras']=dict(Counter(str(BRepAdaptor_Surface(f.wrapped).GetType()).split('.')[-1] for f in shape.Faces()));return result



def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def ejecutar(source,base,destination,report):
 source,base,destination,report=map(Path,(source,base,destination,report));paths=(source,base,destination,report)
 if len({p.resolve() for p in paths})!=4 or destination.exists() or report.exists():raise ValueError('Entradas distintas y salidas nuevas obligatorias')
 before=sha(source),sha(base);record=dict(ok=False);start=time.monotonic()
 try:
  sys.path.insert(0,str(Path(__file__).resolve().parent/'motor_superficies'))
  from preprocesador_stl import cargar_exacto
  from calidad_topologica import leer_solido_step_estricto
  from topologia_vertices import inspeccionar_vertices
  from reparador_exacto_aislado import ControlExacto
  from meshfit_detect import detect
  from reconstruccion_curvas import cilindros_respaldados,validar_cilindros_y_frontera,inventario
  from reunion_con_huecos import proponer as reunir,comparar_soportes
  from planos_certificados import convertir
  from cilindros_contiguos import certificar_recortes,cilindros
  original=cargar_exacto(source)
  if len(original.faces)>30000 or not original.is_watertight or not original.is_winding_consistent or inspeccionar_vertices(original)['vertices_no_manifold'] or len(original.split(only_watertight=False))!=1:raise ValueError('La reunión requiere una fuente cerrada, orientada y sin contactos ambiguos')
  with tempfile.TemporaryDirectory(prefix='visor_fuente_reunion_') as directory:
   if ControlExacto(original,Path(directory)/'fuente.off').pares():raise ValueError('La fuente tiene intersecciones')
  previous=leer_solido_step_estricto(base);old=inventario_completo(previous)
  if old['caras']<80 or old['caras']>1500 or old['tipos_caras'].get('GeomAbs_BSplineSurface',0)<2:raise ValueError('Se conserva el resultado analítico o compacto anterior')
  result,record['grupos']=reunir(previous,Path(__file__).resolve().parent/'motor_superficies')
  try:result,record['planos_certificados']=convertir(result,Path(__file__).resolve().parent/'motor_superficies')
  except ValueError as exc:record['planos_omitidos']=str(exc)
  record['cilindros_conservados']=dict(caras=len(cilindros(previous)),radios_y_dominios_sin_union=True)
  # Ampliar candidatos suaves manteniendo la MISMA cota de soporte de 0,003 mm.
  # Si no existe una segunda reunión válida, se conserva la primera propuesta.
  try:
   expanded,groups=reunir(result,Path(__file__).resolve().parent/'motor_superficies',angle_degrees=5.)
   support=comparar_soportes(previous.Faces(),expanded)
   record['segunda_reunion']=dict(grupos=groups,soporte_global_previo=support)
   result=expanded
  except ValueError as exc:record['segunda_reunion_omitida']=str(exc)
  new=inventario_completo(result)
  if new['caras']>=old['caras'] or new['tipos_caras'].get('GeomAbs_BSplineSurface',0)>.75*old['tipos_caras']['GeomAbs_BSplineSurface']:raise ValueError('No reduce al menos un 25% las divisiones B-spline')
  from exportacion_solida import exportar
  record['exportacion_solida']=exportar(result,destination)
  detected,working=detect(str(source),angle_tol_deg=32.,rms_tol_rel=.01,flat_tol_deg=8.,scan_mode=False,mesh_input=original.copy());required=cilindros_respaldados(detected,working)
  shape,cylinders,quality,topology,boundary=validar_cilindros_y_frontera(source,destination,original,required)
  record['soporte_global_previo']=comparar_soportes(previous.Faces(),shape)
  if cilindros(previous):record['dominios_cilindricos_reimportados']=certificar_recortes(previous,shape)
  from prueba_cad import REVISION
  if before!=(sha(source),sha(base)):raise ValueError('Cambió una entrada durante la mejora')
  record.update(ok=True,original_sha256=before[0],base_sha256=before[1],step_sha256=sha(destination),antes=old,despues=inventario_completo(shape),calidad=quality,topologia_material=topology,mallado_fino=boundary,cilindros_respaldados=cylinders,revision_cad=REVISION,brep_exacto=True,limites_aceptacion_modificados=False,metodo='reunion_de_campos_con_frontera_preservada')
 except Exception as exc:record['error']=str(exc);destination.unlink(missing_ok=True);traceback.print_exc()
 if before!=(sha(source),sha(base)):raise RuntimeError('Una entrada ha cambiado')
 record['segundos']=time.monotonic()-start;report.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
 return 0 if record['ok'] else 2

if __name__=='__main__':raise SystemExit(ejecutar(*sys.argv[1:]))
