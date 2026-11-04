"""Anclar perfiles medidos a encuentros nativos; no cambia sus tolerancias CAD."""
import itertools
import numpy as np
from scipy.interpolate import BSpline
from scipy.optimize import least_squares
from OCP.Geom import Geom_SurfaceOfLinearExtrusion,Geom_Plane
from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
from OCP.gp import gp_Pnt

def anclar(mesh,chains,surfaces,primary,projectors,max_move):
 import meshfit_brep as base
 from geometria_medida import signed_projection,circle_supports
 incident={}
 for ch in chains.values():
  for vi in (ch['verts'][0],ch['verts'][0] if ch['closed'] else ch['verts'][-1]):incident.setdefault(int(vi),set()).update(ch['pair'])
 # Una esquina compartida pertenece al grafo de la fuente, no a cada
 # perfil por separado. Fijar una referencia común antes de ajustar curvas.
 shared={};axes={};canonical={}
 for v,regions in incident.items():
  rs={r for r in regions if r in primary and isinstance(surfaces[r],Geom_SurfaceOfLinearExtrusion)}
  if len(rs)<2:continue
  directions=[np.array(surfaces[r].Direction().Coord()) for r in rs];a=directions[0]
  if any(np.linalg.norm(np.cross(a,b))>1e-8 for b in directions[1:]):continue
  shared[v]=rs;axes[v]=a
 parent={v:v for v in shared}
 def root(v):
  while parent[v]!=v:parent[v]=parent[parent[v]];v=parent[v]
  return v
 keys=list(shared)
 for i,v in enumerate(keys):
  for w in keys[i+1:]:
   if len(shared[v]&shared[w])<2:continue
   a=axes[v];difference=mesh.vertices[v]-mesh.vertices[w];difference-=a*(difference@a)
   if np.linalg.norm(difference)<1e-8:parent[root(w)]=root(v)
 clusters={}
 for v in keys:clusters.setdefault(root(v),[]).append(v)
 for cluster in clusters.values():
  a=axes[cluster[0]];P=mesh.vertices[cluster];Q=np.mean(P-np.outer(P@a,a),axis=0)
  for v in cluster:canonical[v]=Q+a*(mesh.vertices[v]@a)
 canonical.update(getattr(mesh,"esquinas_canonicas_medidas",{}))
 targets={};curves={};owners={};contexts={};mesh.propuestas_esquinas_medidas={};mesh.parametros_esquinas_medidas={}
 for vertex,regions in incident.items():
  sweeps=[r for r in regions if r in primary and isinstance(surfaces[r],Geom_SurfaceOfLinearExtrusion)]
  if not sweeps:continue
  native=[r for r in regions if r in primary and r not in sweeps];p=np.asarray(canonical.get(vertex,mesh.vertices[vertex]));circles=[]
  for first,second in itertools.combinations(native,2):
   choices=circle_supports(surfaces[first],surfaces[second])
   if choices:
    def score(c):
     q,a,r=c;return abs((p-q)@a)+abs(np.linalg.norm(np.cross(p-q,a))-r)
    circles.append(min(choices,key=score))
  def residual(x):
   result=[]
   for region in native:result.extend(signed_projection(projectors[region],np.asarray([x]))[0])
   for q,a,r in circles:result.extend([(x-q)@a,np.linalg.norm(np.cross(x-q,a))-r])
   return np.asarray(result)
  if native:
   fit=least_squares(lambda x:np.r_[residual(x),(x-p)*1e-6],p,xtol=1e-13,ftol=1e-13,gtol=1e-13,max_nfev=160);point=fit.x
   if max(abs(residual(point)),default=0)>2e-7 or np.linalg.norm(point-p)>max_move:raise ValueError('Las superficies nativas no fijan una esquina compatible '+str({'vertice':vertex,'regiones':[(r,type(surfaces[r]).__name__) for r in native],'residual':max(abs(residual(point)),default=0),'movimiento':np.linalg.norm(point-p)}))
  else:point=p
  contexts[vertex]=(native,circles,p.copy())
  for region in sweeps:
   surface=surfaces[region];key=id(surface);curve=surface.BasisCurve();axis=np.array(surface.Direction().Coord())
   normal_rows=[signed_projection(projectors[r],np.asarray([point]))[1][0] for r in native]
   for q,a,r in circles:normal_rows.extend([a,np.cross(np.cross(point-q,a),a)*-1/max(np.linalg.norm(np.cross(point-q,a)),1e-30)])
   if not normal_rows and len(sweeps)<2:continue
   matrix=np.asarray(normal_rows).reshape(-1,3);matrix-=np.outer(matrix@axis,axis);sv=np.linalg.svd(matrix,compute_uv=False)
   one_source_plane=(len(native)==1 and isinstance(surfaces[native[0]],Geom_Plane))
   if len(native)<2 and not circles and len(sweeps)<2 and not one_source_plane:continue
   origin=np.array(curve.Value(curve.FirstParameter()).Coord());target=point-axis*((point-origin)@axis)
   from proyeccion_barridos import uv_exacta
   parameter=float(uv_exacta(surface,point[None,:])[0,0])
   knots_near=[curve.Knot(k) for k in range(1,curve.NbKnots()+1) if curve.Value(curve.Knot(k)).Distance(curve.Value(float(parameter)))<1e-9]
   if knots_near:parameter=min(knots_near,key=lambda k:abs(k-parameter))
   mesh.propuestas_esquinas_medidas[vertex]=point.copy();targets.setdefault(key,[]).append((float(parameter),target,vertex));curves[key]=curve;owners[key]=surface
 # Un único objetivo 3D por vértice para TODOS sus perfiles. Ningún ajuste
 # posterior de una curva puede sobrescribir el punto ya usado por otra.
 fixed={v:np.asarray(p).copy() for v,p in mesh.propuestas_esquinas_medidas.items()}
 records=[]
 for key,rows in targets.items():
  curve=curves[key];axis=np.array(owners[key].Direction().Coord());origin=np.array(curve.Value(curve.FirstParameter()).Coord())
  by_vertex={}
  for t,target,v in rows:
   point=fixed[v];wanted=point-axis*((point-origin)@axis);by_vertex[v]=(float(t),wanted,int(v))
  rows=sorted(by_vertex.values(),key=lambda row:row[0]);all_rows=list(rows);unique=[]
  for row in rows:
   if unique and abs(row[0]-unique[-1][0])<=1e-13*max(1.,abs(curve.LastParameter()-curve.FirstParameter())):
    if np.linalg.norm(row[1]-unique[-1][1])>5e-8:raise ValueError('Dos objetivos distintos colapsan en un mismo parámetro del perfil; no se fusionan')
    continue
   unique.append(row)
  rows=unique;parameters=np.array([t for t,p,v in rows]);wanted=np.array([p for t,p,v in rows])
  new=curve.Copy()
  if new.IsRational() or new.Degree()!=3:raise ValueError('Perfil no cúbico para anclaje acotado')
  # Multiplicidad dos: el ajuste sigue siendo C1 en cada nudo nuevo.
  for t in parameters:
   if new.FirstParameter()+1e-12<t<new.LastParameter()-1e-12:new.InsertKnot(float(t),2,1e-14,False)
  knots=[]
  for i in range(1,new.NbKnots()+1):knots.extend([new.Knot(i)]*new.Multiplicity(i))
  basis=BSpline.design_matrix(parameters,np.array(knots),3).toarray();current=np.array([new.Value(float(t)).Coord() for t in parameters]);rhs=wanted-current
  edits=np.linalg.lstsq(basis,rhs,rcond=1e-13)[0]
  maximum=float(np.linalg.norm(edits,axis=1).max())
  if maximum>.003:
   from anclaje_acotado import resolver as resolver_cota
   try:edits=resolver_cota(basis,rhs,axis)
   except ValueError as exc:
    from hipotesis_local import HipotesisIncompatible
    worst=int(np.linalg.norm(rhs,axis=1).argmax());raise HipotesisIncompatible([r for r,s in surfaces.items() if s is owners[key]],rows[worst][2],str(exc)) from exc
   maximum=float(np.linalg.norm(edits,axis=1).max());print('ANCLAJE DE POLOS CON COTA EXPLICITA',maximum,flush=True)
  if np.linalg.norm(basis@edits-rhs,axis=1).max()>5e-8:raise ValueError('Los objetivos compartidos no se pueden interpolar con el perfil')
  for index,change in enumerate(edits):new.SetPole(index+1,gp_Pnt(*map(float,np.array(new.Pole(index+1).Coord())+change)))
  verified=max(new.Value(float(t)).Distance(gp_Pnt(*map(float,p))) for t,p in zip(parameters,wanted))
  for t,target,v in all_rows:
   point=np.array(new.Value(float(t)).Coord());point+=axis*float((fixed[v]-point)@axis)
   verified=max(verified,float(np.linalg.norm(point-fixed[v])))
  if verified>5e-8:raise ValueError('No se conserva el encuentro conjunto de todos los vértices')
  replacement=Geom_SurfaceOfLinearExtrusion(new,owners[key].Direction());labels=[r for r,s in surfaces.items() if s is owners[key]]
  for region in labels:surfaces[region]=replacement
  for t,target,v in all_rows:
   point=np.array(new.Value(float(t)).Coord());along=float((fixed[v]-point)@axis)
   for region in labels:mesh.parametros_esquinas_medidas.setdefault(v,{})[region]=(float(t),along)
  records.append(dict(regiones=labels,anclajes=len(rows),movimiento_max_polos_mm=maximum,residual_mm=verified,objetivo_compartido=True,nudos_nuevos_C1=True));print('ANCLAJE CONJUNTO',records[-1],flush=True)
 mesh.propuestas_esquinas_medidas=fixed
 from curvas_barridas import registrar_generatriz_fuente
 for v,parameters in mesh.parametros_esquinas_medidas.items():
  rs=sorted(parameters)
  for j,first in enumerate(rs):
   for second in rs[j+1:]:
    registrar_generatriz_fuente(surfaces[first],surfaces[second],parameters[first][0],parameters[second][0])
 # Revisar los objetivos de cada curva contra el mismo punto 3D compartido.
 # Cada registro se comprobó por evaluación real de su curva, sin tolerancias añadidas.
 return records
