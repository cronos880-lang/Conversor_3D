import math
import cadquery as cq
import pytest
import trimesh
from OCP.BRepCheck import BRepCheck_Analyzer
from conversor3d.benchmarks import cases, generate, residual_box
from conversor3d.geometry import propose


@pytest.mark.parametrize('name', ['cylinder', 'rounded', 'thin_wall', 'small_hole',
                                  'freeform', 'rotated', 'residual_planes'])
def test_reference_has_known_material_and_topology(name):
    spec = cases()[name]
    shape = spec['shape']
    assert BRepCheck_Analyzer(shape.wrapped, True, False, True).IsValid()
    assert abs(shape.Volume() - spec['volume_mm3']) < 1e-7
    if 'void_point_mm' in spec:
        assert not shape.isInside(cq.Vector(*spec['void_point_mm']))
    vertices, triangles = shape.tessellate(.0005, .08)
    mesh = trimesh.Trimesh([p.toTuple() for p in vertices], triangles, process=True)
    assert mesh.is_watertight and mesh.euler_number == spec['euler']
    assert abs(abs(mesh.volume) - spec['volume_mm3']) / spec['volume_mm3'] < .005


@pytest.mark.parametrize('angle', [0., .61, 1.2])
def test_reconstruction_preserves_rigid_transform(angle, tmp_path):
    shape = residual_box().rotate((0, 0, 0), (1, 2, 3), angle * 180 / math.pi).translate((-200, 20, -10))
    baseline, candidate = tmp_path / 'base.step', tmp_path / 'candidate.step'
    cq.exporters.export(shape, str(baseline))
    report = propose(baseline, candidate)
    result = cq.importers.importStep(str(candidate)).val()
    assert report['faces_after'] == 6 and abs(result.Volume() - 48) < 1e-7
    assert report['protected_faces'] == 5


def test_manifest_distinguishes_reference_from_conversion(tmp_path):
    manifest = generate(tmp_path / 'catalog')
    assert len(manifest) == 7
    assert all('no conversión' in row['reference'] for row in manifest)
    with pytest.raises(FileExistsError):
        generate(tmp_path / 'catalog')
