"""Entrada conservadora opcional. No modifica las estrategias ni tolerancias CAD.

Mallas sanas pasan con el mismo archivo; nunca se borran islas por tamaño.
La unión usa Manifold en doble precisión y se contrasta con OpenCascade.
Las aberturas requieren referencia cerrada explícita: su intención no se infiere.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np
import trimesh

MAX_UNION_FACES = 20_000
MAX_UNION_PARTS = 8


def componentes(mesh):
    """Separar sin fill_holes; recuperar interfaces coincidentes con sus caras
    originales cuando la soldadura STL comparte todos los vértices del contacto.
    No crear triángulos, no invertirlos y no descartar ninguno.
    """
    groups = list(trimesh.graph.connected_components(mesh.face_adjacency,
                  nodes=np.arange(len(mesh.faces)), min_len=1))
    parts = list(mesh.submesh(groups, repair=False))
    if all(p.is_watertight for p in parts):
        return parts
    anchors = [list(g) for g in groups if len(g) >= 4]
    pool = {int(i) for g in groups if len(g) < 4 for i in g}
    if not anchors or not pool or len(pool) > 200:
        return parts
    from collections import Counter
    recovered = []
    for ids in anchors:
        while True:
            faces = mesh.faces[ids]
            directed = Counter((int(a), int(b)) for f in faces for a, b in zip(f, np.roll(f, -1)))
            boundary = {e for e, c in directed.items() if c == 1 and directed[e[::-1]] == 0}
            if not boundary:
                break
            eligible = []
            for i in sorted(pool):
                f = mesh.faces[i]
                edges = [(int(a), int(b)) for a, b in zip(f, np.roll(f, -1))]
                if any(e[::-1] in boundary for e in edges) and all(
                        directed[e] == 0 and directed[e[::-1]] <= 1 for e in edges):
                    eligible.append(i)
            if not eligible:
                return parts
            chosen = eligible[0]
            ids.append(chosen)
            pool.remove(chosen)
        p = mesh.submesh([ids], repair=False)[0]
        if not p.is_watertight or not p.is_winding_consistent or p.volume <= 0:
            return parts
        recovered.append(p)
    return recovered if not pool else parts


class ReparacionRechazada(ValueError):
    def __init__(self, message, informe):
        super().__init__(message)
        self.informe = informe


def cargar_exacto(path):
    raw = trimesh.load(str(path), force='mesh', process=False)
    # Soldar exclusivamente coordenadas idénticas; sin mover vértices ni limpiar
    # caras degeneradas/duplicadas antes de diagnosticarlas.
    vertices, inverse = np.unique(raw.vertices, axis=0, return_inverse=True)
    return trimesh.Trimesh(vertices, inverse[raw.faces], process=False)


def diagnosticar(mesh):
    edges, counts = np.unique(np.sort(mesh.edges, axis=1), axis=0, return_counts=True)
    _, inverse, face_counts = np.unique(np.sort(mesh.faces, axis=1), axis=0, return_counts=True, return_inverse=True)
    opposite = 0
    for group in np.flatnonzero(face_counts == 2):
        pair = mesh.faces[np.flatnonzero(inverse == group)]
        signs = np.prod(pair-np.roll(pair, -1, axis=1), axis=1)
        if np.sign(signs[0]) != np.sign(signs[1]) and signs[0] != 0 and signs[1] != 0:
            opposite += 1
    degenerate = int(np.count_nonzero(mesh.area_faces <= 1e-14))
    parts = componentes(mesh) if len(mesh.faces) else []
    components = [{'caras': len(p.faces), 'estanco': bool(p.is_watertight),
                   'orientacion_consistente': bool(p.is_winding_consistent),
                   'volumen_firmado_mm3': float(p.volume), 'euler': int(p.euler_number)} for p in parts]
    opened, nonmanifold = int(np.count_nonzero(counts == 1)), int(np.count_nonzero(counts > 2))
    duplicates = int(np.sum(face_counts-1))
    if not len(mesh.faces) or not np.isfinite(mesh.vertices).all():
        route, severity = 'rechazar_entrada', 'error'
    elif degenerate or duplicates > opposite:
        route, severity = 'rechazar_caras_defectuosas', 'error'
    elif opened:
        route, severity = 'abertura_ambigua_requiere_referencia', 'error'
    elif any(not c['orientacion_consistente'] or c['volumen_firmado_mm3'] <= 1e-9 for c in components):
        route, severity = 'rechazar_orientacion', 'error'
    elif len(parts) == 1 and not nonmanifold and mesh.is_watertight:
        route, severity = 'paso_directo', 'informacion'
    elif len(parts) > 1 and all(c['estanco'] for c in components):
        route, severity = 'analizar_union_cuerpos_cerrados', 'advertencia'
    else:
        route, severity = 'rechazar_union_no_manifold', 'error'
    return {'caras': len(mesh.faces), 'vertices': len(mesh.vertices),
            'aristas_1_cara': opened, 'aristas_2_caras': int(np.count_nonzero(counts == 2)),
            'aristas_mas_2_caras': nonmanifold, 'caras_degeneradas': degenerate,
            'caras_duplicadas': duplicates, 'pares_caras_contacto_opuestas': opposite,
            'componentes': components,
            'numero_componentes': len(parts), 'estanco_global': bool(mesh.is_watertight),
            'caja_mm': mesh.bounds.tolist() if len(mesh.vertices) else [],
            'ruta': route, 'gravedad': severity,
            'autointersecciones': 'no evaluadas en diagnóstico rápido; OCC obligatorio para unión',
            'contactos': 'pendiente de booleano; no inferido solo por caja envolvente'}


def _manifold(mesh):
    import manifold3d as m
    solid = m.Manifold(m.Mesh64(np.asarray(mesh.vertices, dtype=np.float64),
                                np.asarray(mesh.faces, dtype=np.uint64)))
    if solid.status() != m.Error.NoError or solid.is_empty():
        raise ValueError('El booleano robusto rechaza un componente: '+str(solid.status()))
    return solid


def _marco_contacto(mesh):
    """Marco local para contactos YA unidos por aristas coincidentes.

    El float32 de STL puede alabear decenas de nanómetros una interfaz plana
    tras girarla. No se busca proximidad entre piezas separadas. El único
    movimiento permitido es proyectar esa interfaz dentro de 0,000020 mm.
    """
    edges, counts = np.unique(np.sort(mesh.edges, axis=1), axis=0, return_counts=True)
    shared = np.unique(edges[counts > 2])
    identity = np.eye(4)
    if len(shared) < 3:
        return mesh, identity, {'aplicado': False}
    if len(componentes(mesh)) != 2:
        return mesh, identity, {'aplicado': False, 'motivo': 'normalización limitada a dos cuerpos con contacto explícito'}
    points = mesh.vertices[shared]
    origin = points.mean(axis=0)
    _, values, axes = np.linalg.svd(points-origin, full_matrices=False)
    epsilon = min(.000020, float(np.linalg.norm(mesh.extents))*1e-7)
    if len(values) < 3 or values[1] < epsilon or np.max(np.abs((points-origin)@axes[2])) > epsilon:
        return mesh, identity, {'aplicado': False, 'motivo': 'interfaz no plana o ambigua'}
    # Matriz ortonormal con determinante positivo; traslación fuera del plano.
    x, z = axes[0], axes[2]
    y = np.cross(z, x)
    basis = np.column_stack((x, y, z))
    local = (mesh.vertices-origin)@basis
    # El bucle compartido puede ser el BORDE INTERIOR de un contacto anular.
    # La interfaz abarca entonces el anillo exterior al bucle: proyectar todos
    # sus vértices en el plano, con el mismo límite de movimiento nanométrico.
    mask = np.abs(local[:, 2]) <= epsilon
    displacement = float(np.max(np.abs(local[mask, 2])))
    local[mask, 2] = 0.
    transformed = trimesh.Trimesh(local, mesh.faces.copy(), process=False)
    restore = np.eye(4)
    restore[:3, :3], restore[:3, 3] = basis, origin
    return transformed, restore, {'aplicado': True, 'aristas_preexistentes': int(np.count_nonzero(counts > 2)),
                                 'vertices_interfaz': int(mask.sum()), 'max_movimiento_mm': displacement,
                                 'limite_movimiento_mm': epsilon,
                                 'nota': 'Solo interfaz con aristas compartidas; no unión por cercanía.'}


def unir_cerrados(mesh, *, _permitir_rescate_contacto=True):
    from verificacion_reparacion import validar_union
    parts = componentes(mesh)
    if len(mesh.faces) > MAX_UNION_FACES or len(parts) > MAX_UNION_PARTS:
        raise ValueError('Unión compleja fuera del límite experimental de 20.000 caras / 8 cuerpos.')
    local, restore, contact_report = _marco_contacto(mesh)
    local_parts = componentes(local)
    if len(local_parts) != len(parts) or any(not p.is_watertight for p in local_parts):
        raise ValueError('La normalización de contacto altera la descomposición original.')
    solids = [_manifold(p) for p in local_parts]
    result = solids[0]
    relations = []
    for i, other in enumerate(solids[1:], 1):
        overlap = (result ^ other).volume()
        gap = result.min_gap(other, .020)
        relations.append({'componente': i, 'volumen_interseccion_mm3': overlap,
                          'separacion_mm_acotada': gap,
                          'tipo': 'solapamiento' if overlap > 1e-9 else 'contacto_o_separacion'})
        result = result + other
    if len(result.decompose()) != 1:
        raise ValueError('Múltiples cuerpos separados o contacto solo puntual/por arista: '
                         'no se fusionan por cercanía ni se eliminan cuerpos pequeños.')
    # El STL float32 no puede almacenar las microcaras de intersecciones de
    # planos redondeados. Retirar solo redundancias bajo 20 nanómetros;
    # cualquier efecto se vuelve a medir contra OCC y tras serializar STL.
    numerical_limit = min(.000020, float(np.linalg.norm(mesh.extents))*1e-7)
    result = result.simplify(numerical_limit)
    data = result.to_mesh64()
    candidate = trimesh.Trimesh(data.vert_properties[:, :3], data.tri_verts, process=False)
    candidate.apply_transform(restore)
    diag = diagnosticar(candidate)
    if diag['ruta'] != 'paso_directo':
        raise ValueError('Unión no manifold: el resultado no es un único sólido orientado.')
    # Protección adicional: no aceptar la desaparición de todos los túneles de
    # un cuerpo. El contraste geométrico independiente sigue siendo obligatorio.
    genus_before = max(max(0, (2-p.euler_number)//2) for p in parts)
    genus_after = max(0, (2-candidate.euler_number)//2)
    if genus_after < genus_before:
        raise ValueError('No se puede garantizar la preservación de agujeros interiores.')
    try:
        validation = validar_union(parts, candidate)
    except ValueError as initial_error:
        if not _permitir_rescate_contacto:
            raise
        from contactos_numericos import normalizar_contactos_solapados
        stabilized, restore_contact, contact_proof = normalizar_contactos_solapados(mesh)
        if not contact_proof['aplicado']:
            raise
        candidate, _ = unir_cerrados(stabilized, _permitir_rescate_contacto=False)
        candidate.apply_transform(restore_contact)
        # La referencia sigue siendo la entrada ORIGINAL, sin estabilizar.
        # El error nanométrico no se suma al límite de ninguna comprobación.
        validation = validar_union(parts, candidate)
        validation['estabilizacion_contactos'] = contact_proof
        validation['rechazo_booleano_inicial'] = str(initial_error)
        genus_after = max(0, (2-candidate.euler_number)//2)
    validation.update(relaciones=relations, genero_antes=genus_before, genero_despues=genus_after,
                      normalizacion_contacto=contact_report)
    validation['limite_simplificacion_numerica_mm'] = numerical_limit
    return candidate, validation


def reparar_agujero_local(mesh, referencia):
    """Solo triangulaciones faltantes identificadas por una referencia cerrada.

    No inventa la superficie del escáner: conserva todos los vértices y caras
    originales y añade únicamente triángulos de la referencia local explícita.
    Nunca se invoca automáticamente desde la UI.
    """
    from verificacion_reparacion import distancia_malla, puntos_superficie
    diag, refdiag = diagnosticar(mesh), diagnosticar(referencia)
    if refdiag['ruta'] != 'paso_directo' or diag['caras_duplicadas'] or diag['caras_degeneradas']:
        raise ValueError('Se requiere una referencia cerrada y sin defectos.')
    if not diag['aristas_1_cara'] or diag['aristas_mas_2_caras']:
        raise ValueError('No es un agujero local simple.')
    if mesh.vertices.shape != referencia.vertices.shape or not np.array_equal(mesh.vertices, referencia.vertices):
        raise ValueError('Referencia ambigua: las coordenadas deben ser idénticas.')
    old = {tuple(sorted(f)) for f in mesh.faces}
    ref = {tuple(sorted(f)) for f in referencia.faces}
    if not old.issubset(ref):
        raise ValueError('Referencia ambigua: modifica superficies existentes.')
    missing = [f for f in referencia.faces if tuple(sorted(f)) not in old]
    if not 1 <= len(missing) <= 4:
        raise ValueError('Abertura grande: solo se permiten de 1 a 4 triángulos locales.')
    pts = mesh.vertices[np.unique(missing)]
    diameter = float(np.max(np.linalg.norm(pts[:, None]-pts[None, :], axis=2)))
    if diameter > min(1.0, .05*float(np.linalg.norm(mesh.extents))):
        raise ValueError('Abertura grande o funcional: no se rellena automáticamente.')
    candidate = trimesh.Trimesh(mesh.vertices.copy(), np.vstack((mesh.faces, missing)), process=False)
    if diagnosticar(candidate)['ruta'] != 'paso_directo':
        raise ValueError('La reparación local no da un sólido válido.')
    distances = distancia_malla(referencia, puntos_superficie(candidate))
    if distances.max() > 1e-7 or abs(candidate.volume-referencia.volume) > 1e-7:
        raise ValueError('La reparación local no coincide con la referencia.')
    from verificacion_reparacion import solido_poliedrico
    solido_poliedrico(candidate)  # incluidas autointerferencias de la referencia
    return candidate, {'triangulos_añadidos': len(missing), 'diametro_mm': diameter,
                       'referencia': 'cerrada explícita con coordenadas y caras existentes idénticas',
                       'max_observado_mm': float(distances.max()), 'vertices_movidos': 0}


def preparar(source: Path, destination: Path, *, habilitado=True):
    report = {'version': 1, 'original_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'habilitado': habilitado, 'reparado': False, 'original_conservado': True}
    mesh = cargar_exacto(source)
    if len(mesh.faces) > 250_000:
        raise ReparacionRechazada('El STL supera el límite histórico de 250.000 triángulos.', report)
    report['entrada'] = diag = diagnosticar(mesh)
    route = diag['ruta']
    # Compatibilidad: el motor histórico ya hace trimesh process=True. Brick
    # contiene costuras de redondeo que esa lectura suelda. Si ESA misma
    # lectura ya es sana, dejar pasar el archivo original sin reescribirlo.
    # Nunca usar esta excepción para duplicados, degenerados ni orientación.
    if route == 'abertura_ambigua_requiere_referencia' and not diag['caras_duplicadas'] and not diag['caras_degeneradas']:
        legacy = trimesh.load(str(source), force='mesh', process=True)
        legacy_diag = diagnosticar(legacy)
        if legacy_diag['ruta'] == 'paso_directo':
            report['lectura_heredada_motor'] = legacy_diag
            report['nota_costura'] = 'La lectura histórica process=True ya suelda esta costura de redondeo; archivo original intacto.'
            route = 'paso_directo'
    if route == 'paso_directo':
        report['ruta_seleccionada'] = 'paso_directo'
        report['resultado'] = 'mismo archivo; sin reescritura ni cambio de estrategia'
        return source, report
    if not habilitado:
        raise ReparacionRechazada('Preprocesador desactivado; '+route, report)
    reasons = {'rechazar_caras_defectuosas': 'Caras degeneradas o duplicadas: reparación ambigua.',
               'abertura_ambigua_requiere_referencia': 'Borde abierto: no se puede distinguir un agujero accidental de un canal funcional; se requiere referencia explícita.',
               'rechazar_orientacion': 'Orientación inconsistente o invertida; no se cambia silenciosamente.',
               'rechazar_union_no_manifold': 'Unión no manifold: no se pudo garantizar reparación sin cambiar cotas.'}
    if route != 'analizar_union_cuerpos_cerrados':
        raise ReparacionRechazada(reasons.get(route, 'Entrada no válida.'), report)
    try:
        report['ruta_seleccionada'] = 'union_booleana_verificada'
        candidate, report['verificacion_independiente'] = unir_cerrados(mesh)
        candidate.export(str(destination))
        # Validar de nuevo después de serializar en float32 (formato STL).
        reread = cargar_exacto(destination)
        if diagnosticar(reread)['ruta'] != 'paso_directo':
            raise ValueError('El STL serializado pierde su topología.')
        from verificacion_reparacion import validar_union
        report['verificacion_stl_reimportado'] = validar_union(componentes(mesh), reread)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise ReparacionRechazada(str(exc), report) from exc
    report.update(reparado=True, resultado='unión verificada', salida=diagnosticar(reread),
                  reparado_sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    return destination, report
