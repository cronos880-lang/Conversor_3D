import json
from pathlib import Path

import cadquery as cq
import trimesh
import pytest

from conversor3d import pipeline, reference_cache
from conversor3d.legacy import FROZEN, sha
from conversor3d.errors import BaselineConversionError


def test_native_failure_keeps_its_code_and_message(tmp_path, monkeypatch):
    def failed(command, folder, name, **options):
        (folder / 'baseline.stdout.txt').write_text('no JSON result')
        (folder / 'baseline.stderr.txt').write_text('ImportError: DLL de prueba no disponible\n')
        return {'returncode': 2, 'seconds': 0.1}
    monkeypatch.setattr(pipeline, 'execute', failed)
    with pytest.raises(BaselineConversionError, match='DLL de prueba'):
        pipeline.run_baseline(tmp_path / 'source.stl', tmp_path / 'output.step', tmp_path,
                              {'timings': {}})
    report = json.loads((tmp_path / 'pipeline.json').read_text())
    assert report['state'] == 'baseline_rejected'
    assert report['baseline_failure']['native_returncode'] == 2
    assert not (tmp_path / 'output.step').exists()


def test_reference_cache_checks_identity_bytes_and_excludes_certificates(tmp_path):
    source = tmp_path / 'source.stl'
    source.write_bytes(b'input')
    baseline = tmp_path / 'baseline.step'
    baseline.write_bytes(b'geometry')
    cache = tmp_path / 'cache'
    identity = reference_cache.identity(source, 'precision', {'test': 'runtime'})
    result = {'ok': True, 'resultado': {'calidad': {'caras_step': 6}},
              'nested': [{'certificado': {'nonce': 'old'}, 'final_validation': {'ok': True}}]}
    reference_cache.store(cache, identity, baseline, result)
    folder = reference_cache.location(cache, identity)
    assert set(p.name for p in folder.iterdir()) == {'reference.step', 'result.json', 'manifest.json'}
    assert json.loads((folder / 'result.json').read_text())['nested'] == [{}]
    target, record = tmp_path / 'copy.step', tmp_path / 'run.json'
    restored = reference_cache.load(cache, identity, target, record)
    assert restored['ok'] and target.read_bytes() == baseline.read_bytes()
    assert json.loads(record.read_text())['source_sha256'] == sha(source)
    other = reference_cache.identity(source, 'impresion', {'test': 'runtime'})
    assert reference_cache.load(cache, other, tmp_path / 'other.step', tmp_path / 'other.json') is None
    (folder / 'reference.step').write_bytes(b'damaged')
    assert reference_cache.load(cache, identity, tmp_path / 'bad.step', tmp_path / 'bad.json') is None
    assert not (tmp_path / 'bad.step').exists()


def test_cached_geometry_gets_new_cold_certificate_without_running_r19_again(tmp_path, monkeypatch):
    monkeypatch.setenv('CONVERSOR3D_CACHE_DIR', str(tmp_path / 'cache'))
    monkeypatch.setenv('VISOR_PERFIL', 'precision')
    source = tmp_path / 'source.stl'
    trimesh.creation.box(extents=[4, 5, 6]).export(source)
    first, second = tmp_path / 'first.step', tmp_path / 'second.step'
    pipeline.convert(source, first)
    original_execute = pipeline.execute
    def no_baseline(command, *args, **kwargs):
        assert str(FROZEN / 'motor_r19.py') not in list(map(str, command)), 'La caché no evitó repetir R19'
        return original_execute(command, *args, **kwargs)
    monkeypatch.setattr(pipeline, 'execute', no_baseline)
    result = pipeline.convert(source, second)
    assert result['ok'] and sha(first) == sha(second)
    old = json.loads(first.with_suffix('.r19_nucleo.json').read_text())
    new = json.loads(second.with_suffix('.r19_nucleo.json').read_text())
    assert old['certificado']['nonce'] != new['certificado']['nonce']
    report = json.loads(second.with_suffix('.r19_pipeline.json').read_text())
    assert report['reference_cache']['cache_hit'] is True
    assert report['reference_cache']['fresh_cold_validation'] is True
    assert report['reference_cache']['certificate_reused_from_cache'] is False
    assert report['selection']['proposal_skipped'] is True
    assert len(new['mallado_fino']['resoluciones']) == 3
    assert new['material_original']['discrepancias'] == 0
    assert abs(cq.importers.importStep(str(second)).val().Volume() - 120) < 1e-7
    # Incluso con un hash de archivo coherente, una geometría distinta NO queda aprobada.
    monkeypatch.setattr(pipeline, 'execute', original_execute)
    entry = next((tmp_path / 'cache/references').iterdir())
    cq.exporters.export(cq.Solid.makeBox(4, 5, 7), str(entry / 'reference.step'))
    manifest = json.loads((entry / 'manifest.json').read_text())
    manifest['step_sha256'] = sha(entry / 'reference.step')
    (entry / 'manifest.json').write_text(json.dumps(manifest))
    third = tmp_path / 'after_corrupt_reference.step'
    pipeline.convert(source, third)
    report = json.loads(third.with_suffix('.r19_pipeline.json').read_text())
    assert report['reference_cache']['cache_hit'] is False
    assert 'rejected_cached_reference' in report['reference_cache']
    assert abs(cq.importers.importStep(str(third)).val().Volume() - 120) < 1e-7
