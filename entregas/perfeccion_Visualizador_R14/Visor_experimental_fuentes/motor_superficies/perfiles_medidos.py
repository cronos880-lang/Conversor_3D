"""Investigación: familias de revolución y cilindros apoyadas en el STL."""
import numpy as np
from scipy.interpolate import make_interp_spline
from scipy.spatial import cKDTree
from OCP.Geom import Geom_CylindricalSurface,Geom_ToroidalSurface,Geom_SurfaceOfRevolution,Geom_BSplineSurface,Geom_BSplineCurve
from OCP.BRep import BRep_Tool
from OCP.BRepTools import BRepTools
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.TopAbs import TopAbs_IN,TopAbs_ON
from OCP.gp import gp_Pnt,gp_Dir,gp_Ax1,gp_Pnt2d
import meshfit_brep as base

def puntos_cara(face,surf):
 u0,u1,v0,v1=BRepTools.UVBounds_s(face.wrapped);points=[]
 for u in np.linspace(u0,u1,11):
  for v in np.linspace(v0,v1,11):
   if BRepClass_FaceClassifier(face.wrapped,gp_Pnt2d(float(u),float(v)),1e-9).State() in (TopAbs_IN,TopAbs_ON):points.append(surf.Value(float(u),float(v)).Coord())
 return np.asarray(points)

def proponer(faces,surfaces,mesh,required):
 from ajuste_cilindrico_medido import fit_native
 out=list(surfaces);records=[]
 # Refitar los cilindros desde vértices fuente antes de propagar sus soportes.
 cylinders=[s if isinstance(s,Geom_CylindricalSurface) else None for s in out]
 fitted,_=fit_native(faces,cylinders,mesh)
 for i,s in enumerate(fitted):
  if s is not None:out[i]=s
 trusted=[]
 for i,s in enumerate(out):
  if not isinstance(s,Geom_CylindricalSurface):continue
  a=np.array(s.Axis().Direction().Coord());q=np.array(s.Location().Coord())
  if any(abs(s.Radius()-r['radio'])<.008 and abs(a@r['eje'])>.99999 and np.linalg.norm(np.cross(q-r['centro'],a))<.008 for r in required):trusted.append((i,s))
 for i,s in enumerate(out):
  if not isinstance(s,Geom_BSplineSurface):continue
  P=puntos_cara(faces[i],s)
  if len(P)<16:continue
  choices=[]
  for ci,c in trusted:
   a=np.array(c.Axis().Direction().Coord());q=np.array(c.Location().Coord());error=float(abs(np.linalg.norm(np.cross(P-q,a),axis=1)-c.Radius()).max())
   if error<.015:choices.append((error,ci,c))
  if choices:
   error,ci,c=min(choices,key=lambda x:x[0]);out[i]=c;records.append(dict(tipo='cilindro_propagado',cara=i,soporte=ci,error_propuesta_mm=error));print('CILINDRO PROPAGADO',i,ci,error,flush=True)
 # Cada grupo requiere el eje de un cilindro confirmado por la fuente.
 used=set()
 for req in sorted(required,key=lambda r:r['max_entrada_mm']):
  a=np.array(req['eje'],float);a/=np.linalg.norm(a)
  if a[np.argmax(abs(a))]<0:a=-a
  q=np.array(req['centro'],float);target=[]
  for i,s in enumerate(out):
   if i in used or any(i==j or s is c for j,c in trusted):continue
   if not isinstance(s,(Geom_CylindricalSurface,Geom_ToroidalSurface)):continue
   direction=np.array(s.Axis().Direction().Coord());origin=np.array(s.Location().Coord())
   if abs(a@direction)>.99999 and np.linalg.norm(np.cross(origin-q,a))<.03:target.append(i)
  if len(target)<2 or not any(isinstance(out[i],Geom_ToroidalSurface) for i in target):continue
  C=mesh.triangles_center;support=[]
  for i in target:
   face=faces[i];s=out[i];bb=face.BoundingBox();pr=base._Proj(s)
   mask=np.all((C>=[bb.xmin-.025,bb.ymin-.025,bb.zmin-.025])&(C<=[bb.xmax+.025,bb.ymax+.025,bb.zmax+.025]),axis=1)
   ids=np.flatnonzero(mask);P=C[ids];err=np.linalg.norm(P-pr.batch(P),axis=1);normals=np.array([pr.normal(p) for p in P]);ndot=np.abs(np.sum(normals*mesh.face_normals[ids],axis=1));ids=ids[(err<.03)&(ndot>.97)]
   if mesh.area_faces[ids].sum()<.4*face.Area():raise ValueError('Falta apoyo fuente de una superficie de revolución propuesta')
   support.extend(ids)
  ids=np.unique(support);P=mesh.vertices[np.unique(mesh.faces[ids])];d=P-q;z=d@a;r=np.linalg.norm(np.cross(d,a),axis=1);levels=[]
  zr=np.round(z,5)
  for zz in np.unique(zr):
   mask=zr==zz
   if mask.sum()>=20:levels.append([np.median(z[mask]),np.median(r[mask]),np.ptp(r[mask]),mask.sum()])
  levels=np.array(levels)
  if len(levels)<8 or levels[:,2].max()>.002:raise ValueError('Perfil angularmente inconsistente')
  xy=levels[:,:2];steps=np.linalg.norm(np.diff(xy,axis=0),axis=1)
  # Los segmentos muy largos reciben testigos interiores para evitar oscilación.
  densified=[]
  for p0,p1,h in zip(xy[:-1],xy[1:],steps):
   densified.extend(p0+t*(p1-p0) for t in np.linspace(0,1,max(2,int(np.ceil(h/.15))+1))[:-1])
  densified.append(xy[-1]);xy=np.array(densified);t=np.r_[0.,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
  first=xy[1]-xy[0];first/=np.linalg.norm(first);last=xy[-1]-xy[-2];last/=np.linalg.norm(last)
  if abs(last[0])<.02:last=np.array([0.,np.sign(last[1])])
  # La dirección final se estima del perfil; no se impone un radio nominal.
  spline=make_interp_spline(t,xy,k=3,bc_type=([(1,first)],[(1,last)]))
  grid=spline(np.linspace(t[0],t[-1],20001));dist,_=cKDTree(grid).query(np.c_[z,r]);maximum=float(dist.max())
  if maximum>.003:raise ValueError(f'El perfil medido no conserva la fuente: {maximum}')
  helper=np.eye(3)[np.argmin(abs(a))];u=np.cross(a,helper);u/=np.linalg.norm(u)
  from OCP.TColgp import TColgp_Array1OfPnt
  from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
  poles=TColgp_Array1OfPnt(1,len(spline.c));knots,mults=np.unique(spline.t,return_counts=True);K=TColStd_Array1OfReal(1,len(knots));M=TColStd_Array1OfInteger(1,len(knots))
  for j,p in enumerate(spline.c,1):poles.SetValue(j,gp_Pnt(*map(float,q+a*p[0]+u*p[1])))
  for j,(k,m) in enumerate(zip(knots,mults),1):K.SetValue(j,float(k));M.SetValue(j,int(m))
  curve=Geom_BSplineCurve(poles,K,M,3,False);surface=Geom_SurfaceOfRevolution(curve,gp_Ax1(gp_Pnt(*map(float,q)),gp_Dir(*map(float,a))))
  for i in target:out[i]=surface;used.add(i)
  records.append(dict(tipo='revolucion_medida',caras=target,vertices_fuente=len(P),niveles=len(levels),max_fuente_mm=maximum,indices_fuente=ids.tolist()));print('REVOLUCION MEDIDA',{k:v for k,v in records[-1].items() if k!='indices_fuente'},flush=True)
 return out,records
