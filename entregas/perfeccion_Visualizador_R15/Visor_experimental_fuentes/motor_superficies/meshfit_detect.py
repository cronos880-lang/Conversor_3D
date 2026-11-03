"""
MeshFit — detección de primitivas (motor Python).

Carga una malla STL, la segmenta por ángulo diedro y ajusta a cada región la mejor
primitiva analítica (plano, cilindro, cono, esfera, toro). A diferencia de la versión
JS, NO fuerza una primitiva: si el ajuste es malo (RMS relativo alto) marca la región
como 'freeform' (sin clasificar), lo que evita geometría fantasma (toros/cilindros que
no existen). Además calcula el rango paramétrico real de cada superficie curva para
poder recortarla a su trozo (medio cilindro, cuarto de toro, etc.) al exportar.
"""
import numpy as np
import trimesh
from trimesh.graph import connected_components


# ----------------------------- Ajustes -----------------------------------
def fit_plane(pts, normals=None, areas=None, cents=None):   # firma uniforme para FIT[]
    c = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    n = vt[2] / np.linalg.norm(vt[2])
    return {"type": "plane", "point": c, "normal": n}


def dev_plane(p, pts):
    return np.abs((pts - p["point"]) @ p["normal"])


def fit_sphere(pts, normals=None, areas=None, cents=None):  # firma uniforme para FIT[]
    A = np.hstack([2 * pts, np.ones((len(pts), 1))])
    b = (pts ** 2).sum(axis=1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = sol[:3]
    R = np.sqrt(max(1e-12, sol[3] + c @ c))
    return {"type": "sphere", "center": c, "radius": float(R)}


def dev_sphere(p, pts):
    return np.abs(np.linalg.norm(pts - p["center"], axis=1) - p["radius"])


def _fit_circle_2d(uv):
    A = np.hstack([2 * uv, np.ones((len(uv), 1))])
    b = (uv ** 2).sum(axis=1)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    c = sol[:2]
    R = np.sqrt(max(1e-12, sol[2] + c @ c))
    return c, float(R)


def _axis_from_normals(normals, areas):
    w = areas / areas.sum()
    nbar = (normals * w[:, None]).sum(axis=0)
    X = normals - nbar
    cov = (X * w[:, None]).T @ X
    _, vecs = np.linalg.eigh(cov)
    a = vecs[:, 0]
    return a / np.linalg.norm(a)


def _perp_basis(axis):
    ref = np.array([1.0, 0, 0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1, 0])
    u = np.cross(axis, ref); u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    return u, v


def fit_cylinder(pts, normals, areas, cents=None):
    axis = _axis_from_normals(normals, areas)
    u, v = _perp_basis(axis)
    uv = np.column_stack([pts @ u, pts @ v])
    c2, R = _fit_circle_2d(uv)
    t = pts @ axis
    axis_pt = u * c2[0] + v * c2[1] + axis * t.mean()
    return {"type": "cylinder", "axis": axis, "point": axis_pt, "radius": R,
            "tmin": float(t.min()), "tmax": float(t.max()), "u": u, "v": v, "c2": c2}


def dev_cylinder(p, pts):
    d = pts - p["point"]
    t = d @ p["axis"]
    radial = d - np.outer(t, p["axis"])
    return np.abs(np.linalg.norm(radial, axis=1) - p["radius"])


def fit_cone(pts, normals, areas, cents=None):
    axis = _axis_from_normals(normals, areas)
    origin = pts.mean(axis=0)
    d = pts - origin
    t = d @ axis
    if float(t.max() - t.min()) < 1e-9:
        return None                       # anillo/disco perpendicular al eje: cono indefinido
    radial = np.linalg.norm(d - np.outer(t, axis), axis=1)
    # r = m t + b
    m, b = np.polyfit(t, radial, 1)
    if m < 0:
        axis = -axis; t = -t
        m, b = np.polyfit(t, radial, 1)
    half = float(np.arctan(abs(m)))
    return {"type": "cone", "axis": axis, "origin": origin, "half_angle": half,
            "tmin": float(t.min()), "tmax": float(t.max()),
            "r_base": float(m * t.min() + b), "r_top": float(m * t.max() + b), "slope": float(m), "b": float(b)}


def dev_cone(p, pts):
    d = pts - p["origin"]
    t = d @ p["axis"]
    radial = np.linalg.norm(d - np.outer(t, p["axis"]), axis=1)
    r_ideal = p["slope"] * t + p["b"]
    return np.abs(radial - r_ideal) * np.cos(p["half_angle"])


def _torus_from_axis(pts, axis, q):
    """Toro dado el eje (dirección `axis` + punto `q`): círculo en el plano (rho, h)."""
    d = pts - q
    h = d @ axis
    rho = np.linalg.norm(d - np.outer(h, axis), axis=1)
    c2, r = _fit_circle_2d(np.column_stack([rho, h]))
    R, h0 = float(c2[0]), float(c2[1])
    if not (R > r > 0):
        return None
    return {"type": "torus", "center": q + axis * h0, "axis": axis, "R": R, "r": r}


def fit_torus(pts, normals, areas, cents=None):
    """Ajuste de toro. El ajuste ingenuo (eje por SVD de los puntos, centro = centroide)
    solo vale para anillos casi COMPLETOS: en un parche parcial (un arco de fillet) el
    centroide no está en el eje y sale un toro torcido que aun así pasa el umbral de RMS.
    Si hay centroides+normales de cara se refina: los centros de tubo (centroide − r·normal)
    de un toro real caen en un círculo alrededor del eje → su plano da el eje verdadero.
    Se prueban ambos signos de la normal (fillet convexo/cóncavo) y se queda el mejor."""
    c0 = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c0, full_matrices=False)
    axis = vt[2] / np.linalg.norm(vt[2])
    best = _torus_from_axis(pts, axis, c0)
    if cents is None or best is None:
        return best
    best_rms = stats(best, pts)[0]
    r = best["r"]
    for sign in (-1.0, 1.0):
        cur_r = r
        for _ in range(3):                                # iterar: eje -> r -> eje
            tc = cents + sign * cur_r * normals           # centros de tubo estimados
            cq = tc.mean(axis=0)
            _, _, vt2 = np.linalg.svd(tc - cq, full_matrices=False)
            a2 = vt2[2] / np.linalg.norm(vt2[2])
            # centro del CÍRCULO de centros de tubo (no su centroide, que en un parche
            # parcial queda fuera del eje): círculo 2D en el plano de los centros de tubo
            e1, e2 = _perp_basis(a2)
            d2 = tc - cq
            c2, _Rc = _fit_circle_2d(np.column_stack([d2 @ e1, d2 @ e2]))
            q = cq + e1 * c2[0] + e2 * c2[1]              # punto en el eje verdadero
            prim = _torus_from_axis(pts, a2, q)
            if prim is None:
                break
            rms = stats(prim, pts)[0]
            if rms < best_rms:
                best, best_rms = prim, rms
            if abs(prim["r"] - cur_r) < 1e-6:
                break
            cur_r = prim["r"]
    return best


def dev_torus(p, pts):
    d = pts - p["center"]
    h = d @ p["axis"]
    rho = np.linalg.norm(d - np.outer(h, p["axis"]), axis=1)
    return np.abs(np.sqrt((rho - p["R"]) ** 2 + h ** 2) - p["r"])


DEV = {"plane": dev_plane, "sphere": dev_sphere, "cylinder": dev_cylinder,
       "cone": dev_cone, "torus": dev_torus}
FIT = {"plane": fit_plane, "sphere": fit_sphere, "cylinder": fit_cylinder,
       "cone": fit_cone, "torus": fit_torus}
# Penalización por complejidad para evitar sobreajuste (preferir lo simple).
PENALTY = {"plane": 1.0, "cylinder": 1.05, "sphere": 1.08, "cone": 1.2, "torus": 1.3}


def stats(prim, pts):
    dev = DEV[prim["type"]](prim, pts)
    return float(np.sqrt((dev ** 2).mean())), float(np.abs(dev).max())


# ----------------------- Detección por región -----------------------------
def _degenerate(ty, prim, diag):
    """Descarta ajustes curvos que en realidad son un plano u otra primitiva más simple."""
    if ty == "cylinder" and prim["radius"] > 3 * diag:
        return True                       # radio enorme ≈ plano
    if ty == "sphere" and prim["radius"] > 5 * diag:
        return True
    if ty == "torus" and (prim["R"] > 3 * diag or prim["r"] > diag):
        return True
    if ty == "cone":
        ha = np.degrees(prim["half_angle"])
        if ha < 3 or ha > 87:             # ≈ cilindro o ≈ plano
            return True
    return False


# Cuando varias primitivas ajustan casi perfecto (RMS≈0, p. ej. un arco de cilindro
# que también vale como esfera o toro), el RMS crudo no desempata bien: hay que
# preferir la primitiva más simple. Este epsilon hace que la PENALTY mande en los
# empates sin afectar a los ajustes con RMS apreciable.
SCORE_EPS = 1e-4


def _near_planar(prim, diag):
    """¿La primitiva curva es en realidad casi un plano (radio enorme / ángulo ínfimo)?"""
    ty = prim["type"]
    if ty in ("cylinder", "sphere") and prim["radius"] > 1.5 * diag:
        return True
    if ty == "torus" and prim["R"] > 1.5 * diag:
        return True
    if ty == "cone" and np.degrees(prim["half_angle"]) > 85:
        return True
    return False


# Mínimo de caras de una región para que se le acepte una primitiva CURVA. Con muy
# pocos triángulos el ajuste está indeterminado: una esfera/cilindro pasa EXACTA por
# 4-5 puntos (rms=0) y le gana al plano por simple sobreajuste -> esferas/blobs fantasma.
# Una curva real de un CAD se tesela con bastantes más caras (un agujero, un redondeo).
MIN_CURVED_FACES = 6

# Validación por NORMALES: un ajuste puede pasar exacto por los PUNTOS sin ser la
# superficie real (los anillos de vértices de un cono siempre caben en una esfera ->
# RMS 0 y el cono salía como esfera). Las normales de las caras no engañan: en la
# primitiva correcta coinciden con la normal analítica en el centroide de cada cara.
NORMAL_GATE = np.cos(np.radians(30.0))   # desalineación media > 30° -> ajuste curvo descartado
NORMAL_W = 0.05                          # peso de la desalineación (rad) en el score

# Apertura de normales mínima para aceptar una superficie CURVA cuando el plano también
# vale: una "plana ondulada" de malla sucia (el fondo de 'Original': apertura media 1.8°)
# ajusta a un cilindro poco profundo que sigue las ondulaciones; una curva REAL abre
# mucho más (fillet un cuarto de tubo ≈ 20°, medido ≥ 17° en toda la batería). Por
# debajo se regulariza a plano (lo que el usuario espera de una cara plana mal mallada).
FLAT_SPREAD_DEG = 15.0


def _normal_dots(prim, cents, normals):
    """|cos| entre la normal de cada cara y la normal analítica de la primitiva en su
    centroide, por CARA (array N). Indiferente a la orientación (cóncavo/convexo)."""
    ty = prim["type"]
    if ty == "plane":
        na = np.broadcast_to(np.asarray(prim["normal"], float), cents.shape)
    elif ty == "sphere":
        d = cents - prim["center"]
        na = d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-30)
    elif ty == "cylinder":
        d = cents - prim["point"]
        rad = d - np.outer(d @ prim["axis"], prim["axis"])
        na = rad / (np.linalg.norm(rad, axis=1, keepdims=True) + 1e-30)
    elif ty == "cone":
        a = np.asarray(prim["axis"], float)
        d = cents - prim["origin"]
        rad = d - np.outer(d @ a, a)
        rhat = rad / (np.linalg.norm(rad, axis=1, keepdims=True) + 1e-30)
        na = rhat - prim["slope"] * a          # ∝ ρ̂·cosθ − a·sinθ (normal del cono)
        na = na / np.linalg.norm(na, axis=1, keepdims=True)
    elif ty == "torus":
        a = np.asarray(prim["axis"], float)
        d = cents - prim["center"]
        rad = d - np.outer(d @ a, a)
        rhat = rad / (np.linalg.norm(rad, axis=1, keepdims=True) + 1e-30)
        d2 = cents - (prim["center"] + prim["R"] * rhat)   # desde el centro del tubo
        na = d2 / (np.linalg.norm(d2, axis=1, keepdims=True) + 1e-30)
    else:
        return np.ones(len(normals))
    return np.abs((na * normals).sum(axis=1))


def _normal_alignment(prim, cents, normals, areas):
    """Alineación media (ponderada por área) entre la normal de cada cara y la normal
    analítica de la primitiva en su centroide. 1 = perfecta, 0 = perpendicular."""
    dots = _normal_dots(prim, cents, normals)
    w = areas / (areas.sum() + 1e-30)
    return float((w * dots).sum())


def classify_region(pts, normals, areas, diag, rms_tol_rel, cents=None, accept_verified_shallow=False):
    """Mejor primitiva válida o None (freeform). Prefiere plano; no fuerza nada.

    `cents`: centroides de las caras de la región (N×3). Si se dan, cada ajuste curvo
    se valida por NORMALES (ver `_normal_alignment`): descarta ajustes que pasan por
    los puntos pero no son la superficie real (cono que salía como esfera)."""
    n_faces = len(normals)
    # Diagonal LOCAL de la región (no la global de la malla): para juzgar si una curva
    # es "casi plana" hay que comparar su radio con el tamaño de SU región, no con el de
    # toda la pieza (si no, una esfera de radio moderado sobre una región pequeña cuela).
    rdiag = float(np.linalg.norm(pts.max(0) - pts.min(0))) or diag

    pl = fit_plane(pts)
    pr, pm = stats(pl, pts)
    pl["rms"], pl["max"] = pr, pm
    plane_ok = (pr / diag) < rms_tol_rel

    # La desalineación de normales entra en el score de TODOS los candidatos (plano
    # incluido): el ruido de teselado los penaliza a todos por igual (no decide), pero
    # en los empates a RMS≈0 la señal fina sí decide (un cono real tiene ndev≈0 y la
    # esfera que pasa por sus anillos ndev>0 -> gana el cono). Al plano no se le aplica
    # el gate duro: una región diminuta con normales raras es mejor plano que agujero.
    pl_ndev = 0.0
    if cents is not None:
        pl_align = _normal_alignment(pl, cents, normals, areas)
        pl_ndev = float(np.arccos(min(1.0, pl_align)))
        pl["ndev_deg"] = float(np.degrees(pl_ndev))

    cands = []
    if plane_ok:
        cands.append(((pr / diag + NORMAL_W * pl_ndev + SCORE_EPS) * PENALTY["plane"], pl))
    if n_faces >= MIN_CURVED_FACES:                      # region con datos suficientes
        for ty in ("cylinder", "sphere", "cone", "torus"):
            try:
                prim = FIT[ty](pts, normals, areas, cents)
            except Exception:
                prim = None
            if not prim or _degenerate(ty, prim, diag):
                continue
            rms, mx = stats(prim, pts)
            prim["rms"], prim["max"] = rms, mx
            if (rms / diag) >= rms_tol_rel:
                continue
            ndev = 0.0
            if cents is not None:
                align = _normal_alignment(prim, cents, normals, areas)
                if align < NORMAL_GATE:
                    continue                 # las normales no son las de esa superficie
                ndev = float(np.arccos(min(1.0, align)))
                prim["ndev_deg"] = float(np.degrees(ndev))
            cands.append(((rms / diag + NORMAL_W * ndev + SCORE_EPS) * PENALTY[ty], prim))

    if not cands:
        return None                          # ni plano ni curva válidos -> freeform
    cands.sort(key=lambda c: c[0])
    best = cands[0][1]
    # preferencia fuerte por el plano: si el plano ajusta bien en términos absolutos,
    # solo se acepta una superficie curva si su curvatura es REAL. Se revierte a plano
    # cuando la curva es claramente peor que el plano, O cuando es casi-plana (radio
    # gigante comparado con SU región), O cuando las normales de la región apenas se
    # abren (< FLAT_SPREAD_DEG = plana ondulada de malla sucia, no una curva de verdad).
    if plane_ok and best["type"] != "plane":
        w = areas / (areas.sum() + 1e-30)
        m = (normals * w[:, None]).sum(axis=0)
        m = m / (np.linalg.norm(m) + 1e-30)
        spread = float((w * np.degrees(np.arccos(np.clip(normals @ m, -1.0, 1.0)))).sum())
        # Malla CAD de curvatura suave: una curva de gran radio puede abarcar
        # menos de 15 grados de normales y aun así ajustarse prácticamente
        # EXACTA a un cilindro. No sustituirla por un plano únicamente por
        # ser una banda poco curvada: exigir evidencia sobre vertices, centro-
        # ides y NORMALES de todos los triángulos, no solo sobre los vértices.
        # Esta prueba NO autoriza redondear polígonos (hexágonos, octógonos):
        # sus centros de cara se separan del cilindro circunscrito.
        exact_cylinder = False
        if accept_verified_shallow and best["type"] == "cylinder" and cents is not None and n_faces >= 16:
            center_resid = dev_cylinder(best, cents)
            vertex_resid = dev_cylinder(best, pts)
            normal_align = _normal_alignment(best, cents, normals, areas)
            exact_cylinder = (
                float(vertex_resid.max()) <= 0.00010 and
                float(center_resid.max()) <= 0.0040 and
                normal_align >= 0.999 and
                pl["rms"] >= max(0.02, 100.0 * best["rms"]) and
                not _near_planar(best, rdiag)
            )
        if best["rms"] > 0.5 * pl["rms"] or _near_planar(best, rdiag) or (spread < FLAT_SPREAD_DEG and not exact_cylinder):
            best = pl
        elif exact_cylinder and spread < FLAT_SPREAD_DEG:
            # La supervisión posterior exige soporte suficiente respecto a
            # TODA la malla, no solo a esta región.
            best["shallow_cylinder_evidence"] = True
    return best


def _segment_regions(mesh, angle_tol_deg, flat_tol_deg):
    """Segmenta las caras en regiones separando fillets de planos.

    El problema del crecimiento por ángulo diedro solo: un fillet (redondeo)
    enlaza dos planos con ángulos pequeños paso a paso, así que toda la banda
    (planos + fillets) cae en una sola región y se ajusta mal (un toro/cilindro
    fantasma). La solución es crecer también por **coplanaridad**:

      Etapa 1 (planos): una cara es "plana" si su mayor ángulo con los vecinos
        SUAVES es < flat_tol_deg (no está curvando). Las caras planas se agrupan
        entre sí por aristas casi coplanares. La banda plana se corta justo en la
        línea tangente del fillet (la primera cara del fillet ya curva), así que
        el plano NO se traga el redondeo.
      Etapa 2 (curvas): el resto de caras (las del fillet, cilindros, conos,
        esferas, toros reales) se agrupan por suavidad (ángulo diedro), igual que
        antes. Como los planos ya están fuera, cada fillet queda aislado de los
        demás y se ajusta a su propio cilindro.

    Las piezas limpias no cambian: sus caras planas siguen siendo planos y sus
    superficies curvas siguen yendo por la etapa 2 exactamente como antes.
    """
    n = len(mesh.faces)
    adj = mesh.face_adjacency
    ang = mesh.face_adjacency_angles
    smooth = ang < np.radians(angle_tol_deg)

    # Máximo ángulo de cada cara con sus vecinos suaves -> ¿está curvando?
    max_smooth_ang = np.zeros(n)
    has_smooth = np.zeros(n, dtype=bool)
    for (i, j), a in zip(adj[smooth], ang[smooth]):
        has_smooth[i] = has_smooth[j] = True
        if a > max_smooth_ang[i]:
            max_smooth_ang[i] = a
        if a > max_smooth_ang[j]:
            max_smooth_ang[j] = a
    flat_tol = np.radians(flat_tol_deg)
    is_flat = (max_smooth_ang < flat_tol)            # caras que no curvan
    # caras sin vecino suave (sueltas) cuentan como planas (chaflán/cara aislada)
    is_flat[~has_smooth] = True

    # Etapa 1: planos = componentes de caras planas unidas por aristas coplanares.
    coplanar = (ang < flat_tol) & is_flat[adj[:, 0]] & is_flat[adj[:, 1]]
    plane_edges = adj[coplanar]
    plane_nodes = np.nonzero(is_flat)[0]
    regions = []
    if len(plane_nodes):
        for c in connected_components(plane_edges, nodes=plane_nodes, min_len=1):
            regions.append(np.asarray(c))

    # Etapa 2: curvas = componentes de caras NO planas unidas por aristas suaves.
    curved = smooth & (~is_flat[adj[:, 0]]) & (~is_flat[adj[:, 1]])
    curved_edges = adj[curved]
    curved_nodes = np.nonzero(~is_flat)[0]
    if len(curved_nodes):
        for c in connected_components(curved_edges, nodes=curved_nodes, min_len=1):
            regions.append(np.asarray(c))

    regions.sort(key=len, reverse=True)
    return regions


def _segment_smooth(mesh, angle_tol_deg):
    """Segmentación de UNA etapa: componentes conexas por suavidad (ángulo diedro).

    Para escaneos orgánicos, la segmentación en 2 etapas (planos vs curvas) fragmenta
    el ruido en miles de regiones. Aquí toda la superficie suave queda en una (o pocas)
    región grande, que luego se trocea en parches NURBS. NO usar en CAD limpio (rompería
    la separación de caras)."""
    n = len(mesh.faces)
    adj = mesh.face_adjacency
    ang = mesh.face_adjacency_angles
    edges = adj[ang < np.radians(angle_tol_deg)]
    comps = connected_components(edges, nodes=np.arange(n), min_len=1)
    regions = sorted((np.asarray(c) for c in comps), key=len, reverse=True)
    return regions


def _looks_like_scan(mesh, angle_tol_deg, frac=0.8, min_faces=10000, coplanar_max=0.03):
    """Heurística: ¿es una malla de escáner orgánica? Sí cuando es densa Y casi toda
    su superficie está conectada por suavidad (la mayor componente suave cubre > frac).
    El CAD limpio tiene caras separadas por aristas vivas -> ninguna componente domina;
    un escaneo orgánico es un único blob suave. Las mallas pequeñas (tests sintéticos)
    se excluyen por el mínimo de caras.

    Veto anti falso-positivo (CAD denso muy teselado, p.ej. '33018 dedo'): las caras
    PLANAS de un CAD se teselan con triángulos EXACTAMENTE coplanarios (ángulo diedro
    numéricamente 0), cosa que el ruido de un escáner no produce jamás. Si más del
    `coplanar_max` de las aristas son coplanarias exactas (<0.05°), es CAD, no escaneo.
    Medido: CAD densos 0.26-0.54; escaneos (aun suavizados) < 0.02."""
    n = len(mesh.faces)
    if n < min_faces:
        return False
    ang = mesh.face_adjacency_angles
    if len(ang) and float((ang < np.radians(0.05)).mean()) > coplanar_max:
        return False
    regions = _segment_smooth(mesh, angle_tol_deg)
    return bool(regions) and len(regions[0]) >= frac * n


# Refinamiento de regiones: umbral por CARA (más laxo que el gate medio) y mínimo de
# caras discrepantes para partir. El caso que arregla: la pared perimetral de una placa
# (extremo redondeado + tramos rectos, todo tangente-continuo) cae en UNA región suave;
# el cilindro ajusta bien DE MEDIA (el arco domina) pero los tramos rectos no son
# cilindro -> el STEP barría el arco completo por fuera de la pieza (los "lóbulos").
# Partiendo la región por normales, el arco queda como cilindro y los rectos como planos.
SPLIT_FACE_DEG = 35.0     # una cara discrepa si su normal se desvía más que esto
SPLIT_MIN_BAD = 4         # nº mínimo de caras discrepantes para molestarse en partir
SPLIT_MAX_DEPTH = 3       # presupuesto de particiones (evita partir sin fin)
PEEL_TOL = 0.5            # el cluster pelado debe ajustar a plano FINO (< 0.5×tolerancia)


def _peel_flat_cluster(mesh, region, normals, areas, diag, rms_tol_rel):
    """En una región FREEFORM, busca el mayor cluster de caras con normal común que
    ajuste fino a un plano. Devuelve (cluster, resto) o None.

    El caso que arregla (fondo de 'Original (1) (2)'): en malla sucia (decimada), una
    cara plana real tiene saltos de ángulo con sus vecinas > flat_tol, así que la
    segmentación no la separa de las bandas laterales curvas; la región mixta no ajusta
    a nada -> TODA iba a NURBS y lo plano salía ondulado. Pelando el plano dominante,
    él se exporta como plano de verdad y el resto se reclasifica por separado.
    El umbral estricto (PEEL_TOL) evita aplanar zonas orgánicas de verdad."""
    order = np.argsort(areas)[::-1][:8]            # semillas: las 8 caras más grandes
    cos_tol = np.cos(np.radians(SPLIT_FACE_DEG))
    total_area = float(areas.sum())
    best = None
    for s in order:
        mask = (normals @ normals[s]) > cos_tol    # producto CON signo: no coge la cara opuesta
        n_in = int(mask.sum())
        if n_in < MIN_CURVED_FACES or mask.all() or int((~mask).sum()) < SPLIT_MIN_BAD:
            continue
        a = float(areas[mask].sum())
        if a < 0.1 * total_area:
            continue
        vidx = np.unique(mesh.faces[region[mask]].ravel())
        pts = mesh.vertices[vidx]
        pl = fit_plane(pts)
        rms, _ = stats(pl, pts)
        if (rms / diag) < PEEL_TOL * rms_tol_rel and (best is None or a > best[0]):
            best = (a, mask)
    if best is None:
        return None
    return region[best[1]], region[~best[1]]


def _components(mesh, faces):
    """Componentes conexas (por adyacencia de caras) de un subconjunto de caras."""
    faces = np.asarray(faces, int)
    if len(faces) == 0:
        return []
    mask = np.zeros(len(mesh.faces), dtype=bool)
    mask[faces] = True
    adj = mesh.face_adjacency
    edges = adj[mask[adj[:, 0]] & mask[adj[:, 1]]]
    return [np.asarray(c) for c in connected_components(edges, nodes=faces, min_len=1)]


def detect(path, angle_tol_deg=32.0, min_faces=2, rms_tol_rel=0.01, flat_tol_deg=8.0,
           scan_mode=False, mesh_input=None):
    """scan_mode: True (forzar escaneo), False (CAD normal) o "auto" (autodetectar)."""
    from collections import deque
    if mesh_input is None:
        mesh = trimesh.load(path, force="mesh")
        mesh.merge_vertices()
    else:
        # Una entrada reparada ya verificada puede contener contactos separados
        # a escala menor que el redondeo de merge_vertices(). No resoldarlos.
        mesh = mesh_input.copy()
        triangles=mesh.vertices[mesh.faces]
        normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
        lengths=np.linalg.norm(normals,axis=1)
        if np.any(lengths==0):raise ValueError('Cara exactamente colapsada en la entrada verificada.')
        mesh.face_normals=normals/lengths[:,None]
    diag = float(np.linalg.norm(mesh.bounds[1] - mesh.bounds[0])) or 1.0

    if scan_mode == "auto":
        scan_mode = _looks_like_scan(mesh, angle_tol_deg)

    # scan_mode: malla de escaneo orgánica -> una etapa + todo freeform (NURBS).
    if scan_mode:
        regions = _segment_smooth(mesh, angle_tol_deg)
    else:
        regions = _segment_regions(mesh, angle_tol_deg, flat_tol_deg)

    fnormals = mesh.face_normals
    fareas = mesh.area_faces
    verts = mesh.vertices

    result = {"diag": diag, "n_faces": int(len(mesh.faces)),
              "n_verts": int(len(mesh.vertices)),
              "bbox": mesh.bounds.tolist(), "primitives": [], "freeform_faces": 0,
              "freeform_regions": []}

    split_cos = np.cos(np.radians(SPLIT_FACE_DEG))
    queue = deque((np.asarray(r), 0) for r in regions)
    while queue:
        region, depth = queue.popleft()
        if len(region) < min_faces:
            continue
        if scan_mode:
            # escaneo orgánico: no se fuerzan primitivas, toda región va a NURBS.
            result["freeform_faces"] += len(region)
            result["freeform_regions"].append(region.tolist())
            continue
        vidx = np.unique(mesh.faces[region].ravel())
        pts = verts[vidx]
        normals = fnormals[region]
        areas = fareas[region]
        cents = verts[mesh.faces[region]].mean(axis=1)   # centroides (validación por normales)
        prim = classify_region(pts, normals, areas, diag, rms_tol_rel, cents=cents, accept_verified_shallow=True)
        # Un fragmento cilíndrico de apoyo muy pequeño no puede desplazar una
        # cara plana solo porque sus vértices casen con una circunferencia.
        # Exigir apoyo global evita cambiar regiones pequeñas de piezas ya
        # fiables sin una evidencia geométrica suficiente.
        if (prim is not None and prim.get("shallow_cylinder_evidence")
                and len(region) < max(80, int(np.ceil(0.02 * len(mesh.faces))))):
            prim = fit_plane(pts)
            prim["rms"], prim["max"] = stats(prim, pts)
        # Refinamiento: si la primitiva CURVA ganadora tiene un subconjunto de caras cuyas
        # normales discrepan, la región mezcla superficies -> partir en componentes conexas
        # de caras alineadas/discrepantes y reclasificar cada trozo por separado.
        if (prim is not None and prim["type"] != "plane" and depth < SPLIT_MAX_DEPTH):
            dots = _normal_dots(prim, cents, normals)
            bad = dots < split_cos
            if int(bad.sum()) >= SPLIT_MIN_BAD and int((~bad).sum()) >= MIN_CURVED_FACES:
                for sub in _components(mesh, region[~bad]) + _components(mesh, region[bad]):
                    queue.append((sub, depth + 1))
                continue
        if prim is None:
            # Antes de rendirse a freeform: si la región esconde un cluster PLANO fino
            # (cara plana de malla sucia pegada a sus laterales curvos), pelarlo y
            # reclasificar los trozos por separado.
            if depth < SPLIT_MAX_DEPTH:
                peel = _peel_flat_cluster(mesh, region, normals, areas, diag, rms_tol_rel)
                if peel is not None:
                    for sub in _components(mesh, peel[0]) + _components(mesh, peel[1]):
                        queue.append((sub, depth + 1))
                    continue
            # región sin primitiva analítica: candidata a superficie NURBS (modo orgánico).
            result["freeform_faces"] += len(region)
            result["freeform_regions"].append(region.tolist())
            continue
        prim["faces"] = region.tolist()
        prim["n_faces"] = int(len(region))
        result["primitives"].append(prim)

    return result, mesh


def _summary(res):
    by = {}
    for p in res["primitives"]:
        by[p["type"]] = by.get(p["type"], 0) + 1
    return by


if __name__ == "__main__":
    import sys, json
    path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\rcosme\Easyfit3d\_stl_test\cuerpo45.stl"
    tol = float(sys.argv[2]) if len(sys.argv) > 2 else 32.0
    res, mesh = detect(path, angle_tol_deg=tol)
    print(f"Malla: {res['n_faces']} caras, {res['n_verts']} vértices, diag {res['diag']:.1f} mm")
    print(f"Primitivas: {len(res['primitives'])}  por tipo {_summary(res)}")
    print(f"Caras sin clasificar (freeform): {res['freeform_faces']}")
    for p in res["primitives"]:
        extra = ""
        if p["type"] == "cylinder":
            extra = f" R={p['radius']:.3f} L={p['tmax']-p['tmin']:.1f}"
        elif p["type"] == "sphere":
            extra = f" R={p['radius']:.3f}"
        elif p["type"] == "cone":
            extra = f" semiang={np.degrees(p['half_angle']):.1f}"
        elif p["type"] == "torus":
            extra = f" R={p['R']:.3f} r={p['r']:.3f}"
        print(f"  {p['type']:8s} caras={p['n_faces']:4d} RMS={p['rms']:.4f}{extra}")
