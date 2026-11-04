"""Prioridad a planos fuente certificados antes de medir perfiles curvos."""
import numpy as np
from OCP.Geom import Geom_Plane

def propuestas(result,mesh,limite=1e-4):
 import meshfit_brep as base
 out=[]
 for prim in result['primitives']:
  if prim['type']!='plane':continue
  surface=base._prim_surface(prim)
  if not isinstance(surface,Geom_Plane):continue
  n=np.array(surface.Axis().Direction().Coord());q=np.array(surface.Location().Coord());D=abs((mesh.vertices-q)@n);error=D[mesh.faces].max(1);mask=(error<=limite)&(abs(mesh.face_normals@n)>.9999);ids=np.flatnonzero(mask)
  if len(ids)<2 or mesh.area_faces[ids].sum()<.1:continue
  out.append((ids,surface))
 out.sort(key=lambda item:-float(mesh.area_faces[item[0]].sum()))
 print('PLANOS FUENTE PROTEGIDOS',len(out),'triangulos',len(np.unique(np.concatenate([ids for ids,s in out]))) if out else 0,flush=True)
 return out
