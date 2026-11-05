from pathlib import Path
import hashlib
import numpy as np,pytest,trimesh
from saneamiento_malla import resolver_costuras,quitar_redundancias,verificar_envolventes,LIMITE_LOCAL_MM
from preprocesador_stl import preparar,ReparacionRechazada,cargar_exacto

def costura(eps=2e-6):
    m=trimesh.creation.box();a,b,c=m.faces[0];V=np.vstack((m.vertices,(m.vertices[a]+m.vertices[b])/2+eps*m.face_normals[0]));mid=len(V)-1
    return trimesh.Trimesh(V,np.vstack((m.faces[1:],[[a,mid,c],[mid,b,c]])),process=False)

@pytest.mark.parametrize('rotacion',[False,True])
def test_costura_se_cierra_subdividiendo_sin_tapa(rotacion):
    m=costura()
    if rotacion:m.apply_transform(trimesh.transformations.rotation_matrix(.57,[2,3,5]));m.apply_translation([117,-73,41])
    n,r=resolver_costuras(m)
    assert not m.is_watertight and n.is_watertight and n.is_winding_consistent
    assert n.euler_number==2 and abs(n.volume-1)<1e-10
    assert len(n.faces)==len(m.faces)+1 and r['cota_global_superficie_mm']<=LIMITE_LOCAL_MM
    assert all(x['sin_cara_de_tapa'] for x in r['costuras'])

def test_costura_no_admite_una_separacion_mayor():
    m=costura(.001);n,r=resolver_costuras(m)
    assert not r['aplicado'] and n is m and not n.is_watertight

def test_un_agujero_triangular_real_no_se_tapa(tmp_path):
    m=trimesh.creation.box();m.update_faces(np.arange(1,len(m.faces)));src=tmp_path/'abierta.stl';m.export(src)
    with pytest.raises(ReparacionRechazada,match='Borde abierto'):preparar(src,tmp_path/'out.stl')

def test_degeneradas_sobre_aristas_no_mueven_geometria():
    m=trimesh.creation.box();bad=trimesh.Trimesh(m.vertices,np.vstack((m.faces,[[0,0,1]])),process=False)
    n,r=quitar_redundancias(bad)
    assert r['degeneradas_exactas']==1 and r['vertices_movidos']==0 and n.is_watertight
    assert np.array_equal(n.faces,m.faces) and np.array_equal(n.vertices,m.vertices)

def test_cadena_opuesta_interna_no_cambia_campo_material():
    import igl
    m=trimesh.creation.box();face=[0,3,5];bad=trimesh.Trimesh(m.vertices,np.vstack((m.faces,face,face[::-1])),process=False)
    n,r=quitar_redundancias(bad);points=np.random.default_rng(2026).uniform(-1,1,(100,3))
    a=igl.winding_number(np.asarray(bad.vertices),np.asarray(bad.faces),points);b=igl.winding_number(np.asarray(n.vertices),np.asarray(n.faces),points)
    assert r['caras_cadena_orientada_nula']==2 and np.max(abs(a-b))<1e-12
    assert np.array_equal(m.faces,n.faces) and abs(m.volume-n.volume)<1e-14

def test_no_descarta_lamina_cuyos_vertices_estan_fuera_del_cuerpo():
    m=trimesh.creation.box();V=np.vstack((m.vertices,[[3,0,0],[3,1,0],[3,0,1]]));bad=trimesh.Trimesh(V,np.vstack((m.faces,[8,9,10],[10,9,8])),process=False)
    with pytest.raises(ValueError,match='vértices ajenos'):quitar_redundancias(bad)

def test_una_isla_positiva_microscopica_se_conserva_y_rechaza(tmp_path):
    a=trimesh.creation.box();b=trimesh.creation.box(extents=[.0002]*3);b.apply_translation([3,0,0]);m=trimesh.util.concatenate((a,b));n,r=quitar_redundancias(m)
    assert n is m and not r['aplicado'];src=tmp_path/'isla.stl';m.export(src)
    with pytest.raises(ReparacionRechazada):preparar(src,tmp_path/'out.stl')

def test_no_retirar_triangulos_validos_por_su_area_pequena():
    m=trimesh.creation.box(extents=[1,1,1e-10]);n,r=quitar_redundancias(m)
    assert n is m and not r['aplicado'] and len(n.faces)==12

def cavidades():
    outer=trimesh.creation.box(extents=[10]*3);holes=[]
    for x in (-2,0,2):
        hole=trimesh.creation.icosphere(subdivisions=1,radius=.4);hole.apply_translation([x,0,0]);hole.invert();holes.append(hole)
    return trimesh.util.concatenate((outer,*holes))

@pytest.mark.parametrize('rotacion',[False,True])
def test_envolventes_negativas_validas_se_conservan_sin_invertir(tmp_path,rotacion):
    m=cavidades()
    if rotacion:m.apply_transform(trimesh.transformations.rotation_matrix(.43,[1,3,2]))
    src=tmp_path/'hueca.stl';m.export(src);before=src.read_bytes();selected,r=preparar(src,tmp_path/'out.stl')
    assert selected==src and not r['reparado'] and r['verificacion_envolventes']['cavidades_cerradas']==3
    assert src.read_bytes()==before and not (tmp_path/'out.stl').exists()

def test_una_envolvente_negativa_fuera_del_solido_no_es_cavidad(tmp_path):
    m=cavidades();part=trimesh.creation.box();part.apply_translation([20,0,0]);part.invert();bad=trimesh.util.concatenate((m,part));src=tmp_path/'fuera.stl';bad.export(src)
    with pytest.raises(ReparacionRechazada,match='envolventes'):preparar(src,tmp_path/'out.stl')

def test_cavidades_negativas_una_dentro_de_otra_son_ambiguas(tmp_path):
    outer=trimesh.creation.box(extents=[10]*3);a=trimesh.creation.box(extents=[3]*3);b=trimesh.creation.box();a.invert();b.invert();m=trimesh.util.concatenate((outer,a,b));src=tmp_path/'doble.stl';m.export(src)
    with pytest.raises(ReparacionRechazada,match='anidadas'):preparar(src,tmp_path/'out.stl')

def test_serializacion_de_costura_y_original_intacto(tmp_path):
    m=costura();src=tmp_path/'precision_ascii.stl'
    src.write_text(trimesh.exchange.stl.export_stl_ascii(m),encoding='ascii');before=hashlib.sha256(src.read_bytes()).hexdigest()
    selected,r=preparar(src,tmp_path/'out.stl')
    assert r['reparado'] and cargar_exacto(selected).is_watertight and hashlib.sha256(src.read_bytes()).hexdigest()==before

def test_autointerseccion_real_se_rechaza_en_frio_antes_del_mallado():
    from motor_v2 import _calidad
    from saneamiento_cad import InterferenciasCAD
    import os
    root=Path(os.getenv('VISOR_BATERIA_EXTERNA',str(Path(__file__).resolve().parent.parent/'material_pruebas/bateria_externa')));src=root/'stl_sanos/17_barrido_spline.stl';step=root/'resultados_sanos/17_barrido_spline.step'
    if not src.exists() or not step.exists():pytest.skip('Fixture CAD externo no disponible')
    before=hashlib.sha256(step.read_bytes()).hexdigest()
    with pytest.raises(InterferenciasCAD) as exc:_calidad(src,step,cargar_exacto(src))
    assert exc.value.calidad['lectura_fria'] and hashlib.sha256(step.read_bytes()).hexdigest()==before

@pytest.mark.parametrize('extra',['arista','cara'])
def test_importacion_no_oculta_objetos_sueltos_al_seleccionar_solids(tmp_path,extra):
    import cadquery as cq
    from calidad_topologica import leer_solido_step_estricto
    body=cq.Workplane('XY').box(2,2,2).val()
    auxiliary=cq.Edge.makeLine((20,0,0),(30,0,0)) if extra=='arista' else cq.Workplane('XY').rect(2,2).extrude(.1).val().Faces()[0].translate((20,0,0))
    path=tmp_path/'mezcla.step';cq.Compound.makeCompound([body,auxiliary]).exportStep(str(path))
    assert len(cq.importers.importStep(str(path)).solids().vals())==1
    with pytest.raises(ValueError,match='objetos sueltos'):leer_solido_step_estricto(path)

def test_contenedor_con_un_solo_solido_se_admite(tmp_path):
    import cadquery as cq
    from calidad_topologica import leer_solido_step_estricto
    body=cq.Workplane('XY').box(2,2,2).val();path=tmp_path/'contenedor.step';cq.Compound.makeCompound([body]).exportStep(str(path))
    assert abs(leer_solido_step_estricto(path).Volume()-8)<1e-10

def test_trabajador_reproduce_costura_pero_no_acepta_tapa_arbitraria(tmp_path,monkeypatch,capsys):
    from recuperacion_numerica import reconstruir
    monkeypatch.setenv('VISOR_PERFIL','precision');m=costura();source=tmp_path/'original.stl';source.write_text(trimesh.exchange.stl.export_stl_ascii(m),encoding='ascii')
    closed,_=resolver_costuras(m);prepared=tmp_path/'cerrada.stl';prepared.write_text(trimesh.exchange.stl.export_stl_ascii(closed),encoding='ascii')
    out=tmp_path/'resultado.step';report=tmp_path/'resultado.json'
    assert reconstruir(source,prepared,out,report)==0
    import json
    r=json.loads(report.read_text());assert r['normalizacion_referencia_material']['costuras']['aplicado']
    assert r['resultado']['calidad']['limites_validacion']['desviacion_max_observada_mm']==.060
