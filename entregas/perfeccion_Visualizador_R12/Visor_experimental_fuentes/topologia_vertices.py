"""Enlaces de vértices: dos caras por arista no bastan para una superficie regular."""
from collections import Counter


def inspeccionar_vertices(mesh, *, limite_ejemplos=20):
    incident=[[] for _ in mesh.vertices]
    for a,b,c in mesh.faces:
        incident[a].append((int(b),int(c)))
        incident[b].append((int(c),int(a)))
        incident[c].append((int(a),int(b)))
    errors=[];boundary=0
    for index,pairs in enumerate(incident):
        if not pairs:continue
        adj={}
        for a,b in pairs:
            adj.setdefault(a,set()).add(b);adj.setdefault(b,set()).add(a)
        unseen=set(adj);fans=0
        while unseen:
            fans+=1;stack=[unseen.pop()]
            while stack:
                for vertex in adj[stack.pop()]:
                    if vertex in unseen:unseen.remove(vertex);stack.append(vertex)
        degrees=Counter(x for pair in pairs for x in pair)
        ends=sum(d==1 for d in degrees.values())
        valid=fans==1 and all(d in (1,2) for d in degrees.values()) and ends in (0,2)
        if valid and ends==2:boundary+=1
        if not valid:
            errors.append({'vertice':index,'xyz_mm':mesh.vertices[index].tolist(),
                           'abanicos':fans,'grados_distintos_de_dos':sum(d!=2 for d in degrees.values())})
    return {'vertices_no_manifold':len(errors),'vertices_de_borde':boundary,
            'ejemplos':errors[:limite_ejemplos],
            'enlaces_regulares_cerrados':bool(len(mesh.faces) and not errors and boundary==0),
            'criterio':'Un ciclo por vértice interior; un camino por vértice de borde.'}
