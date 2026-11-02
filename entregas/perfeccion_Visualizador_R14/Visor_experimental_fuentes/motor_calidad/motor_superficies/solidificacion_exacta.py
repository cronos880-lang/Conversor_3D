"""Orientar caras existentes y crear sólido sin reconstruir su geometría."""
import cadquery as cq
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.ShapeFix import ShapeFix_Shell
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
from OCP.BRepLib import BRepLib
from OCP.BRep import BRep_Tool
from OCP.TopTools import TopTools_IndexedMapOfShape


def solidificar(shape):
    original=cq.Shape.cast(shape);shells=original.Shells()
    if len(shells)!=1 or not BRepCheck_Analyzer(shape,True,False,True).IsValid():
        raise ValueError('Se requiere un único shell CAD exacto')
    before=original.Faces();edge_data=[(e.wrapped,BRep_Tool.Tolerance_s(e.wrapped)) for e in original.Edges()]
    fix=ShapeFix_Shell();fix.FixFaceOrientation(shells[0].wrapped,True,False)
    oriented=fix.Shell();after=cq.Shape.cast(oriented)
    if len(after.Shells())!=1 or len(after.Faces())!=len(before):raise ValueError('La orientación ha dividido el shell')
    # TopTools uses exact TShape+Location identity (IsSame), including hash
    # collision resolution. Re-enumerating/searching every face for every
    # original face was quadratic on dense solids; this has identical meaning.
    after_faces=after.Faces();face_index=TopTools_IndexedMapOfShape()
    for face in after_faces:face_index.Add(face.wrapped)
    if not all(face_index.Contains(f.wrapped) for f in before):
        raise ValueError('La orientación ha sustituido una cara')
    result=BRepBuilderAPI_MakeSolid(oriented).Solid();BRepLib.OrientClosedSolid_s(result)
    if not BRepCheck_Analyzer(result,True,False,True).IsValid():raise ValueError('El shell no forma un sólido exacto orientable')
    final=cq.Shape.cast(result)
    if len(final.Solids())!=1:raise ValueError('No se conserva un único sólido')
    edges=final.Edges()
    if len(edges)!=len(edge_data):raise ValueError('La orientación cambia las aristas')
    edge_index=TopTools_IndexedMapOfShape()
    for other in edges:edge_index.Add(other.wrapped)
    for edge,tolerance in edge_data:
        if not edge_index.Contains(edge) or BRep_Tool.Tolerance_s(edge)!=tolerance:
            raise ValueError('La orientación modifica una arista o su tolerancia')
    return result
