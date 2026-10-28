"""
MeshFit — construcción de un SÓLIDO cerrado (B-rep estanco) a partir de la segmentación.

El exportador clásico (`meshfit_step.export_step`) recorta cada superficie a SU contorno de
malla por separado y luego intenta coserlas: las caras vecinas nunca comparten arista
exacta y el STEP llega al CAD como un montón de superficies sueltas (0 sólidos).

Aquí la topología sale de la MALLA, como en QuickSurface:
  1. cada triángulo tiene una etiqueta de región; cada región tiene su superficie
     (plano/cilindro/cono/esfera/toro detectados, B-spline para lo libre, faceta plana
     como última red);
  2. las fronteras entre regiones son cadenas de aristas de malla; cada cadena se
     convierte en UNA arista B-rep (recta, arco/círculo o B-spline) COMPARTIDA por las
     dos caras que separa -> estanco por construcción;
  3. los vértices de frontera se proyectan sobre las superficies que tocan (alternando)
     para que las aristas caigan sobre ambas;
  4. ShapeFix calcula pcurves, costuras y tolerancias; se cierra el shell en sólido.
Si una cara sale inválida, su región se degrada a facetas y se reconstruye.
"""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from OCP.gp import gp_Pnt, gp_Dir, gp_Ax3, gp_Ax2, gp_Pln, gp_Vec
from OCP.Geom import (Geom_Plane, Geom_CylindricalSurface, Geom_ConicalSurface,
                      Geom_SphericalSurface, Geom_ToroidalSurface, Geom_Circle,
                      Geom_BSplineCurve)
from OCP.GC import GC_MakeSegment
from OCP.GeomAPI import (GeomAPI_ProjectPointOnSurf, GeomAPI_Interpolate,
                         GeomAPI_PointsToBSplineSurface, GeomAPI_PointsToBSpline)
from OCP.GeomLProp import GeomLProp_SLProps
from OCP.TColgp import TColgp_Array2OfPnt, TColgp_HArray1OfPnt, TColgp_Array1OfPnt
from OCP.Approx import Approx_IsoParametric
from OCP.GeomAbs import GeomAbs_C2
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.TopoDS import TopoDS_Vertex, TopoDS_Edge, TopoDS_Wire, TopoDS_Face, TopoDS_Shell, TopoDS
from OCP.TopAbs import (TopAbs_FORWARD, TopAbs_REVERSED, TopAbs_FACE, TopAbs_EDGE, TopAbs_SHELL,
                        TopAbs_WIRE)
from OCP.TopExp import TopExp_Explorer, TopExp
from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
from OCP.ShapeFix import ShapeFix_Shape, ShapeFix_Solid
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepLib import BRepLib


class _FrozenMesh:
    """Copia de SOLO LECTURA con arrays NumPy simples. Cada lectura de una propiedad de un
    trimesh (normales, centros, adyacencias...) verifica su caché HASHEANDO toda la malla:
    en torni (155k triángulos) eran 263 000 hashes y 728 de 1124 s de la etapa de regiones."""
    def __init__(self, m):
        self.vertices = np.asarray(m.vertices, float).copy()
        self.faces = np.asarray(m.faces).copy()
        self.face_normals = np.asarray(m.face_normals, float).copy()
        self.triangles_center = np.asarray(m.triangles_center, float).copy()
        self.area_faces = np.asarray(m.area_faces, float).copy()
        self.face_adjacency = np.asarray(m.face_adjacency).copy()
        self.face_adjacency_angles = np.asarray(m.face_adjacency_angles, float).copy()
        self.face_adjacency_unshared = np.asarray(m.face_adjacency_unshared).copy()
        self.extents = np.asarray(m.extents, float).copy()
        self.area = float(m.area)


def _P(p):
    return gp_Pnt(float(p[0]), float(p[1]), float(p[2]))


def _perp(a):
    a = a / np.linalg.norm(a)
    t = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
    x = np.cross(a, t); x /= np.linalg.norm(x)
    return x, np.cross(a, x)


def _ax3(o, z, x):
    return gp_Ax3(_P(o), gp_Dir(*map(float, z)), gp_Dir(*map(float, x)))


# --------------------------------------------------------------------------- superficies
def _prim_surface(prim):
    t = prim["type"]
    if t == "plane":
        n = np.asarray(prim["normal"], float); n /= np.linalg.norm(n)
        x, _ = _perp(n)
        return Geom_Plane(gp_Pln(_ax3(prim["point"], n, x)))
    if t == "cylinder":
        a = np.asarray(prim["axis"], float); a /= np.linalg.norm(a)
        x, _ = _perp(a)
        return Geom_CylindricalSurface(_ax3(prim["point"], a, x), float(prim["radius"]))
    if t == "cone":
        a = np.asarray(prim["axis"], float); a /= np.linalg.norm(a)
        x, _ = _perp(a)
        return Geom_ConicalSurface(_ax3(prim["origin"], a, x), float(prim["half_angle"]),
                                   max(float(prim["b"]), 1e-4))
    if t == "sphere":
        return Geom_SphericalSurface(_ax3(prim["center"], (0, 0, 1.0), (1.0, 0, 0)),
                                     float(prim["radius"]))
    if t == "torus":
        a = np.asarray(prim["axis"], float); a /= np.linalg.norm(a)
        x, _ = _perp(a)
        return Geom_ToroidalSurface(_ax3(prim["center"], a, x), float(prim["R"]), float(prim["r"]))
    return None


def _facet_surface(mesh, f):
    p = mesh.vertices[mesh.faces[f]]
    n = np.cross(p[1] - p[0], p[2] - p[0])
    ln = np.linalg.norm(n)
    if ln < 1e-14:
        return None
    n /= ln
    x = (p[1] - p[0]); x /= (np.linalg.norm(x) or 1.0)
    return Geom_Plane(gp_Pln(_ax3(p.mean(0), n, x)))


def _fit_bspline(mesh, faces, tol):
    """Campo de alturas sobre el plano PCA -> B-spline bicúbica con MARGEN (el dominio
    cubre de sobra la región, para que las aristas se proyecten dentro). Devuelve
    (surf, ok) — ok=False si la región no es un grafo o el ajuste no llega a `tol`."""
    import trimesh
    from scipy.interpolate import griddata, LSQBivariateSpline
    faces = np.asarray(faces, int)
    vidx = np.unique(mesh.faces[faces].ravel())
    pts = mesh.vertices[vidx].astype(float)
    if len(pts) < 6:
        return None, False
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    n = vt[2]
    fn = mesh.face_normals[faces]
    if (fn @ n).mean() < 0:
        n = -n
    if (fn @ n).min() < 0.35:   # muy empinada sobre su plano: contorno UV comprimido que
        # se auto-interseca (o se pliega: no es grafo) -> que se trocee
        return None, False
    x = vt[0]; y = np.cross(n, x)
    # puntos de la SUPERFICIE de malla (no solo vértices): en CAD las bandas de redondeo
    # son tiras de triángulos largos con muy pocos vértices
    lat = float(np.ptp((pts - c) @ x)) or 1.0
    sv, sf = trimesh.remesh.subdivide_to_size(mesh.vertices, mesh.faces[faces], lat / 25.0)
    S = np.unique(np.round(sv[np.unique(sf.ravel())], 9), axis=0)
    d = S - c
    u, v, h = d @ x, d @ y, d @ n
    lu, lv = float(np.ptp(u)), float(np.ptp(v))
    mu, mv = 0.08 * lu + 1e-3, 0.08 * lv + 1e-3
    bb = [u.min() - mu, u.max() + mu, v.min() - mv, v.max() + mv]
    # regularización: rejilla de relleno con peso bajo (zonas sin datos del dominio)
    gu, gv = np.meshgrid(np.linspace(bb[0], bb[1], 24), np.linspace(bb[2], bb[3], 24))
    gu, gv = gu.ravel(), gv.ravel()
    gh = griddata((u, v), h, (gu, gv), method="linear")
    gn = griddata((u, v), h, (gu, gv), method="nearest")
    gh = np.where(np.isnan(gh), gn, gh)
    U = np.r_[u, gu]; V = np.r_[v, gv]; Hh = np.r_[h, gh]
    W = np.r_[np.ones(len(u)), np.full(len(gu), 0.05)]
    best = None
    asp = min(lu, lv) / max(lu, lv)
    # de menos a más nudos (lo más suave que cumpla); el lado corto lleva menos
    for kl in (1, 2, 4, 7, 11, 16, 24):
        ku = int(round(kl * (1.0 if lu >= lv else asp)))
        kv = int(round(kl * (1.0 if lv > lu else asp)))
        tx = np.linspace(bb[0], bb[1], ku + 2)[1:-1]
        ty = np.linspace(bb[2], bb[3], kv + 2)[1:-1]
        try:
            sp = LSQBivariateSpline(U, V, Hh, tx, ty, w=W, bbox=bb, kx=3, ky=3)
            if getattr(mesh, 'precision_reparacion', False):
                # Un ajuste puede seguir las muestras y tener polos enormes:
                # entonces su volumen depende catastróficamente del giro.
                coeffs = sp.get_coeffs()
                # Algunos sistemas mal condicionados no emiten aviso FITPACK.
                # Sus polos pueden estar a 10^15 mm de una banda de 25 mm.
                # Una cota holgada respecto al tamaño LOCAL evita esa
                # extrapolación; no es un margen de aceptación geométrica.
                coeff_limit = float(np.max(np.abs(h))) + 10 * max(lu, lv, 1e-3)
                if not np.isfinite(coeffs).all() or float(np.max(np.abs(coeffs))) > coeff_limit:
                    continue
        except Exception:
            continue
        res = np.abs(sp.ev(u, v) - h)
        # los vértices de malla son puntos EXACTOS de la pieza (CAD): ninguno puede
        # quedar fuera; el resto de la superficie, al percentil 95
        dv = (pts - c)
        rv = np.abs(sp.ev(dv @ x, dv @ y) - dv @ n)
        e95 = max(float(np.percentile(res, 95)), float(rv.max()) / 1.5)
        best = (sp, e95, tx, ty)
        if e95 <= tol:
            break
    if best is None:
        return None, False
    sp, e95, tx, ty = best          # nudos del ajuste guardado (no del último intento)
    surf = _height_spline_to_bspline(sp, tx, ty, bb, c, x, y, n)
    if surf is None:
        return None, False
    return surf, e95 <= tol


def _height_spline_to_bspline(sp, tx, ty, bb, c, x, y, n):
    """Spline de alturas (scipy, bicúbica sobre el plano c+u·x+v·y) -> B-spline 3D
    EXACTA de OCC: polos en las abscisas de Greville (la parametrización u,v es lineal)."""
    kx = ky = 3
    tu = np.r_[[bb[0]] * (kx + 1), tx, [bb[1]] * (kx + 1)]
    tv = np.r_[[bb[2]] * (ky + 1), ty, [bb[3]] * (ky + 1)]
    nu_, nv_ = len(tu) - kx - 1, len(tv) - ky - 1
    coef = sp.get_coeffs().reshape(nu_, nv_)
    gx = np.array([tu[i + 1:i + kx + 1].mean() for i in range(nu_)])
    gy = np.array([tv[j + 1:j + ky + 1].mean() for j in range(nv_)])
    from OCP.Geom import Geom_BSplineSurface
    from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
    poles = TColgp_Array2OfPnt(1, nu_, 1, nv_)
    for i in range(nu_):
        for j in range(nv_):
            poles.SetValue(i + 1, j + 1, _P(c + gx[i] * x + gy[j] * y + coef[i, j] * n))

    def kn(t, k):
        dist = np.r_[t[0], t[k + 1:-k - 1], t[-1]]
        ka = TColStd_Array1OfReal(1, len(dist)); ma = TColStd_Array1OfInteger(1, len(dist))
        for i, val in enumerate(dist):
            ka.SetValue(i + 1, float(val))
            ma.SetValue(i + 1, k + 1 if i in (0, len(dist) - 1) else 1)
        return ka, ma
    uk, um = kn(tu, kx); vk, vm = kn(tv, ky)
    try:
        return Geom_BSplineSurface(poles, uk, vk, um, vm, kx, ky)
    except Exception:
        return None


# --------------------------------------------------------------------------- utilidades
class _Proj:
    """Proyector reutilizable punto -> superficie."""
    def __init__(self, surf):
        from OCP.ShapeAnalysis import ShapeAnalysis_Surface
        self.s = surf
        self.sas = ShapeAnalysis_Surface(surf)
        # proyección EXACTA en NumPy para las analíticas (la genérica de OCC, punto a punto,
        # se llevaba 3 minutos en Part Studio con miles de vértices de frontera)
        self.kind = None
        try:
            from OCP.Geom import (Geom_CylindricalSurface, Geom_ConicalSurface,
                                  Geom_SphericalSurface, Geom_ToroidalSurface)
            def v3(d):
                return np.array([d.X(), d.Y(), d.Z()])
            if isinstance(surf, Geom_Plane):
                ax = surf.Pln().Axis()
                self.kind, self.a, self.q = "plane", v3(ax.Direction()), v3(ax.Location())
            elif isinstance(surf, Geom_CylindricalSurface):
                ax = surf.Axis()
                self.kind, self.a, self.q, self.R = "cyl", v3(ax.Direction()), v3(ax.Location()), surf.Radius()
            elif isinstance(surf, Geom_ConicalSurface):
                ax = surf.Axis()
                self.kind, self.a, self.q = "cone", v3(ax.Direction()), v3(ax.Location())
                self.r0, self.al = surf.RefRadius(), surf.SemiAngle()
            elif isinstance(surf, Geom_SphericalSurface):
                self.kind, self.q, self.R = "sph", v3(surf.Location()), surf.Radius()
            elif isinstance(surf, Geom_ToroidalSurface):
                ax = surf.Axis()
                self.kind, self.a, self.q = "tor", v3(ax.Direction()), v3(ax.Location())
                self.R, self.r = surf.MajorRadius(), surf.MinorRadius()
        except Exception:
            self.kind = None

    def batch(self, P):
        """Proyección de muchos puntos (N×3). Analíticas: fórmula exacta; resto: OCC."""
        P = np.asarray(P, float)
        k = self.kind
        if k == "plane":
            return P - np.outer((P - self.q) @ self.a, self.a)
        if k == "sph":
            d = P - self.q
            n = np.linalg.norm(d, axis=1, keepdims=True)
            return self.q + self.R * d / np.maximum(n, 1e-12)
        if k in ("cyl", "cone", "tor"):
            d = P - self.q
            t = d @ self.a
            r = d - np.outer(t, self.a)
            rho = np.linalg.norm(r, axis=1)
            ru = r / np.maximum(rho, 1e-12)[:, None]
            if k == "cyl":
                return self.q + np.outer(t, self.a) + self.R * ru
            if k == "cone":                       # generatriz en el semiplano (t, ρ)
                ca, sa = np.cos(self.al), np.sin(self.al)
                sp = t * ca + (rho - self.r0) * sa
                return self.q + np.outer(sp * ca, self.a) + (self.r0 + sp * sa)[:, None] * ru
            C = self.q + self.R * ru                # tor: punto del círculo mayor
            dc = P - C
            nc = np.linalg.norm(dc, axis=1, keepdims=True)
            return C + self.r * dc / np.maximum(nc, 1e-12)
        # superficie libre: búsqueda LOCAL partiendo del punto anterior (los puntos van en
        # orden a lo largo de la arista); la global, sobre un anillo periódico de cientos
        # de polos, costaba ms por punto (166 s en UNA arista de Part Studio)
        from OCP.gp import gp_Pnt2d
        out = P.copy()
        prev = None
        for i, q in enumerate(P):
            try:
                if prev is not None:
                    uv = self.sas.NextValueOfUV(prev, _P(q), 1e-7, -1.0)
                else:
                    uv = self.sas.ValueOfUV(_P(q), 1e-7)
            except Exception:
                prev = None
                continue
            r = self.s.Value(uv.X(), uv.Y())
            out[i] = (r.X(), r.Y(), r.Z())
            prev = gp_Pnt2d(uv.X(), uv.Y())
        return out

    def __call__(self, q):
        try:
            uv = self.sas.ValueOfUV(_P(q), 1e-7)
        except Exception:
            return None, None
        r = self.s.Value(uv.X(), uv.Y())
        return np.array([r.X(), r.Y(), r.Z()]), (uv.X(), uv.Y())

    def normal(self, q):
        pt, uv = self(q)
        if pt is None:
            return None
        pr = GeomLProp_SLProps(self.s, uv[0], uv[1], 1, 1e-9)
        if not pr.IsNormalDefined():
            return None
        nn = pr.Normal()
        return np.array([nn.X(), nn.Y(), nn.Z()])


def _split_connected(mesh, labels):
    """Cada etiqueta -> sus componentes conexas (una cara B-rep debe ser conexa)."""
    adj = mesh.face_adjacency
    same = labels[adj[:, 0]] == labels[adj[:, 1]]
    a = adj[same]
    nf = len(mesh.faces)
    g = coo_matrix((np.ones(len(a)), (a[:, 0], a[:, 1])), shape=(nf, nf))
    _, comp = connected_components(g, directed=False)
    return comp


# --------------------------------------------------------------------------- cadenas
def _boundary_chains(mesh, labels):
    """Cadenas de frontera entre regiones.

    Devuelve (chains, loops):
      chains: dict key -> {"verts": [v0..vk] (canónico), "closed": bool, "pair": (a,b)}
      loops:  dict label -> lista de bucles; cada bucle = lista de (key, forward)
    Las semiaristas se recorren con el sentido de los triángulos (normal exterior), así
    cada bucle deja su región a la IZQUIERDA vista desde fuera."""
    # semiaristas VECTORIZADAS (en torni, 465 000 en un dict de Python por ronda): solo las
    # de frontera pasan a Python
    F = np.asarray(mesh.faces)
    nf, nv = len(F), len(mesh.vertices)
    HA = F.reshape(-1).astype(np.int64)
    HB = F[:, [1, 2, 0]].reshape(-1).astype(np.int64)
    HF = np.repeat(np.arange(nf), 3)
    key = HA * nv + HB
    order = np.argsort(key)
    ks = key[order]
    tw = HB * nv + HA
    pos_ = np.clip(np.searchsorted(ks, tw), 0, len(ks) - 1)
    found = ks[pos_] == tw
    twin = np.where(found, HF[order[pos_]], -1)
    LA = labels[HF]
    LB = np.where(twin >= 0, labels[np.maximum(twin, 0)], -1)
    bd = LA != LB
    # semiaristas de frontera por etiqueta: origen -> lista de (destino, etiqueta vecina)
    out = {}
    for a, b, la, lb in zip(HA[bd].tolist(), HB[bd].tolist(), LA[bd].tolist(), LB[bd].tolist()):
        out.setdefault(la, {}).setdefault(a, []).append((b, lb))
    # esquina = vértice que toca ≥3 regiones
    pairs = np.unique(np.c_[F.ravel(), np.repeat(labels, 3)], axis=0)
    corner = np.bincount(pairs[:, 0], minlength=nv) >= 3
    # La reconstrucción conservadora puede conservar como esquinas los
    # vértices de sus parches pequeños, incluso si sólo tocan dos regiones.
    forced=getattr(mesh,'esquinas_contorno_compartido',None)
    if forced is not None:corner[np.asarray(sorted(forced),dtype=int)]=True
    for la, d in out.items():
        for a, lst in d.items():
            if len(lst) > 1:
                corner[a] = True            # pellizco: el borde se ramifica
    chains, loops = {}, {}
    for la, d in out.items():
        used = set()
        for a0 in list(d.keys()):
            for (b0, _) in d[a0]:
                if (a0, b0) in used:
                    continue
                # recorrer el bucle
                seq = [a0]; nb = []
                a, b = a0, b0
                while True:
                    used.add((a, b))
                    nb.append(next(l for (bb, l) in d[a] if bb == b))
                    seq.append(b)
                    if b == a0:
                        break
                    nxt = [bb for (bb, _) in d.get(b, []) if (b, bb) not in used]
                    if not nxt:
                        break               # bucle abierto (malla no estanca)
                    a, b = b, nxt[0]
                closed_loop = seq[-1] == seq[0]
                cyc = seq[:-1] if closed_loop else seq
                n = len(cyc)
                # cortes: esquinas o cambio de vecino
                cuts = [i for i in range(n) if corner[cyc[i]] or nb[i - 1] != nb[i % len(nb)]]
                if not closed_loop:
                    cuts = sorted(set([0, n - 1] + cuts))
                lp = []
                if not cuts:                 # bucle cerrado sin esquinas: UNA arista cerrada
                    lb = nb[0]
                    vs = list(cyc) if la < lb else list(reversed(cyc))
                    k0 = int(np.argmin(vs))
                    vs = vs[k0:] + vs[:k0]
                    key = (min(la, lb), max(la, lb), "c", tuple(vs))
                    chains.setdefault(key, {"verts": vs, "closed": True, "pair": (la, lb)})
                    lp.append((key, la < lb))
                else:
                    rot = cyc[cuts[0]:] + cyc[:cuts[0]] if closed_loop else cyc
                    nbr = (nb[cuts[0]:] + nb[:cuts[0]]) if closed_loop else nb
                    rc = [(c - cuts[0]) % n for c in cuts] if closed_loop else cuts
                    rc = sorted(rc)
                    if closed_loop:
                        rc = rc + [n]
                        rot = rot + [rot[0]]
                    for i in range(len(rc) - 1):
                        s, e = rc[i], rc[i + 1]
                        vs = rot[s:e + 1]
                        lb = nbr[s]
                        cv = vs if la < lb else list(reversed(vs))
                        key = (min(la, lb), max(la, lb), "o", tuple(cv))
                        chains.setdefault(key, {"verts": list(cv), "closed": False, "pair": (la, lb)})
                        lp.append((key, la < lb))
                loops.setdefault(la, []).append(lp)
    return chains, loops, corner


# --------------------------------------------------------------------------- curvas
def _fit_circle(P):
    c = P.mean(0)
    _, s, vt = np.linalg.svd(P - c, full_matrices=False)
    n = vt[2]
    x, y = vt[0], vt[1]
    q = np.c_[(P - c) @ x, (P - c) @ y]
    A = np.c_[2 * q, np.ones(len(q))]
    sol, *_ = np.linalg.lstsq(A, (q ** 2).sum(1), rcond=None)
    cc = sol[:2]
    R = float(np.sqrt(max(sol[2] + cc @ cc, 0)))
    C = c + cc[0] * x + cc[1] * y
    planar = float(np.abs((P - c) @ n).max())
    rad = float(np.abs(np.linalg.norm(P - C, axis=1) - R).max())
    return C, n, R, max(planar, rad)


def _edge_curve(P, closed, tol):
    """Curva 3D para una cadena de puntos: recta, arco/círculo o B-spline.
    Devuelve (Geom_Curve, p_ini, p_fin)."""
    if not closed and len(P) == 2:
        tc = GC_MakeSegment(_P(P[0]), _P(P[1])).Value()
        return tc, tc.FirstParameter(), tc.LastParameter()
    if not closed:
        d = P[-1] - P[0]
        L = np.linalg.norm(d)
        if L > 1e-12:
            t = d / L
            off = (P - P[0]) - np.outer((P - P[0]) @ t, t)
            if np.linalg.norm(off, axis=1).max() <= tol:
                tc = GC_MakeSegment(_P(P[0]), _P(P[-1])).Value()
                return tc, tc.FirstParameter(), tc.LastParameter()
    if len(P) >= (4 if not closed else 3):
        C, n, R, err = _fit_circle(P)
        span = np.linalg.norm(P.max(0) - P.min(0))
        if err <= tol and R < 50 * span + 1e-9:
            x = P[0] - C; x -= (x @ n) * n
            if np.linalg.norm(x) > 1e-12:
                x /= np.linalg.norm(x)
                y = np.cross(n, x)
                ang = np.unwrap(np.arctan2((P - C) @ y, (P - C) @ x))
                if not closed and ang[-1] < ang[0]:
                    n = -n; y = -y
                    ang = np.unwrap(np.arctan2((P - C) @ y, (P - C) @ x))
                if closed:
                    if ang[min(2, len(ang) - 1)] < ang[0]:
                        n = -n; y = -y
                    circ = Geom_Circle(gp_Ax2(_P(C), gp_Dir(*n), gp_Dir(*x)), R)
                    return circ, 0.0, 2 * np.pi
                a1 = float(ang[-1] - ang[0])
                if 1e-6 < a1 < 2 * np.pi:
                    circ = Geom_Circle(gp_Ax2(_P(C), gp_Dir(*n), gp_Dir(*x)), R)
                    # el arco ENTERO debe seguir la polilínea (4 puntos casi colineales
                    # admiten un círculo que se abomba 0.6 mm entre ellos)
                    S = np.array([[q.X(), q.Y(), q.Z()] for q in
                                  (circ.Value(t) for t in np.linspace(0, a1, 8 * len(P)))])
                    if _dist_to_polyline(S, P).max() <= 2 * tol:
                        return circ, 0.0, a1
    # B-spline por los puntos. Antes se REMUESTREA uniforme por longitud de arco: con
    # puntos muy desigualmente espaciados la interpolación se dispara entre ellos.
    Q = P[:-1] if closed and np.linalg.norm(P[-1] - P[0]) < 1e-12 else P
    keep = [0]
    for i in range(1, len(Q)):
        if np.linalg.norm(Q[i] - Q[keep[-1]]) > 1e-7:
            keep.append(i)
    Q = Q[keep]
    if closed and len(Q) < 3 or not closed and len(Q) < 2:
        raise ValueError("cadena degenerada")
    poly = np.vstack([Q, Q[:1]]) if closed else Q          # polilínea de referencia
    # como mucho 200 puntos al ajuste (con 1500, la aproximación de OCC tardaba 160 s en
    # UNA arista); la validación sigue siendo contra la polilínea completa
    Qs = _resample(poly, int(np.clip(len(Q), 4, 200)))
    if closed:
        Qs = Qs[:-1]
    cands = []
    if not closed and len(Qs) > 8:
        # APROXIMAR dentro de tolerancia (pocos polos -> STEP ligero y curva lisa)
        a1 = TColgp_Array1OfPnt(1, len(Qs))
        for i, q in enumerate(Qs):
            a1.SetValue(i + 1, _P(q))
        try:
            ap = GeomAPI_PointsToBSpline(a1, 3, 8, GeomAbs_C2, 0.5 * tol)
            if ap.IsDone():
                cands.append(ap.Curve())
        except Exception:
            pass
    try:
        arr = TColgp_HArray1OfPnt(1, len(Qs))
        for i, q in enumerate(Qs):
            arr.SetValue(i + 1, _P(q))
        it = GeomAPI_Interpolate(arr, bool(closed), 1e-9)
        it.Perform()
        if it.IsDone():
            cands.append(it.Curve())
    except Exception:
        pass
    for cv in cands:
        a, b = cv.FirstParameter(), cv.LastParameter()
        ends = max(cv.Value(a).Distance(_P(poly[0])), cv.Value(b).Distance(_P(poly[-1])))
        S = np.array([[q.X(), q.Y(), q.Z()] for q in
                      (cv.Value(t) for t in np.linspace(a, b, 4 * len(poly) + 8))])
        # la curva ENTERA (no solo en los puntos de paso) debe seguir la polilínea
        if ends <= 1e-7 + 0.1 * tol and _dist_to_polyline(S, poly).max() <= 2 * tol:
            return cv, a, b
    # red de seguridad: polilínea exacta (B-spline de grado 1)
    return _polyline_curve(poly)


def _resample(poly, n):
    """n puntos uniformes por longitud de arco sobre una polilínea (conserva extremos)."""
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    cum = np.r_[0, np.cumsum(seg)]
    t = np.linspace(0, cum[-1], n)
    return np.c_[[np.interp(t, cum, poly[:, k]) for k in range(3)]].T


def _dist_to_polyline(S, poly):
    a, b = poly[:-1], poly[1:]
    ab = b - a
    L2 = np.maximum((ab ** 2).sum(1), 1e-18)
    best = np.full(len(S), np.inf)
    for i in range(0, len(a), 256):
        aa, ab_, ll = a[i:i + 256], ab[i:i + 256], L2[i:i + 256]
        t = np.clip(((S[:, None, :] - aa[None]) * ab_[None]).sum(2) / ll[None], 0, 1)
        d = np.linalg.norm(S[:, None, :] - (aa[None] + t[..., None] * ab_[None]), axis=2)
        best = np.minimum(best, d.min(1))
    return best


def _polyline_curve(poly):
    from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
    n = len(poly)
    poles = TColgp_Array1OfPnt(1, n)
    for i, q in enumerate(poly):
        poles.SetValue(i + 1, _P(q))
    cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(poly, axis=0), axis=1))]
    kn = TColStd_Array1OfReal(1, n); mu = TColStd_Array1OfInteger(1, n)
    for i in range(n):
        kn.SetValue(i + 1, float(cum[i])); mu.SetValue(i + 1, 2 if i in (0, n - 1) else 1)
    cv = Geom_BSplineCurve(poles, kn, mu, 1)
    return cv, cv.FirstParameter(), cv.LastParameter()


def _try_primitive(mesh, reg, tol):
    """Primitiva (plano/cilindro/cono/esfera/toro) para una región libre si la malla se
    pega a ella dentro de `tol` (vértices Y centros de triángulo). None si no."""
    from meshfit_detect import classify_region
    reg = np.asarray(reg, int)
    vidx = np.unique(mesh.faces[reg].ravel())
    pts = mesh.vertices[vidx].astype(float)
    if len(pts) < 3:
        return None
    diag = float(np.linalg.norm(mesh.extents))
    try:
        import os
        prim = classify_region(pts, mesh.face_normals[reg], mesh.area_faces[reg], diag, 0.01,
                               cents=mesh.triangles_center[reg],
                               accept_verified_shallow=(os.environ.get('VISOR_REFINAMIENTO_BREP') == '1'))
    except Exception:
        return None
    if prim is None:
        return None
    s = _prim_surface(prim)
    if s is None:
        return None
    pr = _Proj(s)
    chk = np.vstack([pts, mesh.triangles_center[reg]])
    if len(chk) > 600:
        chk = chk[np.linspace(0, len(chk) - 1, 600).astype(int)]
    for q in chk:
        r, _ = pr(q)
        if r is None or np.linalg.norm(r - q) > tol:
            return None
    return s, prim


# --------------------------------------------------------------------------- construcción
SHARP_DEG = 25.0      # ángulo diedro a partir del cual una arista de malla es "viva"
# RUIDO de la malla: mediana del ángulo diedro entre triángulos vecinos (grados). En CAD
# ~0–1°; en un escaneo (±0.02 mm sobre triángulos de 0.25 mm) ~5–7°. Todos los umbrales
# de ÁNGULO se escalan con él (`_ang`): en CAD no cambia nada, en escaneos se adaptan.
_NOISE = {"deg": 0.0}


def _ang(base_deg, k=3.0):
    """Umbral angular adaptado al ruido: max(base, k·ruido)."""
    return max(base_deg, k * _NOISE["deg"])
MAX_FREE_FACES = 400000  # más triángulos libres que esto -> no se intenta el sólido
GROW_MIN_FACES = 6000   # zonas libres mayores: antes, crecimiento de primitivas (meshfit_grow)


def _prim_arrays(prim):
    """dict de primitiva con arrays numpy (los del visor/JSON llegan como listas)."""
    q = {k: (np.asarray(v, float) if isinstance(v, (list, tuple)) and k != "faces" else v)
         for k, v in prim.items()}
    for k in ("normal", "axis"):
        if k in q:
            q[k] = q[k] / np.linalg.norm(q[k])
    if q.get("type") == "cone" and "slope" not in q:
        q["slope"] = float(np.tan(q["half_angle"]))
    return q


def _prim_dev(prim, pts):
    from meshfit_detect import DEV
    return DEV[prim["type"]](prim, pts)


def _prim_ndot(prim, cents, normals):
    from meshfit_detect import _normal_dots
    return _normal_dots(prim, cents, normals)


def _region_surfaces(result, mesh, ff_tol, bs_tol=None, extra=None, prims_out=None):
    """labels por triángulo + superficie por etiqueta (+ primitiva analítica si la hay).
    `extra`: [(caras, Geom_Surface), ...] regiones con superficie IMPUESTA por el usuario
    (NURBS pintadas a mano, roscas): se asignan primero y quedan BLOQUEADAS (la limpieza
    automática no les quita ni les funde nada)."""
    nf = len(mesh.faces)
    labels = np.full(nf, -1, int)
    surfs, prims = [], []
    locked = set()
    for fr, s_ in (extra or []):
        fr = np.asarray(fr, int)
        fr = fr[labels[fr] == -1]
        if len(fr) == 0 or s_ is None:
            continue
        labels[fr] = len(surfs); locked.add(len(surfs)); surfs.append(s_); prims.append(None)
    stack = [np.asarray(r, int) for r in result.get("freeform_regions", []) if len(r)]
    prim_list = result["primitives"]
    if _NOISE["deg"] > 2.0:
        # ESCANEO con ruido: la detección por ángulo diedro devuelve miles de "planos" de
        # pocos triángulos (ruido) que, con prioridad, quedaban fijados -> se ignoran y
        # el crecimiento de primitivas (robusto al ruido) segmenta la pieza entera
        stack = [np.arange(nf)]
        prim_list = []
    for prim in prim_list:
        s = _prim_surface(prim)
        if s is None:
            continue
        fidx = np.asarray(prim["faces"], int)
        fidx = fidx[labels[fidx] == -1]
        if len(fidx) == 0:
            continue
        # CONTROL DE CALIDAD: la primitiva tiene que pegarse a su malla. El detector a
        # veces regulariza a plano bandas de redondeo (normales a 30°+, 0.5 mm fuera):
        # en el sólido eso deja la cara despegada -> esa zona va como superficie libre.
        vidx = np.unique(mesh.faces[fidx].ravel())
        if len(vidx) > 400:
            vidx = vidx[np.linspace(0, len(vidx) - 1, 400).astype(int)]
        pr = _Proj(s)
        dev = []
        for v in vidx:
            q, _ = pr(mesh.vertices[v])
            dev.append(np.inf if q is None else np.linalg.norm(q - mesh.vertices[v]))
        # Un hexágono tiene sus VÉRTICES sobre un cilindro circunscrito,
        # pero los interiores de las caras planas no. Verificamos también
        # los centroides para evitar redondear polígonos reales.
        if __import__("os").environ.get("VISOR_CENTROID_GATE") == "1" and prim["type"] != "plane":
            sample_faces = fidx
            if len(sample_faces) > 500:
                sample_faces = sample_faces[np.linspace(0, len(sample_faces)-1, 500).astype(int)]
            face_err = _prim_dev(prim, mesh.triangles_center[sample_faces])
            if len(face_err) and float(np.max(face_err)) > ff_tol:
                stack.append(fidx)
                continue
        if float(np.percentile(dev, 95)) > ff_tol:
            stack.append(fidx)
            continue
        labels[fidx] = len(surfs)
        surfs.append(s); prims.append(_prim_arrays(prim))
    # triángulos que nadie reclamó (p. ej. el 💾 del visor solo manda sus entidades):
    # sus componentes conexas son zonas libres más
    claimed = labels >= 0
    for r in stack:
        claimed[r] = True
    if not claimed.all():
        free = np.where(~claimed, 0, -1 - np.arange(len(labels)))
        comp = _split_connected(mesh, free)
        fr = np.where(~claimed)[0]
        cr = comp[fr]
        stack += [fr[cr == k] for k in np.unique(cr)]
    # MALLAS DENSAS: una zona libre enorme suele ser una pieza entera teselada fino
    # (P1/torni: el detector por ángulo diedro lo junta todo). Se segmenta primero por
    # CRECIMIENTO DE PRIMITIVAS; lo que sobra sigue el camino de siempre.
    stack = [r[labels[r] == -1] for r in stack]
    stack = [r for r in stack if len(r)]
    big = [r for r in stack if len(r) >= GROW_MIN_FACES]
    if big:
        from meshfit_grow import grow_primitives
        stack = [r for r in stack if len(r) < GROW_MIN_FACES]
        for r in big:
            regs, rest = grow_primitives(mesh, r, bs_tol or ff_tol,
                                         ndot=np.cos(np.radians(_ang(12.0))))
            for fr, pr_ in regs:
                s_ = _prim_surface(pr_)
                if s_ is None:
                    continue
                labels[fr] = len(surfs); surfs.append(s_); prims.append(_prim_arrays(pr_))
            if len(rest) and _NOISE["deg"] > 2.0:
                # ESCANEO: la franja que el escáner redondea entre dos caras no encaja en
                # ninguna -> se asigna a la primitiva vecina más cercana (arista VIVA, como
                # en el diseño original); solo lo que queda lejos sigue como zona libre
                rest = _absorb_scan_edges(mesh, labels, prims, rest, 4 * ff_tol)
            if len(rest):
                sub = np.where(np.isin(np.arange(len(labels)), rest), 0,
                               -2 - np.arange(len(labels)))
                comp = _split_connected(mesh, sub)
                cr = comp[rest]
                stack += [rest[cr == k] for k in np.unique(cr)]
    _process_free(mesh, stack, labels, surfs, prims, ff_tol, bs_tol)
    # LIMPIEZA (2ª pasada): los bordes de las zonas libres se ceden a las primitivas
    # vecinas que los contienen EXACTOS (en CAD la tapa plana entera acababa metida en
    # la B-spline del redondeo -> ondas visibles y aristas diagonales), se reajustan
    # las zonas libres con lo que les queda y se absorben las regiones diminutas.
    changed = _relax_to_primitives(mesh, labels, prims, ff_tol, locked=locked)
    if changed:
        refit = [np.where(labels == l)[0] for l in changed]
        for r in refit:
            labels[r] = -1
        refit = [r for r in refit if len(r)]
        _process_free(mesh, refit, labels, surfs, prims, ff_tol, bs_tol)
    _merge_regions(mesh, labels, prims, surfs, ff_tol, locked=locked)
    _upgrade_freeform(mesh, labels, surfs, prims, bs_tol or ff_tol, locked=locked)
    _merge_bspline_clusters(mesh, labels, surfs, prims, bs_tol or ff_tol, locked=locked)
    _merge_regions(mesh, labels, prims, surfs, ff_tol, locked=locked)
    _merge_rings(mesh, labels, prims, surfs, bs_tol or ff_tol, locked=locked)
    _merge_regions(mesh, labels, prims, surfs, ff_tol, locked=locked)
    if _NOISE["deg"] > 2.0 and (labels == -1).any():
        _absorb_nearest(mesh, labels, prims, surfs, np.where(labels == -1)[0])
    for f in np.where(labels == -1)[0]:       # triángulos que nadie reclamó
        s = _facet_surface(mesh, f)
        if s is not None:
            labels[f] = len(surfs); surfs.append(s); prims.append(None)
    if prims_out is not None:                  # primitiva por etiqueta (None = B-spline/faceta)
        prims_out[:] = prims
    return labels, surfs


def _process_free(mesh, stack, labels, surfs, prims, ff_tol, bs_tol=None):
    """Zonas libres -> (partir por aristas vivas) -> primitiva | B-spline | bisección |
    facetas. Escribe en labels/surfs/prims."""
    # las zonas libres se parten antes por sus ARISTAS VIVAS internas: una superficie
    # suave no puede seguir un pliegue (chaflán + cara metidos en la misma región)
    adj = mesh.face_adjacency
    sharp = mesh.face_adjacency_angles > np.radians(_ang(SHARP_DEG, 4.0))
    nf_all = len(mesh.faces)
    split = []
    for reg in stack:
        inreg = np.zeros(nf_all, bool); inreg[reg] = True
        keep = inreg[adj[:, 0]] & inreg[adj[:, 1]] & ~sharp
        a = adj[keep]
        g = coo_matrix((np.ones(len(a)), (a[:, 0], a[:, 1])), shape=(nf_all, nf_all))
        _, comp = connected_components(g, directed=False)
        cr = comp[reg]
        split += [reg[cr == k] for k in np.unique(cr)]
    stack = split
    while stack:
        reg = stack.pop()
        reg = reg[labels[reg] == -1]
        if len(reg) == 0:
            continue
        # ¿el trozo es en realidad una primitiva? (al partir por aristas vivas salen
        # paredes planas/cilíndricas limpias de regiones que el detector dio por libres)
        # PLANOS EXACTOS escondidos en la zona libre (la tapa plana + su redondeo en una
        # sola región): se pelan antes, si no la B-spline los absorbe y ondula
        planes, rest = _peel_planes(mesh, reg, max(1e-3, 0.1 * ff_tol))
        if planes:
            for cl, pr_ in planes:
                labels[cl] = len(surfs); surfs.append(_prim_surface(pr_)); prims.append(pr_)
            if len(rest):
                sub = np.full(len(labels), -1, int); sub[rest] = 0
                comp = _split_connected(mesh, np.where(sub == 0, 0, -2 - np.arange(len(sub))))
                cr = comp[rest]
                stack += [rest[cr == k] for k in np.unique(cr)]
            continue
        tp = _try_primitive(mesh, reg, ff_tol)
        if tp is not None:
            labels[reg] = len(surfs); surfs.append(tp[0]); prims.append(_prim_arrays(tp[1]))
            continue
        noisy = _NOISE["deg"] > 2.0
        # escaneo: B-spline con tolerancia acorde al ruido; trozos de ≥100 triángulos
        tol_bs = (bs_tol or ff_tol) * (2.0 if noisy else 1.0)
        surf, ok = _fit_bspline(mesh, reg, tol_bs) if len(reg) >= 6 else (None, False)
        if ok:
            labels[reg] = len(surfs); surfs.append(surf); prims.append(None); continue
        if len(reg) >= (200 if noisy else 24):
            fn = mesh.face_normals[reg]
            nbar = fn.mean(0)
            if np.linalg.norm(nbar) < 0.5:
                _, _, vt = np.linalg.svd(fn - nbar, full_matrices=False)
                proj = fn @ vt[0]
            else:
                cen = mesh.triangles_center[reg]
                proj = cen[:, int(np.argmax(np.ptp(cen, 0)))]
            med = np.median(proj)
            l, r = reg[proj <= med], reg[proj > med]
            if len(l) and len(r):
                stack += [l, r]; continue
        if noisy:
            continue          # escaneo: nada de facetas sobre ruido; se reparte al final
        for f in reg:                         # última red: facetas
            s = _facet_surface(mesh, f)
            if s is not None:
                labels[f] = len(surfs); surfs.append(s); prims.append(None)


def _peel_planes(mesh, reg, tight, min_frac=0.05):
    """Grupos CONEXOS de triángulos exactamente coplanares dentro de `reg` (normales a
    <0.5° y vértice opuesto a <= tight del plano vecino) con área >= min_frac de la
    región y >= 3 triángulos (un quad de redondeo partido en 2 también es coplanar).
    Devuelve ([(caras, prim_plano), ...], resto)."""
    reg = np.asarray(reg, int)
    if len(reg) < 6:
        return [], reg
    inreg = np.zeros(len(mesh.faces), bool); inreg[reg] = True
    adj = mesh.face_adjacency
    m = inreg[adj[:, 0]] & inreg[adj[:, 1]]
    a = adj[m]
    n = mesh.face_normals
    co = (n[a[:, 0]] * n[a[:, 1]]).sum(1) > np.cos(np.radians(0.5))
    # vértice no compartido de t2 contra el plano de t1
    unshared = mesh.face_adjacency_unshared[m][:, 1]
    off = np.abs(((mesh.vertices[unshared] - mesh.triangles_center[a[:, 0]]) * n[a[:, 0]]).sum(1))
    co &= off <= tight
    a = a[co]
    nf = len(mesh.faces)
    g = coo_matrix((np.ones(len(a)), (a[:, 0], a[:, 1])), shape=(nf, nf))
    _, comp = connected_components(g, directed=False)
    cr = comp[reg]
    total = float(mesh.area_faces[reg].sum())
    out, taken = [], np.zeros(len(reg), bool)
    for k in np.unique(cr):
        sel = cr == k
        cl = reg[sel]
        if len(cl) < 3 or mesh.area_faces[cl].sum() < min_frac * total:
            continue
        pts = mesh.vertices[np.unique(mesh.faces[cl].ravel())]
        c = pts.mean(0)
        _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
        nn = vt[2] * np.sign(vt[2] @ mesh.face_normals[cl].mean(0) or 1.0)
        if np.abs((pts - c) @ nn).max() > tight:
            continue
        out.append((cl, {"type": "plane", "point": c, "normal": nn}))
        taken |= sel
    return out, reg[~taken]


def _absorb_scan_edges(mesh, labels, prims, rest, tol, max_pass=200):
    """Triángulos sin primitiva (franjas de arista redondeadas por el escáner) -> a la
    primitiva VECINA más cercana si sus 3 vértices distan ≤ tol, anillo a anillo.
    Devuelve los que quedan sin asignar."""
    rest = np.asarray(rest, int)
    free = np.zeros(len(labels), bool); free[rest] = True
    adj = mesh.face_adjacency
    F, V = mesh.faces, mesh.vertices
    isprim = np.array([p is not None for p in prims] + [False])
    for _ in range(max_pass):
        la, lb = labels[adj[:, 0]], labels[adj[:, 1]]
        c1 = free[adj[:, 0]] & ~free[adj[:, 1]] & isprim[lb]
        c2 = free[adj[:, 1]] & ~free[adj[:, 0]] & isprim[la]
        t = np.r_[adj[c1, 0], adj[c2, 1]]
        b = np.r_[lb[c1], la[c2]]
        if len(t) == 0:
            break
        best_d = np.full(len(labels), np.inf)
        best_l = np.full(len(labels), -1)
        for bl in np.unique(b):
            tt = np.unique(t[b == bl])
            dv = _prim_dev(prims[bl], V[F[tt]].reshape(-1, 3)).reshape(-1, 3).max(1)
            upd = dv < best_d[tt]
            best_d[tt[upd]] = dv[upd]; best_l[tt[upd]] = bl
        ok = np.where((best_l >= 0) & (best_d <= tol))[0]
        if len(ok) == 0:
            break
        labels[ok] = best_l[ok]
        free[ok] = False
    return np.where(free)[0]


def _absorb_nearest(mesh, labels, prims, surfs, faces, max_pass=500):
    """ESCANEO: triángulos sin región -> a la región VECINA (primitiva o B-spline) cuya
    superficie les queda más cerca, anillo a anillo (las facetas sobre ruido impedían
    cerrar el sólido)."""
    free = np.zeros(len(labels), bool); free[np.asarray(faces, int)] = True
    adj = mesh.face_adjacency
    F, V = mesh.faces, mesh.vertices
    projs = {}
    for _ in range(max_pass):
        c1 = free[adj[:, 0]] & ~free[adj[:, 1]] & (labels[adj[:, 1]] >= 0)
        c2 = free[adj[:, 1]] & ~free[adj[:, 0]] & (labels[adj[:, 0]] >= 0)
        t = np.r_[adj[c1, 0], adj[c2, 1]]
        b = np.r_[labels[adj[c1, 1]], labels[adj[c2, 0]]]
        if len(t) == 0:
            break
        best_d = np.full(len(labels), np.inf)
        best_l = np.full(len(labels), -1)
        for bl in np.unique(b):
            tt = np.unique(t[b == bl])
            C = mesh.triangles_center[tt]
            if prims[bl] is not None:
                dv = np.abs(_prim_dev(prims[bl], C))
            else:
                if bl not in projs:
                    projs[bl] = _Proj(surfs[bl])
                dv = np.linalg.norm(projs[bl].batch(C) - C, axis=1)
            upd = dv < best_d[tt]
            best_d[tt[upd]] = dv[upd]; best_l[tt[upd]] = bl
        ok = np.where(best_l >= 0)[0]
        if len(ok) == 0:
            break
        labels[ok] = best_l[ok]
        free[ok] = False


RELAX_NDOT = np.cos(np.radians(6.0))   # normal del triángulo vs normal de la primitiva


def _relax_to_primitives(mesh, labels, prims, ff_tol, max_pass=400, locked=()):
    """Triángulos de borde de zonas NO primitivas (B-spline/facetas) que encajan
    exactos en una primitiva vecina (vértices a <= tight y normal alineada) pasan a ella,
    anillo a anillo. Devuelve las etiquetas no primitivas que han cambiado."""
    # con ruido (escaneo) los vértices no caen exactos: margen a la mitad de ff_tol
    tight = max(1e-3, 0.1 * ff_tol) if _NOISE["deg"] < 2 else 0.5 * ff_tol
    adj = mesh.face_adjacency
    F, V = mesh.faces, mesh.vertices
    isprim = np.array([p is not None for p in prims] + [False])   # índice -1 -> False
    lock = np.zeros(len(prims) + 1, bool)
    lock[list(locked)] = True
    movable = ~isprim & ~lock                       # B-spline/facetas no bloqueadas
    changed = set()
    for _ in range(max_pass):
        la, lb = labels[adj[:, 0]], labels[adj[:, 1]]
        diff = la != lb
        # candidato: (triángulo t de zona no primitiva, primitiva vecina b)
        c1 = diff & movable[la] & isprim[lb]
        c2 = diff & movable[lb] & isprim[la]
        t = np.r_[adj[c1, 0], adj[c2, 1]]
        b = np.r_[lb[c1], la[c2]]
        if len(t) == 0:
            break
        moved = 0
        for bl in np.unique(b):
            tt = np.unique(t[b == bl])
            tt = tt[movable[labels[tt]]]
            if len(tt) == 0:
                continue
            p = prims[bl]
            dv = _prim_dev(p, V[F[tt]].reshape(-1, 3)).reshape(-1, 3).max(1)
            # También la distancia de los centroides, no solo los vértices.
            if __import__("os").environ.get("VISOR_CENTROID_GATE") == "1":
                dc = _prim_dev(p, mesh.triangles_center[tt])
                dv = np.maximum(dv, dc)
            nd = _prim_ndot(p, mesh.triangles_center[tt], mesh.face_normals[tt])
            ok = tt[(dv <= tight) & (nd >= np.cos(np.radians(_ang(6.0))))]
            if len(ok):
                changed.update(int(x) for x in np.unique(labels[ok]))
                labels[ok] = bl
                moved += len(ok)
        if moved == 0:
            break
    return changed


def _surface_samples(mesh, faces, step):
    """Vértices + puntos de la superficie de malla (triángulos largos subdivididos)."""
    import trimesh
    sv, sf = trimesh.remesh.subdivide_to_size(mesh.vertices, mesh.faces[faces], step)
    return np.unique(np.round(sv[np.unique(sf.ravel())], 9), axis=0)


def _cubic_uniform_w(t):
    """Pesos de los 4 polos de un tramo de B-spline cúbica uniforme (t en [0,1))."""
    t2, t3 = t * t, t * t * t
    return np.stack([(1 - t) ** 3 / 6, (3 * t3 - 6 * t2 + 4) / 6,
                     (-3 * t3 + 3 * t2 + 3 * t + 1) / 6, t3 / 6], axis=1)


def _fit_ring(mesh, faces, axis, q, tol):
    """UNA B-spline periódica en θ para una banda que da la vuelta completa alrededor de
    un eje (el redondeo entre un tubo y una base: el detector lo trocea en toros de radios
    distintos porque con el tubo inclinado no es un toro exacto). Coordenadas cilíndricas
    (θ, ρ, z) y perfil girado α∈{0,45,90,135}° en el plano (ρ,z) -> parámetro s a lo largo
    del perfil; se ajustan los polos 3D por mínimos cuadrados con base periódica (θ) ×
    cúbica anclada (s) y regularización suave. Devuelve Geom_BSplineSurface o None."""
    from OCP.Geom import Geom_BSplineSurface
    from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
    from scipy.interpolate import BSpline
    a = axis / np.linalg.norm(axis)
    e1, e2 = _perp(a)
    diag = float(np.linalg.norm(np.ptp(mesh.vertices[mesh.faces[faces].ravel()], 0)))
    S = _surface_samples(mesh, faces, diag / 80.0)
    V = mesh.vertices[np.unique(mesh.faces[faces].ravel())]
    def cyl(P):
        d = P - q
        z = d @ a
        r = d - np.outer(z, a)
        return np.arctan2(r @ e2, r @ e1), np.linalg.norm(r, axis=1), z
    th, rho, z = cyl(S)
    # vuelta COMPLETA (si no, el camino normal de B-spline/bisección ya vale)
    srt = np.sort(np.mod(th, 2 * np.pi))
    if np.max(np.diff(np.r_[srt, srt[0] + 2 * np.pi])) > np.radians(25):
        return None
    import scipy.sparse as sps
    from scipy.sparse.linalg import spsolve
    if len(S) > 60000:                                   # muestreo acotado (moleteados)
        S = S[np.random.default_rng(0).choice(len(S), 60000, replace=False)]
        th, rho, z = cyl(S)
    thv, rhov, zv = cyl(V)
    kx = 3

    def design(thq, sq, nth, ncs, tv, lo, hi):
        """Matriz DISPERSA: base cúbica uniforme periódica en θ × cúbica anclada en s
        (16 no nulos por fila; con la densa un moleteado pedía cientos de MB)."""
        x = np.mod(thq, 2 * np.pi) / (2 * np.pi) * nth
        i0 = np.floor(x).astype(int); wt = _cubic_uniform_w(x - i0)
        Ms = BSpline.design_matrix(np.clip(sq, lo, hi - 1e-12), tv, kx).tocoo()
        r, c, v = Ms.row, Ms.col, Ms.data
        rows = np.concatenate([r] * 4)
        cols = np.concatenate([np.mod(i0[r] + k, nth) * ncs + c for k in range(4)])
        vals = np.concatenate([wt[r, k] * v for k in range(4)])
        return sps.csr_matrix((vals, (rows, cols)), shape=(len(thq), nth * ncs))

    def second_diff(n, cyclic):
        e = np.ones(n)
        D = sps.diags([e[:-1], -2 * e, e[:-1]], [-1, 0, 1], shape=(n, n), format="lil")
        if cyclic:
            D[0, n - 1] = 1; D[n - 1, 0] = 1
        else:
            D = D[1:-1]
        return sps.csr_matrix(D)

    def solve(alpha, nth, ns):
        ca, sa = np.cos(alpha), np.sin(alpha)
        s, sv_ = rho * ca + z * sa, rhov * ca + zv * sa
        lo, hi = float(s.min()), float(s.max())
        m = 0.05 * (hi - lo) + 1e-3
        lo, hi = lo - m, hi + m
        tv = np.r_[[lo] * 4, np.linspace(lo, hi, ns - 2)[1:-1], [hi] * 4]
        ncs = len(tv) - kx - 1
        if nth * ncs > len(S) / 3:
            return None
        A = design(th, s, nth, ncs, tv, lo, hi)
        # regularización: segundas diferencias de los polos en θ y en s (rellena huecos)
        lam = 1e-3 * np.sqrt(len(S) / (nth * ncs))
        Rt = sps.kron(second_diff(nth, True), sps.identity(ncs))
        Rs = sps.kron(sps.identity(nth), second_diff(ncs, False)) if ncs > 2 else None
        N = A.T @ A + lam ** 2 * (Rt.T @ Rt + (Rs.T @ Rs if Rs is not None else 0))
        C = spsolve(sps.csc_matrix(N), A.T @ S)
        C = np.asarray(C).reshape(nth * ncs, 3)
        res = np.linalg.norm(A @ C - S, axis=1)
        resv = np.linalg.norm(design(thv, sv_, nth, ncs, tv, lo, hi) @ C - V, axis=1)
        e95 = max(float(np.percentile(res, 95)), float(resv.max()) / 1.5)
        return (e95, C, nth, ncs, tv)

    # 1) la orientación del perfil que mejor describe la banda, con resolución media
    alphas = np.radians([45.0, 135.0, 0.0, 90.0])
    trial = [(solve(al, 32, 6), al) for al in alphas]
    trial = [(r, al) for r, al in trial if r is not None]
    if not trial:
        return None
    best, alpha = min(trial, key=lambda t: t[0][0])
    if best[0] > 8 * tol:
        return None              # sin arreglo a resolución media (en torni: 322 s perdidos)
    # 2) refinar ESA orientación hasta la tolerancia (un moleteado pide cientos de polos en θ)
    if best[0] > tol:
        for nth, ns in ((48, 8), (64, 10), (96, 10), (128, 12), (192, 12), (256, 14), (384, 14)):
            r = solve(alpha, nth, ns)
            if r is None:
                break
            stalled = r[0] > 0.9 * best[0]
            if r[0] < best[0]:
                best = r
            if best[0] <= tol or stalled:
                break
    e95, C, nth, ncs, tv = best
    if e95 > tol:
        return None
    poles = TColgp_Array2OfPnt(1, nth, 1, ncs)
    for i in range(nth):
        for j in range(ncs):
            poles.SetValue(i + 1, j + 1, _P(C[i * ncs + j]))
    uk = TColStd_Array1OfReal(1, nth + 1); um = TColStd_Array1OfInteger(1, nth + 1)
    for i in range(nth + 1):
        uk.SetValue(i + 1, float(i)); um.SetValue(i + 1, 1)
    dist = np.r_[tv[0], tv[4:-4], tv[-1]]
    vk = TColStd_Array1OfReal(1, len(dist)); vm = TColStd_Array1OfInteger(1, len(dist))
    for i, val in enumerate(dist):
        vk.SetValue(i + 1, float(val)); vm.SetValue(i + 1, 4 if i in (0, len(dist) - 1) else 1)
    try:
        return Geom_BSplineSurface(poles, uk, vk, um, vm, 3, 3, True, False)
    except Exception:
        return None


def _fit_axisymmetric_ring(mesh, faces, axis, q, tol):
    """Ajusta una banda 3D de revolución desde SU perfil STL medido.

    Solo se acepta si los radios coinciden angularmente para cada cota axial.
    No idealiza ni transforma cilindros: usa un perfil cúbico, que puede variar
    con la altura y recupera formas abombadas reales como las del tirante.
    """
    from OCP.Geom import Geom_SurfaceOfRevolution
    from OCP.GeomAPI import GeomAPI_Interpolate
    from OCP.gp import gp_Ax1, gp_Dir
    from OCP.TColgp import TColgp_HArray1OfPnt
    from scipy.interpolate import PchipInterpolator
    a = np.asarray(axis, float); a /= np.linalg.norm(a)
    q = np.asarray(q, float)
    V = mesh.vertices[np.unique(mesh.faces[faces].ravel())]
    d = V - q; z = d @ a
    r = np.linalg.norm(d - np.outer(z, a), axis=1)
    if np.min(r) < 0.1 or np.ptp(z) < 0.2:
        return None
    # Agrupar cotas de anillos completos: rechazo si el perfil varía con el ángulo.
    zr = np.round(z, 3)
    uniq, inv = np.unique(zr,return_inverse=True)
    levels=[]
    for i in range(len(uniq)):
        mask=inv == i
        if mask.sum() < 6: continue
        rv = r[mask]; levels.append((float(np.median(z[mask])), float(np.median(rv)),float(np.max(abs(rv-np.median(rv))))))
    if len(levels)<7 or max(k[2] for k in levels) > 0.35 * tol:
        return None
    levels=np.array(levels)
    levels=levels[np.argsort(levels[:,0])]
    if np.any(np.diff(levels[:,0])<0.001):
        return None
    # Interpolación monoforme del perfil para evitar ondulaciones entre muestras.
    f=PchipInterpolator(levels[:,0],levels[:,1],extrapolate=False)
    zgrid=np.linspace(levels[0,0],levels[-1,0],max(80,4*len(levels)))
    rg=f(zgrid)
    # Validación independiente del ajuste numérico contra TODOS los vértices de la región
    if np.max(np.abs(f(np.clip(z,levels[0,0],levels[-1,0]))-r)) > max(0.5*tol,0.001):
        return None
    e1,_ = _perp(a)
    h=TColgp_HArray1OfPnt(1,len(zgrid))
    for j,(zz,rr) in enumerate(zip(zgrid,rg),1):
        h.SetValue(j,_P(q + zz*a + rr*e1))
    try:
        interp=GeomAPI_Interpolate(h,False,1e-8)
        interp.Perform()
        if not interp.IsDone():return None
        surf=Geom_SurfaceOfRevolution(interp.Curve(), gp_Ax1(_P(q),gp_Dir(*map(float,a))))
        return surf
    except Exception:
        return None


def _merge_rings(mesh, labels, prims, surfs, tol, locked=()):
    """Grupos de regiones curvas vecinas (toros, B-splines, esferas) que juntos dan la
    vuelta a un eje -> UNA cara (`_fit_ring`). El eje sale de una primitiva de revolución
    vecina (el tubo) o, si no hay, de la estimación robusta de `meshfit_nurbs`."""
    from OCP.Geom import Geom_BSplineSurface
    nb = _region_neighbors(mesh, labels)
    G = _groups(labels)
    def curvy(l):
        if l < 0 or l in locked:
            return False
        p = prims[l]
        if p is None:
            return isinstance(surfs[l], Geom_BSplineSurface)
        return p["type"] in ("torus", "sphere")
    cand = [int(l) for l in np.unique(labels) if curvy(int(l))]
    seen, groups = set(), []
    for l in cand:
        if l in seen:
            continue
        stack, g = [l], []
        seen.add(l)
        while stack:
            x = stack.pop(); g.append(x)
            for y in nb.get(x, ()):
                if y not in seen and curvy(y):
                    seen.add(y); stack.append(y)
        if len(g) >= 2:
            groups.append(g)
    nxt_id = None
    for g in groups:
        faces = np.concatenate([G[x] for x in g])
        if len(faces) < 30 or np.linalg.norm(mesh.face_normals[faces].mean(0)) > 0.8:
            continue
        axes = []
        for l in g:
            for b in nb.get(l, ()):
                p = prims[b] if b >= 0 else None
                if p is not None and p["type"] in ("cylinder", "cone"):
                    pt = p.get("point", p.get("origin"))
                    axes.append((np.asarray(p["axis"], float), np.asarray(pt, float)))
        try:
            from meshfit_nurbs import _cyl_frame
            V = mesh.vertices[np.unique(mesh.faces[faces].ravel())]
            fr = _cyl_frame(V, mesh.face_normals[faces], mesh.area_faces[faces])
            axes.append((fr[0], fr[1]))
        except Exception:
            pass
        for ax, pt in axes:
            # Primero probar perfil radial medido: una sola superficie suave sin
            # parches por cuadrantes. Solo para bandas realmente axisimétricas.
            surf = _fit_axisymmetric_ring(mesh, faces, ax, pt, tol)
            if surf is None:
                surf = _fit_ring(mesh, faces, ax, pt, tol)
            if surf is not None:
                l0 = g[0]
                labels[faces] = l0
                surfs[l0] = surf; prims[l0] = None
                break


def _upgrade_freeform(mesh, labels, surfs, prims, tol, locked=()):
    """Superficies libres (B-spline) que en realidad son una PRIMITIVA: se prueban plano /
    cilindro / cono / esfera / toro, libres y sobre los ejes de revolución de la pieza,
    con ajuste geométrico fino; si una contiene ≥97 % de los triángulos, la sustituye
    (el redondeo de un extremo de P1, 20 846 triángulos, quedaba como B-spline porque el
    crecimiento no llegó a sembrarlo)."""
    from OCP.Geom import Geom_BSplineSurface
    import meshfit_grow as MG
    G = _groups(labels)
    cand = [l for l, f in G.items()
            if l >= 0 and l not in locked and prims[l] is None
            and isinstance(surfs[l], Geom_BSplineSurface) and len(f) >= 50]
    if not cand:
        return 0
    g = MG._Grower(mesh, tol, np.cos(np.radians(_ang(12.0))))
    axes = MG.global_axes(mesh, np.arange(len(mesh.faces)), tol) if len(mesh.faces) >= 2000 else []
    n = 0
    for l in cand:
        f = G[l]
        best = None
        for ty in ("plane", "cylinder", "cone", "sphere", "torus"):
            for ax in [None] + (axes if ty != "plane" else []):
                p = g.fit(ty, f, ax)
                if p is None or (ty == "torus" and not (p["R"] > p["r"] > 0)):
                    continue
                okf = float(g.ok(p, f).mean())
                # además el resto no puede quedar lejos (Cuerpo218: 3 % fuera dejaba
                # aristas de 3 mm de tolerancia)
                if okf >= 0.97 and float(g.ok(p, f, 3 * tol).mean()) < 0.995:
                    continue
                if okf >= 0.97 and (best is None or okf > best[0]):
                    best = (okf, p)
        if best is not None:
            p = dict(best[1]); p.pop("_ax", None)
            s = _prim_surface(p)
            if s is not None:
                surfs[l] = s; prims[l] = _prim_arrays(p); n += 1
    return n


def _merge_bspline_clusters(mesh, labels, surfs, prims, tol, locked=(), max_faces=400):
    """Racimos de B-splines pequeñas VECINAS (esquinas donde se cruzan redondeos: 100
    trocitos de <1 mm² en P1) -> una sola si la unión se ajusta dentro de tolerancia."""
    from OCP.Geom import Geom_BSplineSurface
    def is_bs(l):
        return (l >= 0 and l not in locked and prims[l] is None
                and isinstance(surfs[l], Geom_BSplineSurface))
    for _ in range(4):
        merged = 0
        nb = _region_neighbors(mesh, labels)
        G = _groups(labels)
        sizes = {l: len(f) for l, f in G.items()}
        small = sorted([l for l in sizes if is_bs(l) and sizes[l] <= max_faces],
                       key=lambda l: sizes[l])
        gone = set()
        for l in small:
            if l in gone or sizes.get(l, 0) == 0:
                continue
            for b in sorted(nb.get(l, ()), key=lambda x: -sizes.get(x, 0)):
                if b in gone or not is_bs(b):
                    continue
                union = np.r_[G[l], G[b]]
                s, ok = _fit_bspline(mesh, union, tol)
                if ok:
                    labels[G[l]] = b
                    G[b] = union; G[l] = G[l][:0]
                    surfs[b] = s
                    sizes[b] = sizes.get(b, 0) + sizes[l]; sizes[l] = 0
                    gone.add(l); merged += 1
                    break
        if merged == 0:
            break


def _groups(labels):
    """etiqueta -> índices de sus triángulos, en O(N log N) (buscar `labels == l` dentro
    de bucles sobre 1200 regiones de torni eran cientos de millones de comparaciones)."""
    order = np.argsort(labels, kind="stable")
    sl = labels[order]
    cuts = np.flatnonzero(np.diff(sl)) + 1
    return {int(sl[a]): order[a:b] for a, b in zip(np.r_[0, cuts], np.r_[cuts, len(sl)])}


def _region_neighbors(mesh, labels):
    """dict etiqueta -> set de etiquetas vecinas (comparten arista de malla)."""
    adj = mesh.face_adjacency
    la, lb = labels[adj[:, 0]], labels[adj[:, 1]]
    d = la != lb
    nb = {}
    for a, b in zip(la[d], lb[d]):
        nb.setdefault(int(a), set()).add(int(b)); nb.setdefault(int(b), set()).add(int(a))
    return nb


def _fits(mesh, ft, l, prims, surfs, tol, ndot_min, med_tol=None):
    """¿La superficie de la región `l` contiene los triángulos `ft`? -> desviación o None.
    `med_tol`: además, la desviación MEDIANA debe quedar por debajo (misma superficie con
    ruido de teselado en el borde vs. superficie realmente distinta)."""
    F, V = mesh.faces, mesh.vertices
    pts = V[np.unique(F[ft].ravel())]
    if len(ft) <= 3:          # astilla: la normal de un triángulo largo no es fiable
        ndot_min = min(ndot_min, np.cos(np.radians(40)))
    if prims[l] is not None:
        # Un vértice puede pertenecer a un cilindro incluso si su cara plana
        # no lo hace (secciones hexagonales). Comprobar puntos interiores.
        chkpts = np.vstack([pts, mesh.triangles_center[ft]]) if __import__("os").environ.get("VISOR_CENTROID_GATE") == "1" else pts
        dvs = _prim_dev(prims[l], chkpts)
        dv = float(dvs.max())
        if dv > tol or (med_tol is not None and float(np.median(dvs)) > med_tol):
            return None
        nd = float(_prim_ndot(prims[l], mesh.triangles_center[ft], mesh.face_normals[ft]).min())
        return dv if nd >= ndot_min else None
    # B-spline / faceta: proyección (muestreo) + normal por la superficie
    pr = _Proj(surfs[l])
    chk = np.vstack([pts, mesh.triangles_center[ft]])
    if len(chk) > 80:
        chk = chk[np.linspace(0, len(chk) - 1, 80).astype(int)]
    dv = 0.0
    for q in chk:
        r, _ = pr(q)
        if r is None:
            return None
        dv = max(dv, float(np.linalg.norm(r - q)))
        if dv > tol:
            return None
    k = ft[np.argmax(mesh.area_faces[ft])]
    nn = pr.normal(mesh.triangles_center[k])
    if nn is None or abs(float(nn @ mesh.face_normals[k])) < ndot_min:
        return None
    return dv


def _merge_regions(mesh, labels, prims, surfs, ff_tol, max_faces=12, locked=()):
    """Menos parches donde la geometría es la MISMA (2º reporte de Rafa en Fusion):
      a) primitivas VECINAS iguales se funden (el tubo del soporte salía en 3 cilindros
         R=10 coaxiales -> 1 cara);
      b) regiones diminutas (≤ max_faces triángulos o < 0.2 % del área) se funden con la
         vecina —primitiva o B-spline— que las contiene dentro de tolerancia (astillas de
         0.1–0.8 mm² en el redondeo)."""
    total = float(mesh.area)
    tight = max(1e-3, 0.2 * ff_tol)
    for _ in range(4):
        merged = 0
        nb = _region_neighbors(mesh, labels)
        G = _groups(labels)
        area = {l: float(mesh.area_faces[f].sum()) for l, f in G.items()}
        # a) primitivas iguales: la grande absorbe a la vecina si la contiene exacta
        for l in sorted(area, key=lambda x: -area[x]):
            if l < 0 or prims[l] is None or area.get(l, 0) == 0:
                continue
            for b in sorted(nb.get(l, ()), key=lambda x: -area.get(x, 0)):
                if b < 0 or b == l or prims[b] is None or area.get(b, 0) == 0:
                    continue
                if prims[b]["type"] != prims[l]["type"]:
                    continue
                fb = G[b]
                if _fits(mesh, fb, l, prims, surfs, 0.6 * ff_tol, np.cos(np.radians(_ang(10.0))),
                         med_tol=tight * 0.5) is not None:
                    labels[fb] = l
                    G[l] = np.r_[G[l], fb]; G[b] = fb[:0]
                    area[l] += area[b]; area[b] = 0
                    merged += 1
        nb = _region_neighbors(mesh, labels)
        G = _groups(labels)
        # b) astillas
        small = [l for l, f in G.items()
                 if l >= 0 and l not in locked and (len(f) <= max_faces or area.get(l, 0) < 0.002 * total)]
        small.sort(key=lambda l: area.get(l, 0))
        for l in small:
            ft = G.get(l, np.zeros(0, int))
            if len(ft) == 0:
                continue
            best = None
            for b in nb.get(l, ()):
                if b < 0 or b == l or len(G.get(b, ())) == 0:
                    continue
                dv = _fits(mesh, ft, b, prims, surfs, 0.5 * ff_tol, np.cos(np.radians(_ang(15.0))))
                if dv is not None:
                    key = (prims[b] is None, dv)          # mejor primitiva, luego la más ceñida
                    if best is None or key < best[0]:
                        best = (key, b)
            if best is not None:
                labels[ft] = best[1]
                G[best[1]] = np.r_[G[best[1]], ft]; G[l] = ft[:0]
                merged += 1
        if merged == 0:
            break


def _snap(mesh, chains, corner, comp_surf, projs, max_move, start=None):
    """Posición de cada vértice de frontera: proyección alternada sobre las superficies
    de las regiones que toca (converge a la intersección). `start`: posiciones de partida
    por vértice (fronteras alisadas de las piezas orgánicas); el resto, la malla."""
    vset = {}
    for ch in chains.values():
        a, b = ch["pair"]
        for v in ch["verts"]:
            vset.setdefault(v, set()).update([a, b])
    pos = {}
    # por LOTES: vértices agrupados por el conjunto de superficies que tocan
    groups = {}
    for v, labs in vset.items():
        groups.setdefault(tuple(sorted(l for l in labs if l >= 0)), []).append(v)
    for labs, vs in groups.items():
        vs = np.array(vs)
        P0 = mesh.vertices[vs].astype(float)
        if start:
            for i, v in enumerate(vs.tolist()):
                if v in start:
                    P0[i] = start[v]
        P = P0.copy()
        for _ in range(6 if len(labs) > 1 else 1):
            for l in labs:
                P = projs[l].batch(P)
        far = np.linalg.norm(P - P0, axis=1) > max_move
        P[far] = P0[far]
        for v, p in zip(vs.tolist(), P):
            pos[v] = p
    return pos


def _smooth_chains(mesh, chains, length):
    """Fronteras entre parches ORGÁNICOS: siguen aristas de malla y salen en zigzag (de
    medio triángulo). Media móvil a lo largo de cada cadena (ventana ~`length` mm, que se
    estrecha hacia los extremos: las esquinas no se mueven). Devuelve {vértice: punto}."""
    V = mesh.vertices
    out = {}
    for ch in chains.values():
        vs = ch["verts"]
        n = len(vs)
        if n < 5:
            continue
        P = V[vs].astype(float)
        seg = float(np.linalg.norm(np.diff(P, axis=0), axis=1).mean()) or 1.0
        k = int(round(0.5 * length / seg))
        if k < 1:
            continue
        if ch["closed"]:
            Pe = np.vstack([P[-k:], P, P[:k]])
            cs = np.vstack([np.zeros((1, 3)), np.cumsum(Pe, axis=0)])
            S = (cs[2 * k + 1:] - cs[:-2 * k - 1]) / (2 * k + 1)
            idx = range(n)
        else:
            cs = np.vstack([np.zeros((1, 3)), np.cumsum(P, axis=0)])
            i = np.arange(n)
            hw = np.minimum(np.minimum(i, n - 1 - i), k)
            S = (cs[i + hw + 1] - cs[i - hw]) / (2 * hw + 1)[:, None]
            idx = range(1, n - 1)
        for j in idx:
            out[vs[j]] = S[j]
    return out


def _detalle_brep(porcentaje, fase):
    # Etapas REALES de OpenCascade; el indicador no depende del tiempo transcurrido.
    try:
        from avance_conversion import avance
        avance(porcentaje, fase)
    except ImportError:
        pass


def _build(mesh, labels, comp_surf, tol, max_move, smooth_len=0.0):
    import os, time as _tm
    _T = os.environ.get("MF_TIMING"); _t = _tm.time()
    _detalle_brep(57, f'Preparando {len(comp_surf)} superficies CAD para construir el B-Rep')
    projs = {l: _Proj(s) for l, s in comp_surf.items()}
    if _T: print(f"    _build: proyectores {_tm.time() - _t:.1f}s ({len(projs)})"); _t = _tm.time()
    _detalle_brep(59, f'Extrayendo fronteras entre {len(comp_surf)} regiones')
    chains, loops, corner = _boundary_chains(mesh, labels)
    if _T: print(f"    _build: cadenas {_tm.time() - _t:.1f}s ({len(chains)})"); _t = _tm.time()
    start = _smooth_chains(mesh, chains, smooth_len) if smooth_len > 0 else None
    _detalle_brep(61, f'Proyectando contornos ({len(chains)} cadenas de aristas)')
    pos = _snap(mesh, chains, corner, comp_surf, projs, max_move, start=start)
    protected=getattr(mesh,'vertices_protegidos',set())
    if protected:
        for v in pos:
            if v in protected:pos[v]=mesh.vertices[v].copy()
    if _T: print(f"    _build: snap {_tm.time() - _t:.1f}s ({len(pos)} vértices)"); _t = _tm.time()
    B = BRep_Builder()
    vshape = {}

    def vertex(v):
        if v not in vshape:
            V = TopoDS_Vertex()
            B.MakeVertex(V, _P(pos[v]), 1e-8 if v in protected else 1e-6)
            vshape[v] = V
        return vshape[v]

    eshape = {}
    diag = float(np.linalg.norm(mesh.extents))
    step = diag / 150.0
    _etimes = []
    _detalle_brep(63, f'Construyendo {len(chains)} curvas de arista CAD')
    for i_ch, (key, ch) in enumerate(chains.items()):
        if i_ch and i_ch % max(1, len(chains)//4) == 0:
            _detalle_brep(min(67, 63+int(4*i_ch/max(1,len(chains)))),
                          f'Aristas B-Rep: {i_ch}/{len(chains)}')
        _te0 = _tm.time()
        P = np.array([pos[v] for v in ch["verts"]])
        if ch["closed"]:
            P = np.vstack([P, P[:1]])
        # DENSIFICAR: en CAD los vértices de frontera pueden estar a 10+ mm; la curva
        # entre ellos debe seguir la INTERSECCIÓN real de las dos superficies, no la
        # cuerda -> puntos intermedios proyectados alternando sobre ambas
        la, lb = ch["pair"]
        pl = [projs[l] for l in (la, lb) if l in projs]
        # entre dos PLANOS la intersección es la recta entre vértices: nada que densificar
        plane2 = len(pl) == 2 and all(isinstance(comp_surf[l], Geom_Plane) for l in (la, lb))
        if plane2:
            # puntos interiores sobre la RECTA de intersección exacta (los vértices de
            # esquina quedan en un compromiso entre 3+ superficies y no son colineales)
            def _pl(g):
                pp = g.Pln(); n_ = pp.Axis().Direction(); o_ = pp.Location()
                return np.array([n_.X(), n_.Y(), n_.Z()]), np.array([o_.X(), o_.Y(), o_.Z()])
            n1, o1 = _pl(comp_surf[la]); n2, o2 = _pl(comp_surf[lb])
            dl = np.cross(n1, n2)
            if np.linalg.norm(dl) < np.sin(np.radians(5)):
                # casi coplanarios (el mismo plano partido en dos): la recta de
                # intersección está mal condicionada -> camino general
                plane2 = False
            else:
                dl /= np.linalg.norm(dl)
                A3 = np.array([n1, n2, dl]); b3 = np.array([n1 @ o1, n2 @ o2, dl @ P.mean(0)])
                p0l = np.linalg.solve(A3, b3)
                inner = P[1:-1]
                if len(inner):
                    P = np.vstack([P[:1], p0l + np.outer((inner - p0l) @ dl, dl), P[-1:]])
        dense = [P[0]]
        if not plane2 and len(P) > 1:
            # puntos de cuerda de todos los tramos de golpe, proyectados por LOTES
            seglen = np.linalg.norm(np.diff(P, axis=0), axis=1)
            ks = np.clip(np.ceil(seglen / step), 1, 16).astype(int)
            Q0, owner, lims = [], [], []
            for i, k in enumerate(ks):
                for t in np.arange(1, k) / k:
                    Q0.append(P[i] + t * (P[i + 1] - P[i])); owner.append(i)
                    # el punto de cuerda puede distar de la curva real hasta su flecha
                    lims.append(max(max_move, 0.5 * seglen[i]))
            if Q0:
                Q0 = np.array(Q0); Q = Q0.copy()
                nit = 8 if any(pr.kind for pr in pl) else 3      # 2 libres: caro, menos vueltas
                for _ in range(nit):
                    for pr in pl:
                        Q = pr.batch(Q)
                bad = np.linalg.norm(Q - Q0, axis=1) > np.array(lims)
                Q[bad] = Q0[bad]
                owner = np.array(owner)
            for i in range(len(P) - 1):
                if len(Q0):
                    dense.extend(Q[owner == i])
                dense.append(P[i + 1])
        P = P if plane2 else np.array(dense)
        crv = None
        if plane2 and not ch["closed"] and np.linalg.norm(P[-1] - P[0]) > 1e-6:
            # entre dos planos la arista ES un segmento (los extremos pueden distar unas
            # centésimas de la recta exacta: lo absorbe la tolerancia)
            seg = GC_MakeSegment(_P(P[0]), _P(P[-1])).Value()
            crv, p0, p1 = seg, seg.FirstParameter(), seg.LastParameter()
        if crv is None:
            # ROBUSTEZ (escaneos con ruido: dos esquinas proyectadas al mismo punto tumbaban
            # el sólido entero): ajuste normal -> polilínea exacta -> posiciones de malla
            P_mesh = mesh.vertices[ch["verts"]].astype(float)
            if ch["closed"]:
                P_mesh = np.vstack([P_mesh, P_mesh[:1]])
            for cand in (P, P_mesh):
                try:
                    crv, p0, p1 = _edge_curve(cand, ch["closed"], tol)
                    break
                except Exception:
                    try:
                        if np.linalg.norm(np.diff(cand, axis=0), axis=1).sum() > 1e-6:
                            keep = np.r_[True, np.linalg.norm(np.diff(cand, axis=0), axis=1) > 1e-9]
                            crv, p0, p1 = _polyline_curve(cand[keep])
                            break
                    except Exception:
                        pass
            if crv is None:
                raise ValueError("arista degenerada")
        E = TopoDS_Edge()
        B.MakeEdge(E, crv, 1e-6)
        V0 = vertex(ch["verts"][0])
        V1 = V0 if ch["closed"] else vertex(ch["verts"][-1])
        B.Add(E, V0.Oriented(TopAbs_FORWARD))
        B.Add(E, V1.Oriented(TopAbs_REVERSED))
        B.Range(E, p0, p1)
        # tolerancias de vértice: lo que distan de la curva en sus extremos
        a = crv.Value(p0); b = crv.Value(p1)
        B.UpdateVertex(V0, max(1e-6, 1.01 * a.Distance(_P(pos[ch["verts"][0]]))))
        B.UpdateVertex(V1, max(1e-6, 1.01 * b.Distance(_P(pos[ch["verts"][-1]]))))
        eshape[key] = E
        if _T: _etimes.append((round(_tm.time() - _te0, 2), len(ch["verts"]), type(comp_surf.get(ch["pair"][0])).__name__[5:9], type(comp_surf.get(ch["pair"][1])).__name__[5:9]))

    _detalle_brep(68, f'Aristas completas; ensamblando {len(loops)} caras CAD')
    faces = {}
    _ftimes = []
    if _T: print(f"    _build: aristas {_tm.time() - _t:.1f}s; más lentas: {sorted(_etimes, reverse=True)[:4]}"); _t = _tm.time()
    for l, lps in loops.items():
        _tf0 = _tm.time()
        surf = comp_surf[l]
        fidx = np.where(labels == l)[0]
        # ¿la normal de la superficie apunta hacia fuera (como la malla)? VOTACIÓN entre los
        # triángulos más grandes (uno solo podía ser una astilla de 30 mm de normal poco fiable)
        ks = fidx[np.argsort(-mesh.area_faces[fidx])[:30]]
        votes = 0.0
        for k in ks:
            nrm = projs[l].normal(mesh.triangles_center[k])
            if nrm is not None:
                votes += np.sign(float(nrm @ mesh.face_normals[k])) * mesh.area_faces[k]
        inward = votes < 0
        F = TopoDS_Face()
        B.MakeFace(F, surf, 1e-7)
        for lp in lps:
            W = TopoDS_Wire()
            B.MakeWire(W)
            for key, fwd in lp:
                E = eshape[key]
                B.Add(W, E.Oriented(TopAbs_FORWARD if fwd else TopAbs_REVERSED))
            B.Add(F, W.Reversed() if inward else W)
        faces[l] = F.Reversed() if inward else F
        if _T: _ftimes.append((_tm.time() - _tf0, l))
    if _T: print(f"    _build: caras {_tm.time() - _t:.1f}s; más lentas: {sorted(_ftimes, reverse=True)[:4]}")
    _detalle_brep(70, f'Caras ensambladas: {len(faces)}; creando shell')
    shell = TopoDS_Shell()
    B.MakeShell(shell)
    for F in faces.values():
        B.Add(shell, F)
    return shell, faces


def _free_edges(shape):
    m = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(shape, TopAbs_EDGE, TopAbs_FACE, m)
    n = 0
    for i in range(1, m.Extent() + 1):
        e = TopoDS.Edge_s(m.FindKey(i))
        if not BRep_Tool.Degenerated_s(e) and m.FindFromIndex(i).Size() < 2:
            n += 1
    return n


def _make_solid(fixed, cavidades_verificadas=False, contornos_compartidos=False):
    """shell arreglado -> sólido (o None)."""
    exp = TopExp_Explorer(fixed, TopAbs_SHELL)
    if not exp.More():
        return None
    if cavidades_verificadas:
        # Un sólido con huecos cerrados contiene varios shells orientados.
        # Agrupar por aristas compartidas, sin descartar paredes interiores.
        from OCP.TopTools import TopTools_IndexedMapOfShape
        faces=[];index=TopTools_IndexedMapOfShape();ex=TopExp_Explorer(fixed,TopAbs_FACE)
        while ex.More():
            face=TopoDS.Face_s(ex.Current());faces.append(face);index.Add(face);ex.Next()
        edge_faces=TopTools_IndexedDataMapOfShapeListOfShape()
        TopExp.MapShapesAndAncestors_s(fixed,TopAbs_EDGE,TopAbs_FACE,edge_faces)
        parent=list(range(len(faces)))
        def root(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
            return i
        for ei in range(1,edge_faces.Extent()+1):
            adjacent=list(edge_faces.FindFromIndex(ei));ids=[]
            for face in adjacent:
                i=index.FindIndex(face)-1
                if i>=0:ids.append(i)
            for i in ids[1:]:parent[root(i)]=root(ids[0])
        groups={}
        for i,face in enumerate(faces):groups.setdefault(root(i),[]).append(face)
        builder=BRep_Builder();maker=BRepBuilderAPI_MakeSolid()
        for group in groups.values():
            shell=TopoDS_Shell();builder.MakeShell(shell)
            for face in group:builder.Add(shell,face)
            shell.Closed(True);maker.Add(shell)
        sol=maker.Solid()
    else:
        sol = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(exp.Current())).Solid()
    if contornos_compartidos:
        from fijacion_contornos import OrientarSolido
        sf=OrientarSolido(sol)
    else:sf = ShapeFix_Solid(sol)
    sf.Perform()
    result=sf.Solid()
    if contornos_compartidos:
        import cadquery as cq
        for edge in cq.Shape.cast(result).Edges():
            if not BRep_Tool.SameRange_s(edge.wrapped) or not BRep_Tool.SameParameter_s(edge.wrapped):
                BRepLib.SameRange_s(edge.wrapped,1e-10);BRepLib.SameParameter_s(edge.wrapped,1e-9,True)
        from planos_canonicos import canonizar_planos
        result,_=canonizar_planos(result)
    return result


def _face_label(mesh, labels, face, diag):
    """Región de malla a la que pertenece una cara B-rep (por puntos de su teselado:
    ShapeFix_Solid copia las caras y se pierde la identidad topológica)."""
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopLoc import TopLoc_Location
    from scipy.spatial import cKDTree
    P = []
    try:
        BRepMesh_IncrementalMesh(face, diag / 200.0, False, 0.5, True)
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(TopoDS.Face_s(face), loc)
        if tri is not None:
            tr = loc.Transformation()
            for i in range(1, tri.NbNodes() + 1):
                q = tri.Node(i).Transformed(tr); P.append((q.X(), q.Y(), q.Z()))
    except Exception:
        pass
    if not P:
        # plan B: una cara MALA a menudo no se deja teselar -> puntos de su superficie
        # dentro de sus límites UV que el clasificador da por interiores (o, si no, las
        # puntas de sus aristas)
        from OCP.BRepTools import BRepTools
        from OCP.BRepClass import BRepClass_FaceClassifier
        from OCP.TopAbs import TopAbs_IN
        from OCP.gp import gp_Pnt2d
        F = TopoDS.Face_s(face)
        S = BRep_Tool.Surface_s(F)
        try:
            u0, u1, v0, v1 = BRepTools.UVBounds_s(F)
            for u in np.linspace(u0, u1, 9)[1:-1]:
                for v in np.linspace(v0, v1, 9)[1:-1]:
                    cl = BRepClass_FaceClassifier(F, gp_Pnt2d(u, v), 1e-7)
                    if cl.State() == TopAbs_IN:
                        q = S.Value(u, v); P.append((q.X(), q.Y(), q.Z()))
        except Exception:
            pass
        if not P:
            ex = TopExp_Explorer(F, TopAbs_EDGE)
            while ex.More():
                from OCP.BRepAdaptor import BRepAdaptor_Curve
                c = BRepAdaptor_Curve(TopoDS.Edge_s(ex.Current()))
                q = c.Value(0.5 * (c.FirstParameter() + c.LastParameter()))
                P.append((q.X(), q.Y(), q.Z()))
                ex.Next()
        if not P:
            return None
    _, k = cKDTree(mesh.triangles_center).query(np.array(P))
    vals, cnt = np.unique(labels[k], return_counts=True)
    return int(vals[np.argmax(cnt)])


def _self_intersecting(face, prec=1e-4):
    """¿Algún contorno de la cara se cruza en el espacio de parámetros? (BRepCheck no lo
    ve: una pared del rebaje de P1 pasaba por válida y no se dejaba ni teselar)."""
    from OCP.ShapeAnalysis import ShapeAnalysis_Wire
    w = TopExp_Explorer(face, TopAbs_WIRE)
    while w.More():
        try:
            if ShapeAnalysis_Wire(TopoDS.Wire_s(w.Current()), TopoDS.Face_s(face),
                                  prec).CheckSelfIntersection():
                return True
        except Exception:
            pass
        w.Next()
    return False


def _fix_wire_intersections(shape, prec):
    """Aristas contiguas que se cruzan pasada su esquina común (dos curvas casi tangentes
    ajustadas por separado): ShapeFix_Wire.FixSelfIntersection, que la reparación general
    no activa. Devuelve (forma, nº de contornos tocados)."""
    from OCP.ShapeFix import ShapeFix_Wire
    from OCP.ShapeBuild import ShapeBuild_ReShape
    ctx = ShapeBuild_ReShape()
    n = 0
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        F = TopoDS.Face_s(ex.Current())
        w = TopExp_Explorer(F, TopAbs_WIRE)
        while w.More():
            W = TopoDS.Wire_s(w.Current())
            try:
                from OCP.ShapeAnalysis import ShapeAnalysis_Wire
                if ShapeAnalysis_Wire(W, F, prec).CheckSelfIntersection():
                    sfw = ShapeFix_Wire(W, F, prec)
                    sfw.SetContext(ctx)
                    if sfw.FixSelfIntersection():
                        ctx.Replace(W, sfw.Wire())
                        n += 1
            except Exception:
                pass
            w.Next()
        ex.Next()
    return (ctx.Apply(shape) if n else shape), n


def _bad_faces(shape):
    """Caras con cualquier estado de error en el análisis del sólido completo (incluye
    los fallos de orientación que el shell atribuye a una cara)."""
    from OCP.BRepCheck import BRepCheck_Status
    an = BRepCheck_Analyzer(shape)
    bad = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        f = exp.Current()
        r = an.Result(f)
        if r is not None and any(st != BRepCheck_Status.BRepCheck_NoError for st in r.Status()):
            bad.append(f)
        exp.Next()
    return bad


def _place_seams(mesh, labels, comp_surf):
    """Cada cara sobre superficie de REVOLUCIÓN (cilindro/cono/toro) que NO da la vuelta
    completa recibe su propia copia de la superficie con el origen angular (la COSTURA
    u=0) girado al centro del mayor hueco angular de la región: su recorte ya no cruza la
    costura (un cilindro con agujero cuyo recorte cruzaba u=0 daba 'IntersectingWires' y
    caras sin orientación en P1)."""
    from OCP.Geom import Geom_CylindricalSurface, Geom_ConicalSurface, Geom_ToroidalSurface
    from OCP.gp import gp_Ax3, gp_Dir
    for l in np.unique(labels):
        l = int(l)
        s = comp_surf.get(l)
        if not isinstance(s, (Geom_CylindricalSurface, Geom_ConicalSurface, Geom_ToroidalSurface)):
            continue
        fidx = np.where(labels == l)[0]
        ax = s.Axis()
        a = np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
        q = np.array([ax.Location().X(), ax.Location().Y(), ax.Location().Z()])
        d = mesh.vertices[np.unique(mesh.faces[fidx].ravel())] - q
        r = d - np.outer(d @ a, a)
        x0 = np.cross(a, [1.0, 0, 0] if abs(a[0]) < 0.9 else [0, 1.0, 0]); x0 /= np.linalg.norm(x0)
        y0 = np.cross(a, x0)
        th = np.sort(np.mod(np.arctan2(r @ y0, r @ x0), 2 * np.pi))
        gaps = np.diff(np.r_[th, th[0] + 2 * np.pi])
        k = int(np.argmax(gaps))
        if gaps[k] < np.radians(10):
            continue                          # vuelta completa: ShapeFix pone la costura
        mid = th[k] + gaps[k] / 2
        xd = np.cos(mid) * x0 + np.sin(mid) * y0
        pos = s.Position()
        loc = pos.Location()
        a3 = gp_Ax3(loc, gp_Dir(*map(float, a)), gp_Dir(*map(float, xd)))
        if isinstance(s, Geom_CylindricalSurface):
            comp_surf[l] = Geom_CylindricalSurface(a3, s.Radius())
        elif isinstance(s, Geom_ConicalSurface):
            comp_surf[l] = Geom_ConicalSurface(a3, s.SemiAngle(), s.RefRadius())
        else:
            comp_surf[l] = Geom_ToroidalSurface(a3, s.MajorRadius(), s.MinorRadius())


def _presplit_holed_rings(mesh, labels, comp_surf, ff_tol, *, completos=False):
    """Caras de revolución que dan la VUELTA COMPLETA y además tienen AGUJEROS (cilindro
    de P1: las dos cabezas unidas por detrás del rebaje) -> dos medias cañas desde el
    principio; luego `_place_seams` pone la costura de cada una en el hueco de la otra.
    Agujeros = característica de Euler χ = V − E + F < 0 (banda simple: χ = 0)."""
    from OCP.Geom import Geom_CylindricalSurface, Geom_ConicalSurface, Geom_ToroidalSurface
    nxt = int(labels.max()) + 1
    for l in [int(x) for x in np.unique(labels)]:
        s = comp_surf.get(l)
        if not isinstance(s, (Geom_CylindricalSurface, Geom_ConicalSurface, Geom_ToroidalSurface)):
            continue
        fidx = np.where(labels == l)[0]
        F = mesh.faces[fidx]
        E = np.unique(np.sort(np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], axis=1), axis=0)
        chi = len(np.unique(F.ravel())) - len(E) + len(F)
        if chi >= 0 and not (completos and isinstance(s,Geom_CylindricalSurface)):
            continue
        ax = s.Axis()
        a = np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
        q = np.array([ax.Location().X(), ax.Location().Y(), ax.Location().Z()])
        d = mesh.vertices[np.unique(F.ravel())] - q
        r = d - np.outer(d @ a, a)
        x0 = np.cross(a, [1.0, 0, 0] if abs(a[0]) < 0.9 else [0, 1.0, 0]); x0 /= np.linalg.norm(x0)
        th = np.sort(np.mod(np.arctan2(r @ np.cross(a, x0), r @ x0), 2 * np.pi))
        if np.max(np.diff(np.r_[th, th[0] + 2 * np.pi])) >= np.radians(10):
            continue                              # no da la vuelta: basta con la costura
        nxt = _split_region(mesh, labels, comp_surf, l, nxt, ff_tol)
    return nxt


def _split_region(mesh, labels, comp_surf, l, nxt, ff_tol, to_facets=False):
    """Parte la región `l` en dos mitades (mediana a lo largo de su eje principal).
    Primitivas: las mitades CONSERVAN la misma superficie (arregla anillos finos sin
    perder calidad). B-spline: cada mitad se reajusta con la suya (otro plano de
    proyección; si no ajusta, conserva la original). Muy pequeña o `to_facets` ->
    facetas. Devuelve el siguiente id libre."""
    from OCP.Geom import (Geom_BSplineSurface, Geom_CylindricalSurface, Geom_ConicalSurface,
                          Geom_ToroidalSurface)
    fidx = np.where(labels == l)[0]
    if len(fidx) >= 8 and not to_facets:
        cen = mesh.triangles_center[fidx]
        orig = comp_surf[l]
        if isinstance(orig, (Geom_CylindricalSurface, Geom_ConicalSurface, Geom_ToroidalSurface)):
            # superficie de REVOLUCIÓN: partir por ÁNGULO alrededor de su eje -> dos medias
            # cañas sin vuelta completa (los bucles de una cara periódica con agujeros se
            # cruzaban: 'IntersectingWires' en el cilindro principal de P1)
            ax = orig.Axis()
            a = np.array([ax.Direction().X(), ax.Direction().Y(), ax.Direction().Z()])
            q = np.array([ax.Location().X(), ax.Location().Y(), ax.Location().Z()])
            d = cen - q
            r = d - np.outer(d @ a, a)
            ru = r / (np.linalg.norm(r, axis=1, keepdims=True) + 1e-12)
            mdir = ru.mean(0)
            if np.linalg.norm(mdir) < 0.2:      # vuelta completa: cualquier referencia vale
                mdir = ru[0]
            e1 = mdir - (mdir @ a) * a
            e1 /= np.linalg.norm(e1) or 1.0
            th = np.arctan2(r @ np.cross(a, e1), r @ e1)   # ángulo respecto a la dirección media
            half = fidx[th > np.median(th)]               # mediana angular: dos mitades reales
        else:
            _, _, vt = np.linalg.svd(cen - cen.mean(0), full_matrices=False)
            pr = (cen - cen.mean(0)) @ vt[0]
            half = fidx[pr > np.median(pr)]
        if 0 < len(half) < len(fidx):
            sub = np.zeros(len(mesh.faces), int) - 1
            sub[fidx] = 0; sub[half] = 1
            comp = _split_connected(mesh, np.where(sub >= 0, sub, -2 - np.arange(len(sub))))
            is_bs = isinstance(orig, Geom_BSplineSurface)
            for j, k in enumerate(np.unique(comp[fidx])):
                part = fidx[comp[fidx] == k]
                srf = orig
                if is_bs:
                    ns, ok = _fit_bspline(mesh, part, ff_tol)
                    if ok:
                        srf = ns
                if j == 0:
                    comp_surf[l] = srf
                    continue
                labels[part] = nxt
                comp_surf[int(nxt)] = srf
                nxt += 1
            return nxt
    for f in fidx:
        s = _facet_surface(mesh, f)
        if s is not None:
            labels[f] = nxt; comp_surf[int(nxt)] = s; nxt += 1
    return nxt


IA_ORGANIC_SMOOTH = 0.885   # Ajuste IA en pieza orgánica sin suavizado elegido: ~4.5 mm
IA_TOL = 0.05               # Ajuste IA: cuánto puede moverse una medida para ser «redonda»


def build_solid(result, mesh, verbose=True, max_rounds=5, extra_regions=None, organic="auto",
                organic_smooth=0.0, ajuste_ia=False, precision_reparacion=False,
                preservar_contactos=False, cavidades_verificadas=False, refinar_curvas=False,
                contornos_compartidos=False):
    """Devuelve (shape, info). shape = sólido si se cierra; si no, el shell arreglado.
    info: dict con 'solid', 'valid', 'free_edges', 'faces', 'volume', 'round'.
    `organic`: "auto" (decide `meshfit_organic.looks_organic`), True o False. Una pieza
    ORGÁNICA (escaneo de una forma esculpida, sin primitivas) se reparte en parches
    B-spline en vez de crecer primitivas. `organic_smooth` (0..1): suavizado de la pieza
    orgánica (`meshfit_organic.smoothed_mesh`; 0 = fiel al escaneo). `ajuste_ia`:
    intención de diseño (`meshfit_ideal`): simetrías, medidas exactas, superficie armónica;
    el informe de decisiones va en info["ideal"]."""
    if not isinstance(mesh, _FrozenMesh):
        # ESCANEOS: agujeros y triángulos degenerados -> sin malla estanca no hay sólido
        if not mesh.is_watertight:
            from meshfit_repair import repair_mesh, remap_result
            mesh, fmap, _ = repair_mesh(mesh, verbose=verbose)
            result = remap_result(result, fmap)
            if extra_regions:
                extra_regions = [(fmap[np.asarray(f, int)][fmap[np.asarray(f, int)] >= 0], s_)
                                 for f, s_ in extra_regions]
        if not mesh.is_winding_consistent:
            mesh.fix_normals()
        mesh = _FrozenMesh(mesh)
    mesh.precision_reparacion = bool(precision_reparacion or refinar_curvas)
    if preservar_contactos:
        mesh.vertices_protegidos=set(int(v) for faces,_ in (extra_regions or [])
                                     for v in mesh.faces[np.asarray(faces,dtype=int)].ravel())
    # ruido de la malla ORIGINAL (la simetrización del Ajuste IA lo baja: 7.4° -> 5.5° en un
    # escaneo sintético, y con otros umbrales la segmentación salía distinta y PEOR)
    _NOISE["deg"] = float(np.degrees(np.median(mesh.face_adjacency_angles)))
    # STL digitales: una triangulación densa puede tener diedros > 2° sin ser ruido.
    # Solo activar bajo petición explícita del motor CAD; no idealizar escaneos.
    import os as _os
    if _os.environ.get("VISOR_STL_DIGITAL") == "1":
        _NOISE["deg"] = min(_NOISE["deg"], 1.0)
    ia_report = []
    if ajuste_ia:
        # AJUSTE IA, paso 1: simetrías de la pieza -> malla simetrizada (mismas caras)
        from meshfit_ideal import ai_prepare
        tm_, ia_report = ai_prepare(mesh, verbose=verbose)
        ia_report = list(ia_report)
        mesh = _FrozenMesh(tm_)
    if verbose and _NOISE["deg"] > 2:
        print(f"  [brep] malla con ruido: diedro mediano {_NOISE['deg']:.1f}° -> umbrales angulares adaptados")
    diag = float(np.linalg.norm(mesh.extents))
    tol = max(1e-3, 1e-4 * diag)                 # tolerancia de ajuste de aristas
    ff_tol = max(0.006, 6e-4 * diag)              # tolerancia de parche B-spline
    if _NOISE["deg"] > 2.0:
        # escaneo: las fronteras salen DENTADAS por el ruido; con la tolerancia fina de CAD
        # las curvas de arista copiaban el zigzag y los contornos se tocaban/cruzaban
        tol = max(tol, 0.5 * ff_tol)
    # Malla de CAD (caras planas teseladas con triángulos EXACTAMENTE coplanares, cosa que
    # el ruido de escáner no produce): sus vértices están sobre la pieza real, así que a
    # las B-spline se les exige 3× más -> sin ondas que los reflejos del CAD delatan
    # (el redondeo del soporte se veía como un anillo hinchado con 0.16 mm de onda).
    coplanar = float((mesh.face_adjacency_angles < np.radians(0.05)).mean())
    bs_tol = ff_tol / 3.0 if coplanar > 0.03 else ff_tol
    if organic == "auto":
        from meshfit_organic import looks_organic
        organic = looks_organic(result, mesh, verbose=verbose)
    import time as _time
    _t0 = _time.time()
    smooth_len = 0.0
    if organic:
        # PIEZA ORGÁNICA: parches-grafo + B-spline ajustada con solape (meshfit_organic).
        # Tolerancia 1/4 de la de zona libre (0.05 mm en 200 mm): un escaneo suavizado
        # del MetroX tiene ~0.005 mm de ruido, la NURBS puede pegarse mucho más.
        from meshfit_organic import organic_surfaces, organic_tol, smoothed_mesh
        tol_org = organic_tol(diag)
        if ajuste_ia and not (organic_smooth and organic_smooth > 0):
            organic_smooth = IA_ORGANIC_SMOOTH
        if ajuste_ia:
            from meshfit_organic import smooth_length
            ia_report.append(f"Pieza orgánica: superficies ARMÓNICAS ajustadas a la vez (L "
                             f"{smooth_length(organic_smooth):.1f} mm): malla alisada penalizando el cambio de curvatura (sin ondas ni islas, sin encoger) y 3 caras ajustadas a la vez -> costuras tangentes")
        fair = None
        mesh_in = mesh
        if organic_smooth and organic_smooth > 0:
            # SUAVIZADO: superficies ARMÓNICAS ajustadas a la vez (meshfit_fair); si la
            # pieza no admite tapas+banda, malla filtrada y TODO el sólido sobre ella
            from meshfit_fair import harmonic
            fair = harmonic(mesh, organic_smooth, verbose=verbose)
            if fair is None:
                mesh = _FrozenMesh(smoothed_mesh(mesh, organic_smooth, verbose=verbose))
            elif fair[0] is not mesh:
                mesh = _FrozenMesh(fair[0])          # malla de la fase 1 (otras caras)
        if fair is not None:
            labels0, surfs, _st = fair[1].copy(), list(fair[2]), fair[3]
        else:
            labels0, surfs, _st = organic_surfaces(mesh, tol_org, verbose=verbose)
        # entidades del usuario (NURBS pintadas, roscas): mandan sobre su zona
        kmap = None
        if len(mesh.faces) != len(mesh_in.faces) and extra_regions:
            # malla de la fase 1: las caras pintadas se pasan a la cara alisada más cercana
            from scipy.spatial import cKDTree
            _, kmap = cKDTree(np.asarray(mesh.triangles_center)).query(
                np.asarray(mesh_in.triangles_center))
        for fr, s_ in (extra_regions or []):
            fr = np.asarray(fr, int)
            if kmap is not None:
                fr = np.unique(kmap[fr])
            if len(fr) and s_ is not None:
                labels0[fr] = len(surfs); surfs.append(s_)
        if (labels0 < 0).any():
            _absorb_nearest(mesh, labels0, [None] * len(surfs), surfs,
                            np.where(labels0 < 0)[0])
        tol = max(tol, 0.5 * tol_org)
        h = float(np.median(np.linalg.norm(mesh.vertices[mesh.faces[:, 0]] -
                                           mesh.vertices[mesh.faces[:, 1]], axis=1)))
        smooth_len = 6.0 * h              # fronteras sin zigzag (ventana ~2 mm)
        if verbose:
            print(f"  [brep] pieza ORGÁNICA -> {len(surfs)} parches B-spline")
    else:
        # Guarda de tiempo: zonas libres gigantes (moleteados, escaneos densos) se
        # trocearían en cientos de parches durante minutos -> camino clásico directamente.
        claimed = np.zeros(len(mesh.faces), bool)
        for p in result["primitives"]:
            claimed[np.asarray(p["faces"], int)] = True
        for fr, _s in (extra_regions or []):
            claimed[np.asarray(fr, int)] = True
        n_free = int((~claimed).sum())
        if n_free > MAX_FREE_FACES:
            info = {"error": f"zona libre de {n_free} triángulos (> {MAX_FREE_FACES})"}
            if verbose:
                print(f"  [brep] {info['error']}: se omite el sólido")
            return None, info
        prims_l = []
        # Ruta experimental EXPLÍCITA para una entrada reparada y verificada.
        # Ajustar/absorber regiones con el umbral escalado por la diagonal podía
        # fundir una pared plana con su redondeo y crear ondas de >0,1 mm.
        # Se exige un ajuste más fino; los controles finales siguen intactos.
        region_ff = min(ff_tol, 0.015) if precision_reparacion else ff_tol
        region_bs = min(bs_tol, 0.005) if precision_reparacion else bs_tol
        if refinar_curvas:
            # Un cilindro crecido con tolerancia amplia puede aproximar un
            # redondeo que necesita superficie libre. No forzar ese ajuste:
            # conservar después los cilindros respaldados por el STL y validar
            # toda la geometría. La ruta normal conserva sus parámetros.
            region_ff = min(region_ff, .006)
            region_bs = min(region_bs, .003)
        if contornos_compartidos:
            from contornos_compatibles import priorizar_cilindros_respaldados
            extra_regions=priorizar_cilindros_respaldados(result,mesh,extra_regions)
        labels0, surfs = _region_surfaces(result, mesh, region_ff, region_bs, extra=extra_regions,
                                          prims_out=prims_l)
        if ajuste_ia:
            # AJUSTE IA, paso 2: MEDIDAS EXACTAS (ejes rectos, coaxiales, radios y
            # distancias redondas) -> sus superficies se rehacen con los valores ideales
            from meshfit_ideal import idealize_prims
            idx = [i for i, p in enumerate(prims_l) if p is not None]
            grp = _groups(labels0)
            pts_l = []
            for i in idx:
                vv = np.unique(mesh.faces[grp.get(i, np.zeros(0, int))].ravel())
                if len(vv) > 1500:
                    vv = vv[np.linspace(0, len(vv) - 1, 1500).astype(int)]
                pts_l.append(mesh.vertices[vv])
            keep = [k for k, pp in enumerate(pts_l) if len(pp) >= 3]
            idx = [idx[k] for k in keep]; pts_l = [pts_l[k] for k in keep]
            newp, rep_ = idealize_prims([prims_l[i] for i in idx], pts_l, tol=IA_TOL,
                                        verbose=verbose, cad=coplanar > 0.1)
            for i, q in zip(idx, newp):
                s_ = _prim_surface(q)
                if s_ is not None:
                    surfs[i] = s_
            ia_report += rep_
    if verbose:
        print(f"  [brep] regiones: {_time.time() - _t0:.1f}s")
    comp = _split_connected(mesh, labels0)
    comp_surf = {}
    for c in np.unique(comp):
        f0 = int(np.where(comp == c)[0][0])
        comp_surf[int(c)] = surfs[labels0[f0]]
    labels = comp.copy()
    info = {}
    shape = None
    strikes = {}
    best_valid = None
    _presplit_holed_rings(mesh, labels, comp_surf, ff_tol,
                         completos=contornos_compartidos and _os.environ.get('VISOR_MEDIAS_CANAS_COMPLETAS')=='1')
    # Solo afecta a reconstrucciones pequeñas que no mejoran y presentan
    # contornos cruzados repetidos. Una ruta experimental independiente puede
    # intentar otra segmentación; no hay motivo para agotar 5 rondas iguales.
    # Si la pieza se cierra antes, NO se altera ningún resultado.
    _recuperacion_activa = (_os.environ.get('VISOR_RECUPERACION_CAD', '1') == '1'
                           and _os.environ.get('VISOR_STL_DIGITAL') != '1'
                           and len(mesh.faces) <= 5000
                           and _NOISE['deg'] > 3.0)
    _errores_ronda_anterior = None
    for rnd in range(max_rounds):
        try:
            # un vértice de malla ya está en la pieza: proyectarlo no debe moverlo más que
            # unas pocas tolerancias de ajuste (si salta más, cayó en la zona extrapolada)
            _t1 = _time.time()
            _place_seams(mesh, labels, comp_surf)
            edge_tol = min(tol, 0.003) if precision_reparacion else tol
            movement = min(4 * ff_tol, 0.020) if precision_reparacion else 4 * ff_tol
            if refinar_curvas:
                edge_tol = min(edge_tol, .001)
                movement = min(movement, .012)
            if contornos_compartidos:
                from contornos_compatibles import construir
                from fijacion_contornos import completar_vertices_singulares
                import cadquery as cq
                shell,faces=construir(mesh,labels,comp_surf,edge_tol,max_move=movement,smooth_len=smooth_len,
                                     parches_regulares=True,triangulos_libres=True)
                shell,_=completar_vertices_singulares(shell)
                updated=cq.Shape.cast(shell).Faces()
                if len(updated)!=len(faces):raise ValueError('El cierre paramétrico cambia el número de caras.')
                faces={label:f.wrapped for label,f in zip(faces,updated)}
            else:
                shell, faces = _build(mesh, labels, comp_surf, edge_tol, max_move=movement,
                                      smooth_len=smooth_len)
            _tb = _time.time() - _t1
        except Exception as e:
            info["error"] = str(e)
            if verbose:
                print(f"  [brep] construcción fallida: {e}")
            return None, info
        _detalle_brep(71, f'Reparando contornos con OpenCascade (intento {rnd+1}/{max_rounds})')
        if contornos_compartidos:
            from fijacion_contornos import AjusteContornos
            fix=AjusteContornos(shell)
        else:fix = ShapeFix_Shape(shell)
        fix.SetPrecision(1e-7 if preservar_contactos else tol)
        fix.SetMaxTolerance(0.01 * diag)
        fix.Perform()
        fixed = fix.Shape()
        _tf = _time.time() - _t1 - _tb
        fixed, nfw = _fix_wire_intersections(fixed, 1e-7 if contornos_compartidos else tol)
        if verbose and nfw:
            print(f"     · {nfw} contorno(s) que se cruzaban, reparado(s)")
        ctx = fix.Context()
        # qué caras finales salen de cada región (para devolver los fallos a su región)
        owner = []
        for l, F in faces.items():
            exp = TopExp_Explorer(ctx.Apply(F), TopAbs_FACE)
            if not exp.More():
                owner.append((None, l))
            while exp.More():
                owner.append((exp.Current(), l)); exp.Next()
        _detalle_brep(73, 'Comprobando aristas libres y cierre del sólido CAD')
        nfree = _free_edges(fixed)
        sol = None
        if nfree == 0:
            try:
                sol = _make_solid(fixed,cavidades_verificadas=cavidades_verificadas,
                                  **({'contornos_compartidos':True} if contornos_compartidos else {}))
            except Exception as e:
                info["solid_error"] = str(e)
        test = sol if sol is not None else fixed
        badf = _bad_faces(test)
        bad = {l for (f, l) in owner if f is None}
        for bf in badf:
            hit = [l for f, l in owner if f is not None and f.IsSame(bf)]
            bad.update(hit or [_face_label(mesh, labels, bf, diag)])
        bad.discard(None)
        _detalle_brep(75, f'Validando topología de {len(faces)} caras reconstruidas')
        valid = BRepCheck_Analyzer(test).IsValid()
        info = {"faces": len(faces), "free_edges": nfree, "bad_faces": len(bad), "round": rnd,
                "solid": sol is not None, "valid": valid}
        # la MEJOR versión válida de todas las rondas (seguir reparando contornos cruzados
        # podía estropear un sólido que ya era válido: P1, cuerpo45)
        if valid and sol is not None and (best_valid is None or len(bad) < best_valid[2]):
            best_valid = (test, dict(info), len(bad), labels.copy(), dict(comp_surf))
        if verbose:
            print(f"  [brep] ronda {rnd}: {len(faces)} caras, {len(bad)} con error, "
                  f"{nfree} bordes libres, sólido={sol is not None}, válido={valid}  "
                  f"[construir {_tb:.0f}s, ShapeFix {_tf:.0f}s, total {_time.time() - _t1:.0f}s]")
            for l in bad:
                print(f"     · región {l}: {type(comp_surf[l]).__name__[5:]} "
                      f"{int((labels == l).sum())} tri")
        shape = test
        # Evitar estancamiento en regiones planas con wires cruzados, p. ej.
        # mallas CAD digitales pequeñas: dos rondas SIN mejora + >=2 cruces.
        if (rnd >= 1 and _recuperacion_activa and not valid
              and _errores_ronda_anterior is not None
              and len(bad) >= _errores_ronda_anterior > 0 and nfw >= 2):
            if verbose:
                print('  [brep] contornos cruzados sin mejora entre rondas; se activa recuperación CAD alternativa')
            break
        _errores_ronda_anterior = len(bad)
        if (valid and sol is not None) or rnd == max_rounds - 1:
            break
        if not bad:
            break                                  # inválido sin culpable localizable
        nxt = int(labels.max()) + 1
        # 1er remedio: ISLAS pequeñas dentro de la cara mala (restos de 1 mm de un redondeo
        # dentro de un cilindro: sus contornos tocaban el borde en un vértice ->
        # 'IntersectingWires', y partir no ayuda porque la isla queda en una mitad). Se
        # funden en la cara que las rodea si son pequeñas frente a ella.
        nbm = _region_neighbors(mesh, labels)
        absorbed = set()
        for l in list(bad):
            nl = int((labels == l).sum())
            for b in list(nbm.get(l, ())):
                if b < 0 or b in bad or b in absorbed:
                    continue
                nb_b = int((labels == b).sum())
                island = nbm.get(b, set()) <= {l}
                if (island and nb_b <= max(30, nl // 5)) or nb_b <= min(30, nl // 20):
                    labels[labels == b] = l
                    absorbed.add(b)
        if absorbed:
            if verbose:
                print(f"     · {len(absorbed)} isla(s) pequeña(s) absorbida(s)")
            continue
        for l in bad:
            # una zona que ya se partió y sigue fallando -> facetas (escalada)
            # (nunca una región GRANDE: miles de facetas dejan el sólido inservible)
            small = (labels == l).sum() < 300
            hard = small and (strikes.get(l, 0) >= 1 or rnd >= max_rounds - 2)
            nxt = _split_region(mesh, labels, comp_surf, l, nxt, ff_tol, to_facets=hard)
            strikes[l] = strikes.get(l, 0) + 1
    if best_valid is not None and not (info.get("valid") and info.get("solid")
                                       and info.get("bad_faces", 1) <= best_valid[2]):
        shape, info, _, labels, comp_surf = best_valid
        if verbose:
            print(f"  [brep] se usa la mejor versión válida (ronda {info['round']})")
    info["organic"] = bool(organic)
    if ajuste_ia:
        info["ideal"] = ia_report
    global LAST_REGIONS
    LAST_REGIONS = (labels, comp_surf)              # depuración / informes
    if info.get("solid"):
        g = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, g, 1e-6)   # adaptativa (la de defecto falla en caras periódicas)
        info["volume"] = float(g.Mass())
    if verbose:
        print(f"  [brep] sólido={info.get('solid')} válido={info.get('valid')} "
              f"vol={info.get('volume', 0):.2f}")
    return shape, info


if __name__ == "__main__":
    import sys
    from meshfit_detect import detect
    from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
    from OCP.Interface import Interface_Static
    stl = sys.argv[1]
    res, mesh = detect(stl)
    shape, info = build_solid(res, mesh)
    print(info, "malla vol", mesh.volume)
    if len(sys.argv) > 2 and shape is not None:
        Interface_Static.SetCVal_s("write.step.unit", "MM")
        w = STEPControl_Writer(); w.Transfer(shape, STEPControl_AsIs); w.Write(sys.argv[2])
