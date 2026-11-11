"""Regresiones de espera silenciosa y de extracción interrumpida de un paquete."""
from pathlib import Path
import importlib.util
import sys

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


def test_silent_child_reports_activity_and_flushes_log(tmp_path, capsys):
    progress = script('installation_progress')
    log = tmp_path / 'install.log'
    result = progress.run_progress([sys.executable, '-u', '-c',
        'import time; time.sleep(.4); print("COMPLETED")'],
        log_path=log, heartbeat=.05, timeout=10, label='paquete lento')
    captured = capsys.readouterr().out
    assert '[EN CURSO] paquete lento' in captured
    assert 'COMPLETED' in result and 'COMPLETED' in log.read_text()


def test_silent_stuck_child_is_stopped_at_deadline():
    progress = script('installation_progress')
    with pytest.raises(TimeoutError, match='plazo'):
        progress.run_progress([sys.executable, '-u', '-c', 'import time; time.sleep(60)'],
                              heartbeat=.05, timeout=.2, label='paquete bloqueado')


def test_two_installations_cannot_modify_same_environment(tmp_path):
    progress = script('installation_progress')
    path = tmp_path / 'install.lock'
    with progress.installation_lock(path):
        with pytest.raises(RuntimeError, match='otra instalación'):
            with progress.installation_lock(path):
                pytest.fail('No debe obtener un segundo bloqueo')
    with progress.installation_lock(path):
        pass  # Un archivo de bloqueo antiguo no impide reintentar.


def test_missing_file_is_incomplete_despite_correct_version(tmp_path):
    installer = script('install_dependencies')
    class Distribution:
        version = '1.0'

        @property
        def files(self):
            return [name for name in ('module.py', 'data.txt') if (tmp_path / name).exists()]

        def read_text(self, name):
            assert name == 'RECORD'
            return 'module.py,,6\ndata.txt,,4\noptional.pyc,,\n'

        def locate_file(self, file):
            return tmp_path / file

    dist = Distribution()
    (tmp_path / 'module.py').write_text('module')
    assert not installer.complete_distribution(dist, '1.0')
    (tmp_path / 'data.txt').write_text('data')
    assert installer.complete_distribution(dist, '1.0')
    (tmp_path / 'data.txt').write_text('da')
    assert not installer.complete_distribution(dist, '1.0')
    assert not installer.complete_distribution(dist, '2.0')


def test_split_locks_retain_every_hash_and_reject_unpinned_package(tmp_path):
    installer = script('install_dependencies')
    for platform in ('windows', 'linux'):
        path = SCRIPTS.parent / f'requirements-{platform}-py312.lock'
        blocks = installer.locked_packages(path)
        assert len(blocks) == (78 if platform == 'windows' else 77)
        assert sum(text.count('--hash=') for _, _, text in blocks) == path.read_text().count('--hash=')
    bad = tmp_path / 'bad.lock'
    bad.write_text('numpy==2.3.5\n')
    with pytest.raises(ValueError, match='hash'):
        installer.locked_packages(bad)
