"""
MeshFit — ajuste de superficie NURBS (B-spline) a una región de la malla.

Dos parametrizaciones, elegidas automáticamente según el parche (`fit_mesh_region`):

- **Plano (campo de alturas)**: parche de una sola hoja (un bulto, una transición).
  Se proyecta sobre su plano PCA, se remuestrea en rejilla (scipy.griddata) y se
  ajusta una B-spline bicúbica C2 con OCP.
- **Cilíndrico (campo de radios)**: parche que ENVUELVE un eje (normales que abren
  más de ~±60°, p.ej. una rosca pintada alrededor del tornillo entero). Sobre un
  plano la altura sería MULTIVALUADA (cara de delante y de detrás) y el ajuste
  explotaba en púas; en cilíndricas ρ(θ,z) es única — una rosca ES un campo de
  radios. El eje sale de `meshfit_detect.fit_cylinder` (normales+áreas).

Robustez compartida: rejilla ANISÓTROPA (más puntos en el lado largo del parche),
tolerancia ADAPTATIVA al residuo del remuestreo, y reintentos anti-resonancia si el
spline oscila. La superficie se tesela para el visor y sirve para exportar STEP
(`meshfit_step._face_manual_nurbs` usa el MISMO ajuste vía `fit_mesh_region`).
"""
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
    """Centroide y base (U, V, N) de la región. N = dirección de menor varianza = normal."""
    c = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    U, V, N = vt[0], vt[1], vt[2]
    return c, U / np.linalg.norm(U), V / np.linalg.norm(V), N / np.linalg.norm(N)


def grid_from_smooth(n, smooth=0.0):
    """Resolución de la rejilla de control a partir del 'suavizado' (0..1).

    0 = máximo detalle (rejilla fina ~√n, la superficie sigue la malla); 1 = muy suave
    (rejilla 5×5, pocos puntos de control → superficie lisa que ignora los bultos).
    Mismo cálculo en el visor y en el export para que la NURBS exportada coincida
    con la que se ve en pantalla. Techo 40: parches MUY grandes ganan detalle."""
    gmax = int(np.clip(round(np.sqrt(max(n, 1))), 6, 40))
    smooth = float(np.clip(smooth, 0.0, 1.0))
    return int(max(5, round(gmax - smooth * (gmax - 5))))


def grid_aniso(n, du, dv, smooth=0.0, gmin=4, gmax=80):
    """Rejilla ANISÓTROPA: reparte el presupuesto de puntos de control según la forma
    del parche. Presupuesto total = grid_from_smooth(n)²; una rejilla cuadrada en un
    parche alargado 4:1 (una banda de rosca) desperdicia la mitad de los puntos en el
    lado corto y deja el largo sin resolución (aliasing). Devuelve (nu, nv)."""
    g = grid_from_smooth(n, smooth)
    r = np.sqrt(max(du, 1e-9) / max(dv, 1e-9))
    nu = int(np.clip(round(g * r), gmin, gmax))
    nv = int(np.clip(round(g * g / max(nu, 1)), gmin, gmax))
    return nu, nv


def resample_tol(gu, gv, H, uu, vv, hh, diag):
    """Tolerancia de aproximación ADAPTATIVA: el residuo del remuestreo (distancia de
    los datos reales a la rejilla interpolada) marca cuánta precisión SOPORTAN los
    datos. Pedir más (tolerancia fija fina) obliga al spline a perseguir el zigzag
    aliased y se pone a OSCILAR (visto en la rosca del tornillo M8). Con rejilla
    suficiente el residuo es ~0 y la tolerancia queda fina (parches suaves intactos)."""
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
    """Rango de 'alturas' de la superficie muestreada ns×ns; `hfun(P)` da la altura de
    un punto 3D (altura sobre el plano en modo plano, radio al eje en cilíndrico).
    Sirve para detectar OSCILACIÓN: si el spline resuena, su altura se dispara muy
    por encima del rango de los datos (fuera de los puntos donde se mide el residuo)."""
    u0, u1, v0, v1 = surf.Bounds()
    hmin, hmax = np.inf, -np.inf
    for uu in np.linspace(u0, u1, ns):
        for vv in np.linspace(v0, v1, ns):
            p = surf.Value(float(uu), float(vv))
            h = hfun(np.array([p.X(), p.Y(), p.Z()]))
            hmin, hmax = min(hmin, h), max(hmax, h)
    return hmax - hmin


def _radial_scatter(th, z, rho, nb_u=24, nb_v=8):
    """Dispersión del radio por celda (θ,z): mide si ρ(θ,z) es un campo UNIVALUADO
    con ese eje. Un eje bueno da poca dispersión por celda (solo el dentado de la
    rosca); un eje malo mezcla radios de zonas distintas en la misma celda."""
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
    """Eje robusto para el modo cilíndrico. El eje de `fit_cylinder` (por normales)
    falla en parches de ROSCA (los flancos inclinan las normales ±60° y el eje sale
    torcido): se prueban varios candidatos (normales + los 3 ejes PCA de los puntos),
    cada uno con su punto de eje por ajuste de círculo, y gana el que deje el campo
    de radios ρ(θ,z) más univaluado (`_radial_scatter`)."""
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
        q = float(c2[0]) * e1 + float(c2[1]) * e2      # punto en el eje candidato
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
    """Rango angular ocupado por los datos (maneja el wrap de ±π). Devuelve
    (u0, u1, completo): [0..2π] si cubren casi toda la vuelta."""
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
    """Núcleo del ajuste: malla + caras → dict con la superficie OCP y todo el mapeo.

    Detecta si el parche ENVUELVE (|media de normales| < 0.5 ≈ abren más de ±60°) y
    elige plano o cilíndrico. Claves devueltas: surf, mode ('plane'|'cyl'), frame,
    full (vuelta completa), u0/u1/v0/v1 (rango del DOMINIO: datos + grow), nu/nv/grid,
    tol3d, diag, rho_mean, pts (vértices del parche), hfun (altura de un punto 3D).

    `grow` (mm, tirador ◆ del visor): AMPLÍA el dominio de la rejilla más allá del
    parche — plano: ±grow en u y v; cilíndrico: ±grow en z y grow/ρ̄ radianes en θ
    (tope: una vuelta). Las celdas nuevas no tienen datos y el relleno ARMÓNICO las
    continúa con suavidad desde el borde -> la B-spline queda definida (y mansa) en
    la zona ampliada. El recorte decide luego cuánto de esa zona se enseña/exporta."""
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
        if grow > 1e-9:                            # ampliación ◆: extender el dominio
            v0 -= grow; v1 += grow
            if not full:
                dth = grow / max(rho_mean, 1e-6)
                u0 -= dth; u1 += dth
                over = (u1 - u0) - TWO_PI          # sin dar más de una vuelta
                if over > 0:
                    u0 += over / 2; u1 -= over / 2
        uu = u0 + np.mod(th - u0, TWO_PI)
        uu = np.clip(uu, u0, u1)
        du = (u1 - u0) * rho_mean                  # longitud de arco (para la anisotropía)
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
        if grow > 1e-9:                            # ampliación ◆: extender el dominio
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
        # padding periódico: continuidad del interpolado en la costura θ = u0 = u1-2π
        mgn = 0.15 * TWO_PI
        left = uu <= u0 + mgn
        right = uu >= u1 - mgn
        su = np.concatenate([uu, uu[left] + TWO_PI, uu[right] - TWO_PI])
        sv = np.concatenate([vv, vv[left], vv[right]])
        sh = np.concatenate([hh, hh[left], hh[right]])

    H = griddata((su, sv), sh, (GU, GV), method="linear")
    nan = np.isnan(H)                       # nodos fuera del casco convexo de los datos
    if nan.any():
        # Relleno ARMÓNICO de las celdas sin datos: la semilla es el vecino más
        # cercano, pero luego se relajan (difusión) SOLO las celdas rellenadas, con
        # las de datos fijas. El relleno 'nearest' a secas deja ESCALONES en parches
        # de cobertura dispersa (la cinta helicoidal de una rosca seleccionada con
        # 'Crecer': franjas diagonales con huecos) y el spline resonaba en púas.
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

    # Grado fijo CÚBICO (3,3): bicúbica C2 estable (grados altos oscilan en rejillas
    # pequeñas). Parametrización ISOPARAMÉTRICA: uniforme como nuestra rejilla → el
    # mapa lineal datos→UV del recorte/export es exacto. Reintentos anti-resonancia:
    # si el spline oscila (altura muestreada >> rango de los datos), tolerancia ×4.
    h_data = float(hh.max() - hh.min())
    surf = None
    err = None
    # el muestreo del vigilante debe seguir a la rejilla: una púa fina entre nodos
    # de un muestreo fijo 20×20 pasaba desapercibida (visto con la cinta de rosca)
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
    """(u, v) de un punto 3D en las coordenadas de DATOS del ajuste (coords de plano
    en modo plano; (θ desenrollado, z) en cilíndrico). El mapa a parámetros de la
    superficie es lineal (parametrización isoparamétrica sobre rejilla uniforme)."""
    if info["mode"] == "cyl":
        _, q, e1, e2, a = info["frame"]
        d = np.asarray(P, float) - q
        z = float(d @ a)
        r = d - z * a
        th = float(np.arctan2(r @ e2, r @ e1))
        u = info["u0"] + (th - info["u0"]) % TWO_PI
        if u > info["u1"]:                      # cae en el hueco (banda parcial): al extremo más cercano
            u = info["u1"] if (u - info["u1"]) < (info["u0"] + TWO_PI - u) else info["u0"]
        return u, z
    _, c, U, V, _N = info["frame"]
    d = np.asarray(P, float) - c
    return float(d @ U), float(d @ V)


def fit_bspline(pts, grid=None, tol3d=None, smooth=0.0):
    """(Legado, solo modo plano y sin malla.) Ajusta una B-spline a la nube `pts` como
    campo de alturas sobre su plano PCA. Preferir `fit_mesh_region` (elige plano o
    cilíndrico y devuelve el mapeo completo)."""
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
    """Evalúa la superficie en una rejilla nu×nv → (vertices N×3, triangles M×3)."""
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
    """Segmentos del contorno de la región (aristas usadas por UNA sola cara de la
    selección), en 3D. Devuelve (A, B): extremos de cada segmento, ambos (E,3)."""
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
    vid = np.asarray(bedges)                       # (E,2) índices de vértice
    return (mesh.vertices[vid[:, 0]].astype(float),
            mesh.vertices[vid[:, 1]].astype(float))


def _inside_polygon(pts_uv, A, B):
    """Punto-en-polígono por par-impar (ray casting horizontal) contra TODOS los
    segmentos del contorno — así maneja también los agujeros. pts_uv (M,2),
    A/B (E,2). Devuelve máscara booleana (M,) de los puntos dentro del contorno."""
    x = pts_uv[:, 0][:, None]; y = pts_uv[:, 1][:, None]      # (M,1)
    ax = A[:, 0][None, :]; ay = A[:, 1][None, :]              # (1,E)
    bx = B[:, 0][None, :]; by = B[:, 1][None, :]
    cond = (ay > y) != (by > y)                               # la arista cruza la horizontal de y
    t = (y - ay) / (by - ay + 1e-30)
    xint = ax + t * (bx - ax)
    crosses = cond & (xint > x)
    return (crosses.sum(axis=1) % 2) == 1


def _boundary_uv(info, mesh, faces):
    """Segmentos de contorno mapeados a las coords (u,v) del ajuste. En cilíndrico,
    el extremo B se lleva al periodo más cercano a A (continuidad del segmento) y en
    vuelta completa se añaden duplicados ±2π (la costura queda cubierta)."""
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
    """Densifica la red de CONTROL sin cambiar la forma (inserción de nudos, partiendo
    siempre el tramo más ancho por la mitad — determinista). La aproximación C2 puede
    dejar muy pocos polos (p. ej. 6×4): cada polo movería media superficie. Para el
    editor ✏️ hace falta una red del tamaño que pida el usuario, con efecto LOCAL."""
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
    """Mueve PUNTOS DE CONTROL de la B-spline ya ajustada: edits = [[i, j, dx, dy, dz], ...]
    con i/j 0-based sobre la rejilla de polos REAL de la superficie (no la de remuestreo).
    El ajuste es determinista → los mismos índices producen la misma superficie en el
    visor y en el export STEP. Índices fuera de rango se ignoran (p. ej. si cambió la
    rejilla y quedó un edit huérfano)."""
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
    """Rejilla de polos de la superficie: (lista [x,y,z] en orden i-mayor, nu, nv)."""
    nu, nv = surf.NbUPoles(), surf.NbVPoles()
    out = []
    for i in range(nu):
        for j in range(nv):
            p = surf.Pole(i + 1, j + 1)
            out.append([p.X(), p.Y(), p.Z()])
    return out, nu, nv


def _near_boundary(pts_uv, A, B, dist, info):
    """Máscara de puntos (u,v) a distancia MÉTRICA <= dist del contorno (segmentos A→B).
    Es la dilatación que agranda el recorte cuando la NURBS lleva ampliación ◆: se
    conserva lo de dentro del contorno Y el anillo de `dist` mm alrededor. En modo
    cilíndrico θ se escala por el radio medio para que la distancia sea en mm."""
    sx = info["rho_mean"] if info["mode"] == "cyl" else 1.0
    scale = np.array([sx, 1.0])
    P, Q = A * scale, B * scale
    seg = Q - P
    L = np.linalg.norm(seg, axis=1)
    step = max(dist / 2.0, 1e-6)
    samples = [P, Q]                       # muestrear cada segmento cada ~dist/2
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
    """Punto de entrada: malla trimesh + índices de cara → (dict para el frontend, surf OCP).

    `trim`: recorta el teselado al contorno real de la selección (par-impar en u,v), para
    que la NURBS del visor NO sobresalga del parche pintado (igual que el STEP exportado).
    `grow` (mm): ampliación ◆ — el dominio del ajuste se extiende (ver `fit_mesh_region`)
    y el recorte se DILATA: se conserva el interior del contorno más el anillo de grow mm.
    `edits`: movimientos de puntos de control [[i, j, dx, dy, dz], ...] (editor ✏️ del
    visor), aplicados tras el ajuste. El dict devuelto incluye la rejilla de polos
    (`poles`, `poles_nu`, `poles_nv`) ya con los edits aplicados, para dibujar la red.
    """
    faces = np.asarray(faces, int)
    grow = max(0.0, float(grow))
    info = fit_mesh_region(mesh, faces, grid=grid, smooth=smooth, grow=grow)
    surf = info["surf"]
    if grid:                            # rejilla pedida = tamaño de la red de control
        refine_poles(surf, int(grid), int(grid))
    apply_pole_edits(surf, edits)
    pts = info["pts"]
    # el teselado de dibujo escala con la rejilla de control (por lado): una rejilla
    # fina dibujada a 40×40 fijo perdería el detalle que acaba de ganar
    res_u = int(max(40, 2 * info["nu"]))
    res_v = int(max(40, 2 * info["nv"]))
    verts, tris = tessellate(surf, res_u, res_v)

    # Desviación: distancia de cada punto original a la superficie teselada (antes de
    # recortar). Con grow, la zona ampliada no cuenta: pts son solo los datos reales.
    dist, _ = cKDTree(verts).query(pts)
    rms, mx = float(np.sqrt((dist ** 2).mean())), float(dist.max())

    if trim:                                           # recorta los triángulos fuera del contorno
        A, B = _boundary_uv(info, mesh, faces)
        if A is not None:
            cen3 = verts[tris].mean(axis=1)            # centroide 3D de cada triángulo -> (u,v)
            cen_uv = np.array([map_uv(info, p) for p in cen3])
            if info["mode"] == "cyl":
                # el rayo del par-impar debe ir a lo largo de v (los bordes de una banda
                # que envuelve corren casi paralelos a u y el rayo en u degenera)
                keep = _inside_polygon(cen_uv[:, ::-1], A[:, ::-1], B[:, ::-1])
            else:
                keep = _inside_polygon(cen_uv, A, B)
            if grow > 1e-9:                            # dilatar el recorte con la ampliación
                keep |= _near_boundary(cen_uv, A, B, grow, info)
            if keep.sum() >= 4:                        # no recortar si quedaría casi vacío
                tris = tris[keep]

    poles, pnu, pnv = surface_poles(surf)
    data = {
        "vertices": verts.tolist(),
        "triangles": tris.tolist(),
        "rms": rms,
        "max": mx,
        "n_pts": int(len(pts)),
        "n_faces": int(len(faces)),
        "grid": info["grid"],          # "nu×nv" (rejilla anisótropa de remuestreo)
        "poles": poles,                # rejilla de PUNTOS DE CONTROL real (editor ✏️)
        "poles_nu": pnu, "poles_nv": pnv,
    }
    return data, surf


if __name__ == "__main__":
    import sys
    import trimesh

    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\rcosme\Easyfit3d\_stl_test\cuerpo45.stl"
    mesh = trimesh.load(path, force="mesh")
    mesh.merge_vertices()
    # Sin selección real: usa TODA la malla (solo humo de prueba del motor).
    faces = list(range(len(mesh.faces)))
    data, surf = fit_region(mesh, faces)
    print(f"NURBS sobre {data['n_pts']} puntos / {data['n_faces']} caras")
    print(f"  rejilla de control {data['grid']}")
    print(f"  teselada: {len(data['vertices'])} vértices, {len(data['triangles'])} triángulos")
    print(f"  RMS {data['rms']:.4f} mm · máx {data['max']:.4f} mm")
