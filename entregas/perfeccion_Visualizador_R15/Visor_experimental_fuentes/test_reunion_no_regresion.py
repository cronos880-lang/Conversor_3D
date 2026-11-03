"""Regresión real de R13: una propuesta dentro de tolerancias puede empeorar."""
from pathlib import Path
import copy,hashlib,io,json,shutil
import pytest
import perfeccion_calidad
from reunion_resultado_aislada import intentar

def test_rechaza_la_regresion_medida_y_conserva_el_step_previo(tmp_path,monkeypatch):
 fixtures=Path(__file__).parent/'fixtures_cad/reunion_regresion_R13'
 data=json.loads((fixtures/'mediciones_reales.json').read_text())
 source=tmp_path/'entrada.stl';step=tmp_path/'salida.step'
 shutil.copyfile(fixtures/'original.stl',source);shutil.copyfile(fixtures/'anterior.step',step)
 initial=step.read_bytes();original=source.read_bytes()
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 assert data['calidad_final_propuesta']['desviacion_max_verificada_mm']>.03
 def recorded_worker(script,args,timeout,log):
  src,baseline,candidate,report=map(Path,args)
  shutil.copyfile(fixtures/'propuesta_rechazada.step',candidate)
  record=copy.deepcopy(data['trabajador_propuesta'])
  # Reutiliza la prueba CAD real de estos mismos bytes. El archivo base cambia
  # sólo de encabezado frente a la ejecución observada; la medición se conserva.
  assert record['step_sha256']==sha(candidate) and record['original_sha256']==sha(src)
  record['base_sha256']=sha(baseline)
  report.write_text(json.dumps(record));return 1.
 def observed_parent_quality(src,candidate,mesh,**options):
  assert options['control_avanzado'] and options['prueba_cad'].step_sha256==sha(candidate)
  return copy.deepcopy(data['calidad_final_propuesta'])
 monkeypatch.setattr(perfeccion_calidad,'ejecutar_subproceso',recorded_worker)
 with pytest.raises(ValueError,match='empeora la desviación máxima'):
  intentar(source,step,copy.deepcopy(data['payload_anterior']),observed_parent_quality,io.StringIO())
 assert step.read_bytes()==initial and source.read_bytes()==original
