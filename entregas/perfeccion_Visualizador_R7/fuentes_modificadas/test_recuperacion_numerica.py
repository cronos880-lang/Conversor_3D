from pathlib import Path
import hashlib,json,os
import numpy as np
import pytest,trimesh
from proximidad_triangular import punto_mas_cercano,baricentricas

@pytest.mark.parametrize('scale',[1e-8,1e-6,1e-4,1.,100.])
@pytest.mark.parametrize('rotated',[False,True])
def test_proximidad_conserva_la_escala_de_triangulos_microscopicos(scale,rotated):
 from scipy.spatial.transform import Rotation
 R=Rotation.from_rotvec([.31,-.57,.83]).as_matrix() if rotated else np.eye(3);origin=np.array([2.4,-.0096,16.790347644]);T=np.array([[0,0,0],[2,0,0],[0,3,0.]])*scale;P=np.array([[.5,.5,.3],[1,-.2,.3]])*scale;expected=np.array([[.5,.5,0],[1,0,0.]])*scale
 tri=np.repeat((T@R.T+origin)[None,:,:],2,axis=0);p=P@R.T+origin;answer=punto_mas_cercano(tri,p);assert np.allclose(answer,expected@R.T+origin,rtol=0,atol=max(1e-13,scale*1e-8));b=baricentricas(tri,answer);assert np.all(np.isfinite(b)) and np.allclose(b.sum(1),1)

def test_proximidad_triangulo_degenerado_no_devuelve_nan():
 T=np.array([[[0,0,0],[1,0,0],[2,0,0.]]]);p=np.array([[.5,1,0.]])
 assert np.array_equal(punto_mas_cercano(T,p),[[.5,0,0.]])

def cavidad():
 outer=trimesh.creation.box(extents=[10]*3);inner=trimesh.creation.box(extents=[1]*3);inner.invert();return trimesh.util.concatenate((outer,inner))

def test_invariantes_rechazan_sacar_una_cavidad_fuera_del_material():
 from invariantes_material import InvariantesMaterial
 m=cavidad();inv=InvariantesMaterial(m);v=m.vertices.copy();void=np.unique(m.faces[inv.groups[inv.negative[0]]]);v[void]+=[20,0,0];assert not inv.comprobar(v)

def test_cota_global_rechaza_movimientos_excesivos_aunque_el_volumen_no_cambie():
 from validacion_reconstruccion import certificar_malla
 m=trimesh.creation.box();candidate=m.copy();candidate.apply_translation([.003,0,0])
 with pytest.raises(ValueError,match='presupuesto'):certificar_malla(m,candidate)

@pytest.mark.parametrize('hardlink',[False,True])
def test_worker_no_sobrescribe_referencias_ni_aliases(tmp_path,hardlink,capsys):
 from recuperacion_numerica import reconstruir
 src=tmp_path/'original.stl';src.write_bytes(trimesh.creation.box().export(file_type='stl'));before=src.read_bytes();dst=tmp_path/'salida.step'
 if hardlink:os.link(src,dst)
 else:dst=src
 report=tmp_path/'informe.json';assert reconstruir(src,src,dst,report)==2;assert src.read_bytes()==before and not report.exists()

def test_worker_rechaza_entrada_abierta_sin_publicar_step(tmp_path,capsys):
 from recuperacion_numerica import reconstruir
 m=trimesh.creation.box();m.update_faces(np.arange(1,len(m.faces)));src=tmp_path/'abierta.stl';src.write_bytes(m.export(file_type='stl'));dst=tmp_path/'salida.step';report=tmp_path/'informe.json'
 assert reconstruir(src,src,dst,report)==2 and not dst.exists();assert not json.loads(report.read_text())['ok']

def test_worker_convierte_caja_y_conserva_los_limites_originales(tmp_path,monkeypatch,capsys):
 from recuperacion_numerica import reconstruir
 monkeypatch.setenv('VISOR_PERFIL','precision');src=tmp_path/'caja.stl';src.write_bytes(trimesh.creation.box(extents=[4]*3).export(file_type='stl'));before=src.read_bytes();dst=tmp_path/'caja.step';report=tmp_path/'informe.json';assert reconstruir(src,src,dst,report)==0;r=json.loads(report.read_text());json.dumps(r,allow_nan=False);q=r['resultado']['calidad'];assert q['autointerferencias_occ'] is False and q['inspeccion_densa']['aceptado'];assert q['limites_validacion']['caja_error_max_mm']==.020 and q['limites_validacion']['volumen_error_max_pct']==.5 and q['limites_validacion']['desviacion_max_observada_mm']==.060;assert src.read_bytes()==before

def test_guardia_topologica_no_admite_rellenar_una_cavidad(tmp_path):
 import cadquery as cq
 from invariantes_material import InvariantesMaterial
 from validacion_reconstruccion import certificar_topologia_step
 m=cavidad();filled=cq.Solid.makeBox(10,10,10,cq.Vector(-5,-5,-5))
 with pytest.raises(ValueError,match='cavidades'):certificar_topologia_step(filled,m,InvariantesMaterial(m))

def test_motor_conserva_prioridad_del_cad_anterior(tmp_path,monkeypatch,capsys):
 import motor_v2 as motor,preprocesador_stl as prep,recuperacion_numerica as numeric
 src=tmp_path/'origen.stl';src.write_bytes(trimesh.creation.box().export(file_type='stl'));dst=tmp_path/'salida.step'
 def prepare(source,target):
  target.write_bytes(source.read_bytes());return target,{'reparado':True,'ruta_seleccionada':'contactos_locales_exactos_verificados','salida':{'cavidades_cerradas':0}}
 def native(source,target,log,**kwargs):target.write_text('native');return {'calidad':{},'caras_stl':12}
 monkeypatch.setattr(prep,'preparar',prepare);monkeypatch.setattr(motor,'convertir',native);monkeypatch.setattr(motor,'_calidad',lambda *a,**k:{});monkeypatch.setattr(numeric,'ejecutar_aislado',lambda *a,**k:pytest.fail('No debe sustituir un CAD ya válido'));monkeypatch.setattr(motor.sys,'argv',['motor_v2.py',str(src),str(dst)])
 assert motor.main()==0 and dst.read_text()=='native';assert json.loads(capsys.readouterr().out.splitlines()[-1])['ok']

def test_motor_activa_recuperacion_solo_despues_de_los_rechazos(tmp_path,monkeypatch,capsys):
 import motor_v2 as motor,preprocesador_stl as prep,recuperacion_numerica as numeric
 src=tmp_path/'origen.stl';src.write_bytes(trimesh.creation.box().export(file_type='stl'));dst=tmp_path/'salida.step';calls=[]
 def prepare(source,target):
  target.write_bytes(source.read_bytes());return target,{'reparado':True,'ruta_seleccionada':'contactos_locales_exactos_verificados','salida':{'cavidades_cerradas':0}}
 def native(*args,**kwargs):calls.append('native');raise ValueError('rechazo analítico')
 def recover(source,prepared,target,log):calls.append('numeric');target.write_text('verificado');return {'calidad':{},'caras_stl':12}
 monkeypatch.setattr(prep,'preparar',prepare);monkeypatch.setattr(motor,'convertir',native);monkeypatch.setattr(numeric,'ejecutar_aislado',recover);monkeypatch.setattr(motor.sys,'argv',['motor_v2.py',str(src),str(dst)]);monkeypatch.setenv('VISOR_RECUPERACION_NUMERICA','1')
 assert motor.main()==0 and calls==['native','native','numeric'];assert dst.read_text()=='verificado';assert json.loads(capsys.readouterr().out.splitlines()[-1])['ok']

@pytest.mark.parametrize('rotated',[False,True])
def test_cavidad_con_pared_subresolucion_se_recupera_sin_borrar_material(tmp_path,monkeypatch,rotated,capsys):
 from recuperacion_numerica import reconstruir
 from scipy.spatial.transform import Rotation
 monkeypatch.setenv('VISOR_PERFIL','precision');outer=trimesh.creation.box(extents=[10]*3);inner=trimesh.creation.box(extents=[.01,1,1]);inner.apply_translation([4.99499995,0,0]);inner.invert();mesh=trimesh.util.concatenate((outer,inner))
 if rotated:mesh.apply_transform(trimesh.transformations.rotation_matrix(.43,[1,2,3]))
 src=tmp_path/'caso_nuevo.stl';src.write_text(trimesh.exchange.stl.export_stl_ascii(mesh));dst=tmp_path/'salida.step';report=tmp_path/'informe.json';assert reconstruir(src,src,dst,report)==0;r=json.loads(report.read_text());assert r['topologia']['cavidades_preservadas']==1;assert r['topologia']['euler_brep']==r['topologia']['euler_malla']==4;assert r['geometria_local']['cota_global_superficie_mm']<=.002

def test_guardia_topologica_detecta_un_taladro_rellenado_con_volumen_en_tolerancia():
 import cadquery as cq
 from invariantes_material import InvariantesMaterial
 from validacion_reconstruccion import certificar_topologia_step
 outer=cq.Solid.makeBox(10,10,10,cq.Vector(-5,-5,-5));hole=cq.Solid.makeCylinder(.05,10,cq.Vector(0,0,-5));perforated=outer.cut(hole);v,f=perforated.tessellate(.001);m=trimesh.Trimesh([p.toTuple() for p in v],f,process=True);assert m.is_watertight and m.euler_number==0;assert abs(outer.Volume()-perforated.Volume())/outer.Volume()<.005
 with pytest.raises(ValueError,match='túneles'):certificar_topologia_step(outer,m,InvariantesMaterial(m))

def test_no_se_admite_un_original_abierto_con_una_preparacion_cerrada(tmp_path,capsys):
 from recuperacion_numerica import reconstruir
 closed=trimesh.creation.box();opened=closed.copy();opened.update_faces(np.arange(1,len(opened.faces)));src=tmp_path/'abierta.stl';prepared=tmp_path/'cerrada.stl';src.write_bytes(opened.export(file_type='stl'));prepared.write_bytes(closed.export(file_type='stl'));dst=tmp_path/'salida.step';report=tmp_path/'informe.json'
 assert reconstruir(src,prepared,dst,report)==2 and not dst.exists();assert 'original debe estar cerrada' in json.loads(report.read_text())['error']

def test_no_se_elimina_una_isla_material_pequena_para_forzar_un_solo_solido():
 from invariantes_material import InvariantesMaterial
 a=trimesh.creation.box();b=trimesh.creation.box(extents=[.0001]*3);b.apply_translation([2,0,0]);m=trimesh.util.concatenate((a,b))
 with pytest.raises(ValueError,match='no se descartan cuerpos'):InvariantesMaterial(m)

@pytest.mark.parametrize('alias',['destino','informe','preparado','hardlink'])
def test_motor_protege_el_original_antes_de_limpiar_salidas(tmp_path,monkeypatch,capsys,alias):
 import motor_v2 as motor
 dst=tmp_path/'salida.step';src={'destino':dst,'informe':dst.with_suffix('.entrada.json'),'preparado':dst.with_suffix('.reparado.stl'),'hardlink':tmp_path/'origen.stl'}[alias];src.write_bytes(trimesh.creation.box().export(file_type='stl'));before=src.read_bytes()
 if alias=='hardlink':os.link(src,dst)
 monkeypatch.setattr(motor.sys,'argv',['motor_v2.py',str(src),str(dst)]);assert motor.main()==2;assert src.read_bytes()==before;assert json.loads(capsys.readouterr().out)['tipo_error']=='rutas_incompatibles'

def test_recuperacion_general_sigue_al_rechazo_del_motor_historico(tmp_path,monkeypatch,capsys):
 import motor_v2 as motor,preprocesador_stl as prep,recuperacion_numerica as numeric
 src=tmp_path/'origen.stl';src.write_bytes(trimesh.creation.box().export(file_type='stl'));dst=tmp_path/'salida.step';calls=[]
 monkeypatch.setattr(prep,'preparar',lambda source,target:(source,{'reparado':False,'ruta_seleccionada':'paso_directo'}))
 def failed():calls.append('historico');print(json.dumps({'ok':False,'error':'fidelidad no superada'}));return 2
 def recover(source,prepared,target,log):calls.append('numeric');target.write_text('verificado');return {'calidad':{},'caras_stl':12}
 monkeypatch.setattr(motor,'_main_cad',failed);monkeypatch.setattr(numeric,'ejecutar_aislado',recover);monkeypatch.setattr(motor.sys,'argv',['motor_v2.py',str(src),str(dst)]);monkeypatch.setenv('VISOR_RECUPERACION_NUMERICA','1')
 assert motor.main()==0 and calls==['historico','numeric'];assert json.loads(capsys.readouterr().out.splitlines()[-1])['ok']

def test_volumen_inviable_se_rechaza_antes_de_medir_caja_o_teselar(tmp_path,monkeypatch):
 import cadquery as cq
 from motor_v2 import _calidad
 from diagnostico_validacion import ErrorGeometrico
 original=trimesh.creation.box();source=tmp_path/'original.stl';source.write_bytes(original.export(file_type='stl'));step=tmp_path/'deformado.step'
 cq.Solid.makeBox(2,2,2).exportStep(str(step))
 def expensive(*args,**kwargs):pytest.fail('No se debe medir o teselar un candidato cuyo volumen ya es inviable')
 monkeypatch.setattr(cq.Shape,'BoundingBox',expensive);monkeypatch.setattr(cq.Shape,'tessellate',expensive)
 with pytest.raises(ErrorGeometrico) as exc:_calidad(source,step,original)
 assert exc.value.criterios[0]['nombre']=='Error de volumen' and exc.value.criterios[0]['limite']==.5
