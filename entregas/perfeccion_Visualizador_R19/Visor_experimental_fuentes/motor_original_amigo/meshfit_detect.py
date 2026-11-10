import numpy as np
import trimesh
from trimesh.graph import connected_components


def fit_plane(pts, normals=None, areas=None, cents=None):
    c = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    n = vt[2] / np.linalg.norm(vt[2])
    return {"type": "plane", "point": c, "normal": n}


def dev_plane(p, pts):
    return np.abs((pts - p["point"]) @ p["normal"])


def fit_sphere(pts, normals=None, areas=None, cents=None):
    A = np.hstack([2 * pts, np.ones((len(pts), 1))])
    b = (pts ** 2).sum(axis=1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = sol[:3]
    R = np.sqrt(max(1e-12, sol[3] + c @ c))
    return {"type": "sphere", "center": c, "radius": float(R)}


def dev_sphere(p, pts):
    return np.abs(np.linalg.norm(pts - p["center"], axis=1) - p["radius"])


def _fit_circle_2d(uv):
    A = np.hstack([2 * uv, np.ones((len(uv), 1))])
    b = (uv ** 2).sum(axis=1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = sol[:2]
    R = np.sqrt(max(1e-12, sol[2] + c @ c))
    return c, float(R)


def _axis_from_normals(normals, areas):
    w = areas / areas.sum()
    nbar = (normals * w[:, None]).sum(axis=0)
    X = normals - nbar
    cov = (X * w[:, None]).T @ X
    _, vecs = np.linalg.eigh(cov)
    a = vecs[:, 0]
    return a / np.linalg.norm(a)


def _perp_basis(axis):
    ref = np.array([1.0, 0, 0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1, 0])
    u = np.cross(axis, ref); u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    return u, v


def fit_cylinder(pts, normals, areas, cents=None):
    axis = _axis_from_normals(normals, areas)
    u, v = _perp_basis(axis)
    uv = np.column_stack([pts @ u, pts @ v])
    c2, R = _fit_circle_2d(uv)
    t = pts @ axis
    axis_pt = u * c2[0] + v * c2[1] + axis * t.mean()
    return {"type": "cylinder", "axis": axis, "point": axis_pt, "radius": R,
            "tmin": float(t.min()), "tmax": float(t.max()), "u": u, "v": v, "c2": c2}


def dev_cylinder(p, pts):
    d = pts - p["point"]
    t = d @ p["axis"]
    radial = d - np.outer(t, p["axis"])
    return np.abs(np.linalg.norm(radial, axis=1) - p["radius"])


def fit_cone(pts, normals, areas, cents=None):
    axis = _axis_from_normals(normals, areas)
    origin = pts.mean(axis=0)
    d = pts - origin
    t = d @ axis
    if float(t.max() - t.min()) < 1e-9:
        return None
    radial = np.linalg.norm(d - np.outer(t, axis), axis=1)

    m, b = np.polyfit(t, radial, 1)
    if m < 0:
        axis = -axis; t = -t
        m, b = np.polyfit(t, radial, 1)
    half = float(np.arctan(abs(m)))
    return {"type": "cone", "axis": axis, "origin": origin, "half_angle": half,
            "tmin": float(t.min()), "tmax": float(t.max()),
            "r_base": float(m * t.min() + b), "r_top": float(m * t.max() + b), "slope": float(m), "b": float(b)}


def dev_cone(p, pts):
    d = pts - p["origin"]
    t = d @ p["axis"]
    radial = np.linalg.norm(d - np.outer(t, p["axis"]), axis=1)
    r_ideal = p["slope"] * t + p["b"]
    return np.abs(radial - r_ideal) * np.cos(p["half_angle"])


def _torus_from_axis(pts, axis, q):

    d = pts - q
    h = d @ axis
    rho = np.linalg.norm(d - np.outer(h, axis), axis=1)
    c2, r = _fit_circle_2d(np.column_stack([rho, h]))
    R, h0 = float(c2[0]), float(c2[1])
    if not (R > r > 0):
        return None
    return {"type": "torus", "center": q + axis * h0, "axis": axis, "R": R, "r": r}


def fit_torus(pts, normals, areas, cents=None):

    c0 = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c0, full_matrices=False)
    axis = vt[2] / np.linalg.norm(vt[2])
    best = _torus_from_axis(pts, axis, c0)
    if cents is None or best is None:
        return best
    best_rms = stats(best, pts)[0]
    r = best["r"]
    for sign in (-1.0, 1.0):
        cur_r = r
        for _ in range(3):
            tc = cents + sign * cur_r * normals
            cq = tc.mean(axis=0)
            _, _, vt2 = np.linalg.svd(tc - cq, full_matrices=False)
            a2 = vt2[2] / np.linalg.norm(vt2[2])

            e1, e2 = _perp_basis(a2)
            d2 = tc - cq
            c2, _Rc = _fit_circle_2d(np.column_stack([d2 @ e1, d2 @ e2]))
            q = cq + e1 * c2[0] + e2 * c2[1]
            prim = _torus_from_axis(pts, a2, q)
            if prim is None:
                break
            rms = stats(prim, pts)[0]
            if rms < best_rms:
                best, best_rms = prim, rms
            if abs(prim["r"] - cur_r) < 1e-6:
                break
            cur_r = prim["r"]
    return best


def dev_torus(p, pts):
    d = pts - p["center"]
    h = d @ p["axis"]
    rho = np.linalg.norm(d - np.outer(h, p["axis"]), axis=1)
    return np.abs(np.sqrt((rho - p["R"]) ** 2 + h ** 2) - p["r"])

DEV = {"plane": dev_plane, "sphere": dev_sphere, "cylinder": dev_cylinder,
       "cone": dev_cone, "torus": dev_torus}
FIT = {"plane": fit_plane, "sphere": fit_sphere, "cylinder": fit_cylinder,
       "cone": fit_cone, "torus": fit_torus}

PENALTY = {"plane": 1.0, "cylinder": 1.05, "sphere": 1.08, "cone": 1.2, "torus": 1.3}


def stats(prim, pts):
    dev = DEV[prim["type"]](prim, pts)
    return float(np.sqrt((dev ** 2).mean())), float(np.abs(dev).max())


def _degenerate(ty, prim, diag):

    if ty == "cylinder" and prim["radius"] > 3 * diag:
        return True
    if ty == "sphere" and prim["radius"] > 5 * diag:
        return True
    if ty == "torus" and (prim["R"] > 3 * diag or prim["r"] > diag):
        return True
    if ty == "cone":
        ha = np.degrees(prim["half_angle"])
        if ha < 3 or ha > 87:
            return True
    return False

SCORE_EPS = 1e-4


def _near_planar(prim, diag):

    ty = prim["type"]
    if ty in ("cylinder", "sphere") and prim["radius"] > 1.5 * diag:
        return True
    if ty == "torus" and prim["R"] > 1.5 * diag:
        return True
    if ty == "cone" and np.degrees(prim["half_angle"]) > 85:
        return True
    return False

MIN_CURVED_FACES = 6

NORMAL_GATE = np.cos(np.radians(30.0))
NORMAL_W = 0.05

FLAT_SPREAD_DEG = 15.0


def _normal_dots(prim, cents, normals):

    ty = prim["type"]
    if ty == "plane":
        na = np.broadcast_to(np.asarray(prim["normal"], float), cents.shape)
    elif ty == "sphere":
        d = cents - prim["center"]
        na = d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-30)
    elif ty == "cylinder":
        d = cents - prim["point"]
        rad = d - np.outer(d @ prim["axis"], prim["axis"])
        na = rad / (np.linalg.norm(rad, axis=1, keepdims=True) + 1e-30)
    elif ty == "cone":
        a = np.asarray(prim["axis"], float)
        d = cents - prim["origin"]
        rad = d - np.outer(d @ a, a)
        rhat = rad / (np.linalg.norm(rad, axis=1, keepdims=True) + 1e-30)
        na = rhat - prim["slope"] * a
        na = na / np.linalg.norm(na, axis=1, keepdims=True)
    elif ty == "torus":
        a = np.asarray(prim["axis"], float)
        d = cents - prim["center"]
        rad = d - np.outer(d @ a, a)
        rhat = rad / (np.linalg.norm(rad, axis=1, keepdims=True) + 1e-30)
        d2 = cents - (prim["center"] + prim["R"] * rhat)
        na = d2 / (np.linalg.norm(d2, axis=1, keepdims=True) + 1e-30)
    else:
        return np.ones(len(normals))
    return np.abs((na * normals).sum(axis=1))


def _normal_alignment(prim, cents, normals, areas):

    dots = _normal_dots(prim, cents, normals)
    w = areas / (areas.sum() + 1e-30)
    return float((w * dots).sum())


def classify_region(pts, normals, areas, diag, rms_tol_rel, cents=None):

    n_faces = len(normals)

    rdiag = float(np.linalg.norm(pts.max(0) - pts.min(0))) or diag

    pl = fit_plane(pts)
    pr, pm = stats(pl, pts)
    pl["rms"], pl["max"] = pr, pm
    plane_ok = (pr / diag) < rms_tol_rel

    pl_ndev = 0.0
    if cents is not None:
        pl_align = _normal_alignment(pl, cents, normals, areas)
        pl_ndev = float(np.arccos(min(1.0, pl_align)))
        pl["ndev_deg"] = float(np.degrees(pl_ndev))

    cands = []
    if plane_ok:
        cands.append(((pr / diag + NORMAL_W * pl_ndev + SCORE_EPS) * PENALTY["plane"], pl))
    if n_faces >= MIN_CURVED_FACES:
        for ty in ("cylinder", "sphere", "cone", "torus"):
            try:
                prim = FIT[ty](pts, normals, areas, cents)
            except Exception:
                prim = None
            if not prim or _degenerate(ty, prim, diag):
                continue
            rms, mx = stats(prim, pts)
            prim["rms"], prim["max"] = rms, mx
            if (rms / diag) >= rms_tol_rel:
                continue
            ndev = 0.0
            if cents is not None:
                align = _normal_alignment(prim, cents, normals, areas)
                if align < NORMAL_GATE:
                    continue
                ndev = float(np.arccos(min(1.0, align)))
                prim["ndev_deg"] = float(np.degrees(ndev))
            cands.append(((rms / diag + NORMAL_W * ndev + SCORE_EPS) * PENALTY[ty], prim))

    if not cands:
        return None
    cands.sort(key=lambda c: c[0])
    best = cands[0][1]

    if plane_ok and best["type"] != "plane":
        w = areas / (areas.sum() + 1e-30)
        m = (normals * w[:, None]).sum(axis=0)
        m = m / (np.linalg.norm(m) + 1e-30)
        spread = float((w * np.degrees(np.arccos(np.clip(normals @ m, -1.0, 1.0)))).sum())
        if best["rms"] > 0.5 * pl["rms"] or _near_planar(best, rdiag) or spread < FLAT_SPREAD_DEG:
            best = pl
    return best


def _segment_regions(mesh, angle_tol_deg, flat_tol_deg):

    n = len(mesh.faces)
    adj = mesh.face_adjacency
    ang = mesh.face_adjacency_angles
    smooth = ang < np.radians(angle_tol_deg)

    max_smooth_ang = np.zeros(n)
    has_smooth = np.zeros(n, dtype=bool)
    for (i, j), a in zip(adj[smooth], ang[smooth]):
        has_smooth[i] = has_smooth[j] = True
        if a > max_smooth_ang[i]:
            max_smooth_ang[i] = a
        if a > max_smooth_ang[j]:
            max_smooth_ang[j] = a
    flat_tol = np.radians(flat_tol_deg)
    is_flat = (max_smooth_ang < flat_tol)

    is_flat[~has_smooth] = True

    coplanar = (ang < flat_tol) & is_flat[adj[:, 0]] & is_flat[adj[:, 1]]
    plane_edges = adj[coplanar]
    plane_nodes = np.nonzero(is_flat)[0]
    regions = []
    if len(plane_nodes):
        for c in connected_components(plane_edges, nodes=plane_nodes, min_len=1):
            regions.append(np.asarray(c))

    curved = smooth & (~is_flat[adj[:, 0]]) & (~is_flat[adj[:, 1]])
    curved_edges = adj[curved]
    curved_nodes = np.nonzero(~is_flat)[0]
    if len(curved_nodes):
        for c in connected_components(curved_edges, nodes=curved_nodes, min_len=1):
            regions.append(np.asarray(c))

    regions.sort(key=len, reverse=True)
    return regions


def _segment_smooth(mesh, angle_tol_deg):

    n = len(mesh.faces)
    adj = mesh.face_adjacency
    ang = mesh.face_adjacency_angles
    edges = adj[ang < np.radians(angle_tol_deg)]
    comps = connected_components(edges, nodes=np.arange(n), min_len=1)
    regions = sorted((np.asarray(c) for c in comps), key=len, reverse=True)
    return regions


def _looks_like_scan(mesh, angle_tol_deg, frac=0.8, min_faces=10000, coplanar_max=0.03):

    n = len(mesh.faces)
    if n < min_faces:
        return False
    ang = mesh.face_adjacency_angles
    if len(ang) and float((ang < np.radians(0.05)).mean()) > coplanar_max:
        return False
    regions = _segment_smooth(mesh, angle_tol_deg)
    return bool(regions) and len(regions[0]) >= frac * n

SPLIT_FACE_DEG = 35.0
SPLIT_MIN_BAD = 4
SPLIT_MAX_DEPTH = 3
PEEL_TOL = 0.5


def _peel_flat_cluster(mesh, region, normals, areas, diag, rms_tol_rel):

    order = np.argsort(areas)[::-1][:8]
    cos_tol = np.cos(np.radians(SPLIT_FACE_DEG))
    total_area = float(areas.sum())
    best = None
    for s in order:
        mask = (normals @ normals[s]) > cos_tol
        n_in = int(mask.sum())
        if n_in < MIN_CURVED_FACES or mask.all() or int((~mask).sum()) < SPLIT_MIN_BAD:
            continue
        a = float(areas[mask].sum())
        if a < 0.1 * total_area:
            continue
        vidx = np.unique(mesh.faces[region[mask]].ravel())
        pts = mesh.vertices[vidx]
        pl = fit_plane(pts)
        rms, _ = stats(pl, pts)
        if (rms / diag) < PEEL_TOL * rms_tol_rel and (best is None or a > best[0]):
            best = (a, mask)
    if best is None:
        return None
    return region[best[1]], region[~best[1]]


def _components(mesh, faces):

    faces = np.asarray(faces, int)
    if len(faces) == 0:
        return []
    mask = np.zeros(len(mesh.faces), dtype=bool)
    mask[faces] = True
    adj = mesh.face_adjacency
    edges = adj[mask[adj[:, 0]] & mask[adj[:, 1]]]
    return [np.asarray(c) for c in connected_components(edges, nodes=faces, min_len=1)]


def detect(path, angle_tol_deg=32.0, min_faces=2, rms_tol_rel=0.01, flat_tol_deg=8.0,
           scan_mode=False):

    from collections import deque
    mesh = trimesh.load(path, force="mesh")
    mesh.merge_vertices()
    diag = float(np.linalg.norm(mesh.bounds[1] - mesh.bounds[0])) or 1.0

    if scan_mode == "auto":
        scan_mode = _looks_like_scan(mesh, angle_tol_deg)

    if scan_mode:
        regions = _segment_smooth(mesh, angle_tol_deg)
    else:
        regions = _segment_regions(mesh, angle_tol_deg, flat_tol_deg)

    fnormals = mesh.face_normals
    fareas = mesh.area_faces
    verts = mesh.vertices

    result = {"diag": diag, "n_faces": int(len(mesh.faces)),
              "n_verts": int(len(mesh.vertices)),
              "bbox": mesh.bounds.tolist(), "primitives": [], "freeform_faces": 0,
              "freeform_regions": []}

    split_cos = np.cos(np.radians(SPLIT_FACE_DEG))
    queue = deque((np.asarray(r), 0) for r in regions)
    while queue:
        region, depth = queue.popleft()
        if len(region) < min_faces:
            continue
        if scan_mode:

            result["freeform_faces"] += len(region)
            result["freeform_regions"].append(region.tolist())
            continue
        vidx = np.unique(mesh.faces[region].ravel())
        pts = verts[vidx]
        normals = fnormals[region]
        areas = fareas[region]
        cents = verts[mesh.faces[region]].mean(axis=1)
        prim = classify_region(pts, normals, areas, diag, rms_tol_rel, cents=cents)

        if (prim is not None and prim["type"] != "plane" and depth < SPLIT_MAX_DEPTH):
            dots = _normal_dots(prim, cents, normals)
            bad = dots < split_cos
            if int(bad.sum()) >= SPLIT_MIN_BAD and int((~bad).sum()) >= MIN_CURVED_FACES:
                for sub in _components(mesh, region[~bad]) + _components(mesh, region[bad]):
                    queue.append((sub, depth + 1))
                continue
        if prim is None:

            if depth < SPLIT_MAX_DEPTH:
                peel = _peel_flat_cluster(mesh, region, normals, areas, diag, rms_tol_rel)
                if peel is not None:
                    for sub in _components(mesh, peel[0]) + _components(mesh, peel[1]):
                        queue.append((sub, depth + 1))
                    continue

            result["freeform_faces"] += len(region)
            result["freeform_regions"].append(region.tolist())
            continue
        prim["faces"] = region.tolist()
        prim["n_faces"] = int(len(region))
        result["primitives"].append(prim)

    return result, mesh


def _summary(res):
    by = {}
    for p in res["primitives"]:
        by[p["type"]] = by.get(p["type"], 0) + 1
    return by

if __name__ == "__main__":
    import sys, json
    path = sys.argv[1] if len(sys.argv) > 1 else r"pieza.stl"
    tol = float(sys.argv[2]) if len(sys.argv) > 2 else 32.0
    res, mesh = detect(path, angle_tol_deg=tol)
    print(f"Malla: {res['n_faces']} caras, {res['n_verts']} vértices, diag {res['diag']:.1f} mm")
    print(f"Primitivas: {len(res['primitives'])}  por tipo {_summary(res)}")
    print(f"Caras sin clasificar (freeform): {res['freeform_faces']}")
    for p in res["primitives"]:
        extra = ""
        if p["type"] == "cylinder":
            extra = f" R={p['radius']:.3f} L={p['tmax']-p['tmin']:.1f}"
        elif p["type"] == "sphere":
            extra = f" R={p['radius']:.3f}"
        elif p["type"] == "cone":
            extra = f" semiang={np.degrees(p['half_angle']):.1f}"
        elif p["type"] == "torus":
            extra = f" R={p['R']:.3f} r={p['r']:.3f}"
        print(f"  {p['type']:8s} caras={p['n_faces']:4d} RMS={p['rms']:.4f}{extra}")
