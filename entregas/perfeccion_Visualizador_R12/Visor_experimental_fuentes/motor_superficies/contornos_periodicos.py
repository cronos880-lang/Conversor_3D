"""Unir ciclos analíticos partidos sin eliminar superficies ni mover vértices.

El unificador de OCCT no siempre reúne arcos elípticos. Sólo se sustituyen
ciclos completos sobre la misma cónica, sin otras uniones en sus vértices
interiores. Las curvas libres y los cuerpos pequeños no se simplifican.
"""
import math
import numpy as np
from OCP.BRep import BRep_Tool,BRep_Builder
from OCP.BRepAdaptor import BRepAdaptor_Curve,BRepAdaptor_Curve2d
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.Geom import Geom_Ellipse,Geom_Circle
from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.TopExp import TopExp
from OCP.TopAbs import TopAbs_FORWARD,TopAbs_REVERSED
from OCP.TopoDS import TopoDS,TopoDS_Edge,TopoDS_Wire
from OCP.ShapeBuild import ShapeBuild_ReShape
from OCP.gp import gp_Vec2d

NUMERICO_MM=1e-9

def normalizar_step(path):
    """Normalizar el candidato en lectura fría y sustituirlo sólo si es exacto.

    Se ejecuta antes de las puertas geométricas, de interferencias y mallado.
    No constituye por sí sola una aprobación de la conversión.
    """
    import cadquery as cq
    import tempfile
    from pathlib import Path
    from OCP.BRepCheck import BRepCheck_Analyzer
    from calidad_topologica import leer_solido_step_estricto
    path=Path(path)
    try:
        original=leer_solido_step_estricto(path)
        result,proof=reunir_ciclos_analiticos(original.wrapped)
        if not proof['ciclos_reunidos']:return {'aplicado':False,**proof}
        with tempfile.TemporaryDirectory(prefix='visor_ciclos_',dir=path.parent) as directory:
            candidate=Path(directory)/'contornos.step';cq.exporters.export(cq.Shape.cast(result),str(candidate))
            cold=leer_solido_step_estricto(candidate)
            if not BRepCheck_Analyzer(cold.wrapped,True,False,True).IsValid():
                raise ValueError('La nueva serialización no conserva la coherencia CAD exacta.')
            candidate.replace(path)
        return {'aplicado':True,**proof,'lectura_fria_exacta':True,'limites_geometricos_modificados':False}
    except Exception as exc:
        return {'aplicado':False,'motivo':str(exc),'candidato_original_conservado':True}

def _soporte(curve):
    if isinstance(curve,Geom_Circle):a=b=curve.Radius()
    elif isinstance(curve,Geom_Ellipse):a,b=curve.MajorRadius(),curve.MinorRadius()
    else:return None
    return (np.array(curve.Location().Coord()),np.array(curve.Position().Direction().Coord()),
            np.array(curve.Position().XDirection().Coord()),a,b)

def _mismo_soporte(a,b):
    p,n,x,major,minor=a;q,m,y,other_major,other_minor=b
    error=float(np.linalg.norm(p-q))+abs(major-other_major)+abs(minor-other_minor)
    error+=max(major,other_major)*float(np.linalg.norm(np.cross(n,m)))
    if max(major-minor,other_major-other_minor)<1e-10:
        error+=2*max(major-minor,other_major-other_minor)
    else:error+=max(major,other_major)*float(np.linalg.norm(np.cross(x,y)))
    return error<=NUMERICO_MM

def reunir_ciclos_analiticos(shape):
    import cadquery as cq
    from pcurvas_compartidas import crear_pcurva,_error
    wrapped=cq.Shape.cast(shape);edges=wrapped.Edges();faces=wrapped.Faces()
    emap=TopTools_IndexedMapOfShape();vmap=TopTools_IndexedMapOfShape()
    for edge in edges:emap.Add(edge.wrapped)
    for vertex in wrapped.Vertices():vmap.Add(vertex.wrapped)
    endpoints=[];degree={};adjacent={i:set() for i in range(len(edges))}
    for i,edge in enumerate(edges):
        a=vmap.FindIndex(TopExp.FirstVertex_s(edge.wrapped,False));b=vmap.FindIndex(TopExp.LastVertex_s(edge.wrapped,False))
        endpoints.append((a,b))
        for v in {a,b}:degree.setdefault(v,set()).add(i)
    for i,face in enumerate(faces):
        for edge in face.Edges():adjacent[emap.FindIndex(edge.wrapped)-1].add(i)
    buckets={}
    curves={};ranges={}
    for i,edge in enumerate(edges):
        if endpoints[i][0]==endpoints[i][1] or len(adjacent[i])!=2:continue
        adaptor=BRepAdaptor_Curve(edge.wrapped);lo,hi=adaptor.FirstParameter(),adaptor.LastParameter()
        curve=BRep_Tool.Curve_s(edge.wrapped,lo,hi);support=_soporte(curve)
        if support is None:continue
        curves[i]=curve;ranges[i]=(lo,hi)
        key=tuple(sorted(adjacent[i]));groups=buckets.setdefault(key,[])
        if any(not faces[face].wrapped.Location().IsIdentity() for face in key):continue
        group=next((g for g in groups if _mismo_soporte(support,g['support'])),None)
        if group is None:group={'support':support,'edges':[]};groups.append(group)
        group['edges'].append(i)
    candidates=[]
    for groups in buckets.values():
        for group in groups:
            pending=set(group['edges'])
            while pending:
                component={pending.pop()};changed=True
                while changed:
                    used={v for i in component for v in endpoints[i]}
                    found={i for i in pending if used.intersection(endpoints[i])};changed=bool(found)
                    component.update(found);pending-=found
                if len(component)<2:continue
                incident={v:[i for i in component if v in endpoints[i]] for i in component for v in endpoints[i]}
                if any(len(links)!=2 for links in incident.values()):continue
                anchors=[v for v in incident if len(degree[v])!=2]
                if len(anchors)>1:continue
                anchor=anchors[0] if anchors else min(incident)
                current=anchor;remaining=set(component);walk=[]
                while remaining:
                    choices=[i for i in incident[current] if i in remaining]
                    if not choices:break
                    index=min(choices);a,b=endpoints[index];forward=a==current
                    walk.append((index,forward));current=b if forward else a;remaining.remove(index)
                if remaining or current!=anchor:continue
                common=curves[walk[0][0]].Copy();total=0.;signs=[];max_error=0.
                for index,forward in walk:
                    lo,hi=ranges[index];parameters=np.linspace(lo,hi,33)
                    if not forward:parameters=parameters[::-1]
                    points=[curves[index].Value(float(t)) for t in parameters]
                    projections=[GeomAPI_ProjectPointOnCurve(p,common) for p in points]
                    if any(p.NbPoints()==0 for p in projections):break
                    max_error=max(max_error,max(p.LowerDistance() for p in projections))
                    mapped=np.unwrap([p.LowerDistanceParameter() for p in projections],period=2*math.pi)
                    delta=float(mapped[-1]-mapped[0]);total+=delta;signs.append(np.sign(delta))
                else:
                    if max_error>NUMERICO_MM or len(set(signs))!=1 or abs(abs(total)-2*math.pi)>1e-10:continue
                    vertex=TopoDS.Vertex_s(vmap.FindKey(anchor));point=BRep_Tool.Pnt_s(vertex)
                    projection=GeomAPI_ProjectPointOnCurve(point,common)
                    if projection.NbPoints()==0 or projection.LowerDistance()>NUMERICO_MM:continue
                    first=projection.LowerDistanceParameter();last=first+2*math.pi
                    builder=BRep_Builder();new=TopoDS_Edge();builder.MakeEdge(new,common,max(BRep_Tool.Tolerance_s(edges[i].wrapped) for i in component))
                    builder.Add(new,vertex.Oriented(TopAbs_FORWARD));builder.Add(new,vertex.Oriented(TopAbs_REVERSED));builder.Range(new,first,last)
                    candidates.append({'old':component,'anchor':anchor,'new':new,'curve':common,'first':first,'last':last,'signs':dict(walk)})
    if not candidates:return shape,{'ciclos_reunidos':0,'superficies_modificadas':False}
    lookup={i:c for c in candidates for i in c['old']};context=ShapeBuild_ReShape();builder=BRep_Builder();changed_faces=0
    for original_ in faces:
        old=TopoDS.Face_s(original_.wrapped.Oriented(TopAbs_FORWARD))
        if not any(emap.FindIndex(e.wrapped)-1 in lookup for e in original_.Edges()):continue
        if not old.Location().IsIdentity():raise ValueError('La normalización de ciclos requiere caras sin transformación local.')
        face=TopoDS.Face_s(old.EmptyCopied());surface=BRep_Tool.Surface_s(old)
        for old_wire_ in cq.Face(old).Wires():
            old_wire=TopoDS.Wire_s(old_wire_.wrapped.Oriented(TopAbs_FORWARD));explorer=BRepTools_WireExplorer(old_wire,old);ordered=[]
            while explorer.More():ordered.append(explorer.Current());explorer.Next()
            ids=[emap.FindIndex(e)-1 for e in ordered]
            others=[i for i,index in enumerate(ids) if index not in lookup]
            if others:offset=others[0]
            elif ordered:
                candidate=lookup[ids[0]]
                offset=next(i for i,e in enumerate(ordered) if vmap.FindIndex(TopExp.FirstVertex_s(e,True))==candidate['anchor'])
            else:offset=0
            ordered=ordered[offset:]+ordered[:offset];ids=ids[offset:]+ids[:offset]
            wire=TopoDS_Wire();builder.MakeWire(wire);i=0
            while i<len(ordered):
                if ids[i] not in lookup:builder.Add(wire,ordered[i]);i+=1;continue
                candidate=lookup[ids[i]];end=i
                while end<len(ordered) and ids[end] in candidate['old']:end+=1
                if set(ids[i:end])!=candidate['old'] or len(ids[i:end])!=len(candidate['old']):
                    raise ValueError('Los arcos no forman una única vuelta consecutiva en la cara.')
                if vmap.FindIndex(TopExp.FirstVertex_s(ordered[i],True))!=candidate['anchor']:
                    raise ValueError('El ciclo no empieza en su vértice de unión.')
                index=ids[i];lo,hi=ranges[index];adaptor=BRepAdaptor_Curve(ordered[i]);t=lo if ordered[i].Orientation()==TopAbs_FORWARD else hi
                from OCP.gp import gp_Pnt,gp_Vec
                p=gp_Pnt();tangent=gp_Vec();adaptor.D1(t,p,tangent)
                if ordered[i].Orientation()==TopAbs_REVERSED:tangent.Reverse()
                q=gp_Pnt();direction=gp_Vec();candidate['curve'].D1(candidate['first'],q,direction)
                forward=tangent.Dot(direction)>0
                uv,proof=crear_pcurva(candidate['curve'],candidate['first'],candidate['last'],surface)
                if i>0:
                    previous=ordered[i-1];pc=BRepAdaptor_Curve2d(previous,old)
                    endpoint=pc.Value(pc.FirstParameter() if previous.Orientation()==TopAbs_REVERSED else pc.LastParameter())
                    start=uv.Value(candidate['first'] if forward else candidate['last']);shift=[0.,0.]
                    for dim,periodic in [(0,surface.IsUPeriodic()),(1,surface.IsVPeriodic())]:
                        if periodic:
                            period=surface.UPeriod() if dim==0 else surface.VPeriod()
                            shift[dim]=round((endpoint.Coord()[dim]-start.Coord()[dim])/period)*period
                    if any(shift):uv.Translate(gp_Vec2d(*shift))
                if _error(candidate['curve'],uv,surface,candidate['first'],candidate['last'])>5e-8:
                    raise ValueError('El ciclo reunido no conserva su parametrización.')
                edge=candidate['new'];builder.UpdateEdge(edge,uv,face,BRep_Tool.Tolerance_s(edge));builder.Range(edge,face,candidate['first'],candidate['last'])
                builder.SameRange(edge,True);builder.SameParameter(edge,True)
                builder.Add(wire,edge.Oriented(TopAbs_FORWARD if forward else TopAbs_REVERSED));i=end
            wire.Closed(True);builder.Add(face,wire.Oriented(old_wire_.wrapped.Orientation()))
        context.Replace(old,face);changed_faces+=1
    result=context.Apply(shape)
    final=cq.Shape.cast(result)
    if len(final.Faces())!=len(faces) or len(final.Solids())!=len(wrapped.Solids()):
        raise ValueError('La reunión de ciclos cambia las superficies o los cuerpos.')
    from OCP.BRepCheck import BRepCheck_Analyzer
    if BRepCheck_Analyzer(shape,True,False,True).IsValid() and not BRepCheck_Analyzer(result,True,False,True).IsValid():
        return shape,{'ciclos_reunidos':0,'rechazado':'La normalización no conserva la validez exacta.','superficies_modificadas':False}
    return result,{'ciclos_reunidos':len(candidates),'caras_reconstruidas':changed_faces,'superficies_modificadas':False,
                   'limite_coincidencia_mm':NUMERICO_MM,'vertices_desplazados':0,'aristas_eliminadas':sum(len(c['old'])-1 for c in candidates)}
