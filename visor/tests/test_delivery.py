"""Comprobar integridad y alcance del paquete real de fuentes entregado."""
from pathlib import Path
import hashlib
import importlib.util
import json
import zipfile

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r20_archive_keeps_frozen_bytes_and_excludes_new_models_and_environments(tmp_path):
    builder = script('build_r20')
    archive = tmp_path / 'R20.zip'
    summary = builder.build(archive)
    assert summary['identity']['release'] == 'R20'
    assert summary['identity']['version'] == '20.0.0'
    assert summary['identity']['port'] == 8784
    with zipfile.ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read(builder.PREFIX + '/R20_MANIFEST.json'))
        assert manifest['bundled_third_party_binaries'] is False
        assert not any('/.venv' in name or '/datos/' in name or '/data/' in name
                       or '/runtime/' in name for name in bundle.namelist())
        frozen = json.loads((builder.REPO / 'visor/frozen-r19.sha256.json').read_text())
        for name, digest in frozen.items():
            path = builder.PREFIX + '/entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes/' + name
            assert hashlib.sha256(bundle.read(path)).hexdigest() == digest
        for relative, digest in manifest['files'].items():
            assert hashlib.sha256(bundle.read(builder.PREFIX + '/' + relative)).hexdigest() == digest
        batch = bundle.read(builder.PREFIX + '/Iniciar_R20.bat')
        assert b'\r\n' in batch and b'manage_environment.py' in batch
        assert b'.venv_r20\\Scripts\\python.exe' in batch


def test_installer_rejects_changed_package_before_installing(tmp_path):
    module = script('manage_environment')
    source = tmp_path / 'module.py'
    source.write_bytes(b'original')
    manifest = {'files': {'module.py': hashlib.sha256(source.read_bytes()).hexdigest()}}
    (tmp_path / 'R20_MANIFEST.json').write_text(json.dumps(manifest))
    module.verify_payload(tmp_path)
    source.write_bytes(b'modified')
    with pytest.raises(ValueError, match='modificado'):
        module.verify_payload(tmp_path)
