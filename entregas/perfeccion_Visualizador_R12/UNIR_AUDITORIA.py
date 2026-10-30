from pathlib import Path
import hashlib,json,sys
r=Path(__file__).resolve().parent
info=json.loads((r/'AUDITORIA_EN_PARTES.json').read_text(encoding='utf-8'))
target=r/info['archivo_reconstruido']
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
if target.exists():
 if sha(target)==info['sha256_reconstruido']:print('La auditoría ya está reunida y verificada.');sys.exit(0)
 raise SystemExit('Existe un ZIP distinto; no se sobrescribe: '+str(target))
for row in info['partes']:
 p=r/row['archivo']
 if not p.is_file() or p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:raise SystemExit('Falta una parte o su hash no coincide: '+str(p))
tmp=target.with_suffix('.reuniendo.tmp')
with tmp.open('xb') as f:
 for row in info['partes']:
  with (r/row['archivo']).open('rb') as source:
   for b in iter(lambda:source.read(1024*1024),b''):f.write(b)
if sha(tmp)!=info['sha256_reconstruido']:tmp.unlink();raise SystemExit('No coincide el hash completo.')
if target.exists():raise SystemExit('El destino apareció durante la reunión; no se sobrescribe.')
tmp.replace(target)
print('Auditoría reunida y SHA-256 verificado:',target.name)
