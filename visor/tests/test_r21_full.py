from pathlib import Path
import importlib.util
import json
import os
import subprocess
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


def test_complete_archive_carries_its_engine_and_detects_changed_files(tmp_path):
    builder = script('build_r21_full')
    archive = tmp_path / 'complete.zip'
    result = builder.build(archive)
    assert result['identity']['kind'] == 'COMPLETA'
    assert result['identity']['requires_r20'] is False
    assert result['identity']['own_environment'] == '.venv_r21'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert not any(Path(n).suffix.lower() in {'.exe', '.dll', '.pyd', '.so', '.zip'} for n in z.namelist())
        z.extractall(tmp_path)
    root = tmp_path / builder.PREFIX
    manager = script('manage_environment_r21')
    manifest = manager.verify_payload(root)
    frozen = 'entregas/perfeccion_Visualizador_R19/Visor_experimental_fuentes/'
    assert len([n for n in manifest['files'] if n.startswith(frozen)]) == 357
    for name in ('Iniciar_R21.bat', 'Instalar_Entorno_R21.bat', 'Reparar_Entorno_R21.bat', 'Diagnostico_R21.bat'):
        assert (root / name).is_file()
    (root / 'visor/src/conversor3d/pipeline.py').write_text('# altered')
    with pytest.raises(ValueError, match='modificado'):
        manager.verify_payload(root)


def test_complete_environment_ignores_old_paths(tmp_path, monkeypatch):
    manager = script('manage_environment_r21')
    monkeypatch.setattr(manager, 'ROOT', tmp_path)
    monkeypatch.setenv('CONVERSOR3D_BASE_R20', 'R20 no existe')
    monkeypatch.setenv('CONVERSOR3D_DATA_DIR', 'datos ajenos')
    monkeypatch.setenv('PYTHONPATH', 'codigo ajeno')
    env = manager.environment(8789)
    assert 'CONVERSOR3D_BASE_R20' not in env
    assert Path(env['CONVERSOR3D_PROJECT_ROOT']) == tmp_path
    assert Path(env['CONVERSOR3D_DATA_DIR']) == tmp_path / 'datos'
    assert Path(env['PYTHONPATH']) == tmp_path / 'visor/src'
    assert env['CONVERSOR3D_PORT'] == '8789'


@pytest.mark.skipif(os.name != 'nt', reason='Bootstrap Windows real')
def test_complete_bootstrap_uses_only_its_own_environment(tmp_path):
    builder = script('build_r21_full')
    archive = tmp_path / 'complete.zip'
    builder.build(archive)
    with zipfile.ZipFile(archive) as z:
        z.extractall(tmp_path / 'R21 independiente con espacios')
    root = tmp_path / 'R21 independiente con espacios' / builder.PREFIX
    (root / 'visor/scripts/manage_environment_r21.py').write_text(
        "import sys,json,struct;print(json.dumps({'prefix':sys.prefix,'args':sys.argv[1:],"
        "'python':list(sys.version_info[:2]),'bits':struct.calcsize('P')*8}))\n")
    system32 = Path(os.environ['SystemRoot']) / 'System32'
    first = subprocess.run([str(system32 / 'cmd.exe'), '/d', '/c', 'Iniciar_R21.bat', '--no-browser'],
        cwd=root, env={**os.environ, 'CONVERSOR3D_SIN_PAUSA': '1'},
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    assert first.returncode == 0, first.stdout + first.stderr
    initial = json.loads(next(line for line in first.stdout.splitlines() if line.startswith('{')))
    assert initial['python'] == [3, 12] and initial['bits'] == 64
    assert Path(initial['prefix']).resolve() != (root / '.venv_r21').resolve()
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(root / '.venv_r21')], check=True, timeout=60)
    result = subprocess.run([str(system32 / 'cmd.exe'), '/d', '/c', 'Iniciar_R21.bat', '--no-browser'],
        cwd=root, env={**os.environ, 'PATH': str(system32), 'CONVERSOR3D_SIN_PAUSA': '1',
                      'CONVERSOR3D_BASE_R20': 'carpeta inexistente'},
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(next(line for line in result.stdout.splitlines() if line.startswith('{')))
    assert Path(payload['prefix']).resolve() == (root / '.venv_r21').resolve()
    assert payload['args'] == ['start', '--no-browser']
