"""STL inmutable -> triangulación OCP y diagnóstico de conectividad.

La triangulación no se presenta como shell ni se usa para sustituir el original.
Las reparaciones siguen bajo los contratos del preprocesador R18.
"""
import numpy as np
from contratos_r19 import sha, MAX_TRIANGULOS_OPTIMIZACION


def evaluar(source):
    from OCP.RWStl import RWStl
    from preprocesador_stl import cargar_exacto
    from topologia_vertices import inspeccionar_vertices
    before = sha(source)
    native = RWStl.ReadFile_s(str(source))
    if native is None or native.NbTriangles() == 0:
        raise ValueError('RWStl no ha leído una triangulación')
    mesh = cargar_exacto(source)
    if not len(mesh.faces):
        raise ValueError('El STL está vacío')
    vertex_report = inspeccionar_vertices(mesh)
    incidence = np.bincount(mesh.edges_unique_inverse, minlength=len(mesh.edges_unique))
    closed = bool(mesh.is_watertight)
    oriented = bool(mesh.is_winding_consistent)
    report = dict(original_sha256=before, unidades='mm', unidades_origen='STL sin unidades; se conserva la interpretación mm del Visor',
                  lector_ocp='RWStl', triangulos_ocp=native.NbTriangles(), vertices_ocp=native.NbNodes(),
                  triangulos=len(mesh.faces), vertices=len(mesh.vertices),
                  aristas_abiertas=int(np.count_nonzero(incidence == 1)),
                  aristas_no_manifold=int(np.count_nonzero(incidence > 2)),
                  vertices_no_manifold=int(vertex_report['vertices_no_manifold']),
                  cerrado=closed, orientado=oriented, euler=int(mesh.euler_number),
                  triangulos_degenerados=int(np.count_nonzero(mesh.area_faces <= 1e-18)),
                  cotas_mm=mesh.bounds.tolist(), original_modificado=False,
                  optimizacion_admisible=bool(closed and oriented and not vertex_report['vertices_no_manifold']
                                             and len(mesh.faces) <= MAX_TRIANGULOS_OPTIMIZACION),
                  autointersecciones='Se comprueban en el núcleo y en los tres mallados finales; el cierre no las descarta')
    if sha(source) != before:
        raise ValueError('El STL cambió durante la ingesta')
    return report
