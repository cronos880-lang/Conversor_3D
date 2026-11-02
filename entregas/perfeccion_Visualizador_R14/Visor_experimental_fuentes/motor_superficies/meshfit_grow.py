"""
MeshFit — segmentación por CRECIMIENTO DE PRIMITIVAS (para mallas densas).

`meshfit_detect` separa regiones por ángulo diedro entre triángulos vecinos: perfecto en
mallas de CAD gruesas, pero en un STL exportado con teselado FINO (P1, torni, «Part Studio
1»: 90–155 k triángulos) todos los ángulos entre vecinos son de 0.5–2° y TODA la pieza
acaba en una sola región libre que nada sabe ajustar.

Aquí, como en QuickSurface/RANSAC con conectividad: desde una semilla se ajusta plano /
cilindro / esfera / cono / toro a su vecindario y se CRECE por la malla mientras los
triángulos encajan en esa superficie (vértices a <= tol y normal alineada), reajustando
la primitiva cada vez que la región dobla su tamaño. Gana el tipo que más área cubre
(con una pequeña penalización por complejidad). No depende de lo fino que sea el teselado.
"""
import time
import numpy as np
import scipy.sparse as sps

from meshfit_detect import FIT, DEV, _normal_dots, _degenerate, _torus_from_axis

TYPES = ("plane", "cylinder", "sphere", "cone", "torus")
PASS1 = ("plane", "cylinder", "cone")          # 1ª pasada: lo simple, que da los EJES
PENALTY = {"plane": 1.0, "cylinder": 1.03, "sphere": 1.06, "cone": 1.10, "torus": 1.15}


# ---- ajustes con EJE FIJO (redondeos/chaflanes de revolución alrededor de un eje ya
# ---- conocido: un trozo pequeño de toro no determina su eje, pero con el eje dado sí)
def _axial(pts, a, q):
    d = pts - q
    t = d @ a
    return t, np.linalg.norm(d - np.outer(t, a), axis=1)


def fit_cylinder_ax(pts, a, q):
    t, rho = _axial(pts, a, q)
    return {"type": "cylinder", "axis": a, "point": q + a * float(t.mean()),
            "radius": float(rho.mean())}


def fit_cone_ax(pts, a, q):
    t, rho = _axial(pts, a, q)
    if np.ptp(t) < 1e-6:
        return None
    m, b = np.polyfit(t, rho, 1)
    if abs(m) < np.tan(np.radians(2)):
        return None                                  # casi cilindro
    if m < 0:
        a = -a; t = -t; m, b = np.polyfit(t, rho, 1)
    return {"type": "cone", "axis": a, "origin": q, "half_angle": float(np.arctan(m)),
            "slope": float(m), "b": float(b)}


def fit_sphere_ax(pts, a, q):
    t, rho = _axial(pts, a, q)                       # ρ²+t² = 2·t·h0 + (R²-h0²)
    A = np.c_[2 * t, np.ones(len(t))]
    (h0, k), *_ = np.linalg.lstsq(A, rho ** 2 + t ** 2, rcond=None)
    R2 = k + h0 * h0
    if R2 <= 0:
        return None
    return {"type": "sphere", "center": q + a * h0, "radius": float(np.sqrt(R2))}


def fit_torus_ax(pts, a, q):
    p = _torus_from_axis(pts, a, q)
    return p


AX_FIT = {"cylinder": fit_cylinder_ax, "cone": fit_cone_ax, "sphere": fit_sphere_ax,
          "torus": fit_torus_ax}


def _frame(a):
    a = a / np.linalg.norm(a)
    e1 = np.cross(a, [1.0, 0, 0] if abs(a[0]) < 0.9 else [0, 1.0, 0]); e1 /= np.linalg.norm(e1)
    return a, e1, np.cross(a, e1)


def refine(p, pts, tol):
    """Ajuste GEOMÉTRICO fino (mínimos cuadrados no lineales sobre la distancia real
    punto-superficie, pérdida robusta) partiendo de una estimación aproximada: el eje
    sacado de normales de triángulos diminutos sale desplazado décimas de mm (P1: 0.28 mm,
    0.18°) y con tolerancia estricta nada encaja. Devuelve la primitiva refinada o la
    original si el ajuste no mejora."""
    from scipy.optimize import least_squares
    ty = p["type"]
    if ty == "plane" or len(pts) < 8:
        return p
    if len(pts) > 3000:
        pts = pts[np.linspace(0, len(pts) - 1, 3000).astype(int)]
    try:
        if ty == "sphere":
            f = lambda x: np.linalg.norm(pts - x[:3], axis=1) - x[3]
            r = least_squares(f, np.r_[p["center"], p["radius"]], loss="soft_l1", f_scale=tol, max_nfev=60)
            q = dict(p, center=r.x[:3], radius=float(abs(r.x[3])))
        else:
            a0, e1, e2 = _frame(np.asarray(p["axis"], float))
            c0 = np.asarray(p.get("point", p.get("origin", p.get("center"))), float)

            def axis_of(x):
                a = a0 + x[0] * e1 + x[1] * e2
                return a / np.linalg.norm(a), c0 + x[2] * e1 + x[3] * e2

            def cyl(pp, a, c):
                d = pp - c
                t = d @ a
                return t, np.linalg.norm(d - np.outer(t, a), axis=1)
            if ty == "cylinder":
                f = lambda x: cyl(pts, *axis_of(x))[1] - x[4]
                r = least_squares(f, np.r_[0, 0, 0, 0, p["radius"]], loss="soft_l1", f_scale=tol, max_nfev=60)
                a, c = axis_of(r.x)
                q = dict(p, axis=a, point=c, radius=float(abs(r.x[4])))
            elif ty == "cone":
                def f(x):
                    a, c = axis_of(x)
                    t, rho = cyl(pts, a, c)
                    return (rho - (x[4] * t + x[5])) / np.sqrt(1 + x[4] ** 2)
                r = least_squares(f, np.r_[0, 0, 0, 0, p["slope"], p["b"]], loss="soft_l1",
                                  f_scale=tol, max_nfev=60)
                a, c = axis_of(r.x)
                m, b = float(r.x[4]), float(r.x[5])
                if m < 0:
                    return p                     # cambiaría de sentido: mejor no tocar
                q = dict(p, axis=a, origin=c, slope=m, b=b, half_angle=float(np.arctan(m)))
            elif ty == "torus":
                def f(x):
                    a, c = axis_of(x)
                    c = c + x[4] * a
                    t, rho = cyl(pts, a, c)
                    return np.sqrt((rho - x[5]) ** 2 + t ** 2) - x[6]
                r = least_squares(f, np.r_[0, 0, 0, 0, 0, p["R"], p["r"]], loss="soft_l1",
                                  f_scale=tol, max_nfev=60)
                a, c = axis_of(r.x)
                q = dict(p, axis=a, center=c + r.x[4] * a, R=float(r.x[5]), r=float(abs(r.x[6])))
            else:
                return p
        old = float(np.median(np.abs(DEV[ty](p, pts))))
        new = float(np.median(np.abs(DEV[ty](q, pts))))
        return q if new <= old else p
    except Exception:
        return p


def _adjacency(mesh, max_angle_deg=None):
    """Adyacencia de caras (CSR). Con `max_angle_deg`, solo por aristas SUAVES."""
    a = mesh.face_adjacency
    if max_angle_deg is not None:
        a = a[mesh.face_adjacency_angles < np.radians(max_angle_deg)]
    n = len(mesh.faces)
    return sps.coo_matrix((np.ones(2 * len(a), bool), (np.r_[a[:, 0], a[:, 1]],
                                                        np.r_[a[:, 1], a[:, 0]])),
                          shape=(n, n)).tocsr()


class _Grower:
    def __init__(self, mesh, tol, ndot):
        self.m = mesh
        self.A = _adjacency(mesh)
        # el vecindario de una SEMILLA no cruza aristas vivas (la semilla del taladro de P1
        # arrastraba la cara frontal a 90° y nada encajaba)
        self.As = _adjacency(mesh, 25.0)
        self.tol, self.ndot = tol, ndot
        # arrays NumPy normales (los TrackedArray de trimesh añadían ~25 % de sobrecoste)
        self.V, self.F = np.asarray(mesh.vertices).copy(), np.asarray(mesh.faces).copy()
        self.N = np.asarray(mesh.face_normals).copy()
        self.C = np.asarray(mesh.triangles_center).copy()
        self.S = np.asarray(mesh.area_faces).copy()
        self.diag = float(np.linalg.norm(mesh.extents))

    def neighbors(self, idx):
        if len(idx) == 0:
            return idx
        return np.unique(self.A[idx].indices)

    def fit(self, ty, faces, ax=None, fine=True):
        """Ajuste libre, o con eje fijo si `ax` = (dirección, punto)."""
        vid = np.unique(self.F[faces].ravel())
        if ty != "plane" and len(faces) < 6:
            return None
        try:
            if ax is not None:
                p = AX_FIT[ty](self.V[vid], ax[0], ax[1])
            elif ty in ("cylinder", "cone"):
                p = self._fit_axial_free(ty, faces, vid)
            else:
                p = FIT[ty](self.V[vid], self.N[faces], self.S[faces], self.C[faces])
        except Exception:
            return None
        if p is None:
            return None
        p["type"] = ty
        if ty != "plane" and fine:
            P = self.V[vid]
            if len(P) > 400:                       # muestra: el ajuste fino es lo caro
                P = P[np.linspace(0, len(P) - 1, 400).astype(int)]
            p = refine(p, P, self.tol)
        if ty != "plane" and _degenerate(ty, p, self.diag):
            return None
        if ax is not None:
            p["_ax"] = ax                     # los reajustes parten del mismo eje
        return p

    def _fit_axial_free(self, ty, faces, vid):
        """Cilindro/cono con el MEJOR de varios ejes candidatos: el de las normales y los
        3 ejes principales de los puntos. Con ruido de normales (±7° en P1) y una semilla
        de pocos grados de arco, el eje por normales sale torcido; el eje PCA de una tira
        alargada a lo largo del cilindro es el bueno."""
        P = self.V[vid]
        cands = []
        try:
            p0 = FIT[ty](P, self.N[faces], self.S[faces], self.C[faces])
            if p0 is not None:
                cands.append(p0)
        except Exception:
            pass
        c = P.mean(0)
        _, _, vt = np.linalg.svd(P - c, full_matrices=False)
        for k in range(3):
            a = vt[k] / np.linalg.norm(vt[k])
            x, y = np.cross(a, [1.0, 0, 0] if abs(a[0]) < 0.9 else [0, 1.0, 0]), None
            x /= np.linalg.norm(x); y = np.cross(a, x)
            uv = np.c_[(P - c) @ x, (P - c) @ y]
            A = np.c_[2 * uv, np.ones(len(uv))]
            sol, *_ = np.linalg.lstsq(A, (uv ** 2).sum(1), rcond=None)
            q = c + sol[0] * x + sol[1] * y
            p = AX_FIT[ty](P, a, q)
            if p is not None:
                cands.append(p)
        best = None
        for p in cands:
            p["type"] = ty
            if _degenerate(ty, p, self.diag):
                continue
            sc = float(self.ok(p, faces).mean())
            if best is None or sc > best[0]:
                best = (sc, p)
        return None if best is None else best[1]

    def ok(self, p, faces, tol=None):
        """máscara: triángulos que encajan en la primitiva (los 3 vértices + normal)."""
        dv = DEV[p["type"]](p, self.V[self.F[faces]].reshape(-1, 3)).reshape(-1, 3).max(1)
        # Guardar la geometría poligonal real: una sección de seis caras no
        # equivale al cilindro que pasa por sus vértices.
        if __import__("os").environ.get("VISOR_CENTROID_GATE") == "1" and p["type"] != "plane":
            dc = DEV[p["type"]](p, self.C[faces])
            dv = np.maximum(dv, dc)
        nd = _normal_dots(p, self.C[faces], self.N[faces])
        return (dv <= (tol or self.tol)) & (nd >= self.ndot)

    def grow(self, ty, p, seed, allowed):
        region = np.zeros(len(self.F), bool)
        s = seed[self.ok(p, seed)]
        if len(s) == 0:
            return region, p
        region[s] = True
        n_refit = 2 * len(s)
        new = s
        while True:
            front = self.neighbors(new)
            front = front[allowed[front] & ~region[front]]
            if len(front) == 0:
                break
            new = front[self.ok(p, front)]
            if len(new) == 0:
                break
            region[new] = True
            cnt = int(region.sum())
            if cnt >= n_refit:
                rf = np.where(region)[0]
                p2 = self.fit(ty, rf, p.get("_ax"))
                # el reajuste se acepta si sigue conteniendo (casi) toda la región
                if p2 is not None and self.ok(p2, rf).mean() >= 0.97:
                    p = p2
                n_refit = 2 * cnt
        return region, p

    def seed_patch(self, f, allowed, kmin=40, kmax=4000):
        """Vecindario de la semilla con TAMAÑO FÍSICO (≈ diag/12), no nº de triángulos:
        con teselado fino en astillas, 40 triángulos abarcan 3° de un cilindro y el eje
        sale indeterminado (ganaban esferas diminutas)."""
        size = self.diag / 12.0
        inpatch = np.zeros(len(self.F), bool); inpatch[f] = True
        patch, front = [np.array([f])], np.array([f])
        n = 1
        while n < kmax:
            nb = np.unique(self.As[front].indices) if len(front) else front
            nb = nb[allowed[nb] & ~inpatch[nb]]
            if len(nb) == 0:
                break
            inpatch[nb] = True; patch.append(nb); front = nb; n += len(nb)
            if n >= kmin:
                # ancho en las DOS direcciones principales (astillas de 30 mm de largo y
                # 0.1° de arco cumplen el tamaño "a lo largo" enseguida)
                P = self.C[np.concatenate(patch)]
                sv = np.linalg.svd(P - P.mean(0), compute_uv=False)
                ext2 = 4.0 * sv[1] / np.sqrt(len(P))      # ≈ anchura en la 2ª dirección
                if ext2 >= 0.5 * size:
                    break
        return np.concatenate(patch)

    def best_at(self, f, allowed, types, axes):
        """Mejor primitiva crecida desde la semilla f (libre y con los ejes conocidos)."""
        patch = self.seed_patch(f, allowed)
        best = None
        cands = [(ty, None) for ty in types]
        cands += [(ty, ax) for ax in axes for ty in ("torus", "cone", "cylinder", "sphere")]
        for ty, ax in cands:
            # cribado rápido (sin ajuste fino, tolerancia x4) y solo entonces el fino
            p = self.fit(ty, patch, ax, fine=False)
            if p is None or self.ok(p, patch, 4 * self.tol).mean() < 0.9:
                continue
            if ty != "plane":
                p = self.fit(ty, patch, ax)
            if p is None or self.ok(p, patch).mean() < 0.9:
                continue
            reg, p = self.grow(ty, p, patch, allowed)
            area = float(self.S[reg].sum())
            score = area / PENALTY[ty]
            if best is None or score > best[0]:
                best = (score, reg, p, area)
        return patch, best


def global_axes(mesh, faces, tol, min_frac=0.25):
    """Ejes de REVOLUCIÓN dominantes de la pieza (piezas de torno: P1, torni...). En una
    superficie de revolución la normal de cada punto CORTA el eje: para cada dirección
    candidata (ejes PCA de los puntos y de las normales) se busca el punto del eje que
    minimiza la distancia (en el plano ⟂) a las rectas normales, y se acepta si una
    fracción grande del área es coherente con él. Devuelve [(dirección, punto), ...]."""
    faces = np.asarray(faces, int)
    P, N, A = mesh.triangles_center[faces], mesh.face_normals[faces], mesh.area_faces[faces]
    dirs = []
    V = mesh.vertices[np.unique(mesh.faces[faces].ravel())]
    for M in (np.cov((V - V.mean(0)).T), (N * A[:, None]).T @ N):
        _, vecs = np.linalg.eigh(M)
        dirs += [vecs[:, k] for k in range(3)]
    lim = max(10 * tol, 0.002 * float(np.linalg.norm(mesh.extents)))
    out = []
    for a in dirs:
        a = a / np.linalg.norm(a)
        x = np.cross(a, [1.0, 0, 0] if abs(a[0]) < 0.9 else [0, 1.0, 0]); x /= np.linalg.norm(x)
        y = np.cross(a, x)
        p2 = np.c_[P @ x, P @ y]; n2 = np.c_[N @ x, N @ y]
        ln = np.linalg.norm(n2, axis=1)
        use = ln > 0.3                                   # normales no paralelas al eje
        if use.sum() < 20:
            continue
        n2u = n2[use] / ln[use, None]
        # recta normal por p2 con dirección n2: cross(n2, p2 - q) = 0 -> lineal en q
        Aq = np.c_[-n2u[:, 1], n2u[:, 0]]
        bq = -n2u[:, 1] * p2[use, 0] + n2u[:, 0] * p2[use, 1]
        w = np.sqrt(A[use])
        q2, *_ = np.linalg.lstsq(Aq * w[:, None], bq * w, rcond=None)
        res = np.abs(Aq @ q2 - bq)
        coh = np.zeros(len(faces), bool)
        coh[np.where(use)[0][res < lim]] = True
        coh |= ~use & (np.abs(N @ a) > 0.99)             # caras planas ⟂ eje (frentes)
        frac = float(A[coh].sum() / A.sum())
        if frac >= min_frac:
            q = q2[0] * x + q2[1] * y
            if not any(abs(a @ b) > np.cos(np.radians(2)) for b, _, _ in out):
                out.append((a, q, frac))
    out.sort(key=lambda t: -t[2])
    return [(a, q) for a, q, _ in out]


def grow_primitives(mesh, faces, tol, ndot=np.cos(np.radians(12)), min_faces=12,
                    min_area_frac=2e-4, time_budget=120.0, verbose=False, max_fails=300):
    """Segmenta `faces` (índices de triángulo) en regiones de primitiva por crecimiento.
    Devuelve (lista de (caras, prim_dict), caras_sobrantes)."""
    t0 = time.time()
    g = _Grower(mesh, tol, ndot)
    faces = np.asarray(faces, int)
    allowed = np.zeros(len(mesh.faces), bool); allowed[faces] = True
    tried = np.zeros(len(mesh.faces), bool)
    total_area = float(mesh.area_faces[faces].sum())
    # semillas: primero las zonas más "lisas" (menor ángulo con sus vecinos) y grandes
    adj, ang = mesh.face_adjacency, mesh.face_adjacency_angles
    maxang = np.zeros(len(mesh.faces))
    np.maximum.at(maxang, adj[:, 0], ang); np.maximum.at(maxang, adj[:, 1], ang)
    # semillas: primero los triángulos GRANDES (en CAD están en las superficies simples:
    # taladros, planos, cilindros; los diminutos, en los redondeos) y a igualdad, los lisos
    order = faces[np.lexsort((np.round(maxang[faces], 3), -np.round(mesh.area_faces[faces], 6)))]
    out = []
    axes = global_axes(mesh, faces, tol) if len(faces) >= 200 else []
    if verbose and axes:
        print(f"  [grow] ejes de revolución: {[np.round(a, 3).tolist() for a, _ in axes]}")

    def add_axis(p):
        if p["type"] not in ("cylinder", "cone", "torus"):
            return
        a = np.asarray(p["axis"], float); a = a / np.linalg.norm(a)
        q = np.asarray(p.get("point", p.get("origin", p.get("center"))), float)
        for b, r in axes:                          # ¿eje ya conocido? (paralelo y coincidente)
            if abs(a @ b) > np.cos(np.radians(1.0)):
                d = (q - r) - ((q - r) @ b) * b
                if np.linalg.norm(d) < 20 * tol:
                    return
        axes.append((a, q))

    # 1ª pasada: planos, cilindros y conos (dan los ejes); 2ª: todo + ajustes con esos ejes
    for types, use_axes in ((PASS1, bool(axes)), (TYPES, True)):
        tried = np.zeros(len(mesh.faces), bool)
        fails = 0
        for f in order:
            if not allowed[f] or tried[f]:
                continue
            if time.time() - t0 > time_budget:
                break
            patch, best = g.best_at(f, allowed, types, axes if use_axes else [])
            if best is None or best[1].sum() < min_faces or best[3] < min_area_frac * total_area:
                # solo el ENTORNO INMEDIATO de la semilla: marcar todo su vecindario (hasta
                # 4000 triángulos) "envenenaba" zonas buenas vecinas (el taladro de P1, que
                # encaja exacto, nunca llegaba a ser semilla)
                ring = g.neighbors(np.array([f]))
                tried[f] = True; tried[ring] = True
                tried[g.neighbors(ring)] = True          # dos anillos
                fails += 1
                if fails >= max_fails:                   # lo que queda son retales
                    break
                continue
            fails = 0
            _, reg, p, area = best
            rf = np.where(reg)[0]
            p.pop("_ax", None)
            out.append((rf, p))
            allowed[rf] = False
            add_axis(p)
            if verbose:
                print(f"  [grow] {p['type']:8s} {len(rf):6d} tri  {area:9.1f} mm²")
    rest = faces[allowed[faces]]
    return out, rest


if __name__ == "__main__":
    import sys, trimesh
    m = trimesh.load(sys.argv[1]); m.merge_vertices()
    diag = float(np.linalg.norm(m.extents))
    t = time.time()
    regs, rest = grow_primitives(m, np.arange(len(m.faces)), max(0.01, 1e-3 * diag) / 3,
                                 verbose=True)
    from collections import Counter
    print(f"{len(regs)} regiones en {time.time() - t:.1f}s  tipos {Counter(p['type'] for _, p in regs)}"
          f"  sobrante {len(rest)} tri ({100 * m.area_faces[rest].sum() / m.area:.1f}% área)")
