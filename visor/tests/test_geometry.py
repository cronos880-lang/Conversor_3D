from pathlib import Path
import json
import cadquery as cq
import numpy as np
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.gp import gp_Pnt
from OCP.Geom import Geom_BezierSurface
from OCP.GeomConvert import GeomConvert
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_Sewing
from OCP.BRepCheck import BRepCheck_Analyzer
from conversor3d.geometry import propose, curve_poles


def residual_box():
    faces = [f for f in cq.Solid.makeBox(6, 4, 2).Faces() if f.Center().z < 1.99]
    for x in range(6):
        poles = TColgp_Array2OfPnt(1, 2, 1, 2)
        for i, xx in enumerate((x, x + 1), 1):
            for j, yy in enumerate((0, 4), 1):
                poles.SetValue(i, j, gp_Pnt(xx, yy, 2))
        surf = GeomConvert.SurfaceToBSplineSurface_s(Geom_BezierSurface(poles))
        faces.append(cq.Face(BRepBuilderAPI_MakeFace(surf, 1e-7).Face()))
    sew = BRepBuilderAPI_Sewing(1e-7)
    for face in faces:
        sew.Add(face.wrapped)
    sew.Perform()
    return cq.Solid.makeSolid(cq.Shape.cast(sew.SewedShape()))


def test_shared_boundaries_reduce_residual_faces(tmp_path):
    original = residual_box()
    source, target = tmp_path / 'base.step', tmp_path / 'candidate.step'
    cq.exporters.export(original, str(source))
    before = source.read_bytes()
    result = propose(source, target)
    shape = cq.importers.importStep(str(target)).val()
    assert result['faces_before'] == 11 and result['faces_after'] == 6
    assert result['protected_faces'] == 5 and len(result['changes']) == 6
    assert BRepCheck_Analyzer(shape.wrapped, True, False, True).IsValid()
    assert abs(shape.Volume() - 48) < 1e-8 and source.read_bytes() == before
    assert result['accepted'] is False and result['requires_full_validation']


def test_boundary_check_covers_arc_interior():
    edge = cq.Edge.makeThreePointArc(cq.Vector(0, 0, 0), cq.Vector(.5, 0, 1), cq.Vector(1, 0, 0))
    assert abs(edge.startPoint().z) < 1e-12 and abs(edge.endPoint().z) < 1e-12
    assert abs(curve_poles(edge)[:, 2]).max() >= 1


def test_new_proposer_passes_original_full_validation(tmp_path):
    import trimesh
    from conversor3d.legacy import run_worker
    shape = residual_box()
    baseline, candidate, source = (tmp_path / name for name in ('base.step', 'candidate.step', 'source.stl'))
    cq.exporters.export(shape, str(baseline))
    vertices, triangles = shape.tessellate(.00025, .04)
    mesh = trimesh.Trimesh([p.toTuple() for p in vertices], triangles, process=True)
    mesh.fix_normals()
    mesh.subdivide().export(source)
    propose(baseline, candidate)
    assessed = run_worker({'action': 'assess_baseline', 'source': str(source),
                           'baseline': str(baseline)}, tmp_path / 'assess')
    spec = tmp_path / 'baseline.json'
    spec.write_text(json.dumps(assessed['value']))
    evidence = tmp_path / 'validation'
    validated = run_worker({'action': 'validate_candidate', 'source': str(source),
                            'candidate': str(candidate), 'baseline': str(baseline),
                            'baseline_run': str(spec), 'evidence': str(evidence)}, evidence)
    approval = validated['value']
    assert approval['accepted'] and approval['validated']
    assert approval['calidad']['caras_step'] == 6
    assert approval['calidad']['integridad_cad']['tolerancia_max_mm'] == 1e-7
    assert approval['final_validation']['material_original']['discrepancias'] == 0
    assert approval['contraste_comun']['regresiones_sobre_00001_mm'] == 0
