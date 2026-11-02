import numpy as np
import scipy.sparse as sps
from scipy.sparse.linalg import spsolve

from meshfit_organic import (band_segments, _band, _face_adj_matrix, _fill_selection,
                             _annulus_param, _vertex_normals, _design, periodic_design,
                             periodic_bspline, _Coefs, OVERLAP, MAX_KNOTS, smooth_length)

COUPLE = 1000.0
BAND_L = 2.0
PARAM_ITERS = 2
CAP_STEP = 0.0
ALONG_STEP = 0.0


def _dmat(m, order, cyclic=False):
    st = {2: [1.0, -2.0, 1.0], 3: [-1.0, 3.0, -3.0, 1.0]}[order]
    if cyclic:
        rows = np.repeat(np.arange(m), len(st))
        cols = (np.arange(m)[:, None] + np.arange(len(st))[None, :]).ravel() % m
        return sps.csr_matrix((np.tile(st, m), (rows, cols)), shape=(m, m))
    k = m - len(st) + 1
    if k <= 0:
        return sps.csr_matrix((0, m))
    rows = np.repeat(np.arange(k), len(st))
    cols = (np.arange(k)[:, None] + np.arange(len(st))[None, :]).ravel()
    return sps.csr_matrix((np.tile(st, k), (rows, cols)), shape=(k, m))


def _penalty3(nbu, nbv, su, sv, cyclic_u=False):

    Du, Dv = _dmat(nbu, 3, cyclic_u), _dmat(nbv, 3)
    P = sps.kron(Du.T @ Du, sps.identity(nbv)) / su ** 6
    if Dv.shape[0]:
        P = P + sps.kron(sps.identity(nbu), Dv.T @ Dv) / sv ** 6
    return (P * (su * sv)).tocsr()


def _height_model(mesh, faces, ns, band, step):

    faces = np.asarray(faces, int)
    w = mesh.area_faces[faces]
    n = (ns[faces] * w[:, None]).sum(0); n /= np.linalg.norm(n)
    own_v = np.unique(mesh.faces[faces].ravel())
    band = band[ns[band] @ n > 0.2] if band is not None and len(band) else np.zeros(0, int)
    bv = np.setdiff1d(np.unique(mesh.faces[band].ravel()), own_v) if len(band) else np.zeros(0, int)
    vidx = np.r_[own_v, bv]
    Pv = mesh.vertices[vidx]
    c0 = mesh.vertices[own_v].mean(0)
    t = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    x0 = np.cross(n, t); x0 /= np.linalg.norm(x0); y0 = np.cross(n, x0)
    d2 = np.c_[(mesh.vertices[own_v] - c0) @ x0, (mesh.vertices[own_v] - c0) @ y0]
    _, _, vt = np.linalg.svd(d2 - d2.mean(0), full_matrices=False)
    x = vt[0, 0] * x0 + vt[0, 1] * y0; y = np.cross(n, x)
    A = Pv - c0
    u, v, h = A @ x, A @ y, A @ n
    lu, lv = float(np.ptp(u)), float(np.ptp(v))
    bb = [u.min() - 0.03 * lu - 1e-3, u.max() + 0.03 * lu + 1e-3,
          v.min() - 0.03 * lv - 1e-3, v.max() + 0.03 * lv + 1e-3]
    st_ = max(max(lu, lv) / MAX_KNOTS, step)
    ku = int(np.clip(round(lu / st_), 3, MAX_KNOTS)); kv = int(np.clip(round(lv / st_), 3, MAX_KNOTS))
    tx = np.linspace(bb[0], bb[1], ku + 2)[1:-1]; ty = np.linspace(bb[2], bb[3], kv + 2)[1:-1]
    tu = np.r_[[bb[0]] * 4, tx, [bb[1]] * 4]; tv = np.r_[[bb[2]] * 4, ty, [bb[3]] * 4]
    B = _design(u, v, tu, tv)
    su, sv = (bb[1] - bb[0]) / (ku + 1), (bb[3] - bb[2]) / (kv + 1)
    area = float(mesh.area_faces[faces].sum() + (mesh.area_faces[band].sum() if len(band) else 0))
    return {"kind": "height", "vidx": vidx, "no": len(own_v), "B": B.tocsr(), "dim": 1,
            "nb": B.shape[1], "target": h, "P": _penalty3(len(tu) - 4, len(tv) - 4, su, sv),
            "rho": len(vidx) / max(area, 1e-9), "frame": (c0, x, y, n), "u": u, "v": v,
            "knots": (tx, ty, bb)}


def _band_model(mesh, faces, band, vn, step, step_t=None):

    sel = np.zeros(len(mesh.faces), bool); sel[faces] = True
    if band is not None and len(band):
        sel[band] = True
    sel = _fill_selection(mesh, sel, keep=2)
    pr = _annulus_param(mesh, np.where(sel)[0])
    if pr is None:
        return None
    used, th, t, Lm, Wm = pr
    own = np.isin(used, np.unique(np.asarray(mesh.faces)[faces]))
    order = np.r_[np.where(own)[0], np.where(~own)[0]]
    th, t, vidx = th[order], t[order], used[order]
    lo, hi = float(t.min()) - 0.03, float(t.max()) + 0.03
    nth = int(np.clip(round(Lm / step), 16, 600))
    nts = int(np.clip(round(Wm * (hi - lo) / (step_t or step)), 1, 80))
    tv = np.r_[[lo] * 4, np.linspace(lo, hi, nts + 2)[1:-1], [hi] * 4]
    B = periodic_design(th, t, nth, tv, lo, hi)
    sth, sts = Lm / nth, Wm * (hi - lo) / (nts + 1)
    area = float(mesh.area_faces[np.where(sel)[0]].sum())
    return {"kind": "band", "vidx": vidx, "no": int(own.sum()), "B": B.tocsr(), "dim": 3,
            "nb": B.shape[1], "target": np.asarray(mesh.vertices, float)[vidx],
            "N": vn[vidx], "P": _penalty3(nth, len(tv) - 4, sth, sts, cyclic_u=True),
            "rho": len(vidx) / max(area, 1e-9), "per": (nth, len(tv) - 4, tv),
            "th": th.copy(), "t": t.copy(), "lo": lo, "hi": hi, "R": Lm / (2 * np.pi)}


def _band_reparam(m, Cm, max_step=1.0):

    nth, ncs, tv = m["per"]
    th, t, lo, hi = m["th"], m["t"], m["lo"], m["hi"]
    d = 1e-4

    def S(a, b):
        return periodic_design(a, np.clip(b, lo, hi - 1e-9), nth, tv, lo, hi) @ Cm
    P0 = S(th, t)
    St = (S(th + d, t) - S(th - d, t)) / (2 * d)
    Su = (S(th, t + d) - S(th, t - d)) / (2 * d)
    r = m["target"] - P0
    a11 = (St * St).sum(1); a12 = (St * Su).sum(1); a22 = (Su * Su).sum(1)
    b1 = (St * r).sum(1); b2 = (Su * r).sum(1)
    det = a11 * a22 - a12 * a12
    ok = det > 1e-12
    dth = np.where(ok, (a22 * b1 - a12 * b2) / np.where(ok, det, 1), 0.0)
    dt = np.where(ok, (a11 * b2 - a12 * b1) / np.where(ok, det, 1), 0.0)

    mv = np.sqrt(a11 * dth ** 2 + a22 * dt ** 2)
    f = np.minimum(1.0, max_step / np.maximum(mv, 1e-12))
    m["th"] = np.mod(th + f * dth, 2 * np.pi)
    m["t"] = np.clip(t + f * dt, lo, hi - 1e-9)
    m["B"] = periodic_design(m["th"], m["t"], nth, tv, lo, hi).tocsr()
    return float(np.median(mv))


def _eval_ops(m, off, ntot, rows=None):

    B = m["B"] if rows is None else m["B"][rows]
    n = B.shape[0]
    if m["kind"] == "height":
        c0, x, y, nn = m["frame"]
        u = m["u"] if rows is None else m["u"][rows]
        v = m["v"] if rows is None else m["v"][rows]
        blocks, e0 = [], []
        for k in range(3):
            Ek = sps.hstack([sps.csr_matrix((n, off)), nn[k] * B,
                             sps.csr_matrix((n, ntot - off - m["nb"]))]).tocsr()
            blocks.append(Ek); e0.append(c0[k] + u * x[k] + v * y[k])
        return sps.vstack(blocks).tocsr(), np.concatenate(e0)
    blocks = []
    for k in range(3):
        o = off + k * m["nb"]
        blocks.append(sps.hstack([sps.csr_matrix((n, o)), B,
                                  sps.csr_matrix((n, ntot - o - m["nb"]))]).tocsr())
    return sps.vstack(blocks).tocsr(), np.zeros(3 * n)


def _offset_ops(m, off, ntot, rows, vn):

    B = m["B"][rows]
    n = B.shape[0]
    N = vn[m["vidx"][rows]]
    if m["kind"] == "height":
        nn = m["frame"][3]
        f = N @ nn
        R = sps.hstack([sps.csr_matrix((n, off)), sps.diags(f) @ B,
                        sps.csr_matrix((n, ntot - off - m["nb"]))]).tocsr()
        return R, -f * m["target"][rows]
    blocks = []
    for k in range(3):
        o = off + k * m["nb"]
        blocks.append(sps.hstack([sps.csr_matrix((n, o)), sps.diags(N[:, k]) @ B,
                                  sps.csr_matrix((n, ntot - o - m["nb"]))]).tocsr())
    R = (blocks[0] + blocks[1] + blocks[2]).tocsr()
    return R, -(m["target"][rows] * N).sum(1)

_CACHE = {}


def fair_surfaces_cached(mesh, smooth, verbose=True, L=None):

    from meshfit_organic import _key
    key = _key(mesh, -1.0, L if L is not None else smooth_length(smooth))
    if key in _CACHE:
        return _CACHE[key]
    out = fair_surfaces(mesh, smooth, verbose=verbose, L=L)
    while len(_CACHE) >= 2:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = out
    return out

FIT_L = 1.0


def _cluster_decimate(V, F, p):

    import trimesh
    key = np.floor((V - V.min(0)) / p).astype(np.int64)
    _, cid, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    cid = cid.ravel()
    Vc = np.zeros((cid.max() + 1, 3)); np.add.at(Vc, cid, V); Vc /= cnt[:, None]
    Fc = cid[F]
    ok = (Fc[:, 0] != Fc[:, 1]) & (Fc[:, 1] != Fc[:, 2]) & (Fc[:, 0] != Fc[:, 2])
    Fc = Fc[ok]
    _, first = np.unique(np.sort(Fc, axis=1), axis=0, return_index=True)
    m = trimesh.Trimesh(Vc, Fc[np.sort(first)], process=False)
    m.remove_unreferenced_vertices()
    return m


def _pinch_vertices(F, nv):

    from scipy.sparse.csgraph import connected_components
    F = np.asarray(F)
    v = np.r_[F[:, 0], F[:, 1], F[:, 2]]
    a = np.r_[F[:, 1], F[:, 2], F[:, 0]]; b = np.r_[F[:, 2], F[:, 0], F[:, 1]]
    keys, inv = np.unique(np.r_[v.astype(np.int64) * nv + a, v.astype(np.int64) * nv + b],
                          return_inverse=True)
    n = len(keys); ia, ib = inv[:len(v)], inv[len(v):]
    _, comp = connected_components(sps.coo_matrix((np.ones(len(ia)), (ia, ib)), shape=(n, n)),
                                   directed=False)
    pairs = np.unique(np.c_[keys // nv, comp], axis=0)
    return np.where(np.bincount(pairs[:, 0], minlength=nv) > 1)[0]


def _clean_coarse(mc):

    import trimesh
    from meshfit_repair import repair_mesh
    for _ in range(4):
        F = np.asarray(mc.faces)
        e = np.sort(np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], axis=1)
        _, inv, c = np.unique(e, axis=0, return_inverse=True, return_counts=True)
        bad = np.zeros(len(F), bool)
        bad[np.tile(np.arange(len(F)), 3)[c[inv.ravel()] > 2]] = True
        bad |= np.isin(F, _pinch_vertices(F, len(mc.vertices))).any(1)
        if not bad.any() and mc.is_watertight:
            return mc
        mc = trimesh.Trimesh(mc.vertices, F[~bad], process=False)
        mc.remove_unreferenced_vertices()
        mc, _, _ = repair_mesh(mc, verbose=False, max_hole_frac=0.1)
    ok = mc.is_watertight and mc.is_winding_consistent and \
        not len(_pinch_vertices(mc.faces, len(mc.vertices)))
    return mc if ok else None


def fair_mesh(mesh, L, verbose=True):

    import time
    import trimesh
    from scipy.sparse.linalg import factorized
    t0 = time.time()
    V0 = np.asarray(mesh.vertices, float); F = np.asarray(mesh.faces)
    diag = float(np.linalg.norm(np.ptp(V0, axis=0)))
    p = float(np.clip(diag / 200.0, 0.4, 1.5))
    mc = _clean_coarse(_cluster_decimate(V0, F, p))
    if mc is None or len(mc.faces) < 3000:
        if verbose:
            print("  [armónico] la malla simplificada no quedó limpia -> sin fase 1")
        return None
    X0 = np.asarray(mc.vertices, float); Fc = np.asarray(mc.faces); n = len(X0)
    e = np.unique(np.sort(np.r_[Fc[:, [0, 1]], Fc[:, [1, 2]], Fc[:, [2, 0]]], axis=1), axis=0)
    A = sps.coo_matrix((np.ones(2 * len(e)), (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])),
                       shape=(n, n)).tocsr()
    A.data[:] = 1.0
    Lp = (sps.identity(n) - sps.diags(1.0 / np.asarray(A.sum(1)).ravel()) @ A).tocsr()
    G = sps.coo_matrix((np.r_[np.ones(len(e)), -np.ones(len(e))],
                        (np.r_[np.arange(len(e)), np.arange(len(e))], np.r_[e[:, 0], e[:, 1]])),
                       shape=(len(e), n)).tocsr()
    GL = (G @ Lp).tocsr()
    M3 = (GL.T @ GL).tocsc()
    h = float(np.median(np.linalg.norm(X0[e[:, 0]] - X0[e[:, 1]], axis=1)))
    alpha = (L / h) ** 6
    w = np.ones(n); X = X0
    for _ in range(2):
        solve = factorized((sps.diags(w) + alpha * M3).tocsc())
        X = np.stack([solve(w * X0[:, c]) for c in range(3)], axis=1)
        R = X0 - X
        X = X + np.stack([solve(w * R[:, c]) for c in range(3)], axis=1)
        nrm = trimesh.Trimesh(X, Fc, process=False).vertex_normals
        r = np.abs(((X0 - X) * nrm).sum(1))
        sig = 1.4826 * float(np.median(r)) + 1e-12
        w = np.minimum(1.0, 2.0 * sig / np.maximum(r, 1e-12))
    out = trimesh.Trimesh(X, Fc, process=False)
    if verbose:
        print(f"  [armónico] fase 1: malla de {len(Fc)} triángulos alisada (L {L:.1f} mm, "
              f"volumen {100 * (out.volume / mc.volume - 1):+.2f} %) en {time.time() - t0:.1f}s")
    return out

_MESH_CACHE = {}


def fair_mesh_cached(mesh, L, verbose=True):
    from meshfit_organic import _key
    key = _key(mesh, -2.0, L)
    if key not in _MESH_CACHE:
        while len(_MESH_CACHE) >= 2:
            _MESH_CACHE.pop(next(iter(_MESH_CACHE)))
        _MESH_CACHE[key] = fair_mesh(mesh, L, verbose=verbose)
    return _MESH_CACHE[key]


def harmonic(mesh, smooth, verbose=True):

    L = smooth_length(smooth)
    coarse = fair_mesh_cached(mesh, L, verbose=verbose)
    if coarse is not None:
        r = fair_surfaces_cached(coarse, smooth, verbose=verbose, L=min(FIT_L, L))
        if r is not None:
            return (coarse,) + tuple(r)
    r = fair_surfaces_cached(mesh, smooth, verbose=verbose)
    return None if r is None else (mesh,) + tuple(r)


def fair_surfaces(mesh, smooth, verbose=True, L=None):

    import time
    from meshfit_brep import _height_spline_to_bspline
    t0 = time.time()
    L = smooth_length(smooth) if L is None else L
    sg = band_segments(mesh, verbose=verbose)
    if sg is None:
        return None
    segs, kinds, ns = sg
    diag = float(np.linalg.norm(mesh.extents))
    Af = _face_adj_matrix(mesh)
    F = np.asarray(mesh.faces); V = np.asarray(mesh.vertices, float)
    h = float(np.median(np.linalg.norm(V[F[:, 0]] - V[F[:, 1]], axis=1)))

    rings = int(np.clip(round(max(OVERLAP * diag, BAND_L * L) / h), 2, 40))
    vn = _vertex_normals(mesh)
    step = max(1.2, 0.5 * L)
    cap_step = max(step, CAP_STEP)
    along = max(step, ALONG_STEP)
    models = []
    for f, kd in zip(segs, kinds):
        bandf = _band(Af, f, rings)
        m = (_band_model(mesh, f, bandf, vn, along, step) if kd == 2
             else _height_model(mesh, f, ns, bandf, cap_step))
        if m is None:
            return None
        models.append(m)
    offs = np.cumsum([0] + [m["dim"] * m["nb"] for m in models])
    ntot = int(offs[-1])

    where = {}
    for mi, m in enumerate(models):
        for r, vtx in enumerate(m["vidx"].tolist()):
            where.setdefault(vtx, []).append((mi, r))
    pairs = {}
    for vtx, lst in where.items():
        if len(lst) >= 2:
            for a in range(len(lst)):
                for b in range(a + 1, len(lst)):
                    (ma, ra), (mb, rb) = lst[a], lst[b]
                    pairs.setdefault((ma, mb), ([], []))
                    pairs[(ma, mb)][0].append(ra); pairs[(ma, mb)][1].append(rb)

    Pblocks = []
    for m in models:
        lam = m["rho"] * L ** 6
        Pblocks += [lam * m["P"]] * m["dim"]
    Pg = sps.block_diag(Pblocks, format="csr")

    def assemble():
        Cs, cs = [], []
        for (ma, mb), (ra, rb) in pairs.items():
            ra, rb = np.array(ra), np.array(rb)
            rows_a, ca = _offset_ops(models[ma], offs[ma], ntot, ra, vn)
            rows_b, cb = _offset_ops(models[mb], offs[mb], ntot, rb, vn)
            Cs.append(rows_a - rows_b); cs.append(cb - ca)
        Cp = sps.vstack(Cs).tocsr() if Cs else sps.csr_matrix((0, ntot))
        cp = np.concatenate(cs) if cs else np.zeros(0)
        Ds, ts = [], []
        for mi, m in enumerate(models):
            if m["kind"] == "height":
                D = sps.hstack([sps.csr_matrix((m["B"].shape[0], offs[mi])), m["B"],
                                sps.csr_matrix((m["B"].shape[0], ntot - offs[mi] - m["nb"]))]).tocsr()
                Ds.append(D); ts.append(m["target"])
            else:
                E, _e = _eval_ops(m, offs[mi], ntot)
                Ds.append(E); ts.append(m["target"].T.ravel())
        return Cp, cp, sps.vstack(Ds).tocsr(), np.concatenate(ts)
    w = None
    slip = []
    for it in range(int(PARAM_ITERS) + 1):
        Cp, cp, D, tgt = assemble()
        if w is None:
            w = np.ones(D.shape[0])
        K = (D.T @ sps.diags(w) @ D + (Cp.T @ Cp) * COUPLE + Pg).tocsc()
        z = spsolve(K, D.T @ (w * tgt) + (Cp.T @ cp) * COUPLE)
        r = D @ z - tgt
        sig = 1.4826 * float(np.median(np.abs(r))) + 1e-9
        w = np.minimum(1.0, 2.0 * sig / np.maximum(np.abs(r), 1e-12))
        if it < PARAM_ITERS:
            for mi, m in enumerate(models):
                if m["kind"] == "band":
                    slip.append(_band_reparam(m, z[offs[mi]:offs[mi + 1]].reshape(3, m["nb"]).T))

    labels = np.full(len(F), -1, int)
    surfs, errs, pst = [], [], []
    vdev = np.full(len(V), np.nan)
    for mi, (m, f) in enumerate(zip(models, segs)):
        zc = z[offs[mi]:offs[mi + 1]]
        no = m["no"]
        if m["kind"] == "height":
            tx, ty, bb = m["knots"]
            c0, x, y, nn = m["frame"]
            surf = _height_spline_to_bspline(_Coefs(zc), tx, ty, bb, c0, x, y, nn)
            rr = (m["B"] @ zc - m["target"])[:no] * (vn[m["vidx"][:no]] @ nn)
            grid = f"{len(tx) + 4}×{len(ty) + 4}"
        else:
            nth, ncs, tv = m["per"]
            Cm = zc.reshape(3, m["nb"]).T
            surf = periodic_bspline(Cm, nth, ncs, tv)
            rr = (((m["B"] @ Cm) - m["target"]) * m["N"]).sum(1)[:no]
            grid = f"{nth}×{ncs} (periódica)"
        if surf is None:
            return None
        a = np.abs(rr)
        e95 = float(np.percentile(a, 95))
        labels[f] = len(surfs); surfs.append(surf); errs.append(e95)
        pst.append({"e95": e95, "rms": float(np.sqrt((a ** 2).mean())), "max": float(a.max()),
                    "sigma": float(np.std(rr)), "grid": grid, "param": m["kind"] == "band"})
        vdev[m["vidx"][:no]] = rr
    ok_ = np.isfinite(vdev)
    stats = {"e95": errs, "patches": pst, "layout": "armónico", "vdev": vdev,
             "sigma": float(np.std(vdev[ok_])), "dev_max": float(np.abs(vdev[ok_]).max()),
             "dev_p95": float(np.percentile(np.abs(vdev[ok_]), 95))}
    if Cp.shape[0]:
        mis = np.abs(Cp @ z - cp)
        stats["couple_mismatch"] = (float(np.median(mis)), float(mis.max()))
    if verbose:
        print(f"  [armónico] 3 caras ajustadas A LA VEZ (L {L:.1f} mm, {ntot} incógnitas, "
              f"{Cp.shape[0]} puntos de acople) en {time.time() - t0:.1f}s; desviación "
              f"sigma {stats['sigma']:.3f}, p95 {stats['dev_p95']:.3f}, máx {stats['dev_max']:.3f} mm")
    return labels, surfs, stats
