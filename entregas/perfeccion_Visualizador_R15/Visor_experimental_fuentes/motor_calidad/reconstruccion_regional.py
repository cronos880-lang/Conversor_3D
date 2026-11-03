"""Local CAD patches on smooth connected regions, preserving real boundaries.

Only a proposal: the original STL, exact CAD, material, fine meshes and the
previous conversion's error must be checked before it can replace a result.
Analytic cylinder/cone/torus faces are protected from replacement.
"""
from collections import defaultdict
import numpy as np
import cadquery as cq
from OCP.BRep import BRep_Tool, BRep_Builder
from OCP.Geom import Geom_Plane, Geom_BSplineSurface
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
from OCP.BRepLib import BRepLib
from reunion_con_huecos import construir_grupo, exacto






def cuadrilatero_curvo(faces,part,wires,max_support=.0005):
    """Native four-boundary CAD loft, with native isoparametric edges.

    Avoid projecting every old edge numerically onto the new surface: the
    native rectangular face already has exact UV bounds and iso pcurves.
    """
    from reunion_con_huecos import _ordenar,comparar_soportes
    from OCP.GeomFill import GeomFill_BSplineCurves,GeomFill_StretchStyle
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.TopoDS import TopoDS
    from pcurvas_compartidas import _iso_comun
    if len(wires)!=1:raise ValueError('Se preservan los huecos')
    ordered,physical=_ordenar(wires[0])
    # Native wire builders may choose a different starting edge. Canonicalize
    # the four-boundary parameterization using geometry, not TShape addresses.
    start=min(range(len(ordered)),key=lambda i:tuple(np.round(ordered[i][0].Value(ordered[i][1]).Coord(),9)))
    ordered=ordered[start:]+ordered[:start]
    if not 4<=len(ordered)<=10:raise ValueError('Presupuesto de lados compuestos')
    if len(ordered)==4:curves=[c for c,a,b in ordered]
    else:
        from frontera_compuesta import cuatro_lados
        curves=cuatro_lados(ordered)
        if curves is None:raise ValueError('No se componen cuatro lados exactos')
    surface=GeomFill_BSplineCurves(*curves,GeomFill_StretchStyle).Surface()
    if any(_iso_comun(c,a,b,surface) is None for _,c,a,b in physical):raise ValueError('El loft no conserva límites isoparamétricos')
    maker=BRepBuilderAPI_MakeFace(surface,1e-7)
    if not maker.IsDone():raise ValueError('No se construye la cara CAD')
    face=cq.Face(maker.Face())
    if face.normalAt(face.Center()).dot(faces[part[0]].normalAt(faces[part[0]].Center()))<0:face=cq.Face(TopoDS.Face_s(face.wrapped.Reversed()))
    if not exacto(face.wrapped):raise ValueError('Loft no exacto')
    area=sum(faces[i].Area() for i in part)
    if abs(face.Area()-area)>max(1e-6,area*.001):raise ValueError('El loft cambia área de región')
    support=comparar_soportes([faces[i] for i in part],face)
    if support['max_mm']>max_support:raise ValueError('El loft abandona la fuente local')
    return face,dict(construction='loft_cuatro_curvas_nativo',max_soporte_bidireccional_mm=support['max_mm'])


def proponer(shape, *, max_angle=8., max_group=None, reference_volume=None, blocked_faces=(),support_limit=.0005):
    faces=shape.Faces();ownership=defaultdict(list);edges={}
    if max_group is None:max_group=6 if len(faces)<=500 else 2
    for i,face in enumerate(faces):
        for edge in face.Edges():ownership[edge.hashCode()].append(i);edges[edge.hashCode()]=edge
    allowed={i for i,f in enumerate(faces) if isinstance(BRep_Tool.Surface_s(f.wrapped),(Geom_Plane,Geom_BSplineSurface)) and f.Area()>=.005}-set(blocked_faces)
    graph=defaultdict(set)
    for key,pair in ownership.items():
        if len(pair)!=2 or not all(i in allowed for i in pair):continue
        edge=edges[key]
        # Fragile micro-contact boundaries remain entirely unchanged.
        if edge.Length()<.02:continue
        a,b=pair
        try:
            worst=max(1-abs(faces[a].normalAt(edge.positionAt(t)).dot(faces[b].normalAt(edge.positionAt(t)))) for t in (.2,.5,.8))
            if worst>1-np.cos(np.radians(max_angle)):continue
            if any(e.Length()<.002 for i in pair for e in faces[i].Edges()):continue
            graph[a].add(b);graph[b].add(a)
        except Exception:continue
    removed=set();added=[];records=[]
    def attempt(part):
        if any(i in removed for i in part):return False
        border={e.hashCode():e for i in part for e in faces[i].Edges() if sum(j in part for j in ownership[e.hashCode()])==1}
        if not 3<=len(border)<=28:return False
        wires=cq.Wire.combine(list(border.values()))
        if not wires:return False
        try:
            face,proof=cuadrilatero_curvo(faces,part,wires,max_support=support_limit)
            # Individual patches must pass exact geometry, not just sewing.
            if not exacto(face.wrapped):return False
            removed.update(part);added.append(face);records.append(dict(faces=part,**proof))
            print('[Regiones CAD]',part,'-> 1; bound',proof['max_soporte_bidireccional_mm'],flush=True)
            return True
        except Exception as exc:
            records.append(dict(faces=part,rejected=str(exc)))
            return False
    for seed in sorted(allowed,key=lambda i:(-len(graph[i]),-faces[i].Area(),i)):
        if seed in removed:continue
        group=[seed];seen={seed};queue=[seed]
        while queue and len(group)<max_group:
            current=queue.pop(0)
            for other in sorted(graph[current]-removed-seen):
                seen.add(other);group.append(other);queue.append(other)
                if len(group)>=max_group:break
        if len(group)>2 and attempt(sorted(group)):continue
        for other in sorted(graph[seed]-removed):
            if attempt(sorted([seed,other])):break
    if not removed:
        from collections import Counter
        print('RECHAZOS REGIONALES',Counter(r.get('rejected','') for r in records),flush=True)
        raise ValueError('No hay regiones suaves reconstruibles sin modificar su frontera')
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt
    definitions=[]
    for face in added:
        surface=BRep_Tool.Surface_s(face.wrapped).Copy()
        if not isinstance(surface,Geom_BSplineSurface):raise ValueError('El loft requiere soporte B-spline')
        surface.IncreaseDegree(max(4,surface.UDegree()),max(4,surface.VDegree()))
        if surface.UMultiplicity(1)!=surface.UDegree()+1 or surface.VMultiplicity(1)!=surface.VDegree()+1:raise ValueError('Loft no clamped')
        definitions.append((face,surface,np.array(face.normalAt(face.Center()).toTuple())))
    latest=[]
    def assemble(offset):
        latest.clear()
        sewing=BRepBuilderAPI_Sewing(1e-7,True,True,True,False)
        for i,face in enumerate(faces):
            if i not in removed:sewing.Add(face.wrapped)
        for face,surface,direction in definitions:
            s=surface.Copy()
            for i in range(3,s.NbUPoles()-1):
                for j in range(3,s.NbVPoles()-1):
                    p=np.array(s.Pole(i,j).Coord())+offset*direction;s.SetPole(i,j,gp_Pnt(*map(float,p)))
            built=cq.Face(BRepBuilderAPI_MakeFace(s,1e-7).Face())
            if built.normalAt(built.Center()).dot(face.normalAt(face.Center()))<0:built=cq.Face(TopoDS.Face_s(built.wrapped.Reversed()))
            latest.append(built)
            sewing.Add(built.wrapped)
        sewing.Perform();shells=cq.Shape.cast(sewing.SewedShape()).Shells()
        if len(shells)!=len(shape.Shells()):raise ValueError('La reconstrucción regional cambia las fronteras')
        maker=BRepBuilderAPI_MakeSolid()
        for shell in shells:maker.Add(shell.wrapped)
        solid=maker.Solid();BRepLib.OrientClosedSolid_s(solid)
        return cq.Solid(solid)
    target=shape.Volume();result=assemble(0.);initial=result.Volume();delta=initial-target;offset=0.
    improving=bool(reference_volume is not None and abs(initial-reference_volume)<=abs(target-reference_volume)+1e-8)
    if not improving and abs(delta)>max(1e-8,abs(target)*1e-10):
        probe=1e-4;slope=(assemble(probe).Volume()-initial)/probe
        if abs(slope)<1e-10:raise ValueError('No se determina la restricción de volumen del sólido cerrado')
        offset=-delta/slope
        if abs(offset)>.003:raise ValueError('La restricción de volumen exige desplazar demasiado los polos interiores')
        result=assemble(offset)
    final=result.Volume()
    if not improving and abs(final-target)>max(1e-8,abs(target)*1e-10):raise ValueError('No conserva el volumen del sólido cerrado')
    if not exacto(result.wrapped):raise ValueError('La reconstrucción regional no conserva CAD exacto')
    accepted=[r for r in records if 'construction' in r]
    for info,face in zip(accepted,latest):info['new_face_signature']=dict(center=face.Center().toTuple(),area=face.Area())
    records.append(dict(global_volume_constraint=True,target_mm3=target,initial_mm3=initial,final_mm3=final,interior_pole_shift_mm=float(offset),boundary_and_tangents_unchanged=True,improves_source_volume=improving,source_volume_mm3=reference_volume))
    return result,records
