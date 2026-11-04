"""Reimportación independiente del cubo-carrito y sus tres giros de prueba.

Uso: python verificar_cubo_step.py --corpus CARPETA --resultados CARPETA
La batería debe haberse ejecutado antes con bateria_reparacion.py. Los puntos
del canal son expectativas de ESTE caso de prueba, nunca reglas del motor.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

GIROS = {'cubo-carrito.stl': (0., 0., 0.),
         'cubo-carrito_giro_1.stl': (.37, -.61, 1.03),
         'cubo-carrito_giro_2.stl': (0., 0., .71),
         'cubo-carrito_giro_3.stl': (1.57, .29, -.45)}


def verificar(source, step, row):
    import cadquery as cq
    import trimesh
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Check
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN, TopAbs_OUT
    from motor_v2 import _calidad, _estadisticas
    from preprocesador_stl import cargar_exacto
    from validacion_local import _distancias_cad, _puntos_brep
    from verificacion_reparacion import distancia_malla, puntos_superficie

    if (not row['ok'] or hashlib.sha256(step.read_bytes()).hexdigest() != row['sha256_step']
            or hashlib.sha256(source.read_bytes()).hexdigest() != row['sha256']):
        raise ValueError('Conversión fallida o huella del STEP distinta de la batería.')
    repaired = step.with_suffix('.reparado.stl')
    prepared = cargar_exacto(repaired)
    if (hashlib.sha256(repaired.read_bytes()).hexdigest() !=
            row['informe_motor']['preprocesamiento']['reparado_sha256']
            or not prepared.is_watertight or prepared.euler_number != 0):
        raise ValueError('La malla reparada no coincide con la evidencia o pierde el túnel del cubo.')
    original = cargar_exacto(source)
    solid = cq.importers.importStep(str(step)).solids().val()
    quality = _calidad(repaired, step, prepared)  # mismo control histórico, sin márgenes nuevos
    if not BRepAlgoAPI_Check(solid.wrapped, False, True).IsValid():
        raise ValueError('El STEP reimportado presenta autointerferencias.')
    volumes = []
    for epsilon in (1e-6, 1e-8):
        g = GProp_GProps()
        BRepGProp.VolumeProperties_s(solid.wrapped, g, epsilon)
        volumes.append(float(g.Mass()))
    ref = row['informe_motor']['preprocesamiento']['verificacion_stl_reimportado']['volumen_referencia_mm3']
    if (not np.isfinite(volumes).all() or abs(volumes[0]-volumes[1])/ref > 1e-5
            or abs(volumes[-1]-ref)/ref > .005):
        raise ValueError('Volumen adaptativo no convergente o fuera del límite original.')
    # Todos los vértices, centroides y 4.000 puntos de área deterministas del
    # STL unido. Las tapas de contacto internas del original no son superficie
    # exterior; su retirada ya está contrastada con la unión OCC independiente.
    a = _distancias_cad(solid, puntos_superficie(prepared))
    verts, tris = solid.tessellate(.003, angularTolerance=.04)
    points = np.asarray([p.toTuple() for p in verts])
    tris = np.asarray(tris)
    cad_points = np.vstack((points, points[tris].mean(axis=1), _puntos_brep(solid, 3000)))
    b = distancia_malla(prepared, cad_points)
    qa, qb = _estadisticas(a), _estadisticas(b)
    limit = quality['limites_validacion']['p95_superficie_max_mm']
    if (not np.isfinite(a).all() or not np.isfinite(b).all()
            or max(np.percentile(a,95), np.percentile(b,95)) > limit or max(a.max(),b.max()) > .060):
        raise ValueError('La inspección densa no supera los mismos límites superficiales.')
    rotation = trimesh.transformations.euler_matrix(*GIROS[source.name])
    control = [(22.4,22.4,z) for z in (12.,25.4,80.,170.)] + [(.5,22.4,12.),(4.5,22.4,80.)]
    transformed = trimesh.transform_points(control, rotation)
    expected = [TopAbs_OUT]*4 + [TopAbs_IN]*2
    states = [BRepClass3d_SolidClassifier(solid.wrapped,gp_Pnt(*map(float,p)),1e-7).State()
              for p in transformed]
    if states != expected:
        raise ValueError('El canal o las paredes no conservan la ocupación esperada.')
    return {'ok': True, 'sha256_original': hashlib.sha256(source.read_bytes()).hexdigest(),
            'sha256_step': row['sha256_step'], 'calidad_historica_repetida': quality,
            'autointerferencias_occ': False, 'volumen_adaptativo_mm3': volumes,
            'volumen_referencia_mm3': ref, 'volumen_adaptativo_error_pct': 100*abs(volumes[-1]-ref)/ref,
            'caja_reparada_vs_original_mm': float(np.max(abs(prepared.bounds-original.bounds))),
            'superficie_stl_step_densa_mm': qa, 'superficie_step_stl_densa_mm': qb,
            'canal_y_paredes': [{'punto_mm': p.tolist(), 'esperado': str(e), 'obtenido': str(s)}
                                for p,e,s in zip(transformed,expected,states)],
            'nota': 'Control de distancias muestreado; no cota Hausdorff global ni prueba de editabilidad Onshape.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus', type=Path, required=True)
    ap.add_argument('--resultados', type=Path, required=True)
    args = ap.parse_args()
    battery = json.loads((args.resultados/'bateria.json').read_text())
    rows = {r['archivo']: r for r in battery['resultados']}
    results = {}
    for name in GIROS:
        try:
            results[name] = verificar(args.corpus/name, args.resultados/(Path(name).stem+'.step'), rows[name])
        except Exception as exc:
            results[name] = {'ok': False, 'error': str(exc)}
        print(name, results[name]['ok'], flush=True)
        (args.resultados/'verificacion_independiente.json').write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if len(results)==4 and all(r['ok'] for r in results.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
