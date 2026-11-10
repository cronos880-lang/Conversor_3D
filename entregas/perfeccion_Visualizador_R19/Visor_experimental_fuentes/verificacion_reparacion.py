"""Contraste independiente del booleano de mallas con OpenCascade.

Usa las facetas originales como planos, sin ajustar cilindros ni suavizar.
La comprobación de interferencias no sustituye una demostración matemática.
"""
from __future__ import annotations
import numpy as np


def solido_poliedrico(mesh, *, _permitir_regularizacion=True):
    import cadquery as cq
    from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeFace,
                                   BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid)
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Check
    sew = BRepBuilderAPI_Sewing(1e-7)
    for triangle in mesh.triangles:
        polygon = BRepBuilderAPI_MakePolygon()
        for xyz in triangle:
            polygon.Add(gp_Pnt(*map(float, xyz)))
        polygon.Close()
        sew.Add(BRepBuilderAPI_MakeFace(polygon.Wire()).Face())
    sew.Perform()
    shape = cq.Shape.cast(BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(sew.SewedShape())).Solid())
    unify = ShapeUpgrade_UnifySameDomain(shape.wrapped, True, True, False)
    unify.Build()
    shape = cq.Shape.cast(unify.Shape())
    if not shape.isValid() or len(shape.Solids()) != 1 or shape.Volume() <= 0:
        raise ValueError('El componente no forma un sólido poliédrico válido en OpenCascade.')
    if not BRepAlgoAPI_Check(shape.wrapped, False, True).IsValid():
        if _permitir_regularizacion:
            from regularizacion_planar import regularizar_cancelaciones_planas
            regularized, proof = regularizar_cancelaciones_planas(mesh)
            if proof['aplicado']:
                checked = solido_poliedrico(regularized, _permitir_regularizacion=False)
                checked.regularizacion_plana = proof
                return checked
        raise ValueError('OpenCascade detecta autointersecciones o interferencias ambiguas.')
    return shape


def union_independiente(parts):
    import cadquery as cq
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    shapes = [solido_poliedrico(p) for p in parts]
    regularizations = [{'componente': i, **s.regularizacion_plana}
                       for i,s in enumerate(shapes) if hasattr(s,'regularizacion_plana')]
    shape = shapes[0]
    for other in shapes[1:]:
        op = BRepAlgoAPI_Fuse(shape.wrapped, other.wrapped)
        op.SetFuzzyValue(1e-7)
        op.Build()
        if not op.IsDone():
            raise ValueError('No se pudo calcular la unión independiente con OpenCascade.')
        shape = cq.Shape.cast(op.Shape())
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise ValueError('Múltiples cuerpos: la unión independiente no produce un sólido válido.')
    shape.regularizaciones_planas = regularizations
    return shape


def puntos_superficie(mesh, n=4000):
    import trimesh
    points, _ = trimesh.sample.sample_surface(mesh, n, seed=17023)
    return np.vstack((mesh.vertices, mesh.triangles_center, points))


def distancia_malla(mesh, points):
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
    points = np.asarray(points, dtype=float)
    poly = vtk.vtkPolyData()
    vp = vtk.vtkPoints()
    vp.SetData(numpy_to_vtk(np.asarray(mesh.vertices, dtype=np.float64), deep=True))
    poly.SetPoints(vp)
    cells = vtk.vtkCellArray()
    cells.SetData(numpy_to_vtkIdTypeArray(np.arange(0, 3*(len(mesh.faces)+1), 3,
                      dtype=np.int64), deep=True),
                  numpy_to_vtkIdTypeArray(np.asarray(mesh.faces, dtype=np.int64).ravel(), deep=True))
    poly.SetPolys(cells)
    locator = vtk.vtkStaticCellLocator()
    locator.SetDataSet(poly)
    locator.BuildLocator()
    closest = [0., 0., 0.]
    cid, subid, dist2 = vtk.reference(0), vtk.reference(0), vtk.reference(0.)
    out = []
    for p in points:
        locator.FindClosestPoint(p, closest, cid, subid, dist2)
        out.append(float(dist2)**.5)
    return np.asarray(out)


def malla_cad(shape):
    import trimesh
    vertices, faces = shape.tessellate(.001)
    return trimesh.Trimesh([p.toTuple() for p in vertices], faces, process=True)


def validar_union(parts, candidate):
    # Referencia construida desde los componentes de ENTRADA, nunca desde la
    # malla candidata. Calcular ambos booleanos en el marco exacto del contacto
    # evita que las triangulaciones casi coplanares de float32 dejen caras
    # interiores espurias en la teselación de OCC tras rotar un STL.
    import trimesh
    from preprocesador_stl import _marco_contacto, componentes
    merged = trimesh.util.concatenate(parts)
    vertices, inverse = np.unique(merged.vertices, axis=0, return_inverse=True)
    merged = trimesh.Trimesh(vertices, inverse[merged.faces], process=False)
    normalized, restore, normalization = _marco_contacto(merged)
    ref = union_independiente(componentes(normalized))
    refmesh = malla_cad(ref)  # Planos: la teselación no introduce curvatura.
    refmesh.apply_transform(restore)
    # Contraste de superficie bidireccional con todos los vértices, centroides
    # y 4.000 puntos de área por dirección. No compara superficies interiores.
    a = distancia_malla(refmesh, puntos_superficie(candidate))
    b = distancia_malla(candidate, puntos_superficie(refmesh))
    volume_error = abs(candidate.volume-ref.Volume())/max(ref.Volume(), 1e-12)
    bbox_error = float(np.max(np.abs(candidate.bounds-refmesh.bounds)))
    max_dist = max(float(a.max()), float(b.max()))
    p95 = max(float(np.percentile(a, 95)), float(np.percentile(b, 95)))
    if volume_error > .00001 or bbox_error > .002 or max_dist > .002:
        raise ValueError('No se pudo garantizar reparación sin cambiar cotas: '
                         f'contraste OCC volumen={volume_error:.6%}, caja={bbox_error:.6f}, '
                         f'superficie={max_dist:.6f} mm.')
    return {'referencia': 'unión poliédrica independiente OpenCascade; fuzzy 0,0000001 mm',
            'volumen_referencia_mm3': ref.Volume(), 'volumen_error_pct': volume_error*100,
            'caja_error_mm': bbox_error, 'p95_mm': p95, 'max_observado_mm': max_dist,
            'muestras_direcciones': [len(a), len(b)], 'brep_valido': ref.isValid(),
            'solidos_referencia': len(ref.Solids()),
            'regularizaciones_planas_referencia': ref.regularizaciones_planas,
            'normalizacion_referencia': normalization,
            'limites': {'volumen_pct': .001, 'caja_mm': .002, 'superficie_mm': .002},
            'nota': 'Mediciones deterministas muestreadas, no cota Hausdorff global.'}
