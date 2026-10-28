"""Casos positivos y negativos sin red; geometría real con OCC y Manifold."""
from pathlib import Path
import os
import subprocess
import sys
import time
import numpy as np
import pytest
import trimesh
from preprocesador_stl import (cargar_exacto, diagnosticar, preparar,
                               reparar_agujero_local, unir_cerrados, ReparacionRechazada)
from control_recursos import comunicar_vigilado, LimiteRecursos


def canonical(mesh):
    v, inverse = np.unique(mesh.vertices, axis=0, return_inverse=True)
    return trimesh.Trimesh(v, inverse[mesh.faces], process=False)


def boxes(offset):
    a = trimesh.creation.box(extents=[10, 10, 10])
    b = a.copy()
    b.apply_translation(offset)
    return trimesh.util.concatenate([a, b])


def test_diagnostico_no_repara_agujeros_al_separar():
    m = trimesh.creation.box()
    m.update_faces(np.arange(len(m.faces)) != 0)
    before = m.faces.copy()
    d = diagnosticar(m)
    assert d['aristas_1_cara'] == 3
    assert not d['componentes'][0]['estanco']
    assert np.array_equal(before, m.faces)


def test_duplicados_degenerados_orientacion():
    box = trimesh.creation.box()
    duplicate = trimesh.Trimesh(box.vertices, np.vstack([box.faces, box.faces[:1]]), process=False)
    assert diagnosticar(duplicate)['caras_duplicadas'] == 1
    assert diagnosticar(duplicate)['aristas_mas_2_caras'] == 3
    deg = trimesh.Trimesh(box.vertices, np.vstack([box.faces, [0, 0, 1]]), process=False)
    assert diagnosticar(deg)['caras_degeneradas'] == 1
    box.invert()
    assert diagnosticar(box)['ruta'] == 'rechazar_orientacion'


def test_paso_directo_bytes_identicos(tmp_path):
    src = tmp_path/'box.stl'
    trimesh.creation.box().export(src)
    before = src.read_bytes()
    target = tmp_path/'reparado.stl'
    selected, rep = preparar(src, target)
    assert selected == src and not rep['reparado']
    assert src.read_bytes() == before and not target.exists()


@pytest.mark.parametrize('offset,volume', [([10, 0, 0], 2000), ([8, 0, 0], 1800)])
@pytest.mark.parametrize('rotation', [None, [.37, -.61, 1.03]])
def test_union_contacto_solapamiento_rotados(offset, volume, rotation):
    source = boxes(offset)
    if rotation:
        source.apply_transform(trimesh.transformations.euler_matrix(*rotation))
    source = canonical(source)
    result, rep = unir_cerrados(source)
    d = diagnosticar(result)
    assert d['ruta'] == 'paso_directo' and d['numero_componentes'] == 1
    assert abs(result.volume-volume) < 1e-5
    assert rep['max_observado_mm'] < .002


@pytest.mark.parametrize('offset', [[10.000001, 0, 0], [10.001, 0, 0], [12, 0, 0], [10, 10, 0], [10, 10, 10]])
def test_no_fusionar_separados_o_contacto_sin_area(offset):
    with pytest.raises(ValueError):
        unir_cerrados(canonical(boxes(offset)))


def test_no_elimina_cuerpo_pequeno(tmp_path):
    a = trimesh.creation.icosphere(subdivisions=3, radius=10)
    b = trimesh.creation.box(extents=[.1, .1, .1])
    b.apply_translation([30, 0, 0])
    src = tmp_path/'isla.stl'
    trimesh.util.concatenate([a, b]).export(src)
    with pytest.raises(ReparacionRechazada, match='Múltiples cuerpos'):
        preparar(src, tmp_path/'salida.stl')


def test_agujero_local_referencia_explicita_sin_mover_vertices():
    ref = canonical(trimesh.creation.icosphere(subdivisions=3, radius=2))
    mesh = trimesh.Trimesh(ref.vertices.copy(), ref.faces[1:].copy(), process=False)
    candidate, rep = reparar_agujero_local(mesh, ref)
    assert candidate.is_watertight and np.array_equal(mesh.vertices, candidate.vertices)
    assert abs(candidate.volume-ref.volume) < 1e-10
    assert rep['triangulos_añadidos'] == 1


def test_abertura_pequena_tampoco_se_sella_sin_referencia(tmp_path):
    mesh = trimesh.creation.icosphere(subdivisions=3, radius=2)
    mesh.update_faces(np.arange(len(mesh.faces)) != 0)
    src = tmp_path/'scan.stl'
    mesh.export(src)
    with pytest.raises(ReparacionRechazada, match='Borde abierto'):
        preparar(src, tmp_path/'out.stl')


def test_pared_ausente_rechazada_incluso_con_referencia():
    ref = canonical(trimesh.creation.box(extents=[10, 10, 10]))
    mesh = trimesh.Trimesh(ref.vertices, ref.faces[2:], process=False)
    with pytest.raises(ValueError, match='Abertura grande'):
        reparar_agujero_local(mesh, ref)


def test_no_rellena_canal_pasante(tmp_path):
    # Tubo: el hueco funcional tiene una superficie cerrada; pasa sin tocarlo.
    tube = trimesh.creation.annulus(r_min=3, r_max=5, height=10, sections=40)
    src = tmp_path/'canal.stl'
    tube.export(src)
    selected, rep = preparar(src, tmp_path/'out.stl')
    assert selected == src and not rep['reparado']
    assert rep['entrada']['componentes'][0]['euler'] == 0


def test_no_tapa_canal_durante_union():
    tube = trimesh.creation.annulus(r_min=3, r_max=5, height=10, sections=32)
    ring = tube.copy()
    ring.apply_translation([0, 0, 8])
    result, rep = unir_cerrados(canonical(trimesh.util.concatenate([tube, ring])))
    assert result.euler_number == 0 and rep['genero_despues'] == 1
    assert abs(result.volume-tube.volume*1.8) < 1e-6


def test_aleta_sin_volumen_no_crea_solido(tmp_path):
    mesh = trimesh.Trimesh([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]], process=False)
    src = tmp_path/'aleta.stl'
    mesh.export(src)
    with pytest.raises(ReparacionRechazada):
        preparar(src, tmp_path/'out.stl')


def test_fallo_backend_no_exporta_exito(tmp_path, monkeypatch):
    import preprocesador_stl
    src = tmp_path/'contacto.stl'
    boxes([10, 0, 0]).export(src)
    def broken(_):
        raise RuntimeError('backend no disponible')
    monkeypatch.setattr(preprocesador_stl, '_manifold', broken)
    with pytest.raises(ReparacionRechazada, match='backend no disponible'):
        preparar(src, tmp_path/'out.stl')
    assert not (tmp_path/'out.stl').exists()


def test_union_compleja_fuera_limite_falla_claro():
    parts = [trimesh.creation.box().apply_translation([i*2, 0, 0]) for i in range(9)]
    with pytest.raises(ValueError, match='límite experimental'):
        unir_cerrados(canonical(trimesh.util.concatenate(parts)))


@pytest.mark.parametrize('kind', ['tiempo', 'memoria'])
def test_vigilante_detiene_proceso(kind):
    p = subprocess.Popen([sys.executable, '-c', 'import time; a=bytearray(8000000); time.sleep(30)'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    start = time.monotonic()
    with pytest.raises(LimiteRecursos):
        comunicar_vigilado(p, .2 if kind == 'tiempo' else 10,
                          lambda process: process.kill(),
                          memoria_bytes=1 if kind == 'memoria' else 512*1024**2)
    assert p.poll() is not None and time.monotonic()-start < 5


def test_los_umbrales_cad_no_cambian():
    import motor_v2 as m
    assert (m.MAX_VOLUME_ERROR, m.MAX_BBOX_ERROR, m.MAX_SURFACE_P95,
            m.MAX_SURFACE_OBSERVED, m.MAX_WORK_SURFACE_DIFFERENCE) == (.005, .020, .020, .060, .010)


def test_interfaces_no_descartan_ninguna_cara_original():
    from preprocesador_stl import componentes
    source = canonical(boxes([10, 0, 0]))
    parts = componentes(source)
    assert len(parts) == 2 and sum(len(p.faces) for p in parts) == len(source.faces)
    assert all(p.is_watertight for p in parts)


def test_autointerferencia_explicita_rechazada():
    from verificacion_reparacion import solido_poliedrico
    mesh = trimesh.creation.box()
    mesh.vertices[0] = [2, 2, 2]
    with pytest.raises(ValueError):
        solido_poliedrico(mesh)


@pytest.mark.skipif(not os.getenv('VISOR_MATERIAL_PRUEBAS'), reason='STL privados no indicados')
def test_cubo_carrito_y_referencia_real(tmp_path):
    from verificacion_reparacion import distancia_malla, puntos_superficie
    root = Path(os.environ['VISOR_MATERIAL_PRUEBAS'])
    src = root/'caso_cubo_carrito/cubo-carrito.stl'
    selected, rep = preparar(src, tmp_path/'cubo.stl')
    candidate = cargar_exacto(selected)
    ref = cargar_exacto(root/'caso_cubo_carrito/cubo-carrito_REPARADO.stl')
    assert rep['entrada']['aristas_mas_2_caras'] == 4
    assert rep['salida']['numero_componentes'] == 1
    assert candidate.euler_number == ref.euler_number == 0
    assert abs(candidate.volume-ref.volume)/ref.volume < .00001
    assert max(distancia_malla(candidate, puntos_superficie(ref)).max(),
               distancia_malla(ref, puntos_superficie(candidate)).max()) < .020


@pytest.mark.skipif(not os.getenv('VISOR_MATERIAL_PRUEBAS'), reason='STL privados no indicados')
@pytest.mark.parametrize('angles', [[.37, -.61, 1.03], [0, 0, .71], [1.57, .29, -.45]])
def test_cubo_carrito_reparacion_rotada(tmp_path, angles):
    source = Path(os.environ['VISOR_MATERIAL_PRUEBAS'])/'caso_cubo_carrito/cubo-carrito.stl'
    mesh = cargar_exacto(source)
    mesh.apply_transform(trimesh.transformations.euler_matrix(*angles))
    rotated = tmp_path/'rotado.stl'
    mesh.export(rotated)
    selected, rep = preparar(rotated, tmp_path/'reparado.stl')
    assert rep['reparado'] and rep['salida']['ruta'] == 'paso_directo'
    assert rep['verificacion_stl_reimportado']['volumen_error_pct'] < .001


@pytest.mark.skipif(not os.getenv('VISOR_MATERIAL_PRUEBAS'), reason='STL privados no indicados')
def test_14_historicos_no_se_reescriben(tmp_path):
    import hashlib
    files = sorted((Path(os.environ['VISOR_MATERIAL_PRUEBAS'])/'stl_regresion_14').glob('*.stl'))
    assert len(files) == 14
    for i, source in enumerate(files):
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        destination = tmp_path/f'{i}.stl'
        selected, report = preparar(source, destination)
        assert selected == source and not report['reparado'] and not destination.exists()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
