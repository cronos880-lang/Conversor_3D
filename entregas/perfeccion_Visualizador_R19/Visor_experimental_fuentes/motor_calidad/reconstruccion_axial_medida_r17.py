"""Propuestas CAD desde perfiles y rebajes medidos en el STL original.

No se aceptan aquí: el trabajador verifica geometría, material y tres mallados.
"""
import numpy as np,cadquery as cq
from perfiles_planos_r15 import circle,compact,sketch

def ejes(mesh):
 N=np.asarray(mesh.face_normals);A=np.asarray(mesh.area_faces);out=[]
 groups=sorted(mesh.facets,key=lambda g:-A[g].sum())[:32]
 for group in groups:
  if len(group)<4:continue
  points=mesh.vertices[np.unique(mesh.faces[group])];center=points.mean(0);_,_,vt=np.linalg.svd(points-center,full_matrices=False);axis=vt[-1];axis*=np.sign(axis[np.argmax(abs(axis))]);residual=float(abs((points-center)@axis).max())
  lat=float(A[abs(N@axis)<1e-5].sum()/A.sum());cap=float(A[abs(N@axis)>1-1e-7].sum()/A.sum())
  if residual<.0001 and cap>.005 and lat>.4:out.append((residual/max(float(np.linalg.norm(np.ptp(points,axis=0))),1e-15),-float(A[group].sum()),axis))
 out.sort(key=lambda x:(x[0],x[1]));unique=[]
 for residual,area,axis in out:
  if not any(abs(axis@a)>1-1e-8 for a in unique):unique.append(axis)
 return unique
def base(axis):
 choice=int(np.argmin(abs(axis)));u=np.eye(3)[choice];u-=axis*(u@axis);u/=np.linalg.norm(u);v=np.cross(u,axis);return u,v

def secciones(mesh,axis,*,origin=None):
 u,v=base(axis);V=np.asarray(mesh.vertices);origin=V.mean(0) if origin is None else origin;Z=(V-origin)@axis;fractions=np.sort((np.arange(1,25)*.6180339887498949)%1);levels=[float(Z.min()+(Z.max()-Z.min())*f) for f in fractions if .03<f<.97];levels=[z for z in levels if np.min(abs(Z-z))>.0004];levels=[levels[i] for i in np.linspace(0,len(levels)-1,min(17,len(levels)),dtype=int)];records=[]
 if len(levels)<8:raise ValueError('No hay suficientes secciones alejadas de los cambios de estación')
 for z in levels:
  section=mesh.section(plane_origin=origin+axis*z,plane_normal=axis)
  if section is None:raise ValueError('Sección vacía')
  loops=section.discrete
  if len(loops)!=2:raise ValueError('No son dos contornos circulares completos')
  circles=[]
  for p in loops:
   xy=np.c_[(p-origin)@u,(p-origin)@v];xy=compact(xy)[:-1]
   if len(xy)<24:raise ValueError('Evidencia angular insuficiente para un círculo completo')
   c,r,error=circle(xy);a=xy-c;b=np.roll(a,-1,axis=0);d=b-a;t=np.clip(-np.sum(a*d,axis=1)/np.maximum(np.sum(d*d,axis=1),1e-30),0,1);rmin=np.linalg.norm(a+t[:,None]*d,axis=1).min();rmax=np.linalg.norm(a,axis=1).max();residual=max(abs(r-rmin),abs(r-rmax))
   if error>.004 or residual>.008:raise ValueError(f'La sección no aporta un círculo preciso: z={z}, r={r}, error_vertices={error}, error_segmentos={residual}, puntos={len(xy)}')
   circles.append(dict(center=c,radius=r,error=error,radial_segment_error=residual,points=len(xy)))
  if np.linalg.norm(circles[0]['center']-circles[1]['center'])>.001:raise ValueError('Contornos no coaxiales')
  records.append(dict(z=z,circles=circles,center=np.mean([c['center'] for c in circles],axis=0)))
 return origin,u,v,records

def _revolver_perfil(profile,origin,axis,u):
 P=compact(profile);original_profile=P.copy()
 def simplify(P):
  if len(P)<=2:return P
  D=P[-1]-P[0];norm=D@D
  distances=np.linalg.norm(P-P[0],axis=1) if norm<1e-24 else np.linalg.norm(P-(P[0]+np.clip((P-P[0])@D/norm,0,1)[:,None]*D),axis=1)
  i=int(np.argmax(distances))
  return np.vstack([simplify(P[:i+1])[:-1],simplify(P[i:])]) if distances[i]>.00008 else P[[0,-1]]
 P=simplify(P)
 # Shared meridian vertices remain shared after removing sampling noise.
 for coordinate in range(2):
  parents=list(range(len(P)-1))
  def find(i):
   while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
   return i
  for i in range(len(P)-1):
   j=(i+1)%(len(P)-1)
   if abs(P[i,coordinate]-P[j,coordinate])<.0001:parents[find(i)]=find(j)
  for root in set(map(find,range(len(P)-1))):
   ids=[i for i in range(len(P)-1) if find(i)==root];P[ids,coordinate]=np.mean(P[ids,coordinate])
 P[-1]=P[0]
 if len(P)-1>16:raise ValueError('El perfil medido requiere más de dieciséis tramos')
 edges=[cq.Edge.makeLine(cq.Vector(*(origin+u*a[0]+axis*a[1])),cq.Vector(*(origin+u*b[0]+axis*b[1]))) for a,b in zip(P[:-1],P[1:])]
 wire=cq.Wire.assembleEdges(edges);proof=dict(type='source_supported_lines',segments=len(edges),points=original_profile.tolist(),profile=P.tolist(),proposal_profile_mm=.0002)
 shape=cq.Solid.revolve(wire,[],360,cq.Vector(*origin),cq.Vector(*(origin+axis))).clean()
 if len(shape.Solids())!=1 or not shape.isValid():raise ValueError('Revolución inválida')
 return shape,proof

def construir(mesh):
 axes=ejes(mesh)
 if not axes:raise ValueError('Sin un eje de tapas y superficies')
 errors=[]
 for axis in axes[:3]:
  try:
   origin,u,v,sections=secciones(mesh,axis);Z=np.array([s['z'] for s in sections]);C=np.array([s['center'] for s in sections]);fit=np.linalg.lstsq(np.c_[Z,np.ones(len(Z))],C,rcond=None)[0];center=fit[1];refined=axis+u*fit[0,0]+v*fit[0,1];refined/=np.linalg.norm(refined)
   if np.linalg.norm(refined-axis)>2e-5:raise ValueError('El eje no se mantiene entre las secciones')
   origin=origin+u*center[0]+v*center[1];origin,u,v,sections=secciones(mesh,axis,origin=origin)
   if max(np.linalg.norm(s['center']) for s in sections)>.001:raise ValueError('No se confirma el eje completo')
   candidates=[]
   # A local planar recess must not become an annular groove by selecting its meridian.
   # Compare several measured meridians; the least segmented bulk is subsequently
   # checked against EVERY planar detail and the complete original surface.
   for angle in (0.,.6180339887498949*np.pi,1.2360679774997898*np.pi,1.8541019662496847*np.pi,.4721359549995796*np.pi):
    radial=u*np.cos(angle)+v*np.sin(angle);normal=np.cross(axis,radial);section=mesh.section(plane_origin=origin,plane_normal=normal)
    if section is None:continue
    profiles=[]
    for points in section.discrete:
     R=(points-origin)@radial;H=(points-origin)@axis
     if R.min()>0:profiles.append(np.c_[R,H])
    if len(profiles)!=1:continue
    try:
     shape,proof=_revolver_perfil(profiles[0],origin,axis,radial)
     candidates.append((len(shape.Faces()),-float(shape.Volume()),shape,proof,radial))
    except ValueError:continue
   if not candidates:raise ValueError('No se obtiene una región meridiana cerrada')
   _,_,shape,proof,radial=min(candidates,key=lambda item:(item[0],item[1]))
   return shape,dict(metodo='meridianos_contrastados_desde_STL',eje=axis.tolist(),origen=origin.tolist(),direccion_meridiana=radial.tolist(),meridianos_contrastados=len(candidates),perfil=proof,secciones=[dict(z=float(s['z']),radios=[c['radius']for c in s['circles']],error_max_circulo=max(c['radial_segment_error']for c in s['circles']))for s in sections],caras=len(shape.Faces()),volumen=float(shape.Volume()),volumen_original=float(mesh.volume))
  except Exception as exc:errors.append(str(exc))
 raise ValueError('; '.join(errors))



def regiones_planas_axiales(mesh,axis):
 import trimesh
 heights=np.asarray(mesh.vertices)@axis;F=np.asarray(mesh.faces);means=heights[F].mean(axis=1);dots=np.asarray(mesh.face_normals)@axis
 active=(np.ptp(heights[F],axis=1)<=.0001)&(abs(dots)>.9);ids=np.flatnonzero(active);links=mesh.face_adjacency
 valid=active[links[:,0]]&active[links[:,1]]&(dots[links[:,0]]*dots[links[:,1]]>0)&(abs(means[links[:,0]]-means[links[:,1]])<=.0001)
 return [np.asarray(group,dtype=int)for group in trimesh.graph.connected_components(links[valid],nodes=ids,min_len=1)]


def conservar_rebajes(mesh,shape,axis):
 from OCP.BRepClass3d import BRepClass3d_SolidClassifier
 from OCP.TopAbs import TopAbs_IN
 from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
 from OCP.BRepExtrema import BRepExtrema_DistShapeShape
 from OCP.gp import gp_Pnt,gp_Dir,gp_Lin
 from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector
 from shapely.geometry import Polygon
 from collections import Counter,defaultdict
 records=[];V,F=mesh.vertices,mesh.faces;axis=np.asarray(axis);u,v=base(axis);original=shape
 for group in regiones_planas_axiales(mesh,axis):
  indices=np.unique(F[group]);points=V[indices];origin=points.mean(0);normal=axis*np.sign(np.mean(mesh.face_normals[group],axis=0)@axis)
  if max(abs((points-origin)@normal))>.0001:continue
  if len(indices)>2048 or len(records)>=32:raise ValueError('Los detalles exceden el presupuesto de construcción')
  center=mesh.triangles_center[group[len(group)//2]];dist=BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float,center))).Vertex(),original.Shells()[0].wrapped);dist.Perform()
  if dist.Value()<.002:continue
  classifier=BRepClass3d_SolidClassifier(original.wrapped);classifier.Perform(gp_Pnt(*map(float,center)),1e-7)
  if classifier.State()!=TopAbs_IN:raise ValueError('Detalle saliente aún no admitido; conservar ruta anterior')
  ray=IntCurvesFace_ShapeIntersector();ray.Load(original.wrapped,1e-7);ray.Perform(gp_Lin(gp_Pnt(*map(float,center)),gp_Dir(*map(float,normal))),0,float(np.linalg.norm(mesh.extents)))
  depths=[ray.WParameter(i) for i in range(1,ray.NbPnt()+1) if ray.WParameter(i)>.001]
  if not depths:raise ValueError('No se encuentra la tapa correspondiente al rebaje')
  depth=min(depths)
  if depth>min(3.,np.linalg.norm(mesh.extents)*.05):raise ValueError('Rebaje fuera del alcance acotado')
  counter=Counter(tuple(sorted((int(a),int(b)))) for face in F[group] for a,b in zip(face,np.roll(face,-1)));edges=[e for e,c in counter.items() if c==1];adj=defaultdict(list)
  for a,b in edges:adj[a].append(b);adj[b].append(a)
  if any(len(x)!=2 for x in adj.values()):raise ValueError('Contorno plano ramificado')
  todo=set(adj);loops=[]
  while todo:
   first=min(todo);ids=[first];previous=None;current=first
   while True:
    nxt=next(x for x in adj[current] if x!=previous)
    if nxt==first:break
    if nxt in ids:raise ValueError('Ciclo plano repetido')
    ids.append(nxt);previous,current=current,nxt
   todo.difference_update(ids);P=V[ids];P=P-np.outer((P-origin)@normal,normal);xy=np.c_[P@u,P@v];poly=Polygon(xy)
   if not poly.is_valid or poly.area<1e-9:raise ValueError('Polígono plano no válido')
   loops.append((poly,P))
  parents=[]
  for i,(poly,P) in enumerate(loops):
   hosts=[j for j,(q,Q) in enumerate(loops) if j!=i and q.area>poly.area and q.covers(poly.representative_point())];parents.append(min(hosts,key=lambda j:loops[j][0].area) if hosts else None)
  for i,(poly,P) in enumerate(loops):
   if parents[i] is not None:continue
   outer=cq.Wire.makePolygon([cq.Vector(*p) for p in P],close=True);inner=[cq.Wire.makePolygon([cq.Vector(*p) for p in Q],close=True) for j,(q,Q) in enumerate(loops) if parents[j]==i]
   tool=cq.Solid.extrudeLinear(outer,inner,cq.Vector(*(normal*(depth+.001))));shape=shape.cut(tool)
  records.append(dict(faces=int(len(group)),faces_fuente=[int(i)for i in group],vertices=len(indices),depth_mm=float(depth),area_mm2=float(mesh.area_faces[group].sum()),contornos=len(loops)))
 shape=shape.clean()
 if len(shape.Solids())!=1 or not shape.isValid():raise ValueError('La recuperación de rebajes no deja un sólido válido')
 return shape,records



def proponer(mesh):
 if mesh.euler_number!=0:raise ValueError('La familia axial requiere una frontera de género uno')
 shape,proof=construir(mesh)
 if len(shape.Faces())>16:raise ValueError('El meridiano requiere más detalle del admitido por esta familia')
 shape,details=conservar_rebajes(mesh,shape,proof['eje'])
 if len(shape.Faces())>1500:raise ValueError('Los detalles superan el alcance de esta reconstrucción')
 proof.update(rebajes=details,caras_finales=len(shape.Faces()),metodo='revolucion_medida_con_rebajes_originales',limites_aceptacion_modificados=False)
 return shape,proof


def comprobar_detalles(mesh,shape,proof):
 from material_cad_indexado import ClasificadorMaterial
 ids=[i for g in proof['rebajes'] for i in g['faces_fuente']]
 if not ids:return dict(puntos=0,discrepancias=0,caras_fuente=0)
 ids=np.asarray(ids,dtype=int);centers=mesh.triangles_center[ids];normals=mesh.face_normals[ids];points=np.vstack([centers+normals*.0005,centers-normals*.0005]);expected=np.r_[np.zeros(len(ids),bool),np.ones(len(ids),bool)]
 classifier=ClasificadorMaterial(shape);actual=classifier.classify(points,expected=expected)
 if not np.array_equal(actual,expected):raise ValueError('Un detalle plano original ha desaparecido o cambiado de material')
 return dict(puntos=len(points),discrepancias=0,caras_fuente=len(ids),distancia_probe_mm=.0005,consultas_nativas=classifier.queries)
