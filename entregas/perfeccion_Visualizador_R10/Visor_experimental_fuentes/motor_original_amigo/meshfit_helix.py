import numpy as np

from OCP.gp import gp_Pnt
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
from OCP.Approx import Approx_IsoParametric
from OCP.GeomAbs import GeomAbs_C2

from meshfit_nurbs import (_cyl_frame, _ang_span, _inside_polygon,
                           _boundary_segments_3d, tessellate, surf_h_range, TWO_PI)


def _phase_scatter(z, th, rho, P, sign, nbins=24):

    k = P / TWO_PI
    w = np.mod(z - sign * k * th, P)
    ib = np.clip((w / P * nbins).astype(int), 0, nbins - 1)
    cnt = np.bincount(ib, minlength=nbins)
    s1 = np.bincount(ib, weights=rho, minlength=nbins)
    s2 = np.bincount(ib, weights=rho ** 2, minlength=nbins)
    ok = cnt >= 3
    if ok.sum() < nbins // 2:
        return np.inf
    var = s2[ok] / cnt[ok] - (s1[ok] / cnt[ok]) ** 2
    return float(np.sqrt(np.maximum(var, 0.0)).mean())


def _estimate_pitch(z, th, rho):

    zr = float(z.max() - z.min())
    if zr <= 0:
        raise ValueError("el parche no tiene extensión axial (no parece una rosca)")
    pmin = max(zr / 200.0, 0.05)
    pmax = zr / 1.5
    if pmax <= pmin:
        raise ValueError("el parche cubre menos de un paso y medio de rosca")
    best = None
    cands = np.geomspace(pmin, pmax, 120)
    for _ in range(3):
        for P in cands:
            for s in (1.0, -1.0):
                sc = _phase_scatter(z, th, rho, float(P), s)
                if best is None or sc < best[0]:
                    best = (sc, float(P), s)
        span = cands[1] / cands[0] if len(cands) > 1 else 1.05
        P0 = best[1]
        cands = np.linspace(P0 / span, P0 * span, 40)
    return best[1], best[2], best[0]


def _fit_profile_lin(z, th, rho, P, sign, nbins=64):

    k = P / TWO_PI
    w = np.mod(z - sign * k * th, P)
    ib = np.clip((w / P * nbins).astype(int), 0, nbins - 1)
    prof = np.full(nbins, np.nan)
    for b in range(nbins):
        sel = rho[ib == b]
        if len(sel) >= 2:
            prof[b] = np.median(sel)
    filled = ~np.isnan(prof)
    if filled.sum() < nbins // 2:
        raise ValueError("parche demasiado disperso para reconstruir el perfil de rosca")
    if not filled.all():
        idx = np.nonzero(filled)[0]
        prof = np.interp(np.arange(nbins), idx, prof[idx], period=nbins)
    prof = (np.roll(prof, 1) + prof + np.roll(prof, -1)) / 3.0
    wc = (np.arange(nbins) + 0.5) / nbins * P
    wx = np.r_[wc - P, wc, wc + P]
    fy = np.r_[prof, prof, prof]

    def g(ww, _P=P, _wx=wx, _fy=fy):
        return np.interp(np.mod(np.asarray(ww, float), _P), _wx, _fy)
    return g, wc, prof


def _fit_profile(z, th, rho, P, sign, nbins=32):

    from scipy.interpolate import CubicSpline
    k = P / TWO_PI
    w = np.mod(z - sign * k * th, P)
    ib = np.clip((w / P * nbins).astype(int), 0, nbins - 1)
    prof = np.empty(nbins)
    filled = np.zeros(nbins, dtype=bool)
    for b in range(nbins):
        sel = rho[ib == b]
        if len(sel) >= 2:
            prof[b] = np.median(sel)
            filled[b] = True
    if filled.sum() < nbins // 2:
        raise ValueError("parche demasiado disperso para reconstruir el perfil de rosca")
    if not filled.all():
        idx = np.nonzero(filled)[0]
        allb = np.arange(nbins)
        prof = np.interp(allb, idx, prof[idx], period=nbins)
    wc = (np.arange(nbins) + 0.5) / nbins * P

    wx = np.append(wc, wc[0] + P)
    fy = np.append(prof, prof[0])
    g = CubicSpline(wx, fy, bc_type="periodic")
    return (lambda ww, _g=g, _P=P, _w0=wc[0]: _g(_w0 + np.mod(ww - _w0, _P))), wc, prof


def _frame_from(d, p0):
    from meshfit_detect import _perp_basis
    d = np.asarray(d, float) / np.linalg.norm(d)
    e1, e2 = _perp_basis(d)
    return d, np.asarray(p0, float), e1, e2


def _cyl_coords(pts, d, p0, e1, e2):
    dd = pts - p0
    z = dd @ d
    r = dd - np.outer(z, d)
    return z, np.linalg.norm(r, axis=1), np.arctan2(r @ e2, r @ e1)


def _thread_frame(pts, fn, fa):

    from scipy.optimize import least_squares, minimize
    a, q, e1, e2, z, rho, th = _cyl_frame(pts, fn, fa)
    best = (a, q, e1, e2, z, rho, th)
    try:
        def rc(x):
            d = np.array([np.sin(x[0]) * np.cos(x[1]), np.sin(x[0]) * np.sin(x[1]), np.cos(x[0])])
            dd = pts - (q + x[2] * e1 + x[3] * e2)
            return np.linalg.norm(dd - np.outer(dd @ d, d), axis=1) - x[4]
        x = least_squares(rc, [np.arccos(np.clip(a[2], -1, 1)), np.arctan2(a[1], a[0]), 0.0, 0.0,
                               float(rho.mean())], loss="soft_l1", f_scale=0.5).x
        d0 = np.array([np.sin(x[0]) * np.cos(x[1]), np.sin(x[0]) * np.sin(x[1]), np.cos(x[0])])
        if d0 @ a < 0:
            d0 = -d0
        d0, p0, f1, f2 = _frame_from(d0, q + x[2] * e1 + x[3] * e2)
        zz, rr, tt = _cyl_coords(pts, d0, p0, f1, f2)
        P, sign, _ = _estimate_pitch(zz, tt, rr)

        def cost(y):
            D, Q, E1, E2 = _frame_from(d0 + y[0] * f1 + y[1] * f2, p0 + y[2] * f1 + y[3] * f2)
            z_, r_, t_ = _cyl_coords(pts, D, Q, E1, E2)
            try:
                g, _, _ = _fit_profile_lin(z_, t_, r_, P, sign)
            except ValueError:
                return 1e3
            res = r_ - g(np.mod(z_ - sign * P / TWO_PI * t_, P))
            return float(np.sqrt(np.mean(res ** 2)))

        def cost_frame(fr):
            z_, r_, t_ = _cyl_coords(pts, *fr)
            try:
                P_, s_, _ = _estimate_pitch(z_, t_, r_)
                g, _, _ = _fit_profile_lin(z_, t_, r_, P_, s_)
            except ValueError:
                return 1e3
            res = r_ - g(np.mod(z_ - s_ * P_ / TWO_PI * t_, P_))
            return float(np.sqrt(np.mean(res ** 2)))
        sol = minimize(cost, [0, 0, 0, 0], method="Nelder-Mead",
                       options={"xatol": 1e-6, "fatol": 1e-7, "maxiter": 500, "initial_simplex":
                                np.array([[0, 0, 0, 0], [0.01, 0, 0, 0], [0, 0.01, 0, 0],
                                          [0, 0, 0.1, 0], [0, 0, 0, 0.1]], float)})
        y = sol.x
        D, Q, E1, E2 = _frame_from(d0 + y[0] * f1 + y[1] * f2, p0 + y[2] * f1 + y[3] * f2)
        if cost_frame((D, Q, E1, E2)) < cost_frame((a, q, e1, e2)):
            best = (D, Q, E1, E2) + tuple(_cyl_coords(pts, D, Q, E1, E2))
    except Exception:
        pass
    return best

_PITCH_MM = [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7, 0.75, 0.8, 1.0, 1.25, 1.5,
             1.75, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
_TPI = [4, 4.5, 5, 6, 7, 8, 9, 10, 11, 11.5, 12, 13, 14, 16, 18, 19, 20, 24, 27, 28, 32,
        36, 40, 44, 48, 56, 64, 72, 80]


def standard_pitch(P, rel=0.004):

    cands = [(p, f"paso métrico {p:g} mm") for p in _PITCH_MM] + \
            [(25.4 / n, f"{n:g} hilos por pulgada") for n in _TPI]
    p, txt = min(cands, key=lambda c: abs(c[0] - P))
    return (p, txt) if abs(p - P) / P < rel else None

_FIT_CACHE = {}


def fit_helix(mesh, faces, snap_pitch=False):

    import hashlib
    faces = np.asarray(faces, int)
    key = (len(mesh.faces), hashlib.md5(np.ascontiguousarray(np.asarray(mesh.vertices)[:200]).tobytes()).hexdigest(),
           hashlib.md5(np.sort(faces).tobytes()).hexdigest(), bool(snap_pitch))
    if key in _FIT_CACHE:
        return _FIT_CACHE[key]
    out = _fit_helix(mesh, faces, snap_pitch)
    while len(_FIT_CACHE) >= 8:
        _FIT_CACHE.pop(next(iter(_FIT_CACHE)))
    _FIT_CACHE[key] = out
    return out


def _fit_helix(mesh, faces, snap_pitch=False):
    vidx = np.unique(mesh.faces[faces].ravel())
    if len(vidx) < 60:
        raise ValueError(f"parche demasiado pequeño para una rosca ({len(vidx)} vértices)")
    fn = mesh.face_normals[faces]
    fa = mesh.area_faces[faces]

    T = np.asarray(mesh.vertices, float)[np.asarray(mesh.faces)[faces]]
    n_s = int(np.clip(2 * len(faces), 6000, 20000))
    rng = np.random.default_rng(0)
    fi = rng.choice(len(faces), n_s, p=fa / fa.sum())
    r1 = np.sqrt(rng.random(n_s)); r2 = rng.random(n_s)
    pts = ((1 - r1)[:, None] * T[fi, 0] + (r1 * (1 - r2))[:, None] * T[fi, 1]
           + (r1 * r2)[:, None] * T[fi, 2])
    pts = np.vstack([pts, np.asarray(mesh.vertices, float)[vidx]])

    a, q, e1, e2, z, rho, th = _thread_frame(pts, fn, fa)
    P, sign, scatter = _estimate_pitch(z, th, rho)
    P_meas, std_txt = P, None
    if snap_pitch:
        st = standard_pitch(P)
        if st is not None:
            P, std_txt = st
    g, wc, prof = _fit_profile_lin(z, th, rho, P, sign)

    k = P / TWO_PI
    rho_model = g(np.mod(z - sign * k * th, P))
    res = rho - rho_model
    rms = float(np.sqrt((res ** 2).mean()))

    u0, u1, full = _ang_span(th)
    info = {
        "frame": ("cyl", q, e1, e2, a),
        "mode": "cyl", "full": full,
        "u0": float(u0), "u1": float(u1),
        "v0": float(z.min()), "v1": float(z.max()),
        "pitch": float(P), "sign": float(sign),
        "r_crest": float(prof.max()), "r_root": float(prof.min()),
        "r_mean": float(prof.mean()),
        "axis": a.tolist(), "point": q.tolist(),
        "rms_radial": rms, "max_radial": float(np.abs(res).max()), "pts": pts, "g": g,
        "pitch_measured": float(P_meas), "pitch_std": std_txt,
        "diag": float(np.linalg.norm(pts.max(0) - pts.min(0))) or 1.0,
    }

    def model(theta, zz):
        return g(np.mod(zz - sign * k * theta, P))

    return info, model


def _helix_periodic(info, model, per_turn=24, per_pitch=24):

    import scipy.sparse as sps
    from scipy.sparse.linalg import spsolve
    from OCP.Geom import Geom_BSplineSurface
    from OCP.TColgp import TColgp_Array2OfPnt
    from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
    from meshfit_organic import periodic_design
    _, q, e1, e2, a = info["frame"]
    u0, v0, v1, P = info["u0"], info["v0"], info["v1"], info["pitch"]
    nth = int(per_turn)
    nseg = max(4, int(np.ceil((v1 - v0) / P * per_pitch)))
    tv = np.r_[[v0] * 4, np.linspace(v0, v1, nseg + 1)[1:-1], [v1] * 4]
    ncs = len(tv) - 4
    ts = np.linspace(0.0, TWO_PI, 4 * nth, endpoint=False)
    zs = np.linspace(v0, v1, 4 * nseg + 1)
    TT, ZZ = np.meshgrid(ts, zs, indexing="ij")
    TT = TT.ravel(); ZZ = ZZ.ravel()
    th = u0 + TT
    rr = model(th, ZZ)
    X = q + rr[:, None] * (np.cos(th)[:, None] * e1 + np.sin(th)[:, None] * e2) + ZZ[:, None] * a
    B = periodic_design(TT, ZZ, nth, tv, v0, v1)
    K = (B.T @ B + 1e-10 * sps.identity(B.shape[1])).tocsc()
    C = np.column_stack([spsolve(K, B.T @ X[:, c]) for c in range(3)])
    poles = TColgp_Array2OfPnt(1, nth, 1, ncs)
    for i in range(nth):
        for j in range(ncs):
            poles.SetValue(i + 1, j + 1, gp_Pnt(*map(float, C[i * ncs + j])))
    uk = TColStd_Array1OfReal(1, nth + 1); um = TColStd_Array1OfInteger(1, nth + 1)
    for i in range(nth + 1):
        uk.SetValue(i + 1, float(u0 + i * TWO_PI / nth)); um.SetValue(i + 1, 1)
    dist = np.r_[tv[0], tv[4:-4], tv[-1]]
    vk = TColStd_Array1OfReal(1, len(dist)); vm = TColStd_Array1OfInteger(1, len(dist))
    for i, val in enumerate(dist):
        vk.SetValue(i + 1, float(val)); vm.SetValue(i + 1, 4 if i in (0, len(dist) - 1) else 1)
    surf = Geom_BSplineSurface(poles, uk, vk, um, vm, 3, 3, True, False)

    chk = np.random.default_rng(0).integers(0, len(X), 2000)
    err = max(surf.Value(float(th[k]), float(ZZ[k])).Distance(gp_Pnt(*map(float, X[k]))) for k in chk)
    info["surf_err"] = float(err)
    return surf


def helix_surface(info, model):

    if info.get("full"):
        try:
            surf = _helix_periodic(info, model)
            r_span = info["r_crest"] - info["r_root"]
            if info["surf_err"] <= max(0.01, 0.05 * r_span):
                return surf
        except Exception:
            pass
    _, q, e1, e2, a = info["frame"]
    u0, u1 = info["u0"], info["u1"]
    v0, v1 = info["v0"], info["v1"]
    P = info["pitch"]
    nu = int(np.clip(round((u1 - u0) / TWO_PI * 16), 8, 32))

    nv = int(np.clip(round((v1 - v0) / P * 14), 16, 220))
    gu = np.linspace(u0, u1, nu)
    gv = np.linspace(v0, v1, nv)
    arr = TColgp_Array2OfPnt(1, nu, 1, nv)
    for i, uu in enumerate(gu):
        rr = model(uu, gv)
        dirv = np.cos(uu) * e1 + np.sin(uu) * e2
        for j in range(nv):
            Pt = q + float(rr[j]) * dirv + gv[j] * a
            arr.SetValue(i + 1, j + 1, gp_Pnt(float(Pt[0]), float(Pt[1]), float(Pt[2])))

    def hfun(Pnt3):
        dd = np.asarray(Pnt3, float) - q
        return float(np.linalg.norm(dd - float(dd @ a) * a))

    r_span = info["r_crest"] - info["r_root"] + 1e-6
    ns = int(min(96, max(32, round(1.2 * max(nu, nv)))))
    tol = max(1e-3, 1e-3 * info["diag"])
    surf = None
    err = None
    for _ in range(4):
        try:
            surf = GeomAPI_PointsToBSplineSurface(
                arr, Approx_IsoParametric, 3, 3, GeomAbs_C2, tol).Surface()
        except Exception as e:
            err = e
            break
        if surf_h_range(surf, hfun, ns=ns) <= 1.5 * r_span + 0.1:
            break
        tol *= 4.0
    if surf is None:
        raise RuntimeError(f"la superficie helicoidal falló: {err}")
    return surf


def _map_uv(info, Pnt3):

    _, q, e1, e2, a = info["frame"]
    d = np.asarray(Pnt3, float) - q
    zz = float(d @ a)
    r = d - zz * a
    t = float(np.arctan2(r @ e2, r @ e1))
    u = info["u0"] + (t - info["u0"]) % TWO_PI
    if u > info["u1"]:
        u = info["u1"] if (u - info["u1"]) < (info["u0"] + TWO_PI - u) else info["u0"]
    return u, zz


def fit_region_helix(mesh, faces, snap_pitch=False):

    faces = np.asarray(faces, int)
    info, model = fit_helix(mesh, faces, snap_pitch=snap_pitch)
    surf = helix_surface(info, model)

    nu_t = int(np.clip(round((info["u1"] - info["u0"]) / TWO_PI * 48), 32, 96))
    nv_t = int(np.clip(round((info["v1"] - info["v0"]) / info["pitch"] * 16), 32, 400))
    verts, tris = tessellate(surf, nu_t, nv_t)

    rms, mx = info["rms_radial"], info["max_radial"]

    A3, B3 = (None, None) if info["full"] else _boundary_segments_3d(mesh, faces)
    if info["full"]:

        _, q, e1, e2, a = info["frame"]
        zp, _, tp = _cyl_coords(info["pts"], a, q, e1, e2)
        nb = 180
        bp = (np.mod(tp - info["u0"], TWO_PI) / TWO_PI * nb).astype(int) % nb
        zlo = np.full(nb, np.inf); zhi = np.full(nb, -np.inf)
        np.minimum.at(zlo, bp, zp); np.maximum.at(zhi, bp, zp)
        okb = np.isfinite(zlo)
        if okb.sum() >= nb // 2:
            idx = np.nonzero(okb)[0]
            zlo = np.interp(np.arange(nb), idx, zlo[idx], period=nb)
            zhi = np.interp(np.arange(nb), idx, zhi[idx], period=nb)
            zc, _, tc = _cyl_coords(verts[tris].mean(axis=1), a, q, e1, e2)
            bc = (np.mod(tc - info["u0"], TWO_PI) / TWO_PI * nb).astype(int) % nb
            mz = 0.5 * (info["v1"] - info["v0"]) / max(nv_t, 1)
            keep = (zc >= zlo[bc] - mz) & (zc <= zhi[bc] + mz)
            if keep.sum() >= 4:
                tris = tris[keep]
    if A3 is not None:
        A = np.array([_map_uv(info, p) for p in A3])
        B = np.array([_map_uv(info, p) for p in B3])
        dB = np.mod(B[:, 0] - A[:, 0] + np.pi, TWO_PI) - np.pi
        B[:, 0] = A[:, 0] + dB
        if info["full"]:
            sh = np.array([TWO_PI, 0.0])
            A = np.vstack([A, A + sh, A - sh])
            B = np.vstack([B, B + sh, B - sh])
        cen3 = verts[tris].mean(axis=1)
        cen_uv = np.array([_map_uv(info, p) for p in cen3])
        keep = _inside_polygon(cen_uv[:, ::-1], A[:, ::-1], B[:, ::-1])
        if keep.sum() >= 4:
            tris = tris[keep]

    hand = "derechas" if info["sign"] > 0 else "izquierdas"
    data = {
        "vertices": verts.tolist(),
        "triangles": tris.tolist(),
        "rms": rms, "max": mx,
        "n_pts": int(len(info["pts"])), "n_faces": int(len(faces)),
        "pitch": info["pitch"], "hand": hand,
        "r_crest": info["r_crest"], "r_root": info["r_root"],
        "d_crest": 2 * info["r_crest"], "d_root": 2 * info["r_root"],
        "axis": info["axis"], "point": info["point"],
        "turns": (info["v1"] - info["v0"]) / info["pitch"],
        "pitch_measured": info["pitch_measured"], "pitch_std": info["pitch_std"],
    }
    return data, surf

if __name__ == "__main__":
    import sys
    import trimesh

    path = sys.argv[1] if len(sys.argv) > 1 else r"pieza.stl"
    mesh = trimesh.load(path, force="mesh")
    mesh.merge_vertices()

    cents = mesh.vertices[mesh.faces].mean(axis=1)
    c0 = mesh.bounds.mean(axis=0)
    d = cents - c0
    rho = np.linalg.norm(d[:, :2], axis=1)
    sel = np.nonzero((d[:, 2] > 0) & (rho > 2.0))[0]
    data, surf = fit_region_helix(mesh, sel.tolist())
    print(f"rosca: paso={data['pitch']:.4f} mm  sentido={data['hand']}  vueltas={data['turns']:.1f}")
    print(f"  Ø cresta={data['d_crest']:.3f}  Ø fondo={data['d_root']:.3f}")
    print(f"  RMS={data['rms']:.4f} mm  máx={data['max']:.4f} mm  ({data['n_faces']} caras)")
    v = np.array(data["vertices"])
    print(f"  teselado bbox={np.round(v.max(0)-v.min(0), 1)}")


def _lsq_axis(pts, fn, fa):

    from scipy.optimize import least_squares
    try:
        a, q, e1, e2, z, rho, th = _cyl_frame(pts, fn, fa)

        def rc(x):
            d = np.array([np.sin(x[0]) * np.cos(x[1]), np.sin(x[0]) * np.sin(x[1]), np.cos(x[0])])
            dd = pts - (q + x[2] * e1 + x[3] * e2)
            return np.linalg.norm(dd - np.outer(dd @ d, d), axis=1) - x[4]
        x = least_squares(rc, [np.arccos(np.clip(a[2], -1, 1)), np.arctan2(a[1], a[0]), 0.0, 0.0,
                               float(rho.mean())], loss="soft_l1", f_scale=0.5).x
        d = np.array([np.sin(x[0]) * np.cos(x[1]), np.sin(x[0]) * np.sin(x[1]), np.cos(x[0])])
        return d, q + x[2] * e1 + x[3] * e2, abs(float(x[4]))
    except Exception:
        return None


def _coaxial(a1, p1, a2, p2, R):
    if abs(float(np.dot(a1, a2))) < np.cos(np.radians(3.0)):
        return False
    dp = np.asarray(p2, float) - np.asarray(p1, float)
    off = np.linalg.norm(dp - (dp @ a1) * a1)
    return off < 0.15 * R + 0.3


def _same_height(items, cand, i, C):

    a, p = items[i]["a"], items[i]["p"]
    rng = {}
    for j in cand:
        z = (C[items[j]["faces"]] - p) @ a
        rng[j] = (float(z.min()), float(z.max()))
    gap = 0.05 * items[i]["R"] + 0.5
    lo, hi = rng[i]
    free = {i}
    grew = True
    while grew:
        grew = False
        for j in cand:
            if items[j]["kind"] == "free" and j not in free:
                z0, z1 = rng[j]
                if z0 <= hi + gap and z1 >= lo - gap:
                    free.add(j)
                    lo, hi = min(lo, z0), max(hi, z1)
                    grew = True
    grp = sorted(free)
    for j in cand:
        if items[j]["kind"] == "cyl":
            z0, z1 = rng[j]
            if min(z1, hi) - max(z0, lo) >= 0.5 * (z1 - z0):
                grp.append(j)
    return grp


def find_threads(res, mesh, verbose=True, min_faces=300, snap_pitch=False):

    F = np.asarray(mesh.faces); V = np.asarray(mesh.vertices, float)
    fn = np.asarray(mesh.face_normals); fa = np.asarray(mesh.area_faces)
    C = V[F].mean(axis=1)
    items = []
    for r in res.get("freeform_regions", []):
        r = np.asarray(r, int)
        if len(r) < 60:
            continue
        ax = _lsq_axis(V[np.unique(F[r].ravel())], fn[r], fa[r])
        if ax is not None:
            items.append({"kind": "free", "faces": r, "a": ax[0], "p": ax[1], "R": ax[2]})
    for p in res.get("primitives", []):
        if p.get("type") == "cylinder":
            a = np.asarray(p["axis"], float); a /= np.linalg.norm(a)
            items.append({"kind": "cyl", "faces": np.asarray(p["faces"], int), "a": a,
                          "p": np.asarray(p["point"], float), "R": float(p["radius"])})
    used = np.zeros(len(items), bool)
    out = []
    taken = np.zeros(len(F), bool)
    for i, it in enumerate(items):
        if used[i] or it["kind"] != "free":
            continue
        cand = [j for j, jt in enumerate(items) if not used[j] and
                _coaxial(it["a"], it["p"], jt["a"], jt["p"], max(it["R"], jt["R"])) and
                abs(jt["R"] - it["R"]) < 0.5 * it["R"] + 0.5]
        grp = _same_height(items, cand, i, C)
        faces = np.unique(np.concatenate([items[j]["faces"] for j in grp]))
        faces = faces[~taken[faces]]
        for j in grp:
            used[j] = True
        if len(faces) < min_faces:
            continue

        cur, ok, info = faces, False, None
        for _ in range(3):
            try:
                info, model = fit_helix(mesh, cur)
            except Exception:
                break
            depth = info["r_crest"] - info["r_root"]
            turns = (info["v1"] - info["v0"]) / info["pitch"]
            if not (depth >= max(0.1, 0.02 * info["r_mean"]) and turns >= 1.5
                    and info["pitch"] <= 1.5 * info["r_mean"]):
                break
            _, q, e1, e2, a = info["frame"]
            vid = np.unique(F[cur].ravel())
            z, rho, th = _cyl_coords(V[vid], a, q, e1, e2)
            rv = np.zeros(len(V)); rv[vid] = np.abs(rho - model(th, z))
            r_all = rv[vid]
            lim = max(3 * 1.4826 * float(np.median(r_all)), 0.03, 0.05 * depth)
            nxt = cur[rv[F[cur]].max(1) <= lim]
            if len(nxt) < min_faces:
                break
            if info["rms_radial"] <= max(0.03, 0.1 * depth) and len(nxt) >= 0.97 * len(cur):
                ok = True
                break
            cur = nxt
        if not ok:
            if verbose and info is not None:
                print(f"  [rosca] candidato descartado: paso {info['pitch']:.3f}, rms {info['rms_radial']:.3f}")
            continue
        keep = cur
        info2, _m2 = fit_helix(mesh, keep, snap_pitch=snap_pitch)
        turns = (info2["v1"] - info2["v0"]) / info2["pitch"]
        taken[keep] = True
        out.append({"faces": keep, "info": info2})
        if verbose:
            print(f"  [rosca] ROSCA: paso {info2['pitch']:.4f} mm, "
                  f"{'derechas' if info2['sign'] > 0 else 'izquierdas'}, Ø {2 * info2['r_crest']:.3f}/"
                  f"{2 * info2['r_root']:.3f}, {turns:.1f} vueltas, rms {info2['rms_radial']:.4f} "
                  f"({len(keep)} caras)")
    return out
