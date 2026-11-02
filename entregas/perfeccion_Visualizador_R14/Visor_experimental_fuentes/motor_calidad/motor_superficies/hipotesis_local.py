"""Retirar una hipótesis nueva incompatible; no modificar límites de aceptación."""
class HipotesisIncompatible(ValueError):
 def __init__(self,regiones,vertice,motivo):
  super().__init__(motivo);self.regiones=list(map(int,regiones));self.vertice=int(vertice)


def soporte_libre_exacto(surface,points):
    """Cambiar la representación, conservando el soporte sobre el dominio fuente."""
    import numpy as np
    from OCP.Geom import Geom_RectangularTrimmedSurface
    from OCP.GeomConvert import GeomConvert
    from OCP.Geom import Geom_Plane,Geom_SurfaceOfLinearExtrusion
    from proyeccion_barridos import uv_exacta
    points=np.asarray(points)
    if isinstance(surface,Geom_Plane):
        pose=surface.Position();origin=np.array(pose.Location().Coord());x=np.array(pose.XDirection().Coord());y=np.array(pose.YDirection().Coord())
        uv=np.column_stack([(points-origin)@x,(points-origin)@y]);lo=uv.min(0)-.01;hi=uv.max(0)+.01
    elif isinstance(surface,Geom_SurfaceOfLinearExtrusion):
        uv=uv_exacta(surface,points);lo=uv.min(axis=0);hi=uv.max(axis=0)
        first=surface.BasisCurve().FirstParameter();last=surface.BasisCurve().LastParameter()
        lo[0]=max(first,lo[0]-1e-5);hi[0]=min(last,hi[0]+1e-5)
        lo[1]-=.01;hi[1]+=.01
    else:raise ValueError('Sólo se retiran perfiles propuestos o planos medidos, nunca cilindros confirmados')
    if np.any(hi<=lo):raise ValueError('Dominio libre degenerado')
    patch=GeomConvert.SurfaceToBSplineSurface_s(Geom_RectangularTrimmedSurface(surface,float(lo[0]),float(hi[0]),float(lo[1]),float(hi[1])))
    error=max(surface.Value(float(u),float(v)).Distance(patch.Value(float(u),float(v))) for u,v in uv)
    if error>1e-9:raise ValueError('La representación libre no conserva el soporte exacto')
    return patch
