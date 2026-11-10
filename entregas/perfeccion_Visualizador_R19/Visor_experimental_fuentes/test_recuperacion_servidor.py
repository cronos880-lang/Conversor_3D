"""Interrumpir una mejora después de una conversión CAD REAL validada."""
from pathlib import Path
import threading,time,json
import pytest,trimesh
from fastapi.testclient import TestClient
import servidor
from control_recursos import LimiteRecursos


@pytest.fixture
def engine(tmp_path,monkeypatch):
 real=Path(servidor.__file__).resolve().parent;root=tmp_path/'motor';root.mkdir();logs=tmp_path/'logs';logs.mkdir()
 script="""import sys,io,json,time,contextlib
from pathlib import Path
sys.path.insert(0,REAL_ROOT)
import motor_v2
from respaldo_r19 import guardar
capture=io.StringIO()
with contextlib.redirect_stdout(capture):code=motor_v2.main()
if code:raise SystemExit(code)
payload=json.loads(capture.getvalue().strip().splitlines()[-1])
source,destination=map(Path,sys.argv[1:]);guardar(source,destination,payload)
destination.write_bytes(b'propuesta incompleta que no debe entregarse')
destination.with_name(destination.name+'.opcional').write_text('lista')
while True:time.sleep(.1)
""".replace('REAL_ROOT',repr(str(real)))
 (root/'motor_r19.py').write_text(script)
 monkeypatch.setattr(servidor,'ROOT',root);monkeypatch.setattr(servidor,'LOG_DIR',logs);monkeypatch.setattr(servidor,'JOBS',{})
 body=trimesh.creation.box(extents=[2,3,4]).export(file_type='stl')
 return body,logs


def wait_ready(proc):
 destination=Path(proc.args[-1]);marker=destination.with_name(destination.name+'.opcional');end=time.monotonic()+45
 while not marker.exists():
  if proc.poll() is not None:
   out,err=proc.communicate();raise AssertionError('El motor de control terminó antes del respaldo: '+out[-1000:]+err[-1000:])
  if time.monotonic()>end:servidor._detener_arbol(proc);raise AssertionError('No terminó la conversión CAD de control')
  time.sleep(.02)
 step=destination.with_name(destination.name+'.r19_base_validada.step')
 return step.read_bytes()


@pytest.mark.parametrize('async_job',[False,True])
def test_limite_en_mejora_devuelve_la_conversion_cad_ya_validada(engine,monkeypatch,async_job):
 body,logs=engine;expected=[]
 def supervised(proc,timeout,stop,**kwargs):
  expected.append(wait_ready(proc));stop(proc);out,err=proc.communicate()
  raise LimiteRecursos('Límite simulado sólo después de validar la base CAD',out,err,1,codigo='tiempo_agotado')
 monkeypatch.setattr(servidor,'comunicar_vigilado',supervised)
 with TestClient(servidor.app) as client:
  if async_job:
   response=client.post('/iniciar-conversion',files={'archivo':('caja.stl',body,'application/octet-stream')},data={'perfil':'precision'});assert response.status_code==200;job=response.json()['id']
   end=time.monotonic()+50
   while time.monotonic()<end:
    state=client.get('/estado-conversion/'+job).json()
    if state['estado']!='ejecutando':break
    time.sleep(.05)
   assert state['estado']=='terminado',state;response=client.get('/descargar-conversion/'+job)
  else:response=client.post('/convertir',files={'archivo':('caja.stl',body,'application/octet-stream')},data={'perfil':'precision'})
  assert response.status_code==200,response.text[:200]
  assert response.content==expected[0] and response.content.startswith(b'ISO-10303-21;')
 records=[json.loads(p.read_text()) for p in logs.glob('*.json') if len(p.stem)==12]
 assert len(records)==1 and records[0]['resultado']=='exito' and records[0]['codigo_motor']!=0
 assert records[0]['recuperacion_respaldo']['aplicado'] and 'incidencia_mejora' in records[0]


def test_cancelar_no_publica_el_respaldo_aunque_sea_valido(engine,monkeypatch):
 body,logs=engine;ready=threading.Event()
 def supervised(proc,timeout,stop,**kwargs):
  wait_ready(proc);ready.set()
  while proc.poll() is None:time.sleep(.02)
  out,err=proc.communicate();raise LimiteRecursos('Interrupción después del respaldo',out,err,1,codigo='tiempo_agotado')
 monkeypatch.setattr(servidor,'comunicar_vigilado',supervised)
 with TestClient(servidor.app) as client:
  response=client.post('/iniciar-conversion',files={'archivo':('caja.stl',body,'application/octet-stream')},data={'perfil':'precision'});job=response.json()['id']
  assert ready.wait(50)
  response=client.post('/cancelar-conversion/'+job);assert response.json()['estado']=='cancelado'
  assert client.get('/descargar-conversion/'+job).status_code==404
