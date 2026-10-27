"""
MeshFit — detección por RANSAC secuencial (estilo Efficient-RANSAC).

En cada ronda prueba plano / cilindro / esfera sobre las caras NO asignadas, valida los
inliers también por la **normal** (no solo por distancia, así no roba caras de superficies
vecinas), se queda con la primitiva de más inliers, la extrae y repite. Lo que no encaja en
ninguna primitiva limpia queda como **freeform** (no se inventan toros ni cilindros falsos).

Trabaja sobre caras (centroide + normal de cara) para respetar la unidad de la malla.
Usa pyransac3d para el muestreo robusto y los `fit_*` de meshfit_detect para refinar.
"""
import numpy as np
import trimesh
import pyransac3d as pyrsc

from meshfit_detect import fit_plane, fit_cylinder, fit_sphere, stats


def detect_ransac(path, thresh_rel=0.004, normal_tol_deg=22.0, min_faces=6, max_prims=60):
    mesh = trimesh.load(path, force="mesh")
    mesh.merge_vertices()
    diag = float(np.linalg.norm(mesh.bounds[1] - mesh.bounds[0])) or 1.0
    thresh = diag * thresh_rel
    cos_tol = np.cos(np.radians(normal_tol_deg))
    sin_tol = np.sin(np.radians(normal_tol_deg))

    C = mesh.triangles_center
    N = mesh.face_normals
    A = mesh.area_faces
    V = mesh.vertices
    F = mesh.faces

    remaining = np.arange(len(F))
    prims = []

    while len(remaining) >= min_faces and len(prims) < max_prims:
        pts = C[remaining]
        nrm = N[remaining]
        cands = []   # (tipo, caras_globales, score)

        # --- Plano ---
        try:
            eq, inl = pyrsc.Plane().fit(pts, thresh=thresh, minPoints=min_faces, maxIteration=600)
            inl = np.asarray(inl, dtype=int)
            if len(inl):
                pn = np.array(eq[:3], float); pn /= (np.linalg.norm(pn) or 1)
                good = inl[np.abs(nrm[inl] @ pn) > cos_tol]
                if len(good) >= min_faces:
                    cands.append(("plane", remaining[good], len(good) * 1.15))  # leve preferencia
        except Exception:
            pass

        # --- Cilindro ---
        try:
            cen, ax, r, inl = pyrsc.Cylinder().fit(pts, thresh=thresh, maxIteration=1500)
            inl = np.asarray(inl, dtype=int)
            ax = np.array(ax, float); ax /= (np.linalg.norm(ax) or 1)
            if len(inl) and r < 3 * diag:
                good = inl[np.abs(nrm[inl] @ ax) < sin_tol]   # normal ⊥ eje
                if len(good) >= min_faces:
                    cands.append(("cylinder", remaining[good], len(good)))
        except Exception:
            pass

        # --- Esfera ---
        try:
            cen, r, inl = pyrsc.Sphere().fit(pts, thresh=thresh, maxIteration=500)
            inl = np.asarray(inl, dtype=int)
            cen = np.array(cen, float)
            if len(inl) and r < 5 * diag:
                d = pts[inl] - cen
                d /= (np.linalg.norm(d, axis=1, keepdims=True) + 1e-12)
                good = inl[np.abs(np.einsum("ij,ij->i", nrm[inl], d)) > cos_tol]
                if len(good) >= min_faces:
                    cands.append(("sphere", remaining[good], len(good) * 0.95))
        except Exception:
            pass

        if not cands:
            break
        cands.sort(key=lambda c: -c[2])
        ty, gfaces, _ = cands[0]

        # refinar el ajuste con los vértices de esas caras
        vidx = np.unique(F[gfaces].ravel())
        P = V[vidx]
        if ty == "plane":
            prim = fit_plane(P)
        elif ty == "cylinder":
            prim = fit_cylinder(P, N[gfaces], A[gfaces])
        else:
            prim = fit_sphere(P)
        prim["rms"], prim["max"] = stats(prim, P)
        prim["faces"] = gfaces.tolist()
        prim["n_faces"] = int(len(gfaces))
        prims.append(prim)

        remaining = np.setdiff1d(remaining, gfaces, assume_unique=False)

    return {"diag": diag, "n_faces": int(len(F)), "n_verts": int(len(V)),
            "bbox": mesh.bounds.tolist(), "primitives": prims,
            "freeform_faces": int(len(remaining))}, mesh


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\rcosme\Easyfit3d\_stl_test\cuerpo45.stl"
    res, mesh = detect_ransac(path)
    by = {}
    for p in res["primitives"]:
        by[p["type"]] = by.get(p["type"], 0) + 1
    print(f"Malla: {res['n_faces']} caras, diag {res['diag']:.1f} mm")
    print(f"RANSAC: {len(res['primitives'])} primitivas {by}; freeform {res['freeform_faces']} caras")
    for p in res["primitives"]:
        extra = (f" R={p['radius']:.3f}" if p["type"] in ("cylinder", "sphere") else "")
        print(f"  {p['type']:8s} caras={p['n_faces']:4d} RMS={p['rms']:.4f}{extra}")
