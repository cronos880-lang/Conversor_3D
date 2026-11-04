"""Conversiones reales de la copia congelada; pruebas de familia y regresión R16."""
from pathlib import Path
import sys,json,hashlib,time,concurrent.futures
W=Path(__file__).parent;M=W/'prueba paquete R17 con espacios/perfeccion_Visualizador_R17/Visor_experimental_fuentes';R16=Path('/workspace/work/bancada_objetivo_20261104');sys.path.insert(0,str(M));sys.path.insert(0,str(R16))
from bateria_reparacion import ejecutar
from certificado_calidad_r15 import firma_motor
from comparar_step_numerico import comparar
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
base={r['id']:r for r in json.loads((R16/'REGRESION_VALIDADA_R16.json').read_text())['resultados']};protocol=json.loads(Path('/workspace/work/mejora_motor_post_r7_20261026/regresion_historica/protocolo.json').read_text());old=[dict(c,perfil='precision',grupo_control='regresion_R16')for c in protocol['casos']if c['grupo']in('historica12','cubo4')or c['id']=='conector']
old.append(dict(id='Technic_PEGS_Cross_x6_A',grupo_control='regresion_R16',perfil='precision',source='/workspace/work/mejora_cad_post_avance_20261026/entradas_nuevas/Technic_PEGS_Cross_x6_A.stl',sha256='2a2844baf0a1cfa4df28257909cfc2060fee828d4e5339c6d4fd21f43f5e2b30'))
brida='/workspace/work/desarrollo_R15_20261103/brida_independiente_R15.stl';old.append(dict(id='brida_independiente',grupo_control='regresion_R16',perfil='precision',source=brida,sha256=sha(brida)))
additional=[dict(c,grupo_control='nueva_familia')for c in json.loads((W/'CONTROLES_ADICIONALES.json').read_text())]
priority=['Bancada_Motor','maneta','LLanta_Trasera','Tirante','cubo-carrito','cubo-carrito_giro_1','cubo-carrito_giro_2','cubo-carrito_giro_3','brida_independiente','conector','pinza','Technic_PEGS_Cross_x6_A']
old.sort(key=lambda c:priority.index(c['id'])if c['id']in priority else 100);cases=[old[0]]+additional+old[1:];output=W/'regresion_cli_R17';output.mkdir(exist_ok=True);code=firma_motor(M)
def run(case):
 source=Path(case['source']);assert sha(source)==case['sha256'];print('INICIO',case['id'],case['perfil'],flush=True);destination=output/(case['id']+'.step')
 row=ejecutar(M,source,destination,limite=2400,memoria_mb=4200,extra_env={'VISOR_PERFIL':case['perfil'],'PYTHONDONTWRITEBYTECODE':'1'});row.update(id=case['id'],grupo_control=case['grupo_control'],perfil_solicitado=case['perfil'],codigo_fuente_sha256=code);assert sha(source)==case['sha256']and firma_motor(M)==code
 q=row['informe_motor'].get('resultado',{}).get('calidad',{});row['calidad']=q;row['control_superado']=False
 if row['ok']:
  if case['grupo_control']=='regresion_R16':
   ref=base[case['id']];q0=ref['calidad'];baseline=R16/'navegador_Bancada_Motor_R16.step'if case['id']=='Bancada_Motor'else R16/'regresion_cli_R16'/(case['id']+'.step');assert sha(baseline)==ref['sha256_step'];a,b=baseline.read_bytes(),destination.read_bytes();literal=a[a.index(b'DATA;'):]==b[b.index(b'DATA;'):];row.update(DATA_identico_R16=literal,calidad_R16=q0,referencia_R16_sha256=sha(baseline))
   equivalent=literal
   if not literal:row['auditoria_STEP']=comparar(baseline,destination);equivalent=row['auditoria_STEP']['equivalente']
   row['control_superado']=bool(equivalent and q['caras_step']==q0['caras_step']and q['tipos_caras']==q0['tipos_caras']and all(q[k]<=q0[k]+1e-6 for k in ['desviacion_max_verificada_mm','caja_error_mm','volumen_error_pct']))
  else:
   result=row['informe_motor']['resultado'];proof=result.get('reconstruccion_fuente',{});row['nueva_ruta_aplicada']=bool(proof.get('aplicado'));row['control_superado']=bool(row['nueva_ruta_aplicada']and q['perfil_validacion']['id']==case['perfil']and q['tipos_caras'].get('GeomAbs_Cylinder',0)>=2)
 print('FINAL',case['id'],row['ok'],row['control_superado'],q.get('caras_step'),row['segundos'],flush=True);return row
saved=W/'REGRESION_R17_EN_CURSO.json';rows=[]
if saved.exists():
 for row in json.loads(saved.read_text())['resultados']:
  path=output/(row['id']+'.step')
  if row.get('control_superado')and row.get('codigo_fuente_sha256')==code and path.exists()and sha(path)==row['sha256_step']:rows.append(row)
done={r['id']for r in rows}
with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
 for future in concurrent.futures.as_completed([pool.submit(run,c)for c in cases if c['id']not in done]):
  rows.append(future.result());saved.write_text(json.dumps(dict(completo=False,codigo_sha256=code,resultados=rows),ensure_ascii=False,indent=2))
record=dict(completo=len(rows)==23 and all(r['control_superado']for r in rows),codigo_sha256=code,conversiones=len(rows),controles_regresion=sum(r['grupo_control']=='regresion_R16'for r in rows),controles_nueva_familia=sum(r['grupo_control']=='nueva_familia'for r in rows),resultados=rows,originales_probados=13,original_aplazado='Fast+Funnel+large.stl por indicación del usuario')
(W/'REGRESION_VALIDADA_R17.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));print(json.dumps({k:record[k]for k in ['completo','conversiones','controles_regresion','controles_nueva_familia']}),flush=True)
if not record['completo']:raise SystemExit(2)
