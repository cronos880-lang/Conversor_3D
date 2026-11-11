import json
from pathlib import Path
import cadquery as cq
import pytest
import trimesh
from conversor3d.pipeline import convert
from conversor3d.legacy import sha, run_worker


@pytest.mark.parametrize('profile', ['precision', 'impresion'])
def test_final_output_always_has_full_certificate(tmp_path, monkeypatch, profile):
    monkeypatch.setenv('VISOR_PERFIL', profile)
    monkeypatch.setenv('CONVERSOR3D_CACHE_DIR', str(tmp_path / 'cache'))
    source, target = tmp_path / 'source.stl', tmp_path / 'output.step'
    trimesh.creation.box(extents=[4, 5, 6]).export(source)
    before = sha(source)
    result = convert(source, target)
    certificate = json.loads(Path(result['development']['certificate']).read_text())
    assert result['ok'] and certificate['record']['ok']
    assert certificate['record']['certificado']['perfil']['id'] == profile
    sidecar = json.loads(target.with_suffix('.r19_nucleo.json').read_text())
    assert sidecar['certificado'] == certificate['record']['certificado']
    pipeline = json.loads(target.with_suffix('.r19_pipeline.json').read_text())
    assert pipeline['timings']['baseline_total_seconds'] >= 0
    assert pipeline['timings']['final_certificate_seconds'] >= 0
    assert pipeline['input_analysis']['authorizes_geometry'] is False
    identity = certificate['record']['certificado']
    assert identity['source_sha256'] == before == sha(source)
    assert identity['step_sha256'] == sha(target)
    assert certificate['record']['material_original']['discrepancias'] == 0
    assert len(certificate['record']['mallado_fino']['resoluciones']) == 3
    assert abs(cq.importers.importStep(str(target)).val().Volume() - 120) < 1e-7
    with pytest.raises(ValueError, match='nueva'):
        convert(source, target)
    # El certificado original no autoriza un STEP distinto.
    changed = tmp_path / 'changed.step'
    cq.exporters.export(cq.Solid.makeBox(4, 5, 7), str(changed))
    with pytest.raises(ValueError):
        run_worker({'action': 'verify_final', 'source': str(source), 'candidate': str(changed),
                    'certificate': result['development']['certificate']}, tmp_path / 'stale')
