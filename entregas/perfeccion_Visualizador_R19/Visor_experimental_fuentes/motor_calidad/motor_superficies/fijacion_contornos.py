"""Completar costuras y aristas degeneradas del B-Rep ya construido.

No recalcular las curvas compartidas verificadas ni retirar zonas pequeñas.
Una superficie triangular NURBS tiene un cuarto lado degenerado en su dominio;
ese lado debe figurar en el contorno UV aunque no mida nada en el espacio3D.
"""
from OCP.ShapeFix import ShapeFix_Shape,ShapeFix_Solid

def salto_numerico_certificado(surface,end,start,point,limite=5e-8):
    """Cota convexa de derivadas: todo el segmento UV coincide físicamente.

    Sólo soportes no racionales y segmento dentro de su dominio; sin sondeos
    usados como prueba de cota. El llamante exige además CAD exacto de la cara.
    """
    import numpy as np
    from OCP.Geom import Geom_BSplineSurface
    if not isinstance(surface,Geom_BSplineSurface) or surface.IsURational() or surface.IsVRational() or surface.IsUPeriodic() or surface.IsVPeriodic():return False
    a=np.array(end.Coord());b=np.array(start.Coord());u0,u1,v0,v1=surface.Bounds()
    eps=64*np.finfo(float).eps*max(1.,abs(u0),abs(u1),abs(v0),abs(v1))
    if min(a[0],b[0])<u0-eps or max(a[0],b[0])>u1+eps or min(a[1],b[1])<v0-eps or max(a[1],b[1])>v1+eps:return False
    original_a,original_b=a.copy(),b.copy()
    a=np.clip(a,[u0,v0],[u1,v1]);b=np.clip(b,[u0,v0],[u1,v1])
    P=np.array([[surface.Pole(i,j).Coord() for j in range(1,surface.NbVPoles()+1)] for i in range(1,surface.NbUPoles()+1)])
    bounds=[]
    for axis,degree in [(0,surface.UDegree()),(1,surface.VDegree())]:
        knot=surface.UKnot if axis==0 else surface.VKnot
        mult=surface.UMultiplicity if axis==0 else surface.VMultiplicity
        count=surface.NbUKnots() if axis==0 else surface.NbVKnots()
        knots=np.repeat([knot(i) for i in range(1,count+1)],[mult(i) for i in range(1,count+1)])
        controls=np.diff(P,axis=axis);den=np.array([knots[i+degree+1]-knots[i+1] for i in range(P.shape[axis]-1)])
        if np.any(den<=0):return False
        controls=controls*(degree/den).reshape((-1,1,1) if axis==0 else (1,-1,1))
        bounds.append(float(np.linalg.norm(controls,axis=2).max()))
    displacement=float(np.dot(np.abs(a-b),bounds))
    displacement+=surface.Value(*original_a).Distance(surface.Value(*a))+surface.Value(*original_b).Distance(surface.Value(*b))
    distance=surface.Value(*original_a).Distance(point)
    return bool(distance+displacement<=limite and surface.Value(*b).Distance(point)<=limite)


def completar_vertices_singulares(shape):
    """Cerrar sólo lados UV cuya imagen completa ya es un vértice existente."""
    import cadquery as cq
    from OCP.BRep import BRep_Builder,BRep_Tool
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.BRepAdaptor import BRepAdaptor_Curve2d
    from OCP.TopoDS import TopoDS_Edge,TopoDS_Wire,TopoDS
    from OCP.TopAbs import TopAbs_FORWARD,TopAbs_REVERSED
    from OCP.TopExp import TopExp
    from OCP.Geom import Geom_BSplineSurface
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.ShapeBuild import ShapeBuild_ReShape
    from pcurvas_compartidas import _lineal_uv
    context=ShapeBuild_ReShape();builder=BRep_Builder();added=0
    for face_ in cq.Shape.cast(shape).Faces():
        face=TopoDS.Face_s(face_.wrapped.Oriented(TopAbs_FORWARD));surface=BRep_Tool.Surface_s(face)
        if not isinstance(surface,Geom_BSplineSurface):continue
        u0,u1,v0,v1=surface.Bounds()
        for wire_ in cq.Face(face).Wires():
            wire=wire_.wrapped;explorer=BRepTools_WireExplorer(wire,face);edges=[]
            while explorer.More():edges.append(explorer.Current());explorer.Next()
            new=TopoDS_Wire();builder.MakeWire(new);changed=False
            for edge,following in zip(edges,edges[1:]+edges[:1]):
                builder.Add(new,edge)
                a=BRepAdaptor_Curve2d(edge,face);b=BRepAdaptor_Curve2d(following,face)
                end=a.Value(a.FirstParameter() if edge.Orientation()==TopAbs_REVERSED else a.LastParameter())
                start=b.Value(b.LastParameter() if following.Orientation()==TopAbs_REVERSED else b.FirstParameter())
                if end.Distance(start)<1e-9:continue
                vertex=TopExp.LastVertex_s(edge,True);next_vertex=TopExp.FirstVertex_s(following,True)
                if not vertex.IsSame(next_vertex):raise ValueError('El contorno no comparte un vértice3D; no se cierra.')
                point=BRep_Tool.Pnt_s(vertex);iso=None
                if BRepCheck_Analyzer(face,True,False,True).IsValid() and salto_numerico_certificado(surface,end,start,point):
                    continue
                for value in (u0,u1):
                    if max(abs(end.X()-value),abs(start.X()-value))<1e-10*max(1.,abs(u1-u0)):
                        iso=surface.UIso(value);break
                if iso is None:
                    for value in (v0,v1):
                        if max(abs(end.Y()-value),abs(start.Y()-value))<1e-10*max(1.,abs(v1-v0)):
                            iso=surface.VIso(value);break
                if iso is None or not hasattr(iso,'NbPoles') or any(
                        iso.Pole(i).Distance(point)>1e-8 or iso.Weight(i)<=0 for i in range(1,iso.NbPoles()+1)):
                    raise ValueError('El salto UV no es un vértice singular demostrado; no se cierra.')
                # Una NURBS de pesos positivos queda en la envolvente convexa
                # de sus polos: aquí toda su imagen coincide con ese vértice.
                zero=TopoDS_Edge();builder.MakeEdge(zero);builder.Degenerated(zero,True)
                uv=_lineal_uv(0.,1.,end.Coord(),start.Coord())
                builder.UpdateEdge(zero,uv,face,1e-7);builder.Range(zero,0.,1.);builder.Range(zero,face,0.,1.)
                builder.Add(zero,vertex.Oriented(TopAbs_FORWARD));builder.Add(zero,vertex.Oriented(TopAbs_REVERSED))
                builder.SameRange(zero,True);builder.SameParameter(zero,True)
                builder.Add(new,zero);added+=1;changed=True
            if changed:new.Closed(True);context.Replace(wire,new)
    return (context.Apply(shape) if added else shape),{'aristas_degeneradas_anadidas':added,
        'geometria3D_modificada':False,'cierre_solo_de_vertices_demostrados':True}

class AjusteContornos(ShapeFix_Shape):
    def __init__(self,shape):
        super().__init__(shape)
        self.FixSameParameterMode=0;self.FixVertexPositionMode=0;self.FixVertexTolMode=0
        face=self.FixFaceTool()
        face.FixWireMode=1;face.FixMissingSeamMode=1;face.FixOrientationMode=1
        face.FixSmallAreaWireMode=0;face.RemoveSmallAreaFaceMode=0
        face.FixIntersectingWiresMode=0;face.FixLoopWiresMode=0;face.AutoCorrectPrecisionMode=0
        wire=self.FixWireTool()
        wire.ModifyGeometryMode=False;wire.ModifyTopologyMode=True
        wire.FixReorderMode=1;wire.FixConnectedMode=1;wire.FixDegeneratedMode=1
        wire.FixEdgeCurvesMode=0;wire.FixSameParameterMode=0
        wire.FixSmallMode=0;wire.FixLackingMode=0;wire.FixSelfIntersectionMode=0
        wire.FixGaps2dMode=0;wire.FixGaps3dMode=0;wire.FixNotchedEdgesMode=0;wire.FixTailMode=0
        self.SetPrecision(1e-7);self.SetMaxTolerance(1e-5)
    def SetPrecision(self,value):super().SetPrecision(1e-7)
    def SetMaxTolerance(self,value):super().SetMaxTolerance(1e-5)

class OrientarSolido(ShapeFix_Solid):
    def __init__(self,solid):
        super().__init__(solid)
        self.FixShellMode=0;self.CreateOpenSolidMode=False
