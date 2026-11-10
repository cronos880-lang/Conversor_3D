"""La normalización conserva la geometría y las uniones reales de la cónica."""
import sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'motor_superficies'))
import numpy as np
import cadquery as cq
from OCP.BRep import BRep_Builder,BRep_Tool
from OCP.TopoDS import TopoDS_Vertex,TopoDS_Edge,TopoDS_Wire,TopoDS_Face,TopoDS_Shell
from OCP.TopAbs import TopAbs_FORWARD,TopAbs_REVERSED
from OCP.Geom import Geom_Ellipse,Geom_SurfaceOfLinearExtrusion,Geom_Plane
from OCP.Geom2d import Geom2d_Line
from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir,gp_Pln,gp_Vec,gp_Pnt2d,gp_Dir2d
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
from OCP.BRepLib import BRepLib
from OCP.BRepCheck import BRepCheck_Analyzer
from contornos_periodicos import reunir_ciclos_analiticos,_mismo_soporte
from pcurvas_compartidas import crear_pcurva

def cilindro_eliptico(delta=2e-7):
    builder=BRep_Builder();curves=[Geom_Ellipse(gp_Ax2(gp_Pnt(0,0,z),gp_Dir(0,0,1)),3.,2.) for z in (0.,1.)]
    vertices=[]
    for curve in curves:
        pair=[]
        for t in (0.,delta):
            vertex=TopoDS_Vertex();builder.MakeVertex(vertex,curve.Value(t),1e-7);pair.append(vertex)
        vertices.append(pair)
    arcs=[]
    for k,curve in enumerate(curves):
        pair=[]
        for lo,hi,a,b in [(0.,delta,0,1),(delta,2*math.pi,1,0)]:
            edge=TopoDS_Edge();builder.MakeEdge(edge,curve,1e-7);builder.Add(edge,vertices[k][a].Oriented(TopAbs_FORWARD));builder.Add(edge,vertices[k][b].Oriented(TopAbs_REVERSED));builder.Range(edge,lo,hi);pair.append(edge)
        arcs.append(pair)
    from OCP.Geom import Geom_Line
    seam_curve=Geom_Line(gp_Pnt(3,0,0),gp_Dir(0,0,1));seam=TopoDS_Edge();builder.MakeEdge(seam,seam_curve,1e-7)
    builder.Add(seam,vertices[0][0].Oriented(TopAbs_FORWARD));builder.Add(seam,vertices[1][0].Oriented(TopAbs_REVERSED));builder.Range(seam,0.,1.)
    side=TopoDS_Face();surface=Geom_SurfaceOfLinearExtrusion(curves[0],gp_Dir(0,0,1));builder.MakeFace(side,surface,1e-7)
    for k in (0,1):
        for edge,(lo,hi) in zip(arcs[k],[(0.,delta),(delta,2*math.pi)]):
            uv=Geom2d_Line(gp_Pnt2d(0,k),gp_Dir2d(1,0));builder.UpdateEdge(edge,uv,side,1e-7);builder.Range(edge,side,lo,hi)
    builder.UpdateEdge(seam,Geom2d_Line(gp_Pnt2d(2*math.pi,0),gp_Dir2d(0,1)),Geom2d_Line(gp_Pnt2d(0,0),gp_Dir2d(0,1)),side,1e-7);builder.Range(seam,side,0.,1.)
    wire=TopoDS_Wire();builder.MakeWire(wire)
    for edge in [*arcs[0],seam,arcs[1][1].Reversed(),arcs[1][0].Reversed(),seam.Reversed()]:builder.Add(wire,edge)
    wire.Closed(True);builder.Add(side,wire);caps=[]
    for k in (0,1):
        plane=Geom_Plane(gp_Pln(gp_Pnt(0,0,k),gp_Dir(0,0,1)));face=TopoDS_Face();builder.MakeFace(face,plane,1e-7);wire=TopoDS_Wire();builder.MakeWire(wire)
        for edge,(lo,hi) in zip(arcs[k],[(0.,delta),(delta,2*math.pi)]):
            uv,_=crear_pcurva(curves[k],lo,hi,plane);builder.UpdateEdge(edge,uv,face,1e-7);builder.Range(edge,face,lo,hi);builder.Add(wire,edge)
        wire.Closed(True);builder.Add(face,wire);caps.append(face)
    for edge in [*arcs[0],*arcs[1],seam]:builder.SameRange(edge,True);builder.SameParameter(edge,True)
    shell=TopoDS_Shell();builder.MakeShell(shell)
    for face in [side,caps[0].Reversed(),caps[1]]:builder.Add(shell,face)
    shell.Closed(True);solid=BRepBuilderAPI_MakeSolid(shell).Solid();BRepLib.OrientClosedSolid_s(solid)
    return cq.Shape.cast(solid)

def test_ciclo_eliptico_con_microarco_conserva_solido_y_volumen():
    shape=cilindro_eliptico();assert BRepCheck_Analyzer(shape.wrapped,True,False,True).IsValid()
    result,proof=reunir_ciclos_analiticos(shape.wrapped);result=cq.Shape.cast(result)
    assert proof['ciclos_reunidos']==2 and len(result.Faces())==3 and len(result.Edges())==3
    assert BRepCheck_Analyzer(result.wrapped,True,False,True).IsValid()
    assert abs(result.Volume()-6*math.pi)<1e-9 and abs(result.Volume()-shape.Volume())<1e-9
    assert max(BRep_Tool.Tolerance_s(e.wrapped) for e in result.Edges())<=1e-7

def test_un_ciclo_ya_cerrado_no_se_reescribe():
    shape=cq.Workplane('XY').circle(2).extrude(1).val();result,proof=reunir_ciclos_analiticos(shape.wrapped)
    assert proof['ciclos_reunidos']==0 and result.IsSame(shape.wrapped)

def test_un_cuerpo_microscopico_independiente_no_desaparece():
    main=cilindro_eliptico();small=cq.Workplane('XY').box(1e-5,1e-5,1e-5).val().translate((20,0,0))
    compound=cq.Compound.makeCompound([main,small]);result,proof=reunir_ciclos_analiticos(compound.wrapped);result=cq.Shape.cast(result)
    assert len(result.Solids())==2 and len(result.Faces())==9
    before=sorted(s.Volume() for s in compound.Solids());after=sorted(s.Volume() for s in result.Solids())
    assert before[0]>0 and abs(after[0]/before[0]-1)<1e-8

def test_soportes_distintos_no_se_confunden_con_la_misma_elipse():
    p=np.zeros(3);n=np.array([0.,0.,1.]);x=np.array([1.,0.,0.]);base=(p,n,x,3.,2.)
    assert not _mismo_soporte(base,(p,n,x,3.001,2.))
    assert not _mismo_soporte(base,(p,n,np.array([0.,1.,0.]),3.,2.))
    assert not _mismo_soporte(base,(p+np.array([0,0,.001]),n,x,3.,2.))
