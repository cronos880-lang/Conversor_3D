"""Rescate de una entrada reparada mediante un marco rígido local verificable.

No ajusta cotas ni acepta tolerancias nuevas. La rotación facilita el cálculo
del mismo B-Rep; el STEP se restaura y valida contra la entrada en su marco real.
"""
from __future__ import annotations
from pathlib import Path
import tempfile
import numpy as np


def convertir_marco_local(source, destination, log, convertir, calidad):
    import cadquery as cq
    import trimesh
    from OCP.gp import gp_Trsf
    from meshfit_step import _write_step
    mesh = trimesh.load(str(source), force='mesh', process=True)
    order = np.argsort(-mesh.area_faces, kind='stable')
    first = mesh.face_normals[order[0]]
    second = next((mesh.face_normals[i] for i in order
                   if mesh.area_faces[i] >= .01*mesh.area_faces[order[0]]
                   and abs(mesh.face_normals[i]@first) < .01), None)
    if second is None:
        raise ValueError('No hay dos direcciones ortogonales suficientemente sustentadas para el marco CAD.')
    x = first/np.linalg.norm(first)
    y = second - (second@x)*x
    y /= np.linalg.norm(y)
    basis = np.column_stack((x, y, np.cross(x,y)))
    origin = mesh.bounds.mean(axis=0)
    local_points = (mesh.vertices-origin)@basis
    quantized = local_points.astype(np.float32).astype(float)
    quant_error = float(np.max(np.linalg.norm(quantized-local_points, axis=1)))
    if quant_error > .000020:
        raise ValueError('La serialización del marco local supera 0,000020 mm; rescate omitido.')
    with tempfile.TemporaryDirectory(prefix='visor_cad_marco_') as directory:
        directory = Path(directory)
        local_stl, local_step = directory/'local.stl', directory/'local.step'
        trimesh.Trimesh(local_points, mesh.faces.copy(), process=False).export(local_stl)
        result = convertir(local_stl, local_step, log, flat_tol_deg=1.3,
                           digital=True, analitico=True, precision_reparacion=True)
        shape = cq.importers.importStep(str(local_step)).solids().val()
        transform = gp_Trsf()
        transform.SetValues(*[float(v) for v in np.column_stack((basis,origin)).ravel()])
        restored = shape.transformShape(cq.Matrix(transform))
        _write_step(restored.wrapped, str(directory/'restaurado.step'))
        # Validar en coordenadas REALES y contra el STL reparado original.
        # El error de serialización NO se añade a ningún límite de aceptación.
        result['calidad'] = calidad(source, directory/'restaurado.step', mesh)
        destination.write_bytes((directory/'restaurado.step').read_bytes())
        result['marco_local'] = {'matriz_restauracion':np.column_stack((basis,origin)).tolist(),
                                 'max_serializacion_local_mm':quant_error,
                                 'limite_serializacion_local_mm':.000020,
                                 'validacion_final':'STEP restaurado frente al STL reparado en coordenadas originales; mismos límites'}
        return result
