"""Construcción OCP de shells y sólidos; CadQuery sólo envuelve el resultado."""
import cadquery as cq
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepLib import BRepLib
from contratos_r19 import TOLERANCIA_COSTURA_MM


def inspeccionar(shape):
    return dict(solidos=len(shape.Solids()), shells=len(shape.Shells()), caras=len(shape.Faces()),
                cerrado=bool(shape.Shells()) and all(BRep_Tool.IsClosed_s(s.wrapped) for s in shape.Shells()),
                brep_exacto=bool(BRepCheck_Analyzer(shape.wrapped, True, False, True).IsValid()),
                volumen_mm3=float(shape.Volume()) if shape.Solids() else None)


def exigir_solido(shape):
    report = inspeccionar(shape)
    if report['solidos'] != 1 or report['shells'] != 1 or not report['cerrado'] or not report['brep_exacto'] or report['volumen_mm3'] <= 0:
        raise ValueError('No es un único sólido cerrado exacto válido: ' + str(report))
    # La conservación de cavidades, material e interferencias requiere además
    # los controles fríos originales; no se infiere de este chequeo estructural.
    return report


def coser_y_solidificar(faces):
    faces = list(faces)
    if not faces:
        raise ValueError('No hay caras para coser')
    sewing = BRepBuilderAPI_Sewing(TOLERANCIA_COSTURA_MM, True, True, True, False)
    for face in faces:
        sewing.Add(face.wrapped)
    sewing.Perform()
    shape = cq.Shape.cast(sewing.SewedShape())
    if sewing.NbFreeEdges() or sewing.NbMultipleEdges() or len(shape.Shells()) != 1:
        raise ValueError('Costura abierta, no manifold o con varios shells')
    maker = BRepBuilderAPI_MakeSolid(shape.Shells()[0].wrapped)
    if not maker.IsDone():
        raise ValueError('No se ha construido el sólido')
    solid = maker.Solid()
    if not BRepLib.OrientClosedSolid_s(solid):
        raise ValueError('No se puede orientar el sólido cerrado')
    result = cq.Shape.cast(solid)
    exigir_solido(result)
    return result
