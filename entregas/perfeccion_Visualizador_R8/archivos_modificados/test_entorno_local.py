from pathlib import Path
import entorno_local as env

def test_detecta_entorno_en_programa_completo_y_en_carpeta_fuentes(tmp_path):
    executable=tmp_path/'Visor_experimental_fuentes/.venv/Scripts/python.exe';executable.parent.mkdir(parents=True);executable.write_bytes(b'python')
    assert executable in env.candidatos(tmp_path)
    assert executable in env.candidatos(tmp_path/'Visor_experimental_fuentes')

def test_reutiliza_r7_sin_modificar_su_contenido(tmp_path,monkeypatch):
    old=tmp_path/'R7';new=tmp_path/'R8';new.mkdir()
    executable=old/'.venv/Scripts/python.exe';executable.parent.mkdir(parents=True);executable.write_bytes(b'python R7 original')
    monkeypatch.setattr(env,'compatible',lambda p:Path(p)==executable)
    monkeypatch.setattr(env,'seleccionar_carpeta',lambda:str(old))
    assert env.resolver(new)==executable.resolve()
    assert executable.read_bytes()==b'python R7 original'
    assert (new/'.entorno_python.txt').read_text()==str(executable.resolve())
    assert not (old/'.entorno_python.txt').exists()

def test_configuracion_obsoleta_puede_usar_entorno_actual(tmp_path,monkeypatch):
    (tmp_path/'.entorno_python.txt').write_text(str(tmp_path/'eliminado/python.exe'))
    current=Path(env.sys.executable)
    monkeypatch.setattr(env,'compatible',lambda p:Path(p)==current)
    monkeypatch.setattr(env,'seleccionar_carpeta',lambda:(_ for _ in ()).throw(AssertionError('No pedir carpeta')))
    assert env.resolver(tmp_path)==current.resolve()

def test_cancelar_selector_no_inicia_instalaciones(tmp_path,monkeypatch):
    monkeypatch.setattr(env,'compatible',lambda p:False)
    monkeypatch.setattr(env,'seleccionar_carpeta',lambda:'')
    assert env.resolver(tmp_path) is None and not (tmp_path/'.entorno_python.txt').exists()
