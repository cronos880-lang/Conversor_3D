"""Subdividir una arista del mallado de propuesta sin dejar uniones en T."""
import numpy as np
import trimesh
class RefinarArista(ValueError):
 def __init__(self,vertices,points):
  super().__init__('La curva requiere separar sus tramos polinómicos.');self.vertices=vertices;self.points=points

def dividir(mesh,labels,vertices,points,limite=.003):
 a,b=map(int,vertices);A,B=mesh.vertices[[a,b]];D=B-A;den=float(D@D)
 if den<1e-14:raise ValueError('Arista demasiado pequeña para refinar')
 rows=[]
 for point in points:
  t=float((point-A)@D/den);distance=float(np.linalg.norm(point-(A+t*D)))
  if not 1e-8<t<1-1e-8 or distance>limite:raise ValueError('La subdivisión abandona la arista fuente acotada')
  rows.append((t,np.asarray(point),distance))
 rows.sort(key=lambda r:r[0]);V=list(mesh.vertices);chain=[a]
 for t,p,d in rows:chain.append(len(V));V.append(p)
 chain.append(b);F=[];L=[];count=0
 for tri,label in zip(mesh.faces,labels):
  if a not in tri or b not in tri:F.append(tri);L.append(label);continue
  count+=1
  # Conservar la orientación de ambos triángulos incidentes.
  index=next(j for j in range(3) if {int(tri[j]),int(tri[(j+1)%3])}=={a,b});order=chain if tri[index]==a else chain[::-1];opposite=int(tri[(index+2)%3])
  for x,y in zip(order[:-1],order[1:]):F.append([x,y,opposite]);L.append(label)
 if count!=2:raise ValueError('La subdivisión exige una arista manifold compartida')
 result=trimesh.Trimesh(np.asarray(V),np.asarray(F),process=False)
 if not result.is_watertight or not result.is_winding_consistent or result.euler_number!=mesh.euler_number:raise ValueError('La subdivisión no conserva la topología fuente')
 return result,np.asarray(L,dtype=labels.dtype),dict(vertices_nuevos=len(rows),max_distancia_arista_mm=max(r[2] for r in rows))
