"""Representar como planos las NURBS cuya coplanaridad completa está demostrada."""
import numpy as np
from OCP.Geom import Geom_BSplineSurface,Geom_BezierSurface,Geom_Plane
from OCP.gp import gp_Pln,gp_Pnt,gp_Dir,gp_Vec

def plano_demostrado(surface):
    if not isinstance(surface,(Geom_BSplineSurface,Geom_BezierSurface)):return None
    poles=[]
    for i in range(1,surface.NbUPoles()+1):
        for j in range(1,surface.NbVPoles()+1):
            if surface.Weight(i,j)<=0:return None
            poles.append(surface.Pole(i,j).Coord())
    points=np.asarray(poles);center=points.mean(0);_,singular,vt=np.linalg.svd(points-center,full_matrices=False)
    if len(singular)<3 or singular[1]<1e-12:return None
    normal=vt[-1]
    if np.abs((points-center)@normal).max()>1e-10:return None
    u0,u1,v0,v1=surface.Bounds();p=gp_Pnt();du=gp_Vec();dv=gp_Vec()
    surface.D1((u0+u1)*.5,(v0+v1)*.5,p,du,dv)
    direction=np.cross(du.Coord(),dv.Coord())
    if direction@normal<0:normal=-normal
    return Geom_Plane(gp_Pln(gp_Pnt(*map(float,center)),gp_Dir(*map(float,normal))))

def canonizar_planos(shape):
    import cadquery as cq
    from OCP.BRep import BRep_Tool,BRep_Builder
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopoDS import TopoDS,TopoDS_Face,TopoDS_Wire
    from OCP.TopAbs import TopAbs_FORWARD
    from OCP.ShapeBuild import ShapeBuild_ReShape
    from pcurvas_compartidas import crear_pcurva
    context=ShapeBuild_ReShape();builder=BRep_Builder();converted=0;removed=0
    for old_ in cq.Shape.cast(shape).Faces():
        old=TopoDS.Face_s(old_.wrapped.Oriented(TopAbs_FORWARD))
        if not old.Location().IsIdentity():continue
        original=BRep_Tool.Surface_s(old);plane=plano_demostrado(original)
        if plane is None:continue
        face=TopoDS_Face();builder.MakeFace(face,plane,1e-7)
        for old_wire in cq.Face(old).Wires():
            wire=TopoDS_Wire();builder.MakeWire(wire);exp=BRepTools_WireExplorer(old_wire.wrapped,old)
            while exp.More():
                edge=exp.Current();exp.Next()
                if BRep_Tool.Degenerated_s(edge):removed+=1;continue
                adaptor=BRepAdaptor_Curve(edge);first,last=adaptor.FirstParameter(),adaptor.LastParameter()
                curve=BRep_Tool.Curve_s(edge,first,last);uv,proof=crear_pcurva(curve,first,last,plane)
                builder.UpdateEdge(edge,uv,face,1e-7);builder.Range(edge,face,first,last)
                builder.UpdateEdge(edge,None,old,1e-7)
                builder.SameRange(edge,True);builder.SameParameter(edge,True)
                builder.Add(wire,edge)
            wire.Closed(True);builder.Add(face,wire)
        context.Replace(old,face);converted+=1
    return context.Apply(shape),{'caras_canonizadas':converted,'aristas_degeneradas_redundantes_retiradas':removed,
                                 'cota_coplanaridad_polos_mm':1e-10,'curvas3D_modificadas':False}
