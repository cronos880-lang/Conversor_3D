"""Conservar orientación y anidamiento de todas las componentes cerradas."""
import numpy as np

class InvariantesMaterial:
 def __init__(self,mesh):
  import trimesh
  self.faces=mesh.faces.copy();groups=list(trimesh.graph.connected_components(mesh.face_adjacency,nodes=np.arange(len(mesh.faces)),min_len=1));self.groups=[np.asarray(g,int) for g in groups];self.signs=[];self.positive=[];self.negative=[]
  for i,g in enumerate(self.groups):
   sign=1 if self.volumen(mesh.vertices,self.faces[g])>0 else -1;self.signs.append(sign);(self.positive if sign>0 else self.negative).append(i)
  if len(self.positive)!=1:raise ValueError('Se requiere exactamente una componente positiva; no se descartan cuerpos')
  self.body_faces=self.faces[self.groups[self.positive[0]]];self.probes=[int(self.faces[self.groups[i][0],0]) for i in self.negative]
  if not self.comprobar(mesh.vertices):raise ValueError('El material no presenta un anidamiento válido')
 @staticmethod
 def volumen(V,F):
  xyz=np.asarray(V[F],dtype=np.longdouble);origin=xyz.reshape(-1,3).mean(0);xyz=xyz-origin
  return np.sum(np.sum(xyz[:,0]*np.cross(xyz[:,1],xyz[:,2]),axis=1))/6
 def comprobar(self,V):
  import igl
  for g,sign in zip(self.groups,self.signs):
   if self.volumen(V,self.faces[g])*sign<=0:return False
  if self.probes:
   w=igl.winding_number(np.asarray(V,dtype=np.float64),self.body_faces,np.asarray(V[self.probes],dtype=np.float64))
   if not np.all(w>.75):return False
  return True
