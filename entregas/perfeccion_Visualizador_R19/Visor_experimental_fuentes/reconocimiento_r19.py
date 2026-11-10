"""Inventario CAD y regiones contiguas; sin reglas por archivo o coordenadas.

R18 reconstruye planos, cilindros y otras superficies desde el STL. Este módulo
analiza su resultado y sólo propone consolidar soportes ya demostrados.
"""
from collections import Counter
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
from OCP.gp import gp_Vec
from contratos_r19 import TOLERANCIA_COSTURA_MM, MAX_CARAS_CAD


def coplanares(a, b):
    sa, sb = BRepAdaptor_Surface(a.wrapped), BRepAdaptor_Surface(b.wrapped)
    if sa.GetType() != GeomAbs_Plane or sb.GetType() != GeomAbs_Plane:
        return False
    pa, pb = sa.Plane(), sb.Plane()
    na, nb = pa.Axis().Direction(), pb.Axis().Direction()
    if gp_Vec(na).Crossed(gp_Vec(nb)).Magnitude() > 1e-10:
        return False
    return pa.Distance(pb.Location()) <= TOLERANCIA_COSTURA_MM


def analizar(shape):
    faces = shape.Faces()
    types = [BRepAdaptor_Surface(f.wrapped).GetType() for f in faces]
    result = dict(caras=len(faces), tipos=dict(Counter(str(t).replace('GeomAbs_SurfaceType.', '') for t in types)),
                  presupuesto_admisible=len(faces) <= MAX_CARAS_CAD)
    if not result['presupuesto_admisible']:
        return result
    # Identidad topológica: dos aristas geométricamente cercanas no bastan.
    edges = {}
    for i, face in enumerate(faces):
        for edge in face.Edges():
            edges.setdefault(edge, []).append(i)
    adjacent = sorted({tuple(sorted((i, j))) for ids in edges.values() for i in ids for j in ids if i < j})
    result['adyacencias'] = len(adjacent)
    result['pares_planos_coplanares'] = [[i, j] for i, j in adjacent if coplanares(faces[i], faces[j])]
    from cilindros_contiguos import mismo_soporte
    result['pares_cilindricos'] = [[i, j] for i, j in adjacent
                                  if types[i] == types[j] == GeomAbs_Cylinder and mismo_soporte(faces[i], faces[j])]
    return result
