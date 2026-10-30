"""Reconocimiento geométrico conservador sobre el STL ORIGINAL (experimental).

No modifica la malla ni redondea cotas. La reconstrucción existente mantiene el
control; este módulo identifica geometría CAD y relaciones con evidencia medible.
"""
from __future__ import annotations

from collections import Counter
import numpy as np
from scipy.spatial import cKDTree


def _unit(a):
    a = np.asarray(a, float)
    n = np.linalg.norm(a)
    return a / n if n > 1e-14 else None


def _axis_distance(p, a, q, b):
    """Distancia entre rectas (no entre los centros de sus segmentos)."""
    cross = np.cross(a, b)
    if np.linalg.norm(cross) > 1e-8:
        return abs(float((p-q) @ cross)) / float(np.linalg.norm(cross))
    return float(np.linalg.norm(np.cross(p-q, a)))


def relaciones_verificadas(primitives, angular_deg=0.3, linear_tol=0.01):
    """Relaciones geométricas candidatas; no aplica snaps no reversibles.

    Ángulos calculados sin signo: normales opuestas también son paralelas.
    Solo relaciones entre primitivas con ajuste RMS dentro del límite local.
    """
    out = []
    entries = [(i,p) for i,p in enumerate(primitives)
               if float(p.get('rms', 1e99)) <= linear_tol]
    cos_t = np.cos(np.radians(angular_deg))
    sin_t = np.sin(np.radians(angular_deg))
    for j, (ia, a) in enumerate(entries):
        if a['type'] not in ('plane','cylinder','cone'):
            continue
        u = _unit(a['normal'] if a['type']=='plane' else a['axis'])
        if u is None:
            continue
        for ib, b in entries[j+1:]:
            if b['type'] not in ('plane','cylinder','cone'):
                continue
            v = _unit(b['normal'] if b['type']=='plane' else b['axis'])
            if v is None:
                continue
            d = abs(float(np.dot(u,v)))
            kind = None
            residual = None
            if d >= cos_t:
                kind = 'planos_paralelos' if a['type']==b['type']=='plane' else 'ejes_paralelos'
                residual = float(np.degrees(np.arccos(np.clip(d, -1, 1))))
            elif d <= sin_t and a['type']==b['type']=='plane':
                kind = 'planos_perpendiculares'
                residual = float(np.degrees(np.arcsin(np.clip(d, 0, 1))))
            if a['type']==b['type']=='cylinder' and d >= cos_t:
                delta = _axis_distance(np.asarray(a['point']),u,np.asarray(b['point']),v)
                if delta <= linear_tol:
                    kind = 'cilindros_coaxiales'
                    residual = delta
            if kind is not None:
                out.append({'regiones':[ia,ib], 'relacion':kind,
                            'residuo':round(float(residual),7)})
    return out


def etiquetar(result, face_count):
    labels = np.full(face_count,-1,dtype=np.int32)
    for i,p in enumerate(result['primitives']):
        labels[np.asarray(p['faces'],dtype=int)] = i
    return labels


def inventario_original(path_stl, detector, *, flat_tol_deg=8.0):
    """Reconoce la malla original ANTES de simplificar; no toca el B-Rep."""
    result, mesh = detector(str(path_stl), angle_tol_deg=32.0,
                            rms_tol_rel=0.01, flat_tol_deg=flat_tol_deg,
                            scan_mode=False)
    labels = etiquetar(result, len(mesh.faces))
    groups = Counter(p['type'] for p in result['primitives'])
    # Valores conservadores, no fuerza números redondos de diseño.
    dims = float(np.linalg.norm(mesh.extents))
    linear_tol = min(0.01, max(0.002, .0001*dims))
    rels = relaciones_verificadas(result['primitives'],linear_tol=linear_tol)
    # Adyacencia de regiones: qué CAD analíticas DE VERDAD comparten frontera.
    adjacency = np.asarray(mesh.face_adjacency,dtype=int)
    neighbors = adjacency[labels[adjacency[:,0]] != labels[adjacency[:,1]]]
    pair_counts = Counter(tuple(sorted(map(int,x))) for x in
                          np.c_[labels[neighbors[:,0]], labels[neighbors[:,1]]]
                          if -1 not in x)
    summary = {'triangulos':int(len(mesh.faces)),
               'regiones_analiticas':int(len(result['primitives'])),
               'regiones_libres':int(len(result['freeform_regions'])),
               'tipos':dict(groups),
               'relaciones_geometricas':rels[:250],
               'num_relaciones':len(rels),
               'num_uniones_analiticas':len(pair_counts),
               'triangulos_sin_analitica':int((labels==-1).sum()),
               'nota':'Las relaciones son diagnósticos candidatos; no se alteran cotas.'}
    return summary, (result,mesh,labels)


def transferir_etiquetas(original, trabajo, *, max_mm=0.015,
                          normal_deg=15.0, max_uncertain_fraction=0.005):
    """Transfiere clases analíticas a otra triangulación SOLO cuando es verificable.

    Usa vecinos espaciales, coherencia de normales y residuo de la primitiva.
    No devuelve una segmentación si hay regiones libres u otros resultados dudosos.
    Esto es una prueba preliminar: las etiquetas transferidas no se hacen B-Rep
    automáticamente mientras su topología no pase una comprobación específica.
    """
    from meshfit_detect import DEV
    result, original_mesh, old_labels = original
    centers = np.asarray(trabajo.triangles_center)
    normals = np.asarray(trabajo.face_normals)
    tree = cKDTree(np.asarray(original_mesh.triangles_center))
    _, ids = tree.query(centers,k=min(8,len(old_labels)))
    ids = np.atleast_2d(ids)
    if ids.shape[0] != len(centers):
        ids = ids.T
    src_centers = np.asarray(original_mesh.triangles_center)
    src_normals = np.asarray(original_mesh.face_normals)
    candidate_labels = old_labels[ids]
    point_err = np.linalg.norm(src_centers[ids]-centers[:,None,:],axis=2)
    ndot = (src_normals[ids]*normals[:,None,:]).sum(axis=2)
    score = point_err + np.where(ndot>=np.cos(np.radians(normal_deg)),0.0,1e6)
    best = np.argmin(score,axis=1)
    row = np.arange(len(centers))
    label = candidate_labels[row,best]
    ok = (score[row,best]<max_mm +
          np.sqrt(np.asarray(trabajo.area_faces)/2)) & (label>=0)
    # Verificar que los triángulos nuevos ENCAJAN en la superficie analítica.
    for k in np.unique(label[ok]):
        pp = result['primitives'][int(k)]
        ix=np.where(ok & (label==k))[0]
        if len(ix):
            err=np.asarray(DEV[pp['type']](pp,centers[ix]))
            ok[ix[err>max_mm]] = False
    uncertain=int((~ok).sum())
    return {'transferible':bool(uncertain<=max_uncertain_fraction*len(centers)),
            'porcentaje_incierto':round(100*uncertain/max(1,len(centers)),3),
            'triangulos_inciertos':uncertain,
            'nota':'No usar etiquetas transferidas para generar CAD hasta verificar contornos.'}
