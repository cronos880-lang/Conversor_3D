"""Detectar bandas extruidas suaves entre tapas planas, sin tocar cilindros.

Una banda sólo se propone si su frontera tiene dos tapas planas perpendiculares
al eje y todas sus otras curvas son generatrices. La aceptación CAD, fuente y
material sigue siendo independiente.
"""
from collections import defaultdict
import numpy as np
from OCP.BRep import BRep_Tool
from OCP.Geom import Geom_SurfaceOfLinearExtrusion,Geom_Plane,Geom_BSplineSurface

def grupos(shape):
    faces=shape.Faces();own=defaultdict(set);edges={};out=[];used=set()
    for i,f in enumerate(faces):
        for e in f.Edges():own[e.hashCode()].add(i);edges[e.hashCode()]=e
    for seed,f in enumerate(faces):
        s=BRep_Tool.Surface_s(f.wrapped)
        if seed in used or not isinstance(s,Geom_SurfaceOfLinearExtrusion):continue
        axis=np.array(s.Direction().Coord());allowed=set();graph=defaultdict(set)
        seed_range=np.array([v.toTuple() for v in f.Vertices()])@axis;seed_lo,seed_hi=seed_range.min(),seed_range.max()
        for i,g in enumerate(faces):
            support=BRep_Tool.Surface_s(g.wrapped)
            if not isinstance(support,(Geom_Plane,Geom_BSplineSurface,Geom_SurfaceOfLinearExtrusion)):continue
            try:
                extent=np.array([v.toTuple() for v in g.Vertices()])@axis
                if abs(extent.min()-seed_lo)>1e-5 or abs(extent.max()-seed_hi)>1e-5:continue
                if abs(np.array(g.normalAt(g.Center()).toTuple())@axis)<.002:allowed.add(i)
            except Exception:continue
        for key,pair in own.items():
            if len(pair)!=2 or not all(i in allowed for i in pair):continue
            a,b=pair;e=edges[key]
            try:
                if any(faces[a].normalAt(e.positionAt(t)).dot(faces[b].normalAt(e.positionAt(t)))<np.cos(np.radians(12)) for t in [.2,.5,.8]):continue
                graph[a].add(b);graph[b].add(a)
            except Exception:continue
        part={seed};queue=[seed]
        while queue and len(part)<=12:
            current=queue.pop(0)
            for other in sorted(graph[current]-part-used):part.add(other);queue.append(other)
        if not 2<=len(part)<=12:continue
        caps=set();compatible=True
        for key,owners in own.items():
            if len(part&owners)!=1:continue
            external=owners-part
            if len(external)!=1:compatible=False;break
            neighbor=next(iter(external));surface=BRep_Tool.Surface_s(faces[neighbor].wrapped)
            if isinstance(surface,Geom_Plane) and abs(np.array(surface.Axis().Direction().Coord())@axis)>1-1e-10:
                caps.add(neighbor);continue
            edge=edges[key];pts=np.array([edge.positionAt(t).toTuple() for t in np.linspace(0,1,7)]);p=pts-pts[0];perp=p-np.outer(p@axis,axis)
            if np.linalg.norm(perp,axis=1).max()>5e-8:compatible=False;break
        if compatible and len(caps)==2:
            used.update(part);out.append(dict(faces=sorted(part),axis=axis.tolist(),caps=sorted(caps)))
    return out
