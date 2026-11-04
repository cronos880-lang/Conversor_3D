"""Puertas de calidad del reparador R5, incluidos los dos archivos reales."""
from pathlib import Path
import hashlib,json,os
import numpy as np
import pytest,trimesh
from reparacion_contactos_locales import descomponer_contactos,contraer_microaristas_generadas
from preprocesador_stl import cargar_exacto

@pytest.mark.parametrize('rotate',[False,True])
def test_descomposicion_de_contacto_por_arista_conserva_todas_las_superficies(rotate):
    a=trimesh.creation.box(extents=[2]*3);b=a.copy();b.apply_translation([2,2,0]);mesh=trimesh.util.concatenate((a,b));mesh.merge_vertices(digits_vertex=12)
    if rotate:mesh.apply_transform(trimesh.transformations.rotation_matrix(.47,[1,2,3]))
    before=mesh.triangles.copy();candidate,report=descomponer_contactos(mesh)
    from topologia_vertices import inspeccionar_vertices
    assert candidate.is_watertight and candidate.is_winding_consistent
    assert inspeccionar_vertices(candidate)['vertices_no_manifold']==0 and report['aristas_de_contacto']
    assert abs(candidate.volume-16)<1e-10 and np.array_equal(before,mesh.triangles)
    for tri,source in zip(candidate.triangles,report['superficies_fuente']):
        plane=mesh.face_normals[source];origin=mesh.triangles[source,0]
        assert np.max(np.abs((tri-origin)@plane))<1e-10


def test_control_exacto_no_considera_exito_una_malla_abierta(tmp_path):
    from reparador_exacto_aislado import ControlExacto
    mesh=trimesh.creation.box();mesh.update_faces(np.arange(1,len(mesh.faces)))
    with pytest.raises(ValueError,match='cerrada válida'):ControlExacto(mesh,tmp_path/'abierta.off')


def test_worker_rechaza_aberturas_y_entrega_informe_completo(tmp_path):
    from reparador_exacto_aislado import ejecutar
    mesh=trimesh.creation.box();mesh.update_faces(np.arange(1,len(mesh.faces)))
    source=tmp_path/'abierta.stl';source.write_bytes(mesh.export(file_type='stl'));digest=hashlib.sha256(source.read_bytes()).hexdigest();out=tmp_path/'salida.stl';report=tmp_path/'informe.json'
    assert ejecutar(source,out,report)==2
    r=json.loads(report.read_text());assert not r['reparado'] and not out.exists() and 'cerrada' in r['error']
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest


@pytest.mark.parametrize('name',['6558_fixed','Pieza_Nueva_Detenida'])
def test_dos_reparaciones_reales_reimportadas_sin_intersecciones(name,tmp_path):
    from reparador_exacto_aislado import ControlExacto,medidas_superficie,validar_material
    root=Path(os.environ['VISOR_RESULTADOS_R5']);source=Path(os.environ['VISOR_CASOS_R5'])/(name+'.stl');path=root/(name+'.reparado.stl');report=json.loads((root/(name+'.json')).read_text())
    assert report['reparado'] and report['cad_certificado'] is False
    assert hashlib.sha256(source.read_bytes()).hexdigest()==report['original_sha256']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==report['reparado_sha256']
    m=cargar_exacto(path);assert m.is_watertight and m.is_winding_consistent
    control=ControlExacto(m,tmp_path/'control.off');assert not control.pares()
    q=medidas_superficie(cargar_exacto(source),m)
    assert q['max_mm']<=.060 and q['p95_mm']<=.020
    proof=validar_material(cargar_exacto(source),m,[])
    assert proof['discrepancias']==0 and proof['puntos']>2000
    assert report['validacion_frontera']['max_mm']<=.002 and report['validacion_frontera']['volumen_error_pct']<=.001


def test_una_entrada_sana_no_invoca_el_worker(tmp_path,monkeypatch):
    import preprocesador_stl as p,subprocess
    source=tmp_path/'sana.stl';source.write_bytes(trimesh.creation.box().export(file_type='stl'));digest=source.read_bytes()
    monkeypatch.setattr(subprocess,'run',lambda *a,**k:pytest.fail('No debe reconstruir una malla sana'))
    chosen,report=p.preparar(source,tmp_path/'otra.stl')
    assert chosen==source and not report['reparado'] and source.read_bytes()==digest


def test_cad_rechazado_conserva_stl_y_no_publica_step(tmp_path,monkeypatch,capsys):
    monkeypatch.setenv('VISOR_RECUPERACION_NUMERICA','0')
    import motor_v2 as m,preprocesador_stl as p
    source=tmp_path/'source.stl';source.write_bytes(trimesh.creation.box().export(file_type='stl'));dst=tmp_path/'salida.step';calls=[]
    def prepare(src,out):
        out.write_bytes(src.read_bytes())
        return out,{'reparado':True,'ruta_seleccionada':'contactos_locales_exactos_verificados','salida':{'caras':12,'cavidades_cerradas':0}}
    def fail(*args,**kwargs):calls.append(kwargs);raise ValueError('CAD inválido de referencia')
    monkeypatch.setattr(p,'preparar',prepare);monkeypatch.setattr(m,'convertir',fail);monkeypatch.setattr(m.sys,'argv',['motor_v2.py',str(source),str(dst)])
    assert m.main()==2
    result=json.loads(capsys.readouterr().out.splitlines()[-1])
    assert result['tipo_error']=='cad_pendiente_tras_reparacion' and not result['ok']
    assert len(calls)==2 and all(c['control_avanzado'] and c['conservar_vertices'] for c in calls)
    assert dst.with_suffix('.reparado.stl').exists() and not dst.exists()


def test_no_desaparece_un_cuerpo_positivo_microscopico():
    vertices=np.array([[0,0,0],[1e-8,0,0],[0,1,0],[0,0,1.]])
    tiny=trimesh.Trimesh(vertices,[[0,2,1],[0,1,3],[0,3,2],[1,2,3]],process=False)
    assert tiny.is_watertight and tiny.volume>0
    candidate,_=contraer_microaristas_generadas(tiny,limite_mm=1e-6)
    assert candidate.is_watertight and candidate.volume>0 and len(candidate.faces)==4
