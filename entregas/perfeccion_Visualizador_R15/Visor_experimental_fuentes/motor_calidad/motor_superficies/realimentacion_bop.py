"""Reconstruir sólo hipótesis implicadas en interferencias del conjunto.

El BOP en frío y todos los controles originales siguen siendo obligatorios.
No elimina cuerpos ni cambia tolerancias. Sólo la vía experimental usa esto.
"""
import json,os
from pathlib import Path
import numpy as np
import cadquery as cq
from OCP.BRepAlgoAPI import BRepAlgoAPI_Check
from OCP.TopExp import TopExp
from OCP.TopAbs import TopAbs_FACE,TopAbs_EDGE,TopAbs_VERTEX
from OCP.TopTools import TopTools_IndexedMapOfShape,TopTools_IndexedDataMapOfShapeListOfShape
from OCP.Geom import Geom_Plane,Geom_SurfaceOfLinearExtrusion


def retirables(regions,state):
    return [r for r in regions if r in state['primary'] and isinstance(state['surfaces'][r],(Geom_Plane,Geom_SurfaceOfLinearExtrusion))]


def diagnosticar(shape,state):
    check=BRepAlgoAPI_Check(shape.wrapped,False,True)
    if check.IsValid():return dict(interferencias=0,retiros=[],refinar=[])
    problems=list(check.Result());face_map=TopTools_IndexedMapOfShape();face_labels={}
    for label,face in state['faces'].items():face_labels[face_map.Add(face)]=int(label)
    maps={}
    for kind in [TopAbs_EDGE,TopAbs_VERTEX]:
        m=TopTools_IndexedDataMapOfShapeListOfShape();TopExp.MapShapesAndAncestors_s(shape.wrapped,kind,TopAbs_FACE,m);maps[kind]=m
    def owners(obj):
        if obj.IsNull():return set()
        if obj.ShapeType()==TopAbs_FACE:
            index=face_map.FindIndex(obj);return {face_labels[index]} if index else set()
        m=maps.get(obj.ShapeType())
        if m is None:return set()
        index=m.FindIndex(obj)
        return set() if not index else {face_labels[face_map.FindIndex(f)] for f in m.FindFromIndex(index) if face_map.FindIndex(f)}
    labels=state['labels'];mesh=state['mesh'];groups={int(r):np.flatnonzero(labels==r) for r in np.unique(labels)}
    withdrawals={};refine=set();rows=[]
    for problem in problems:
        faulty=list(problem.GetFaultyShapes1())+list(problem.GetFaultyShapes2());regions=set().union(*(owners(x) for x in faulty)) if faulty else set()
        if not regions:raise ValueError('BOP no permite vincular el defecto a regiones fuente')
        candidates=retirables(regions,state)
        if not candidates:
            # La frontera de un parche libre puede venir de una hipótesis vecina.
            ids=np.concatenate([groups[r] for r in regions]);vertices=np.unique(mesh.faces[ids]);touching=np.flatnonzero(np.isin(mesh.faces,vertices).any(axis=1))
            candidates=retirables(set(map(int,labels[touching])),state)
        row=dict(estado=str(problem.GetCheckStatus()),regiones=sorted(regions))
        if candidates:
            region=min(candidates,key=lambda r:float(mesh.area_faces[groups[r]].sum()))
            points=[v.Center().toTuple() for obj in faulty for v in cq.Shape.cast(obj).Vertices()]
            ids=np.unique(mesh.faces[groups[region]])
            if points:
                center=np.mean(points,axis=0);vertex=int(ids[np.linalg.norm(mesh.vertices[ids]-center,axis=1).argmin()])
            else:vertex=int(ids[0])
            withdrawals[region]=vertex;row['retirar']=region
        else:
            available=[r for r in regions if r not in state['primary'] and len(groups[r])>1 and getattr(mesh,'regiones_libres_refinadas',{}).get(id(state['surfaces'][r]),0)<2]
            if not available:
                row['sin_accion']='No se retiran superficies confirmadas ni se altera una región ya triangular'
                rows.append(row);continue
            region=min(available,key=lambda r:float(mesh.area_faces[groups[r]].sum()));refine.add(region);row['refinar']=region
        rows.append(row)
    return dict(interferencias=len(problems),retiros=sorted(withdrawals.items()),refinar=sorted(refine-set(withdrawals)),defectos=rows)


def resolver(shape,max_reconstrucciones=2):
    import constructor_barridos as constructor
    from solidificacion_exacta import solidificar
    records=[]
    def save():
        target=os.environ.get('PILOTO_CAD_FALLOS')
        if target:
            p=Path(target);p.mkdir(parents=True,exist_ok=True);(p/'realimentacion_BOP.json').write_text(json.dumps(records,indent=2))
    for iteration in range(max_reconstrucciones+1):
        state=constructor.ULTIMO_ESTADO
        if state is None:raise ValueError('No se dispone de la trazabilidad fuente de la reconstrucción')
        try:diagnosis=diagnosticar(shape,state)
        except Exception as exc:
            records.append(dict(iteracion=iteration,error=str(exc)));save();raise
        records.append(dict(iteracion=iteration,caras=len(shape.Faces()),**diagnosis));save()
        print('BOP CONJUNTO',dict(iteracion=iteration,caras=len(shape.Faces()),interferencias=diagnosis['interferencias'],retiros=diagnosis['retiros'],refinar=diagnosis['refinar']),flush=True)
        if not diagnosis['interferencias']:return shape,records
        if not diagnosis['retiros'] and not diagnosis['refinar']:
            raise ValueError('Persisten interferencias sin una reconstrucción local certificable: '+str(diagnosis['interferencias']))
        if iteration==max_reconstrucciones:raise ValueError('Persisten interferencias del conjunto tras las reconstrucciones acotadas: '+str(diagnosis['interferencias']))
        tol,move,smooth,regular,triangles=state['args']
        shell,_=constructor.construir(state['mesh'],state['labels'],state['surfaces'],tol,move,smooth,regular,triangles,_estado=state,_retiros=diagnosis['retiros'],_refinar=diagnosis['refinar'])
        shape=cq.Shape.cast(solidificar(shell))
    raise AssertionError('Bucle de revisión no concluido')
