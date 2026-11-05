"""Run from extracted release with the prepared CAD Python; no reference cache."""
from pathlib import Path
import sys,json,hashlib,subprocess,os
ROOT=Path(__file__).resolve().parent.parent;APP=ROOT/'Visor_experimental_fuentes';OUTPUT=ROOT/'Repeticion_Controles';OUTPUT.mkdir(exist_ok=True)
rows=[]
for relative in ['Pruebas_Curvas/Flame_Base.stl','Pruebas_Curvas/Base.stl','Pruebas_Curvas/Body.stl']+[str(p.relative_to(ROOT))for p in sorted((ROOT/'Controles_Independientes').glob('*/entrada.stl'))]:
 source=ROOT/relative;name=source.parent.name if source.name=='entrada.stl'else source.stem;destination=OUTPUT/(name+'.step');before=hashlib.sha256(source.read_bytes()).hexdigest();env={**os.environ,'VISOR_PERFIL':'precision','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
 result=subprocess.run([sys.executable,str(APP/'motor_v2.py'),str(source),str(destination)],cwd=APP,env=env,capture_output=True,text=True);(OUTPUT/(name+'.stdout.txt')).write_text(result.stdout);(OUTPUT/(name+'.stderr.txt')).write_text(result.stderr);record=json.loads(result.stdout.strip().splitlines()[-1]);assert before==hashlib.sha256(source.read_bytes()).hexdigest();rows.append(dict(archivo=relative,ok=result.returncode==0 and record.get('ok'),resultado=record));(OUTPUT/'RESULTADOS.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(name,rows[-1]['ok'],flush=True)
 if not rows[-1]['ok']:raise SystemExit(2)
