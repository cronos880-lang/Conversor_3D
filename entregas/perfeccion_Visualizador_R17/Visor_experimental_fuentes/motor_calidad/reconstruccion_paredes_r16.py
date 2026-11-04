"""Unir regiones de pared mediante frontera compartida e interior medido.

Se proponen grupos por conectividad y normales geométricas. No hay nombres de
archivo, coordenadas, plantillas ni número de caras específico de una pieza.
La propuesta sólo se acepta fuera de este módulo tras verificar el STL original.
"""
from collections import defaultdict
import numpy as np
import cadquery as cq
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace,BRepBuilderAPI_Sewing,BRepBuilderAPI_MakeSolid
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepLib import BRepLib
from OCP.Geom import Geom_Plane,Geom_BSplineSurface
from OCP.GeomFill import GeomFill_BSplineCurves,GeomFill_StretchStyle
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pnt

def firma_cara(face):
    """Identificación local para retirar una propuesta, nunca certificado CAD.

    El área adaptativa OCC de una NURBS puede variar al serializar los mismos
    polos. Se usan puntos del soporte y caja, y se exige coincidencia única.
    """
    surface=BRep_Tool.Surface_s(face.wrapped);u0,u1,v0,v1=surface.Bounds();box=face.BoundingBox()
    return dict(center=face.Center().toTuple(),area=face.Area(),box=[getattr(box,k) for k in ('xmin','ymin','zmin','xmax','ymax','zmax')],samples=[list(surface.Value(float(u0+(u1-u0)*u),float(v0+(v1-v0)*v)).Coord()) for u in (.13,.47,.83) for v in (.17,.53,.89)])

def corresponde_firma(face,signature):
    if not isinstance(BRep_Tool.Surface_s(face.wrapped),Geom_BSplineSurface):return False
    observed=firma_cara(face)
    return (np.max(abs(np.array(observed['box'])-np.array(signature['box'])))<2e-7 and np.max(np.linalg.norm(np.array(observed['samples'])-np.array(signature['samples']),axis=1))<5e-8)

def grupos(shape,blocked=()):
    faces=shape.Faces();own=defaultdict(set);edges={};normals={};graph=defaultdict(set)
    for i,f in enumerate(faces):
        for e in f.Edges():own[e.hashCode()].add(i);edges[e.hashCode()]=e
        if i in blocked or not isinstance(BRep_Tool.Surface_s(f.wrapped),(Geom_Plane,Geom_BSplineSurface)):continue
        try:normals[i]=np.array(f.normalAt(f.Center()).toTuple())
        except Exception:continue
    for key,pair in own.items():
        if len(pair)!=2 or not all(i in normals for i in pair):continue
        a,b=sorted(pair)
        if normals[a]@normals[b]<np.cos(np.radians(10)):continue
        graph[a].add(b);graph[b].add(a)
    used=set();parts=[]
    for seed in sorted(normals,key=lambda i:(-faces[i].Area(),i)):
        if seed in used:continue
        part={seed};queue=[seed]
        while queue:
            current=queue.pop(0)
            for other in sorted(graph[current]-used-part):
                if normals[other]@normals[seed]<np.cos(np.radians(20)):continue
                part.add(other);queue.append(other)
                if len(part)>=24:break
            if len(part)>=24:break
        used.update(part)
        if len(part)>1 and any(isinstance(BRep_Tool.Surface_s(faces[i].wrapped),Geom_BSplineSurface) for i in part):parts.append(sorted(part))
    return parts,own,edges

def construir(faces,part,border):
    from reunion_con_huecos import _ordenar
    from frontera_compuesta import cuatro_lados
    from pcurvas_compartidas import _iso_comun
    from ajuste_interior_r16 import ajustar
    wires=cq.Wire.combine(border)
    if len(wires)!=1 or not wires[0].IsClosed():raise ValueError('Se conserva la región con huecos o más de un contorno')
    ordered,physical=_ordenar(wires[0])
    if not 4<=len(ordered)<=28:raise ValueError('Contorno fuera del presupuesto')
    start=min(range(len(ordered)),key=lambda i:tuple(np.round(ordered[i][0].Value(ordered[i][1]).Coord(),9)));ordered=ordered[start:]+ordered[:start]
    curves=[c for c,a,b in ordered] if len(ordered)==4 else cuatro_lados(ordered)
    if curves is None:raise ValueError('No se compone una frontera de cuatro lados')
    surface=GeomFill_BSplineCurves(*curves,GeomFill_StretchStyle).Surface()
    if any(_iso_comun(c,a,b,surface) is None for _,c,a,b in physical):raise ValueError('La construcción no conserva las curvas físicas')
    surface,proof=ajustar(surface,[faces[i] for i in part],spans=10)
    if any(_iso_comun(c,a,b,surface) is None for _,c,a,b in physical):raise ValueError('El ajuste cambia la frontera')
    face=cq.Face(BRepBuilderAPI_MakeFace(surface,1e-7).Face());anchor=max(part,key=lambda i:faces[i].Area())
    if face.normalAt(faces[anchor].Center()).dot(faces[anchor].normalAt(faces[anchor].Center()))<0:face=cq.Face(TopoDS.Face_s(face.wrapped.Reversed()))
    if not BRepCheck_Analyzer(face.wrapped,True,False,True).IsValid():raise ValueError('La cara propuesta no pasa CAD exacto')
    if abs(face.Area()-sum(faces[i].Area() for i in part))>sum(faces[i].Area() for i in part)*.003:raise ValueError('La región cambia su área más del presupuesto de propuesta')
    return face,proof

def proponer(shape,*,reference_volume=None,blocked_faces=(),maximum_groups=16):
    from bandas_compuestas_r16 import grupos as bandas
    faces=shape.Faces();parts,own,edges=grupos(shape,blocked_faces);strips=[b for b in bandas(shape) if not set(b['faces'])&set(blocked_faces)];parts=[b['faces'] for b in strips]+parts;removed=set();added=[];records=[]
    for part in parts[:maximum_groups]:
        if set(part)&removed:continue
        try:
            border=[edges[k] for k,owners in own.items() if len(set(part)&owners)==1]
            face,proof=construir(faces,part,border)
            removed.update(part);added.append(face);records.append(dict(faces=part,ok=True,**proof));print('PARED RECONSTRUIDA',part,'-> 1',flush=True)
        except Exception as exc:
            records.append(dict(faces=part,ok=False,error=str(exc)));print('PARED CONSERVADA',part,str(exc),flush=True)
    if not added:raise ValueError('No hay paredes unificables con su frontera exacta')
    def assemble(offset=0.):
        sew=BRepBuilderAPI_Sewing(1e-7,True,True,True,False);built=[]
        for i,f in enumerate(faces):
            if i not in removed:sew.Add(f.wrapped)
        for face in added:
            if offset:
                sf=BRep_Tool.Surface_s(face.wrapped).Copy();normal=np.array(face.normalAt(face.Center()).toTuple())
                for i in range(3,sf.NbUPoles()-1):
                    for j in range(3,sf.NbVPoles()-1):sf.SetPole(i,j,gp_Pnt(*map(float,np.array(sf.Pole(i,j).Coord())+offset*normal)))
                f=cq.Face(BRepBuilderAPI_MakeFace(sf,1e-7).Face())
                if f.normalAt(f.Center()).dot(face.normalAt(face.Center()))<0:f=cq.Face(TopoDS.Face_s(f.wrapped.Reversed()))
            else:f=face
            sew.Add(f.wrapped);built.append(f)
        sew.Perform();combined=cq.Shape.cast(sew.SewedShape())
        if sew.NbFreeEdges() or len(combined.Shells())!=len(shape.Shells()):raise ValueError('Las paredes no conservan el cierre del sólido')
        maker=BRepBuilderAPI_MakeSolid()
        for sh in combined.Shells():maker.Add(sh.wrapped)
        result=maker.Solid();BRepLib.OrientClosedSolid_s(result);return cq.Solid(result),built
    result,latest=assemble();initial=result.Volume();previous=shape.Volume();offset=0.
    if reference_volume is not None and abs(initial-reference_volume)>abs(previous-reference_volume)+1e-8:
        probe,_=assemble(1e-4);slope=(probe.Volume()-initial)/1e-4
        if abs(slope)<1e-10:raise ValueError('No se determina la restricción de volumen')
        offset=(previous-initial)/slope
        if abs(offset)>.0005:raise ValueError('El volumen requiere demasiado desplazamiento interior')
        result,latest=assemble(offset)
        if abs(result.Volume()-previous)>max(1e-8,previous*1e-10):raise ValueError('El volumen no se conserva')
    if not BRepCheck_Analyzer(result.wrapped,True,False,True).IsValid():raise ValueError('El sólido no conserva CAD exacto')
    for record,face in zip([r for r in records if r['ok']],latest):record['new_face_signature']=firma_cara(face)
    records.append(dict(restriccion_volumen=True,anterior_mm3=previous,inicial_mm3=initial,final_mm3=result.Volume(),desplazamiento_interior_mm=offset))
    return result,records
