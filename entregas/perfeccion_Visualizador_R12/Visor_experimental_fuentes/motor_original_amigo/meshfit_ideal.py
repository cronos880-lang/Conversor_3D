import numpy as np
from scipy.spatial import cKDTree


def _reflect(P, n, d):
    return P - 2.0 * ((P @ n) - d)[:, None] * n


def _vnormals(mesh):
    V = np.asarray(mesh.vertices, float); F = np.asarray(mesh.faces)
    fn = mesh.face_normals * mesh.area_faces[:, None]
    vn = np.zeros((len(V), 3))
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    return vn / (np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12)


def _sym_err(P, V, N, tree, n, d):

    R = _reflect(P, n, d)
    _, k = tree.query(R)
    return np.abs(((R - V[k]) * N[k]).sum(1)), k


def find_symmetry(mesh, verbose=True, sample=8000):

    V = np.asarray(mesh.vertices, float)
    N = _vnormals(mesh)
    diag = float(np.linalg.norm(np.ptp(V, axis=0)))
    rng = np.random.default_rng(0)
    P = V[rng.choice(len(V), min(sample, len(V)), replace=False)]
    tree = cKDTree(V)
    c = V.mean(0)
    _, _, vt = np.linalg.svd(V - c, full_matrices=False)
    out = []
    acc_med = max(0.15, 1e-3 * diag)
    for ax in range(3):
        n = vt[ax].copy(); d = float(c @ n)
        dn0, _ = _sym_err(P, V, N, tree, n, d)
        if np.median(dn0) > 0.05 * diag:
            continue
        for it in range(30):
            dn, k = _sym_err(P, V, N, tree, n, d)
            if it == 6 and np.median(dn) > 5 * acc_med:
                break
            m = dn < np.percentile(dn, 90)
            D = P[m] - V[k[m]]; mid = 0.5 * (P[m] + V[k[m]])
            keep = np.linalg.norm(D, axis=1) > 1e-6
            if keep.sum() < 20:
                break
            _, _, w = np.linalg.svd(D[keep], full_matrices=False)
            n2 = w[0] * np.sign(w[0] @ n); d2 = float(np.median(mid[keep] @ n2))
            done = np.linalg.norm(n2 - n) < 1e-7 and abs(d2 - d) < 1e-6
            n, d = n2, d2
            if done:
                break
        dn, _ = _sym_err(P, V, N, tree, n, d)
        med, p90 = float(np.median(dn)), float(np.percentile(dn, 90))
        ok = med <= acc_med and p90 <= max(0.8, 4e-3 * diag)
        if verbose:
            print(f"  [ajuste IA] plano de simetría {ax}: asimetría mediana {med:.3f} mm, "
                  f"p90 {p90:.3f} mm -> {'SÍ' if ok else 'no'}")
        if ok:
            out.append({"n": n, "d": d, "median": med, "p90": p90})

    uniq = []
    for pl in sorted(out, key=lambda q: q["median"]):
        if all(abs(pl["n"] @ q["n"]) < 0.99 for q in uniq):
            uniq.append(pl)
    return uniq


def symmetrize(mesh, planes, iters=2, verbose=True):

    import trimesh
    V = np.asarray(mesh.vertices, float).copy()
    F = np.asarray(mesh.faces)
    rep = []
    for pl in planes:
        n, d = pl["n"], pl["d"]

        thr = max(0.1, 4.0 * pl["median"])
        moved = None
        for _ in range(iters):
            m_ = trimesh.Trimesh(V, F, process=False)
            N = _vnormals(m_)
            tree = cKDTree(V)
            R = _reflect(V, n, d)
            _, k = tree.query(R)

            S = R - ((R - V[k]) * N[k]).sum(1)[:, None] * N[k]
            gap = np.linalg.norm(S - R, axis=1)
            w = np.clip(1.0 - gap / thr, 0.0, 1.0)
            target = 0.5 * (V + _reflect(S, n, d))
            V = V + w[:, None] * (target - V)
            moved = w
        frac = float((moved > 0.5).mean())
        if pl["median"] < 1e-3:
            rep.append("Simetría espejo: la pieza ya es simétrica exacta (nada que corregir)")
        else:
            rep.append(f"Simetría espejo aplicada (asimetría típica {pl['median']:.2f} mm): "
                       f"{100 * frac:.0f} % de la pieza promediada con su espejo; el resto "
                       f"(rasgos de un solo lado) se conserva")
        if verbose:
            print("  [ajuste IA] " + rep[-1])
    return trimesh.Trimesh(V, F, process=False), rep


def _round_nice(x, tol, steps=(1.0, 0.5, 0.1)):

    for s in steps:
        r = round(x / s) * s
        if abs(r - x) <= tol:
            return float(r)
    return None


def _frame_from_planes(prims):

    ns = []
    for p in prims:
        if p.get("type") == "plane":
            ns.append((np.asarray(p["normal"], float), float(p.get("_w", 1.0))))
    if not ns:
        return []
    ns.sort(key=lambda t: -t[1])
    a0 = ns[0][0] / np.linalg.norm(ns[0][0])
    for n, _w in ns[1:]:
        n = n / np.linalg.norm(n)
        if abs(n @ a0) < np.sin(np.radians(3)):
            a1 = n - (n @ a0) * a0
            a1 /= np.linalg.norm(a1)
            return [a0, a1, np.cross(a0, a1)]
    return [a0]


def _snap_dir(v, frame, deg=2.0):

    v = np.asarray(v, float); v = v / np.linalg.norm(v)
    for a in frame:
        c = float(a @ v)
        if abs(c) >= np.cos(np.radians(deg)):
            return a * np.sign(c), np.arccos(min(1.0, abs(c))) > 1e-4
    return v, False


def _qual(p, pts):
    from meshfit_detect import DEV
    d = DEV[p["type"]](p, pts)
    return float(np.sqrt((d ** 2).mean())), float(np.abs(d).max())


def idealize_prims(prims, pts_list, tol=0.05, verbose=True, cad=False):

    import copy
    P = [copy.deepcopy(p) for p in prims]
    for p, pts in zip(P, pts_list):
        p["_w"] = float(len(pts))
    base = [_qual(p, pts) for p, pts in zip(P, pts_list)]

    tl = [float(np.clip(3.0 * b[0], 0.005, tol)) for b in base]
    if cad:

        tl = [0.002] * len(base)

    def accept(i, q):
        r0, m0 = base[i]
        r1, m1 = _qual(q, pts_list[i])
        if r1 <= r0 + 0.5 * tl[i] and m1 <= m0 + tl[i]:
            P[i] = q
            return True
        return False
    rep = []
    frame = _frame_from_planes(P)

    n_dir = 0
    for i, p in enumerate(P):
        k = {"plane": "normal", "cylinder": "axis", "cone": "axis", "torus": "axis"}.get(p["type"])
        if not k:
            continue
        v2, changed = _snap_dir(p[k], frame)
        if changed:
            q = copy.deepcopy(p); q[k] = v2
            n_dir += accept(i, q)
    if n_dir:
        rep.append(f"{n_dir} cara(s)/eje(s) enderezados a 0°/90° exactos de la dirección principal")

    kq = {"cylinder": "point", "cone": "origin", "torus": "center"}
    axial = [i for i, p in enumerate(P) if p["type"] in kq]
    axial.sort(key=lambda i: -P[i]["_w"])
    n_coax = 0
    done = set()
    for a in axial:
        if a in done:
            continue
        A = P[a]; ax = np.asarray(A["axis"]) / np.linalg.norm(A["axis"]); q0 = np.asarray(A[kq[A["type"]]])
        for b in axial:
            if b == a or b in done:
                continue
            Bp = P[b]
            if abs(np.asarray(Bp["axis"]) @ ax) < np.cos(np.radians(1)):
                continue
            qb = np.asarray(Bp[kq[Bp["type"]]])
            dq = qb - q0
            off = float(np.linalg.norm(dq - (dq @ ax) * ax))
            if off > 3 * max(tl[a], tl[b]):
                continue
            if off < 1e-4 and abs(abs(np.asarray(Bp["axis"]) @ ax) - 1) < 1e-9:
                done.add(b); continue
            q = copy.deepcopy(Bp)
            q[kq[Bp["type"]]] = q0 + (dq @ ax) * ax
            q["axis"] = ax * np.sign(np.asarray(Bp["axis"]) @ ax)
            if accept(b, q):
                n_coax += 1; done.add(b)
        done.add(a)
    if n_coax:
        rep.append(f"{n_coax} eje(s) casi coaxiales unificados en un eje común")

    n_r = []
    for i, p in enumerate(P):
        q = copy.deepcopy(p); txt = None
        if p["type"] in ("cylinder", "sphere"):
            r = _round_nice(2 * float(p["radius"]), 2 * tl[i])
            if r is not None and abs(r / 2 - p["radius"]) > 1e-4:
                q["radius"] = r / 2; txt = f"Ø{2 * float(p['radius']):.3f}→{r:g}"
        elif p["type"] == "torus":
            parts = []
            for k in ("R", "r"):
                r = _round_nice(float(p[k]), tl[i])
                if r is not None and abs(r - p[k]) > 1e-4:
                    parts.append(f"{k} {float(p[k]):.3f}→{r:g}"); q[k] = r
            txt = ", ".join(parts) or None
        elif p["type"] == "cone":
            a = np.degrees(float(p["half_angle"]))
            ar = round(a * 2) / 2
            if 1e-3 < abs(ar - a) <= 0.5:
                q["half_angle"] = np.radians(ar); q["slope"] = float(np.tan(q["half_angle"]))
                txt = f"cono {2 * a:.2f}°→{2 * ar:g}°"
        if txt and accept(i, q):
            n_r.append(txt)
    if n_r:
        rep.append("Medidas redondeadas: " + ", ".join(n_r[:12]) + (" …" if len(n_r) > 12 else ""))

    n_d = []
    for ax in frame:
        pls = [i for i, p in enumerate(P) if p["type"] == "plane"
               and abs(np.asarray(p["normal"]) @ ax) > 1 - 1e-9]
        if len(pls) < 2:
            continue
        ref = max(pls, key=lambda i: P[i]["_w"])
        r0 = float(np.asarray(P[ref]["point"]) @ ax)
        for i, p in enumerate(P):
            if i == ref:
                continue
            if p["type"] == "plane" and i in pls:
                key = "point"
            elif p["type"] in ("cylinder", "cone") and abs(np.asarray(p["axis"]) @ ax) < 1e-9:
                key = kq[p["type"]]
            else:
                continue
            dist = float(np.asarray(p[key]) @ ax) - r0
            r = _round_nice(dist, max(tl[i], tl[ref]))
            if r is None or abs(r - dist) < 1e-4:
                continue
            q = copy.deepcopy(p); q[key] = np.asarray(p[key]) + (r - dist) * ax
            if accept(i, q):
                n_d.append(("" if p["type"] == "plane" else "eje a ") + f"{abs(dist):.3f}→{abs(r):g}")
    if n_d:
        rep.append("Distancias redondeadas (desde la cara de referencia): " +
                   ", ".join(n_d[:12]) + (" …" if len(n_d) > 12 else ""))
    if not rep:
        rep.append("Medidas: ninguna se puede redondear sin salirse de la tolerancia de medida")
    for p in P:
        p.pop("_w", None)
    if verbose:
        for r_ in rep:
            print("  [ajuste IA] " + r_)
    return P, rep

_PREP_CACHE = {}


def ai_prepare(mesh, verbose=True):

    import hashlib
    h = hashlib.md5(np.ascontiguousarray(mesh.faces, dtype=np.int64).tobytes())
    h.update(np.ascontiguousarray(mesh.vertices, dtype=np.float64).tobytes())
    key = h.hexdigest()
    if key in _PREP_CACHE:
        return _PREP_CACHE[key]
    import trimesh
    planes = find_symmetry(mesh, verbose=verbose)
    if planes:
        out, rep = symmetrize(mesh, planes, verbose=verbose)
    else:
        out = trimesh.Trimesh(np.asarray(mesh.vertices, float), np.asarray(mesh.faces), process=False)
        rep = ["Sin simetría clara: no se simetriza (se habría inventado demasiado)"]
    while len(_PREP_CACHE) >= 2:
        _PREP_CACHE.pop(next(iter(_PREP_CACHE)))
    _PREP_CACHE[key] = (out, rep)
    return out, rep


def is_cad_mesh(mesh):

    ang = np.asarray(mesh.face_adjacency_angles)
    return bool(len(ang)) and float((ang < np.radians(0.05)).mean()) > 0.1
