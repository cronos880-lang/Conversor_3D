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


def test_r21_finds_renamed_base_from_windows_nested_extraction(tmp_path):
    launcher = script('r21_launcher')
    root = tmp_path / 'ZIP R21 extraido' / 'Conversor_3D_R21_actualizacion'
    base = tmp_path / 'Mi visor con espacios'
    root.mkdir(parents=True)
    python = launcher.base_python(base)
    python.parent.mkdir(parents=True)
    python.write_bytes(b'fixture')
    engine = base / 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes'
    engine.mkdir(parents=True)
    (engine / 'motor_r19.py').write_text('# fixture')
    assert launcher.choose_base(root, interactive=False) == base


@pytest.mark.skipif(os.name != 'nt', reason='Necesita cmd.exe y Windows PowerShell reales')
def test_windows_bootstrap_needs_no_global_python_and_preserves_spaces(tmp_path):
    import subprocess
    import sys
    builder = script('build_r21_update')
    archive = tmp_path / 'update.zip'
    builder.build(archive)
    with zipfile.ZipFile(archive) as z:
        z.extractall(tmp_path / 'Extraer todo R21')
    root = tmp_path / 'Extraer todo R21' / builder.PREFIX
    base = tmp_path / 'Mi R20 renombrada'
    interpreter = base / '.venv_r20/Scripts/python.exe'
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(interpreter.parent.parent)],
                   check=True, timeout=60)
    engine = base / 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes'
    engine.mkdir(parents=True)
    (engine / 'motor_r19.py').write_text('# fixture')
    # Probar el bootstrap en aislamiento, antes de la comprobación de integridad Python.
    probe = "import sys,json;print(json.dumps({'args':sys.argv[1:]}))\n"
    (root / 'r21_launcher.py').write_text(probe)
    env = {**os.environ, 'PATH': os.environ['SystemRoot'] + '\\System32', 'CONVERSOR3D_SIN_PAUSA': '1'}
    run = subprocess.run([os.environ['SystemRoot'] + '\\System32\\cmd.exe', '/d', '/c',
                          'Iniciar_R21.bat', '--no-browser'], cwd=root, env=env,
                         capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    payload = json.loads(next(line for line in run.stdout.splitlines() if line.startswith('{')))
    assert payload['args'] == ['--base-r20', str(base), '--no-browser']
