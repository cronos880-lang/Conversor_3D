"""Puerta adicional muestreada para todo candidato CAD.

Cubre interiores de caras además de aristas. No demuestra una cota Hausdorff
global y no modifica los límites geométricos del motor.
"""
import numpy as np


def inspeccionar_denso(mesh, solid, *, limite_p95, limite_max):
    import trimesh
    from validacion_local import _esparcir, _distancias_cad, _puntos_brep, proyectar_en_brep
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
    # Los centroides de una teselación son muestras aproximadas; algunos
    # teselados OCC incluso atraviesan recortes. Un rechazo requiere puntos
    # del CAD matemático, no de una triangulación defectuosa de ese CAD.
    suspect=np.flatnonzero(b>limite_max)
    if np.percentile(b,95)>limite_p95:
        suspect=np.flatnonzero(b>limite_p95)
    projection={'muestras_proyectadas':len(suspect),'max_distancia_al_brep_mm':0.}
    if len(suspect):
        avance(78,f'Contrastando {len(suspect)} muestras sospechosas con el B-Rep exacto')
        projected,offset=proyectar_en_brep(solid,cad_points[suspect])
        cad_points[suspect]=projected
        b[suspect]=distancia_malla(mesh,projected)
        projection['max_distancia_al_brep_mm']=float(offset.max())

    def stats(values, cloud):
        if not len(values) or not np.isfinite(values).all():
            raise ValueError('Inspección densa sin mediciones geométricas finitas.')
        return {'muestras': len(values), 'p95_mm': float(np.percentile(values, 95)),
                'max_mm': float(values.max()),
                'zonas_sospechosas': [{'xyz_mm': cloud[k].tolist(), 'distancia_mm': float(values[k])}
                                     for k in np.argsort(-values)[:5] if values[k] > limite_max]}

    report = {'stl_a_cad': stats(a, points), 'cad_a_stl': stats(b, cad_points),
              'limite_p95_mm': limite_p95, 'limite_max_mm': limite_max,
              'contraste_muestras_cad':projection,
              'nota': 'Muestreo determinista, no garantía Hausdorff global.'}
    report['aceptado'] = all(v['p95_mm'] <= limite_p95 and v['max_mm'] <= limite_max
                             for v in (report['stl_a_cad'], report['cad_a_stl']))
    return report


def exigir_denso(mesh, solid, *, limite_p95, limite_max):
    report = inspeccionar_denso(mesh, solid, limite_p95=limite_p95, limite_max=limite_max)
    if not report['aceptado']:
        from diagnostico_validacion import ErrorGeometrico,criterio
        error = ErrorGeometrico('Inspección densa rechazada',[
            criterio('p95 STL→CAD',report['stl_a_cad']['p95_mm'],limite_p95),
            criterio('p95 CAD→STL',report['cad_a_stl']['p95_mm'],limite_p95),
            criterio('Máximo STL→CAD',report['stl_a_cad']['max_mm'],limite_max),
            criterio('Máximo CAD→STL',report['cad_a_stl']['max_mm'],limite_max)])
        error.informe_denso = report
        raise error
    return report
