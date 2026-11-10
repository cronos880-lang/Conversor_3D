"""Contratos CAD reales, exportación, geometría y reversión del pipeline R19."""
from pathlib import Path
import json
import os
import subprocess
import sys
import cadquery as cq
import numpy as np
import pytest
import trimesh
from contratos_r19 import ROOT, sha
from topologia_r19 import coser_y_solidificar, exigir_solido
from exportacion_r19 import exportar
from ingesta_r19 import evaluar
from optimizacion_r19 import construir
from reconocimiento_r19 import coplanares


def caja_fragmentada():
    mesh = trimesh.creation.box(extents=[4, 5, 6])
    faces = [cq.Face.makeFromWires(cq.Wire.makePolygon([cq.Vector(*p) for p in triangle], close=True))
             for triangle in mesh.triangles]
    return coser_y_solidificar(faces), mesh


def cuerpo_con_planos_y_costura():
    shape = cq.Solid.makeBox(2, 4, 2)
    for x in (2, 4):
        shape = shape.fuse(cq.Solid.makeBox(2, 4, 2, cq.Vector(x, 0, 0)))
    half = cq.Solid.makeCylinder(.5, 2, cq.Vector(5, 2, 0), cq.Vector(0, 0, 1), 180)
    return shape.cut(half).cut(half.rotate((5, 2, 0), (5, 2, 1), 180))


def test_ingesta_no_confunde_malla_cerrada_con_solido_y_no_repara_aberturas(tmp_path):
    mesh = trimesh.creation.box()
    source = tmp_path / 'entrada.stl'
    mesh.export(source)
    before = sha(source)
    report = evaluar(source)
    assert report['cerrado'] and report['orientado'] and report['triangulos_ocp'] == 12
    assert report['original_sha256'] == before == sha(source)
    mesh.update_faces(np.arange(2, len(mesh.faces)))
    mesh.export(tmp_path / 'abierto.stl')
    report = evaluar(tmp_path / 'abierto.stl')
    assert not report['cerrado'] and report['aristas_abiertas'] > 0 and not report['optimizacion_admisible']


def test_cosido_no_fuerza_cierre_ni_mezcla_cuerpos():
    box = cq.Solid.makeBox(2, 3, 4)
    with pytest.raises(ValueError, match='abierta'):
        coser_y_solidificar(box.Faces()[:-1])
    second = box.translate((10, 0, 0))
    with pytest.raises(ValueError, match='shells'):
        coser_y_solidificar(box.Faces() + second.Faces())


@pytest.mark.parametrize('backend', ['ocp', 'cadquery'])
def test_step_serializado_reimporta_solido_y_taladro(tmp_path, backend):
    shape = cq.Solid.makeBox(6, 4, 2).cut(cq.Solid.makeCylinder(.5, 2, cq.Vector(3, 2, 0)))
    reread, report = exportar(shape, tmp_path / 'salida.step', backend=backend)
    assert report['reimportado'] and exigir_solido(reread)['brep_exacto']
    assert abs(shape.Volume() - reread.Volume()) < 1e-7
    assert not reread.isInside(cq.Vector(3, 2, 1))
    assert reread.isInside(cq.Vector(1, 1, 1))
    before = (tmp_path / 'salida.step').read_bytes()
    with pytest.raises(ValueError, match='sobrescribe'):
        exportar(shape, tmp_path / 'salida.step', backend=backend)
    assert (tmp_path / 'salida.step').read_bytes() == before


def test_normales_paralelas_no_justifican_fusionar_planos_desplazados():
    a = cq.Face.makePlane(2, 2)
    b = a.translate((0, 0, .001))
    assert not coplanares(a, b)
    assert coplanares(a, a)


def test_consolidacion_planar_conserva_volumen_y_original(tmp_path):
    shape, mesh = caja_fragmentada()
    assert len(shape.Faces()) == 12
    source = tmp_path / 'referencia.step'
    exportar(shape, source)
    before = sha(source)
    candidate, _ = construir(source, tmp_path / 'planos', 'planos')
    rebuilt = cq.importers.importStep(str(candidate)).val()
    assert len(rebuilt.Faces()) == 6 and abs(rebuilt.Volume() - 120) < 1e-8
    assert sha(source) == before


def test_consolidacion_planar_protege_caras_y_costuras_cilindricas(tmp_path):
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    shape = cuerpo_con_planos_y_costura()
    def cylinders(s):
        return [f for f in s.Faces() if BRepAdaptor_Surface(f.wrapped).GetType() == GeomAbs_Cylinder]
    assert len(cylinders(shape)) == 2
    source = tmp_path / 'referencia.step'
    exportar(shape, source)
    candidate, _ = construir(source, tmp_path / 'planos', 'planos')
    rebuilt = cq.importers.importStep(str(candidate)).val()
    assert len(rebuilt.Faces()) < len(shape.Faces())
    assert len(cylinders(rebuilt)) == 2
    assert abs(sum(f.Area() for f in cylinders(shape)) - sum(f.Area() for f in cylinders(rebuilt))) < 1e-7
    assert abs(shape.Volume() - rebuilt.Volume()) < 1e-7


def test_planos_sin_cilindros_superan_control_frio_original(tmp_path, monkeypatch):
    from contratos_r19 import escribir_json
    from motor_v2 import _calidad
    from preprocesador_stl import cargar_exacto
    from validacion_r19 import validar
    monkeypatch.setenv('VISOR_PERFIL', 'precision')
    shape, mesh = caja_fragmentada()
    source, baseline = tmp_path / 'original.stl', tmp_path / 'referencia.step'
    mesh.subdivide().subdivide().export(source)
    exportar(shape, baseline)
    quality = _calidad(source, baseline, cargar_exacto(source), control_avanzado=True)
    spec = tmp_path / 'referencia.run.json'
    escribir_json(spec, dict(returncode=0, payload=dict(ok=True, resultado=dict(calidad=quality)),
                             source_sha256=sha(source), step_sha256=sha(baseline)))
    candidate, _ = construir(baseline, tmp_path / 'planos', 'planos')
    result = validar(source, candidate, baseline, spec, tmp_path)
    assert result['accepted'] and result['validated'] and result['calidad']['caras_step'] == 6
    assert result['cilindros'] == []
    assert result['contraste_comun']['regresiones_sobre_00001_mm'] == 0


@pytest.mark.parametrize('profile', ['precision', 'impresion'])
def test_cli_completo_conserva_perfil_y_step_base_si_no_hay_mejora(tmp_path, profile):
    source = tmp_path / 'caja.stl'
    trimesh.creation.box(extents=[4, 5, 6]).export(source)
    output = tmp_path / 'caja.step'
    run = subprocess.run([sys.executable, str(ROOT / 'motor_r19.py'), str(source), str(output)],
                         capture_output=True, text=True, timeout=120,
                         env={**os.environ, 'VISOR_PERFIL': profile})
    assert run.returncode == 0, run.stderr
    payload = json.loads(run.stdout.strip().splitlines()[-1])
    assert payload['ok'] and payload['resultado']['calidad']['perfil_validacion']['id'] == profile
    assert payload['mejora_superficies']['etapa_seleccionada'] == 'r18'
    assert output.read_bytes() == (tmp_path / 'caja.r19/base.step').read_bytes()
    before = output.read_bytes()
    run = subprocess.run([sys.executable, str(ROOT / 'motor_r19.py'), str(source), str(output)], capture_output=True, text=True)
    assert run.returncode != 0 and output.read_bytes() == before


@pytest.mark.parametrize('failure', ['native_exit', 'incomplete_report', 'timeout'])
def test_trabajador_opcional_interrumpido_no_se_acepta(tmp_path, monkeypatch, failure):
    import pipeline_r19 as p
    def fail(args, **kwargs):
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(args, 1)
        if failure == 'incomplete_report':
            Path(args[-1]).write_text('{"accepted":')
            return 0
        return 139
    monkeypatch.setattr(p, 'ejecutar', fail)
    report = p.trabajador(dict(method='costuras'), tmp_path, 'costuras', {}, 1)
    assert report['accepted'] is False and report['validated'] is False


def test_respaldo_r19_completo_prevalece_y_cancelacion_no_lo_recupera(tmp_path):
    from test_respaldo_conversion import job
    import respaldo_r19 as r
    source, step, payload = job(tmp_path)
    expected = step.read_bytes()
    r.guardar(source, step, payload)
    step.write_bytes(b'candidato incompleto')
    assert r.recuperar(source, step, perfil='precision', motivo='cancelado', cancelado=True) is None
    assert step.read_bytes() == b'candidato incompleto'
    recovered = r.recuperar(source, step, perfil='precision', motivo='trabajador detenido')
    assert recovered['recuperacion_respaldo']['revision'] == r.REVISION and step.read_bytes() == expected
    step.write_bytes(b'otra propuesta')
    source.write_bytes(b'original distinto')
    assert r.recuperar(source, step, perfil='precision', motivo='rechazo') is None
    assert step.read_bytes() == b'otra propuesta'


def test_malla_densa_conserva_presupuesto_original_del_motor(tmp_path, monkeypatch):
    import pipeline_r19 as p
    mesh = trimesh.creation.box()
    for _ in range(7):
        mesh = mesh.subdivide()
    assert mesh.is_watertight and len(mesh.faces) > 100000
    source = tmp_path / 'densa.stl'
    mesh.export(source)
    monkeypatch.setattr(p, 'trabajador', lambda *a, **k: dict(ok=False))
    observed = []
    def interrupted(args, **kwargs):
        observed.append(kwargs['timeout'])
        Path(kwargs['stdout']).write_text(json.dumps(dict(ok=False, error='Interrupción controlada de prueba')))
        return 2
    monkeypatch.setattr(p, 'ejecutar', interrupted)
    assert p.convertir(source, tmp_path / 'salida.step')['ok'] is False
    assert observed == [3600]
    assert json.loads((tmp_path / 'salida.r19_pipeline.json').read_text())['presupuesto']['maximo_s'] == 3600
