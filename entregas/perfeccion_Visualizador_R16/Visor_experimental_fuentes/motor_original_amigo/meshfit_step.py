import numpy as np

from OCP.gp import (gp_Pnt, gp_Dir, gp_Ax3, gp_Pln, gp_Cylinder, gp_Cone,
                    gp_Sphere, gp_Torus)
from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeFace, BRepBuilderAPI_Sewing,
                                BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeEdge,
                                BRepBuilderAPI_MakeWire)
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
from OCP.Approx import Approx_IsoParametric
from OCP.GeomAbs import GeomAbs_C2
from OCP.gp import gp_Pnt2d
from OCP.GCE2d import GCE2d_MakeSegment
from OCP.BRepLib import BRepLib
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRep import BRep_Tool
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.Interface import Interface_Static
from OCP.IFSelect import IFSelect_RetDone


def _ax3(origin, zdir, xdir):
    return gp_Ax3(gp_Pnt(*map(float, origin)), gp_Dir(*map(float, zdir)), gp_Dir(*map(float, xdir)))


def _perp(axis):
    axis = np.asarray(axis, float)
    ref = np.array([1.0, 0, 0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1, 0])
    x = np.cross(axis, ref); x /= np.linalg.norm(x)
    y = np.cross(axis, x)
    return x, y


def _ang_range(angles, full_tol_deg=15.0, margin_deg=1.0):

    a = np.sort(np.mod(angles, 2 * np.pi))
    n = len(a)
    ext = np.append(a, a[0] + 2 * np.pi)
    gaps = np.diff(ext)
    k = int(np.argmax(gaps))
    if gaps[k] < np.radians(full_tol_deg):
        return 0.0, 2 * np.pi
    m = np.radians(margin_deg)
    if k == n - 1:
        return float(a[0] - m), float(a[n - 1] + m)
    return float(a[k + 1] - m), float(a[k] + 2 * np.pi + m)


def _boundary_loops(mesh, face_idx):

    from collections import Counter, defaultdict
    faces = mesh.faces[np.asarray(face_idx)]
    cnt = Counter()
    for tri in faces:
        for i in range(3):
            a, b = int(tri[i]), int(tri[(i + 1) % 3])
            cnt[(a, b) if a < b else (b, a)] += 1
    bedges = [e for e, c in cnt.items() if c == 1]
    adj = defaultdict(list)
    for a, b in bedges:
        adj[a].append(b); adj[b].append(a)
    used = set()
    loops = []
    for a0, b0 in bedges:
        if (a0, b0) in used:
            continue
        loop = [a0]
        used.add((a0, b0)); used.add((b0, a0))
        cur = b0
        while cur != a0:
            loop.append(cur)
            nxt = [v for v in adj[cur] if (cur, v) not in used]
            if not nxt:
                break
            nv = nxt[0]
            used.add((cur, nv)); used.add((nv, cur))
            cur = nv
        loops.append(loop)
    return loops


def _signed_area_2d(u, v):

    return 0.5 * float(np.sum(u * np.roll(v, -1) - np.roll(u, -1) * v))


def _offset_poly_2d(uv, d):

    uv = np.asarray(uv, float)
    n = len(uv)
    sgn = 1.0 if _signed_area_2d(uv[:, 0], uv[:, 1]) >= 0 else -1.0
    out = np.empty_like(uv)
    for i in range(n):
        p0, p1, p2 = uv[i - 1], uv[i], uv[(i + 1) % n]
        d1, d2 = p1 - p0, p2 - p1
        l1 = float(np.hypot(*d1)) or 1.0
        l2 = float(np.hypot(*d2)) or 1.0
        d1, d2 = d1 / l1, d2 / l2
        n1 = np.array([sgn * d1[1], -sgn * d1[0]])
        n2 = np.array([sgn * d2[1], -sgn * d2[0]])
        b = n1 + n2
        bl = float(np.hypot(*b))
        if bl < 1e-9:
            out[i] = p1 + n1 * d
            continue
        k = min(2.0 / bl, 4.0)
        out[i] = p1 + (b / bl) * k * d
    return out


def _offset_poly_2d_aniso(uv, d4, bx, by, gu, gv):

    uv = np.asarray(uv, float)
    n = len(uv)
    sgn = 1.0 if _signed_area_2d(uv[:, 0], uv[:, 1]) >= 0 else -1.0
    T = np.empty((n, 2)); D = np.empty(n); P = np.empty((n, 2))
    for i in range(n):
        t = uv[(i + 1) % n] - uv[i]
        l = float(np.hypot(*t)) or 1.0
        t = t / l
        no = np.array([sgn * t[1], -sgn * t[0]])
        n3 = no[0] * bx + no[1] * by
        cu, cv = float(n3 @ gu), float(n3 @ gv)
        dist = (max(cu, 0) * d4[0] + max(-cu, 0) * d4[1]
                + max(cv, 0) * d4[2] + max(-cv, 0) * d4[3])
        T[i] = t; D[i] = dist
        P[i] = uv[i] + no * dist
    out = np.empty_like(uv)
    for i in range(n):
        ip = (i - 1) % n
        cross = T[ip][0] * T[i][1] - T[ip][1] * T[i][0]
        if abs(cross) < 1e-9:
            no = np.array([sgn * T[i][1], -sgn * T[i][0]])
            v = uv[i] + no * D[i]
        else:
            s = ((P[i][0] - P[ip][0]) * T[i][1] - (P[i][1] - P[ip][1]) * T[i][0]) / cross
            v = P[ip] + T[ip] * s
        dv = v - uv[i]
        lim = 4.0 * max(D[ip], D[i], 1e-12)
        dl = float(np.hypot(*dv))
        out[i] = uv[i] + dv / dl * lim if dl > lim else v
    return out


def _ext2(prim, key):

    v = prim.get(key)
    if not v:
        return None
    a, b = float(v[0]), float(v[1])
    return (a, b) if (abs(a) > 1e-9 or abs(b) > 1e-9) else None


def _face_plane(prim, mesh, face_idx):

    verts = mesh.vertices
    n = np.asarray(prim["normal"], float); n /= np.linalg.norm(n)
    x, y = _perp(n)
    o = np.asarray(prim["point"], float)
    loops = _boundary_loops(mesh, face_idx)
    if not loops:
        return None

    def to_2d(loop):
        d = verts[loop] - o
        return np.column_stack([d @ x, d @ y])

    uv_loops = [to_2d(l) for l in loops]
    uv_loops.sort(key=lambda uv: abs(_signed_area_2d(uv[:, 0], uv[:, 1])), reverse=True)

    grow = prim.get("grow") or 0.0
    if isinstance(grow, (list, tuple)):
        d4 = [max(0.0, float(v)) for v in grow]
        if max(d4) > 1e-9:
            gu = np.asarray(prim["gu"], float); gu /= np.linalg.norm(gu)
            gv = np.asarray(prim["gv"], float); gv /= np.linalg.norm(gv)
            uv_loops[0] = _offset_poly_2d_aniso(uv_loops[0], d4, x, y, gu, gv)
    elif float(grow) > 1e-9:
        uv_loops[0] = _offset_poly_2d(uv_loops[0], float(grow))

    def make_wire(uv, ccw):
        if (_signed_area_2d(uv[:, 0], uv[:, 1]) > 0) != ccw:
            uv = uv[::-1]
        poly = BRepBuilderAPI_MakePolygon()
        for q in uv:
            p = o + x * float(q[0]) + y * float(q[1])
            poly.Add(gp_Pnt(float(p[0]), float(p[1]), float(p[2])))
        poly.Close()
        return poly.Wire()

    mk = BRepBuilderAPI_MakeFace(make_wire(uv_loops[0], True), True)
    for hole in uv_loops[1:]:
        if abs(_signed_area_2d(hole[:, 0], hole[:, 1])) > 1e-9:
            mk.Add(make_wire(hole, False))
    return mk.Face()


def _unwrap(vals, period=2 * np.pi):

    out = [float(vals[0])]
    for x in vals[1:]:
        prev = out[-1]
        x = float(x)
        while x - prev > period / 2:
            x -= period
        while x - prev < -period / 2:
            x += period
        out.append(x)
    return out


def _trim_curved(surf, mesh, face_idx, to_uv, uperiodic=True, vperiodic=False):

    loops = _boundary_loops(mesh, face_idx)
    if not loops:
        return None
    verts = mesh.vertices
    uv_loops = []
    for loop in loops:
        uv = [to_uv(verts[vi].astype(float)) for vi in loop]
        us = _unwrap([p[0] for p in uv]) if uperiodic else [p[0] for p in uv]
        vs = _unwrap([p[1] for p in uv]) if vperiodic else [p[1] for p in uv]
        uv_loops.append(list(zip(us, vs)))

    def signed_area(uv):
        u = np.array([p[0] for p in uv]); v = np.array([p[1] for p in uv])
        return _signed_area_2d(u, v)

    uv_loops.sort(key=lambda l: abs(signed_area(l)), reverse=True)
    if abs(signed_area(uv_loops[0])) < 1e-9:
        return None

    def make_wire(uv, ccw):

        if (signed_area(uv) > 0) != ccw:
            uv = uv[::-1]
        w = BRepBuilderAPI_MakeWire()
        n = len(uv)
        for i in range(n):
            a, b = uv[i], uv[(i + 1) % n]
            if abs(a[0] - b[0]) < 1e-12 and abs(a[1] - b[1]) < 1e-12:
                continue
            seg = GCE2d_MakeSegment(gp_Pnt2d(a[0], a[1]), gp_Pnt2d(b[0], b[1])).Value()
            w.Add(BRepBuilderAPI_MakeEdge(seg, surf).Edge())
        ww = w.Wire()
        BRepLib.BuildCurves3d_s(ww)
        return ww

    mk = BRepBuilderAPI_MakeFace(surf, make_wire(uv_loops[0], True), True)
    for hole in uv_loops[1:]:
        if abs(signed_area(hole)) > 1e-9:
            mk.Add(make_wire(hole, False))
    return mk.Face()


def _area(face):
    g = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, g)
    return float(g.Mass())


def _hull_face_uv(surf, uvs):

    from scipy.spatial import ConvexHull
    hull = ConvexHull(np.asarray(uvs, float))
    pts = [uvs[i] for i in hull.vertices]
    w = BRepBuilderAPI_MakeWire()
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if abs(a[0] - b[0]) < 1e-12 and abs(a[1] - b[1]) < 1e-12:
            continue
        seg = GCE2d_MakeSegment(gp_Pnt2d(float(a[0]), float(a[1])),
                                gp_Pnt2d(float(b[0]), float(b[1]))).Value()
        w.Add(BRepBuilderAPI_MakeEdge(seg, surf).Edge())
    ww = w.Wire()
    BRepLib.BuildCurves3d_s(ww)
    return BRepBuilderAPI_MakeFace(surf, ww, True).Face()


def _finish_curved(rectface, mesh, face_idx, to_uv, uperiodic=True, vperiodic=False):

    surf = BRep_Tool.Surface_s(rectface)
    try:
        trimmed = _trim_curved(surf, mesh, face_idx, to_uv, uperiodic, vperiodic)
    except Exception as e:
        print(f"  [curva sin recortar a contorno] {e}")
        trimmed = None
    if trimmed is not None and BRepCheck_Analyzer(trimmed).IsValid():
        return trimmed
    try:
        pts = mesh.vertices[np.unique(mesh.faces[np.asarray(face_idx)].ravel())].astype(float)
        uvs = np.array([to_uv(P) for P in pts], float)
        if uperiodic:
            u0, _ = _ang_range(uvs[:, 0])
            uvs[:, 0] = u0 + np.mod(uvs[:, 0] - u0, 2 * np.pi)
        if vperiodic:
            v0, _ = _ang_range(uvs[:, 1])
            uvs[:, 1] = v0 + np.mod(uvs[:, 1] - v0, 2 * np.pi)
        hull = _hull_face_uv(surf, uvs)
    except Exception:
        hull = None
    if hull is not None and BRepCheck_Analyzer(hull).IsValid() and _area(hull) < 0.999 * _area(rectface):
        return hull
    return rectface


def _face_cylinder(prim, mesh, face_idx):
    axis = np.asarray(prim["axis"], float); axis /= np.linalg.norm(axis)
    x, y = _perp(axis)
    o = np.asarray(prim["point"], float)
    pts = mesh.vertices[np.unique(mesh.faces[face_idx].ravel())].astype(float)
    d = pts - o
    ang = np.arctan2(d @ y, d @ x)
    v = d @ axis
    u0, u1 = _ang_range(ang)
    cyl = gp_Cylinder(_ax3(o, axis, x), float(prim["radius"]))
    ext, ang_ext = _ext2(prim, "ext"), _ext2(prim, "ang_ext")
    if ext or ang_ext:

        e0, e1 = ext or (0.0, 0.0)
        a0, a1 = ang_ext or (0.0, 0.0)
        u0, u1 = u0 - a0, u1 + a1
        if u1 - u0 >= 2 * np.pi:
            u0, u1 = 0.0, 2 * np.pi
        return BRepBuilderAPI_MakeFace(cyl, u0, u1,
                                       float(v.min()) - e0, float(v.max()) + e1).Face()
    rect = BRepBuilderAPI_MakeFace(cyl, u0, u1, float(v.min()), float(v.max())).Face()
    def to_uv(P):
        dd = P - o
        return (float(np.arctan2(dd @ y, dd @ x)), float(dd @ axis))
    return _finish_curved(rect, mesh, face_idx, to_uv)


def _face_cone(prim, mesh, face_idx):
    axis = np.asarray(prim["axis"], float); axis /= np.linalg.norm(axis)
    x, y = _perp(axis)
    o = np.asarray(prim["origin"], float)
    half = float(prim["half_angle"])
    r_ref = float(prim["b"])
    pts = mesh.vertices[np.unique(mesh.faces[face_idx].ravel())].astype(float)
    d = pts - o
    ang = np.arctan2(d @ y, d @ x)
    u0, u1 = _ang_range(ang)
    v = (d @ axis) / np.cos(half)
    cone = gp_Cone(_ax3(o, axis, x), half, max(r_ref, 1e-4))
    ext, ang_ext = _ext2(prim, "ext"), _ext2(prim, "ang_ext")
    if ext or ang_ext:

        e0, e1 = ext or (0.0, 0.0)
        a0, a1 = ang_ext or (0.0, 0.0)
        u0, u1 = u0 - a0, u1 + a1
        if u1 - u0 >= 2 * np.pi:
            u0, u1 = 0.0, 2 * np.pi
        cos_h, sin_h = float(np.cos(half)), float(np.sin(half))
        v0 = float(v.min()) - e0 / cos_h
        v1 = float(v.max()) + e1 / cos_h
        if sin_h > 1e-9:
            v0 = max(v0, -max(r_ref, 1e-4) / sin_h + 1e-6)
        return BRepBuilderAPI_MakeFace(cone, u0, u1, v0, v1).Face()
    rect = BRepBuilderAPI_MakeFace(cone, u0, u1, float(v.min()), float(v.max())).Face()
    cos_h = np.cos(half)
    def to_uv(P):
        dd = P - o
        return (float(np.arctan2(dd @ y, dd @ x)), float((dd @ axis) / cos_h))
    return _finish_curved(rect, mesh, face_idx, to_uv)


def _face_sphere(prim, mesh, face_idx):
    o = np.asarray(prim["center"], float)
    R = float(prim["radius"])
    z = np.array([0.0, 0, 1.0]); x = np.array([1.0, 0, 0]); yv = np.array([0.0, 1, 0])
    pts = mesh.vertices[np.unique(mesh.faces[face_idx].ravel())].astype(float)
    d = pts - o
    ang = np.arctan2(d @ yv, d @ x)
    lat = np.arcsin(np.clip((d @ z) / R, -1, 1))
    u0, u1 = _ang_range(ang)
    sph = gp_Sphere(_ax3(o, z, x), R)
    rect = BRepBuilderAPI_MakeFace(sph, u0, u1, float(lat.min()), float(lat.max())).Face()
    def to_uv(P):
        dd = P - o
        return (float(np.arctan2(dd @ yv, dd @ x)), float(np.arcsin(np.clip((dd @ z) / R, -1, 1))))
    return _finish_curved(rect, mesh, face_idx, to_uv)


def _face_torus(prim, mesh, face_idx):
    axis = np.asarray(prim["axis"], float); axis /= np.linalg.norm(axis)
    x, y = _perp(axis)
    o = np.asarray(prim["center"], float)
    R, r = float(prim["R"]), float(prim["r"])
    pts = mesh.vertices[np.unique(mesh.faces[face_idx].ravel())].astype(float)
    d = pts - o
    ang = np.arctan2(d @ y, d @ x)
    rho = np.sqrt((d @ x) ** 2 + (d @ y) ** 2) - R
    vang = np.arctan2(d @ axis, rho)
    u0, u1 = _ang_range(ang)
    v0, v1 = _ang_range(vang)
    tor = gp_Torus(_ax3(o, axis, x), R, r)
    rect = BRepBuilderAPI_MakeFace(tor, u0, u1, v0, v1).Face()
    def to_uv(P):
        dd = P - o
        rh = np.sqrt((dd @ x) ** 2 + (dd @ y) ** 2) - R
        return (float(np.arctan2(dd @ y, dd @ x)), float(np.arctan2(dd @ axis, rh)))
    return _finish_curved(rect, mesh, face_idx, to_uv, vperiodic=True)


def _face_nurbs(mesh, face_idx, nu=14, nv=14, deg_max=8, interp="cubic", enforce_area=True,
                adaptive=False):

    from scipy.interpolate import griddata
    from meshfit_nurbs import grid_from_smooth
    verts = mesh.vertices
    vidx = np.unique(mesh.faces[np.asarray(face_idx)].ravel())
    pts = verts[vidx].astype(float)
    if len(pts) < 16:
        return None
    if adaptive:

        nu = nv = int(np.clip(round(np.sqrt(len(pts))), nu, 30))
    c = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    n = vt[2] / np.linalg.norm(vt[2])
    x = vt[0] / np.linalg.norm(vt[0])
    y = np.cross(n, x)
    d = pts - c
    u, v, h = d @ x, d @ y, d @ n
    umin, umax, vmin, vmax = float(u.min()), float(u.max()), float(v.min()), float(v.max())
    us = np.linspace(umin, umax, nu)
    vs = np.linspace(vmin, vmax, nv)
    GU, GV = np.meshgrid(us, vs)
    H = griddata((u, v), h, (GU, GV), method=interp)
    if np.isnan(H).any():
        Hn = griddata((u, v), h, (GU, GV), method="nearest")
        H = np.where(np.isnan(H), Hn, H)

    lat = max(umax - umin, vmax - vmin, 1e-6)
    h_data = float(h.max() - h.min())
    h_fit = float(np.nanmax(H) - np.nanmin(H))
    if not np.isfinite(h_fit) or h_fit > 6.0 * h_data + 0.25 * lat:
        print(f"  [nurbs descartado: altura ajustada {h_fit:.0f} mm >> curvatura real "
              f"{h_data:.2f} mm (lat {lat:.1f}) -> region plegada/explotada]")
        return None
    arr = TColgp_Array2OfPnt(1, nu, 1, nv)
    for iu in range(nu):
        for iv in range(nv):
            P = c + us[iu] * x + vs[iv] * y + float(H[iv, iu]) * n
            arr.SetValue(iu + 1, iv + 1, gp_Pnt(float(P[0]), float(P[1]), float(P[2])))

    deg = int(deg_max) if min(nu, nv) > 16 else min(int(deg_max), 3)
    surf = GeomAPI_PointsToBSplineSurface(arr, Approx_IsoParametric, 3, deg, GeomAbs_C2, 1e-3).Surface()
    rect = BRepBuilderAPI_MakeFace(surf, 1e-6).Face()
    try:
        trimmed = _trim_nurbs(mesh, face_idx, surf, c, x, y, umin, umax, vmin, vmax)
    except Exception as e:
        print(f"  [nurbs sin recortar] {e}")
        trimmed = None

    face = rect
    if trimmed is not None and BRepCheck_Analyzer(trimmed).IsValid():
        face = trimmed
    else:
        try:
            hull = _hull_trim(surf, u, v, umin, umax, vmin, vmax)
        except Exception:
            hull = None
        if hull is not None and BRepCheck_Analyzer(hull).IsValid():
            face = hull

    if enforce_area:
        mesh_area = float(mesh.area_faces[np.asarray(face_idx)].sum())
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(face, g)
        fa = g.Mass()
        if not np.isfinite(fa) or fa > 3.0 * mesh_area:
            print(f"  [nurbs descartado: area {fa:.0f} vs malla {mesh_area:.0f} mm2 -> region plegada]")
            return None
    return face


def _hull_trim(surf, u, v, umin, umax, vmin, vmax):

    from scipy.spatial import ConvexHull
    pts2 = np.column_stack([u, v])
    hull = ConvexHull(pts2)
    U1, U2, V1, V2 = surf.Bounds()
    du = (umax - umin) or 1.0
    dv = (vmax - vmin) or 1.0
    uvs = []
    for i in hull.vertices:
        U = U1 + (float(u[i]) - umin) / du * (U2 - U1)
        V = V1 + (float(v[i]) - vmin) / dv * (V2 - V1)
        uvs.append((min(max(U, U1), U2), min(max(V, V1), V2)))
    wire = BRepBuilderAPI_MakeWire()
    n = len(uvs)
    for i in range(n):
        a, b = uvs[i], uvs[(i + 1) % n]
        if abs(a[0] - b[0]) < 1e-12 and abs(a[1] - b[1]) < 1e-12:
            continue
        seg = GCE2d_MakeSegment(gp_Pnt2d(a[0], a[1]), gp_Pnt2d(b[0], b[1])).Value()
        wire.Add(BRepBuilderAPI_MakeEdge(seg, surf).Edge())
    w = wire.Wire()
    BRepLib.BuildCurves3d_s(w)
    return BRepBuilderAPI_MakeFace(surf, w, True).Face()


def _trim_nurbs(mesh, face_idx, surf, c, x, y, umin, umax, vmin, vmax):

    verts = mesh.vertices
    loops = _boundary_loops(mesh, face_idx)
    if not loops:
        return None

    def loop_area(loop):
        d = verts[loop] - c
        uu, vv = d @ x, d @ y
        return abs(0.5 * np.sum(uu * np.roll(vv, -1) - np.roll(uu, -1) * vv))

    outer = max(loops, key=loop_area)
    if len(outer) < 3:
        return None
    U1, U2, V1, V2 = surf.Bounds()
    du = (umax - umin) or 1.0
    dv = (vmax - vmin) or 1.0

    def to_uv(vi):
        p = verts[vi] - c
        U = U1 + (float(p @ x) - umin) / du * (U2 - U1)
        V = V1 + (float(p @ y) - vmin) / dv * (V2 - V1)
        return min(max(U, U1), U2), min(max(V, V1), V2)

    uvs = [to_uv(vi) for vi in outer]

    if _signed_area_2d(np.array([p[0] for p in uvs]), np.array([p[1] for p in uvs])) < 0:
        uvs = uvs[::-1]
    wire = BRepBuilderAPI_MakeWire()
    nN = len(uvs)
    for i in range(nN):
        a, b = uvs[i], uvs[(i + 1) % nN]
        if abs(a[0] - b[0]) < 1e-12 and abs(a[1] - b[1]) < 1e-12:
            continue
        seg = GCE2d_MakeSegment(gp_Pnt2d(a[0], a[1]), gp_Pnt2d(b[0], b[1])).Value()
        wire.Add(BRepBuilderAPI_MakeEdge(seg, surf).Edge())
    w = wire.Wire()
    BRepLib.BuildCurves3d_s(w)
    return BRepBuilderAPI_MakeFace(surf, w, True).Face()


def _facet_faces(mesh, face_idx):

    out = []
    for tri in mesh.faces[np.asarray(face_idx)]:
        poly = BRepBuilderAPI_MakePolygon()
        for vi in tri:
            p = mesh.vertices[int(vi)].astype(float)
            poly.Add(gp_Pnt(float(p[0]), float(p[1]), float(p[2])))
        poly.Close()
        out.append(BRepBuilderAPI_MakeFace(poly.Wire(), True).Face())
    return out

FACET_MAX = 60


def _nurbs_faces(mesh, face_idx, depth=0, max_depth=7, min_faces=80, max_fit=4000, deg_max=8):

    face_idx = np.asarray(face_idx)
    can_split = depth < max_depth and len(face_idx) >= 2 * min_faces
    if len(face_idx) <= max_fit:
        face = _face_nurbs(mesh, face_idx, deg_max=deg_max, adaptive=True)
        if face is not None:

            g = GProp_GProps()
            BRepGProp.SurfaceProperties_s(face, g)
            marea = float(mesh.area_faces[face_idx].sum())
            box = Bnd_Box()
            BRepBndLib.Add_s(face, box)
            x0, y0, z0, x1, y1, z1 = box.Get()
            fdiag = float(np.linalg.norm([x1 - x0, y1 - y0, z1 - z0]))
            rpts = mesh.vertices[np.unique(mesh.faces[face_idx].ravel())]
            rdiag = float(np.linalg.norm(rpts.max(0) - rpts.min(0))) or 1.0
            flaco = fdiag > 1.6 * rdiag
            if not flaco and (g.Mass() <= 1.5 * marea or not can_split):
                return [face]
            if flaco and not can_split:
                if len(face_idx) <= FACET_MAX:
                    print(f"  [nurbs->facetas: bbox {fdiag:.0f} mm >> region {rdiag:.0f} mm (lamina disparada)]")
                    return _facet_faces(mesh, face_idx)
                print(f"  [nurbs descartado: bbox {fdiag:.0f} mm >> region {rdiag:.0f} mm -> lamina disparada]")
                return []
    if not can_split:

        if len(face_idx) <= FACET_MAX:
            return _facet_faces(mesh, face_idx)
        return []
    fn = mesh.face_normals[face_idx]
    nbar = fn.mean(axis=0)
    if np.linalg.norm(nbar) < 0.5:

        _, _, vt = np.linalg.svd(fn - nbar, full_matrices=False)
        proj = fn @ vt[0]
    else:
        centroids = mesh.vertices[mesh.faces[face_idx]].mean(axis=1)
        ax = int(np.argmax(centroids.max(axis=0) - centroids.min(axis=0)))
        proj = centroids[:, ax]
    med = float(np.median(proj))
    left = face_idx[proj <= med]
    right = face_idx[proj > med]
    if len(left) < min_faces or len(right) < min_faces:
        return []
    return (_nurbs_faces(mesh, left, depth + 1, max_depth, min_faces, max_fit, deg_max) +
            _nurbs_faces(mesh, right, depth + 1, max_depth, min_faces, max_fit, deg_max))


def _face_helix(mesh, region):

    from meshfit_helix import fit_helix, helix_surface, _map_uv
    region = np.asarray(region, int)
    info, model = fit_helix(mesh, region)
    surf = helix_surface(info, model)
    rect = BRepBuilderAPI_MakeFace(surf, 1e-6).Face()
    if info["full"]:
        return rect
    U1, U2, V1, V2 = surf.Bounds()
    du = (info["u1"] - info["u0"]) or 1.0
    dv = (info["v1"] - info["v0"]) or 1.0
    su = (U2 - U1) / du
    sv = (V2 - V1) / dv

    def to_uv(P):
        u, v = _map_uv(info, P)
        return (U1 + (u - info["u0"]) * su, V1 + (v - info["v0"]) * sv)

    try:
        trimmed = _trim_curved(surf, mesh, region, to_uv, uperiodic=False)
    except Exception:
        trimmed = None
    if trimmed is not None and BRepCheck_Analyzer(trimmed).IsValid():
        return trimmed
    try:
        uvs = np.array([to_uv(P) for P in info["pts"]])
        hull = _hull_face_uv(surf, uvs)
    except Exception:
        hull = None
    if hull is not None and BRepCheck_Analyzer(hull).IsValid():
        return hull
    return rect


def _grown_nurbs_face(info, surf, mesh, region, grow):

    from meshfit_nurbs import map_uv
    verts = mesh.vertices
    loops = _boundary_loops(mesh, region)
    if not loops:
        return None
    uv_loops = [np.array([map_uv(info, verts[vi].astype(float)) for vi in loop])
                for loop in loops if len(loop) >= 3]
    if not uv_loops:
        return None
    sx = info["rho_mean"] if info["mode"] == "cyl" else 1.0
    scale = np.array([sx, 1.0])
    areas = [abs(_signed_area_2d(uv[:, 0] * sx, uv[:, 1])) for uv in uv_loops]
    k = int(np.argmax(areas))
    grown = _offset_poly_2d(uv_loops[k] * scale, float(grow)) / scale
    grown[:, 0] = np.clip(grown[:, 0], info["u0"], info["u1"])
    grown[:, 1] = np.clip(grown[:, 1], info["v0"], info["v1"])
    U1, U2, V1, V2 = surf.Bounds()
    du = (info["u1"] - info["u0"]) or 1.0
    dv = (info["v1"] - info["v0"]) or 1.0

    def wire_from(uv, ccw):
        if (_signed_area_2d(uv[:, 0], uv[:, 1]) > 0) != ccw:
            uv = uv[::-1]
        w = BRepBuilderAPI_MakeWire()
        n = len(uv)
        for i in range(n):
            a, b = uv[i], uv[(i + 1) % n]
            pa = (U1 + (a[0] - info["u0"]) / du * (U2 - U1), V1 + (a[1] - info["v0"]) / dv * (V2 - V1))
            pb = (U1 + (b[0] - info["u0"]) / du * (U2 - U1), V1 + (b[1] - info["v0"]) / dv * (V2 - V1))
            if abs(pa[0] - pb[0]) < 1e-12 and abs(pa[1] - pb[1]) < 1e-12:
                continue
            seg = GCE2d_MakeSegment(gp_Pnt2d(*pa), gp_Pnt2d(*pb)).Value()
            w.Add(BRepBuilderAPI_MakeEdge(seg, surf).Edge())
        ww = w.Wire()
        BRepLib.BuildCurves3d_s(ww)
        return ww

    mk = BRepBuilderAPI_MakeFace(surf, wire_from(grown, True), True)
    for j, hole in enumerate(uv_loops):
        if j != k and abs(_signed_area_2d(hole[:, 0], hole[:, 1])) > 1e-9:
            mk.Add(wire_from(hole, False))
    return mk.Face()


def _face_manual_nurbs(mesh, region, smooth, grow=0.0, grid=None, edits=None):

    from meshfit_nurbs import fit_mesh_region, map_uv, apply_pole_edits, refine_poles
    region = np.asarray(region, int)
    grow = max(0.0, float(grow))
    info = fit_mesh_region(mesh, region, grid=(int(grid) if grid else None),
                           smooth=smooth, grow=grow)
    surf = info["surf"]
    if grid:
        refine_poles(surf, int(grid), int(grid))
    apply_pole_edits(surf, edits)
    U1, U2, V1, V2 = surf.Bounds()
    du = (info["u1"] - info["u0"]) or 1.0
    dv = (info["v1"] - info["v0"]) or 1.0
    su = (U2 - U1) / du
    sv = (V2 - V1) / dv

    def to_uv(P):
        u, v = map_uv(info, P)
        return (U1 + (u - info["u0"]) * su, V1 + (v - info["v0"]) * sv)

    rect = BRepBuilderAPI_MakeFace(surf, 1e-6).Face()
    if info["mode"] == "cyl" and info["full"]:
        return rect
    if grow > 1e-9:
        try:
            face = _grown_nurbs_face(info, surf, mesh, region, grow)
        except Exception as e:
            print(f"  [nurbs ampliada sin recorte] {e}")
            face = None
        if face is not None and BRepCheck_Analyzer(face).IsValid():
            return face
        return rect
    try:

        trimmed = _trim_curved(surf, mesh, region, to_uv, uperiodic=False)
    except Exception:
        trimmed = None
    if trimmed is not None and BRepCheck_Analyzer(trimmed).IsValid():
        return trimmed
    try:
        uvs = np.array([to_uv(P) for P in info["pts"]])
        hull = _hull_face_uv(surf, uvs)
    except Exception:
        hull = None
    if hull is not None and BRepCheck_Analyzer(hull).IsValid():
        return hull
    return rect

LAST_INFO = {"solid": False}

_FACE = {"plane": _face_plane, "cylinder": _face_cylinder, "cone": _face_cone,
         "sphere": _face_sphere, "torus": _face_torus}


def export_step(result, mesh, out_path, organic=True, extra_nurbs_regions=None,
                extra_nurbs_smooth=None, extra_helix_regions=None, extra_nurbs_grow=None,
                extra_nurbs_grid=None, extra_nurbs_edits=None, solid=True, organic_smooth=0.0,
                ajuste_ia=False):

    global LAST_INFO
    LAST_INFO = {"solid": False}

    grown = (any(p.get("ext") or p.get("ang_ext") or p.get("grow") for p in result["primitives"])
             or any(float(g or 0) > 1e-9 for g in (extra_nurbs_grow or [])))
    if solid and grown:
        LAST_INFO = {"solid": False, "reason": "ampliaciones"}
    if solid and not grown:
        try:
            from meshfit_brep import build_solid
            extra = _user_surfaces(mesh, extra_nurbs_regions, extra_nurbs_smooth,
                                   extra_nurbs_grid, extra_nurbs_edits, extra_helix_regions, snap_pitch=ajuste_ia)
            shape, info = build_solid(result, mesh, extra_regions=extra,
                                      organic_smooth=organic_smooth, ajuste_ia=ajuste_ia)
            if shape is not None and info.get("solid") and info.get("valid"):
                LAST_INFO = info
                _write_step(shape, out_path)
                return info["faces"]
            print(f"  [brep] sin sólido válido ({info}); camino clásico")
        except Exception as e:
            print(f"  [brep] error {e}; camino clásico")
    sew = BRepBuilderAPI_Sewing(1e-3)
    n_ok = 0
    for prim in result["primitives"]:
        try:
            face = _FACE[prim["type"]](prim, mesh, np.asarray(prim["faces"]))
            if face is not None:
                sew.Add(face); n_ok += 1
        except Exception as e:
            print(f"  [skip {prim['type']}] {e}")

    _smooth = list(extra_nurbs_smooth or [])
    _grow = list(extra_nurbs_grow or [])
    _grid = list(extra_nurbs_grid or [])
    _edits = list(extra_nurbs_edits or [])
    manual = [(np.asarray(r, int),
               float(_smooth[i]) if i < len(_smooth) else 0.0,
               float(_grow[i]) if i < len(_grow) else 0.0,
               int(_grid[i]) if i < len(_grid) and _grid[i] else 0,
               _edits[i] if i < len(_edits) else None)
              for i, r in enumerate(extra_nurbs_regions or []) if len(r)]
    helices = [np.asarray(r, int) for r in (extra_helix_regions or []) if len(r)]
    manual_faces = set(int(f) for r, *_ in manual for f in r)
    manual_faces.update(int(f) for r in helices for f in r)

    if organic:
        for region in result.get("freeform_regions", []):
            region = np.asarray([int(f) for f in region if int(f) not in manual_faces], int)
            if len(region) == 0:
                continue
            try:

                mf = max(24, min(80, len(region) // 8))
                for face in _nurbs_faces(mesh, region, min_faces=mf):
                    sew.Add(face); n_ok += 1
            except Exception as e:
                print(f"  [skip nurbs] {e}")

    for region in helices:
        try:
            face = _face_helix(mesh, region)
            if face is not None:
                sew.Add(face); n_ok += 1
        except Exception as e:
            print(f"  [skip helicoide] {e}")

    for region, smooth, growv, gridv, editsv in manual:
        try:

            face = _face_manual_nurbs(mesh, region, smooth, growv, gridv, editsv)
            if face is None:
                print(f"  [nurbs manual sin cara: {len(region)} caras]")
            else:
                sew.Add(face); n_ok += 1
        except Exception as e:
            print(f"  [skip nurbs manual] {e}")

    sew.Perform()
    shape = sew.SewedShape()
    _write_step(shape, out_path)
    return n_ok


def _user_surfaces(mesh, nurbs_regions, nurbs_smooth, nurbs_grid, nurbs_edits, helix_regions,
                   snap_pitch=False):

    from meshfit_nurbs import fit_mesh_region, apply_pole_edits, refine_poles
    out = []
    sm, gr, ed = list(nurbs_smooth or []), list(nurbs_grid or []), list(nurbs_edits or [])
    for i, r in enumerate(nurbs_regions or []):
        if not len(r):
            continue
        try:
            grid = int(gr[i]) if i < len(gr) and gr[i] else None
            info = fit_mesh_region(mesh, np.asarray(r, int), grid=grid,
                                   smooth=float(sm[i]) if i < len(sm) else 0.0, grow=0.0)
            surf = info["surf"]
            if grid:
                refine_poles(surf, grid, grid)
            apply_pole_edits(surf, ed[i] if i < len(ed) else None)
            out.append((np.asarray(r, int), surf))
        except Exception as e:
            print(f"  [nurbs manual sin superficie: {e}]")
    for r in (helix_regions or []):
        if not len(r):
            continue
        try:
            from meshfit_helix import fit_helix, helix_surface
            info, model = fit_helix(mesh, np.asarray(r, int), snap_pitch=snap_pitch)
            out.append((np.asarray(r, int), helix_surface(info, model)))
        except Exception as e:
            print(f"  [rosca sin superficie: {e}]")
    return out


def _d2(p, q):
    return (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2


def _tess_welded(shape):

    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from OCP.TopExp import TopExp_Explorer, TopExp
    from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_REVERSED
    from OCP.TopoDS import TopoDS
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopTools import TopTools_IndexedMapOfShape
    vmap = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_VERTEX, vmap)
    emap = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_EDGE, emap)
    P = []
    for i in range(1, vmap.Extent() + 1):
        p = BRep_Tool.Pnt_s(TopoDS.Vertex_s(vmap.FindKey(i)))
        P.append((p.X(), p.Y(), p.Z()))
    pa, pb = [], []
    first = {}
    T = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face_s(exp.Current())
        exp.Next()
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is None:
            continue
        tr = loc.Transformation()
        base = len(P) - 1
        for i in range(1, tri.NbNodes() + 1):
            q = tri.Node(i).Transformed(tr)
            P.append((q.X(), q.Y(), q.Z()))
        ex = TopExp_Explorer(face, TopAbs_EDGE)
        while ex.More():
            e = TopoDS.Edge_s(ex.Current())
            ex.Next()
            pol = BRep_Tool.PolygonOnTriangulation_s(e, tri, loc)
            if pol is None:
                continue
            nodes = [base + pol.Node(k) for k in range(1, pol.NbNodes() + 1)]
            v0 = vmap.FindIndex(TopExp.FirstVertex_s(e)) - 1
            v1 = vmap.FindIndex(TopExp.LastVertex_s(e)) - 1
            if _d2(P[nodes[0]], P[v1]) < _d2(P[nodes[0]], P[v0]):
                v0, v1 = v1, v0
            pa += [nodes[0], nodes[-1]]
            pb += [v0, v1]
            ref = first.setdefault(emap.FindIndex(e), nodes)
            if ref is not nodes and len(ref) == len(nodes):
                if len(ref) > 2 and _d2(P[nodes[1]], P[ref[-2]]) < _d2(P[nodes[1]], P[ref[1]]):
                    ref = ref[::-1]
                pa += nodes
                pb += ref
        rev = face.Orientation() == TopAbs_REVERSED
        for i in range(1, tri.NbTriangles() + 1):
            a, b, c = tri.Triangle(i).Get()
            T.append((base + a, base + c, base + b) if rev else (base + a, base + b, base + c))
    P = np.array(P, float)
    n = len(P)
    g = coo_matrix((np.ones(len(pa)), (pa, pb)), shape=(n, n))
    _, lab = connected_components(g, directed=False)
    rep = np.full(lab.max() + 1, n)
    np.minimum.at(rep, lab, np.arange(n))
    return P[rep], lab[np.array(T, np.int64)]


def _merge_same(V, T):

    q = np.round(V.astype(np.float32).astype(np.float64) * 1e8)
    _, first, inv = np.unique(q, axis=0, return_index=True, return_inverse=True)
    return V[first], inv.reshape(-1)[T]


def _cancel_pairs(T):

    key = np.sort(T, axis=1)
    _, first, inv, cnt = np.unique(key, axis=0, return_index=True, return_inverse=True,
                                   return_counts=True)
    if (cnt == 1).all():
        return T
    return T[np.sort(first[cnt % 2 == 1])]


def _edge_use(T):

    h = T[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2)
    _, inv, cnt = np.unique(np.sort(h, axis=1), axis=0, return_inverse=True, return_counts=True)
    inv = inv.reshape(-1)
    s = np.zeros(len(cnt), int)
    np.add.at(s, inv, np.where(h[:, 0] < h[:, 1], 1, -1))
    fold = (cnt == 2) & (s != 0)
    return cnt[inv].reshape(-1, 3), fold[inv].reshape(-1, 3), h


def _ear_fill(V, L, edges):

    import heapq
    k = len(L)
    prv = [(i - 1) % k for i in range(k)]
    nxt = [(i + 1) % k for i in range(k)]
    alive = [True] * k
    ver = [0] * k
    P = V[L]

    def push(i):
        d = float(np.sum((P[prv[i]] - P[nxt[i]]) ** 2))
        heapq.heappush(heap, (d, ver[i], i))

    heap = []
    for i in range(k):
        push(i)
    tris, left = [], k
    while left > 3 and heap:
        _, v, i = heapq.heappop(heap)
        if not alive[i] or v != ver[i]:
            continue
        a, c = L[prv[i]], L[nxt[i]]
        e = (a, c) if a < c else (c, a)
        if e in edges:
            continue
        tris.append((c, L[i], a))
        edges.add(e)
        alive[i] = False
        p, n = prv[i], nxt[i]
        nxt[p], prv[n] = n, p
        left -= 1
        for j in (p, n):
            ver[j] += 1
            push(j)
    i = next(j for j in range(k) if alive[j])
    rest = [L[i]]
    j = nxt[i]
    while j != i:
        rest.append(L[j])
        j = nxt[j]
    if len(rest) == 3:
        tris.append((rest[2], rest[1], rest[0]))
        return tris, []
    return tris, rest


def _fill_holes(V, T):

    use, _, h = _edge_use(T)
    hb = h[use.reshape(-1) == 1]
    directed = set(map(tuple, hb.tolist()))
    adj = {}
    for a, b in hb.tolist():
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    loops = []
    while adj:
        path = [next(iter(adj))]
        pos = {path[0]: 0}
        while path[-1] in adj:
            cur = path[-1]
            b = adj[cur].pop()
            adj[b].remove(cur)
            for v in (cur, b):
                if not adj[v]:
                    del adj[v]
            if b in pos:
                j = pos[b]
                loops.append(path[j:])
                for v in path[j + 1:]:
                    del pos[v]
                path = path[:j + 1]
            else:
                pos[b] = len(path)
                path.append(b)

    loops = [L for L in loops if len(L) >= 3]
    lv = np.unique(np.concatenate(loops)) if loops else np.zeros(0, int)
    near = T[np.isin(T, lv).any(axis=1)]
    edges = set(map(tuple, np.sort(near[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1).tolist()))
    newV, newT = [], []
    for L in loops:
        k = len(L)
        fwd = sum((L[i], L[(i + 1) % k]) in directed for i in range(k))
        if 2 * fwd < k:
            L = L[::-1]
        tris, rest = _ear_fill(V, L, edges)
        newT += tris
        if rest:
            c = len(V) + len(newV)
            newV.append(V[rest].mean(axis=0))
            newT += [(rest[(i + 1) % len(rest)], rest[i], c) for i in range(len(rest))]
    if newV:
        V = np.vstack([V, np.array(newV)])
    if newT:
        T = np.vstack([T, np.array(newT, T.dtype)])
    return V, T, len(loops)


def _close_mesh(V, T, rounds=6):

    rep = {"degenerados": 0, "anulados": 0, "no_variedad": 0, "plegados": 0, "agujeros": 0}
    for _ in range(rounds):
        V, T = _merge_same(V, T)
        ok = (T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 2] != T[:, 0])
        rep["degenerados"] += int((~ok).sum())
        n0 = int(ok.sum())
        T = _cancel_pairs(T[ok])
        rep["anulados"] += n0 - len(T)
        use, fold, _ = _edge_use(T)
        nm, fo = (use > 2).any(axis=1), fold.any(axis=1)
        if (use == 2).all() and not fo.any():
            return V, T, True, rep
        rep["no_variedad"] += int(nm.sum())
        rep["plegados"] += int((fo & ~nm).sum())
        T = T[~(nm | fo)]
        V, T, nl = _fill_holes(V, T)
        rep["agujeros"] += nl
    V, T = _merge_same(V, T)
    use, _, _ = _edge_use(T)
    return V, T, bool((use == 2).all()), rep


def step_to_stl(step_path, stl_path, deflection=0.02, angle=0.2):

    import trimesh
    from OCP.STEPControl import STEPControl_Reader
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.IMeshTools import IMeshTools_Parameters
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from OCP.TopLoc import TopLoc_Location
    r = STEPControl_Reader()
    r.ReadFile(step_path)
    r.TransferRoots()
    shape = r.OneShape()
    BRepMesh_IncrementalMesh(shape, deflection, False, angle, True)

    nfail = 0
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        f = TopoDS.Face_s(exp.Current())
        exp.Next()
        if BRep_Tool.Triangulation_s(f, TopLoc_Location()) is None:
            for k in (1.0, 1.5, 2.5, 5.0, 10.0):
                p = IMeshTools_Parameters()
                p.Deflection, p.Angle = deflection * k, min(angle * k, 1.0)
                p.Relative, p.InParallel, p.AllowQualityDecrease = False, False, True
                BRepMesh_IncrementalMesh(f, p)
                if BRep_Tool.Triangulation_s(f, TopLoc_Location()) is not None:
                    break
            else:
                nfail += 1
    V, T = _tess_welded(shape)
    V, T, closed, rep = _close_mesh(V, T)
    if nfail:
        rep["caras_sin_teselar"] = nfail
    if any(rep.values()):
        print(f"  [stl] arreglos del teselado: {rep}  estanca={closed}")
    m = trimesh.Trimesh(V, T, process=False)
    m.remove_unreferenced_vertices()
    if closed and not m.is_winding_consistent:
        m.fix_normals(multibody=True)
    if closed:

        comp = trimesh.graph.connected_components(m.face_adjacency, nodes=np.arange(len(m.faces)))
        if len(comp) > 1:
            t = m.triangles
            vol = np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])) / 6.0
            cv = np.array([vol[c].sum() for c in comp])
            keep = np.abs(cv) > 1e-7 * np.abs(cv).max()
            if not keep.all():
                m.update_faces(np.isin(np.arange(len(m.faces)), np.concatenate(
                    [c for c, k in zip(comp, keep) if k])))
                m.remove_unreferenced_vertices()
        if m.volume < 0:
            m.invert()
    m.export(stl_path)
    return len(m.faces), closed


def _write_step(shape, out_path):
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    status = writer.Write(out_path)
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEPControl_Writer.Write status={status}")

if __name__ == "__main__":
    import sys
    from meshfit_detect import detect
    stl = sys.argv[1] if len(sys.argv) > 1 else r"pieza.stl"
    out = sys.argv[2] if len(sys.argv) > 2 else r"pieza.step"
    res, mesh = detect(stl)
    n = export_step(res, mesh, out)
    print(f"STEP escrito: {out}  ({n} caras recortadas)")
