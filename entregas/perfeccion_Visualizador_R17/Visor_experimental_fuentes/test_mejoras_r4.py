"""Topología de vértices y selección automática con límites explícitos."""
from pathlib import Path
import hashlib,json,os,copy
import numpy as np
import pytest
import trimesh
from topologia_vertices import inspeccionar_vertices


@pytest.mark.parametrize('rotation',[False,True])
def test_revolucion_recupera_cilindro_completo_sin_modificar_stl(rotation):
    from revolucion_verificada import proponer,incorporar
    mesh=trimesh.creation.cylinder(radius=1,height=3,sections=32)
    axis=np.array([0.,0.,1.])
    if rotation:
        matrix=trimesh.transformations.rotation_matrix(.713,[1,2,3])
        mesh.apply_transform(matrix);axis=matrix[:3,:3]@axis
    vertices=mesh.vertices.copy();faces=mesh.faces.copy()
    result={'primitives':[{'type':'cylinder','axis':axis.tolist(),
            'faces':list(range(len(mesh.faces))),'n_faces':len(mesh.faces)}],
            'freeform_regions':[]}
    proposals=proponer(result,mesh)
    assert len(proposals)==1 and proposals[0]['type']=='cylinder'
    assert proposals[0]['max']<.004 and proposals[0]['n_faces']==64
    assert incorporar(result,mesh)
    coverage=[f for p in result['primitives'] for f in p['faces']]
    assert sorted(coverage)==list(range(len(mesh.faces)))
    assert np.array_equal(vertices,mesh.vertices) and np.array_equal(faces,mesh.faces)


def test_revolucion_no_redondea_hexagono_mecanico():
    from revolucion_verificada import proponer
    mesh=trimesh.creation.cylinder(radius=2,height=3,sections=6)
    mesh=mesh.subdivide().subdivide()
    assert not proponer({'primitives':[]},mesh)


@pytest.mark.skipif(not os.getenv('VISOR_CASOS_R4'),reason='RAR de pruebas no indicado')
def test_bandas_reales_tienen_evidencia_y_cobertura_sin_editar_vertices():
    import motor_v2
    from meshfit_detect import detect
    from revolucion_verificada import incorporar
    source=Path(os.environ['VISOR_CASOS_R4'])/'30383_alternate_fixed.stl'
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    result,mesh=detect(str(source));vertices=mesh.vertices.copy()
    bands=incorporar(result,mesh)
    assert len(bands)==5 and sum(b['tipo']=='cone' for b in bands)==3
    assert max(b['max_vertices_centroides_mm'] for b in bands)<=.011
    coverage=[f for p in result['primitives'] for f in p['faces']]
    coverage.extend(f for r in result['freeform_regions'] for f in r)
    assert len(coverage)==len(set(coverage))
    assert np.array_equal(vertices,mesh.vertices) and hashlib.sha256(source.read_bytes()).hexdigest()==digest


def test_fragmentacion_no_acepta_fewer_faces_si_empeora_error_denso():
    from revolucion_verificada import mejora
    q={'precision_alcanzada':'precision','caras_step':200,'volumen_error_pct':.01,
       'caja_error_mm':.001,'integridad_cad':{'tolerancia_max_mm':.01,'tolerancia_p95_mm':.002},
       'inspeccion_densa':{d:{'p95_mm':.012,'max_mm':.025} for d in ('stl_a_cad','cad_a_stl')}}
    other=copy.deepcopy(q);other['caras_step']=150
    assert mejora(q,other)[0]
    other['inspeccion_densa']['stl_a_cad']['max_mm']=.03
    assert not mejora(q,other)[0]


def pinzamiento_cerrado():
    mesh=trimesh.creation.icosphere(subdivisions=1)
    a=int(np.argmin(mesh.vertices[:,0]));b=int(np.argmax(mesh.vertices[:,0]))
    mesh.vertices[b]=mesh.vertices[a];mesh.merge_vertices(digits_vertex=12)
    return mesh


def test_cerrado_por_aristas_no_garantiza_vertices_manifold(tmp_path,monkeypatch):
    monkeypatch.setenv('VISOR_REPARADOR_EXACTO','0')
    from preprocesador_stl import preparar,ReparacionRechazada
    mesh=pinzamiento_cerrado();assert mesh.is_watertight and mesh.is_winding_consistent
    report=inspeccionar_vertices(mesh)
    assert report['vertices_no_manifold']==1 and report['ejemplos'][0]['abanicos']==2
    source=tmp_path/'pinzado.stl';source.write_bytes(mesh.export(file_type='stl'));digest=hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ReparacionRechazada) as rejected:preparar(source,tmp_path/'salida.stl')
    assert rejected.value.codigo=='entrada_vertices_no_manifold'
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest and not (tmp_path/'salida.stl').exists()


def test_borde_abierto_no_se_confunde_con_pinza_de_vertices():
    mesh=trimesh.creation.box();mesh.update_faces(np.arange(1,len(mesh.faces)))
    report=inspeccionar_vertices(mesh)
    assert report['vertices_no_manifold']==0 and report['vertices_de_borde']==3
    assert not report['enlaces_regulares_cerrados']


@pytest.mark.skipif(not os.getenv('VISOR_CASOS_R4'),reason='RAR de pruebas no indicado')
@pytest.mark.parametrize('name,count',[('6558_fixed.stl',33),('Dimensiones tambien.stl',14),('Pieza_Nueva_Detenida.stl',54)])
def test_vertices_reales_se_diagnostican_antes_de_reconstruir(tmp_path,name,count,monkeypatch):
    monkeypatch.setenv('VISOR_REPARADOR_EXACTO','0')
    from preprocesador_stl import preparar,ReparacionRechazada
    source=Path(os.environ['VISOR_CASOS_R4'])/name;digest=hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ReparacionRechazada) as rejected:preparar(source,tmp_path/'salida.stl')
    r=rejected.value.informe['entrada']
    assert r['estanco_global'] and r['aristas_mas_2_caras']==0
    assert r['topologia_vertices']['vertices_no_manifold']==count
    assert rejected.value.codigo=='entrada_vertices_no_manifold' and hashlib.sha256(source.read_bytes()).hexdigest()==digest


@pytest.mark.parametrize('offset,achieved',[(.005,'precision'),(.03,'impresion')])
def test_impresion_informa_precision_real_alcanzada(tmp_path,monkeypatch,offset,achieved):
    import cadquery as cq
    from motor_v2 import _calidad
    source=tmp_path/'cubo.stl';step=tmp_path/'cubo.step';mesh=trimesh.creation.box(extents=[10]*3);source.write_bytes(mesh.export(file_type='stl'))
    cq.exporters.export(cq.Workplane('XY').box(10,10,10).translate((offset,0,0)),str(step))
    monkeypatch.setenv('VISOR_PERFIL','impresion')
    q=_calidad(source,step,mesh)
    assert q['precision_alcanzada']==achieved and q['perfil_validacion']['id']=='impresion'
    assert abs(q['desviacion_max_verificada_mm']-offset)<1e-6
    assert q['limites_precision_originales']['caja_mm']==.020


def test_muestra_cad_fuera_del_recorte_se_contrasta_con_superficie_exacta(tmp_path,monkeypatch):
    import cadquery as cq
    from motor_v2 import _calidad
    mesh=trimesh.creation.annulus(r_min=1,r_max=3,height=2,sections=64);source=tmp_path/'anillo.stl';source.write_bytes(mesh.export(file_type='stl'))
    solid=cq.Workplane('XY').circle(3).circle(1).extrude(2).translate((0,0,-1)).val();step=tmp_path/'anillo.step';cq.exporters.export(solid,str(step))
    class TeseladoDefectuoso:
        def tessellate(self,*args,**kwargs):return [cq.Vector(-2,0,1),cq.Vector(2,0,1),cq.Vector(0,2,1),cq.Vector(0,.7,1)],[(0,1,2)]
        def isValid(self):return True
    monkeypatch.setattr(type(solid),'copy',lambda self:TeseladoDefectuoso())
    q=_calidad(source,step,mesh,control_avanzado=True)
    assert q['contraste_muestreo_cad']['muestras_proyectadas']>=1
    assert q['contraste_muestreo_cad']['max_distancia_al_brep_mm']>.29
    assert q['inspeccion_densa']['aceptado'] and q['limites_validacion']['desviacion_max_observada_mm']==.060


def candidatos():
    def q(faces,p95,maximum,box,level):
        return {'calidad':{'caras_step':faces,'volumen_error_pct':.01,'caja_error_mm':box,
               'integridad_cad':{'tolerancia_max_mm':.001,'tolerancia_p95_mm':.001},
               'distancia_stl_step_mm':{'p95':p95,'max_muestreado':maximum},
               'distancia_step_stl_mm':{'p95':p95,'max_muestreado':maximum},
               'tipos_caras':{'GeomAbs_Plane':faces},'precision_alcanzada':level}}
    return q(20,.025,.07,.03,'impresion'),q(25,.005,.01,.001,'precision')


@pytest.mark.parametrize('selector',['_mejora_suficiente','_comparar_candidatos_cad'])
def test_prioriza_precision_sobre_reduccion_de_caras(selector):
    import motor_v2
    old,new=candidatos();compare=getattr(motor_v2,selector)
    assert compare(old,new)[0] and not compare(new,old)[0]


def test_recuperacion_no_se_corta_automaticamente_al_superar_20000(tmp_path,monkeypatch,capsys):
    import cadquery as cq
    import motor_v2 as m
    source=tmp_path/'malla_grande.stl';step=tmp_path/'salida.step';mesh=trimesh.creation.box(extents=[10]*3)
    for _ in range(6):mesh=mesh.subdivide()
    assert len(mesh.faces)==49152;source.write_bytes(mesh.export(file_type='stl'))
    calls=[]
    def construir(src,dst,log,**kw):
        calls.append(kw)
        if len(calls)==1:raise ValueError('El motor B-Rep no ha reconstruido un sólido CAD válido.')
        cq.exporters.export(cq.Workplane('XY').box(10,10,10),str(dst))
        return {'caras_stl':len(mesh.faces),'modo':'superficies','calidad':m._calidad(src,dst,mesh,control_avanzado=True)}
    monkeypatch.setattr(m,'convertir',construir);monkeypatch.setattr(m.sys,'argv',['motor_v2.py',str(source),str(step)])
    assert m._main_cad()==0 and len(calls)==2 and calls[1]['flat_tol_deg']==1.3
    assert calls[1]['control_avanzado'] and step.exists()
    result=json.loads(capsys.readouterr().out.splitlines()[-1]);assert result['ok']


def test_busca_precision_automaticamente_en_uso_impresion(tmp_path,monkeypatch,capsys):
    import cadquery as cq
    import motor_v2 as m
    source=tmp_path/'cubo.stl';target=tmp_path/'salida.step';mesh=trimesh.creation.box(extents=[10]*3);source.write_bytes(mesh.export(file_type='stl'))
    monkeypatch.setenv('VISOR_PERFIL','impresion');calls=[]
    def construir(src,dst,log,**kw):
        calls.append(kw)
        offset=.03 if len(calls)==1 else 0.
        cq.exporters.export(cq.Workplane('XY').box(10,10,10).translate((offset,0,0)),str(dst))
        return {'caras_stl':len(mesh.faces),'modo':'superficies','calidad':m._calidad(src,dst,mesh,control_avanzado=True)}
    monkeypatch.setattr(m,'convertir',construir);monkeypatch.setattr(m.sys,'argv',['motor_v2.py',str(source),str(target)])
    assert m._main_cad()==0 and len(calls)==2
    result=json.loads(capsys.readouterr().out.splitlines()[-1])['resultado']
    assert result['calidad']['perfil_validacion']['id']=='impresion'
    assert result['calidad']['precision_alcanzada']=='precision' and result['calidad']['caja_error_mm']<1e-6


def test_api_guarda_original_y_causa_de_vertices_pinzdos(tmp_path,monkeypatch):
    monkeypatch.setenv('VISOR_REPARADOR_EXACTO','0')
    from fastapi.testclient import TestClient
    import servidor
    monkeypatch.setattr(servidor,'LOG_DIR',tmp_path)
    raw=pinzamiento_cerrado().export(file_type='stl')
    with TestClient(servidor.app) as client:
        response=client.post('/convertir',files={'archivo':('pinzado.stl',raw)},data={'perfil':'precision'})
        assert response.status_code==422 and 'vértices no manifold' in response.json()['detail']
        meta=json.loads(next(p for p in tmp_path.glob('*.json') if not p.name.endswith('.entrada.json')).read_text())
        assert meta['tipo_error']=='entrada_vertices_no_manifold'
        saved=client.get(meta['archivos_reparacion']['original']);assert saved.status_code==200 and saved.content==raw
        assert not list(tmp_path.glob('*.step')) and 'reparado' not in meta['archivos_reparacion']
