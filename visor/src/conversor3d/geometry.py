"""Proponer planos de borde compartido sin modificar las caras analíticas."""
import hashlib
import io
from pathlib import Path

import cadquery as cq
import numpy as np
from scipy.optimize import linprog
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepTools import BRepTools, BRepTools_ReShape
from OCP.Geom import Geom_Plane, Geom_TrimmedCurve
from OCP.GeomAPI import GeomAPI_IntSS, GeomAPI_ProjectPointOnCurve
from OCP.GeomConvert import GeomConvert
from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
from OCP.ShapeAnalysis import ShapeAnalysis_CanonicalRecognition
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.TopTools import TopTools_FormatVersion_VERSION_3
from OCP.TopoDS import TopoDS_Face
from OCP.gp import gp_Pln, gp_Pnt, gp_Dir

BREP_MM = 1e-7
BORDER_MM = 5e-8
RECOGNITION_MM = 1e-4  # Propuesta exclusivamente; nunca tolerancia de aceptación.


def face_digest(face: cq.Face) -> str:
    stream = io.BytesIO()
    BRepTools.Write_s(face.wrapped, stream, False, False, TopTools_FormatVersion_VERSION_3)
    return hashlib.sha256(stream.getvalue()).hexdigest()


def curve_poles(edge: cq.Edge) -> np.ndarray:
    curve = BRep_Tool.Curve_s(edge.wrapped, 0., 0.)
    start, end = BRep_Tool.Range_s(edge.wrapped)
    spline = GeomConvert.CurveToBSplineCurve_s(Geom_TrimmedCurve(curve, start, end))
    if any(spline.Weight(i) <= 0 for i in range(1, spline.NbPoles() + 1)):
        raise ValueError('Curva racional sin envolvente de pesos positivos')
    return np.array([spline.Pole(i).Coord() for i in range(1, spline.NbPoles() + 1)])


def boundary_plane(face: cq.Face) -> tuple[Geom_Plane, dict]:
    """Ajuste minimax de la curva completa; no modifica sus puntos ni tolerancias."""
    seed = gp_Pln()
    recognizer = ShapeAnalysis_CanonicalRecognition(face.wrapped)
    if not recognizer.IsPlane(RECOGNITION_MM, seed) or recognizer.GetGap() > RECOGNITION_MM:
        raise ValueError('El soporte no propone un plano suficientemente próximo')
    poles = np.vstack([curve_poles(edge) for edge in face.Edges()])
    center = poles.mean(axis=0)
    normal = np.array(seed.Axis().Direction().Coord())
    u = np.cross(normal, np.eye(3)[np.argmin(abs(normal))])
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    local = poles - center
    matrix = np.c_[local @ u, local @ v, np.ones(len(local))]
    heights = local @ normal
    constraints = np.vstack((np.c_[matrix, -np.ones(len(matrix))],
                             np.c_[-matrix, -np.ones(len(matrix))]))
    fit = linprog([0., 0., 0., 1.], A_ub=constraints, b_ub=np.r_[heights, -heights],
                  bounds=[(-.1, .1), (-.1, .1), (None, None), (0, None)],
                  options={'primal_feasibility_tolerance': 1e-9,
                           'dual_feasibility_tolerance': 1e-9})
    if not fit.success:
        raise ValueError('No se obtiene un plano de borde factible')
    a, b, c, _ = fit.x
    axis = normal - a * u - b * v
    axis /= np.linalg.norm(axis)
    point = center + c * normal
    bound = float(abs((poles - point) @ axis).max())
    if not np.isfinite(bound) or bound > BORDER_MM:
        raise ValueError(f'El borde requiere {bound:.9g} mm; límite {BORDER_MM:g} mm')
    return Geom_Plane(gp_Pln(gp_Pnt(*point), gp_Dir(*axis))), {
        'boundary_hull_max_mm': bound, 'recognition_gap_mm': recognizer.GetGap(),
        'point_mm': point.tolist(), 'normal': axis.tolist()}


def check_intersections(face, surface, neighbors):
    """Contrasta intersecciones manteniendo fijas las aristas compartidas."""
    rows = []
    for edge, neighbor in neighbors:
        kind = BRepAdaptor_Surface(neighbor.wrapped).GetType()
        if kind not in (GeomAbs_Plane, GeomAbs_Cylinder):
            continue
        intersection = GeomAPI_IntSS(surface, BRep_Tool.Surface_s(neighbor.wrapped), BREP_MM)
        if not intersection.IsDone():
            raise ValueError('Intersección con vecino analítico no resuelta')
        if intersection.NbLines() == 0:
            # Planos coincidentes no determinan una única curva de corte.
            if kind != GeomAbs_Plane:
                raise ValueError('Intersección cilíndrica sin curva')
            plane = BRepAdaptor_Surface(neighbor.wrapped).Plane()
            if (abs(abs(surface.Pln().Axis().Direction().Dot(plane.Axis().Direction())) - 1) > 1e-10
                    or plane.Distance(surface.Location()) > BORDER_MM):
                raise ValueError('Planos sin intersección ni coincidencia certificada')
            rows.append({'coincident_planes': True})
            continue
        errors = []
        for t in np.linspace(0, 1, 9):
            point = gp_Pnt(*edge.positionAt(float(t)).toTuple())
            distances = []
            for i in range(1, intersection.NbLines() + 1):
                projected = GeomAPI_ProjectPointOnCurve(point, intersection.Line(i))
                if projected.NbPoints():
                    distances.append(projected.LowerDistance())
            if not distances:
                raise ValueError('No se puede contrastar la curva de intersección')
            errors.append(min(distances))
        if max(errors) > BREP_MM:
            raise ValueError('La intersección desplazaría el borde de una cara protegida')
        rows.append({'sampled_edge_to_intersection_max_mm': max(errors)})
    return rows


def propose(baseline: Path, destination: Path) -> dict:
    """Escribe un candidato nuevo. Su existencia no implica aprobación."""
    baseline, destination = Path(baseline), Path(destination)
    if destination.exists() or baseline.resolve() == destination.resolve():
        raise ValueError('La salida debe ser nueva e independiente')
    original_hash = hashlib.sha256(baseline.read_bytes()).hexdigest()
    original = cq.importers.importStep(str(baseline)).val()
    if len(original.Solids()) != 1 or not BRepCheck_Analyzer(original.wrapped, True, False, True).IsValid():
        raise ValueError('La referencia debe ser un sólido exacto válido')
    faces = original.Faces()
    protected = [f for f in faces if BRepAdaptor_Surface(f.wrapped).GetType()
                 in (GeomAbs_Plane, GeomAbs_Cylinder)]
    snapshots = [face_digest(f) for f in protected]
    edges = {}
    for i, face in enumerate(faces):
        for edge in face.Edges():
            edges.setdefault(edge, set()).add(i)
    context = BRepTools_ReShape()
    changed, created, rejections = [], [], []
    for index, face in enumerate(faces):
        if any(face.wrapped.IsSame(p.wrapped) for p in protected):
            continue
        try:
            surface, proof = boundary_plane(face)
            neighbors = [(edge, faces[j]) for edge in face.Edges()
                         for j in edges[edge] - {index}]
            proof['intersections'] = check_intersections(face, surface, neighbors)
            builder, replacement = BRep_Builder(), TopoDS_Face()
            builder.MakeFace(replacement, surface, BREP_MM)
            for wire in face.Wires():
                builder.Add(replacement, wire.wrapped)
            replacement.Orientation(face.wrapped.Orientation())
            if not BRepCheck_Analyzer(replacement, True, False, True).IsValid():
                raise ValueError('Cara propuesta no exacta válida')
            context.Replace(face.wrapped, replacement)
            created.append(cq.Face(replacement))
            changed.append({'face': index, **proof})
        except (ValueError, RuntimeError) as error:
            rejections.append({'face': index, 'reason': str(error)})
    result = cq.Shape.cast(context.Apply(original.wrapped)) if changed else original
    if changed:
        unifier = ShapeUpgrade_UnifySameDomain(result.wrapped, False, True, False)
        unifier.SetSafeInputMode(True)
        unifier.SetLinearTolerance(BREP_MM)
        unifier.SetAngularTolerance(1e-10)
        for face in result.Faces():
            if not any(face.wrapped.IsSame(new.wrapped) for new in created):
                for edge in face.Edges():
                    unifier.KeepShape(edge.wrapped)
        unifier.Build()
        result = cq.Shape.cast(unifier.Shape())
    for face, digest in zip(protected, snapshots):
        if (face_digest(face) != digest
                or not any(face.wrapped.IsSame(f.wrapped) for f in result.Faces())):
            raise ValueError('Cambió una cara analítica protegida')
    if not BRepCheck_Analyzer(result.wrapped, True, False, True).IsValid():
        raise ValueError('El candidato no es un B-Rep exacto válido')
    if max(BRep_Tool.Tolerance_s(e.wrapped) for e in result.Edges()) > BREP_MM:
        raise ValueError('El candidato aumenta las tolerancias B-Rep')
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != original_hash:
        raise ValueError('La referencia cambió durante la propuesta')
    cq.exporters.export(result, str(destination))
    return {'candidate': str(destination), 'baseline_sha256': original_hash,
            'candidate_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
            'faces_before': len(faces), 'faces_after': len(result.Faces()),
            'protected_faces': len(protected), 'changes': changed, 'rejections': rejections,
            'accepted': False, 'requires_full_validation': True}
