"""
MeshFit — PIEZAS ORGÁNICAS (escaneos sin planos ni cilindros) -> parches NURBS.

Primer escaneo real del Revopoint MetroX (oct 2026, `Merge_01_mesh.stl`): bulbo + cuello +
base en T, 396 k triángulos, NI UNA primitiva. El camino de piezas mecánicas (crecer
primitivas y trocear por bisección lo que sobra) no está pensado para esto: deja parches
de formas arbitrarias y fronteras en zigzag.

Aquí la superficie se reparte en parches que son GRAFOS sobre un plano (cada triángulo
mira, como mucho, ~55° lejos de la dirección del parche), al estilo de un «polycube»:
  1. normales SUAVIZADAS (difusión sobre la malla, radio de unos mm): el ruido del
     escáner no debe decidir fronteras;
  2. cada triángulo va a la dirección de un CUBO (±X, ±Y, ±Z del marco principal de la
     pieza) a la que más mira -> las fronteras caen donde la normal está a medio camino
     entre dos caras del cubo: curvas suaves sobre la pieza, no zigzags de ruido;
  3. componentes conexas; las pequeñas se funden con el vecino con el que más frontera
     comparten si el parche resultante sigue siendo un grafo;
  4. filtro de mayoría en las fronteras (quita dientes de un triángulo).
Cada parche se ajusta luego con una B-spline (campo de alturas sobre su dirección media,
P-spline) y `meshfit_brep` construye el sólido con aristas compartidas.

REPARTO PREFERIDO (`_band_layout`, desde el 15-oct tras ver el de cubo en Fusion): TRES
caras — tapa de arriba y de abajo (campos de alturas sobre el eje fino de la pieza) + una
banda PERIÓDICA alrededor del canto (anillo con parametrización armónica). El de cubo
queda de respaldo cuando la pieza no tiene esa forma (agujeros pasantes, varias bandas...).
"""
import numpy as np
from scipy.sparse import coo_matrix, diags, identity
from scipy.sparse.csgraph import connected_components


def smooth_face_normals(mesh, radius):
    """Normales de cara suavizadas por difusión sobre los vértices (radio ~ `radius` mm)."""
    V = np.asarray(mesh.vertices, float)
    F = np.asarray(mesh.faces)
    nv = len(V)
    fn = mesh.face_normals * mesh.area_faces[:, None]
    vn = np.zeros((nv, 3))
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    e = np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]
    A = coo_matrix((np.ones(2 * len(e)), (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])),
                   shape=(nv, nv)).tocsr()
    A.data[:] = 1.0
    A = A + identity(nv, format="csr")
    W = diags(1.0 / np.asarray(A.sum(1)).ravel()) @ A
    h = float(np.median(np.linalg.norm(V[F[:, 0]] - V[F[:, 1]], axis=1))) or 1.0
    it = int(np.clip((radius / h) ** 2, 3, 600))
    for i in range(it):
        vn = W @ vn
        if i % 20 == 19:
            vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
    fs = vn[F].sum(1)
    return fs / (np.linalg.norm(fs, axis=1, keepdims=True) + 1e-12)


def _frame(mesh, faces):
    """Ejes principales (área ponderada) de la región: las 6 direcciones del cubo."""
    C = mesh.triangles_center[faces]
    w = mesh.area_faces[faces]
    c = (C * w[:, None]).sum(0) / w.sum()
    M = ((C - c) * w[:, None]).T @ (C - c)
    _, vec = np.linalg.eigh(M)
    E = vec.T[::-1]                       # mayor varianza primero
    return np.vstack([E, -E])


def _components(adj, labels, nf):
    same = labels[adj[:, 0]] == labels[adj[:, 1]]
    a = adj[same & (labels[adj[:, 0]] >= 0)]
    g = coo_matrix((np.ones(len(a)), (a[:, 0], a[:, 1])), shape=(nf, nf))
    _, comp = connected_components(g, directed=False)
    return comp


def _graph_ok(ns, w, max_dev_cos):
    """¿Las normales (suavizadas) caben en un cono alrededor de su media? (grafo)."""
    m = (ns * w[:, None]).sum(0)
    ln = np.linalg.norm(m)
    if ln < 1e-12:
        return False, None
    m /= ln
    d = ns @ m
    # percentil bajo, no el mínimo: un diente de ruido no invalida el parche
    return bool(np.percentile(d, 0.5) >= max_dev_cos), m


def organic_segments(mesh, faces=None, smooth_r=None, ns=None, min_area_frac=0.012,
                     max_dev_deg=62.0, verbose=True, dirs=None, graph_check=True,
                     labels0=None):
    """Reparte `faces` (por defecto toda la malla) en parches-grafo. Devuelve lista de
    arrays de caras. `dirs`: direcciones a las que se asigna cada triángulo (por defecto
    las 6 del cubo; [e, -e] = dos MITADES por la línea de partición). `graph_check=False`:
    las componentes pequeñas se funden sin exigir que el parche siga siendo un grafo."""
    nf = len(mesh.faces)
    faces = np.arange(nf) if faces is None else np.asarray(faces, int)
    diag = float(np.linalg.norm(mesh.extents))
    if ns is None:
        ns = smooth_face_normals(mesh, smooth_r or max(1.0, diag / 80.0))
    D = _frame(mesh, faces) if dirs is None else np.asarray(dirs, float)
    lab = np.full(nf, -1, int)
    lab[faces] = (np.argmax(ns[faces] @ D.T, axis=1) if labels0 is None
                  else np.asarray(labels0)[faces])
    adj = mesh.face_adjacency
    inreg = lab[adj[:, 0]] >= 0
    inreg &= lab[adj[:, 1]] >= 0
    adj = adj[inreg]
    comp = _components(adj, lab, nf)
    reg = np.full(nf, -1, int)
    reg[faces] = comp[faces]
    # renumerar 0..k-1
    _, reg_f = np.unique(reg[faces], return_inverse=True)
    reg[faces] = reg_f
    area = mesh.area_faces
    total = float(area[faces].sum())
    amin = min_area_frac * total
    cosd = np.cos(np.radians(max_dev_deg))
    n0 = int(reg_f.max()) + 1
    # ---- fundir componentes pequeñas en su mejor vecino (si el resultado es grafo)
    stuck = set()
    for _ in range(5000):
        ids = reg[faces]
        A = np.bincount(ids, weights=area[faces], minlength=int(ids.max()) + 1)
        small = [k for k in np.argsort(A) if A[k] > 0 and A[k] < amin and k not in stuck]
        if not small:
            break
        k = int(small[0])
        la, lb = reg[adj[:, 0]], reg[adj[:, 1]]
        cross = (la != lb) & ((la == k) | (lb == k))
        other = np.where(la[cross] == k, lb[cross], la[cross])
        if len(other) == 0:
            stuck.add(k); continue
        cand, cnt = np.unique(other, return_counts=True)
        merged = False
        for o in cand[np.argsort(-cnt)]:
            sel = np.where((reg == k) | (reg == o))[0]
            ok = _graph_ok(ns[sel], area[sel], cosd)[0] if graph_check else True
            if ok:
                reg[reg == k] = o
                merged = True
                break
        if not merged:
            stuck.add(k)
    # ---- filtro de mayoría en fronteras (dientes de 1 triángulo)
    for _ in range(6):
        la, lb = reg[adj[:, 0]], reg[adj[:, 1]]
        diff = la != lb
        if not diff.any():
            break
        # para cada cara, cuántos vecinos tiene de otra etiqueta y cuál
        f = np.r_[adj[diff, 0], adj[diff, 1]]
        o = np.r_[lb[diff], la[diff]]
        key = f.astype(np.int64) * (int(reg.max()) + 2) + o
        uk, cnt = np.unique(key, return_counts=True)
        ff = uk // (int(reg.max()) + 2)
        oo = uk % (int(reg.max()) + 2)
        flip = cnt >= 2                    # 2 de sus 3 vecinos son de la otra región
        if not flip.any():
            break
        reg[ff[flip]] = oo[flip]
    # componentes finales (el filtro puede dejar islas de 1-2 triángulos) -> conexas, y
    # las migajas a la región vecina con la que más frontera comparten
    comp = _components(adj, reg, nf)
    for _ in range(20):
        cnt = np.bincount(comp[faces], minlength=nf)
        tiny = cnt[comp[faces]] < 30
        if not tiny.any():
            break
        ca, cb = comp[adj[:, 0]], comp[adj[:, 1]]
        diff = ca != cb
        f = np.r_[adj[diff, 0], adj[diff, 1]]
        o = np.r_[cb[diff], ca[diff]]
        mine = np.r_[ca[diff], cb[diff]]
        sel = cnt[mine] < 30
        if not sel.any():
            break
        key = mine[sel].astype(np.int64) * nf + o[sel]
        uk, kc = np.unique(key, return_counts=True)
        src, dst = uk // nf, uk % nf
        best = {}
        for s_, d_, c_ in zip(src.tolist(), dst.tolist(), kc.tolist()):
            if c_ > best.get(s_, (0, -1))[0] and cnt[d_] >= cnt[s_]:
                best[s_] = (c_, d_)
        if not best:
            break
        remap = np.arange(nf)
        for s_, (_, d_) in best.items():
            remap[s_] = d_
        comp = remap[comp]
    out = []
    for k in np.unique(comp[faces]):
        out.append(faces[comp[faces] == k])
    out.sort(key=len, reverse=True)
    if verbose:
        print(f"  [orgánico] {n0} componentes ({len(D)} direcciones) -> {len(out)} parches "
              f"(mayor {len(out[0])} tri, menor {len(out[-1])} tri)")
    return out


# --------------------------------------------------------------------------- detección
def doubly_curved_fraction(mesh, n_samples=600, verbose=False):
    """Fracción de la superficie con DOBLE curvatura (ninguna curvatura principal ~0).
    Planos, cilindros y conos (la mayor parte de una pieza mecánica) son desarrollables:
    una de sus curvaturas es nula. Un bulbo o una pieza esculpida curva en las dos
    direcciones. Cuádrica local en vértices de muestra (deterministas)."""
    from scipy.spatial import cKDTree
    diag = float(np.linalg.norm(mesh.extents))
    r = diag / 40.0
    kap0 = 1.0 / diag                     # radio > diag cuenta como «recto»
    rng = np.random.default_rng(0)
    # puntos UNIFORMES sobre la superficie (no vértices: en el CAD los triángulos largos
    # dejan los vértices en las aristas y la cuádrica salía curva en todas partes)
    p = mesh.area_faces / mesh.area_faces.sum()
    npts = 60000
    fi = rng.choice(len(p), npts, p=p)
    a, b = rng.random(npts), rng.random(npts)
    sw = a + b > 1
    a[sw], b[sw] = 1 - a[sw], 1 - b[sw]
    tri = np.asarray(mesh.vertices, float)[np.asarray(mesh.faces)[fi]]
    V = tri[:, 0] + a[:, None] * (tri[:, 1] - tri[:, 0]) + b[:, None] * (tri[:, 2] - tri[:, 0])
    S = V[:min(n_samples, npts)]
    T = cKDTree(V)
    dbl = tot = 0
    for q in S:
        nb = T.query_ball_point(q, r)
        if len(nb) < 12:
            continue
        P = V[nb] - q
        _, _, vt = np.linalg.svd(P - P.mean(0), full_matrices=False)
        n = vt[2]; x = vt[0]; y = vt[1]
        u, v, h = P @ x, P @ y, P @ n
        A = np.c_[u * u, u * v, v * v, u, v, np.ones_like(u)]
        cf, *_ = np.linalg.lstsq(A, h, rcond=None)
        k = np.linalg.eigvalsh(np.array([[2 * cf[0], cf[1]], [cf[1], 2 * cf[2]]]))
        tot += 1
        if np.abs(k).min() > kap0:
            dbl += 1
    f = dbl / max(tot, 1)
    if verbose:
        print(f"  [orgánico] doble curvatura en el {100 * f:.0f} % de la superficie")
    return f


def looks_organic(result, mesh, verbose=True):
    """¿Pieza orgánica (todo NURBS) o mecánica (primitivas)? Orgánica cuando la detección
    apenas encontró primitivas Y la mayor parte de la superficie curva en las dos
    direcciones (una esfera de verdad la habría cazado la detección)."""
    area = mesh.area_faces
    cov = sum(float(area[np.asarray(p["faces"], int)].sum()) for p in result.get("primitives", []))
    cov /= float(area.sum())
    if cov > 0.3 or len(mesh.faces) < 5000:
        return False
    # CAD (caras planas teseladas con triángulos EXACTAMENTE coplanares: 26-54 % de las
    # aristas; un escaneo, aun suavizado, < 3 %) -> nunca orgánica
    if float((mesh.face_adjacency_angles < np.radians(0.05)).mean()) > 0.1:
        return False
    # medido (r=diag/40): escaneo orgánico 0.70; escaneos sintéticos de piezas mecánicas
    # 0.27-0.36; CAD 0.21-0.46 (además vetado arriba)
    return doubly_curved_fraction(mesh, verbose=verbose) > 0.55


# --------------------------------------------------------------------------- ajuste
OVERLAP = 0.012     # ancho de la franja de solape con los vecinos, fracción de la diagonal


def _face_adj_matrix(mesh):
    adj = mesh.face_adjacency
    nf = len(mesh.faces)
    return coo_matrix((np.ones(2 * len(adj)), (np.r_[adj[:, 0], adj[:, 1]],
                                               np.r_[adj[:, 1], adj[:, 0]])),
                      shape=(nf, nf)).tocsr()


def _band(Afaces, faces, rings):
    """Caras a <= `rings` anillos de la región (sin la región): franja de SOLAPE."""
    nf = Afaces.shape[0]
    m = np.zeros(nf, bool); m[faces] = True
    cur = m.copy()
    for _ in range(rings):
        cur = cur | (Afaces @ cur.astype(np.float32) > 0)
    cur[faces] = False
    return np.where(cur)[0]


class _Coefs:
    """Lo mínimo de un spline de scipy que usa `_height_spline_to_bspline`."""
    def __init__(self, c):
        self.c = c

    def get_coeffs(self):
        return self.c


def _design(u, v, tu, tv):
    """Matriz de diseño B-spline bicúbica (producto tensorial, fila a fila): n × (nbu·nbv),
    columnas en el orden de FITPACK (i·nbv + j)."""
    from scipy.interpolate import BSpline
    from scipy.sparse import csr_matrix
    Bu = BSpline.design_matrix(u, tu, 3).tocsr()
    Bv = BSpline.design_matrix(v, tv, 3).tocsr()
    n = len(u)
    nbu, nbv = len(tu) - 4, len(tv) - 4
    Bu.sort_indices(); Bv.sort_indices()
    if Bu.nnz != 4 * n or Bv.nnz != 4 * n:
        Bu = Bu.toarray(); Bv = Bv.toarray()
        from scipy.sparse import csr_matrix as C
        return C((Bu[:, :, None] * Bv[:, None, :]).reshape(n, -1))
    iu = Bu.indices.reshape(n, 4); du = Bu.data.reshape(n, 4)
    iv = Bv.indices.reshape(n, 4); dv = Bv.data.reshape(n, 4)
    cols = (iu[:, :, None] * nbv + iv[:, None, :]).reshape(n, 16)
    vals = (du[:, :, None] * dv[:, None, :]).reshape(n, 16)
    return csr_matrix((vals.ravel(), cols.ravel(), np.arange(0, 16 * n + 1, 16)),
                      shape=(n, nbu * nbv))


def _solve_penalized(B, X, P, scale, no, tol, N=None):
    """Resuelve el P-spline (B: diseño, X: datos (n,) o (n,3), P: penalización): la
    penalización más fuerte que deja el 95 % de los puntos propios (`[:no]`) a <= tol, y
    LAMBDA_EXTRA pasos más fina (menos sesgo en costuras). Si X es 3D, el error se mide en
    la normal N. Devuelve (C, e95, rms, máx, sigma, residuo con signo de todos los puntos).
    (Suavizar aquí, cara a cara, DESCUADRABA las costuras -> el suavizado va en la malla,
    `smoothed_mesh`.)"""
    from scipy.sparse.linalg import splu

    def resid(C):
        R = B @ C - X
        return (R * N).sum(1) if R.ndim == 2 else R

    def stats(C):
        r = resid(C)
        ro = np.abs(r[:no])
        return (C, float(np.percentile(ro, 95)), float(np.sqrt((ro ** 2).mean())),
                float(ro.max()), float(np.std(r[:no])), r)

    def solve(A, R, lam):
        lu_ = splu((A + lam * P).tocsc())
        if R.ndim == 1:
            return lu_.solve(np.ascontiguousarray(R))
        return np.stack([lu_.solve(np.ascontiguousarray(R[:, k])) for k in range(R.shape[1])], axis=1)

    A = (B.T @ B).tocsc(); R = B.T @ X
    best = None
    extra = None
    for lam in LAMBDAS:
        try:
            C = solve(A, R, lam * scale)
        except Exception:
            continue
        best = stats(C)
        if extra is None and best[1] <= tol:
            extra = LAMBDA_EXTRA          # unos pasos más finos: menos sesgo en las costuras
        if extra is not None:
            if extra <= 0:
                break
            extra -= 1
    return best


def _dmat(m, cyclic=False):
    """Segundas diferencias de m coeficientes; cíclicas si `cyclic`."""
    import scipy.sparse as sps
    st = [1, -2, 1]
    if cyclic:
        rows = np.repeat(np.arange(m), len(st))
        cols = (np.arange(m)[:, None] + np.arange(len(st))[None, :]).ravel() % m
        return sps.csr_matrix((np.tile(st, m).astype(float), (rows, cols)), shape=(m, m))
    k = m - len(st) + 1
    if k <= 0:
        return sps.csr_matrix((0, m))
    rows = np.repeat(np.arange(k), len(st))
    cols = (np.arange(k)[:, None] + np.arange(len(st))[None, :]).ravel()
    return sps.csr_matrix((np.tile(st, k).astype(float), (rows, cols)), shape=(k, m))


def _diff_penalty(nbu, nbv, su, sv, cyclic_u=False):
    """Penalización isótropa de 2ª diferencia en unidades físicas (≈ ∫f_uu² + f_vv² dA)."""
    from scipy.sparse import identity as sid, kron
    Du, Dv = _dmat(nbu, cyclic_u), _dmat(nbv)
    P = kron(Du.T @ Du, sid(nbv)) / su ** 4
    if Dv.shape[0]:
        P = P + kron(sid(nbu), Dv.T @ Dv) / sv ** 4
    return (P * (su * sv)).tocsc()


def _pspline(u, v, h, bb, ku, kv, no, tol):
    """P-SPLINE: B-spline bicúbica con MUCHOS nudos + penalización de las segundas
    diferencias de los coeficientes (Eilers-Marx). Se elige la penalización MÁS FUERTE
    (superficie más lisa) que aún deja el 95 % de los puntos propios (`[:no]`) a <= tol:
    sin ondas de nudo a nudo (que en las costuras se veían como pliegues de 5-12°) y,
    donde no hay datos, la superficie sigue recta en vez de dispararse."""
    tx = np.linspace(bb[0], bb[1], ku + 2)[1:-1]
    ty = np.linspace(bb[2], bb[3], kv + 2)[1:-1]
    tu = np.r_[[bb[0]] * 4, tx, [bb[1]] * 4]
    tv = np.r_[[bb[2]] * 4, ty, [bb[3]] * 4]
    nbu, nbv = len(tu) - 4, len(tv) - 4
    B = _design(u, v, tu, tv)
    # penalización isótropa: 2ª diferencia / espaciado² en cada dirección
    su, sv = (bb[1] - bb[0]) / (ku + 1), (bb[3] - bb[2]) / (kv + 1)

    P = _diff_penalty(nbu, nbv, su, sv)
    scale = (B.multiply(B).sum() / max(P.diagonal().sum(), 1e-30))
    C, e95, rms, mx, sig, r = _solve_penalized(B, h, P, scale, no, tol)
    return _Coefs(C), e95, tx, ty, rms, mx, sig, r


LAMBDAS = (1e-1, 3e-2, 1e-2, 3e-3, 1e-3, 3e-4, 1e-4, 3e-5, 1e-5, 1e-6, 1e-7)
LAMBDA_EXTRA = 2     # pasos de penalización MÁS FINOS tras cumplir la tolerancia (la más
                     # lisa posible aplanaba la curvatura en las costuras: pliegue mediano 3° -> 1.4°)
MAX_KNOTS = 56       # nudos interiores por lado (P-spline)


def fit_patch(mesh, faces, ns, tol, band=None):
    """B-spline bicúbica (campo de alturas sobre la dirección media del parche) con los
    vértices de una FRANJA de solape con los vecinos (las dos superficies de una costura
    se ajustan a los mismos datos -> casan en la arista). P-spline: la más lisa que deja
    el 95 % de los vértices propios a <= tol (medido en el escaneo del MetroX frente a
    nudos crecientes sin penalizar: 12 caras en vez de 18, máx 0.29 mm en vez de 0.63,
    pliegues p95 4° en vez de 5°, 10× más rápido).
    Devuelve (surf, e95, ok, stats); stats["vdev"] = (vértices propios, desviación normal
    con signo) para el mapa de desviación."""
    from meshfit_brep import _height_spline_to_bspline
    faces = np.asarray(faces, int)
    w = mesh.area_faces[faces]
    n = (ns[faces] * w[:, None]).sum(0)
    n /= np.linalg.norm(n)
    own_v = np.unique(mesh.faces[faces].ravel())
    if band is not None and len(band):
        band = band[ns[band] @ n > 0.2]          # solo lo que sigue siendo grafo
        bv = np.setdiff1d(np.unique(mesh.faces[band].ravel()), own_v)
    else:
        bv = np.zeros(0, int)
    P = mesh.vertices[own_v]; Q = mesh.vertices[bv]
    c = P.mean(0)
    t = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    x0 = np.cross(n, t); x0 /= np.linalg.norm(x0); y0 = np.cross(n, x0)
    d2 = np.c_[(P - c) @ x0, (P - c) @ y0]
    _, _, vt = np.linalg.svd(d2 - d2.mean(0), full_matrices=False)
    x = vt[0, 0] * x0 + vt[0, 1] * y0; y = np.cross(n, x)
    A = np.vstack([P, Q]) - c
    u, v, h = A @ x, A @ y, A @ n
    no = len(P)
    lu, lv = float(np.ptp(u)), float(np.ptp(v))
    mu, mv = 0.03 * lu + 1e-3, 0.03 * lv + 1e-3
    bb = [u.min() - mu, u.max() + mu, v.min() - mv, v.max() + mv]
    # nudos cada ~2.7 mm en 150 mm; si no llega, hasta ~1.5 mm antes de PARTIR el parche
    # (la bisección dejaba un corte recto cruzando el bulbo); la penalización decide lo liso
    for kmax in (MAX_KNOTS, 100):
        step = max(max(lu, lv) / kmax, 0.8)
        ku = int(np.clip(round(lu / step), 3, kmax))
        kv = int(np.clip(round(lv / step), 3, kmax))
        best = _pspline(u, v, h, bb, ku, kv, no, tol)
        if best[1] <= tol:
            break
    sp, e95, tx, ty, rms, mx, sig, r = best
    surf = _height_spline_to_bspline(sp, tx, ty, bb, c, x, y, n)
    vn = _vertex_normals_sub(mesh, own_v)
    st = {"e95": e95, "rms": rms, "max": mx, "sigma": sig,
          "grid": f"{len(tx) + 4}×{len(ty) + 4}",
          "vdev": (own_v, r[:no] * (vn @ n))}            # altura -> distancia normal
    ok = surf is not None and e95 <= tol
    return surf, e95, ok, st


def _vertex_normals_sub(mesh, vidx):
    """Normales de vértice (área ponderada) solo para `vidx`."""
    F = np.asarray(mesh.faces)
    m = np.isin(F, vidx).any(1)
    fn = mesh.face_normals[m] * mesh.area_faces[m][:, None]
    vn = np.zeros((len(mesh.vertices), 3))
    for k in range(3):
        np.add.at(vn, F[m, k], fn)
    vn = vn[vidx]
    return vn / (np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12)


def _split2(mesh, faces):
    """Mitades por la mediana a lo largo del eje mayor (componentes conexas)."""
    C = mesh.triangles_center[faces]
    _, _, vt = np.linalg.svd(C - C.mean(0), full_matrices=False)
    pr = (C - C.mean(0)) @ vt[0]
    side = pr > np.median(pr)
    adj = mesh.face_adjacency
    nf = len(mesh.faces)
    lab = np.full(nf, -1); lab[faces[side]] = 1; lab[faces[~side]] = 0
    comp = _components(adj, lab, nf)
    return [faces[comp[faces] == k] for k in np.unique(comp[faces])]


# --------------------------------------------------------------- tapas + banda
# Los parches-grafo (cubo) dejaban 10-12 caras en el bulbo del MetroX, con un corte recto
# de bisección cruzándolo (captura de Rafa en Fusion). Ahora: TRES caras — tapa de arriba y
# de abajo (campos de alturas) + UNA banda periódica alrededor del canto, parametrizada
# sobre un cilindro (anillo armónico). Probado y DESCARTADO: 2 mitades por la línea de
# partición (disco armónico): costura justo en el canto, pliegues de hasta 14.6°, y las
# puntas del ala tan comprimidas en la parametrización que teselar fino pedía 9 GB.


def _vertex_normals(mesh):
    V = np.asarray(mesh.vertices, float); F = np.asarray(mesh.faces)
    fn = mesh.face_normals * mesh.area_faces[:, None]
    vn = np.zeros((len(V), 3))
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    return vn / (np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12)


def _fill_selection(mesh, sel, keep=1):
    """Tapa los agujeros de una selección de caras: las componentes del resto que no
    estén entre las `keep` mayores pasan a la selección."""
    lab = np.where(sel, 1, 0)
    comp = _components(mesh.face_adjacency, lab, len(mesh.faces))
    if (~sel).any():
        u, c = np.unique(comp[~sel], return_counts=True)
        big = u[np.argsort(-c)[:keep]]
        sel = sel | (~sel & ~np.isin(comp, big))
    return sel


def _annulus_param(mesh, faces):
    """Parametrización de un ANILLO de caras (banda alrededor del canto) sobre un
    cilindro: t armónica (0 en un borde, 1 en el otro) y θ de la interpolación armónica de
    (cos, sin) entre los dos bordes, alineados por arco. Devuelve (vértices, θ, t, L, W)
    o None si la zona no es un anillo."""
    from scipy.sparse.linalg import spsolve
    from scipy.spatial import cKDTree
    from meshfit_repair import _boundary_loops
    F = np.asarray(mesh.faces)[faces]
    used = np.unique(F)
    idx = np.full(len(mesh.vertices), -1); idx[used] = np.arange(len(used))
    Fl = idx[F]; P = np.asarray(mesh.vertices, float)[used]; n = len(used)
    E = np.unique(np.sort(np.r_[Fl[:, [0, 1]], Fl[:, [1, 2]], Fl[:, [2, 0]]], axis=1), axis=0)
    if n - len(E) + len(Fl) != 0:
        return None                                       # no es un anillo (χ ≠ 0)
    loops = _boundary_loops(Fl)
    if len(loops) != 2:
        return None
    b0, b1 = np.array(loops[0]), np.array(loops[1])

    def arc(b):
        sg = np.linalg.norm(P[np.roll(b, -1)] - P[b], axis=1)
        return np.r_[0, np.cumsum(sg)[:-1]], sg.sum()
    s0, L0 = arc(b0)
    th0 = 2 * np.pi * s0 / L0
    # borde 1: sentido y arranque alineados con el borde 0 (θ del punto más cercano)
    _, k = cKDTree(P[b0]).query(P[b1])
    tn = th0[k]
    if np.angle(np.exp(1j * np.diff(np.r_[tn, tn[:1]]))).sum() < 0:
        b1 = b1[::-1]; tn = tn[::-1]
    i0 = int(np.argmin(np.abs(np.angle(np.exp(1j * tn)))))
    b1 = np.roll(b1, -i0); tn = np.roll(tn, -i0)
    s1, L1 = arc(b1)
    th1 = tn[0] + 2 * np.pi * s1 / L1
    A = coo_matrix((np.ones(2 * len(E)), (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
                   shape=(n, n)).tocsr()
    L = (diags(np.asarray(A.sum(1)).ravel()) - A).tocsr()
    bnd = np.r_[b0, b1]
    inner = np.setdiff1d(np.arange(n), bnd)
    Lii = L[inner][:, inner].tocsc(); Lib = L[inner][:, bnd]
    vals = np.c_[np.r_[np.cos(th0), np.cos(th1)], np.r_[np.sin(th0), np.sin(th1)],
                 np.r_[np.zeros(len(b0)), np.ones(len(b1))]]
    out = np.zeros((n, 3)); out[bnd] = vals
    for k_ in range(3):
        out[inner, k_] = spsolve(Lii, -Lib @ vals[:, k_])
    if np.min(np.hypot(out[:, 0], out[:, 1])) < 0.2:
        return None                                       # θ mal definido (banda muy ancha)
    th = np.mod(np.arctan2(out[:, 1], out[:, 0]), 2 * np.pi)
    area = float(mesh.area_faces[faces].sum())
    Lm = 0.5 * (L0 + L1)
    return used, th, out[:, 2], Lm, area / Lm


def periodic_design(th, t, nth, tv, lo, hi):
    """Matriz de diseño: B-spline cúbica uniforme PERIÓDICA en θ (nth polos) × cúbica
    anclada en t (nudos tv). Columnas i·ncs + j (misma convención que `_fit_ring`)."""
    import scipy.sparse as sps
    from scipy.interpolate import BSpline
    from meshfit_brep import _cubic_uniform_w
    ncs = len(tv) - 4
    x = np.mod(th, 2 * np.pi) / (2 * np.pi) * nth
    i0 = np.floor(x).astype(int); wt = _cubic_uniform_w(x - i0)
    Ms = BSpline.design_matrix(np.clip(t, lo, hi - 1e-12), tv, 3).tocoo()
    r_, c_, v_ = Ms.row, Ms.col, Ms.data
    return sps.csr_matrix((np.concatenate([wt[r_, k] * v_ for k in range(4)]),
                           (np.concatenate([r_] * 4),
                            np.concatenate([np.mod(i0[r_] + k, nth) * ncs + c_ for k in range(4)]))),
                          shape=(len(t), nth * ncs))


def periodic_bspline(C, nth, ncs, tv):
    """Polos 3D (nth·ncs × 3) -> Geom_BSplineSurface periódica en U (o None)."""
    from OCP.Geom import Geom_BSplineSurface
    from OCP.TColgp import TColgp_Array2OfPnt
    from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
    from OCP.gp import gp_Pnt
    poles = TColgp_Array2OfPnt(1, nth, 1, ncs)
    for i in range(nth):
        for j in range(ncs):
            poles.SetValue(i + 1, j + 1, gp_Pnt(*map(float, C[i * ncs + j])))
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


def fit_band_periodic(mesh, faces, tol, band, vn):
    """B-spline PERIÓDICA (vuelta completa en θ) para la banda del canto, P-spline sobre
    la parametrización de anillo, con franja de solape. Devuelve (surf, e95, ok, stats) o
    None si la zona no es un anillo."""
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
    th, t = th[order], t[order]
    X = np.asarray(mesh.vertices, float)[used][order]; N = vn[used][order]
    no = int(own.sum())
    lo, hi = float(t.min()) - 0.03, float(t.max()) + 0.03
    best = None
    for step in (4.0, 2.5, 1.6, 1.1):
        nth = int(np.clip(round(Lm / step), 16, 600))
        nts = int(np.clip(round(Wm * (hi - lo) / step), 1, 80))
        tv = np.r_[[lo] * 4, np.linspace(lo, hi, nts + 2)[1:-1], [hi] * 4]
        ncs = len(tv) - 4
        B = periodic_design(th, t, nth, tv, lo, hi)
        sth, sts = Lm / nth, Wm * (hi - lo) / (nts + 1)
        Pm = _diff_penalty(nth, ncs, sth, sts, cyclic_u=True)
        scale = B.multiply(B).sum() / max(Pm.diagonal().sum(), 1e-30)
        r = _solve_penalized(B, X, Pm, scale, no, tol, N=N)
        if r is not None and (best is None or r[1] < best[1] or r[1] <= tol):
            best = (r[0], r[1], nth, ncs, tv, r[2], r[3], r[4], r[5])
        if best is not None and best[1] <= tol:
            break
    C, e95, nth, ncs, tv, rms, mx, sig, rr = best
    surf = periodic_bspline(C, nth, ncs, tv)
    st = {"e95": e95, "rms": rms, "max": mx, "sigma": sig, "grid": f"{nth}×{ncs} (periódica)",
          "param": True, "vdev": (used[order][:no], rr[:no])}
    return surf, e95, (surf is not None and e95 <= tol), st


CAP_CONE = 50.0      # tapas: normales a menos de este ángulo del eje fino de la pieza
                     # (55°: la franja de solape del borde caía casi vertical y se descartaba;
                     # 45°: tapas pequeñas, más costura en zona curva. Pliegue máx 10° a 50°)


def band_segments(mesh, verbose=True, cone_deg=None):
    """Reparto tapas+banda: (zonas, tipo 0/1 = tapa, 2 = banda, normales suavizadas) o
    None si la pieza no se deja partir así."""
    diag = float(np.linalg.norm(mesh.extents))
    ns = smooth_face_normals(mesh, max(1.0, diag / 80.0))
    e3 = _frame(mesh, np.arange(len(mesh.faces)))[2]
    c = np.cos(np.radians(cone_deg or CAP_CONE))
    d = ns @ e3
    lab0 = np.where(d > c, 0, np.where(d < -c, 1, 2))
    segs = organic_segments(mesh, ns=ns, labels0=lab0, graph_check=False,
                            min_area_frac=0.02, verbose=verbose)
    if len(segs) != 3:
        if verbose:
            print(f"  [orgánico] tapas+banda: {len(segs)} zonas (se esperaban 3) -> parches")
        return None
    kind = [int(np.bincount(lab0[f], minlength=3).argmax()) for f in segs]
    if sorted(kind) != [0, 1, 2]:
        return None
    return segs, kind, ns


def _band_layout(mesh, tol, Af, rings, verbose, cone_deg=None):
    """TRES caras: tapa de arriba y tapa de abajo (campos de alturas sobre el eje fino de
    la pieza, normales a < `cone_deg`) + UNA banda periódica que da la vuelta al canto.
    Las costuras quedan a ~45° de la línea de partición, en zona de curvatura moderada (con
    la costura JUSTO en el canto, 2 caras, los pliegues llegaban a 14.6°). Devuelve
    (labels, surfs, errs, stats) o None si la pieza no tiene esa forma o algo no ajusta."""
    sg = band_segments(mesh, verbose, cone_deg)
    if sg is None:
        return None
    segs, kind, ns = sg
    vn = _vertex_normals(mesh)
    labels = np.full(len(mesh.faces), -1, int)
    surfs, errs, pst = [], [], []
    for f, kd in zip(segs, kind):
        bandf = _band(Af, f, rings)
        if kd == 2:
            r = fit_band_periodic(mesh, f, tol, bandf, vn)
        else:
            r = fit_patch(mesh, f, ns, tol, band=bandf)
        if r is None or not r[2]:
            if verbose:
                what = "banda" if kd == 2 else "tapa"
                print(f"  [orgánico] tapas+banda: la {what} " +
                      ("no es un anillo/disco" if r is None else f"no ajusta (p95 {r[1]:.3f})") +
                      " -> parches")
            return None
        labels[f] = len(surfs); surfs.append(r[0]); errs.append(r[1]); pst.append(r[3])
    return labels, surfs, errs, pst


# --------------------------------------------------------------------------- SUAVIZADO
_SMOOTH_CACHE = {}


def smoothed_mesh(mesh, smooth, verbose=True):
    """Malla SUAVIZADA (mismas caras; vértices movidos solo en su NORMAL) para el control
    «Suavizado» de las piezas orgánicas. Global: no depende del reparto en caras.

    · Difusión G (pasos explícitos sobre la malla, alcance ~L mm) y «TWICING» de Tukey:
      desplazamiento = −(I−G)²·x. Un filtro de difusión simple ENCOGE las zonas curvas
      (un redondeo de 3 mm perdía décimas); aplicando el paso alto dos veces el sesgo
      baja a orden L⁴ (volumen −0.5 % con el máximo, 5 mm).
    · ROBUSTO: los vértices que se salen > 4σ del entorno (picos del escaneo) se llevan a
      la media de sus vecinos ANTES de filtrar: no arrastran la superficie (como al sacar
      un plano de mil puntos descartando los de más error).
    Probado y DESCARTADO: suavizar cada cara NURBS por separado (las costuras se
    descuadraban hasta 17-19°: cada parametrización suaviza a su manera), filtro implícito
    con gradiente conjugado (100 s) y Taubin (hinchaba la pieza +0.4 %).
    Determinista y con caché. Devuelve un trimesh (la misma malla si smooth = 0)."""
    import time
    import trimesh
    L = smooth_length(smooth)
    if L <= 0:
        return mesh
    V = np.asarray(mesh.vertices, float)
    F = np.asarray(mesh.faces)
    diag = float(np.linalg.norm(np.ptp(V, axis=0)))
    key = _key(mesh, organic_tol(diag), L)
    if key in _SMOOTH_CACHE:
        return _SMOOTH_CACHE[key]
    t0 = time.time()
    n = len(V)
    e = np.unique(np.sort(np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], axis=1), axis=0)
    A = coo_matrix((np.ones(2 * len(e)), (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])),
                   shape=(n, n)).tocsr()
    A.data[:] = 1.0
    W = (diags(1.0 / np.maximum(np.asarray(A.sum(1)).ravel(), 1)) @ A).tocsr()
    h = float(np.median(np.linalg.norm(V[e[:, 0]] - V[e[:, 1]], axis=1))) or 1.0
    tau = 0.5
    steps = int(np.clip(np.ceil((L / h) ** 2 / tau), 1, 4000))

    def G(X):
        X = X.copy()
        for _ in range(steps):
            X += tau * (W @ X - X)
        return X
    nrm = _vertex_normals(mesh)
    r1 = V - G(V)
    sv = (r1 * nrm).sum(1)
    sig = 1.4826 * float(np.median(np.abs(sv))) + 1e-12
    spikes = np.abs(sv) > 4 * sig
    X0 = V.copy()
    X0[spikes] -= r1[spikes]                       # picos -> media de su entorno
    r1 = X0 - G(X0)
    r2 = r1 - G(r1)                                # (I-G)² x
    Vs = X0 - (r2 * nrm).sum(1)[:, None] * nrm     # solo en la normal: sin deriva tangencial
    out = trimesh.Trimesh(Vs, F, process=False)
    if verbose:
        d = ((Vs - V) * nrm).sum(1)
        print(f"  [suavizado] {L:.2f} mm ({steps} pasos, {100 * spikes.mean():.1f} % picos): "
              f"desplazamiento sigma {np.std(d):.4f}, p95 {np.percentile(np.abs(d), 95):.4f}, "
              f"máx {np.abs(d).max():.4f} mm en {time.time() - t0:.1f}s")
    while len(_SMOOTH_CACHE) >= 2:
        _SMOOTH_CACHE.pop(next(iter(_SMOOTH_CACHE)))
    _SMOOTH_CACHE[key] = out
    return out


def organic_tol(diag):
    """Tolerancia de ajuste de los parches orgánicos: 1/4 de la de zona libre del sólido
    (0.05 mm en una pieza de 200 mm). Un escaneo suavizado del MetroX tiene ~0.005 mm
    de ruido: la NURBS puede pegarse mucho más que en una zona libre de CAD."""
    return max(0.01, 0.25 * max(0.01, 1e-3 * diag))


_CACHE = {}          # clave de malla+tol -> (labels, surfs, stats): 🐍 Detectar -> 💾 Exportar


def _key(mesh, tol, smooth_len=0.0):
    import hashlib
    h = hashlib.md5(np.ascontiguousarray(mesh.faces, dtype=np.int64).tobytes())
    h.update(np.ascontiguousarray(mesh.vertices, dtype=np.float64).tobytes())
    h.update(repr((round(float(tol), 9), round(float(smooth_len), 6))).encode())
    return h.hexdigest()


def smooth_length(smooth):
    """Control de la UI (0..1) -> longitud de suavizado L en mm. 0 = FIEL al escaneo;
    0.25 ≈ 0.9 mm, 0.5 ≈ 1.7 mm, 0.75 ≈ 3.2 mm, 1 = 6 mm. Con el armónico en 2 fases
    (`meshfit_fair.harmonic`) en el bulbo del MetroX: 3 mm -> desviación media 0.07 mm;
    4.5 mm -> 0.12 mm (máx 1.4 en las puntas finas del ala), costuras 0.18°; 6 mm ya
    encoge (−0.7 %) y redondea las puntas."""
    s_ = float(smooth or 0.0)
    return 0.0 if s_ <= 0 else 0.5 * 12.0 ** min(s_, 1.0)


def organic_surfaces(mesh, tol, verbose=True, min_split=4000):
    """Etiqueta por triángulo + B-spline por parche para una pieza orgánica.
    Devuelve (labels, surfs, stats). Determinista y con caché (la vista previa del visor
    y el sólido exportado son EXACTAMENTE los mismos parches). Para suavizar, pasar la
    malla de `smoothed_mesh`."""
    import time
    key = _key(mesh, tol)
    if key in _CACHE:
        labels, surfs, st = _CACHE[key]
        if verbose:
            print(f"  [orgánico] {len(surfs)} B-splines (caché)")
        return labels.copy(), list(surfs), st
    t0 = time.time()
    diag = float(np.linalg.norm(mesh.extents))
    Af = _face_adj_matrix(mesh)
    h = float(np.median(np.linalg.norm(mesh.vertices[mesh.faces[:, 0]] -
                                       mesh.vertices[mesh.faces[:, 1]], axis=1)))
    rings = int(np.clip(round(OVERLAP * diag / h), 2, 40))     # franja de solape (mm / arista)
    # 1º: TRES caras (tapas + banda del canto); si la pieza no se deja, parches-grafo
    hv = _band_layout(mesh, tol, Af, rings, verbose)
    if hv is not None:
        labels, surfs, errs, pst = hv
        stack = []
        layout = "tapas+banda"
    else:
        ns = smooth_face_normals(mesh, max(1.0, diag / 80.0))
        segs = organic_segments(mesh, ns=ns, verbose=verbose)
        labels = np.full(len(mesh.faces), -1, int)
        surfs, errs, pst = [], [], []
        stack = list(segs)
        layout = "parches"
    while stack:
        f = stack.pop()
        surf, e95, ok, st = fit_patch(mesh, f, ns, tol, band=_band(Af, f, rings))
        if not ok and len(f) >= min_split:
            parts = _split2(mesh, f)
            if len(parts) >= 2:
                stack += parts
                continue
        if surf is None:
            continue                         # lo recoge el vecino más cercano (abajo)
        labels[f] = len(surfs); surfs.append(surf); errs.append(e95); pst.append(st)
    if verbose:
        print(f"  [orgánico] {len(surfs)} B-splines ({layout}) en {time.time() - t0:.1f}s; "
              f"error p95 por parche: máx {max(errs):.3f} mm, mediana {np.median(errs):.3f} "
              f"(tol {tol:.3f}); sin superficie {int((labels < 0).sum())} tri")
    # desviación normal con signo por vértice (malla -> superficie) para el mapa de color
    vdev = np.full(len(mesh.vertices), np.nan)
    for ps in pst:
        if "vdev" in ps:
            vi, dv = ps.pop("vdev")
            vdev[vi] = dv
    ok_ = np.isfinite(vdev)
    stats = {"e95": errs, "patches": pst, "layout": layout, "vdev": vdev,
             "sigma": float(np.std(vdev[ok_])) if ok_.any() else 0.0,
             "dev_max": float(np.abs(vdev[ok_]).max()) if ok_.any() else 0.0,
             "dev_p95": float(np.percentile(np.abs(vdev[ok_]), 95)) if ok_.any() else 0.0}
    while len(_CACHE) >= 2:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = (labels.copy(), list(surfs), stats)
    return labels, surfs, stats


def organic_preview(mesh, grid0=40, verbose=True, smooth=0.0, ajuste_ia=False):
    """Vista previa para el visor: los MISMOS parches que irán al sólido (reparación +
    suavizado + `organic_surfaces`, en caché para el export). Devuelve
    {"patches": [...], "dev": base64 float16 por cara ORIGINAL (desviación con signo
    escaneo -> superficie, mm), "stats": {sigma, p95, max, media}, "smooth_mm": L}.
    Cada parche: caras en el índice de la malla ORIGINAL (las del relleno de agujeros no
    existen en el visor), teselado de su B-spline recortado a su región (celdas de una
    rejilla UV cuyo punto cae sobre la región) y estadísticas del ajuste."""
    import base64
    from scipy.spatial import cKDTree
    from meshfit_repair import repair_mesh
    nf0 = len(mesh.faces)
    if mesh.is_watertight:
        m2, fmap = mesh, np.arange(nf0)
    else:
        m2, fmap, _ = repair_mesh(mesh, verbose=verbose)
    diag = float(np.linalg.norm(m2.extents))
    ia_report = []
    base = m2
    if ajuste_ia:
        # mismo orden que build_solid: simetrías -> suavizado armónico -> NURBS
        from meshfit_ideal import ai_prepare
        from meshfit_brep import IA_ORGANIC_SMOOTH
        base, ia_report = ai_prepare(m2, verbose=verbose)
        ia_report = list(ia_report)
        if not smooth:
            smooth = IA_ORGANIC_SMOOTH
        ia_report.append(f"Pieza orgánica: superficies ARMÓNICAS ajustadas a la vez (L "
                         f"{smooth_length(smooth):.1f} mm): malla alisada penalizando el cambio de curvatura (sin ondas ni islas, sin encoger) y 3 caras ajustadas a la vez -> costuras tangentes")
    fair = None
    if smooth and smooth > 0:
        # SUAVIZADO = ARMÓNICO en 2 fases (malla alisada + caras a la vez); si la pieza no
        # admite tapas+banda, suavizado de la malla
        from meshfit_fair import harmonic
        fair = harmonic(base, smooth, verbose=verbose)
    if fair is not None:
        ms = fair[0]
        labels, surfs, st = fair[1].copy(), list(fair[2]), fair[3]
    else:
        ms = smoothed_mesh(base, smooth, verbose=verbose)
        labels, surfs, st = organic_surfaces(ms, organic_tol(diag), verbose=verbose)
    inv = np.full(len(m2.faces), -1, np.int64)
    ok = fmap >= 0
    inv[fmap[ok]] = np.where(ok)[0]
    # desviación escaneo ORIGINAL -> superficie: residuo del ajuste (sobre la malla
    # suavizada) + lo que el suavizado movió cada vértice (en su normal)
    vd = np.nan_to_num(np.asarray(st["vdev"], float))
    same_topo = len(ms.faces) == len(m2.faces) and np.array_equal(np.asarray(ms.faces), np.asarray(m2.faces))
    if same_topo:
        if ms is not m2:
            vd = vd + ((np.asarray(ms.vertices) - np.asarray(m2.vertices)) * _vertex_normals(m2)).sum(1)
    else:
        # malla de la fase 1 (otras caras): desviación de cada vértice original = altura
        # sobre el plano tangente del vértice alisado más cercano + residuo del ajuste allí
        from scipy.spatial import cKDTree as _T
        Vs = np.asarray(ms.vertices); ns_ = _vertex_normals(ms)
        _, kk = _T(Vs).query(np.asarray(m2.vertices))
        vd = vd[kk] - ((np.asarray(m2.vertices) - Vs[kk]) * ns_[kk]).sum(1)
    fdev = vd[np.asarray(m2.faces)].mean(1)
    dev0 = np.zeros(nf0)
    dev0[inv[inv >= 0]] = fdev[inv >= 0]
    real = inv >= 0
    a = np.abs(fdev[real])
    dstats = {"sigma": float(np.std(fdev[real])), "p95": float(np.percentile(a, 95)),
              "max": float(a.max()), "mean": float(a.mean())}
    if not same_topo:                                  # etiqueta de cada cara original
        _, kf = cKDTree(np.asarray(ms.triangles_center)).query(np.asarray(m2.triangles_center))
        orig_lab = labels[kf]
    m2 = ms                                            # teselado/recorte sobre la suavizada
    tree = cKDTree(np.asarray(m2.triangles_center))
    h = float(np.median(np.linalg.norm(m2.vertices[m2.faces[:, 0]] - m2.vertices[m2.faces[:, 1]],
                                       axis=1)))
    out = []
    for l, srf in enumerate(surfs):
        f2 = np.where(labels == l)[0]
        # rejilla de dibujo según el tamaño del parche (una tapa de 150k triángulos con
        # 40×40 salía a celdas de 4 mm); la banda paramétrica, siempre fina
        grid = 160 if st["patches"][l].get("param") else \
            int(np.clip(np.sqrt(len(f2)) / 2.5, grid0, 160))
        u0, u1, v0, v1 = srf.Bounds()
        us, vs = np.linspace(u0, u1, grid + 1), np.linspace(v0, v1, grid + 1)
        P = np.empty((grid + 1, grid + 1, 3))
        for i, a in enumerate(us):
            for j, b in enumerate(vs):
                q = srf.Value(float(a), float(b))
                P[i, j] = (q.X(), q.Y(), q.Z())
        cen = 0.25 * (P[:-1, :-1] + P[1:, :-1] + P[:-1, 1:] + P[1:, 1:]).reshape(-1, 3)
        cell = float(np.linalg.norm(P[1, 1] - P[0, 0])) + 3 * h
        d, k = tree.query(cen)
        # las 4 esquinas también sobre la pieza: fuera de los datos la B-spline extrapola y
        # una celda de borde se estiraba en una «púa» larga (solo afecta a la vista previa;
        # el sólido va recortado por las aristas)
        dc, _ = tree.query(P.reshape(-1, 3))
        dc = dc.reshape(grid + 1, grid + 1)
        cmax = np.maximum.reduce([dc[:-1, :-1], dc[1:, :-1], dc[:-1, 1:], dc[1:, 1:]]).reshape(-1)
        keep = (labels[k] == l) & (d < cell) & (cmax < cell)
        tris, used = [], np.zeros((grid + 1) * (grid + 1), bool)
        for c in np.where(keep)[0]:
            i, j = divmod(int(c), grid)
            a = i * (grid + 1) + j
            b, cc, dd = a + grid + 1, a + 1, a + grid + 2
            tris += [(a, b, dd), (a, dd, cc)]
            used[[a, b, cc, dd]] = True
        idx = np.full(len(used), -1); idx[used] = np.arange(int(used.sum()))
        V = P.reshape(-1, 3)[used]
        T = idx[np.array(tris, int)] if tris else np.zeros((0, 3), int)
        if same_topo:
            fo = inv[f2]
        else:
            fo = inv[np.where(orig_lab == l)[0]]
        ps = st["patches"][l]
        out.append({"faces": fo[fo >= 0].tolist(), "vertices": np.round(V, 4).tolist(),
                    "triangles": T.tolist(), "rms": ps["rms"], "max": ps["max"],
                    "e95": ps["e95"], "grid": ps["grid"]})
    return {"patches": out, "smooth_mm": smooth_length(smooth), "stats": dstats,
            "ideal": ia_report,
            "dev": base64.b64encode(dev0.astype(np.float16).tobytes()).decode("ascii")}
