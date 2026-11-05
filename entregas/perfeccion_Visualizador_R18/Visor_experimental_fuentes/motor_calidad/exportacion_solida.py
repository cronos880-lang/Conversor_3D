"""Exportación explícita de un sólido: nunca publicar un shell como STEP sólido.

No cambia superficies, rellena huecos ni relaja tolerancias. Un shell sólo se
solidifica si ya es una frontera cerrada y orientable, conservando sus caras.
La lectura estricta y la validación contra el STL continúan siendo obligatorias.
"""
from pathlib import Path
import hashlib
import cadquery as cq
from OCP.TopoDS import TopoDS_Iterator
from OCP.BRepCheck import BRepCheck_Analyzer,BRepCheck_Shell,BRepCheck_NoError
from OCP.BRep import BRep_Tool
from OCP.STEPControl import STEPControl_Writer,STEPControl_ManifoldSolidBrep
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static

class ExportacionSolidaError(ValueError):
 def __init__(self,message,diagnostico):super().__init__(message);self.diagnostico=diagnostico


def solidificar_sin_descartar(shape):
 from solidificacion_exacta import solidificar
 solids=[];shells=[]
 def visit(item):
  kind=item.ShapeType()
  if kind=='Solid':solids.append(item);return
  if kind=='Shell':shells.append(item);return
  if kind not in ('Compound','CompSolid'):raise ValueError('No se descartan objetos sueltos: '+kind)
  iterator=TopoDS_Iterator(item.wrapped)
  while iterator.More():visit(cq.Shape.cast(iterator.Value()));iterator.Next()
 visit(shape)
 if len(solids)==1 and not shells:result=solids[0];promoted=False
 elif not solids and len(shells)==1:
  if BRepCheck_Shell(shells[0].wrapped).Closed()!=BRepCheck_NoError:raise ValueError('La frontera tiene aristas abiertas')
  result=cq.Shape.cast(solidificar(shells[0].wrapped));promoted=True
 else:raise ValueError('No hay un único sólido o shell; no se eliminan componentes')
 if not BRepCheck_Analyzer(result.wrapped,True,False,True).IsValid():raise ValueError('El sólido previo no pasa CAD exacto')
 if any(BRepCheck_Shell(shell.wrapped).Closed()!=BRepCheck_NoError for shell in result.Shells()):raise ValueError('Un shell del sólido no está cerrado')
 flags=[bool(shell.wrapped.Closed()) for shell in result.Shells()]
 # La comprobación topológica anterior precede siempre a estas banderas.
 # Para una frontera única se reconstruye sólo el envoltorio del sólido,
 # conservando identidad de caras/aristas y todas sus tolerancias.
 rebuilt=len(result.Shells())==1
 if rebuilt:result=cq.Shape.cast(solidificar(result.wrapped))
 for shell in result.Shells():
  if BRepCheck_Shell(shell.wrapped).Closed()!=BRepCheck_NoError:raise ValueError('La orientación no conserva una frontera cerrada')
  shell.wrapped.Closed(True)
 result.wrapped.Closed(True)
 if not BRepCheck_Analyzer(result.wrapped,True,False,True).IsValid():raise ValueError('La normalización topológica no conserva CAD exacto')
 return result,dict(tipo_entrada=shape.ShapeType(),shell_cerrado_solidificado=promoted,solid_reconstruido_desde_frontera=rebuilt,banderas_cierre_antes=flags,caras=len(result.Faces()),aristas=len(result.Edges()),shells=len(result.Shells()))


def exportar(shape,destination):
 from calidad_topologica import leer_solido_step_estricto
 from saneamiento_cad import exigir_coherencia_exacta
 destination=Path(destination);temporary=destination.with_name(destination.name+'.escribiendo.tmp');record={}
 if destination.exists() or temporary.exists():raise ValueError('La salida STEP debe ser nueva')
 try:
  solid,record=solidificar_sin_descartar(shape);exigir_coherencia_exacta(solid)
  edges=[(e.wrapped,BRep_Tool.Tolerance_s(e.wrapped)) for e in solid.Edges()];maximum=max(t for e,t in edges)
  writer=STEPControl_Writer()
  old_int={name:Interface_Static.IVal_s(name) for name in ('write.surfacecurve.mode','write.precision.mode')}
  old_str={name:Interface_Static.CVal_s(name) for name in ('write.step.schema','write.step.unit')}
  try:
   Interface_Static.SetIVal_s('write.surfacecurve.mode',1);Interface_Static.SetIVal_s('write.precision.mode',0)
   Interface_Static.SetCVal_s('write.step.schema','AP214IS');Interface_Static.SetCVal_s('write.step.unit','MM')
   writer.SetTolerance(maximum)
   transfer=writer.Transfer(solid.wrapped,STEPControl_ManifoldSolidBrep)
   record['transferencia']=str(transfer)
   if transfer!=IFSelect_RetDone:raise ValueError('STEP no acepta la transferencia de un sólido manifold')
   status=writer.Write(str(temporary));record['escritura']=str(status)
   if status!=IFSelect_RetDone:raise ValueError('No se pudo escribir el sólido STEP')
  finally:
   for name,value in old_int.items():Interface_Static.SetIVal_s(name,value)
   for name,value in old_str.items():Interface_Static.SetCVal_s(name,value)
  for edge,tolerance in edges:
   if BRep_Tool.Tolerance_s(edge)!=tolerance:raise ValueError('La escritura ha cambiado la tolerancia de una arista')
  from auditoria_step_crudo import verificar_o_corregir_archivo
  record['auditoria_step_crudo']=verificar_o_corregir_archivo(temporary)
  result=leer_solido_step_estricto(temporary);exigir_coherencia_exacta(result)
  if len(result.Faces())!=record['caras'] or len(result.Shells())!=record['shells']:raise ValueError('La escritura no conserva las caras y fronteras del sólido')
  if max(BRep_Tool.Tolerance_s(e.wrapped) for e in result.Edges())>maximum:raise ValueError('La reimportación aumenta la tolerancia de aristas')
  if record['auditoria_step_crudo']['modified']:
   # Only topological flags were edited. Also check the interpreted solid;
   # full validation against the original STL remains mandatory downstream.
   for name,before,after in (('volumen',solid.Volume(),result.Volume()),('area',solid.Area(),result.Area())):
    if abs(before-after)>max(1e-7,abs(before)*1e-10):raise ValueError('La corrección STEP cambia '+name)
   a,b=solid.BoundingBox(),result.BoundingBox()
   if any(abs(getattr(a,k)-getattr(b,k))>1e-7 for k in ('xmin','ymin','zmin','xmax','ymax','zmax')):raise ValueError('La corrección STEP cambia dimensiones')
  record.update(ok=True,modo='STEPControl_ManifoldSolidBrep',solidos_reimportados=len(result.Solids()),caras_reimportadas=len(result.Faces()),tolerancia_max_mm=maximum,step_sha256=hashlib.sha256(temporary.read_bytes()).hexdigest(),requiere_validacion_original=True)
  temporary.replace(destination);return record
 except Exception as exc:
  temporary.unlink(missing_ok=True)
  raise ExportacionSolidaError(str(exc),record) from exc
