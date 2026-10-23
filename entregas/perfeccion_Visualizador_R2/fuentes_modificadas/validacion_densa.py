"""Puerta adicional muestreada para CAD procedente de reparaciones.

Cubre interiores de caras además de aristas. No demuestra una cota Hausdorff
global y no modifica los límites geométricos del motor.
"""
import numpy as np


def inspeccionar_denso(mesh, solid, *, limite_p95, limite_max):
    import trimesh
    from validacion_local import _esparcir, _distancias_cad, _puntos_brep
    from verificacion_reparacion import distancia_malla

    area, _ = trimesh.sample.sample_surface(mesh, 1000, seed=20261023)
    points = np.vstack((_esparcir(np.vstack((mesh.vertices, mesh.triangles_center)), 2000), area))
    from avance_conversion import avance
    a = _distancias_cad(solid, points, progreso=lambda n,total:
        avance(78,f'Inspección densa STL→STEP: {n}/{total} puntos verificados'))
    avance(78,'Inspección densa STEP→STL: caras y aristas del CAD')
    verts, tris = solid.copy().tessellate(.003, angularTolerance=.04)
    vertices = np.asarray([p.toTuple() for p in verts])
    triangles = np.asarray(tris)
    cad_points = np.vstack((vertices, vertices[triangles].mean(axis=1), _puntos_brep(solid, 10000)))
    b = distancia_malla(mesh, cad_points)

    def stats(values, cloud):
        if not len(values) or not np.isfinite(values).all():
            raise ValueError('Inspección densa sin mediciones geométricas finitas.')
        return {'muestras': len(values), 'p95_mm': float(np.percentile(values, 95)),
                'max_mm': float(values.max()),
                'zonas_sospechosas': [{'xyz_mm': cloud[k].tolist(), 'distancia_mm': float(values[k])}
                                     for k in np.argsort(-values)[:5] if values[k] > limite_max]}

    report = {'stl_a_cad': stats(a, points), 'cad_a_stl': stats(b, cad_points),
              'limite_p95_mm': limite_p95, 'limite_max_mm': limite_max,
              'nota': 'Muestreo determinista, no garantía Hausdorff global.'}
    report['aceptado'] = all(v['p95_mm'] <= limite_p95 and v['max_mm'] <= limite_max
                             for v in (report['stl_a_cad'], report['cad_a_stl']))
    return report


def exigir_denso(mesh, solid, *, limite_p95, limite_max):
    report = inspeccionar_denso(mesh, solid, limite_p95=limite_p95, limite_max=limite_max)
    if not report['aceptado']:
        error = ValueError('Inspección densa rechazada: desviación máxima '
                           f"{max(report['stl_a_cad']['max_mm'], report['cad_a_stl']['max_mm']):.6f} mm; "
                           f'límite original {limite_max:.6f} mm.')
        error.informe_denso = report
        raise error
    return report
