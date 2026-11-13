from pathlib import Path
import hashlib
import importlib.util
import json
import os
import zipfile

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r21_update_is_small_complete_and_contains_no_environment_or_models(tmp_path):
    builder = script('build_r21_update')
    archive = tmp_path / 'update.zip'
    result = builder.build(archive)
    assert result['identity']['kind'] == 'ACTUALIZACION'
    assert result['identity']['version'] == '21.0.0'
    assert result['bytes'] < 512 * 1024
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert not any(Path(n).suffix.lower() in {'.exe', '.dll', '.pyd', '.so', '.stl', '.step', '.stp', '.zip'}
                       or '/datos/' in n or '/.venv' in n for n in bundle.namelist())
        bundle.extractall(tmp_path / 'extracted')
    root = tmp_path / 'extracted' / builder.PREFIX
    launcher = script('r21_launcher')
    manifest = launcher.verify_update(root)
    assert manifest['identity']['base_release'] == 'R20'
    assert len(json.loads((root / 'R19_FROZEN_SHA256.json').read_text())) == 357
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    asset = root / 'visor/src/conversor3d/resources/viewer/presentation.js'
    assert asset.is_file()
    asset.write_bytes(b'changed')
    with pytest.raises(ValueError, match='modificado'):
        launcher.verify_update(root)


def test_r21_base_detection_preserves_separate_folders(tmp_path):
    launcher = script('r21_launcher')
    root, base = tmp_path / 'R21 con espacios', tmp_path / 'Conversor_3D_R20_experimental'
    root.mkdir()
    python = launcher.base_python(base)
    python.parent.mkdir(parents=True)
    python.write_bytes(b'fixture')
    engine = base / 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes'
    engine.mkdir(parents=True)
    (engine / 'motor_r19.py').write_text('# fixture')
    assert launcher.choose_base(root, interactive=False) == base
    assert launcher.choose_base(root, explicit=base, interactive=False) == base
    assert not (base / 'datos').exists()
    with pytest.raises(ValueError, match='entorno'):
        launcher.choose_base(root, explicit=tmp_path / 'wrong', interactive=False)
