"""Regresiones de fondos coincidentes, contactos y caché de teselación CAD."""
from pathlib import Path
import os
import hashlib
import numpy as np
import pytest
import trimesh
from regularizacion_planar import regularizar_cancelaciones_planas
from contactos_numericos import normalizar_contactos_solapados
from preprocesador_stl import componentes, _manifold, cargar_exacto, preparar
from verificacion_reparacion import distancia_malla, puntos_superficie, solido_poliedrico


def fondo_cavidad(espesor=0.):
    """Anillo con dos discos de fondo; espesor cero = caras superpuestas."""
    import shapely
    from scipy.spatial import cKDTree
    ring=trimesh.creation.annulus(r_min=1.,r_max=3.,height=2.,sections=24)
    bottom=ring.vertices[:,2].min()
    cap=np.all(abs(ring.triangles[:,:,2]-bottom)<1e-10,axis=1)
    ids=np.unique(ring.faces[cap])
    radius=np.linalg.norm(ring.vertices[ids,:2],axis=1)
    tree=cKDTree(ring.vertices)
    disks=[]
    for wanted,orientation in ((3.,-1),(1.,1)):
        vertices=ids[abs(radius-wanted)<1e-8]
        points=ring.vertices[vertices,:2]
        points=points[np.argsort(np.arctan2(points[:,1],points[:,0]))]
        for tri in shapely.constrained_delaunay_triangles(shapely.Polygon(points)).geoms:
            uv=np.asarray(tri.exterior.coords)[:3]
            _,face=tree.query(np.column_stack((uv,np.full(3,bottom))))
            xyz=ring.vertices[face]
            if np.cross(xyz[1]-xyz[0],xyz[2]-xyz[0])[2]*orientation<0:face=face[::-1]
            disks.append(face)
    mesh=trimesh.Trimesh(ring.vertices.copy(),np.vstack((ring.faces[~cap],disks)),process=False)
    inner=ids[abs(radius-1)<1e-8]
    mesh.vertices[inner,2]+=espesor
    assert mesh.is_watertight and mesh.is_winding_consistent
    return mesh,ring


def test_cancelacion_plana_conserva_anillo_y_frontera():
    mesh,expected=fondo_cavidad()
    vertices,faces=mesh.vertices.copy(),mesh.faces.copy()
    fixed,report=regularizar_cancelaciones_planas(mesh)
    assert report['aplicado'] and fixed.euler_number==0
    assert all(p['frontera_orientada_identica'] for p in report['parches'])
    assert abs(mesh.volume-fixed.volume)<1e-10
    assert np.array_equal(mesh.vertices,vertices) and np.array_equal(mesh.faces,faces)
    assert {tuple(p) for p in fixed.vertices}<={tuple(p) for p in vertices}
    assert max(distancia_malla(fixed,puntos_superficie(expected)).max(),
               distancia_malla(expected,puntos_superficie(fixed)).max())<1e-9
    assert solido_poliedrico(fixed).isValid()


def test_no_elimina_fondo_fino_real():
    mesh,_=fondo_cavidad(.0001)
    candidate,report=regularizar_cancelaciones_planas(mesh)
    assert not report['aplicado'] and candidate is mesh
    assert mesh.euler_number==2 and solido_poliedrico(mesh).isValid()


@pytest.mark.parametrize('offset',[[10.000001,0,0],[10,10,0],[10,10,10]])
def test_contactos_numericos_no_cierran_separaciones(offset):
    a=trimesh.creation.box(extents=[10,10,10]);b=a.copy().apply_translation(offset)
    source=trimesh.util.concatenate([a,b])
    candidate,restore,proof=normalizar_contactos_solapados(source)
    assert not proof['aplicado'] and candidate is source and np.array_equal(restore,np.eye(4))


def test_estabilizacion_solo_con_contacto_preexistente():
    a=trimesh.creation.box(extents=[10,10,10]);b=a.copy().apply_translation([9.9999999,0,0])
    source=trimesh.util.concatenate([a,b])
    normalized,restore,proof=normalizar_contactos_solapados(source)
    assert proof['aplicado'] and proof['max_movimiento_mm']<=proof['limite_movimiento_mm']
    assert proof['uniones_por_cercania']==0
    solids=[_manifold(p) for p in componentes(normalized)]
    united=solids[0]+solids[1]
    assert len(united.decompose())==1 and abs(united.volume()-1999.99999)<1e-7
    assert np.allclose(restore[:3,:3].T@restore[:3,:3],np.eye(3),atol=1e-12)


@pytest.mark.skipif(not os.getenv('VISOR_CASOS_R2'),reason='STL aportados no indicados')
@pytest.mark.parametrize('name',['Fallo_Dimensional.stl','Pieza ambigua.stl'])
def test_reparacion_real_r2_contrasta_original(tmp_path,name):
    source=Path(os.environ['VISOR_CASOS_R2'])/name
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    selected,report=preparar(source,tmp_path/'reparado.stl')
    assert report['reparado'] and report['verificacion_stl_reimportado']['max_observado_mm']<.002
    assert report['salida']['numero_componentes']==1
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    if name=='Pieza ambigua.stl':
        assert len(report['verificacion_stl_reimportado']['regularizaciones_planas_referencia'])==4
        assert cargar_exacto(selected).euler_number==-16  # nueve túneles de la unión física


@pytest.mark.skipif(not os.getenv('VISOR_FIXTURE_CACHE_R2'),reason='STEP de regresión de caché no indicado')
def test_muestreo_no_corrompe_juicio_del_brep(tmp_path,monkeypatch):
    import cadquery as cq
    from motor_v2 import _calidad
    source=Path(os.environ['VISOR_CASOS_R2'])/'4600_fixed.stl'
    step=Path(os.environ['VISOR_FIXTURE_CACHE_R2'])
    digest=hashlib.sha256(step.read_bytes()).hexdigest()
    shape=cq.importers.importStep(str(step)).solids().val()
    assert shape.isValid()
    sampled=shape.copy();sampled.tessellate(.010)
    assert not sampled.isValid() and shape.isValid()  # reproduce el falso rechazo previo
    progress=tmp_path/'avance.jsonl';monkeypatch.setenv('VISOR_AVANCE_PATH',str(progress))
    # Aislar la caché no autoriza a ignorar las interferencias geométricas
    # adicionales del candidato. Debe rechazarse por ese motivo real.
    from saneamiento_cad import InterferenciasCAD
    with pytest.raises(InterferenciasCAD) as rejected:
        _calidad(source,step,trimesh.load(source,force='mesh'))
    q=rejected.value.calidad
    assert rejected.value.cantidad>0
    assert q['integridad_cad']['brep_valido'] and q['integridad_cad']['solidos']==1
    assert q['limites_validacion']['caja_error_max_mm']==.020
    assert q['limites_validacion']['volumen_error_max_pct']==.5
    assert '700/800 puntos' in progress.read_text()
    assert hashlib.sha256(step.read_bytes()).hexdigest()==digest


@pytest.mark.skipif(not os.getenv('VISOR_FIXTURE_DENSO_R2'),reason='STEP de regresión densa no indicado')
def test_no_acepta_cad_solo_por_ser_valido_sin_interferencias():
    import cadquery as cq
    from saneamiento_cad import comprobar_interferencias
    from validacion_densa import exigir_denso
    step=Path(os.environ['VISOR_FIXTURE_DENSO_R2'])
    mesh=trimesh.load(step.with_suffix('.reparado.stl'),force='mesh')
    solid=cq.importers.importStep(str(step)).solids().val()
    assert solid.isValid() and comprobar_interferencias(solid)==(True,0)
    with pytest.raises(ValueError,match='Inspección densa rechazada') as rejected:
        exigir_denso(mesh,solid,limite_p95=.020,limite_max=.060)
    report=rejected.value.informe_denso
    assert not report['aceptado'] and report['stl_a_cad']['max_mm']>.3
    assert report['limite_max_mm']==.060
