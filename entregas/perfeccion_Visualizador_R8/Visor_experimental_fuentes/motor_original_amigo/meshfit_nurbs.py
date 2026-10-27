import numpy as np
from scipy.interpolate import griddata
from scipy.spatial import cKDTree

from OCP.gp import gp_Pnt
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
from OCP.Approx import Approx_IsoParametric
from OCP.GeomAbs import GeomAbs_C2

TWO_PI = 2.0 * np.pi


def _pca_frame(pts):

    c = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    U, V, N = vt[0], vt[1], vt[2]
    return c, U / np.linalg.norm(U), V / np.linalg.norm(V), N / np.linalg.norm(N)


def grid_from_smooth(n, smooth=0.0):

    gmax = int(np.clip(round(np.sqrt(max(n, 1))), 6, 40))
    smooth = float(np.clip(smooth, 0.0, 1.0))
    return int(max(5, round(gmax - smooth * (gmax - 5))))


def grid_aniso(n, du, dv, smooth=0.0, gmin=4, gmax=80):

    g = grid_from_smooth(n, smooth)
    r = np.sqrt(max(du, 1e-9) / max(dv, 1e-9))
    nu = int(np.clip(round(g * r), gmin, gmax))
    nv = int(np.clip(round(g * g / max(nu, 1)), gmin, gmax))
    return nu, nv


def resample_tol(gu, gv, H, uu, vv, hh, diag):

    from scipy.interpolate import RegularGridInterpolator
    try:
        est = RegularGridInterpolator((gu, gv), H, method="linear",
                                      bounds_error=False, fill_value=None)(
            np.column_stack([uu, vv]))
        res = hh - est
        res_rms = float(np.sqrt(np.nanmean(res ** 2)))
    except Exception:
        res_rms = 0.0
    return max(1e-4, 1e-3 * diag, 1.2 * res_rms)


def surf_h_range(surf, hfun, ns=20):

    u0, u1, v0, v1 = surf.Bounds()
    hmin, hmax = np.inf, -np.inf
    for uu in np.linspace(u0, u1, ns):
        for vv in np.linspace(v0, v1, ns):
            p = surf.Value(float(uu), float(vv))
            h = hfun(np.array([p.X(), p.Y(), p.Z()]))
            hmin, hmax = min(hmin, h), max(hmax, h)
    return hmax - hmin


def _radial_scatter(th, z, rho, nb_u=24, nb_v=8):

    iu = np.clip(((th + np.pi) / TWO_PI * nb_u).astype(int), 0, nb_u - 1)
    zr = float(z.max() - z.min()) or 1.0
    iv = np.clip(((z - z.min()) / zr * nb_v).astype(int), 0, nb_v - 1)
    idx = iu * nb_v + iv
    nbin = nb_u * nb_v
    cnt = np.bincount(idx, minlength=nbin)
    s1 = np.bincount(idx, weights=rho, minlength=nbin)
    s2 = np.bincount(idx, weights=rho ** 2, minlength=nbin)
    ok = cnt >= 3
    if not ok.any():
        return np.inf
    var = s2[ok] / cnt[ok] - (s1[ok] / cnt[ok]) ** 2
    return float(np.sqrt(np.maximum(var, 0.0)).mean())


def _cyl_frame(pts, fn, fa):

    from meshfit_detect import fit_cylinder, _perp_basis, _fit_circle_2d
    cands = []
    try:
        prim = fit_cylinder(pts, fn, fa)
        cands.append(np.asarray(prim["axis"], float))
    except Exception:
        pass
    cpts = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - cpts, full_matrices=False)
    for k in range(3):
        cands.append(vt[k] / np.linalg.norm(vt[k]))
    best = None
    for a in cands:
        e1, e2 = _perp_basis(a)
        uv2 = np.column_stack([pts @ e1, pts @ e2])
        try:
            c2, _R2 = _fit_circle_2d(uv2)
        except Exception:
            continue
        q = float(c2[0]) * e1 + float(c2[1]) * e2
        d = pts - q
        z = d @ a
        r = d - np.outer(z, a)
        rho = np.linalg.norm(r, axis=1)
        th = np.arctan2(r @ e2, r @ e1)
        sc = _radial_scatter(th, z, rho)
        if best is None or sc < best[0]:
            best = (sc, a, q, e1, e2, z, rho, th)
    if best is None:
        raise RuntimeError("no se pudo estimar el eje del parche cilíndrico")
    return best[1:]


def _ang_span(ang, full_tol_deg=15.0, margin_deg=1.0):

    a = np.sort(np.mod(ang, TWO_PI))
    n = len(a)
    ext = np.append(a, a[0] + TWO_PI)
    gaps = np.diff(ext)
    k = int(np.argmax(gaps))
    if gaps[k] < np.radians(full_tol_deg):
        u0 = float(a[0])
        return u0, u0 + TWO_PI, True
    m = np.radians(margin_deg)
    if k == n - 1:
        return float(a[0] - m), float(a[n - 1] + m), False
    return float(a[k + 1] - m), float(a[k] + TWO_PI + m), False


def fit_mesh_region(mesh, faces, grid=None, smooth=0.0, grow=0.0):

    faces = np.asarray(faces, int)
    vidx = np.unique(mesh.faces[faces].ravel())
    pts = mesh.vertices[vidx].astype(float)
    n = len(pts)
    if n < 9:
        raise ValueError(f"región demasiado pequeña para NURBS ({n} vértices, mín. 9)")
    fn = mesh.face_normals[faces]
    fa = mesh.area_faces[faces]
    w = fa / (fa.sum() + 1e-30)
    nbar = (fn * w[:, None]).sum(axis=0)
    diag = float(np.linalg.norm(pts.max(0) - pts.min(0))) or 1.0
    mode = "plane" if np.linalg.norm(nbar) >= 0.5 else "cyl"
    grow = max(0.0, float(grow))
    rho_mean = 1.0

    if mode == "cyl":
        a, q, e1, e2, vv, hh, th = _cyl_frame(pts, fn, fa)
        u0, u1, full = _ang_span(th)
        rho_mean = float(hh.mean()) or 1.0
        v0, v1 = float(vv.min()), float(vv.max())
        if grow > 1e-9:
            v0 -= grow; v1 += grow
            if not full:
                dth = grow / max(rho_mean, 1e-6)
                u0 -= dth; u1 += dth
                over = (u1 - u0) - TWO_PI
                if over > 0:
                    u0 += over / 2; u1 -= over / 2
        uu = u0 + np.mod(th - u0, TWO_PI)
        uu = np.clip(uu, u0, u1)
        du = (u1 - u0) * rho_mean
        dv = v1 - v0
        frame = ("cyl", q, e1, e2, a)

        def to_xyz(u, v, h):
            return q + h * (np.cos(u) * e1 + np.sin(u) * e2) + v * a

        def hfun(P):
            dd = P - q
            return float(np.linalg.norm(dd - float(dd @ a) * a))
    else:
        c, U, V, N = _pca_frame(pts)
        d = pts - c
        uu, vv, hh = d @ U, d @ V, d @ N
        u0, u1 = float(uu.min()), float(uu.max())
        v0, v1 = float(vv.min()), float(vv.max())
        if grow > 1e-9:
            u0 -= grow; u1 += grow; v0 -= grow; v1 += grow
        du, dv = u1 - u0, v1 - v0
        full = False
        frame = ("plane", c, U, V, N)

        def to_xyz(u, v, h):
            return c + u * U + v * V + h * N

        def hfun(P):
            return float((P - c) @ N)

    if grid is None:
        nu, nv = grid_aniso(n, du, dv, smooth)
    else:
        nu = nv = int(grid)
    gu = np.linspace(u0, u1, nu)
    gv = np.linspace(v0, v1, nv)
    GU, GV = np.meshgrid(gu, gv, indexing="ij")

    su, sv, sh = uu, vv, hh
    if mode == "cyl" and full:

        mgn = 0.15 * TWO_PI
        left = uu <= u0 + mgn
        right = uu >= u1 - mgn
        su = np.concatenate([uu, uu[left] + TWO_PI, uu[right] - TWO_PI])
        sv = np.concatenate([vv, vv[left], vv[right]])
        sh = np.concatenate([hh, hh[left], hh[right]])

    H = griddata((su, sv), sh, (GU, GV), method="linear")
    nan = np.isnan(H)
    if nan.any():

        from scipy.ndimage import uniform_filter
        H[nan] = griddata((su, sv), sh, (GU, GV), method="nearest")[nan]
        for _ in range(60):
            Hs = uniform_filter(H, size=3, mode="nearest")
            H[nan] = Hs[nan]

    tol3d = resample_tol(gu, gv, H, uu, vv, hh, diag)

    arr = TColgp_Array2OfPnt(1, nu, 1, nv)
    for i in range(nu):
        for j in range(nv):
            P = to_xyz(GU[i, j], GV[i, j], H[i, j])
            arr.SetValue(i + 1, j + 1, gp_Pnt(float(P[0]), float(P[1]), float(P[2])))

    h_data = float(hh.max() - hh.min())
    surf = None
    err = None

    ns = int(min(96, max(24, round(1.5 * max(nu, nv)))))
    for _ in range(4):
        try:
            surf = GeomAPI_PointsToBSplineSurface(
                arr, Approx_IsoParametric, 3, 3, GeomAbs_C2, tol3d).Surface()
        except Exception as e:
            err = e
            break
        if surf_h_range(surf, hfun, ns=ns) <= 3.0 * h_data + 0.1 * diag:
            break
        tol3d *= 4.0
    if surf is None:
        raise RuntimeError(f"el ajuste B-spline falló: {err}")

    return {"surf": surf, "mode": mode, "frame": frame, "full": full,
            "u0": u0, "u1": u1, "v0": v0, "v1": v1, "grow": grow,
            "nu": nu, "nv": nv, "grid": f"{nu}×{nv}", "rho_mean": rho_mean,
            "tol3d": tol3d, "diag": diag, "pts": pts, "hfun": hfun}


def map_uv(info, P):

    if info["mode"] == "cyl":
        _, q, e1, e2, a = info["frame"]
        d = np.asarray(P, float) - q
        z = float(d @ a)
        r = d - z * a
        th = float(np.arctan2(r @ e2, r @ e1))
        u = info["u0"] + (th - info["u0"]) % TWO_PI
        if u > info["u1"]:
            u = info["u1"] if (u - info["u1"]) < (info["u0"] + TWO_PI - u) else info["u0"]
        return u, z
    _, c, U, V, _N = info["frame"]
    d = np.asarray(P, float) - c
    return float(d @ U), float(d @ V)


def fit_bspline(pts, grid=None, tol3d=None, smooth=0.0):

    pts = np.asarray(pts, float)
    n = len(pts)
    if n < 9:
        raise ValueError(f"región demasiado pequeña para NURBS ({n} vértices, mín. 9)")
    c, U, V, N = _pca_frame(pts)
    d = pts - c
    uu, vv, hh = d @ U, d @ V, d @ N
    if grid is None:
        nu, nv = grid_aniso(n, float(uu.max() - uu.min()), float(vv.max() - vv.min()), smooth)
    else:
        nu = nv = int(grid)
    gu = np.linspace(uu.min(), uu.max(), nu)
    gv = np.linspace(vv.min(), vv.max(), nv)
    GU, GV = np.meshgrid(gu, gv, indexing="ij")
    H = griddata((uu, vv), hh, (GU, GV), method="linear")
    nan = np.isnan(H)
    if nan.any():
        H[nan] = griddata((uu, vv), hh, (GU, GV), method="nearest")[nan]
    diag = float(np.linalg.norm(pts.max(0) - pts.min(0))) or 1.0
    if tol3d is None:
        tol3d = resample_tol(gu, gv, H, uu, vv, hh, diag)
    arr = TColgp_Array2OfPnt(1, nu, 1, nv)
    for i in range(nu):
        for j in range(nv):
            p = c + GU[i, j] * U + GV[i, j] * V + H[i, j] * N
            arr.SetValue(i + 1, j + 1, gp_Pnt(float(p[0]), float(p[1]), float(p[2])))
    h_data = float(hh.max() - hh.min())
    surf = None
    err = None

    def hfun(P):
        return float((P - c) @ N)

    for _ in range(4):
        try:
            surf = GeomAPI_PointsToBSplineSurface(
                arr, Approx_IsoParametric, 3, 3, GeomAbs_C2, tol3d).Surface()
        except Exception as e:
            err = e
            break
        if surf_h_range(surf, hfun) <= 3.0 * h_data + 0.1 * diag:
            break
        tol3d *= 4.0
    if surf is None:
        raise RuntimeError(f"el ajuste B-spline falló: {err}")
    return surf, {"frame": (c, U, V, N), "grid": f"{nu}×{nv}", "nu": nu, "nv": nv,
                  "tol3d": tol3d, "diag": diag}


def tessellate(surf, nu=40, nv=40):

    u0, u1, v0, v1 = surf.Bounds()
    us = np.linspace(u0, u1, nu)
    vs = np.linspace(v0, v1, nv)
    verts = np.empty((nu * nv, 3), float)
    k = 0
    for i in range(nu):
        for j in range(nv):
            p = surf.Value(float(us[i]), float(vs[j]))
            verts[k] = (p.X(), p.Y(), p.Z())
            k += 1
    tris = []
    for i in range(nu - 1):
        for j in range(nv - 1):
            a = i * nv + j
            b = a + 1
            c = a + nv
            d = c + 1
            tris.append((a, b, d))
            tris.append((a, d, c))
    return verts, np.asarray(tris, int)


def _boundary_segments_3d(mesh, faces):

    from collections import Counter
    tris = mesh.faces[np.asarray(faces)]
    cnt = Counter()
    for t in tris:
        for i in range(3):
            a, b = int(t[i]), int(t[(i + 1) % 3])
            cnt[(a, b) if a < b else (b, a)] += 1
    bedges = [e for e, k in cnt.items() if k == 1]
    if len(bedges) < 3:
        return None, None
    vid = np.asarray(bedges)
    return (mesh.vertices[vid[:, 0]].astype(float),
            mesh.vertices[vid[:, 1]].astype(float))


def _inside_polygon(pts_uv, A, B):

    x = pts_uv[:, 0][:, None]; y = pts_uv[:, 1][:, None]
    ax = A[:, 0][None, :]; ay = A[:, 1][None, :]
    bx = B[:, 0][None, :]; by = B[:, 1][None, :]
    cond = (ay > y) != (by > y)
    t = (y - ay) / (by - ay + 1e-30)
    xint = ax + t * (bx - ax)
    crosses = cond & (xint > x)
    return (crosses.sum(axis=1) % 2) == 1


def _boundary_uv(info, mesh, faces):

    A3, B3 = _boundary_segments_3d(mesh, faces)
    if A3 is None:
        return None, None
    A = np.array([map_uv(info, p) for p in A3])
    B = np.array([map_uv(info, p) for p in B3])
    if info["mode"] == "cyl":
        dB = np.mod(B[:, 0] - A[:, 0] + np.pi, TWO_PI) - np.pi
        B[:, 0] = A[:, 0] + dB
        if info["full"]:
            sh = np.array([TWO_PI, 0.0])
            A = np.vstack([A, A + sh, A - sh])
            B = np.vstack([B, B + sh, B - sh])
    return A, B


def refine_poles(surf, nu_target, nv_target):

    for _ in range(96):
        if surf.NbUPoles() >= int(nu_target):
            break
        ks = [surf.UKnot(i + 1) for i in range(surf.NbUKnots())]
        w = int(np.argmax(np.diff(ks)))
        surf.InsertUKnot(float((ks[w] + ks[w + 1]) / 2), 1, 1e-10, True)
    for _ in range(96):
        if surf.NbVPoles() >= int(nv_target):
            break
        ks = [surf.VKnot(i + 1) for i in range(surf.NbVKnots())]
        w = int(np.argmax(np.diff(ks)))
        surf.InsertVKnot(float((ks[w] + ks[w + 1]) / 2), 1, 1e-10, True)


def apply_pole_edits(surf, edits):

    if not edits:
        return
    nu, nv = surf.NbUPoles(), surf.NbVPoles()
    for e in edits:
        i, j = int(e[0]), int(e[1])
        if 0 <= i < nu and 0 <= j < nv:
            p = surf.Pole(i + 1, j + 1)
            surf.SetPole(i + 1, j + 1,
                         gp_Pnt(p.X() + float(e[2]), p.Y() + float(e[3]), p.Z() + float(e[4])))


def surface_poles(surf):

    nu, nv = surf.NbUPoles(), surf.NbVPoles()
    out = []
    for i in range(nu):
        for j in range(nv):
            p = surf.Pole(i + 1, j + 1)
            out.append([p.X(), p.Y(), p.Z()])
    return out, nu, nv


def _near_boundary(pts_uv, A, B, dist, info):

    sx = info["rho_mean"] if info["mode"] == "cyl" else 1.0
    scale = np.array([sx, 1.0])
    P, Q = A * scale, B * scale
    seg = Q - P
    L = np.linalg.norm(seg, axis=1)
    step = max(dist / 2.0, 1e-6)
    samples = [P, Q]
    kmax = int(min(64, np.ceil(float(L.max()) / step))) if len(L) else 0
    for k in range(1, kmax):
        t = k * step
        m = L > t
        if not m.any():
            break
        samples.append(P[m] + seg[m] * (t / L[m])[:, None])
    d, _ = cKDTree(np.vstack(samples)).query(pts_uv * scale)
    return d <= dist + step / 2


def fit_region(mesh, faces, grid=None, smooth=0.0, trim=True, grow=0.0, edits=None):

    faces = np.asarray(faces, int)
    grow = max(0.0, float(grow))
    info = fit_mesh_region(mesh, faces, grid=grid, smooth=smooth, grow=grow)
    surf = info["surf"]
    if grid:
        refine_poles(surf, int(grid), int(grid))
    apply_pole_edits(surf, edits)
    pts = info["pts"]

    res_u = int(max(40, 2 * info["nu"]))
    res_v = int(max(40, 2 * info["nv"]))
    verts, tris = tessellate(surf, res_u, res_v)

    dist, _ = cKDTree(verts).query(pts)
    rms, mx = float(np.sqrt((dist ** 2).mean())), float(dist.max())

    if trim:
        A, B = _boundary_uv(info, mesh, faces)
        if A is not None:
            cen3 = verts[tris].mean(axis=1)
            cen_uv = np.array([map_uv(info, p) for p in cen3])
            if info["mode"] == "cyl":

                keep = _inside_polygon(cen_uv[:, ::-1], A[:, ::-1], B[:, ::-1])
            else:
                keep = _inside_polygon(cen_uv, A, B)
            if grow > 1e-9:
                keep |= _near_boundary(cen_uv, A, B, grow, info)
            if keep.sum() >= 4:
                tris = tris[keep]

    poles, pnu, pnv = surface_poles(surf)
    data = {
        "vertices": verts.tolist(),
        "triangles": tris.tolist(),
        "rms": rms,
        "max": mx,
        "n_pts": int(len(pts)),
        "n_faces": int(len(faces)),
        "grid": info["grid"],
        "poles": poles,
        "poles_nu": pnu, "poles_nv": pnv,
    }
    return data, surf

if __name__ == "__main__":
    import sys
    import trimesh

    path = sys.argv[1] if len(sys.argv) > 1 else r"pieza.stl"
    mesh = trimesh.load(path, force="mesh")
    mesh.merge_vertices()

    faces = list(range(len(mesh.faces)))
    data, surf = fit_region(mesh, faces)
    print(f"NURBS sobre {data['n_pts']} puntos / {data['n_faces']} caras")
    print(f"  rejilla de control {data['grid']}")
    print(f"  teselada: {len(data['vertices'])} vértices, {len(data['triangles'])} triángulos")
    print(f"  RMS {data['rms']:.4f} mm · máx {data['max']:.4f} mm")
