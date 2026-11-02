"""Reassemble only the tested, SHA-256-bound R14 deliverables."""
from pathlib import Path,PurePosixPath
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'PARTES_SHA256.json').read_text())
for item in manifest['archivos']:
 data=bytearray()
 for part in item['partes']:
  piece=(ROOT/'.partes'/part['nombre']).read_bytes()
  assert len(piece)==part['bytes'] and hashlib.sha256(piece).hexdigest()==part['sha256'],part['nombre']
  data.extend(piece)
 assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256'],item['nombre']
 assert Path(item['nombre']).name==item['nombre']
 (ROOT/item['nombre']).write_bytes(data)
 if item['nombre'].endswith('_EXPERIMENTAL_COMPLETA.zip'):
  import io
  with zipfile.ZipFile(io.BytesIO(data)) as archive:
   for info in archive.infolist():
    name=PurePosixPath(info.filename)
    assert not name.is_absolute() and '..' not in name.parts and name.parts[0]=='perfeccion_Visualizador_R14',info.filename
   sources=json.loads(archive.read('perfeccion_Visualizador_R14/FUENTES_SHA256.json'))
   prefix='perfeccion_Visualizador_R14/Visor_experimental_fuentes/'
   assert {name for name in archive.namelist() if name.startswith(prefix) and not name.endswith('/')}=={prefix+name for name in sources}
   for name,sha in sources.items():
    assert hashlib.sha256(archive.read('perfeccion_Visualizador_R14/Visor_experimental_fuentes/'+name)).hexdigest()==sha,name
   archive.extractall(ROOT.parent)
(ROOT/'PUBLICACION_VERIFICADA.json').write_text(json.dumps(dict(verificado=True,archivos=[{k:v for k,v in item.items() if k!='partes'} for item in manifest['archivos']],fuentes_verificadas=len(sources)),indent=2))
print('Entrega R14 reconstruida; integridad de archivos y fuentes comprobada.')
