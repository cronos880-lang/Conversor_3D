from pathlib import Path
import importlib.util
import json
import os
import sys
import time
import pytest

PATH = Path(__file__).resolve().parents[1] / 'Archivos_Parche' / 'Preparar_Entorno_R19.py'
spec = importlib.util.spec_from_file_location('preparar_entorno_probado', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_error_importacion_conserva_modulo_y_mensaje(tmp_path, capsys):
    folder = tmp_path / 'carpeta con espacios'
    folder.mkdir()
    (folder / 'modulo_cad.py').write_text('raise ImportError("DLL CAD de prueba no encontrada")')
    runner = module.Runner(tmp_path / 'registro.txt')
    assert not runner.step('Cargando modulo_cad', [sys.executable, '-c', 'import modulo_cad'], cwd=folder, timeout=10)
    assert 'DLL CAD de prueba no encontrada' in capsys.readouterr().out
    assert 'modulo_cad' in runner.log.read_text() and not runner.results[0]['ok']


def test_bloqueo_emite_actividad_y_finaliza(tmp_path, capsys):
    runner = module.Runner(tmp_path / 'registro.txt', heartbeat=.1)
    started = time.monotonic()
    assert not runner.step('Import bloqueado', [sys.executable, '-c', 'import time;time.sleep(60)'], timeout=.5)
    assert time.monotonic() - started < 5
    assert runner.results[0]['tipo'] == 'tiempo_agotado'
    assert 'Sigue trabajando' in capsys.readouterr().out


def test_cierre_nativo_no_se_confunde_con_exito(tmp_path):
    runner = module.Runner(tmp_path / 'registro.txt')
    assert not runner.step('Libreria nativa', [sys.executable, '-c', 'import os;os._exit(139)'], timeout=5)
    assert runner.results[0]['codigo'] == 139 and runner.results[0]['tipo'] == 'proceso_fallido'


def test_no_ejecutable_muestra_error_real(tmp_path):
    runner = module.Runner(tmp_path / 'registro.txt')
    assert not runner.step('Python ausente', [str(tmp_path / 'no_existe')], timeout=2)
    assert runner.results[0]['tipo'] == 'no_se_pudo_ejecutar'


def test_se_detiene_en_primera_libreria_que_falla(tmp_path, monkeypatch):
    runner = module.Runner(tmp_path / 'registro.txt')
    calls = []
    def step(label, args, **kwargs):
        calls.append(label)
        return not label.endswith('Cargando cadquery')
    monkeypatch.setattr(runner, 'step', step)
    assert module.check(runner, sys.executable) is False
    assert calls[-1].endswith('Cargando cadquery')
    assert not any('conjunta' in label for label in calls)


def test_comprobar_no_crea_ni_instala_entorno(tmp_path, monkeypatch):
    source = tmp_path / 'fuentes'
    source.mkdir()
    (source / 'requirements_bloqueadas.txt').write_text('')
    (tmp_path / 'Iniciar_R19.bat').write_text('@echo off')
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module, 'SOURCE', source)
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: pytest.fail('No ejecutar instalador si no hay entorno'))
    assert module.main(['--comprobar']) == 2
    assert not (source / '.venv').exists()
    report = next((tmp_path / 'Diagnosticos_Instalacion').glob('*.json'))
    assert json.loads(report.read_text())['ok'] is False


def test_parche_separado_no_crea_un_entorno_en_carpeta_equivocada(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(module, 'SOURCE', tmp_path / 'fuentes')
    assert module.main(['--instalar']) == 2
    assert 'otra carpeta' in capsys.readouterr().out
    assert not (tmp_path / 'fuentes/.venv').exists()


@pytest.mark.skipif(os.name == 'nt', reason='Esta comprobación del árbol usa grupos POSIX; taskkill requiere Windows nativo')
def test_timeout_detiene_tambien_descendiente(tmp_path):
    import psutil
    pidfile = tmp_path / 'descendiente.txt'
    code = 'import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(60)'
    runner = module.Runner(tmp_path / 'registro.txt')
    assert not runner.step('Arbol bloqueado', [sys.executable, '-c', code, str(pidfile)], timeout=1)
    assert pidfile.exists()
    try:
        process = psutil.Process(int(pidfile.read_text()))
        assert not process.is_running() or process.status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        pass
