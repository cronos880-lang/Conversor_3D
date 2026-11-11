"""Comprobar integridad y alcance del paquete real de fuentes entregado."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import zipfile

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


def test_r20_archive_keeps_frozen_bytes_and_excludes_new_models_and_environments(tmp_path):
    builder = script('build_r20')
    archive = tmp_path / 'R20.zip'
    summary = builder.build(archive)
    assert summary['identity']['release'] == 'R20'
    assert summary['identity']['version'] == '20.0.0'
    assert summary['identity']['installer_revision'] == 2
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


def test_repair_overlay_matches_corrected_manifest_and_preserves_user_data(tmp_path):
    builder = script('build_r20')
    patcher = script('build_installer_patch')
    original = builder.REPO / 'entregas/perfeccion_Visualizador_R20/perfeccion_Visualizador_R20_EXPERIMENTAL_COMPLETA.zip'
    corrected, repair = tmp_path / 'corrected.zip', tmp_path / 'repair.zip'
    builder.build(corrected)
    patcher.build(original, corrected, repair)
    with zipfile.ZipFile(original) as archive:
        archive.extractall(tmp_path / 'installed')
    root = tmp_path / 'installed' / builder.PREFIX
    for name in ('datos/modelo.stl', '.venv_r20/conservar.txt'):
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b'USER DATA')
    with zipfile.ZipFile(repair) as archive:
        assert not any(name.startswith(('datos/', '.venv_r20/', 'visor/src/conversor3d/'))
                       for name in archive.namelist())
        archive.extractall(root)
    script('manage_environment').verify_payload(root)
    assert (root / 'datos/modelo.stl').read_bytes() == b'USER DATA'
    assert (root / '.venv_r20/conservar.txt').read_bytes() == b'USER DATA'
