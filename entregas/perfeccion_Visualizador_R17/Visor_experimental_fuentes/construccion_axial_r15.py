"""Build compact CAD directly from measured axial sections, before faceting.

Proposals use shared arc endpoints and exact source cap stations. They are never
accepted here: full cold CAD, original geometry, three fine meshes and original
material must pass in the isolated R15 worker. No filename-specific branch.
"""
import time
import numpy as np
import cadquery as cq
from perfiles_planos_r15 import sketch,circle


def marco_axial(mesh):
 N=np.asarray(mesh.face_normals);A=np.asarray(mesh.area_faces);positive=N.copy()
 dominant=np.argmax(abs(positive),axis=1);sign=np.sign(positive[np.arange(len(N)),dominant]);positive*=sign[:,None]
 keys,inverse=np.unique(np.round(positive,6),axis=0,return_inverse=True)
 weights=np.bincount(inverse,weights=A);index=int(weights.argmax())
 if weights[index]<mesh.area*.2:raise ValueError('La malla no tiene estaciones planas dominantes')
 # Quantization groups directions only; never use a quantized direction
 # as geometry. Recover the full-precision area-weighted source normal.
 family=inverse==index
 axis=np.average(positive[family],axis=0,weights=A[family]);axis=axis/np.linalg.norm(axis)
 # Canonical axes differing only by floating-point noise must retain the
 # same meridian; this snaps less than 1e-12 rad, below native CAD precision.
 main=int(np.argmax(abs(axis)))
 if np.linalg.norm(np.delete(axis,main))<1e-12:axis=np.eye(3)[main]*np.sign(axis[main])
 choice=int(np.flatnonzero(abs(axis)<=float(np.min(abs(axis)))+1e-12)[0])
 u=np.eye(3)[choice];u=u-axis*(u@axis);u=u/np.linalg.norm(u);v=np.cross(u,axis)
 return axis,u,v


def _construir_alineado(mesh):
 start=time.monotonic();axis,u,v=marco_axial(mesh)
 V=np.asarray(mesh.vertices);N=np.asarray(mesh.face_normals);C=mesh.triangles_center
 heights=V@axis;xy=np.c_[V@u,V@v]
 levels=[]
 for key in np.unique(np.round(C[abs(N@axis)>.999999]@axis,4)):
  ids=(abs(N@axis)>.999999)&(abs(C@axis-key)<.0001)
  if mesh.area_faces[ids].sum()>mesh.area*.002:levels.append(float(np.median(C[ids]@axis)))
 levels=sorted(set([float(heights.min()),float(heights.max())]+levels));print('[R15] Estaciones axiales',levels,flush=True)
 if not 2<=len(levels)<=8:raise ValueError('No hay una estructura axial acotada')
 profiles=[];holes=[];outer_specs=[]
 for lo,hi in zip(levels[:-1],levels[1:]):
  if hi-lo<.01:continue
  section=mesh.section(plane_origin=axis*((lo+hi)/2),plane_normal=axis)
  if section is None:raise ValueError('Sección axial vacía')
  paths=[np.c_[p@u,p@v] for p in section.discrete];paths.sort(key=lambda p:abs((p[:-1,0]*p[1:,1]-p[:-1,1]*p[1:,0]).sum()),reverse=True)
  wire,proof=sketch(paths[0],lambda p: u*p[0]+v*p[1]+axis*lo,tol=.002)
  outer_specs.append(dict(lo=lo,hi=hi,proof=proof,wire=wire));print('OUTER',lo,hi,proof['type'],len(wire.Edges()),flush=True)
  for p in paths[1:]:
   w,pr=sketch(p,lambda p:u*p[0]+v*p[1]+axis*lo,tol=.002)
   if pr['type']=='circle':
    center=np.array(pr['center']);found=next((h for h in holes if h['type']=='circle' and np.linalg.norm(h['center']-center)<.01 and abs(h['hi']-lo)<.0001),None)
    if found:found['hi']=hi;found['radii'].append(pr['nominal_radius'])
    else:holes.append(dict(type='circle',center=center,lo=lo,hi=hi,radii=[pr['nominal_radius']]))
   else:holes.append(dict(type='prism',wire=w,lo=lo,hi=hi,proof=pr))
 merged=[]
 for item in outer_specs:
  pr=item['proof']
  if merged and pr['type']=='circle' and merged[-1]['proof']['type']=='circle' and np.linalg.norm(np.array(pr['center'])-merged[-1]['proof']['center'])<.0001 and abs(pr['radius']-merged[-1]['proof']['radius'])<.0001:
   old=merged[-1];weight0=old['hi']-old['lo'];weight1=item['hi']-item['lo']
   old['proof']['radius']=float(np.sqrt((weight0*old['proof']['radius']**2+weight1*pr['radius']**2)/(weight0+weight1)));old['hi']=item['hi']
  else:merged.append(item)
 profiles=[]
 for item in merged:
  pr=item['proof'];lo=item['lo'];hi=item['hi']
  if pr['type']=='circle':
   center=np.array(pr['center']);w=cq.Wire.makeCircle(pr['radius'],cq.Vector(*(u*center[0]+v*center[1]+axis*lo)),cq.Vector(*axis))
  else:w=item['wire']
  profiles.append(cq.Solid.extrudeLinear(w,[],cq.Vector(*(axis*(hi-lo)))))
 body=profiles[0]
 for s in profiles[1:]:body=body.fuse(s)
 body=body.clean();print('BODY',len(body.Faces()),body.Volume(),flush=True)
 tools=[];records=[]
 for h in holes:
  if h['type']=='prism':
   tools.append(cq.Solid.extrudeLinear(h['wire'],[],cq.Vector(*(axis*(h['hi']-h['lo'])))));records.append(dict(type='prism',lo=h['lo'],hi=h['hi'],segments=len(h['wire'].Edges())));continue
  center=h['center'];R=max(h['radii']);minR=min(h['radii']);distance=np.linalg.norm(xy-center,axis=1)
  radial=C-(u*center[0]+v*center[1]);radial-=np.outer(radial@axis,axis);normaldot=np.sum(radial*N,axis=1)/np.maximum(np.linalg.norm(radial,axis=1),1e-20)
  mask=(C@axis>=h['lo']-1e-5)&(C@axis<=h['hi']+1e-5)&(normaldot<-.03)
  mask &= np.max(distance[mesh.faces],axis=1)<R+max(2.5,R*.2)
  mask &= np.min(distance[mesh.faces],axis=1)>max(0,minR-max(2.5,R*.2))
  cylmask=mask&(abs(N@axis)<1e-6)
  stable=np.unique(mesh.faces[np.flatnonzero(cylmask)])
  if len(stable)>=24:
   refined,_,error=circle(xy[stable])
   if error<3e-5:
    center=refined;distance=np.linalg.norm(xy-center,axis=1)
  mask=(C@axis>=h['lo']-1e-5)&(C@axis<=h['hi']+1e-5)&(normaldot< -1e-7)
  mask &= np.max(distance[mesh.faces],axis=1)<R+max(2.5,R*.2)
  mask &= np.min(distance[mesh.faces],axis=1)>max(0,minR-max(2.5,R*.2))
  import trimesh
  segments,faces=trimesh.intersections.mesh_plane(mesh,plane_normal=v,plane_origin=u*center[0]+v*center[1],return_faces=True)
  segments=segments[mask[faces]];points=segments.reshape(-1,3);rr=(points@u)-center[0];yy=points@axis
  keep=(rr>0)&(yy>=h['lo']-1e-5)&(yy<=h['hi']+1e-5)
  rr=rr[keep];yy=yy[keep];rows=[]
  for key in np.unique(np.round(yy,8)):
   match=abs(yy-key)<5.01e-9
   rows.append([float(np.median(yy[match])),float(np.mean(rr[match]))])
  print('[R15] Perfil medido',center.tolist(),len(points),len(rows),flush=True)
  rows=np.array(rows);rows=rows[np.argsort(rows[:,0])];print('HOLE',center.tolist(),'interval',h['lo'],h['hi'],'samples',len(rows),'r',rows[:,1].min(),rows[:,1].max(),flush=True)
  if len(rows)<2:raise ValueError('Missing profile levels')
  rows[0,0]=h['lo'];rows[-1,0]=h['hi']
  profile=np.vstack([[0,h['lo']],rows[:,[1,0]],[0,h['hi']]])
  def make_tool(bias=0,profile=profile.copy(),center=center.copy()):
   p=profile.copy();p[1:-1,0]+=bias
   w,proof=sketch(p,lambda p:u*(center[0]+p[0])+v*center[1]+axis*p[1],tol=.002,mandatory=[p[1],p[-2]])
   tool=cq.Solid.revolve(w,[],360,cq.Vector(*(u*center[0]+v*center[1])),cq.Vector(*(u*center[0]+v*center[1]+axis)))
   return tool,proof
  tool,proof=make_tool();tools.append(tool);records.append(dict(type='revolution',center=center.tolist(),lo=h['lo'],hi=h['hi'],samples=rows.tolist(),segments=len(tool.Faces())))
  if R>10:central=(len(tools)-1,make_tool)
 print('TOOLS',len(tools),[len(t.Faces()) for t in tools],flush=True)
 # Native cuts operate on a compact constructed body, not on 20,000 facets.
 shape=body
 for t in tools:shape=shape.cut(t)
 shape=shape.clean();print('CUT',len(shape.Faces()),shape.Volume(),'target',mesh.volume,shape.isValid(),flush=True)
 if 'central' in locals():
  index,make_tool=central;without=body
  for i,t in enumerate(tools):
   if i!=index:without=without.cut(t)
  def build(bias):return without.cut(make_tool(bias)[0]).clean()
  bias=0.;last_error=shape.Volume()-mesh.volume
  for iteration in range(4):
   probe=bias+.0001;check=build(probe);slope=(check.Volume()-shape.Volume())/.0001
   bias-=last_error/slope
   if not np.isfinite(bias) or abs(bias)>.008:raise ValueError('Volume correction exceeds source proposal limit')
   shape=build(bias);last_error=shape.Volume()-mesh.volume;print('VOLUME',bias,last_error,flush=True)
   if abs(last_error)<1e-6:break

 if len(shape.Solids())!=1 or not shape.isValid():raise ValueError('La construcción axial no produce un sólido válido')
 if len(shape.Faces())>1000:raise ValueError('La construcción axial no es compacta')
 return shape,dict(metodo='perfiles_axiales_del_STL',eje=axis.tolist(),estaciones_mm=levels,operaciones=records,
   correccion_radial_volumen_mm=float(bias) if 'central' in locals() else 0.,
   cota_propuesta_perfil_mm=.002,cota_propuesta_circulo_mm=.008,
   volumen_fuente=float(mesh.volume),volumen_cad=float(shape.Volume()),caras=len(shape.Faces()),
   segundos_construccion=time.monotonic()-start,limites_aceptacion_modificados=False)


def construir(mesh):
 axis,u,v=marco_axial(mesh)
 if np.max(abs(axis))>1-1e-12:
  return _construir_alineado(mesh)
 # Build Boolean operations in a true orthonormal local frame. Quantized or
 # oblique cap planes create microscopic cone caps and fragile joins.
 R=np.column_stack([u,axis,v]);origin=mesh.bounds.mean(0)
 local=mesh.copy();local.vertices=(mesh.vertices-origin)@R
 shape,proof=_construir_alineado(local)
 from OCP.gp import gp_Trsf
 T=np.eye(4);T[:3,:3]=R;T[:3,3]=origin
 transform=gp_Trsf();transform.SetValues(*[float(x) for x in T[:3,:].ravel()])
 shape=shape.transformShape(cq.Matrix(transform))
 proof['marco_local_a_STL']=T.tolist();proof['eje_STL']=axis.tolist()
 return shape,proof
