"""Propuestas planas certificadas por TODOS los vértices de sus triángulos."""
import numpy as np
from OCP.Geom import Geom_Plane
from OCP.gp import gp_Pln,gp_Pnt,gp_Dir

def proponer(mesh,labels,surfaces,limite=1e-4):
 import meshfit_brep as base
 groups=base._groups(labels);out=dict(surfaces);normals=mesh.face_normals;area=mesh.area_faces
 # Direcciones medidas en las facetas mayores; no se usan ángulos nominales.
 candidates=normals[np.argsort(-area)[:256]];records=[]
 weights=np.array([float(area[np.abs(normals@n)>np.cos(.001)].sum()) for n in candidates])
 for region,ids in groups.items():
  old=surfaces[region]
  if not isinstance(old,Geom_Plane):continue
  P=mesh.vertices[np.unique(mesh.faces[ids])];n0=np.array(old.Axis().Direction().Coord());choices=[]
  for n,w in zip(candidates,weights):
   if abs(n@n0)<np.cos(.05):continue
   if n@n0<0:n=-n
   d=float(np.median(P@n));maximum=float(abs(P@n-d).max())
   if maximum<=limite:choices.append((w,-float(np.mean((P@n-d)**2)),n.copy(),d,maximum))
  if not choices:continue
  _,_,n,d,error=max(choices,key=lambda x:x[:2]);new=Geom_Plane(gp_Pln(gp_Pnt(*map(float,n*d)),gp_Dir(*map(float,n))));out[region]=new;records.append(dict(region=region,max_triangulos_mm=error))
 # Sólo unir soportes de regiones que comparten vértices fuente. Nunca agrupar
 # dos paredes opuestas separadas ni una cara distante por su proximidad.
 incidence={}
 for tri,region in zip(mesh.faces,labels):
  if not isinstance(out[int(region)],Geom_Plane):continue
  for v in tri:incidence.setdefault(int(v),set()).add(int(region))
 parent={r:r for r in groups};members={r:{r} for r in groups}
 def root(r):
  while parent[r]!=r:parent[r]=parent[parent[r]];r=parent[r]
  return r
 pairs=set()
 for regions in incidence.values():
  regions=sorted(regions)
  pairs.update((a,b) for i,a in enumerate(regions) for b in regions[i+1:])
 for first,second in sorted(pairs):
  a,b=root(first),root(second)
  if a==b:continue
  pa,pb=out[a],out[b];n=np.array(pa.Axis().Direction().Coord());m=np.array(pb.Axis().Direction().Coord())
  if abs(n@m)<1.-1e-12:continue
  ids=np.concatenate([groups[r] for r in members[a]|members[b]]);P=mesh.vertices[np.unique(mesh.faces[ids])];height=P@n;lo,hi=float(height.min()),float(height.max())
  if hi-lo>2*limite:continue
  d=(lo+hi)*.5;new=Geom_Plane(gp_Pln(gp_Pnt(*map(float,n*d)),gp_Dir(*map(float,n))))
  parent[b]=a;members[a]|=members[b];out[a]=new
 relabel=np.array([root(int(r)) for r in labels]);connected=base._split_connected(mesh,relabel);result={}
 for region,ids in base._groups(connected).items():result[region]=out[root(int(labels[ids[0]]))]
 print('PLANOS MEDIDOS',len(records),'max',max((r['max_triangulos_mm'] for r in records),default=0.),flush=True)
 return connected,result,records

def conciliar(mesh,labels,surfaces,limite=1e-4):
 """Ajuste lineal de offsets compartidos con cota geométrica por triángulo."""
 from OCP.Geom import Geom_CylindricalSurface,Geom_SurfaceOfLinearExtrusion
 from scipy.sparse import coo_matrix
 from scipy.sparse.linalg import lsmr
 import meshfit_brep as base
 groups=base._groups(labels);axes=[];sweep_axes=[np.array(s.Direction().Coord()) for s in surfaces.values() if isinstance(s,Geom_SurfaceOfLinearExtrusion)]
 for r,s in surfaces.items():
  if isinstance(s,Geom_CylindricalSurface):axes.append(np.array(s.Axis().Direction().Coord()))
  elif isinstance(s,Geom_SurfaceOfLinearExtrusion):axes.append(np.array(s.Direction().Coord()))
 families=[]
 for a in axes:
  if any(abs(a@b)>.999999 for b in families):continue
  near=[b for b in sweep_axes if abs(a@b)>.999999] or [b for b in axes if abs(a@b)>.999999]
  best=max(near,key=lambda b:sum(abs(b@c)>1.-1e-14 for c in near)).copy()
  constraints=np.array([b for b in families if abs(best@b)<1e-4])
  if len(constraints):
   _,sv,vh=np.linalg.svd(constraints,full_matrices=True);rank=int((sv>1e-5).sum());best-=vh[:rank].T@(vh[:rank]@best);best/=np.linalg.norm(best)
  families.append(best)
 # Las direcciones proceden de varios barridos/cilindros, sin ejes nominales.
 plane_groups={};owners={};out=dict(surfaces)
 for r,s in surfaces.items():
  if not isinstance(s,Geom_Plane):continue
  if len(groups[r])<=1:continue
  key=id(s);plane_groups.setdefault(key,[]).append(r);owners[key]=s
 data=[]
 for key,regions in plane_groups.items():
  s=owners[key];n=np.array(s.Axis().Direction().Coord());ids=np.concatenate([groups[r] for r in regions]);P=mesh.vertices[np.unique(mesh.faces[ids])]
  parallel=[a for a in families if abs(n@a)>.999999]
  if parallel:
   a=max(parallel,key=lambda a:abs(n@a));candidate=a if n@a>0 else -a
  else:
   constraints=np.array([a for a in families if abs(n@a)<1e-4]);candidate=n
   if len(constraints):
    _,singular,vh=np.linalg.svd(constraints,full_matrices=True);rank=int((singular>1e-5).sum())
    if rank<3:
     candidate=n-vh[:rank].T@(vh[:rank]@n)
     if np.linalg.norm(candidate)>1e-12:candidate/=np.linalg.norm(candidate)
  height=P@candidate;d=(height.max()+height.min())*.5
  if np.max(abs(height-d))>limite:candidate=n;height=P@n;d=(height.max()+height.min())*.5
  if np.max(abs(height-d))>limite:continue
  data.append(dict(regions=regions,n=candidate,d=float(d),ids=ids,points=P,area=float(mesh.area_faces[ids].sum())))
 index={r:i for i,item in enumerate(data) for r in item['regions']};incidence={}
 for tri,r in zip(mesh.faces,labels):
  if int(r) not in index:continue
  for v in tri:incidence.setdefault(int(v),set()).add(index[int(r)])
 vertices={v:sorted(rs) for v,rs in incidence.items() if len(rs)>=3};relations=[]
 from scipy.spatial import cKDTree
 for region,surface in surfaces.items():
  if not isinstance(surface,Geom_SurfaceOfLinearExtrusion) or region not in groups:continue
  selected=sorted(v for v in np.unique(mesh.faces[groups[region]]) if len(incidence.get(int(v),()))>=2)
  if len(selected)<2:continue
  a=np.array(surface.Direction().Coord());points=mesh.vertices[selected];projected=points-np.outer(points@a,a);parent=list(range(len(selected)))
  def root(j):
   while parent[j]!=j:parent[j]=parent[parent[j]];j=parent[j]
   return j
  for i,j in cKDTree(projected).query_pairs(1e-4):parent[root(j)]=root(i)
  clusters={}
  for j,v in enumerate(selected):clusters.setdefault(root(j),[]).append(int(v))
  for cluster in clusters.values():
   if len(cluster)<2:continue
   for v in cluster:vertices[v]=sorted(incidence[v])
   for v in cluster[1:]:relations.append((v,cluster[0],a))
 keys=list(vertices);lookup={v:i for i,v in enumerate(keys)};row=[];col=[];values=[];rhs=[]
 for vi,v in enumerate(keys):
  p=mesh.vertices[v]
  for pi in vertices[v]:
   item=data[pi];ri=len(rhs)
   for dim in range(3):row.append(ri);col.append(3*vi+dim);values.append(item['n'][dim])
   row.append(ri);col.append(3*len(keys)+pi);values.append(-1.);rhs.append(float(item['d']-item['n']@p))
 for first,second,axis in relations:
  projection=np.eye(3)-np.outer(axis,axis);initial=projection@(mesh.vertices[first]-mesh.vertices[second])
  for dim in range(3):
   ri=len(rhs)
   for side,sign in [(first,1.),(second,-1.)]:
    for j in range(3):row.append(ri);col.append(3*lookup[side]+j);values.append(float(sign*projection[dim,j]))
   rhs.append(float(-initial[dim]))
 print('ESQUINAS EXTRUIDAS COMPARTIDAS',len(relations),flush=True)
 delta=np.zeros(3*len(keys)+len(data));residual=0.
 if rhs:
  A=coo_matrix((values,(row,col)),shape=(len(rhs),len(delta))).tocsr();scale=np.r_[np.ones(3*len(keys)),[1./np.sqrt(max(item['area'],.01)) for item in data]];B=A.multiply(scale)
  solution=np.linalg.lstsq(B.toarray(),np.array(rhs),rcond=1e-11)[0];delta=scale*solution;residual=float(abs(A@delta-rhs).max())
  print('CONCILIACION SISTEMA',A.shape,'residual',residual,'movimiento',float(abs(delta[:3*len(keys)]).max()),flush=True)
  if residual>1e-9:raise ValueError(f'No se concilian los planos dentro de la precisión CAD: {residual}')
 for i,item in enumerate(data):
  d=item['d']+delta[3*len(keys)+i];error=float(abs(item['points']@item['n']-d).max())
  if error>limite:raise ValueError('La conciliación de planos supera la cota fuente '+str(dict(regiones=item['regions'],error=error,offset=delta[3*len(keys)+i],normal=item['n'].tolist())))
  surface=Geom_Plane(gp_Pln(gp_Pnt(*map(float,item['n']*d)),gp_Dir(*map(float,item['n']))))
  for region in item['regions']:out[region]=surface
 print('PLANOS CONCILIADOS',len(data),'esquinas',len(keys),'residual',residual,'offset_max',float(abs(delta[3*len(keys):]).max()) if len(data) else 0.,flush=True)
 return out
