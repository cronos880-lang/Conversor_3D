"""Corregir sólo el sentido de los contornos; conservar geometría y tolerancias."""
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.ShapeFix import ShapeFix_Face
from OCP.BRep import BRep_Tool
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopoDS import TopoDS


def corregir(face):
    face=TopoDS.Face_s(face)
    if BRepCheck_Analyzer(face,True,False,True).IsValid():return face
    # FixOrientation sólo invierte wires, sin ejecutar reparación general.
    original=[];explorer=TopExp_Explorer(face,TopAbs_EDGE)
    while explorer.More():
        edge=TopoDS.Edge_s(explorer.Current())
        original.append((edge,BRep_Tool.Tolerance_s(edge)))
        explorer.Next()
    fix=ShapeFix_Face(face);fix.SetPrecision(1e-7);fix.SetMaxTolerance(1e-7)
    if not fix.FixOrientation():return face
    result=fix.Face()
    if not BRepCheck_Analyzer(result,True,False,True).IsValid():return face
    remaining=[];explorer=TopExp_Explorer(result,TopAbs_EDGE)
    while explorer.More():remaining.append(TopoDS.Edge_s(explorer.Current()));explorer.Next()
    if len(remaining)!=len(original):raise ValueError('La orientación ha cambiado el número de aristas')
    for edge,tolerance in original:
        if not any(edge.IsSame(other) for other in remaining):raise ValueError('La orientación ha sustituido una arista')
        if BRep_Tool.Tolerance_s(edge)!=tolerance:raise ValueError('La orientación ha alterado una tolerancia')
    if BRep_Tool.Surface_s(face)!=BRep_Tool.Surface_s(result):raise ValueError('La orientación ha sustituido el soporte')
    if face.Orientation()!=result.Orientation():raise ValueError('La orientación ha invertido la cara')
    return result
