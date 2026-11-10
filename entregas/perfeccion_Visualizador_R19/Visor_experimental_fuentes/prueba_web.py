import sys,time,json
from pathlib import Path
from fastapi.testclient import TestClient
import servidor
client=TestClient(servidor.app)
response=client.post('/iniciar-conversion',files={'archivo':('M3 PClip - 2mm.stl',Path('/mnt/data/M3 PClip - 2mm.stl').read_bytes(),'application/octet-stream')})
print('started',response.status_code,response.text,flush=True)
assert response.status_code==200
id=response.json()['id']
t0=time.monotonic(); stats=[]
while time.monotonic()-t0 < 150:
 status=client.get(f'/estado-conversion/{id}').json()
 stats.append(status['porcentaje'])
 if status['estado'] not in ('ejecutando','cancelando'):
  print('finished',status,'monotonic',stats==sorted(stats), 'max_while_running',max(stats[:-1]) if len(stats)>1 else None,flush=True)
  if status['estado']=='terminado':
   r=client.get(f'/descargar-conversion/{id}')
   print('download',r.status_code,len(r.content),flush=True)
  break
 time.sleep(1)
else:print('timeout in integration test',flush=True)
