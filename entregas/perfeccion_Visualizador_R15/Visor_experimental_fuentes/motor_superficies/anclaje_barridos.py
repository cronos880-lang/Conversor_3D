"""Anclar perfiles medidos a encuentros nativos; no cambia sus tolerancias CAD."""
import itertools
import numpy as np
from scipy.interpolate import BSpline
from scipy.optimize import least_squares
from OCP.Geom import Geom_SurfaceOfLinearExtrusion
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
   if np.linalg.norm(difference)<1e-4:parent[root(w)]=root(v)
 clusters={}
 for v in keys:clusters.setdefault(root(v),[]).append(v)
 for cluster in clusters.values():
  a=axes[cluster[0]];P=mesh.vertices[cluster];Q=np.mean(P-np.outer(P@a,a),axis=0)
  for v in cluster:canonical[v]=Q+a*(mesh.vertices[v]@a)
 targets={};curves={};owners={};contexts={};mesh.propuestas_esquinas_medidas={}
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
   if len(native)<2 and not circles and len(sweeps)<2:continue
   origin=np.array(curve.Value(curve.FirstParameter()).Coord());target=point-axis*((point-origin)@axis)
   projection=GeomAPI_ProjectPointOnCurve(gp_Pnt(*map(float,target)),curve)
   choices=[curve.FirstParameter(),curve.LastParameter()]
   if projection.NbPoints():choices.append(projection.LowerDistanceParameter())
   from scipy.optimize import minimize_scalar
   grid=np.linspace(curve.FirstParameter(),curve.LastParameter(),257);j=min(range(len(grid)),key=lambda j:curve.Value(float(grid[j])).Distance(gp_Pnt(*map(float,target))))
   if 0<j<len(grid)-1:
    fit=minimize_scalar(lambda t:np.sum((np.array(curve.Value(float(t)).Coord())-target)**2),bounds=(grid[j-1],grid[j+1]),method='bounded',options={'xatol':1e-14});choices.append(float(fit.x))
   parameter=min(choices,key=lambda t:curve.Value(float(t)).Distance(gp_Pnt(*map(float,target))))
   knots_near=[curve.Knot(k) for k in range(1,curve.NbKnots()+1) if curve.Value(curve.Knot(k)).Distance(curve.Value(float(parameter)))<1e-5]
   if knots_near:parameter=min(knots_near,key=lambda k:abs(k-parameter))
   mesh.propuestas_esquinas_medidas[vertex]=point.copy();targets.setdefault(key,[]).append((float(parameter),target,vertex));curves[key]=curve;owners[key]=surface
 records=[]
 for key,rows in targets.items():
  curve=curves[key];axis=np.array(owners[key].Direction().Coord());origin=np.array(curve.Value(curve.FirstParameter()).Coord());rows.sort(key=lambda r:r[0]);clusters=[]
  for row in rows:
   if clusters and curve.Value(row[0]).Distance(curve.Value(clusters[-1][-1][0]))<1e-5:clusters[-1].append(row)
   else:clusters.append([row])
  merged=[]
  for cluster in clusters:
   if len(cluster)==1:merged.extend(cluster);continue
   preferred=[canonical[v]-axis*((canonical[v]-origin)@axis) for t,p,v in cluster if v in canonical]
   Q=np.asarray(preferred[0]) if preferred else np.mean([r[1] for r in cluster],axis=0);initial=np.r_[Q,[float((mesh.propuestas_esquinas_medidas[v]-Q)@axis) for t,p,v in cluster]]
   def native_residual(x):
    result=[float((x[:3]-origin)@axis)]
    if preferred:result.extend(x[:3]-Q)
    for j,(t,target,v) in enumerate(cluster):
     native,circles,p=contexts[v];point=x[:3]+axis*x[3+j]
     for region in native:result.extend(signed_projection(projectors[region],np.asarray([point]))[0])
     for q,a,r in circles:result.extend([(point-q)@a,np.linalg.norm(np.cross(point-q,a))-r])
    return np.array(result)
   fit=least_squares(lambda x:np.r_[native_residual(x),(x-initial)*1e-7],initial,xtol=1e-14,ftol=1e-14,gtol=1e-14,max_nfev=200)
   if abs(native_residual(fit.x)).max()>2e-7:raise ValueError('Los anclajes próximos no comparten una esquina nativa '+str(dict(regiones=[r for r,s in surfaces.items() if s is owners[key]],vertices=[v for t,p,v in cluster],nativas=[[(r,type(surfaces[r]).__name__) for r in contexts[v][0]] for t,p,v in cluster],residual=float(abs(native_residual(fit.x)).max()))))
   Q=fit.x[:3];parameter=float(np.mean([r[0] for r in cluster]))
   for j,(t,target,v) in enumerate(cluster):
    point=Q+axis*fit.x[3+j]
    if np.linalg.norm(point-mesh.vertices[v])>max_move:raise ValueError('La esquina conjunta abandona la fuente')
    mesh.propuestas_esquinas_medidas[v]=point;merged.append((parameter,Q.copy(),v))
  rows=merged;knots=[]
  for i in range(1,curve.NbKnots()+1):knots.extend([curve.Knot(i)]*curve.Multiplicity(i))
  rows.sort(key=lambda r:r[0]);parameters=np.array([r[0] for r in rows]);wanted=np.array([r[1] for r in rows]);current=np.array([curve.Value(float(t)).Coord() for t in parameters])
  # Insertar nudos NO altera la curva. Con multiplicidad cúbica, el
  # encuentro pasa por un polo. Trasladar ese polo y sus dos vecinos conserva
  # las derivadas primeras a ambos lados y evita un sistema mal condicionado.
  new=curve.Copy()
  if new.IsRational() or new.Degree()!=3:raise ValueError('Perfil no cúbico para anclaje acotado')
  for t in parameters:
   if new.FirstParameter()+1e-10<t<new.LastParameter()-1e-10:new.InsertKnot(float(t),3,1e-12,False)
  expanded=[]
  for i in range(1,new.NbKnots()+1):expanded.extend([new.Knot(i)]*new.Multiplicity(i))
  basis=BSpline.design_matrix(parameters,np.array(expanded),3).toarray();edits={}
  for row,parameter,target in zip(basis,parameters,wanted):
   index=int(row.argmax())
   if row[max(0,index-1):min(len(row),index+2)].sum()<1.-1e-6:raise ValueError('El nudo no interpola localmente su encuentro '+str(dict(regiones=[r for r,s in surfaces.items() if s is owners[key]],parametro=parameter,max_coef=float(row.max()),no_ceros=[(int(j),float(row[j])) for j in np.flatnonzero(row>1e-12)],nudos_cercanos=[float(k) for k in expanded if abs(k-parameter)<1e-6],anclajes=[(float(t),int(v)) for t,p,v in rows])))
   delta=target-np.array(new.Value(float(parameter)).Coord())
   for k in (index-1,index,index+1):
    if not 0<=k<new.NbPoles():continue
    if k in edits and np.linalg.norm(edits[k]-delta)>5e-8:raise ValueError('Anclajes demasiado próximos e incompatibles')
    edits[k]=delta
  maximum=max(float(np.linalg.norm(d)) for d in edits.values())
  if maximum>.003:raise ValueError(f'El anclaje local excede su cota: {maximum}')
  for index,change in edits.items():new.SetPole(index+1,gp_Pnt(*map(float,np.array(new.Pole(index+1).Coord())+change)))
  verified=max(new.Value(float(t)).Distance(gp_Pnt(*map(float,p))) for t,p in zip(parameters,wanted))
  if verified>5e-8:raise ValueError('No se conserva la esquina anclada')
  # La envolvente convexa B-spline limita el movimiento de TODO el perfil,
  # incluidos los intervalos sin muestras: <= mayor movimiento de sus polos.
  replacement=Geom_SurfaceOfLinearExtrusion(new,owners[key].Direction());labels=[r for r,s in surfaces.items() if s is owners[key]]
  for region in labels:surfaces[region]=replacement
  records.append(dict(regiones=labels,anclajes=len(rows),movimiento_max_polos_mm=maximum,residual_mm=verified));print('ANCLAJE BARRIDO',records[-1],flush=True)
 return records
