"""Una curva común certificada también puede discurrir por soportes coincidentes."""
import numpy as np
from OCP.Geom import Geom_SurfaceOfLinearExtrusion

def proponer(sa,sb,points,closed):
 if not all(isinstance(s,Geom_SurfaceOfLinearExtrusion) for s in (sa,sb)):return None
 a=np.array(sa.Direction().Coord());b=np.array(sb.Direction().Coord())
 if np.linalg.norm(np.cross(a,b))>1e-10:return None
 from constructor_barridos import _sobre_superficie
 from proyector_perfil import ProyectorPerfil
 from geometria_medida import crear_pcurva,UV_KNOWN,registrar_uv
 try:
  curve,lo,hi=_sobre_superficie(sa,points,closed,ProyectorPerfil(sa))
  probes=np.array([curve.Value(float(t)).Coord() for t in np.linspace(lo,hi,33)]);error=float(np.linalg.norm(ProyectorPerfil(sb).batch(probes)-probes,axis=1).max())
  if error>2e-8:return None
  first,proof_a=crear_pcurva(curve,lo,hi,sa);second,proof_b=crear_pcurva(curve,lo,hi,sb)
  registrar_uv(curve,sa,first);registrar_uv(curve,sb,second)
  print('CONTORNO COMUN EN SOPORTES COINCIDENTES VERIFICADO',error,flush=True)
  return curve,lo,hi
 except Exception:return None
