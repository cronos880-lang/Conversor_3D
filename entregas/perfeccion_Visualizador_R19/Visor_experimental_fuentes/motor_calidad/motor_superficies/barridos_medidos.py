"""Reconocer perfiles extruidos desde testigos conectados del STL."""
import numpy as np
from proyector_perfil import ProyectorPerfil
from scipy.spatial import cKDTree,distance_matrix
from scipy.sparse.csgraph import minimum_spanning_tree,dijkstra
from scipy.interpolate import make_interp_spline,BSpline
from OCP.BRep import BRep_Tool
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.TopAbs import TopAbs_IN,TopAbs_ON
from OCP.Geom import Geom_Plane,Geom_BSplineSurface,Geom_CylindricalSurface,Geom_SurfaceOfLinearExtrusion,Geom_BSplineCurve
from OCP.gp import gp_Pnt,gp_Pnt2d,gp_Dir
import meshfit_brep as base

def curva_ocp(spline,q,basis):
 from OCP.TColgp import TColgp_Array1OfPnt
 from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
 poles=TColgp_Array1OfPnt(1,len(spline.c));knots,mults=np.unique(spline.t,return_counts=True);K=TColStd_Array1OfReal(1,len(knots));M=TColStd_Array1OfInteger(1,len(knots))
 for j,p in enumerate(spline.c,1):poles.SetValue(j,gp_Pnt(*map(float,q+basis@p)))
 for j,(k,m) in enumerate(zip(knots,mults),1):K.SetValue(j,float(k));M.SetValue(j,int(m))
 return Geom_BSplineCurve(poles,K,M,3,False)

def ajustar(face,surf,mesh,axes,excluidos=(),ajuste_perfil=.0003,source_ids=None):
 if source_ids is None:
  pr=base._Proj(surf);C=mesh.triangles_center;bb=face.BoundingBox();mask=np.all((C>=[bb.xmin-.03,bb.ymin-.03,bb.zmin-.03])&(C<=[bb.xmax+.03,bb.ymax+.03,bb.zmax+.03]),axis=1);ids=np.flatnonzero(mask);P=C[ids];dist=np.linalg.norm(P-pr.batch(P),axis=1);normals=np.array([pr.normal(p) for p in P]);ndot=np.abs(np.sum(normals*mesh.face_normals[ids],axis=1));ids=ids[(dist<.04)&(ndot>.9)]
  inside=[]
  for k in ids:
   _,uv=pr(C[k]);inside.append(uv is not None and BRepClass_FaceClassifier(face.wrapped,gp_Pnt2d(*map(float,uv)),1e-7).State() in (TopAbs_IN,TopAbs_ON))
  ids=ids[np.array(inside,bool)]
  if len(excluidos):ids=ids[~np.isin(ids,excluidos)]
 else:ids=np.asarray(source_ids,dtype=int).copy()
 if len(ids)<12:raise ValueError('Apoyo insuficiente para un barrido')
 for _ in range(3):
  N=mesh.face_normals[ids];weights=mesh.area_faces[ids];values,vectors=np.linalg.eigh((N.T*weights)@N);a=vectors[:,0];good=abs(N@a)<.005
  if good.all():break
  ids=ids[good]
  if len(ids)<12:raise ValueError('No se confirma una dirección de extrusión')
 candidates=[candidate for candidate in axes if abs(a@candidate)>.999999 and np.max(abs(mesh.face_normals[ids]@candidate))<.005]
 if candidates:
  N=mesh.face_normals[ids];weights=mesh.area_faces[ids]
  a=np.array(min(candidates,key=lambda candidate:float(np.average((N@candidate)**2,weights=weights))),float)
 if a[np.argmax(abs(a))]<0:a=-a
 N=mesh.face_normals[ids];weights=mesh.area_faces[ids]
 if weights.sum()<(.1 if face is None or len(excluidos) else .5*face.Area()):raise ValueError('Cobertura insuficiente del barrido')
 helper=np.eye(3)[np.argmin(abs(a))];e=np.cross(a,helper);e/=np.linalg.norm(e);f=np.cross(a,e);basis=np.column_stack([e,f]);V=mesh.vertices[np.unique(mesh.faces[ids])];q=V.mean(0);uv=(V-q)@basis
 if len(uv)>5000:raise ValueError('Demasiados testigos para un perfil medido acotado')
 parent=np.arange(len(uv))
 def root(j):
  while parent[j]!=j:parent[j]=parent[parent[j]];j=parent[j]
  return j
 for x,y in cKDTree(uv).query_pairs(5e-5):parent[root(y)]=root(x)
 owner=np.array([root(j) for j in range(len(uv))]);unique=np.unique(owner);points=np.array([uv[owner==j].mean(0) for j in unique])
 if len(points)>1800:raise ValueError('El perfil supera el presupuesto de 1800 nodos')
 graph=minimum_spanning_tree(distance_matrix(points,points));graph=graph+graph.T;d=dijkstra(graph,indices=0);start=int(np.argmax(d));d,prev=dijkstra(graph,indices=start,return_predecessors=True);end=int(np.argmax(d));path=[end]
 while path[-1]!=start:path.append(int(prev[path[-1]]))
 profile=points[path[::-1]]
 if cKDTree(profile).query(points)[0].max()>.003:raise ValueError('El perfil tiene ramas o testigos incompatibles')
 lengths=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(profile,axis=0),axis=1))]
 step=min(.02,float(lengths[-1])/60.)
 t=np.linspace(0.,lengths[-1],min(1500,max(61,int(np.ceil(lengths[-1]/step))+1)))
 P=np.column_stack([np.interp(t,lengths,profile[:,j]) for j in range(2)])
 spline=None
 def solve(interior):
  knots=np.r_[[t[0]]*4,interior,[t[-1]]*4]
  design=BSpline.design_matrix(t,knots,3).toarray();coefficients=np.empty((design.shape[1],2));coefficients[0]=P[0];coefficients[-1]=P[-1]
  coefficients[1:-1]=np.linalg.lstsq(design[:,1:-1],P-design[:,[0]]*P[0]-design[:,[-1]]*P[-1],rcond=None)[0]
  candidate=BSpline(knots,coefficients,3);return candidate,np.linalg.norm(candidate(t)-P,axis=1)
 for spans in (1,2,4,8,16,32,64,128,256):
  if spans+3>=len(t):break
  candidate,error=solve(np.linspace(t[0],t[-1],spans+1)[1:-1])
  if error.max()<=ajuste_perfil:spline=candidate;break
 if spline is None or len(spline.c)>64:
  interior=[]
  for iteration in range(180):
   candidate,error=solve(interior)
   if error.max()<=ajuste_perfil:
    if spline is None or len(candidate.c)<len(spline.c):spline=candidate
    break
   choices=np.argsort(-error);selected=None
   for j in choices:
    if 0<j<len(t)-1 and all(abs(t[j]-k)>max(1e-8,(t[-1]-t[0])*1e-8) for k in interior):selected=float(t[j]);break
   if selected is None:break
   interior=sorted([*interior,selected])
 if spline is None:spline=make_interp_spline(t,P,k=3)
 print('PERFIL SUAVE',len(spline.c),'polos',flush=True)
 ts=np.linspace(t[0],t[-1],12001);grid=spline(ts);upper=cKDTree(grid).query(uv)[0].max()
 if upper>.003:raise ValueError(f'El barrido no conserva los testigos: {upper}')
 # Cota inversa: la curva tampoco puede salir de la polilínea fuente.
 maximum=0.;A=profile[:-1];D=np.diff(profile,axis=0);den=np.sum(D*D,axis=1)
 for first in range(0,len(grid),256):
  G=grid[first:first+256];delta=G[:,None,:]-A[None,:,:];u=np.clip(np.sum(delta*D[None,:,:],axis=2)/den,0,1);distance=np.linalg.norm(delta-u[:,:,None]*D[None,:,:],axis=2).min(axis=1);maximum=max(maximum,float(distance.max()))
 if maximum>.003:raise ValueError(f'El barrido oscila fuera de la fuente: {maximum}')
 curve=curva_ocp(spline,q,basis)
 # Prolongación sólo para calcular encuentros; se verifica el STEP completo.
 from geometria_medida import extend_profile
 curve=extend_profile(curve)
 surface=Geom_SurfaceOfLinearExtrusion(curve,gp_Dir(*map(float,a)))
 return surface,ids,dict(eje=a.tolist(),vertices_fuente=len(V),max_testigos_mm=float(upper),max_curva_polilinea_mm=maximum,area_fuente=float(weights.sum()))

def propuestas(faces,surfaces,mesh,required,planos_protegidos=(),ajuste_perfil=.0003):
 excluidos=np.unique(np.concatenate([ids for ids,s in planos_protegidos])) if planos_protegidos else np.array([],int)
 records=[];extras=[];out=list(surfaces);raw_axes=[np.array(r['eje']) for r in required]+[np.array(s.Pln().Axis().Direction().Coord()) for ids,s in planos_protegidos if len(ids)>=2];axes=[]
 for a in raw_axes:
  if any(abs(a@b)>.999999 for b in axes):continue
  near=[b for b in raw_axes if abs(a@b)>.999999];representative=max(near,key=lambda b:sum(abs(b@c)>1.-1e-14 for c in near));axes.append(representative)
 for i,s in enumerate(surfaces):
  if faces[i].Area()<.1:
   print("BARRIDO OMITIDO",i,"área de hipótesis menor de .1 mm2",flush=True);continue
  if not isinstance(s,(Geom_BSplineSurface,Geom_CylindricalSurface)):continue
  if isinstance(s,Geom_CylindricalSurface) and any(abs(s.Radius()-r['radio'])<.008 and abs(np.array(s.Axis().Direction().Coord())@r['eje'])>.99999 and np.linalg.norm(np.cross(np.array(s.Location().Coord())-r['centro'],r['eje']))<.008 for r in required):continue
  try:new,ids,proof=ajustar(faces[i],s,mesh,axes,excluidos,ajuste_perfil)
  except Exception as e:print('BARRIDO DESCARTADO',i,str(e),flush=True);continue
  original_ids=ids.copy();pr=ProyectorPerfil(new);roi=mesh.vertices[np.unique(mesh.faces[ids])];centers=mesh.triangles_center;axis=np.array(new.Direction().Coord());projected_roi=roi-np.outer(roi@axis,axis);projected_centers=centers-np.outer(centers@axis,axis);candidate=np.flatnonzero(np.all((projected_centers>=projected_roi.min(0)-.005)&(projected_centers<=projected_roi.max(0)+.005),axis=1));test=np.concatenate([mesh.triangles[candidate],mesh.triangles_center[candidate,None,:]],axis=1);distance=np.linalg.norm(pr.batch(test.reshape(-1,3))-test.reshape(-1,3),axis=1).reshape(-1,4).max(1);candidate=candidate[(distance<.003)&~np.isin(candidate,excluidos)]
  if len(candidate):
   normals=np.array([pr.normal(p) for p in mesh.triangles_center[candidate]]);candidate=candidate[abs(np.sum(normals*mesh.face_normals[candidate],axis=1))>.995]
  allowed=set(map(int,np.r_[ids,candidate]));keep=set(map(int,ids));adj=mesh.face_adjacency
  for _ in range(20):
   added={int(b) for a,b in np.r_[adj,adj[:,::-1]] if int(a) in keep and int(b) in allowed};newkeep=keep|added
   if len(newkeep)==len(keep):break
   keep=newkeep
  ids=np.array(sorted(keep));proof['triangulos_ampliados']=len(ids)-len(original_ids)
  out[i]=new;extras.append((ids,new));records.append(dict(cara=i,**proof));print('BARRIDO MEDIDO',i,proof,flush=True)
 # Compartir las direcciones medidas antes de conciliar sus planos vecinos.
 measured=[(np.array(s.Direction().Coord()),float(mesh.area_faces[ids].sum())) for ids,s in extras]
 families=[]
 for a,w in sorted(measured,key=lambda item:-sum(abs(item[0]@other)>.999999 for other,weight in measured)):
  if any(abs(a@b)>.999999 for b in families):continue
  near=[(b,weight) for b,weight in measured if abs(a@b)>.999999];best=max(near,key=lambda item:(sum(abs(item[0]@other)>1-1e-14 for other,weight in near),item[1]))[0].copy()
  constraints=np.array([b for b in families if abs(best@b)<1e-4])
  if len(constraints):
   _,sv,vh=np.linalg.svd(constraints,full_matrices=True);rank=int((sv>1e-5).sum());best-=vh[:rank].T@(vh[:rank]@best);best/=np.linalg.norm(best)
  families.append(best)
 for j,((ids,surface),record) in enumerate(zip(extras,records)):
  old_axis=np.array(surface.Direction().Coord());axis=max(families,key=lambda a:abs(a@old_axis));axis=axis if axis@old_axis>0 else -axis
  if np.linalg.norm(axis-old_axis)<1e-14:continue
  curve=surface.BasisCurve().Copy();origin=np.array(curve.Value(curve.FirstParameter()).Coord())
  for k in range(1,curve.NbPoles()+1):
   p=np.array(curve.Pole(k).Coord());p-=axis*((p-origin)@axis);curve.SetPole(k,gp_Pnt(*map(float,p)))
  candidate=Geom_SurfaceOfLinearExtrusion(curve,gp_Dir(*map(float,axis)));P=mesh.vertices[np.unique(mesh.faces[ids])];error=float(np.linalg.norm(ProyectorPerfil(candidate).batch(P)-P,axis=1).max())
  if error>.003:raise ValueError('La dirección compartida no conserva el perfil fuente')
  out[record['cara']]=candidate;extras[j]=(ids,candidate);record['eje']=axis.tolist();record['direccion_compartida_max_fuente_mm']=error
 return out,extras,records

def restos_fuente(result,mesh,extras,required):
 """Medir los perfiles que quedaron fuera de la guía CAD provisional."""
 labels,surfaces=base._region_surfaces(result,mesh,.006,.003,extra=extras)
 groups=base._groups(labels);known=len(extras);additional=[];records=[]
 axes=[np.array(s.Direction().Coord()) for ids,s in extras if isinstance(s,Geom_SurfaceOfLinearExtrusion)]
 axes.extend(np.array(r['eje']) for r in required)
 axes.extend(np.array(s.Pln().Axis().Direction().Coord()) for ids,s in extras if isinstance(s,Geom_Plane) and len(ids)>=2)
 unique=[]
 for axis in axes:
  if not any(abs(axis@other)>.999999 for other in unique):unique.append(axis)
 axes=unique
 # Las primitivas descartadas por error de radio pueden ser perfiles NO
 # circulares extruidos. Medirlas antes de la limpieza que las fragmenta.
 protected=np.unique(np.concatenate([np.asarray(f,int) for f,s in extras])) if extras else np.empty(0,int)
 candidates=[]
 for primitive in result['primitives']:
  if primitive['type']=='cylinder' and not required:
   ids=np.setdiff1d(np.asarray(primitive['faces'],int),protected)
   if len(ids)>=12:candidates.append(('primitiva_'+str(len(candidates)),ids,None))
 candidates.extend((region,ids,surfaces[region]) for region,ids in groups.items() if isinstance(surfaces[region],Geom_BSplineSurface) and len(ids)>=12)
 occupied=set(map(int,protected))
 for region,ids,surface in candidates:
  ids=np.array([int(i) for i in ids if int(i) not in occupied],int)
  if len(ids)<12:continue
  try:
   new,indices,proof=ajustar(None,surface,mesh,axes,source_ids=ids)
   P=np.concatenate([mesh.vertices[mesh.faces[indices]],mesh.triangles_center[indices,None,:]],axis=1)
   error=np.linalg.norm(ProyectorPerfil(new).batch(P.reshape(-1,3))-P.reshape(-1,3),axis=1).reshape(-1,4).max(1)
   indices=indices[error<=.003]
   if len(indices)<12:raise ValueError('Falta apoyo de triángulos completos')
   additional.append((indices,new));occupied.update(map(int,indices));records.append(dict(tipo='resto_medido_desde_fuente',triangulos=len(indices),max_triangulos_mm=float(error[error<=.003].max()),**proof));print('RESTO FUENTE MEDIDO',records[-1],flush=True)
  except Exception as exc:print('RESTO FUENTE DESCARTADO',region,str(exc),flush=True)
 return additional,records

def fusionar_continuaciones(mesh,extras):
 """Un corte oblicuo entre perfiles del mismo barrido no es una generatriz.

 Reunir su fuente y volver a medir UNA curva, sólo con apoyo de triángulos
 completos y una unión suave. No se tocan planos ni cilindros protegidos.
 """
 out=list(extras);proof=[]
 for iteration in range(16):
  owner=np.full(len(mesh.faces),-1,int)
  for i,(ids,s) in enumerate(out):
   ids=np.asarray(ids,int);owner[ids[owner[ids]<0]]=i
  adj=mesh.face_adjacency;pairs={tuple(sorted(map(int,p))) for p in owner[adj] if p[0]>=0 and p[1]>=0 and p[0]!=p[1]};merged=False
  for i,j in sorted(pairs):
   sa,sb=out[i][1],out[j][1]
   if not all(isinstance(s,Geom_SurfaceOfLinearExtrusion) for s in (sa,sb)):continue
   axis=np.array(sa.Direction().Coord());other=np.array(sb.Direction().Coord())
   if np.linalg.norm(np.cross(axis,other))>1e-8:continue
   mask=((owner[adj[:,0]]==i)&(owner[adj[:,1]]==j))|((owner[adj[:,0]]==j)&(owner[adj[:,1]]==i));links=np.flatnonzero(mask);edges=mesh.face_adjacency_edges[links];D=mesh.vertices[edges[:,1]]-mesh.vertices[edges[:,0]];length=np.linalg.norm(D,axis=1);transverse=np.linalg.norm(np.cross(D,axis),axis=1)
   if not np.any((length>.1)&(transverse>5e-5)):continue
   normals=np.sum(mesh.face_normals[adj[links,0]]*mesh.face_normals[adj[links,1]],axis=1)
   if np.sum(length[normals>np.cos(np.radians(15))])<.9*np.sum(length):continue
   ids=np.flatnonzero((owner==i)|(owner==j))
   try:
    new,ids,record=ajustar(None,None,mesh,[axis],source_ids=ids)
    P=np.concatenate([mesh.vertices[mesh.faces[ids]],mesh.triangles_center[ids,None,:]],axis=1);error=float(np.linalg.norm(ProyectorPerfil(new).batch(P.reshape(-1,3))-P.reshape(-1,3),axis=1).max())
    if error>.003:raise ValueError('La unión no conserva los triángulos completos')
   except Exception as exc:print('CONTINUACION DESCARTADA',str(exc),flush=True);continue
   record.update(tipo='continuacion_de_barrido_fuente',triangulos=len(ids),max_triangulos_mm=error);proof.append(record);out[i]=(ids,new);out.pop(j);merged=True;print('CONTINUACION FUENTE REUNIDA',record,flush=True);break
  if not merged:break
 return out,proof
