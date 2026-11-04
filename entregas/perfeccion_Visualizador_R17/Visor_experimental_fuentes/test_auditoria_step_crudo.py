"""Serialized STEP checks: a CAD reader alone can silently heal this fixture."""
from pathlib import Path
import re
import cadquery as cq
import pytest
from OCP.BRep import BRep_Tool
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from auditoria_step_crudo import (auditar_texto, auditar_archivo, _proponer_correccion,
                                  verificar_o_corregir_archivo, _inspect)
from exportacion_solida import exportar, ExportacionSolidaError
from calidad_topologica import leer_solido_step_estricto

FIXTURES = Path(__file__).parent / 'fixtures_cad/exportacion_cruda'
BAD = FIXTURES / 'occt79_toro_orientacion_incorrecta.step'
GOOD = FIXTURES / 'occt79_toro_correcto.step'


def test_reader_heals_but_serialized_incidence_detects_two_errors():
    shape = leer_solido_step_estricto(BAD)
    assert BRepCheck_Analyzer(shape.wrapped, True, False, True).IsValid()
    report = auditar_archivo(BAD)
    assert report['complete'] and not report['ok']
    assert len(report['shells'][0]['errors']) == 2


def test_exactly_one_flag_changes_no_geometry_or_other_bytes():
    text = BAD.read_text()
    fixed, bounds = _proponer_correccion(text)
    assert len(bounds) == 1 and len(fixed) == len(text)
    changes = [i for i, (a, b) in enumerate(zip(text, fixed)) if a != b]
    assert len(changes) == 1 and text[changes[0]] in 'TF' and fixed[changes[0]] in 'TF'
    assert auditar_texto(fixed)['ok']
    again, bounds = _proponer_correccion(fixed)
    assert again == fixed and bounds == []


def test_correct_files_remain_byte_identical(tmp_path):
    path = tmp_path / 'correct.step'; path.write_bytes(GOOD.read_bytes())
    report = verificar_o_corregir_archivo(path)
    assert report['ok'] and not report['modified']
    assert path.read_bytes() == GOOD.read_bytes()


def test_repair_preserves_windows_line_endings_and_every_other_byte(tmp_path):
    original = BAD.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    path = tmp_path / 'crlf.step'; path.write_bytes(original)
    report = verificar_o_corregir_archivo(path)
    fixed = path.read_bytes()
    assert report['modified'] and len(fixed) == len(original)
    assert sum(a != b for a, b in zip(original, fixed)) == 1
    assert original.count(b'\r\n') == fixed.count(b'\r\n')


def test_escaped_strings_and_comments_do_not_create_fake_entities():
    text = GOOD.read_text().replace("CLOSED_SHELL(''", "CLOSED_SHELL('name '' #999=CLOSED_SHELL(); ENDSEC;'")
    text = text.replace('DATA;', 'DATA; /* #16=OPEN_SHELL(); */')
    assert auditar_texto(text)['ok']


@pytest.mark.parametrize('text', ['', 'ISO-10303-21; DATA; ENDSEC; END-ISO-10303-21;', 'ISO-10303-21; DATA; #1=PLANE(); ENDSEC; END-ISO-10303-21;'])
def test_missing_topology_never_passes(text):
    try:
        report = auditar_texto(text)
    except ValueError:
        return
    assert not report['ok'] and not report['complete']


def test_duplicate_ids_are_rejected():
    text = GOOD.read_text().replace('ENDSEC;\nEND-ISO', '#16=CLOSED_SHELL(\'\',());\nENDSEC;\nEND-ISO')
    with pytest.raises(ValueError, match='duplicada'):
        auditar_texto(text)


def test_unsupported_loop_is_unknown_not_valid():
    text = GOOD.read_text().replace('EDGE_LOOP(', 'UNSUPPORTED_LOOP(', 1)
    report = auditar_texto(text)
    assert not report['complete'] and not report['ok']
    with pytest.raises(ValueError):
        _proponer_correccion(text)


def test_does_not_repair_arbitrary_orientations():
    text = GOOD.read_text()
    _, entities, _ = _inspect(text)
    # A plane boundary error must be rejected rather than generalized away.
    face = next(e for e in entities.values() if e.kind == 'ADVANCED_FACE' and entities[e.refs[-1]].kind == 'PLANE')
    bound = entities[face.refs[0]]; pos = bound.flag_position
    text = text[:pos] + ('.F.' if bound.orientation == 1 else '.T.') + text[pos+3:]
    assert not auditar_texto(text)['ok']
    with pytest.raises(ValueError):
        _proponer_correccion(text)


def shapes():
    yield 'box', cq.Workplane('XY').box(8, 9, 10).val()
    yield 'cylinder', cq.Solid.makeCylinder(4, 12)
    yield 'sphere', cq.Solid.makeSphere(5)
    yield 'cavity', cq.Workplane('XY').box(10, 10, 10).cut(cq.Workplane('XY').box(2, 2, 2)).val()
    for sign in [1, -1]:
        yield f'fillet_{sign}', cq.Workplane('XZ').moveTo(0, 0).lineTo(28, 0).lineTo(28, 60).lineTo(0, 60).close().revolve(360, (0, 0), (0, sign)).edges('>Z').fillet(.7).val()


@pytest.mark.parametrize('name,source', list(shapes()))
def test_real_exporter_preserves_solid_geometry_and_tolerances(tmp_path, name, source):
    before = [BRep_Tool.Tolerance_s(e.wrapped) for e in source.Edges()]
    path = tmp_path / f'{name}.step'
    record = exportar(source, path)
    assert record['auditoria_step_crudo']['ok'] and auditar_archivo(path)['ok']
    result = leer_solido_step_estricto(path)
    assert len(result.Faces()) == len(source.Faces())
    assert len(result.Shells()) == len(source.Shells())
    assert abs(source.Volume() - result.Volume()) < 1e-7
    assert abs(source.Area() - result.Area()) < 1e-7
    assert before == [BRep_Tool.Tolerance_s(e.wrapped) for e in source.Edges()]
    assert max(BRep_Tool.Tolerance_s(e.wrapped) for e in result.Edges()) <= max(before)
    a, b = source.BoundingBox(), result.BoundingBox()
    assert max(abs(getattr(a, k) - getattr(b, k)) for k in ('xmin', 'ymin', 'zmin', 'xmax', 'ymax', 'zmax')) < 1e-7
    # Interior/exterior, including the closed internal void and the torus rim.
    points = [(x, y, z) for x in (-6., -.5, 0., .5, 6., 27.5, 28.1)
              for y in (-6., 0., 6.) for z in (-6., 0., 6., 59.5, 60.1)]
    for point in points:
        states = [BRepClass3d_SolidClassifier(s.wrapped, gp_Pnt(*point), 1e-7).State() for s in (source, result)]
        assert states[0] == states[1]
    if name == 'fillet_-1':
        assert record['auditoria_step_crudo']['modified']
    else:
        assert not record['auditoria_step_crudo']['modified']


def test_atomic_export_cleans_temporary_on_raw_audit_failure(tmp_path, monkeypatch):
    import auditoria_step_crudo
    def fail(path):
        raise ValueError('fallo crudo inducido')
    monkeypatch.setattr(auditoria_step_crudo, 'verificar_o_corregir_archivo', fail)
    path = tmp_path / 'output.step'
    with pytest.raises(ExportacionSolidaError, match='fallo crudo'):
        exportar(cq.Solid.makeCylinder(3, 9), path)
    assert not path.exists() and not path.with_name(path.name + '.escribiendo.tmp').exists()


def test_two_independent_torus_writer_errors_in_one_connected_solid(tmp_path):
    cylinder=(cq.Workplane('XZ').moveTo(0,0).lineTo(10,0).lineTo(10,20).lineTo(0,20).close()
              .revolve(360,(0,0),(0,-1)).edges('>Z').fillet(.7).val())
    bridge=cq.Workplane().box(30,4,5).translate((0,0,5)).val()
    source=cylinder.translate((-15,0,0)).fuse(cylinder.translate((15,0,0)),bridge).clean()
    assert len(source.Solids())==1 and len(source.Shells())==1
    raw=tmp_path/'raw.step';cq.exporters.export(source,str(raw))
    audit=auditar_archivo(raw)
    assert len(audit['shells'][0]['errors'])==4
    path=tmp_path/'verified.step';record=exportar(source,path)
    assert len(record['auditoria_step_crudo']['corrected_bounds'])==2
    assert auditar_archivo(path)['ok']
    result=leer_solido_step_estricto(path)
    assert abs(result.Volume()-source.Volume())<1e-7
    assert abs(result.Area()-source.Area())<1e-7
    assert max(BRep_Tool.Tolerance_s(e.wrapped) for e in result.Edges())<=max(BRep_Tool.Tolerance_s(e.wrapped) for e in source.Edges())
