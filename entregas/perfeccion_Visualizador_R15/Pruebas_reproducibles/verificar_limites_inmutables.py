from pathlib import Path
import zipfile,json,hashlib,ast
W=Path(__file__).parent;M=W/'motor_experimental';Z=Path('/workspace/entregas_R14/perfeccion_Visualizador_R14_EXPERIMENTAL_COMPLETA.zip');prefix='perfeccion_Visualizador_R14/Visor_experimental_fuentes/'
sha=lambda b:hashlib.sha256(b).hexdigest();checks=[]
with zipfile.ZipFile(Z) as a:
 for root in ['', 'motor_calidad/']:
  old=ast.parse(a.read(prefix+root+'motor_v2.py').decode());new=ast.parse((M/(root+'motor_v2.py')).read_text())
  def evaluator(tree):return ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_calidad'),include_attributes=False)
  assert evaluator(old)==evaluator(new)
  def limits(tree):return {target.id:ast.dump(node.value,include_attributes=False) for node in tree.body if isinstance(node,ast.Assign) for target in node.targets if isinstance(target,ast.Name) and target.id.startswith(('MAX_','MIN_'))}
  assert limits(old)==limits(new);checks.append(dict(archivo=root+'motor_v2.py',evaluador_geometrico_AST_identico_R14=True,limites_constantes_identicos_R14=True))
 for name in ['perfiles_precision.py','validacion_densa.py','validacion_local.py','calidad_topologica.py','saneamiento_cad.py','motor_calidad/perfiles_precision.py','motor_calidad/validacion_densa.py','motor_calidad/reconstruccion_curvas.py']:
  before=a.read(prefix+name);after=(M/name).read_bytes();assert before==after;checks.append(dict(archivo=name,sha256=sha(after),identico_R14=True))
r=dict(ok=True,comprobaciones=checks,nota='Cambian construcción propuesta, consulta CAD de material y reutilización de un control completo vinculado a hashes. No cambian perfiles, función de evaluación geométrica, puntos de material, banda ni tolerancia del clasificador.');(W/'LIMITES_INMUTABLES_R15.json').write_text(json.dumps(r,indent=2,ensure_ascii=False));print('Perfiles, evaluadores y límites originales R14 conservados:',len(checks),'comprobaciones')
