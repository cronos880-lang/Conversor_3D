"""Conservative source-only eligibility; no CAD imports or acceptance decisions."""
import numpy as np
from shapely.geometry import Polygon,Point

def compact(P,tol=1e-8,mandatory=()):
 P=np.asarray(P,float)
 if np.linalg.norm(P[0]-P[-1])<1e-8:P=P[:-1]
 prev=np.roll(P,1,axis=0);nxt=np.roll(P,-1,axis=0);a=P-prev;b=nxt-P
 cr=abs(a[:,0]*b[:,1]-a[:,1]*b[:,0]);keep=cr>tol*np.maximum(np.linalg.norm(a,axis=1)+np.linalg.norm(b,axis=1),1e-30)
 for point in mandatory:keep[int(np.linalg.norm(P-point,axis=1).argmin())]=True
 P=P[keep]
 turn=np.linalg.norm(P-np.roll(P,1,axis=0),axis=1)
 # Start at strongest corner; circle-only profiles handled separately.
 aa=P-np.roll(P,1,axis=0);bb=np.roll(P,-1,axis=0)-P
 cos=np.sum(aa*bb,axis=1)/np.maximum(np.linalg.norm(aa,axis=1)*np.linalg.norm(bb,axis=1),1e-30)
 P=np.roll(P,-int(np.argmin(cos)),axis=0)
 return np.vstack([P,P[0]])

def circle(P):
 p=np.asarray(P,float);origin=p.mean(0);xy=p-origin
 x,y,k=np.linalg.lstsq(np.c_[2*xy,np.ones(len(p))],(xy*xy).sum(1),rcond=None)[0];c=origin+[x,y];r=np.sqrt(max(0,k+x*x+y*y));err=float(abs(np.linalg.norm(p-c,axis=1)-r).max())
 return c,float(r),err

def ejes(mesh):
 N=np.asarray(mesh.face_normals);A=np.asarray(mesh.area_faces);out=[]
 groups=sorted(mesh.facets,key=lambda g:-A[g].sum())[:32]
 for group in groups:
  if len(group)<4:continue
  points=mesh.vertices[np.unique(mesh.faces[group])];center=points.mean(0);_,_,vt=np.linalg.svd(points-center,full_matrices=False);axis=vt[-1];axis*=np.sign(axis[np.argmax(abs(axis))]);residual=float(abs((points-center)@axis).max())
  lat=float(A[abs(N@axis)<1e-5].sum()/A.sum());cap=float(A[abs(N@axis)>1-1e-7].sum()/A.sum())
  if residual<.0001 and cap>.005 and lat>.10:out.append((residual/max(float(np.linalg.norm(np.ptp(points,axis=0))),1e-15),-float(A[group].sum()),axis))
 out.sort(key=lambda x:(x[0],x[1]));unique=[]
 for residual,area,axis in out:
  if not any(abs(axis@a)>1-1e-8 for a in unique):unique.append(axis)
 return unique

def base(axis):
 choice=int(np.argmin(abs(axis)));u=np.eye(3)[choice];u-=axis*(u@axis);u/=np.linalg.norm(u);v=np.cross(u,axis);return u,v

def _circulo(P):
 P=compact(P)[:-1]
 if len(P)<24:raise ValueError('Evidencia angular insuficiente')
 c,r,error=circle(P);A=P-c;B=np.roll(A,-1,axis=0);D=B-A
 t=np.clip(-np.sum(A*D,axis=1)/np.maximum(np.sum(D*D,axis=1),1e-30),0,1)
 residual=max(abs(r-np.linalg.norm(A+t[:,None]*D,axis=1).min()),abs(r-np.linalg.norm(A,axis=1).max()))
 if error>.004 or residual>.008:raise ValueError('El contorno completo no es circular')
 return dict(center=c,radius=r,error=error,radial_segment_error=float(residual),points=len(P),parcial=False)

def _arcos_soportados(P,center):
 P=compact(P)[:-1];R=np.linalg.norm(P-center,axis=1);order=np.argsort(R)
 # A dense supported radius is evidence of cylindrical arcs; fins extend outward.
 best=[];end=0
 for start in range(len(order)):
  end=max(end,start)
  while end<len(order) and R[order[end]]-R[order[start]]<=.004:end+=1
  ids=order[start:end]
  if len(ids)>len(best):best=ids
 if len(best)<24:raise ValueError('No hay arcos exteriores suficientes')
 radius=float(np.median(R[best]));A=P-center;B=np.roll(A,-1,axis=0);D=B-A
 mask=(abs(R-radius)<=.004)&(abs(np.roll(R,-1)-radius)<=.004)
 t=np.clip(-np.sum(A*D,axis=1)/np.maximum(np.sum(D*D,axis=1),1e-30),0,1)
 errors=np.maximum(abs(np.linalg.norm(A+t[:,None]*D,axis=1)-radius),np.maximum(abs(R-radius),abs(np.roll(R,-1)-radius)))
 mask&=errors<=.008
 turns=np.abs(np.arctan2(A[:,0]*B[:,1]-A[:,1]*B[:,0],np.sum(A*B,axis=1)))
 coverage=float(turns[mask].sum())
 if mask.sum()<24 or coverage<np.pi:raise ValueError('Los arcos no cubren media vuelta comprobada')
 return dict(center=np.asarray(center),radius=radius,error=float(abs(R[best]-radius).max()),radial_segment_error=float(errors[mask].max()),points=int(mask.sum()),parcial=True,cobertura_rad=coverage,vertices_hacia_interior=int(np.sum(R<radius-.008)))

def secciones(mesh,axis,origin=None,maximum=17,niveles=None):
 u,v=base(axis);V=np.asarray(mesh.vertices);origin=V.mean(0)if origin is None else origin;Z=(V-origin)@axis
 if niveles is None:
  fractions=np.sort((np.arange(1,25)*.6180339887498949)%1)
  levels=[float(Z.min()+np.ptp(Z)*f)for f in fractions if .03<f<.97]
  levels=[z for z in levels if np.min(abs(Z-z))>.0004]
  if len(levels)<8:raise ValueError('Estaciones insuficientes')
  levels=[levels[i]for i in np.linspace(0,len(levels)-1,min(maximum,len(levels)),dtype=int)]
 else:
  levels=[float(z)for z in niveles if Z.min()<z<Z.max()and np.min(abs(Z-z))>.0004]
  if not levels:raise ValueError('Sin estaciones complementarias válidas')
 records=[]
 for z in levels:
  cut=mesh.section(plane_origin=origin+axis*z,plane_normal=axis)
  if cut is None or not 1<=len(cut.discrete)<=20:raise ValueError('Sección fuera de la familia axial')
  loops=[np.c_[(P-origin)@u,(P-origin)@v]for P in cut.discrete];complete=[];polygons=[Polygon(P)for P in loops]
  if any(not p.is_valid for p in polygons):raise ValueError('Contorno de sección inválido')
  for i,P in enumerate(loops):
   try:complete.append((i,_circulo(P)))
   except ValueError:pass
  if not complete:raise ValueError('Falta un contorno circular completo para medir el eje')
  reference=max(complete,key=lambda item:item[1]['radius'])[1]['center'];hosts=[i for i,p in enumerate(polygons)if p.covers(Point(reference))]
  if not hosts:raise ValueError('No hay material alrededor del eje medido')
  index=max(hosts,key=lambda i:polygons[i].area);full={i:c for i,c in complete}
  outer=full[index]if index in full else _arcos_soportados(loops[index],reference)
  if mesh.euler_number==2:
   circles=[outer]
  else:
   inner_candidates=[(i,c)for i,c in complete if i!=index and np.linalg.norm(c['center']-outer['center'])<=.001 and polygons[index].covers(polygons[i])and c['radius']<outer['radius']]
   if not inner_candidates:raise ValueError('Falta el contorno circular del taladro pasante')
   inner=min(inner_candidates,key=lambda item:item[1]['radius'])[1];circles=[inner,outer]
  if max(np.linalg.norm(c['center']-circles[0]['center'])for c in circles)>.001:raise ValueError('Círculos no coaxiales')
  records.append(dict(z=z,circles=circles,center=np.mean([c['center']for c in circles],axis=0),otros_contornos=len(loops)-len(circles)))
 return origin,u,v,records


def pertenece(mesh):
 """Cheap family guard. All acceptance controls remain in the worker."""
 if mesh.euler_number not in (0,2)or not mesh.is_watertight or not mesh.is_winding_consistent:return False
 for axis in ejes(mesh)[:3]:
  try:
   origin,u,v,rows=secciones(mesh,axis,maximum=3)
   if mesh.euler_number==2:return True
   if not any(r['otros_contornos']or any(c['parcial']for c in r['circles'])for r in rows):continue
   radius=float(np.median([max(c['radius']for c in r['circles'])for r in rows]));center=np.mean([r['center']for r in rows],axis=0);point=origin+u*center[0]+v*center[1]
   candidates=0
   for group in mesh.facets:
    area=float(mesh.area_faces[group].sum())
    if area<mesh.area*.003:continue
    N=np.average(mesh.face_normals[group],axis=0,weights=mesh.area_faces[group]);N/=np.linalg.norm(N);P=mesh.vertices[np.unique(mesh.faces[group])];C=P.mean(0)
    if abs(N@axis)<1e-4 and abs((C-point)@N)<radius*.65 and abs((P-C)@N).max()<=.0001:candidates+=1
   if candidates>=2:return True
  except (ValueError,IndexError,np.linalg.LinAlgError):continue
 return False
