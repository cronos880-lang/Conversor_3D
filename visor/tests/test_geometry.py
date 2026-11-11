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


from conversor3d.benchmarks import residual_box


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
    from conversor3d.validation import evaluate
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
    decision = evaluate(source, baseline, spec, candidate, evidence)
    approval = decision['validation']
    assert approval['accepted'] and approval['validated']
    assert approval['calidad']['caras_step'] == 6
    from conversor3d.pipeline import certify_selection
    reused, hit = certify_selection(decision, source, candidate, spec, tmp_path / 'unused-final')
    assert hit and reused['record']['ok']
    assert not (tmp_path / 'unused-final').exists()
    assert approval['calidad']['integridad_cad']['tolerancia_max_mm'] == 1e-7
    assert approval['final_validation']['material_original']['discrepancias'] == 0
    assert approval['contraste_comun']['regresiones_sobre_00001_mm'] == 0


def test_shared_boundaries_keep_small_cylindrical_hole(tmp_path):
    import trimesh
    from conversor3d.legacy import run_worker
    from conversor3d.validation import evaluate
    original = residual_box().cut(cq.Solid.makeCylinder(.3, 2, cq.Vector(3.2, 2, 0)))
    baseline, candidate, source = (tmp_path / name for name in ('base.step', 'candidate.step', 'source.stl'))
    cq.exporters.export(original, str(baseline))
    vertices, triangles = original.tessellate(.00025, .04)
    mesh = trimesh.Trimesh([p.toTuple() for p in vertices], triangles, process=True)
    mesh.fix_normals(); mesh.export(source)
    proposed = propose(baseline, candidate)
    assert proposed['faces_after'] < proposed['faces_before'] - 4
    result = cq.importers.importStep(str(candidate)).val()
    assert not result.isInside(cq.Vector(3.2, 2, 1))
    assessed = run_worker({'action': 'assess_baseline', 'source': str(source),
                           'baseline': str(baseline)}, tmp_path / 'assess')
    spec = tmp_path / 'baseline.json'; spec.write_text(json.dumps(assessed['value']))
    evidence = tmp_path / 'validation'
    approval = evaluate(source, baseline, spec, candidate, evidence)['validation']
    assert approval['accepted'] and approval['cilindros']
    assert approval['final_validation']['material_original']['discrepancias'] == 0
    assert approval['contraste_comun']['regresiones_sobre_00001_mm'] == 0
