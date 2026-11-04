"""Reunir campos suaves conservando sus contornos exteriores e interiores.

Propuesta geométrica: requiere validación CAD, original, material y tres
mallados antes de sustituir una conversión. No modifica el STL ni las cotas.
"""
from pathlib import Path
import collections,json,sys,time,hashlib
import numpy as np,cadquery as cq
from OCP.BRep import BRep_Tool,BRep_Builder
from OCP.Geom import Geom_BSplineSurface,Geom_Plane
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.GeomFill import GeomFill_BSplineCurves,GeomFill_StretchStyle
from OCP.TopoDS import TopoDS_Face
from OCP.TopAbs import TopAbs_REVERSED
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing,BRepBuilderAPI_MakeSolid
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepLib import BRepLib
from OCP.ShapeFix import ShapeFix_Face


def exacto(shape):return BRepCheck_Analyzer(shape,True,False,True).IsValid()

def _ordenar(wire):
 from recorte_exacto import recortar
 exp=BRepTools_WireExplorer(wire.wrapped);ordered=[];physical=[]
 while exp.More():
  edge=exp.Current();curve=BRep_Tool.Curve_s(edge,0.,0.);a,b=BRep_Tool.Range_s(edge);trim=recortar(curve,a,b)
  if edge.Orientation()==TopAbs_REVERSED:trim.Reverse()
  ordered.append((trim,trim.FirstParameter(),trim.LastParameter()));physical.append((edge,curve,a,b));exp.Next()
 return ordered,physical

def _muestras(ordered,count=9):
 return np.array([curve.Value(float(t)).Coord() for curve,a,b in ordered for t in np.linspace(a,b,count,endpoint=False)])

def exterior_y_huecos(contours):
 """Clasificar anidamiento de contornos; rechazar islas o proyección ambigua."""
 from shapely.geometry import Polygon
 samples=[_muestras(ordered) for ordered,_ in contours];allp=np.vstack(samples);center=allp.mean(0);_,_,axes=np.linalg.svd(allp-center,full_matrices=False);basis=axes[:2].T
 def projector(point):return None,tuple((np.asarray(point)-center)@basis)
 if len(contours)==1:return 0,projector
 polygons=[Polygon((points-center)@basis) for points in samples]
 if any(not p.is_valid or p.area<1e-12 for p in polygons):raise ValueError('Proyección de contornos no simple')
 outer=[i for i,p in enumerate(polygons) if all(i==j or p.contains(q) for j,q in enumerate(polygons))]
 if len(outer)!=1:raise ValueError('No hay un único contorno exterior certificado')
 i=outer[0];holes=[p for j,p in enumerate(polygons) if j!=i]
 if any(a.intersects(b) for j,a in enumerate(holes) for b in holes[j+1:]):raise ValueError('Los contornos interiores se cruzan o contienen islas')
 return i,projector

def comparar_soportes(old,new):
 from reparador_exacto_aislado import medidas_superficie
 import trimesh
 def mesh(items):
  vv=[];ff=[]
  for f in items:
   v,t=f.tessellate(.00025,.04);off=len(vv);vv.extend(x.toTuple() for x in v);ff.extend(tuple(int(i)+off for i in tri) for tri in t)
  return trimesh.Trimesh(np.asarray(vv),np.asarray(ff),process=False)
 r=medidas_superficie(mesh(old),mesh([new]))
 if r['max_mm']>.003:raise ValueError('La reunión abandona el soporte previo: '+str(r['max_mm']))
 return r

def construir_grupo(faces,part,wires):
 from frontera_compuesta import cuatro_lados
 from pcurvas_compartidas import crear_pcurva,_error,_iso_comun
 from carta_altura import reconocer
 from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
 from OCP.gp import gp_Pnt
 contours=[_ordenar(wire) for wire in wires];outer,pca=exterior_y_huecos(contours);ordered,outer_physical=contours[outer];physical=[item for _,items in contours for item in items]
 projectors=[None]
 for i in part:
  chart=reconocer(BRep_Tool.Surface_s(faces[i].wrapped))
  if chart is not None:projectors.append(chart)
 projectors=projectors[:3]+[pca];points=[]
 for i in part:
  v,t=faces[i].tessellate(.0005,.05);v=np.array([p.toTuple() for p in v]);points.extend(v);points.extend(v[np.asarray(t)].mean(axis=1))
 errors=[]
 for j,projector in enumerate(projectors):
  if j and len(ordered)<5:break
  try:
   curves=[c for c,a,b in ordered] if len(ordered) in (3,4) else cuatro_lados(ordered,projector=projector)
   if curves is None:raise ValueError('No hay cuatro lados compuestos')
   surface=GeomFill_BSplineCurves(*curves,GeomFill_StretchStyle).Surface()
   if not all(_iso_comun(c,a,b,surface) is not None for edge,c,a,b in outer_physical):raise ValueError('La superficie no conserva su contorno exterior')
   maximum=max(GeomAPI_ProjectPointOnSurf(gp_Pnt(*map(float,p)),surface).LowerDistance() for p in points)
   if maximum>.003:raise ValueError('El interior abandona el soporte previo: '+str(maximum))
   for ci,(inner_ordered,inner_physical) in enumerate(contours):
    if ci==outer:continue
    for edge,curve,a,b in inner_physical:
     if any(GeomAPI_ProjectPointOnSurf(curve.Value(float(t)),surface).LowerDistance()>5e-8 for t in np.linspace(a,b,17)):
      raise ValueError('Un contorno interior no pertenece a la nueva superficie')
   face=TopoDS_Face();builder=BRep_Builder();builder.MakeFace(face,surface,1e-7)
   for wire in wires:builder.Add(face,wire.wrapped)
   max_uv=0.
   for edge,curve,a,b in physical:
    uv,info=crear_pcurva(curve,a,b,surface);err=_error(curve,uv,surface,a,b);max_uv=max(max_uv,err)
    if err>5e-8:raise ValueError('Desacuerdo de pcurva: '+str(err))
    builder.UpdateEdge(edge,uv,face,BRep_Tool.Tolerance_s(edge));builder.Range(edge,face,a,b)
   fix=ShapeFix_Face(face);fix.SetPrecision(1e-7);fix.SetMaxTolerance(1e-7);fix.FixOrientation();face=fix.Face();built=cq.Face(face)
   if built.normalAt(faces[part[0]].Center()).dot(faces[part[0]].normalAt(faces[part[0]].Center()))<0:face.Reverse();built=cq.Face(face)
   if not exacto(face) or len(built.Wires())!=len(wires):raise ValueError('La cara no conserva los contornos como CAD exacto')
   comparison=comparar_soportes([faces[i] for i in part],built)
   return built,dict(max_soporte_previo_mm=maximum,max_soporte_bidireccional_mm=comparison['max_mm'],max_pcurva_mm=max_uv,contornos=len(wires),huecos=len(wires)-1,carta='tangentes_3D' if projector is None else 'carta_afin' if projector is not pca else 'proyeccion_2D')
  except Exception as exc:errors.append(str(exc))
 raise ValueError('; '.join(dict.fromkeys(errors)))

def proponer(shape,module_dir,angle_degrees=1.):
 sys.path[:0]=[str(module_dir.parent),str(module_dir)];faces=shape.Faces();edge_faces=collections.defaultdict(list);edges={}
 for i,f in enumerate(faces):
  for e in f.Edges():edge_faces[e.hashCode()].append(i);edges[e.hashCode()]=e
 free={i for i,f in enumerate(faces) if isinstance(BRep_Tool.Surface_s(f.wrapped),(Geom_BSplineSurface,Geom_Plane))};adj=collections.defaultdict(set)
 for key,pair in edge_faces.items():
  if len(pair)!=2 or not all(i in free for i in pair):continue
  a,b=pair;edge=edges[key];planes=all(isinstance(BRep_Tool.Surface_s(faces[i].wrapped),Geom_Plane) for i in pair)
  try:
   worst=max(1-abs(faces[a].normalAt(edge.positionAt(t)).dot(faces[b].normalAt(edge.positionAt(t)))) for t in (.2,.5,.8))
   if worst<(1e-12 if planes else 1-np.cos(np.radians(angle_degrees))):adj[a].add(b);adj[b].add(a)
  except Exception:pass
 groups=[]
 while free:
  first=min(free);free.remove(first);stack=[first];part=[]
  while stack:
   i=stack.pop();part.append(i)
   for j in sorted(adj[i]&free):free.remove(j);stack.append(j)
  part.sort()
  if len(part)>1 and any(isinstance(BRep_Tool.Surface_s(faces[i].wrapped),Geom_BSplineSurface) for i in part):groups.append(part)
 removed=set();added=[];records=[]
 def attempt(part):
  info=dict(caras=part,ok=False)
  try:
   border=[e for i in part for e in faces[i].Edges() if sum(j in part for j in edge_faces[e.hashCode()])==1]
   if not 3<=len(border)<=64:raise ValueError('Presupuesto de frontera')
   wires=cq.Wire.combine(border)
   if not wires:raise ValueError('Frontera vacía')
   built,proof=construir_grupo(faces,part,wires);removed.update(part);added.append(built);info.update(ok=True,**proof)
  except Exception as exc:info['error']=str(exc)
  records.append(info);print(info,flush=True);return info['ok']
 for part in groups:
  if attempt(part):continue
  if len(part)>2:
   for i in part:
    if i in removed:continue
    for j in sorted(adj[i]&set(part)):
     if j<=i or j in removed:continue
     if attempt([i,j]):break
 if not removed:raise ValueError('Ninguna reunión válida')
 sewing=BRepBuilderAPI_Sewing(1e-7,True,True,True,False)
 for i,f in enumerate(faces):
  if i not in removed:sewing.Add(f.wrapped)
 for face in added:sewing.Add(face.wrapped)
 sewing.Perform();shells=cq.Shape.cast(sewing.SewedShape()).Shells()
 if len(shells)!=1:raise ValueError('La propuesta no conserva un único shell')
 solid=BRepBuilderAPI_MakeSolid(shells[0].wrapped).Solid();BRepLib.OrientClosedSolid_s(solid)
 if not exacto(solid):raise ValueError('La reunión no conserva CAD exacto')
 return cq.Solid(solid),records

if __name__=='__main__':
 source,destination,report,module_dir=map(Path,sys.argv[1:5]);angle=float(sys.argv[5]) if len(sys.argv)>5 else 1.
 if destination.exists() or report.exists() or len({p.resolve() for p in (source,destination,report)})!=3:raise SystemExit('Las salidas deben ser nuevas y distintas')
 before=hashlib.sha256(source.read_bytes()).hexdigest();start=time.monotonic();record=dict(ok=False)
 try:
  result,records=proponer(cq.importers.importStep(str(source)).val(),module_dir,angle);cq.exporters.export(result,str(destination));record.update(ok=True,caras=len(result.Faces()),grupos=records,base_sha256=before,step_sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
 except Exception as exc:
  import traceback;traceback.print_exc();record['error']=str(exc);destination.unlink(missing_ok=True)
 assert before==hashlib.sha256(source.read_bytes()).hexdigest();record['segundos']=time.monotonic()-start;report.write_text(json.dumps(record,indent=2));print(record,flush=True)
