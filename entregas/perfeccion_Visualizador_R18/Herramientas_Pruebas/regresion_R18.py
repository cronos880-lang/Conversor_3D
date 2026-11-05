from pathlib import Path
import sys,json,hashlib,time,concurrent.futures
W=Path(__file__).parent;M=W/'prueba paquete R18 con espacios/perfeccion_Visualizador_R18/Visor_experimental_fuentes';R17=Path('/workspace/work/curvas_nuevas_20261104');sys.path[:0]=[str(M),'/workspace/work/bancada_objetivo_20261104']
from bateria_reparacion import ejecutar
from certificado_calidad_r15 import firma_motor
from comparar_step_numerico import comparar
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
base={r['id']:r for r in json.loads((R17/'REGRESION_VALIDADA_R17.json').read_text())['resultados']};protocol=json.loads(Path('/workspace/work/mejora_motor_post_r7_20261026/regresion_historica/protocolo.json').read_text());old=[dict(c,perfil='precision',grupo_control='regresion_R17')for c in protocol['casos']if c['grupo']in('historica12','cubo4')or c['id']=='conector']
old += [dict(id='Technic_PEGS_Cross_x6_A',grupo_control='regresion_R17',perfil='precision',source='/workspace/work/mejora_cad_post_avance_20261026/entradas_nuevas/Technic_PEGS_Cross_x6_A.stl',sha256='2a2844baf0a1cfa4df28257909cfc2060fee828d4e5339c6d4fd21f43f5e2b30'),dict(id='brida_independiente',grupo_control='regresion_R17',perfil='precision',source='/workspace/work/desarrollo_R15_20261103/brida_independiente_R15.stl')];old[-1]['sha256']=sha(old[-1]['source'])
old += [dict(c,grupo_control='regresion_R17')for c in json.loads((R17/'CONTROLES_ADICIONALES.json').read_text())]
inputs=json.loads((W/'ENTRADAS_SHA256.json').read_text());bodyq=json.loads((R17/'prueba_navegador_body_R17.json').read_text())['calidad'];base['Body_usuario']=dict(calidad=bodyq,sha256_step=inputs['body_step']['sha256'])
old += [dict(id='Body_usuario',grupo_control='regresion_R17',perfil='precision',source=inputs['body_stl']['path'],sha256=inputs['body_stl']['sha256'])]
r17inputs=json.loads((R17/'ENTRADAS_SHA256.json').read_text());guideui=json.loads((R17/'prueba_navegador_guia_R17.json').read_text());base['Guia_ranurada']=dict(calidad=guideui['calidad'],sha256_step=guideui['sha256_step']);old += [dict(id='Guia_ranurada',grupo_control='regresion_R17',perfil='impresion',source=r17inputs['guia_stl']['path'],sha256=r17inputs['guia_stl']['sha256'])]
additional=[dict(id=name,grupo_control='nueva_familia_R18',perfil=profile,source=inputs[k+'_stl']['path'],sha256=inputs[k+'_stl']['sha256'])for k,name,profile in [('flame','Flame_Base','precision'),('base','Base','precision'),('flame','Flame_impresion','impresion'),('base','Base_impresion','impresion')]]
additional += [dict(c,grupo_control='nueva_familia_R18')for c in json.loads((W/'CONTROLES_INDEPENDIENTES.json').read_text())]
priority=['Bancada_Motor','maneta','LLanta_Trasera','Tirante','cubo-carrito','cubo-carrito_giro_1','cubo-carrito_giro_2','cubo-carrito_giro_3','brida_independiente','conector','pinza','Technic_PEGS_Cross_x6_A'];old.sort(key=lambda c:priority.index(c['id'])if c['id']in priority else 100)
cases=[old[0]]+additional+[next(c for c in old if c['id']=='Body_usuario')]+[c for c in old[1:]if c['id']!='Body_usuario'];assert len(cases)==33
(W/'PROTOCOLO_R18.json').write_text(json.dumps(cases,indent=2));output=W/'regresion_cli_R18';output.mkdir(exist_ok=True);code=firma_motor(M)
def run(case):
 while case['id']!='Bancada_Motor' and (W/'RESERVA_PRUEBAS_ACTIVA').exists():time.sleep(.5)
 source=Path(case['source']);assert sha(source)==case['sha256'];print('INICIO',case['id'],case['perfil'],flush=True);destination=output/(case['id']+'.step')
 row=ejecutar(M,source,destination,limite=2400,memoria_mb=4200,extra_env={'VISOR_PERFIL':case['perfil'],'PYTHONDONTWRITEBYTECODE':'1'});row.update(id=case['id'],grupo_control=case['grupo_control'],perfil_solicitado=case['perfil'],codigo_fuente_sha256=code);assert sha(source)==case['sha256']and firma_motor(M)==code
 q=row['informe_motor'].get('resultado',{}).get('calidad',{});row['calidad']=q;row['control_superado']=False
 if row['ok']:
  if case['grupo_control']=='regresion_R17':
   ref=base[case['id']];q0=ref['calidad'];baseline=Path(inputs['body_step']['path'])if case['id']=='Body_usuario'else (R17/'navegador_guia_R17.step'if case['id']=='Guia_ranurada'else R17/'regresion_cli_R17'/(case['id']+'.step'));assert sha(baseline)==ref['sha256_step'];a,b=baseline.read_bytes(),destination.read_bytes();literal=a[a.index(b'DATA;'):]==b[b.index(b'DATA;'):];row.update(DATA_identico_R17=literal,calidad_R17=q0,referencia_R17_sha256=sha(baseline));equivalent=literal
   if not literal:row['auditoria_STEP']=comparar(baseline,destination);equivalent=row['auditoria_STEP']['equivalente']
   row['control_superado']=bool(equivalent and q['caras_step']==q0['caras_step']and q['tipos_caras']==q0['tipos_caras']and all(q[k]<=q0[k]+1e-6 for k in ['desviacion_max_verificada_mm','caja_error_mm','volumen_error_pct']))
  else:
   result=row['informe_motor']['resultado'];proof=result.get('reconstruccion_fuente',{});row['nueva_ruta_aplicada']=bool(proof.get('aplicado')and result.get('estrategia')=='reconstruccion_fuente_verificada_r18');row['control_superado']=bool(row['nueva_ruta_aplicada']and q['perfil_validacion']['id']==case['perfil']and q['tipos_caras'].get('GeomAbs_Cylinder',0)>=1)
 print('FINAL',case['id'],row['ok'],row['control_superado'],q.get('caras_step'),row['segundos'],flush=True);return row
saved=W/'REGRESION_R18_EN_CURSO.json';rows=[]
if saved.exists():
 for row in json.loads(saved.read_text())['resultados']:
  path=output/(row['id']+'.step')
  if row.get('control_superado')and row.get('codigo_fuente_sha256')==code and path.exists()and sha(path)==row['sha256_step']:rows.append(row)
done={r['id']for r in rows}
with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:
 for future in concurrent.futures.as_completed([pool.submit(run,c)for c in cases if c['id']not in done]):
  rows.append(future.result());saved.write_text(json.dumps(dict(completo=False,codigo_sha256=code,resultados=rows),ensure_ascii=False,indent=2))
record=dict(completo=len(rows)==33 and all(r['control_superado']for r in rows),codigo_sha256=code,conversiones=len(rows),controles_regresion=sum(r['grupo_control']=='regresion_R17'for r in rows),controles_nueva_familia=sum(r['grupo_control']=='nueva_familia_R18'for r in rows),resultados=rows,originales_probados=13,original_aplazado='Fast+Funnel+large.stl por indicación del usuario');(W/'REGRESION_VALIDADA_R18.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));print(json.dumps({k:record[k]for k in ['completo','conversiones','controles_regresion','controles_nueva_familia']}),flush=True)
if not record['completo']:raise SystemExit(2)
