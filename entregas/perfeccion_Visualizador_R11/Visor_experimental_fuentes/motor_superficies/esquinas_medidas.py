"""No extrapolar planos casi tangentes para inventar esquinas fuera del STL."""
import numpy as np
from OCP.Geom import Geom_Plane,Geom_SurfaceOfLinearExtrusion

def separar_conflictos(mesh,labels,surfaces,primary,groups,max_move):
 if not any(isinstance(s,Geom_SurfaceOfLinearExtrusion) for s in surfaces.values()):return []
 incidence={}
 for tri,region in zip(mesh.faces,labels):
  for v in tri:incidence.setdefault(int(v),set()).add(int(region))
 areas={r:float(mesh.area_faces[ids].sum()) for r,ids in groups.items()};records=[]
 for iteration in range(48):
  conflict=None
  for vertex,regions in incidence.items():
   native=[r for r in regions if r in primary and not isinstance(surfaces[r],Geom_SurfaceOfLinearExtrusion)]
   if len(native)<2 or any(not isinstance(surfaces[r],Geom_Plane) for r in native):continue
   normals=np.array([surfaces[r].Axis().Direction().Coord() for r in native]);origins=np.array([surfaces[r].Location().Coord() for r in native]);p=mesh.vertices[vertex]
   initial=np.sum((p-origins)*normals,axis=1);delta=np.linalg.lstsq(normals,-initial,rcond=1e-12)[0];residual=float(abs(normals@delta+initial).max());move=float(np.linalg.norm(delta))
   if residual<=2e-7 and move<=max_move:continue
   candidates=[r for i,r in enumerate(native) if any(i!=j and abs(normals[i]@normals[j])>np.cos(np.radians(5)) for j in range(len(native)))]
   if not candidates:continue
   region=min(candidates,key=lambda r:areas[r]);conflict=dict(vertice=vertex,region=region,area=areas[region],movimiento_evitable_mm=move,residual_mm=residual);break
  if conflict is None:return records
  primary.remove(conflict['region']);records.append(conflict);print('ESQUINA MEDIDA: PARCHE LOCAL',conflict,flush=True)
 raise ValueError('Demasiadas esquinas planas incompatibles para el presupuesto local')
