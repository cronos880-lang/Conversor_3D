"""
MeshFit — primitiva HELICOIDE (rosca): perfil periódico barrido en hélice.

Una rosca es un campo de radios con estructura helicoidal: ρ(θ, z) = g(w) donde
w = (z − s·k·θ) mod P es la FASE (P = paso, k = P/2π, s = sentido ±1: rosca a
derechas/izquierdas) y g = perfil del diente (fondo-flanco-cresta-flanco). El ajuste:

  1. Eje robusto del parche (reutiliza `meshfit_nurbs._cyl_frame`).
  2. PASO y SENTIDO: se barren candidatos de P (grueso + refinado) y gana el que
     deje ρ más univaluado respecto a la fase (dispersión por celda de w).
  3. PERFIL g(w): mediana de ρ por celda de fase + spline cúbico PERIÓDICO.
  4. Superficie: rejilla (θ, z) evaluando el MODELO (puntos exactos, sin ruido)
     → B-spline bicúbica C2 con OCP. Se tesela para el visor (recortada al parche,
     mismo mecanismo que el modo cilíndrico de meshfit_nurbs) y sirve para STEP.

Parámetros de metrología que devuelve: paso, sentido, radio de cresta, radio de
fondo, diámetro medio, eje, y RMS del ajuste.
"""
import numpy as np
from scipy.spatial import cKDTree

from OCP.gp import gp_Pnt
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
from OCP.Approx import Approx_IsoParametric
from OCP.GeomAbs import GeomAbs_C2

from meshfit_nurbs import (_cyl_frame, _ang_span, _inside_polygon,
                           _boundary_segments_3d, tessellate, surf_h_range, TWO_PI)


def _phase_scatter(z, th, rho, P, sign, nbins=24):
    """Dispersión de ρ por celda de FASE w = (z − s·k·θ) mod P. Un (P, s) correcto
    alinea todos los dientes -> dispersión mínima (la señal para estimar el paso)."""
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
    """Estima (paso, sentido) barriendo candidatos: barrido grueso logarítmico y dos
    refinados alrededor del mejor. El paso debe caber al menos 1.5 veces en el parche."""
    zr = float(z.max() - z.min())
    if zr <= 0:
        raise ValueError("el parche no tiene extensión axial (no parece una rosca)")
    pmin = max(zr / 200.0, 0.05)
    pmax = zr / 1.5
    if pmax <= pmin:
        raise ValueError("el parche cubre menos de un paso y medio de rosca")
    best = None
    cands = np.geomspace(pmin, pmax, 120)
    for _ in range(3):                                   # grueso + 2 refinados
        for P in cands:
            for s in (1.0, -1.0):
                sc = _phase_scatter(z, th, rho, float(P), s)
                if best is None or sc < best[0]:
                    best = (sc, float(P), s)
        span = cands[1] / cands[0] if len(cands) > 1 else 1.05
        P0 = best[1]
        cands = np.linspace(P0 / span, P0 * span, 40)
    return best[1], best[2], best[0]


def _fit_profile(z, th, rho, P, sign, nbins=32):
    """Perfil del diente g(w): mediana de ρ por celda de fase + spline cúbico
    periódico. Devuelve (g, w_centros, rho_perfil)."""
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
    if not filled.all():                                # celdas vacías: interpolar circular
        idx = np.nonzero(filled)[0]
        allb = np.arange(nbins)
        prof = np.interp(allb, idx, prof[idx], period=nbins)
    wc = (np.arange(nbins) + 0.5) / nbins * P
    # spline periódico: repetir el primer punto al final con el mismo valor
    wx = np.append(wc, wc[0] + P)
    fy = np.append(prof, prof[0])
    g = CubicSpline(wx, fy, bc_type="periodic")
    return (lambda ww, _g=g, _P=P, _w0=wc[0]: _g(_w0 + np.mod(ww - _w0, _P))), wc, prof


def fit_helix(mesh, faces):
    """Punto de entrada del ajuste. Devuelve (info, modelo) donde `info` tiene el
    marco/eje, paso, sentido, perfil y rangos; `modelo(θ, z)` evalúa el radio."""
    faces = np.asarray(faces, int)
    vidx = np.unique(mesh.faces[faces].ravel())
    pts = mesh.vertices[vidx].astype(float)
    if len(pts) < 60:
        raise ValueError(f"parche demasiado pequeño para una rosca ({len(pts)} vértices)")
    fn = mesh.face_normals[faces]
    fa = mesh.area_faces[faces]

    a, q, e1, e2, z, rho, th = _cyl_frame(pts, fn, fa)
    P, sign, scatter = _estimate_pitch(z, th, rho)
    g, wc, prof = _fit_profile(z, th, rho, P, sign)

    k = P / TWO_PI
    rho_model = g(np.mod(z - sign * k * th, P))
    res = rho - rho_model
    rms = float(np.sqrt((res ** 2).mean()))

    u0, u1, full = _ang_span(th)
    info = {
        "frame": ("cyl", q, e1, e2, a),           # mismo formato que meshfit_nurbs
        "mode": "cyl", "full": full,
        "u0": float(u0), "u1": float(u1),
        "v0": float(z.min()), "v1": float(z.max()),
        "pitch": float(P), "sign": float(sign),
        "r_crest": float(prof.max()), "r_root": float(prof.min()),
        "r_mean": float(prof.mean()),
        "axis": a.tolist(), "point": q.tolist(),
        "rms_radial": rms, "pts": pts, "g": g, "diag": float(np.linalg.norm(pts.max(0) - pts.min(0))) or 1.0,
    }

    def model(theta, zz):
        return g(np.mod(zz - sign * k * theta, P))

    return info, model


def helix_surface(info, model):
    """Superficie B-spline del MODELO helicoidal sobre la rejilla (θ, z). Los puntos
    son exactos (el modelo, no la malla ruidosa) -> el spline converge limpio. La
    resolución sigue la estructura: ~12 puntos por vuelta en θ y ~10 por paso en z."""
    _, q, e1, e2, a = info["frame"]
    u0, u1 = info["u0"], info["u1"]
    v0, v1 = info["v0"], info["v1"]
    P = info["pitch"]
    nu = int(np.clip(round((u1 - u0) / TWO_PI * 16), 8, 32))
    # el muestreo axial debe resolver el perfil (32 celdas/paso en g): con 10/paso el
    # spline re-aliasa el perfil y resuena en púas finas
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

    # cota ESTRICTA: la superficie no puede salirse mucho del rango del perfil
    # [r_fondo, r_cresta] (el modelo es exacto: cualquier exceso es resonancia).
    # Vigilante denso (las púas de resonancia son finas y un 20×20 no las ve).
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
    """(θ desenrollado al rango, z) de un punto 3D — igual que meshfit_nurbs.map_uv
    en modo cilíndrico."""
    _, q, e1, e2, a = info["frame"]
    d = np.asarray(Pnt3, float) - q
    zz = float(d @ a)
    r = d - zz * a
    t = float(np.arctan2(r @ e2, r @ e1))
    u = info["u0"] + (t - info["u0"]) % TWO_PI
    if u > info["u1"]:
        u = info["u1"] if (u - info["u1"]) < (info["u0"] + TWO_PI - u) else info["u0"]
    return u, zz


def fit_region_helix(mesh, faces):
    """Como meshfit_nurbs.fit_region pero con el modelo helicoidal: devuelve el dict
    para el frontend (teselado recortado + parámetros de rosca)."""
    faces = np.asarray(faces, int)
    info, model = fit_helix(mesh, faces)
    surf = helix_surface(info, model)

    nu_t = int(np.clip(round((info["u1"] - info["u0"]) / TWO_PI * 48), 32, 96))
    nv_t = int(np.clip(round((info["v1"] - info["v0"]) / info["pitch"] * 16), 32, 400))
    verts, tris = tessellate(surf, nu_t, nv_t)

    dist, _ = cKDTree(verts).query(info["pts"])
    rms, mx = float(np.sqrt((dist ** 2).mean())), float(dist.max())

    # recorte al contorno pintado (par-impar en (θ,z), rayo a lo largo de z)
    A3, B3 = _boundary_segments_3d(mesh, faces)
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
    }
    return data, surf


if __name__ == "__main__":
    import sys
    import trimesh

    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\rcosme\Downloads\Screw+M8+20mm.stl"
    mesh = trimesh.load(path, force="mesh")
    mesh.merge_vertices()
    # selección de prueba: la zona roscada (radio > 2, mitad superior)
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
