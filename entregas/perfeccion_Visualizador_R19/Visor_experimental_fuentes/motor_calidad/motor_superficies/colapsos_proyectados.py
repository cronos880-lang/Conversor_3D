"""Detectar encuentros nuevos de vértices distintos tras el ajuste CAD."""
import numpy as np
from scipy.spatial import cKDTree


def detectar(original,positions,tolerancia_cad=1e-7):
    keys=np.array(sorted(positions),dtype=int)
    P=np.array([positions[int(v)] for v in keys],float)
    if not np.isfinite(P).all():raise ValueError('La proyección produce coordenadas no finitas')
    if len(P)<2:return []
    limit=2*tolerancia_cad;rows=[]
    for i,j in sorted(cKDTree(P).query_pairs(limit)):
        a,b=map(int,(keys[i],keys[j]));before=float(np.linalg.norm(original[a]-original[b]));after=float(np.linalg.norm(P[i]-P[j]))
        if before>limit and after<limit:rows.append(dict(vertices=[a,b],distancia_fuente_mm=before,distancia_cad_mm=after))
    return sorted(rows,key=lambda r:r['distancia_cad_mm'])
