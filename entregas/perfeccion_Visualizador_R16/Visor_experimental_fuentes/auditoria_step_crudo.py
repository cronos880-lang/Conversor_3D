"""Audit serialized closed-shell edge incidence before a CAD reader heals it.

Independent implementation of the topological rule: each edge of an oriented
closed shell has two opposite uses. This is NOT a surface/UV/geometry validator.
No ScanRuler source is included or translated here. Its reproducible writer
counterexample motivated checking the serialized representation as well.
"""
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class Entity:
    kind: str
    refs: tuple
    orientation: int | None
    flag_position: int | None


def _entities(text):
    # Mask literals/comments, preserving offsets for diagnostics and flag edits.
    token = re.compile(r"'(?:''|[^'])*'|/\*[\s\S]*?\*/|\"[^\"]*\"")
    masked = token.sub(lambda m: ' ' * len(m[0]), text)
    if not re.search(r'\bISO-10303-21\s*;', masked) or not re.search(r'\bEND-ISO-10303-21\s*;', masked):
        raise ValueError('No es un fichero STEP Part 21 completo')
    data = re.search(r'\bDATA\s*;([\s\S]*?)\bENDSEC\s*;', masked)
    if data is None:
        raise ValueError('No hay una sección DATA reconocible')
    if re.search(r'\bDATA\s*;', masked[data.end():]):
        raise ValueError('No se auditan múltiples secciones DATA')
    entities = {}; seen = set()
    topological = {'CLOSED_SHELL', 'OPEN_SHELL', 'ADVANCED_FACE', 'FACE_BOUND',
                   'FACE_OUTER_BOUND', 'EDGE_LOOP', 'VERTEX_LOOP', 'ORIENTED_EDGE',
                   'EDGE_CURVE', 'VERTEX_POINT', 'MANIFOLD_SOLID_BREP', 'BREP_WITH_VOIDS',
                   'SEAM_CURVE', 'SURFACE_CURVE', 'CIRCLE', 'PLANE'}
    oriented = {'FACE_BOUND', 'FACE_OUTER_BOUND', 'ORIENTED_EDGE'}
    record = re.compile(r'#(\d+)\s*=\s*([\s\S]*?);')
    for m in record.finditer(masked, data.start(1), data.end(1)):
        ident = int(m[1])
        if ident in seen:
            raise ValueError(f'Entidad STEP duplicada #{ident}')
        seen.add(ident)
        body = m[2]
        # Do not retain the potentially hundreds of thousands of coordinate,
        # direction and spline-pole records. This auditor checks topology only.
        head = re.match(r'([A-Z_][A-Z_0-9]*)\s*\(', body)
        if head is not None and head[1] not in topological and 'SURFACE' not in head[1]:
            continue
        simple = re.match(r'([A-Z_][A-Z_0-9]*)\s*\(([\s\S]*)\)\s*$', body)
        if simple is None:
            entities[ident] = Entity('COMPLEX', (), None, None)
            continue
        args = simple[2]
        flag = re.search(r'\.([TF])\.\s*$', args) if simple[1] in oriented else None
        pos = m.start(2) + simple.start(2) + flag.start() if flag else None
        refs = tuple(map(int, re.findall(r'#(\d+)', args))) if simple[1] in topological else ()
        entities[ident] = Entity(simple[1], refs,
                                 (1 if flag[1] == 'T' else -1) if flag else None, pos)
    if not entities:
        raise ValueError('La sección DATA no contiene entidades')
    return entities


def _inspect(text):
    entities = _entities(text)
    shells = []
    unsupported = []
    all_uses = {}
    for shell_id, shell in entities.items():
        if shell.kind != 'CLOSED_SHELL':
            continue
        if not shell.refs:
            unsupported.append(f'Frontera cerrada vacía #{shell_id}')
        uses = defaultdict(list)
        for face_id in shell.refs:
            face = entities.get(face_id)
            if face is None or face.kind != 'ADVANCED_FACE' or len(face.refs) < 2:
                unsupported.append(f'Cara #{face_id} no reconocida'); continue
            surface = entities.get(face.refs[-1])
            if surface is None:
                unsupported.append(f'Superficie ausente en #{face_id}'); continue
            for bound_id in face.refs[:-1]:
                bound = entities.get(bound_id)
                if bound is None or bound.kind not in ('FACE_BOUND', 'FACE_OUTER_BOUND') or len(bound.refs) != 1 or bound.orientation is None:
                    unsupported.append(f'Contorno #{bound_id} no reconocido'); continue
                loop = entities.get(bound.refs[0])
                if loop is not None and loop.kind == 'VERTEX_LOOP':
                    if len(loop.refs) != 1 or entities.get(loop.refs[0], Entity('', (), None, None)).kind != 'VERTEX_POINT':
                        unsupported.append(f'Bucle degenerado #{bound.refs[0]} no reconocido')
                    continue
                if loop is None or loop.kind != 'EDGE_LOOP' or not loop.refs:
                    unsupported.append(f'Bucle #{bound.refs[0]} no reconocido'); continue
                for use_id in loop.refs:
                    use = entities.get(use_id)
                    edge_id = use.refs[-1] if use and use.refs else None
                    edge = entities.get(edge_id)
                    if use is None or use.kind != 'ORIENTED_EDGE' or len(use.refs) != 1 or use.orientation is None or edge is None or edge.kind != 'EDGE_CURVE':
                        unsupported.append(f'Uso de arista #{use_id} no reconocido'); continue
                    uses[edge_id].append(dict(face=face_id, bound=bound_id,
                                              surface=surface.kind,
                                              direction=bound.orientation * use.orientation))
        bad = [dict(edge=e, uses=u) for e, u in uses.items()
               if len(u) != 2 or u[0]['direction'] == u[1]['direction']]
        shells.append(dict(shell=shell_id, faces=len(shell.refs), edges=len(uses), errors=bad))
        all_uses[shell_id] = uses
    solids = sum(e.kind in ('MANIFOLD_SOLID_BREP', 'BREP_WITH_VOIDS') for e in entities.values())
    if not shells or not solids:
        unsupported.append('No hay sólido cerrado reconocido')
    if any(e.kind == 'OPEN_SHELL' for e in entities.values()):
        unsupported.append('Hay una frontera abierta en el fichero')
    result = dict(ok=bool(shells) and not unsupported and all(not s['errors'] for s in shells),
                  complete=not unsupported, solids=solids, shells=shells,
                  unsupported=unsupported,
                  scope='Incidencia y orientación topológica serializada; no valida geometría ni áreas UV')
    return result, entities, all_uses


def auditar_texto(text):
    return _inspect(text)[0]


def auditar_archivo(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        return auditar_texto(stream.read())


def _proponer_correccion(text):
    """Only independent torus bounds with two full circles and two bad shared edges.

    No global orientation repair: ambiguous cases remain rejected. Caller must
    verify exact CAD and geometry against its pre-write solid before publishing.
    """
    result, entities, uses_by_shell = _inspect(text)
    if result['ok']:
        return text, []
    if not result['complete']:
        raise ValueError('La auditoría STEP cruda tiene topología no reconocida')
    candidates = []
    groups = []
    for shell in result['shells']:
        errors = shell['errors']
        if not errors:
            continue
        if any(len(b['uses']) != 2 for b in errors):
            raise ValueError('Incoherencia STEP fuera del caso de redondeo acotado')
        # Separate independent occurrences of the same OCCT torus writer bug.
        # Every bad edge must belong to exactly one eligible pair; no global
        # orientation solver and no changes to geometry entities are allowed.
        by_bound = defaultdict(list)
        for b in errors:
            for use in b['uses']:
                if use['surface'] == 'TOROIDAL_SURFACE':
                    by_bound[use['bound']].append(b)
        pairs = [pair for pair in by_bound.values() if len(pair) == 2]
        coverage = defaultdict(int)
        for pair in pairs:
            for b in pair: coverage[b['edge']] += 1
        if any(coverage[b['edge']] != 1 for b in errors):
            raise ValueError('No hay una corrección única y acotada del contorno toroidal')
        groups.extend(pairs)
    for bad in groups:
        shared = set(u['bound'] for u in bad[0]['uses']) & set(u['bound'] for u in bad[1]['uses'])
        eligible = []
        for bound_id in shared:
            selected = [u for b in bad for u in b['uses'] if u['bound'] == bound_id]
            if len(selected) != 2 or any(u['surface'] != 'TOROIDAL_SURFACE' for u in selected):
                continue
            bound = entities[bound_id]; loop = entities[bound.refs[0]]
            if len(loop.refs) not in (2, 4) or bound.flag_position is None:
                continue
            edge_ids = [entities[e].refs[-1] for e in loop.refs]
            boundary_ids = {b['edge'] for b in bad}
            if any(edge_ids.count(e) != 1 for e in boundary_ids):
                continue
            # A periodic torus may include one seam, traversed both ways.
            seam_ids = set(edge_ids) - boundary_ids
            if len(seam_ids) > 1:
                continue
            seams_ok = True
            for e in seam_ids:
                same = [entities[u] for u in loop.refs if entities[u].refs[-1] == e]
                edge = entities[e]
                curve = entities.get(edge.refs[-1]) if edge.refs else None
                if len(same) != 2 or same[0].orientation == same[1].orientation or curve is None or curve.kind != 'SEAM_CURVE':
                    seams_ok = False
            if not seams_ok:
                continue
            full_circles = True
            for edge_id in boundary_ids:
                edge = entities[edge_id]
                curve = entities.get(edge.refs[2]) if len(edge.refs) == 3 else None
                if curve is not None and curve.kind == 'SURFACE_CURVE' and curve.refs:
                    curve = entities.get(curve.refs[0])
                if len(edge.refs) != 3 or edge.refs[0] != edge.refs[1] or curve is None or curve.kind != 'CIRCLE':
                    full_circles = False
            # Both uses of each boundary edge must be on distinct faces.
            if full_circles and all(len({u['face'] for u in b['uses']}) == 2 for b in bad):
                eligible.append(bound_id)
        if len(eligible) != 1:
            raise ValueError('No hay una corrección única y acotada del contorno toroidal')
        candidates += eligible
    patched = text
    for bound_id in candidates:
        entity = entities[bound_id]; pos = entity.flag_position
        old = '.T.' if entity.orientation == 1 else '.F.'
        if patched[pos:pos+3] != old:
            raise ValueError('La posición de orientación no coincide con la entidad')
        patched = patched[:pos] + ('.F.' if old == '.T.' else '.T.') + patched[pos+3:]
    if not auditar_texto(patched)['ok']:
        raise ValueError('La propuesta no corrige toda la incidencia orientada')
    return patched, candidates


def verificar_o_corregir_archivo(path):
    path = Path(path)
    with path.open(encoding='utf-8', newline='') as stream:
        text = stream.read()
    result = auditar_texto(text)
    if result['ok']:
        return dict(ok=True, modified=False, corrected_bounds=[], audit=result)
    corrected, bounds = _proponer_correccion(text)
    with path.open('w', encoding='utf-8', newline='') as stream:
        stream.write(corrected)
    return dict(ok=True, modified=True, corrected_bounds=bounds, audit=auditar_texto(corrected),
                requires_exact_source_validation=True)
