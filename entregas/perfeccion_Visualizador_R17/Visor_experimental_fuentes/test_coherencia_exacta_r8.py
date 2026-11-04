from pathlib import Path
import hashlib
import cadquery as cq
import pytest
from saneamiento_cad import exigir_coherencia_exacta,IncoherenciaCAD
from reconstruccion_curvas import presupuesto_recuperacion

def test_un_step_que_pasa_el_control_ordinario_puede_ser_rechazado_por_el_exacto():
    path=Path(__file__).parent/'fixtures_cad/Bancada_104_NO_APROBADO.step'
    before=hashlib.sha256(path.read_bytes()).hexdigest();shape=cq.importers.importStep(str(path)).val()
    assert shape.isValid()
    with pytest.raises(IncoherenciaCAD) as error:exigir_coherencia_exacta(shape)
    assert error.value.calidad['lectura_fria'] and not error.value.calidad['brep_exacto']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before

def test_un_solido_exacto_sigue_aceptado():
    shape=cq.Workplane('XY').box(2,3,4).edges('|Z').fillet(.2).val()
    exigir_coherencia_exacta(shape)

def test_presupuesto_recuperacion_acotado_y_creciente():
    values=[presupuesto_recuperacion(n) for n in [0,1000,4532,10000,20000,1000000]]
    assert values==sorted(values) and values[0]==300 and values[-1]==900
    assert all(300<=n<=900 for n in values)

def test_normalizacion_rechazada_no_sustituye_el_step_original(tmp_path,monkeypatch):
    import sys
    sys.path.insert(0,str(Path(__file__).parent/'motor_superficies'))
    import contornos_periodicos as cp
    path=tmp_path/'modelo.step';cq.exporters.export(cq.Workplane('XY').box(1,2,3).val(),str(path));original=path.read_bytes()
    def fail(shape):raise ValueError('Proyección no verificada')
    monkeypatch.setattr(cp,'reunir_ciclos_analiticos',fail)
    report=cp.normalizar_step(path)
    assert not report['aplicado'] and report['candidato_original_conservado'] and path.read_bytes()==original
