"""Una hipótesis sólo añade un cilindro tras certificar triángulos fuente completos."""
import numpy as np
from OCP.BRep import BRep_Tool
from OCP.Geom import Geom_CylindricalSurface
from extension_cilindros import propuestas

def confirmar(faces,mesh,required):
 out=list(required);proof=[]
 for i,face in enumerate(faces):
  s=BRep_Tool.Surface_s(face.wrapped)
  if not isinstance(s,Geom_CylindricalSurface):continue
  a=np.array(s.Axis().Direction().Coord());q=np.array(s.Location().Coord());radius=float(s.Radius())
  if any(abs(radius-r['radio'])<1e-6 and abs(a@r['eje'])>1-1e-10 and np.linalg.norm(np.cross(q-r['centro'],a))<1e-6 for r in out):continue
  req=dict(eje=a,centro=q,radio=radius,puntos=np.empty((0,3)))
  ids,_=propuestas(mesh,[req],tol=.001)[0];bb=face.BoundingBox();C=mesh.triangles_center[ids]
  ids=ids[np.all((C>=np.array([bb.xmin,bb.ymin,bb.zmin])-.001)&(C<=np.array([bb.xmax,bb.ymax,bb.zmax])+.001),axis=1)]
  ids=ids[abs(mesh.face_normals[ids]@a)<.005]
  if len(ids)<12 or mesh.area_faces[ids].sum()<max(.5*face.Area(),float(mesh.area_faces.sum())*1e-4):continue
  V=mesh.vertices[np.unique(mesh.faces[ids])]-q;helper=np.eye(3)[np.argmin(abs(a))];u=np.cross(a,helper);u/=np.linalg.norm(u);v=np.cross(a,u)
  angles=np.sort(np.arctan2(V@v,V@u));coverage=2*np.pi-float(np.diff(np.r_[angles,angles[0]+2*np.pi]).max())
  if coverage<np.pi/12:continue
  points=np.vstack([mesh.vertices[np.unique(mesh.faces[ids])],mesh.triangles_center[ids]])
  error=float(abs(np.linalg.norm(np.cross(points-q,a),axis=1)-radius).max())
  if error>.001:continue
  req.update(puntos=points,max_entrada_mm=error);out.append(req)
  proof.append(dict(cara_hipotesis=i,triangulos=int(len(ids)),area_fuente_mm2=float(mesh.area_faces[ids].sum()),radio=radius,max_testigos_mm=error,cota_triangulos_mm=.001))
  print('CILINDRO GUIADO CERTIFICADO',proof[-1],flush=True)
 return out,proof
