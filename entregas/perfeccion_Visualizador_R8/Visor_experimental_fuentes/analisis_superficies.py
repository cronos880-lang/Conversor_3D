"""Reconocimiento experimental y no destructivo de geometría en mallas STL.

No confundir detección de candidatos con una reconstrucción B-Rep validada.
"""
import numpy as np
from scipy.optimize import least_squares


def analizar_superficies(mesh):
    """Identifica parches planos y busca círculos en secciones horizontales.

    Devuelve magnitudes de diagnóstico; no reemplaza la geometría del STL.
    """
    faces = len(mesh.faces)
    patches = mesh.facets
    planar = [len(f) for f in patches if len(f) >= 4]
    # Buscar contornos circulares en niveles Z con suficiente densidad de puntos.
    verts = np.asarray(mesh.vertices)
    height = max(float(np.ptp(verts[:, 2])), 1.)
    zq = np.round(verts[:, 2], 5)
    levels, count = np.unique(zq, return_counts=True)
    levels = levels[np.argsort(count)[-min(15, len(levels)):]]
    circles = []
    for z in levels:
        points = verts[np.abs(zq - z) < 1.e-7][:, :2]
        if len(points) < 16:
            continue
        # RANSAC determinista: puntos del contorno pueden incluir rectas.
        rng = np.random.default_rng(2026)
        best = None
        span = max(float(np.ptp(points, axis=0).max()), 1.)
        tolerance = max(span * 8.e-5, 0.002)
        for _ in range(280):
            pick = points[rng.choice(len(points), 3, replace=False)]
            mat = 2*(pick[1:] - pick[0])
            if abs(np.linalg.det(mat)) < span*span*1.e-5:
                continue
            center = np.linalg.solve(mat, np.sum(pick[1:]**2, axis=1)-np.sum(pick[0]**2))
            rad = np.linalg.norm(pick[0]-center)
            if not 0.01*span < rad < 2*span:
                continue
            dist = abs(np.linalg.norm(points-center, axis=1)-rad)
            inliers = dist < tolerance
            if int(inliers.sum()) >= 12 and (best is None or inliers.sum() > best.sum()):
                best = inliers
        if best is None:
            continue
        selected = points[best]
        approx_center = selected.mean(axis=0)
        approx_r = np.linalg.norm(selected-approx_center, axis=1).mean()
        fit = least_squares(lambda v: np.linalg.norm(selected-v[:2], axis=1)-v[2],
                            [*approx_center, approx_r], max_nfev=70)
        cx, cy, r = fit.x
        err = max(abs(fit.fun))
        if err > tolerance or r <= 0:
            continue
        # Un círculo completo requiere cobertura angular, no un pequeño arco.
        a = np.sort(np.arctan2(selected[:, 1]-cy, selected[:, 0]-cx))
        gap = np.max(np.diff(np.r_[a, a[0]+2*np.pi]))
        if gap > 0.45:
            continue
        if any(abs(r-c['radio']) < tolerance*2 and np.hypot(cx-c['cx'], cy-c['cy']) < tolerance*2 for c in circles):
            continue
        circles.append({'cx':round(float(cx),5),'cy':round(float(cy),5),
                        'radio':round(float(r),5),'z':round(float(z),5),
                        'desviacion_max':round(float(err),6)})
    return {'triangulos':faces, 'regiones_planas':len(planar),
            'triangulos_en_regiones_planas':sum(planar),
            'circulos_detectados_en_secciones':circles[:30],
            'advertencia':'Los círculos detectados son candidatos geométricos; no representan cilindros CAD reconstruidos.'}
