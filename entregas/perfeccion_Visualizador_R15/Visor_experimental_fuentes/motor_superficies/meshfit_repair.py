"""
MeshFit — reparación de mallas de ESCÁNER antes de construir el sólido.

Un sólido B-rep solo se cierra si la malla es estanca. Los escaneos reales (Revopoint
MetroX, oct 2026) llegan con:
  · triángulos DEGENERADOS (un vértice repetido): parejas sueltas que además crean
    aristas no-variedad (4 caras por arista);
  · AGUJEROS donde el escáner no vio (punta del ala: un hueco de 13×11 mm).

`repair_mesh` quita lo degenerado y las islas diminutas, y RELLENA cada agujero con un
disco de anillos concéntricos cuya forma se calcula por ALISADO BILAPLACIANO (Liepa
2003): los vértices nuevos minimizan la curvatura y empalman en tangencia con la malla
de alrededor, en vez de un parche plano que delataría el hueco.

Las caras originales conservan su ORDEN (el visor y la detección usan índices de cara):
`face_map[i]` = índice nuevo de la cara original i (-1 si se quitó); las de relleno van
al final.
"""
import numpy as np
import trimesh
from scipy.sparse import coo_matrix, csr_matrix, identity, diags
from scipy.sparse.linalg import spsolve


def _boundary_loops(F):
    """Bucles de borde ORIENTADOS: semiaristas a->b sin gemela b->a, encadenadas.
    Cada bucle sigue el sentido de los triángulos que lo tocan."""
    ha = F.reshape(-1); hb = F[:, [1, 2, 0]].reshape(-1)
    nv = int(F.max()) + 1
    key = ha.astype(np.int64) * nv + hb
    tw = hb.astype(np.int64) * nv + ha
    lone = ~np.isin(key, tw)
    nxt = {}
    for a, b in zip(ha[lone].tolist(), hb[lone].tolist()):
        nxt.setdefault(a, []).append(b)
    loops, used = [], set()
    for a0 in list(nxt):
        for b0 in nxt[a0]:
            if (a0, b0) in used:
                continue
            seq = [a0]; a, b = a0, b0
            while True:
                used.add((a, b))
                if b == a0:
                    break
                seq.append(b)
                cand = [c for c in nxt.get(b, []) if (b, c) not in used]
                if not cand:
                    seq = None           # borde abierto (pellizco): no es un agujero simple
                    break
                a, b = b, cand[0]
            if seq is not None and len(seq) >= 3:
                loops.append(seq)
    return loops


def _resample_closed(P, n):
    """n puntos uniformes por longitud de arco sobre una polilínea CERRADA."""
    Q = np.vstack([P, P[:1]])
    cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
    t = np.linspace(0, cum[-1], n, endpoint=False)
    return np.c_[[np.interp(t, cum, Q[:, k]) for k in range(3)]].T, t / cum[-1]


def _strip(ia, ta, ib, tb):
    """Triangula la banda entre dos anillos cerrados (índices + parámetro 0..1 de cada
    punto) avanzando siempre por el que va más atrasado (estilo «loft»)."""
    out = []
    na, nb = len(ia), len(ib)
    i = j = 0
    # alinear el arranque del anillo interior con el exterior
    j0 = int(np.argmin(np.abs(((tb - ta[0]) + 0.5) % 1.0 - 0.5)))
    ib = list(ib[j0:]) + list(ib[:j0])
    tb = np.r_[tb[j0:], tb[:j0] + 1.0] - tb[j0] + ta[0]
    ta = np.r_[ta, ta[0] + 1.0]; tb = np.r_[tb, tb[0] + 1.0]
    ia = list(ia) + [ia[0]]; ib = list(ib) + [ib[0]]
    while i < na or j < nb:
        if j >= nb or (i < na and ta[i + 1] <= tb[j + 1]):
            out.append((ia[i], ia[i + 1], ib[j])); i += 1
        else:
            out.append((ia[i], ib[j + 1], ib[j])); j += 1
    return out


def _fill_hole(V, loop, h):
    """Disco de anillos concéntricos que tapa `loop` (orden del borde). Devuelve
    (vértices nuevos, caras con índices: >=0 originales, <0 -> -1-k nuevo k)."""
    P = V[loop]
    c = P.mean(0)
    per = float(np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1).sum())
    rad = per / (2 * np.pi)
    K = max(1, int(round(rad / h)))                  # nº de anillos interiores
    n0 = len(loop)
    cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1))]
    t0 = cum[:-1] / cum[-1]
    new = []
    rings = [(list(loop), t0)]
    for k in range(1, K + 1):
        f = 1.0 - k / (K + 1)
        nk = max(3, int(round(n0 * f)))
        if nk <= 3 and k < K:
            nk = 3
        R, tk = _resample_closed(c + (P - c) * f, nk)
        ids = [-1 - (len(new) + i) for i in range(nk)]
        new.extend(R)
        rings.append((ids, tk))
        if nk == 3:
            break
    faces = []
    for (ia, ta), (ib, tb) in zip(rings[:-1], rings[1:]):
        faces += _strip(ia, ta, ib, tb)
    # centro
    ids, _ = rings[-1]
    cid = -1 - len(new); new.append(c)
    for i in range(len(ids)):
        faces.append((ids[i], ids[(i + 1) % len(ids)], cid))
    return np.array(new), faces


def _fair(V, F, free, fixed_mask):
    """Alisado bilaplaciano (pesos uniformes): L²x = 0 en los vértices `free`, el resto
    fijo. El anillo de malla original alrededor del agujero entra en L² -> empalme C1."""
    nv = len(V)
    e = np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]
    e = np.unique(np.sort(e, axis=1), axis=0)
    A = coo_matrix((np.ones(2 * len(e)), (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])),
                   shape=(nv, nv)).tocsr()
    A.data[:] = 1.0
    deg = np.asarray(A.sum(1)).ravel()
    L = identity(nv, format="csr") - diags(1.0 / np.maximum(deg, 1)) @ A
    L2 = (L @ L).tocsr()
    free = np.asarray(free, int)
    fx = np.where(~np.isin(np.arange(nv), free))[0]
    Aii = L2[free][:, free]
    Aif = L2[free][:, fx]
    out = V.copy()
    for k in range(3):
        out[free, k] = spsolve(Aii.tocsc(), -Aif @ V[fx, k])
    return out


def repair_mesh(mesh, max_hole_frac=0.25, verbose=True):
    """Malla estanca para el sólido. Devuelve (malla_nueva, face_map, info).
    No toca mallas ya estancas (face_map identidad)."""
    V = np.asarray(mesh.vertices, float)
    F = np.asarray(mesh.faces, np.int64)
    nf0 = len(F)
    keep = np.ones(nf0, bool)
    # 1) degenerados: vértice repetido o área nula
    keep &= (F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])
    area = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    keep &= area > 1e-12
    # 2) islas diminutas (restos sueltos del escaneo): < 0.5 % de las caras
    tm = trimesh.Trimesh(V, F[keep], process=False)
    comps = trimesh.graph.connected_components(tm.face_adjacency, nodes=np.arange(len(tm.faces)),
                                               min_len=1)
    idx_keep = np.where(keep)[0]
    big = max(len(c) for c in comps)
    for c in comps:
        if len(c) < max(50, 0.005 * big) and len(c) < big:
            keep[idx_keep[np.asarray(c)]] = False
    info = {"removed_faces": int(nf0 - keep.sum()), "holes": 0, "fill_faces": 0,
            "big_holes": 0}
    F1 = F[keep]
    loops = _boundary_loops(F1)
    if not loops and info["removed_faces"] == 0:
        return mesh, np.arange(nf0), info
    diag = float(np.linalg.norm(np.ptp(V, axis=0)))
    h = float(np.median(np.linalg.norm(V[F1[:, 0]] - V[F1[:, 1]], axis=1)))
    newV = [V]; nV = len(V); add = []
    free = []
    for lp in loops:
        P = V[lp]
        span = float(np.linalg.norm(np.ptp(P, axis=0)))
        if span > max_hole_frac * diag:
            info["big_holes"] += 1          # el borde de una pieza abierta: no se inventa
            continue
        # el relleno se recorre AL REVÉS que el borde (las caras vecinas lo usan a->b)
        nv_, fc = _fill_hole(V, lp[::-1], h)
        base = nV + sum(len(x) for x in newV[1:])
        fc = np.array([[x if x >= 0 else base + (-1 - x) for x in t] for t in fc], np.int64)
        newV.append(nv_); add.append(fc)
        free.extend(range(base, base + len(nv_)))
        info["holes"] += 1
    V2 = np.vstack(newV)
    F2 = np.vstack([F1] + add) if add else F1
    if free:
        V2 = _fair(V2, F2, free, None)
    info["fill_faces"] = int(len(F2) - len(F1))
    face_map = np.full(nf0, -1, np.int64)
    face_map[keep] = np.arange(int(keep.sum()))
    m2 = trimesh.Trimesh(V2, F2, process=False)
    m2.remove_unreferenced_vertices()
    if verbose:
        print(f"  [reparar] {info['removed_faces']} caras degeneradas/sueltas fuera, "
              f"{info['holes']} agujero(s) rellenado(s) con {info['fill_faces']} caras; "
              f"estanca={m2.is_watertight}")
    return m2, face_map, info


def remap_result(result, face_map):
    """Índices de cara del resultado de `detect` -> malla reparada."""
    def rm(fs):
        f = face_map[np.asarray(fs, int)]
        return f[f >= 0].tolist()
    out = dict(result)
    out["primitives"] = []
    for p in result.get("primitives", []):
        q = dict(p); q["faces"] = rm(p["faces"])
        if q["faces"]:
            out["primitives"].append(q)
    out["freeform_regions"] = [r for r in (rm(r) for r in result.get("freeform_regions", [])) if r]
    return out


if __name__ == "__main__":
    import sys
    m = trimesh.load(sys.argv[1], force="mesh")
    m.merge_vertices()
    m2, fm, info = repair_mesh(m)
    print(info, "estanca", m2.is_watertight, "vol", m2.volume if m2.is_watertight else None)
    if len(sys.argv) > 2:
        m2.export(sys.argv[2])
