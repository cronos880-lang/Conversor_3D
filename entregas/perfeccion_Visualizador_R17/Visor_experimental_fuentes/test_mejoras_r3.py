"""Pruebas de aceptación de perfiles, diagnósticos, tiempo y medidas exactas."""
import io,json,os,subprocess,sys
from pathlib import Path
import numpy as np
import pytest
import trimesh
from politica_conversion import presupuesto_conversion
from perfiles_precision import obtener_perfil


def test_perfil_precision_por_defecto_y_nombre_invalido(monkeypatch):
    monkeypatch.delenv('VISOR_PERFIL',raising=False)
    assert obtener_perfil()['id']=='precision'
    with pytest.raises(ValueError):obtener_perfil('perfil_inexistente')


@pytest.mark.parametrize('perfil',['precision','impresion'])
def test_perfil_no_autoriza_tapar_aberturas_ambiguas(tmp_path,monkeypatch,perfil):
    from preprocesador_stl import preparar,ReparacionRechazada
    mesh=trimesh.creation.box();mesh.update_faces(np.arange(1,len(mesh.faces)))
    source=tmp_path/'abierta.stl';source.write_bytes(mesh.export(file_type='stl'))
    monkeypatch.setenv('VISOR_PERFIL',perfil)
    with pytest.raises(ReparacionRechazada):preparar(source,tmp_path/'cerrada.stl')


def test_desplazamiento_admitido_solo_en_perfil_impresion(tmp_path,monkeypatch):
    import cadquery as cq
    from motor_v2 import _calidad
    from diagnostico_validacion import ErrorGeometrico
    src=tmp_path/'cubo.stl';step=tmp_path/'cubo.step'
    mesh=trimesh.creation.box(extents=[10,10,10]);src.write_bytes(mesh.export(file_type='stl'))
    cq.exporters.export(cq.Workplane('XY').box(10,10,10).translate((.03,0,0)),str(step))
    monkeypatch.setenv('VISOR_PERFIL','precision')
    with pytest.raises(ErrorGeometrico) as rejected:_calidad(src,step,mesh)
    assert any(c['nombre']=='Desviación de cotas exteriores' and not c['cumple'] for c in rejected.value.criterios)
    monkeypatch.setenv('VISOR_PERFIL','impresion')
    q=_calidad(src,step,mesh)
    assert q['perfil_validacion']['id']=='impresion' and q['limites_validacion']['caja_error_max_mm']==.04
    assert q['inspeccion_densa']['aceptado'] and q['volumen_error_pct']<1e-6


def test_diagnostico_no_acusa_cota_que_si_cumple():
    from diagnostico_validacion import ErrorGeometrico,criterio
    e=ErrorGeometrico('Reconstrucción deformada',[criterio('Volumen',.7,.5,'%'),criterio('Cotas',.0075,.020)])
    assert 'Volumen' in str(e) and 'Cotas' not in str(e)
    assert e.criterios[1]['cumple'] and e.criterios[1]['unidad']=='mm'


def test_presupuesto_misma_malla_ascii_binario_y_crece_con_complejidad():
    m=trimesh.creation.box()
    binary=m.export(file_type='stl');ascii=m.export(file_type='stl_ascii').encode().replace(b'facet normal',b'facet   normal')
    assert presupuesto_conversion(binary)==presupuesto_conversion(ascii)
    complex_mesh=trimesh.creation.icosphere(subdivisions=5)
    assert presupuesto_conversion(complex_mesh.export(file_type='stl'))['inicial_s']>presupuesto_conversion(binary)['inicial_s']
    with pytest.raises(ValueError):presupuesto_conversion(b'archivo no STL')


def test_no_repite_construccion_identica_y_distingue_perfil(tmp_path,monkeypatch):
    from intentos_conversion import evitar_repetidos
    source=tmp_path/'modelo.stl';source.write_bytes(b'malla_de_regresion_unica');calls=[]
    @evitar_repetidos
    def build(path_stl,path_step,log,*,digital=False):
        calls.append(digital);raise ValueError('Fallo de construcción reproducible')
    monkeypatch.setenv('VISOR_PERFIL','precision')
    log=io.StringIO()
    for _ in range(2):
        with pytest.raises(ValueError):build(source,tmp_path/'salida.step',log)
    assert len(calls)==1 and 'Reintento omitido' in log.getvalue()
    monkeypatch.setenv('VISOR_PERFIL','impresion')
    with pytest.raises(ValueError):build(source,tmp_path/'otra.step',log)
    assert len(calls)==2


def test_reutilizar_shell_conserva_distancias_exactas():
    import cadquery as cq
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.gp import gp_Pnt
    from validacion_local import _distancias_cad
    solid=cq.Workplane('XY').box(10,10,5).faces('>Z').workplane().hole(2).val()
    points=np.random.default_rng(32).uniform([-6,-6,-4],[6,6,4],size=(70,3))
    reference=[]
    for p in points:
        e=BRepExtrema_DistShapeShape(BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float,p))).Vertex(),solid.Shells()[0].wrapped)
        e.Perform();assert e.IsDone();reference.append(e.Value())
    assert np.allclose(_distancias_cad(solid,points),reference,atol=1e-10,rtol=0)


def test_teselacion_que_cruza_un_hueco_no_inventa_error_del_cad(monkeypatch):
    import cadquery as cq
    from validacion_densa import inspeccionar_denso
    mesh=trimesh.creation.annulus(r_min=1,r_max=3,height=2,sections=64)
    solid=cq.Workplane('XY').circle(3).circle(1).extrude(2).translate((0,0,-1)).val()
    class TeseladoDefectuoso:
        def tessellate(self,*args,**kwargs):
            return [cq.Vector(-2,0,1),cq.Vector(2,0,1),cq.Vector(0,2,1)],[(0,1,2)]
    monkeypatch.setattr(type(solid),'copy',lambda self:TeseladoDefectuoso())
    report=inspeccionar_denso(mesh,solid,limite_p95=.02,limite_max=.06)
    assert report['aceptado'] and report['contraste_muestras_cad']['muestras_proyectadas']>=1
    assert report['contraste_muestras_cad']['max_distancia_al_brep_mm']>.3


@pytest.mark.skipif(not os.getenv('VISOR_FIXTURE_RESCATE_R3'),reason='STEP defectuoso aportado no indicado')
def test_rescate_exige_repetir_control_avanzado():
    from motor_v2 import _calidad
    from saneamiento_cad import InterferenciasCAD
    step=Path(os.environ['VISOR_FIXTURE_RESCATE_R3'])
    source=Path(os.environ['VISOR_CASOS_R3'])/'Con fallos pero si step.stl'
    with pytest.raises(InterferenciasCAD) as rejected:
        _calidad(source,step,trimesh.load(source,force='mesh'),control_avanzado=True)
    assert rejected.value.cantidad==32


@pytest.mark.parametrize('busy',[False,True])
def test_tiempo_solo_amplia_con_cpu_y_siempre_detiene_arbol(busy):
    from control_recursos import comunicar_vigilado,LimiteRecursos
    from servidor import _detener_arbol
    command="print('listo',flush=True)\nwhile True: pass" if busy else "import time;print('listo',flush=True);time.sleep(10)"
    proc=subprocess.Popen([sys.executable,'-c',command],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                          start_new_session=os.name!='nt',creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0)
    updates=[]
    try:
        assert proc.stdout.readline().strip()=='listo'
        with pytest.raises(LimiteRecursos) as rejected:
            comunicar_vigilado(proc,.3,_detener_arbol,politica={'maximo_s':.6,'incremento_s':.1},informar=updates.append)
        assert rejected.value.codigo=='tiempo_agotado' and proc.poll() is not None
        if busy:assert updates
        else:assert not updates
        assert all(u['plazo_actual_s']<=.6 for u in updates)
    finally:_detener_arbol(proc)
