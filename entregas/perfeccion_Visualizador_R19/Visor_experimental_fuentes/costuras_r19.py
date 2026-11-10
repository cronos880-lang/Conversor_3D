"""Reconstrucción general de costuras; sólo propone, nunca selecciona.

Los radios, ejes, curvas y presupuestos de calidad proceden del núcleo original.
Cada resultado requiere STEP reimportado, certificado frío y comparación con la
referencia. No contiene reglas por nombre de pieza ni coordenadas nominales.
"""
from pathlib import Path
import sys,json,math,time
import numpy as np,cadquery as cq
from OCP.BRep import BRep_Tool,BRep_Builder
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.ShapeBuild import ShapeBuild_ReShape
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy,BRepBuilderAPI_Sewing,BRepBuilderAPI_MakeSolid
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepLib import BRepLib
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.ShapeFix import ShapeFix_Face
from OCP.TopoDS import TopoDS_Face
ROOT=Path(__file__).resolve().parent
from contratos_r19 import TOLERANCIA_COSTURA_MM
from topologia_r19 import coser_y_solidificar
from exportacion_r19 import exportar
from cilindros_contiguos import mismo_soporte,certificar_recortes
from validacion_local import _distancias_cad
from pcurvas_compartidas import crear_pcurva,_error


def refinar(source,output):
 """Construcción aislada. Aún requiere validación fría y selección original.

 No contiene nombres de piezas, coordenadas nominales ni índices de caras.
 Los cilindros se agrupan por soporte y conectividad; se conservan las curvas
 de borde y se reconstruye su costura con control de dominio y CAD exacto.
 """
 import hashlib
 source=Path(source);R=Path(output)
 if R.exists():raise ValueError('El directorio de resultados debe ser nuevo')
 before=hashlib.sha256(source.read_bytes()).hexdigest()
 R.mkdir(parents=True,exist_ok=False)
 original=cq.importers.importStep(str(source)).val()
 if len(original.Solids())!=1 or not BRepCheck_Analyzer(original.wrapped,True,False,True).IsValid():raise ValueError('Se requiere un único sólido fuente exacto válido')
 if len(original.Faces())>1200:raise ValueError('Fuera del presupuesto de construcción de costuras')
 s=cq.Shape.cast(BRepBuilderAPI_Copy(original.wrapped,True,False).Shape());faces=s.Faces();seen=set();groups=[]
 for i,f in enumerate(faces):
  if i in seen or BRepAdaptor_Surface(f.wrapped).GetType()!=GeomAbs_Cylinder:continue
  compatible={j for j,g in enumerate(faces) if j not in seen and BRepAdaptor_Surface(g.wrapped).GetType()==GeomAbs_Cylinder and mismo_soporte(f,g)}
  while compatible:
   comp={min(compatible)};todo=list(comp)
   while todo:
    a=todo.pop()
    for b in compatible-comp:
     if any(e.wrapped.IsSame(q.wrapped) for e in faces[a].Edges() for q in faces[b].Edges()):comp.add(b);todo.append(b)
   compatible-=comp;seen.update(comp)
   if len(comp)>1:groups.append(sorted(comp))
 removed=set();added=[];contexts=[];records=[]
 for group in groups:
  r=dict(group=group,ok=False)
  try:
   border=[]
   for i in group:
    for edge in faces[i].Edges():
     if sum(any(edge.wrapped.IsSame(q.wrapped) for q in faces[j].Edges()) for j in group)==1:border.append((edge,i))
   wires=cq.Wire.combine([e for e,i in border])
   if len(wires)!=2 or any(not w.IsClosed() for w in wires):raise ValueError('Dominio no anular')
   surface=BRep_Tool.Surface_s(faces[group[0]].wrapped);builder=BRep_Builder();face=TopoDS_Face();builder.MakeFace(face,surface,1e-7)
   for w in wires:builder.Add(face,w.wrapped)
   for e,i in border:
    curve=BRep_Tool.Curve_s(e.wrapped,0.,0.);a,b=BRep_Tool.Range_s(e.wrapped);uv,info=crear_pcurva(curve,a,b,surface)
    if _error(curve,uv,surface,a,b)>5e-8:raise ValueError('Proyección del borde fuera de presupuesto')
    builder.UpdateEdge(e.wrapped,uv,face,BRep_Tool.Tolerance_s(e.wrapped));builder.Range(e.wrapped,face,a,b)
   ctx=ShapeBuild_ReShape();fix=ShapeFix_Face(face);fix.SetContext(ctx);fix.SetPrecision(1e-7);fix.SetMinTolerance(1e-7);fix.SetMaxTolerance(1e-7)
   fix.FixMissingSeamMode=True;fix.FixSmallAreaWireMode=False;fix.RemoveSmallAreaFaceMode=False;fix.Perform();new=fix.Face();c=cq.Face(new)
   if c.normalAt(faces[group[0]].Center()).dot(faces[group[0]].normalAt(faces[group[0]].Center()))<0:new.Reverse();c=cq.Face(new)
   if not BRepCheck_Analyzer(c.wrapped,True,False,True).IsValid():
    trial=R/('cara_periodica_'+str(group[0])+'.step');cq.exporters.export(c,str(trial));c=cq.importers.importStep(str(trial)).val().Faces()[0]
    if not BRepCheck_Analyzer(c.wrapped,True,False,True).IsValid():raise ValueError('Cara no exacta válida tras relectura')
   proof=certificar_recortes(cq.Compound.makeCompound([faces[i] for i in group]),cq.Compound.makeCompound([c]))
   removed.update(group);added.append(c);contexts.append(ctx);r.update(ok=True,proof=proof)
  except Exception as e:r['error']=str(e)
  records.append(r);print(r,flush=True);(R/'construccion.json').write_text(json.dumps(records,indent=2))
 if not added:raise ValueError('Sin costuras reconstruidas')
 final_faces=[]
 for f in [f for i,f in enumerate(faces) if i not in removed]+added:
  sh=f.wrapped
  for ctx in contexts:sh=ctx.Apply(sh)
  final_faces.append(cq.Shape.cast(sh))
 result=coser_y_solidificar(final_faces)
 exportar(result,R/'candidato.step')
 if hashlib.sha256(source.read_bytes()).hexdigest()!=before:raise ValueError('La referencia cambió durante la construcción')
 return R/'candidato.step',records


if __name__=='__main__':
 candidate,records=refinar(*sys.argv[1:])
 print(json.dumps(dict(candidate=str(candidate),groups=sum(r['ok'] for r in records))),flush=True)
