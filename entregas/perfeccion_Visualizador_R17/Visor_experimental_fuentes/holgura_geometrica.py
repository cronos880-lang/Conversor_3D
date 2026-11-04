"""Separación local de características no incidentes con control CGAL exacto."""
import time,numpy as np
from proximidad_triangular import punto_mas_cercano,baricentricas

def puntos_segmentos(a,b,c,d):
 u=b-a;v=d-c;w=a-c;A=np.sum(u*u,axis=-1);B=np.sum(u*v,axis=-1);C=np.sum(v*v,axis=-1);D=np.sum(u*w,axis=-1);E=np.sum(v*w,axis=-1);den=A*C-B*B
 s=np.divide(B*E-C*D,den,out=np.zeros_like(den),where=abs(den)>1e-14*A*C);t=np.divide(A*E-B*D,den,out=np.zeros_like(den),where=abs(den)>1e-14*A*C)
 ss=np.stack([s,np.zeros_like(s),np.ones_like(s),np.clip(-D/np.maximum(A,1e-300),0,1),np.clip((B-D)/np.maximum(A,1e-300),0,1)],axis=-1)
 tt=np.stack([t,np.clip(E/np.maximum(C,1e-300),0,1),np.clip((E+B)/np.maximum(C,1e-300),0,1),np.zeros_like(s),np.ones_like(s)],axis=-1)
 pp=a[...,None,:]+ss[...,None]*u[...,None,:];qq=c[...,None,:]+tt[...,None]*v[...,None,:];dist=np.sum((pp-qq)**2,axis=-1);dist[...,0]=np.where((s>=0)&(s<=1)&(t>=0)&(t<=1)&(abs(den)>1e-14*A*C),dist[...,0],np.inf);ix=np.argmin(dist,axis=-1)
 return np.take_along_axis(pp,ix[...,None,None],axis=-2)[...,0,:],np.take_along_axis(qq,ix[...,None,None],axis=-2)[...,0,:]

def _locator(V,F,lines=False):
 import vtk
 from vtk.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray
 p=vtk.vtkPolyData();points=vtk.vtkPoints();points.SetData(numpy_to_vtk(V,deep=True));p.SetPoints(points);cells=vtk.vtkCellArray();width=F.shape[1];cells.SetData(numpy_to_vtkIdTypeArray(np.arange(0,width*(len(F)+1),width,dtype=np.int64),deep=True),numpy_to_vtkIdTypeArray(np.asarray(F,dtype=np.int64).ravel(),deep=True));(p.SetLines if lines else p.SetPolys)(cells);loc=vtk.vtkStaticCellLocator();loc.SetDataSet(p);loc.BuildLocator();return loc

def candidatos(mesh,radio=1e-4):
 import vtk,trimesh
 V,F=mesh.vertices,mesh.faces;edges=mesh.edges_unique;locator=_locator(V,F);ids=vtk.vtkIdList();vfs=[]
 for i,p in enumerate(V):
  b=np.c_[p-radio,p+radio].ravel();locator.FindCellsWithinBounds(b,ids);near=np.array([ids.GetId(j) for j in range(ids.GetNumberOfIds())],int)
  if len(near):
   near=near[np.all(F[near]!=i,axis=1)]
   if len(near):
    q=punto_mas_cercano(V[F[near]],np.tile(p,(len(near),1)));near=near[np.linalg.norm(q-p,axis=1)<radio];vfs.extend((i,int(j)) for j in near)
 print('VF_CANDIDATOS',len(vfs),flush=True);locator=_locator(V,edges,True);ees=[]
 for i,edge in enumerate(edges):
  xyz=V[edge];b=np.c_[xyz.min(0)-radio,xyz.max(0)+radio].ravel();locator.FindCellsWithinBounds(b,ids);near=np.array([ids.GetId(j) for j in range(ids.GetNumberOfIds()) if ids.GetId(j)>i],int)
  if not len(near):continue
  near=near[~np.any(np.isin(edges[near],edge),axis=1)]
  if not len(near):continue
  a,b=xyz;c,d=np.moveaxis(V[edges[near]],1,0);p,q=puntos_segmentos(np.tile(a,(len(near),1)),np.tile(b,(len(near),1)),c,d);near=near[np.linalg.norm(p-q,axis=1)<radio];ees.extend((i,int(j)) for j in near)
 print('EE_CANDIDATOS',len(ees),flush=True)
 return np.asarray(vfs,dtype=int).reshape(-1,2),np.asarray(ees,dtype=int).reshape(-1,2),edges

def mejorar(mesh,control_path,*,objetivo=5e-6,deadline=None,max_vueltas=12):
 import trimesh
 from reparador_exacto_aislado import ControlExacto,medidas_superficie
 deadline=deadline or time.monotonic()+600;V=mesh.vertices.copy();base=V.copy();F=mesh.faces;check=ControlExacto(mesh,control_path)
 if check.pares():raise ValueError('Se requiere una malla sin autointersecciones')
 vf,ee,edges=candidatos(mesh);inc=[set() for _ in V]
 for i,f in enumerate(F):
  for v in f:inc[v].add(i)
 def altura(T):return np.linalg.norm(np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]),axis=1)/np.maximum(np.linalg.norm(T-np.roll(T,-1,axis=1),axis=2).max(1),1e-300)
 moves=[];trials=0
 def aplicar(ids,delta):
  nonlocal trials
  if time.monotonic()>deadline:raise TimeoutError('Separación local agotada')
  ids=np.asarray(ids,dtype=int);old=V[ids].copy();new=old+delta
  if np.max(np.linalg.norm(new-base[ids],axis=1))>.0005:return False
  affected=np.array(sorted(set().union(*(inc[v] for v in ids))));oldheight=altura(V[F[affected]]).min();V[ids]=new;h=altura(V[F[affected]]).min()
  if h<min(5e-7,oldheight*.8):V[ids]=old;return False
  for i,p in zip(ids,new):check.mover(int(i),p)
  trials+=1
  if check.pares():
   for i,p in zip(ids,old):check.mover(int(i),p)
   V[ids]=old;return False
  moves.append({'vertices':ids.tolist(),'desplazamiento_max_mm':float(np.linalg.norm(delta,axis=1).max())});return True
 for iteration in range(max_vueltas):
  if time.monotonic()>deadline:raise TimeoutError('Separación local agotada')
  count=0;changes=0;minimum=np.inf
  if len(vf):
   vs=vf[:,0];fs=F[vf[:,1]];q=punto_mas_cercano(V[fs],V[vs]);ds=np.linalg.norm(V[vs]-q,axis=1);order=np.argsort(ds)
   for j in order:
    vi=int(vs[j]);face=fs[j];p=V[vi];q=punto_mas_cercano(V[face][None,:,:],p[None,:])[0];d=float(np.linalg.norm(p-q));minimum=min(minimum,d)
    if d>=objetivo:continue
    count+=1
    if d<1e-14:continue
    direction=(p-q)/d;delta=direction*(objetivo-d)*1.25
    if aplicar([vi],delta[None,:]) or aplicar(face,np.tile(-delta,(3,1))) or aplicar(np.r_[vi,face],np.r_[delta[None,:]*.5,np.tile(-delta*.5,(3,1))]):changes+=1
  if len(ee):
   first,second=edges[ee[:,0]],edges[ee[:,1]];p,q=puntos_segmentos(V[first[:,0]],V[first[:,1]],V[second[:,0]],V[second[:,1]]);ds=np.linalg.norm(p-q,axis=1)
   for j in np.argsort(ds):
    a,b=first[j],second[j];p,q=puntos_segmentos(V[a[0]],V[a[1]],V[b[0]],V[b[1]]);d=float(np.linalg.norm(p-q));minimum=min(minimum,d)
    if d>=objetivo:continue
    count+=1
    if d<1e-14:continue
    delta=(p-q)/d*(objetivo-d)*1.25
    if aplicar(a,np.tile(delta,(2,1))) or aplicar(b,np.tile(-delta,(2,1))) or aplicar(np.r_[a,b],np.r_[np.tile(delta*.5,(2,1)),np.tile(-delta*.5,(2,1))]):changes+=1
  print('HOLGURA',iteration,'insuficientes',count,'cambios',changes,'min',minimum,flush=True)
  if not changes or not count:break
 candidate=trimesh.Trimesh(V,F,process=False);proof=medidas_superficie(mesh,candidate)
 if check.pares() or proof['max_mm']>.002:raise ValueError('No se conserva la geometría o la validez exacta')
 return candidate,{'movimientos':len(moves),'ensayos_cgal':trials,'objetivo_mm':objetivo,'superficie':proof,'desplazamiento_vertices_max_mm':float(np.linalg.norm(V-base,axis=1).max())}

def acoplar(mesh,control_path,*,objetivo=5e-6,deadline=None,max_vueltas=12,objetivo_altura=None,validar_extra=None):
 """Mover conjuntamente grupos de contactos para evitar el ciclo de empujes."""
 import trimesh
 from scipy.optimize import linprog
 from scipy.sparse import coo_matrix,hstack,vstack,eye
 from reparador_exacto_aislado import ControlExacto,medidas_superficie
 deadline=deadline or time.monotonic()+600;V=mesh.vertices.copy();base=V.copy();F=mesh.faces;check=ControlExacto(mesh,control_path)
 if check.pares():raise ValueError('La entrada debe estar libre de intersecciones')
 vf,ee,edges=candidatos(mesh);history=[]
 def distances():
  d=[]
  if len(vf):d.extend(np.linalg.norm(V[vf[:,0]]-punto_mas_cercano(V[F[vf[:,1]]],V[vf[:,0]]),axis=1))
  if len(ee):
   a,b=edges[ee[:,0]],edges[ee[:,1]];p,q=puntos_segmentos(V[a[:,0]],V[a[:,1]],V[b[:,0]],V[b[:,1]]);d.extend(np.linalg.norm(p-q,axis=1))
  d=np.asarray(d);loss=float(np.square(np.maximum(0,1-d/objetivo)).sum());bad=int((d<objetivo*.999).sum())
  if objetivo_altura:
   T=V[F];h=np.linalg.norm(np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]),axis=1)/np.maximum(np.linalg.norm(T-np.roll(T,-1,axis=1),axis=2).max(1),1e-300);loss+=float(np.square(np.maximum(0,1-h/objetivo_altura)).sum());bad+=int((h<objetivo_altura*.999).sum())
  return loss,bad,float(d.min(initial=np.inf))
 def rows():
  records=[]
  if len(vf):
   ps=V[vf[:,0]];tris=V[F[vf[:,1]]];qs=punto_mas_cercano(tris,ps);ds=np.linalg.norm(ps-qs,axis=1)
   for j in np.where((ds<objetivo*3)&(ds>1e-14))[0]:
    n=(ps[j]-qs[j])/ds[j];tri=tris[j];bary=baricentricas(tri[None,:,:],qs[j,None,:])[0];bary=np.clip(bary,0,1);bary/=bary.sum();ids=np.r_[vf[j,0],F[vf[j,1]]];g=np.vstack([n,-bary[:,None]*n]);records.append((ids,g,float(ds[j]),'VF'))
  if len(ee):
   aa,bb=edges[ee[:,0]],edges[ee[:,1]];ps,qs=puntos_segmentos(V[aa[:,0]],V[aa[:,1]],V[bb[:,0]],V[bb[:,1]]);ds=np.linalg.norm(ps-qs,axis=1)
   for j in np.where((ds<objetivo*3)&(ds>1e-14))[0]:
    a,b=aa[j],bb[j];u=V[a[1]]-V[a[0]];v=V[b[1]]-V[b[0]];s=np.clip((ps[j]-V[a[0]])@u/(u@u),0,1);t=np.clip((qs[j]-V[b[0]])@v/(v@v),0,1);n=(ps[j]-qs[j])/ds[j];ids=np.r_[a,b];g=np.array([(1-s)*n,s*n,-(1-t)*n,-t*n]);records.append((ids,g,float(ds[j]),'EE'))
  if objetivo_altura:
   T=V[F];cross=np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]);areas=np.linalg.norm(cross,axis=1);longest=np.linalg.norm(T-np.roll(T,-1,axis=1),axis=2).max(1);heights=areas/np.maximum(longest,1e-300)
   for j in np.where(heights<3*objetivo_altura)[0]:
    n=cross[j]/max(areas[j],1e-300);a,b,c=T[j];g=np.array([np.cross(b-c,n),np.cross(c-a,n),np.cross(a-b,n)])/max(longest[j],1e-300);records.append((F[j],g,float(heights[j]),'ALTURA'))
  return records
 def old_full_with(ids,positions):
  candidate=V.copy();candidate[ids]=positions;return candidate
 for iteration in range(max_vueltas):
  if time.monotonic()>deadline:raise TimeoutError('Separación acoplada agotada')
  from avance_conversion import avance
  avance(80+min(10,iteration*2),f'Preparando geometría para STEP · paso {iteration+1}')
  loss,bad,minimum=distances();print('ACOPLADO',iteration,'perdida',loss,'malas',bad,'min',minimum,flush=True)
  if bad==0:break
  records=rows();parents={}
  def find(x):
   parents.setdefault(x,x)
   while parents[x]!=x:parents[x]=parents[parents[x]];x=parents[x]
   return x
  for ids,g,d,kind in records:
   active=ids[np.linalg.norm(g,axis=1)>1e-10]
   for v in active:parents[find(int(v))]=find(int(active[0]))
  groups={}
  for row in records:
   active=row[0][np.linalg.norm(row[1],axis=1)>1e-10];groups.setdefault(find(int(active[0])),[]).append(row)
  changes=0
  for rr in groups.values():
   if all(d>=(objetivo_altura if kind=='ALTURA' else objetivo) for _,_,d,kind in rr):continue
   ids=np.unique(np.concatenate([a[np.linalg.norm(g,axis=1)>1e-10] for a,g,_,_ in rr]));mapping={int(v):i for i,v in enumerate(ids)};N=3*len(ids);ri=[];ci=[];vv=[];bounds=[];rowid=0
   for vertices,grad,d,kind in rr:
    for v,g in zip(vertices,grad):
     if int(v) not in mapping:continue
     for k in range(3):ri.append(rowid);ci.append(3*mapping[int(v)]+k);vv.append(float(g[k]))
    bounds.append(((objetivo_altura if kind=='ALTURA' else objetivo)-d)/objetivo);rowid+=1
   affected=np.where(np.any(np.isin(F,ids),axis=1))[0];T=V[F[affected]];cross=np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]);area=np.linalg.norm(cross,axis=1);normal=cross/area[:,None]
   for tri,n,ar,xyz in zip(F[affected],normal,area,T):
    grad=np.array([np.cross(xyz[1]-xyz[2],n),np.cross(xyz[2]-xyz[0],n),np.cross(xyz[0]-xyz[1],n)])*objetivo/max(ar,1e-30)
    for v,g in zip(tri,grad):
     if int(v) not in mapping:continue
     for k in range(3):ri.append(rowid);ci.append(3*mapping[int(v)]+k);vv.append(float(g[k]))
    bounds.append(-.4);rowid+=1
   A=coo_matrix((vv,(ri,ci)),shape=(rowid,N)).tocsr();I=eye(N,format='csr');Z=coo_matrix((rowid,N)).tocsr();AA=vstack([hstack([-A,Z]),hstack([I,-I]),hstack([-I,-I])],format='csr');bb=np.r_[-np.array(bounds),np.zeros(2*N)]
   result=linprog(np.r_[np.zeros(N),np.ones(N)],A_ub=AA,b_ub=bb,bounds=[(-10,10)]*N+[(0,None)]*N,method='highs',options={'time_limit':max(1.,min(30.,deadline-time.monotonic()))})
   if not result.success:print('LP_RECHAZADO',len(ids),result.message,flush=True);continue
   delta=result.x[:N].reshape(-1,3)*objetivo;old=V[ids].copy();before_loss,_,_=distances()
   for factor in (1.,.5,.25,.125,.0625):
    new=old+delta*factor
    if np.max(np.linalg.norm(new-base[ids],axis=1))>.0005:continue
    V[ids]=new;newtri=V[F[affected]];newcross=np.cross(newtri[:,1]-newtri[:,0],newtri[:,2]-newtri[:,0])
    if not np.all(np.isfinite(newcross)) or np.any(np.sum(newcross*normal,axis=1)<area*.1):V[ids]=old;continue
    newloss,newbad,_=distances()
    if not np.isfinite(newloss):V[ids]=old;continue
    if newloss>=before_loss-1e-7:V[ids]=old;continue
    valid=True
    for fraction in (.25,.5,.75,1.):
     for i,p in zip(ids,old+(new-old)*fraction):check.mover(int(i),p)
     if check.pares():valid=False;break
     if validar_extra is not None and not validar_extra(old_full_with(ids,old+(new-old)*fraction)):valid=False;break
    if valid:
     history.append({'grupo_vertices':len(ids),'factor':factor,'perdida_antes':before_loss,'perdida_despues':newloss,'malas_despues':newbad});changes+=1;print('LP_ACEPTADO',history[-1],flush=True);break
    for i,p in zip(ids,old):check.mover(int(i),p)
    V[ids]=old
   else:V[ids]=old
  if not changes:break
 candidate=trimesh.Trimesh(V,F,process=False);proof=medidas_superficie(mesh,candidate);loss,bad,minimum=distances()
 if check.pares() or proof['max_mm']>.002:raise ValueError('Separación acoplada no válida')
 return candidate,{'grupos_movidos':history,'objetivo_mm':objetivo,'perdida':loss,'pares_bajo_objetivo':bad,'min_holgura_mm':None if not np.isfinite(minimum) else minimum,'superficie':proof}
