"""
MeshFit — exportación STEP con OpenCascade (OCP / cadquery-ocp).

A diferencia del generador JS, aquí el kernel CAD construye las superficies analíticas y
las **recorta a su trozo real** (rango paramétrico de los puntos de la región): un redondeo
de canto sale como medio cilindro / cuarto de toro, no como una superficie completa.
"""
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
    """Rango angular ocupado por los puntos (maneja el wrap; 0..2π si cubren casi todo)."""
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
    """Bucles de borde (índices de vértice) de un conjunto de triángulos.

    Una arista es de borde si pertenece a UNA sola cara de la región. Las
    aristas de borde se encadenan en bucles cerrados. Devuelve la lista de
    bucles (cada uno una lista ordenada de índices de vértice)."""
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
    """Área con signo del polígono (u,v): >0 = antihorario."""
    return 0.5 * float(np.sum(u * np.roll(v, -1) - np.roll(u, -1) * v))


def _offset_poly_2d(uv, d):
    """Offset (mitra limitada) de un polígono 2D: d>0 amplía hacia FUERA. Espejo de
    offsetPoly2D del visor (misma matemática -> el STEP coincide con lo que se ve)."""
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
        k = min(2.0 / bl, 4.0)              # límite de mitra en esquinas agudas
        out[i] = p1 + (b / bl) * k * d
    return out


def _offset_poly_2d_aniso(uv, d4, bx, by, gu, gv):
    """Offset POR LADO del polígono 2D: d4 = [u+, u−, v+, v−] mm en los EJES DEL VISOR
    (gu, gv en 3D). El polígono está en el marco 2D local (bx, by en 3D) del exportador,
    que NO es el del visor: la normal exterior de cada arista se pasa a 3D y se proyecta
    sobre gu/gv para repartir la distancia. Vértices nuevos = intersección de las rectas
    desplazadas de sus dos aristas (mitra limitada). Espejo de offsetPoly2DAniso del visor."""
    uv = np.asarray(uv, float)
    n = len(uv)
    sgn = 1.0 if _signed_area_2d(uv[:, 0], uv[:, 1]) >= 0 else -1.0
    T = np.empty((n, 2)); D = np.empty(n); P = np.empty((n, 2))
    for i in range(n):
        t = uv[(i + 1) % n] - uv[i]
        l = float(np.hypot(*t)) or 1.0
        t = t / l
        no = np.array([sgn * t[1], -sgn * t[0]])
        n3 = no[0] * bx + no[1] * by            # normal exterior de la arista, en 3D
        cu, cv = float(n3 @ gu), float(n3 @ gv)  # componentes en los ejes del visor
        dist = (max(cu, 0) * d4[0] + max(-cu, 0) * d4[1]
                + max(cv, 0) * d4[2] + max(-cv, 0) * d4[3])
        T[i] = t; D[i] = dist
        P[i] = uv[i] + no * dist                # punto de la recta desplazada de la arista i
    out = np.empty_like(uv)
    for i in range(n):
        ip = (i - 1) % n                        # arista anterior (termina en el vértice i)
        cross = T[ip][0] * T[i][1] - T[ip][1] * T[i][0]
        if abs(cross) < 1e-9:                   # aristas paralelas: desplazar por la arista i
            no = np.array([sgn * T[i][1], -sgn * T[i][0]])
            v = uv[i] + no * D[i]
        else:
            s = ((P[i][0] - P[ip][0]) * T[i][1] - (P[i][1] - P[ip][1]) * T[i][0]) / cross
            v = P[ip] + T[ip] * s
        dv = v - uv[i]
        lim = 4.0 * max(D[ip], D[i], 1e-12)     # límite de mitra en esquinas agudas
        dl = float(np.hypot(*dv))
        out[i] = uv[i] + dv / dl * lim if dl > lim else v
    return out


def _ext2(prim, key):
    """Par (a, b) de ampliación ◆ del visor (tiradores), o None si no la hay."""
    v = prim.get(key)
    if not v:
        return None
    a, b = float(v[0]), float(v[1])
    return (a, b) if (abs(a) > 1e-9 or abs(b) > 1e-9) else None


def _face_plane(prim, mesh, face_idx):
    """Plano recortado a su CONTORNO real (polígono de borde de la región),
    no a un rectángulo. Así una tapa redondeada no asoma por las esquinas y un
    lateral se corta justo en la tangente del fillet. Soporta agujeros.

    ORIENTACIÓN: `_boundary_loops` encadena aristas sin dirección, así que cada bucle
    sale con sentido aleatorio. OCC exige exterior ANTIHORARIO y agujeros HORARIOS
    (respecto a la normal del plano); si el agujero sale antihorario, en vez de
    restarse se SUMA (visto en 'Original (1) (2)': anillo de 18.5 mm² exportaba
    50.2 = exterior + agujero). Se orienta cada bucle por su área con signo."""
    verts = mesh.vertices
    n = np.asarray(prim["normal"], float); n /= np.linalg.norm(n)
    x, y = _perp(n)
    o = np.asarray(prim["point"], float)
    loops = _boundary_loops(mesh, face_idx)
    if not loops:
        return None

    def to_2d(loop):
        d = verts[loop] - o
        return np.column_stack([d @ x, d @ y])   # (u,v) sobre el plano = proyección

    uv_loops = [to_2d(l) for l in loops]
    uv_loops.sort(key=lambda uv: abs(_signed_area_2d(uv[:, 0], uv[:, 1])), reverse=True)

    grow = prim.get("grow") or 0.0               # ampliación ◆ del visor: offset del exterior
    if isinstance(grow, (list, tuple)):          # por LADO: [u+, u−, v+, v−] + ejes del visor
        d4 = [max(0.0, float(v)) for v in grow]
        if max(d4) > 1e-9:
            gu = np.asarray(prim["gu"], float); gu /= np.linalg.norm(gu)
            gv = np.asarray(prim["gv"], float); gv /= np.linalg.norm(gv)
            uv_loops[0] = _offset_poly_2d_aniso(uv_loops[0], d4, x, y, gu, gv)
    elif float(grow) > 1e-9:                     # uniforme (formato antiguo)
        uv_loops[0] = _offset_poly_2d(uv_loops[0], float(grow))

    def make_wire(uv, ccw):
        if (_signed_area_2d(uv[:, 0], uv[:, 1]) > 0) != ccw:
            uv = uv[::-1]
        poly = BRepBuilderAPI_MakePolygon()
        for q in uv:
            p = o + x * float(q[0]) + y * float(q[1])   # (u,v) -> 3D sobre el plano ajustado
            poly.Add(gp_Pnt(float(p[0]), float(p[1]), float(p[2])))
        poly.Close()
        return poly.Wire()

    mk = BRepBuilderAPI_MakeFace(make_wire(uv_loops[0], True), True)   # exterior antihorario
    for hole in uv_loops[1:]:                                          # agujeros horarios
        if abs(_signed_area_2d(hole[:, 0], hole[:, 1])) > 1e-9:
            mk.Add(make_wire(hole, False))
    return mk.Face()


def _unwrap(vals, period=2 * np.pi):
    """Hace continua una secuencia de ángulos sumando/restando el periodo, para que un
    contorno que cruza la costura ±π no dé un polígono UV degenerado."""
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
    """Recorta una superficie analítica (cilindro/cono/esfera/toro) a su CONTORNO real
    en el espacio de parámetros, igual que `_face_plane` hace con los planos y
    `_trim_nurbs` con las NURBS. `to_uv(P)` da los parámetros (u,v) de un punto 3D.
    Devuelve la cara recortada o None si falla (el llamador cae al recorte rectangular)."""
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
        # misma regla que _face_plane: exterior antihorario, agujeros horarios (en UV)
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
    """Cara recortada al CASCO CONVEXO de los puntos (u,v) dados (polígono simple ->
    wire siempre válido). Fallback para primitivas curvas cuando el contorno exacto
    sale inválido: mucho más ceñido que el rectángulo paramétrico completo."""
    from scipy.spatial import ConvexHull
    hull = ConvexHull(np.asarray(uvs, float))
    pts = [uvs[i] for i in hull.vertices]              # antihorario garantizado
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
    """Recorta `rectface` (cara con el rango paramétrico rectangular, siempre válida) a su
    contorno real. Si el recorte exacto sale inválido, prueba el CASCO CONVEXO en UV
    (ceñido al soporte real; evita que una banda parcial salga barriendo el rectángulo
    entero, visto en el cilindro grande del Cargador: 2.45x su área de malla). Si también
    falla, se queda con el rectángulo (no empeora)."""
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
        if uperiodic:                                  # desenrollar el ángulo al rango del rect
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
        # Ampliación ◆ del visor: la superficie estirada es la banda paramétrica limpia
        # (rango angular × axial extendido), sin recorte al contorno de la malla — el
        # contorno ya no cubre la zona añadida.
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
    o = np.asarray(prim["origin"], float)        # punto del eje, radio = r en t=0 del fit
    half = float(prim["half_angle"])
    r_ref = float(prim["b"])                       # radio de referencia en 'o'
    pts = mesh.vertices[np.unique(mesh.faces[face_idx].ravel())].astype(float)
    d = pts - o
    ang = np.arctan2(d @ y, d @ x)
    u0, u1 = _ang_range(ang)
    v = (d @ axis) / np.cos(half)                  # parámetro a lo largo de la generatriz
    cone = gp_Cone(_ax3(o, axis, x), half, max(r_ref, 1e-4))
    ext, ang_ext = _ext2(prim, "ext"), _ext2(prim, "ang_ext")
    if ext or ang_ext:
        # Ampliación ◆ del visor: e0/e1 vienen en mm A LO LARGO DEL EJE -> pasar a
        # generatriz (v = t/cos). Banda paramétrica limpia, sin pasar del ápice (radio>=0).
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
    ang = np.arctan2(d @ y, d @ x)                # ángulo mayor (u)
    rho = np.sqrt((d @ x) ** 2 + (d @ y) ** 2) - R
    vang = np.arctan2(d @ axis, rho)              # ángulo del tubo (v)
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
    """Ajusta una región freeform como superficie B-spline (camino AUTOMÁTICO/escaneo).
    Las NURBS MANUALES (parches pintados en el visor) van por `_face_manual_nurbs`,
    que reutiliza el ajuste del visor (`meshfit_nurbs.fit_mesh_region`).

    - `deg_max`: grado máximo (8: mejor ajuste en escaneos suaves; acotado a bicúbica
      cuando la rejilla es pequeña, ver abajo).
    - `interp`: relleno de la rejilla (cubic para escaneos suaves).
    - `enforce_area`: descarta el parche cuando la cara sale >3x el área de malla
      (región plegada, geometría basura de escaneo).

    PointsToBSplineSurface exige una REJILLA de puntos, pero los vértices de una
    región de malla están dispersos. Se proyecta la región a su plano de mejor
    ajuste (u,v), se remuestrea una rejilla regular interpolando la altura sobre
    ese plano (scipy.griddata) y se ajusta la B-spline a esa rejilla. Vale para
    regiones tipo 'grafo' sobre el plano (no plegadas), que es el caso de las
    superficies orgánicas suaves. Devuelve None si no se puede ajustar."""
    from scipy.interpolate import griddata
    from meshfit_nurbs import grid_from_smooth
    verts = mesh.vertices
    vidx = np.unique(mesh.faces[np.asarray(face_idx)].ravel())
    pts = verts[vidx].astype(float)
    if len(pts) < 16:
        return None
    if adaptive:
        # Rejilla de control ADAPTATIVA (camino automático): los parches grandes llevan
        # más puntos de control para no perder detalle; los pequeños se quedan en el
        # tamaño base (suelo = nu, normalmente 14, así no hay regresión) y se acota arriba
        # (techo 30) para que OCP no oscile. ~√(nº de puntos) puntos de control por lado.
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
    GU, GV = np.meshgrid(us, vs)                     # forma (nv, nu)
    H = griddata((u, v), h, (GU, GV), method=interp)
    if np.isnan(H).any():                            # fuera del casco convexo -> vecino más cercano
        Hn = griddata((u, v), h, (GU, GV), method="nearest")
        H = np.where(np.isnan(H), Hn, H)
    # Guarda anti-explosión (sobre el CAMPO DE ALTURAS, antes de construir nada):
    # si la región no es un grafo sobre su plano (se pliega), la interpolación cúbica
    # extrapola fuera del casco y H se dispara -> la B-spline revienta en una "lenteja"
    # gigante. La guarda de área NO lo pilla cuando la superficie sale FINA (área pequeña,
    # bbox enorme). Aquí se compara la altura ajustada con la curvatura REAL de la región
    # (h.ptp): un buen ajuste la reproduce; uno explotado la multiplica por mucho. El
    # camino manual (interp="linear", no extrapola) nunca la dispara -> no le afecta.
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
    # Parametrización ISOPARAMÉTRICA (uniforme): así el mapa lineal plano->UV del recorte
    # es EXACTO (la rejilla us/vs es uniforme) y el contorno UV no se auto-interseca, ni
    # en parches alabeados. Con el default (chord-length) el recorte fallaba ahí.
    # Grado acotado por el tamaño de la rejilla: con rejillas pequeñas (≤16) el grado
    # alto OSCILA (los puntos de control se disparan -> láminas/banderas de metros);
    # bicúbica es la receta estable (la misma que usa el visor). El grado 8 solo aporta
    # en parches grandes de escaneo con rejilla densa.
    deg = int(deg_max) if min(nu, nv) > 16 else min(int(deg_max), 3)
    surf = GeomAPI_PointsToBSplineSurface(arr, Approx_IsoParametric, 3, deg, GeomAbs_C2, 1e-3).Surface()
    rect = BRepBuilderAPI_MakeFace(surf, 1e-6).Face()   # fallback: rectángulo uv sin recortar
    try:
        trimmed = _trim_nurbs(mesh, face_idx, surf, c, x, y, umin, umax, vmin, vmax)
    except Exception as e:
        print(f"  [nurbs sin recortar] {e}")
        trimmed = None
    # Solo se usa la cara recortada si es VÁLIDA. En sub-parches alabeados (escaneos)
    # el wire UV puede auto-intersecarse y dejar caras-astilla/negativas al coser: en
    # ese caso se cae al CASCO CONVEXO de los datos (válido y ceñido al soporte real)
    # y, si también falla, al rectángulo uv completo (siempre limpio, pero holgado).
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
    # Guarda de validez: si la región se pliega (no es un grafo sobre su plano), la
    # interpolación de altura se dispara y la B-spline explota. Se rechaza comparando
    # el área de la cara con el área real de la malla (un escaneo plegado se descarta
    # en vez de exportar geometría basura). Esas regiones necesitan trocearse (futuro).
    if enforce_area:
        mesh_area = float(mesh.area_faces[np.asarray(face_idx)].sum())
        g = GProp_GProps(); BRepGProp.SurfaceProperties_s(face, g)
        fa = g.Mass()
        if not np.isfinite(fa) or fa > 3.0 * mesh_area:
            print(f"  [nurbs descartado: area {fa:.0f} vs malla {mesh_area:.0f} mm2 -> region plegada]")
            return None
    return face


def _hull_trim(surf, u, v, umin, umax, vmin, vmax):
    """Recorte de una NURBS al CASCO CONVEXO de sus datos (u,v). Fallback intermedio
    entre el contorno exacto (puede salir inválido en parches alabeados) y el rectángulo
    UV completo (incluye las esquinas EXTRAPOLADAS por griddata, que sobresalen de la
    pieza). El casco es siempre un polígono simple -> wire válido, y acota la cara al
    soporte real de los datos."""
    from scipy.spatial import ConvexHull
    pts2 = np.column_stack([u, v])
    hull = ConvexHull(pts2)
    U1, U2, V1, V2 = surf.Bounds()
    du = (umax - umin) or 1.0
    dv = (vmax - vmin) or 1.0
    uvs = []
    for i in hull.vertices:                      # scipy: antihorario garantizado
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
    """Recorta la superficie NURBS a su contorno real. Mapea el polígono de borde
    de la región (en coords de plano u,v) a los parámetros (U,V) de la superficie
    con un mapa lineal — sin proyectar punto a punto, así el contorno UV es un
    polígono simple sin auto-intersecciones (evita las caras-astilla del intento
    por proyección)."""
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
    # exterior ANTIHORARIO en UV (si va horario, la cara puede salir como el complemento)
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
    """Última red: una cara plana por TRIÁNGULO (la geometría EXACTA de la malla).
    Para regiones freeform pequeñas donde la NURBS no sale (quad alabeado, pliegue,
    lámina que se dispara): mejor facetas exactas que un agujero en el STEP."""
    out = []
    for tri in mesh.faces[np.asarray(face_idx)]:
        poly = BRepBuilderAPI_MakePolygon()
        for vi in tri:
            p = mesh.vertices[int(vi)].astype(float)
            poly.Add(gp_Pnt(float(p[0]), float(p[1]), float(p[2])))
        poly.Close()
        out.append(BRepBuilderAPI_MakeFace(poly.Wire(), True).Face())
    return out


# Máximo de caras para el fallback de facetas: por debajo, un trozo freeform que no
# admite NURBS se exporta como triángulos exactos en vez de dejar agujero. Las hojas
# de escaneo (min_faces=80 -> hojas de 80+) quedan fuera para no inflar el STEP.
FACET_MAX = 60


def _nurbs_faces(mesh, face_idx, depth=0, max_depth=7, min_faces=80, max_fit=4000, deg_max=8):
    """Devuelve una LISTA de caras NURBS para una región freeform.

    El ajuste height-field solo vale si la región es un GRAFO sobre su plano. Si
    una región se pliega (escaneo), `_face_nurbs` la descarta (guarda de área). En
    ese caso se trocea: se bisecta por el eje más largo de los centroides y se
    recursa en cada mitad, hasta que cada trozo sea casi-grafo (pasa la guarda) o
    sea demasiado pequeño/profundo. Así un escaneo orgánico se cubre con varios
    parches NURBS válidos en vez de una sola superficie explotada.

    Optimización: en regiones grandes (> max_fit caras) ni se intenta el ajuste
    (es caro y se descartaría igual por plegada) — se bisecta directo. Solo se
    ajustan las hojas pequeñas, que es donde el height-field tiene sentido.

    `min_faces` conviene pasarlo proporcional a la región de partida (ver el llamador
    en `export_step`): una banda de blend de CAD de ~200 caras que envuelve >180° solo
    ajusta troceada en cuartos (~50 caras) — con el mínimo fijo de 80 la bisección se
    rendía antes de llegar y la región quedaba SIN exportar (agujero en el STEP)."""
    face_idx = np.asarray(face_idx)
    can_split = depth < max_depth and len(face_idx) >= 2 * min_faces
    if len(face_idx) <= max_fit:
        face = _face_nurbs(mesh, face_idx, deg_max=deg_max, adaptive=True)
        if face is not None:
            # Control de calidad del parche:
            #  - ÁREA >1.5× la malla = superficie que ondula/bombea dentro del contorno
            #    -> trocear más; si ya no se puede, se acepta (mejor holgado que agujero).
            #  - BBOX >1.6× la diagonal de la región = lámina fina que se dispara fuera
            #    de la pieza (área pequeña, extensión enorme: la guarda de área no la ve)
            #    -> trocear más; si ya no se puede, DESCARTAR (una bandera de 50 mm es
            #    peor que un hueco pequeño).
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
        # sin margen para trocear y sin NURBS válida: facetas exactas si el trozo es
        # pequeño (mejor que agujero); los trozos grandes de escaneo se abandonan.
        if len(face_idx) <= FACET_MAX:
            return _facet_faces(mesh, face_idx)
        return []
    fn = mesh.face_normals[face_idx]
    nbar = fn.mean(axis=0)
    if np.linalg.norm(nbar) < 0.5:
        # banda ENVUELTA (normales abiertas más de ~±60°): el height-field nunca ajusta
        # y la bisección espacial puede dejar mitades igual de envueltas. Se corta por
        # SECTORES ANGULARES (mediana de la proyección de las normales sobre su primera
        # componente principal) -> cada mitad abarca la mitad del arco y se "desenrolla".
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
    """Cara STEP de una entidad ROSCA (helicoide): mismo ajuste que el visor
    (`meshfit_helix.fit_helix` es determinista). Si el parche envuelve la vuelta
    completa (o es la cinta multi-vuelta típica de 'Crecer'), el rectángulo (θ,z)
    ES la forma correcta: la banda de rosca entera. En parches parciales se
    recorta al contorno como las demás superficies."""
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
    """Cara de NURBS manual AMPLIADA ◆: contorno exterior de la región offseteado
    `grow` mm hacia FUERA (métrico: en cilíndrico θ se escala por el radio medio),
    clampado al dominio extendido del ajuste y mapeado linealmente a los parámetros
    de la superficie. Los agujeros del parche se conservan tal cual (la ampliación
    es solo del borde exterior). Espejo del recorte dilatado del visor."""
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
    grown[:, 0] = np.clip(grown[:, 0], info["u0"], info["u1"])   # la mitra no puede
    grown[:, 1] = np.clip(grown[:, 1], info["v0"], info["v1"])   # salirse del dominio
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
    """Cara STEP de una NURBS MANUAL (parche pintado): usa el MISMO ajuste que el visor
    (`meshfit_nurbs.fit_mesh_region`, con modo CILÍNDRICO automático para parches que
    envuelven, p.ej. una rosca pintada entera). Recorte: contorno exacto → casco
    convexo → rectángulo UV. En banda cilíndrica de vuelta completa el rectángulo ES
    la forma correcta (la banda ocupa todo (θ,z)). Con `grow` (ampliación ◆ del visor)
    el ajuste se extiende y el recorte usa el contorno OFFSETEADO (`_grown_nurbs_face`);
    si ese recorte falla, cae al rectángulo del dominio ampliado (nunca menos que el
    parche + la ampliación pedida). `grid`/`edits`: rejilla de control forzada y
    movimientos de polos del editor ✏️ — mismo ajuste determinista que el visor."""
    from meshfit_nurbs import fit_mesh_region, map_uv, apply_pole_edits, refine_poles
    region = np.asarray(region, int)
    grow = max(0.0, float(grow))
    info = fit_mesh_region(mesh, region, grid=(int(grid) if grid else None),
                           smooth=smooth, grow=grow)
    surf = info["surf"]
    if grid:                            # misma densificación determinista que el visor
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
        return rect                     # banda de vuelta completa (con grow: más larga en z)
    if grow > 1e-9:
        try:
            face = _grown_nurbs_face(info, surf, mesh, region, grow)
        except Exception as e:
            print(f"  [nurbs ampliada sin recorte] {e}")
            face = None
        if face is not None and BRepCheck_Analyzer(face).IsValid():
            return face
        return rect                     # dominio ampliado completo: nunca menos que lo pedido
    try:
        # sin desenrollado extra: en banda parcial no hay costura que cruzar y en
        # plano tampoco (map_uv ya devuelve coordenadas continuas)
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


# info del último export (sólido o no), para el informe de la API
LAST_INFO = {"solid": False}


_FACE = {"plane": _face_plane, "cylinder": _face_cylinder, "cone": _face_cone,
         "sphere": _face_sphere, "torus": _face_torus}


def export_step(result, mesh, out_path, organic=True, extra_nurbs_regions=None,
                extra_nurbs_smooth=None, extra_helix_regions=None, extra_nurbs_grow=None,
                extra_nurbs_grid=None, extra_nurbs_edits=None, solid=True, organic_smooth=0.0,
                ajuste_ia=False, require_solid=False, precision_reparacion=False,
                regiones_bloqueadas=None, preservar_contactos=False, cavidades_verificadas=False):
    """Construye una cara recortada por primitiva (+ NURBS para regiones freeform si
    organic=True), las cose y escribe el STEP. Devuelve nº caras.

    `extra_nurbs_regions`: lista de listas de índices de cara — las NURBS que el usuario
    pintó a mano en el visor. Se exportan con el mismo motor que las automáticas
    (`_nurbs_faces`, recortadas a su contorno) y MANDAN sobre la detección automática:
    sus caras se quitan de las regiones freeform para no exportar la zona dos veces.
    `extra_nurbs_smooth`: suavizado (0..1) paralelo a cada región, para que la NURBS
    exportada tenga la misma rejilla de control que la que el usuario ve en el visor.
    `extra_nurbs_grow`: ampliación ◆ (mm) paralela a cada región (tiradores del visor).
    `extra_nurbs_grid`/`extra_nurbs_edits`: rejilla de control forzada (0 = auto) y
    movimientos de polos [[i,j,dx,dy,dz],...] del editor ✏️, paralelos a cada región.

    `solid=True`: intenta primero el SÓLIDO estanco (`meshfit_brep.build_solid`, aristas
    compartidas sacadas de la topología de la malla). Solo se usa si sale cerrado y válido
    y no hay entidades manuales (NURBS pintadas/roscas/ampliaciones, que van por el camino
    clásico); si no, cae al cosido de caras sueltas de siempre."""
    global LAST_INFO
    LAST_INFO = {"solid": False}
    # Ampliaciones ◆ (planos/cilindros/conos/NURBS estiradas fuera de la malla): un sólido
    # construido desde la topología de la malla no puede representarlas -> camino clásico.
    # NURBS pintadas y roscas SÍ entran: su superficie (la misma que ve el visor) se impone
    # a su región y queda bloqueada frente a la limpieza automática.
    grown = (any(p.get("ext") or p.get("ang_ext") or p.get("grow") for p in result["primitives"])
             or any(float(g or 0) > 1e-9 for g in (extra_nurbs_grow or [])))
    if solid and grown:
        LAST_INFO = {"solid": False, "reason": "ampliaciones"}
    if solid and not grown:
        try:
            from meshfit_brep import build_solid
            extra = _user_surfaces(mesh, extra_nurbs_regions, extra_nurbs_smooth,
                                   extra_nurbs_grid, extra_nurbs_edits, extra_helix_regions)
            if regiones_bloqueadas:
                extra=list(extra or [])+list(regiones_bloqueadas)
            shape, info = build_solid(result, mesh, extra_regions=extra,
                                      organic_smooth=organic_smooth, ajuste_ia=ajuste_ia,
                                      precision_reparacion=precision_reparacion,
                                      preservar_contactos=preservar_contactos,
                                      cavidades_verificadas=cavidades_verificadas)
            if shape is not None and info.get("solid") and info.get("valid"):
                LAST_INFO = info
                _write_step(shape, out_path)
                return info["faces"]
            print(f"  [brep] sin sólido válido ({info}); camino clásico")
        except Exception as e:
            print(f"  [brep] error {e}; camino clásico")
    # El conversor exige un sólido CAD verdadero: el camino clásico de caras
    # cosidas nunca cumple esa condición (LAST_INFO['solid'] queda en False).
    # No gastar minutos en un resultado que se descartará incondicionalmente.
    if require_solid:
        raise ValueError("El motor B-Rep no ha reconstruido un sólido CAD válido.")
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
                # mínimo adaptativo: en regiones pequeñas (bandas de blend de CAD) se
                # permite trocear hasta ~1/8 de la región; en escaneos grandes sigue 80
                mf = max(24, min(80, len(region) // 8))
                for face in _nurbs_faces(mesh, region, min_faces=mf):
                    sew.Add(face); n_ok += 1
            except Exception as e:
                print(f"  [skip nurbs] {e}")

    for region in helices:                              # entidades ROSCA (helicoide)
        try:
            face = _face_helix(mesh, region)
            if face is not None:
                sew.Add(face); n_ok += 1
        except Exception as e:
            print(f"  [skip helicoide] {e}")

    for region, smooth, growv, gridv, editsv in manual:  # NURBS pintadas a mano en el visor
        try:
            # MISMO ajuste que el visor (fit_mesh_region: plano o cilíndrico automático)
            # y sin guarda de área: el parche que el usuario ve siempre se exporta.
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


def _user_surfaces(mesh, nurbs_regions, nurbs_smooth, nurbs_grid, nurbs_edits, helix_regions):
    """[(caras, Geom_Surface)] de las entidades del usuario con el MISMO ajuste que el
    visor (NURBS manual: rejilla/suavizado/polos editados; rosca: helicoide)."""
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
            info, model = fit_helix(mesh, np.asarray(r, int))
            out.append((np.asarray(r, int), helix_surface(info, model)))
        except Exception as e:
            print(f"  [rosca sin superficie: {e}]")
    return out


def step_to_stl(step_path, stl_path, deflection=0.01, angle=0.1):
    """Malla STL (binaria) del sólido de un STEP, para IMPRIMIR o editar como malla.
    Se relee el STEP en vez de teselar el sólido en memoria: OCC mide/tesela mal en
    memoria alguna cara periódica cuya costura cruza el origen (el volumen salía un 15 %
    bajo) y el STEP releído es justo lo que el usuario abrirá en su CAD. Una sola
    triangulación del sólido -> aristas compartidas -> malla estanca.
    Devuelve (nº triángulos, estanca)."""
    import trimesh
    from OCP.STEPControl import STEPControl_Reader
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopoDS import TopoDS
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location
    r = STEPControl_Reader()
    r.ReadFile(step_path)
    r.TransferRoots()
    shape = r.OneShape()
    BRepMesh_IncrementalMesh(shape, deflection, False, angle, True)
    V, F, off = [], [], 0
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face_s(exp.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            tr = loc.Transformation()
            for i in range(1, tri.NbNodes() + 1):
                q = tri.Node(i).Transformed(tr)
                V.append((q.X(), q.Y(), q.Z()))
            rev = face.Orientation() == TopAbs_REVERSED
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                F.append((a - 1 + off, c - 1 + off, b - 1 + off) if rev else
                         (a - 1 + off, b - 1 + off, c - 1 + off))
            off += tri.NbNodes()
        exp.Next()
    m = trimesh.Trimesh(np.array(V), np.array(F), process=True)   # suelda los nodos de arista
    m.remove_unreferenced_vertices()
    m.export(stl_path)
    return len(m.faces), bool(m.is_watertight)


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
    stl = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\rcosme\Easyfit3d\_stl_test\cuerpo45.stl"
    out = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\rcosme\Easyfit3d\_stl_test\cuerpo45_ocp.step"
    res, mesh = detect(stl)
    n = export_step(res, mesh, out)
    print(f"STEP escrito: {out}  ({n} caras recortadas)")
