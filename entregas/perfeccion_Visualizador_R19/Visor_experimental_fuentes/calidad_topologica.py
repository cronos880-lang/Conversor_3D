"""Comprobaciones adicionales de integridad B-Rep y tolerancias de unión.

No identifica operaciones paramétricas ni garantiza que Move face funcione en
Onshape: es una prueba funcional externa. Estas métricas sirven para rechazar
fusiones que reducen aristas, pero deterioran los empalmes geométricos.
"""
from __future__ import annotations

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepCheck import BRepCheck_Analyzer


def leer_solido_step_estricto(path):
    """No ocultar curvas/caras sueltas seleccionando sólo .solids() al leer."""
    import cadquery as cq
    from OCP.TopoDS import TopoDS_Iterator
    solids=[]
    def visit(shape):
        kind=str(shape.ShapeType())
        if kind=='Solid':solids.append(shape);return
        if kind not in ('Compound','CompSolid'):
            raise ValueError('El STEP contiene objetos sueltos fuera del sólido: '+kind)
        iterator=TopoDS_Iterator(shape.wrapped)
        while iterator.More():
            visit(cq.Shape.cast(iterator.Value()));iterator.Next()
    for root in cq.importers.importStep(str(path)).vals():visit(root)
    if len(solids)!=1 or not solids[0].isValid():
        raise ValueError('El STEP no contiene exactamente un sólido cerrado y válido.')
    return solids[0]


def inspeccionar(solido):
    edges = solido.Edges()
    tol = np.array([float(BRep_Tool.Tolerance_s(e.wrapped)) for e in edges], dtype=float)
    if len(tol) == 0:
        raise ValueError('Sólido CAD sin aristas.')
    valid = bool(BRepCheck_Analyzer(solido.wrapped, True).IsValid())
    mismatched = sum(
        not (BRep_Tool.SameParameter_s(e.wrapped) and BRep_Tool.SameRange_s(e.wrapped))
        for e in edges
    )
    return {
        'brep_valido': valid,
        'solidos': len(solido.Solids()),
        'aristas': len(edges),
        'aristas_parametrizacion_incoherente': mismatched,
        'tolerancia_max_mm': round(float(tol.max()), 7),
        'tolerancia_p95_mm': round(float(np.percentile(tol, 95)), 7),
        'tolerancia_media_mm': round(float(tol.mean()), 7),
        'aristas_tol_mayor_001mm': int((tol > .010).sum()),
    }


def aceptar_consolidacion(antes, despues):
    """Veredicto prudente, basado en regresiones de STEP editables.

    Reduce riesgo de fusión excesiva (la candidata de 88 caras elevaba el
    percentil 95 de tolerancias de 0.0159 a 0.0202 mm). Los límites no
    prueban la compatibilidad de todas las operaciones de un CAD externo.
    """
    if not despues['brep_valido'] or despues['solidos'] != 1:
        return False, 'El sólido reconstruido no pasa la comprobación B-Rep.'
    if despues['aristas_parametrizacion_incoherente']:
        return False, 'Hay aristas con curvas 3D y 2D incoherentes.'
    # Evitar considerar mejor una reducción visual a costa de tolerancias.
    if despues['tolerancia_max_mm'] > max(
        antes['tolerancia_max_mm'] * 1.05,
        antes['tolerancia_max_mm'] + .001
    ):
        return False, 'La tolerancia máxima de las aristas aumenta demasiado.'
    if despues['tolerancia_p95_mm'] > max(
        antes['tolerancia_p95_mm'] + .0015,
        antes['tolerancia_p95_mm'] * 1.12
    ):
        return False, 'Las tolerancias de unión empeoran de forma generalizada.'
    return True, 'Consolidación aceptada con protección de editabilidad geométrica.'
