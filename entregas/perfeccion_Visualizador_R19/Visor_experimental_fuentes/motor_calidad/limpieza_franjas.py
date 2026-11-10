"""Limpieza CONSERVADORA de bandas estrechas coplanares en sólidos B-Rep.

No inventa superficies ni modifica piezas si no detecta el patrón de bandas.
Usa superficies CAD existentes y ShapeUpgrade_UnifySameDomain con aristas
protegidas. Acepta el resultado solo después de la validación STL/STEP.

Los umbrales geométricos se interpretan en las unidades CAD del STL,
habitualmente milímetros. No reconstruye redondeos ni recupera parámetros.
"""
from __future__ import annotations
from collections import defaultdict
import math
from pathlib import Path
import numpy as np
import cadquery as cq
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Plane
from OCP.BRep import BRep_Tool
from OCP.BRepAlgoAPI import BRepAlgoAPI_Check
from calidad_topologica import inspeccionar, aceptar_consolidacion


def _bandas(shape):
    """Componentes lineales de >=5 caras, conectados por franjas casi coplanares."""
    faces = shape.Faces()
    bb = shape.BoundingBox()
    longitud_min = max(5.0, 0.15 * math.sqrt(bb.xlen**2 + bb.ylen**2 + bb.zlen**2))
    planos = {}
    for i,face in enumerate(faces):
        adaptor = BRepAdaptor_Surface(face.wrapped)
        if adaptor.GetType() == GeomAbs_Plane:
            p = adaptor.Plane()
            direction=p.Axis().Direction()
            location=p.Location()
            planos[i]=(np.array([direction.X(),direction.Y(),direction.Z()]),
                       np.array([location.X(),location.Y(),location.Z()]))
    owner = defaultdict(list)
    for i,face in enumerate(faces):
        for edge in face.Edges():
            owner[edge.hashCode()].append((i,edge))
    links = {}
    neighbors = defaultdict(list)
    for shared in owner.values():
        if len(shared) != 2:
            continue
        (i,e),(j,_) = shared
        if i not in planos or j not in planos or e.Length() < longitud_min:
            continue
        n,p=planos[i]; m,q=planos[j]
        # Evita confundir caras planas claramente distintas.
        a=math.degrees(math.acos(float(np.clip(abs(np.dot(n,m)), 0,1))))
        separation=abs(float(np.dot(q-p,n)))
        if a > .2 or separation > .035:
            continue
        # Al menos una de las dos regiones debe ser una banda estrecha.
        if min(faces[i].Area(),faces[j].Area())/e.Length() > .20:
            continue
        key=frozenset((i,j))
        links[key]=e
        neighbors[i].append(j)
        neighbors[j].append(i)
    components=[]
    visited=set()
    for start in sorted(neighbors):
        if start in visited:continue
        nodes=[];stack=[start]
        while stack:
            x=stack.pop()
            if x in visited:continue
            visited.add(x);nodes.append(x)
            stack.extend(neighbors[x])
        if len(nodes) < 5 or any(len(neighbors[x])>2 for x in nodes):
            continue
        ends=sorted(x for x in nodes if len(neighbors[x])==1)
        if len(ends)!=2:continue
        chain=[ends[0]]
        while chain[-1]!=ends[1]:
            choices=[v for v in neighbors[chain[-1]] if v not in chain]
            if len(choices)!=1:break
            chain.append(choices[0])
        if len(chain)!=len(nodes):continue
        components.append((chain,links))
    components.sort(key=lambda item:len(item[0]),reverse=True)
    return components


def _max_tolerancia_aristas(solid):
    return max((float(BRep_Tool.Tolerance_s(e.wrapped)) for e in solid.Edges()), default=0.0)


def limpiar(src_stl: Path, src_step: Path, dst_step: Path, original_mesh, validar):
    """Retorna metadatos; nunca escribe el STEP destino si no pasa validación.

    Se realiza UNA propuesta con grupos de hasta 2 caras para que cada región
    unificada sea muy próxima a su superficie original. Se rechaza cualquier
    degradación geométrica importante o topológica y se preserva el STEP base.
    """
    report={'aplicado':False,'motivo':'Sin franjas largas, estrechas y casi coplanares.'}
    shape=cq.importers.importStep(str(src_step)).solids().val()
    bands=_bandas(shape)
    if not bands:return report
    if len(bands)>1:
        return {'aplicado':False,'motivo':'Varias regiones candidatas: no se simplifican sin validación específica.'}
    chain,links=bands[0]
    if len(chain)>9:
        return {'aplicado':False,'motivo':'Región extensa: se evita una fusión no supervisada.'}
    # Proteger una arista cada dos uniones: nunca forzamos la unión de todas.
    # También proteger el resto de uniones casi coplanares no seleccionadas.
    protected=[links[frozenset((chain[i],chain[i+1]))]
               for i in range(1,len(chain)-1,2)]
    tool=ShapeUpgrade_UnifySameDomain(shape.wrapped,True,True,False)
    tool.SetLinearTolerance(.025)
    tool.SetAngularTolerance(math.radians(.2))
    for edge in protected:tool.KeepShape(edge.wrapped)
    tool.Build()
    out=cq.Shape(tool.Shape())
    expected=len(shape.Faces())-(len(chain)-1-len(protected))
    if len(out.Faces())!=expected or len(out.Solids())!=1:
        report['motivo']='La consolidación modificó otras regiones: descartada.'
        return report
    # La reimportación STEP es necesaria: algunas reparaciones se producen en
    # la escritura y lectura del fichero, no en el objeto CAD en memoria.
    cq.exporters.export(out,str(dst_step))
    try:
        converted=cq.importers.importStep(str(dst_step)).solids().val()
        if not converted.isValid() or len(converted.Faces())!=expected:
            raise ValueError('STEP reconstruido no es un sólido válido.')
        original_error=validar(src_stl,src_step,original_mesh)
        next_error=validar(src_stl,dst_step,original_mesh)
        volume_change=abs(converted.Volume()-shape.Volume())/shape.Volume()
        edge0=_max_tolerancia_aristas(shape)
        edge1=_max_tolerancia_aristas(converted)
        topologia_original = inspeccionar(shape)
        topologia_convertida = inspeccionar(converted)
        aprobada, explicacion = aceptar_consolidacion(topologia_original, topologia_convertida)
        if not aprobada:
            raise ValueError(explicacion)
        bounds0=original_error['caja_error_mm']
        bounds1=next_error['caja_error_mm']
        stl0=original_error['distancia_stl_step_mm']
        stl1=next_error['distancia_stl_step_mm']
        cad0=original_error['distancia_step_stl_mm']
        cad1=next_error['distancia_step_stl_mm']
        # No perseguir reducción de caras a costa de precisión o de mayores
        # tolerancias de unión. La mejora es opcional y reversible.
        if volume_change > .001:raise ValueError('Variación de volumen excesiva.')
        if edge1 > max(edge0+.003,.015):raise ValueError('Aumenta la tolerancia de aristas.')
        if bounds1 > bounds0+.002:raise ValueError('Se alteran las cotas exteriores.')
        if stl1['max_muestreado'] > stl0['max_muestreado']+.012:
            raise ValueError('Desviación excesiva STL a CAD.')
        if cad1['max_muestreado'] > cad0['max_muestreado']+.008:
            raise ValueError('Desviación excesiva CAD a STL.')
        if max(stl1['p95']-stl0['p95'],cad1['p95']-cad0['p95'])>.003:
            raise ValueError('La desviación superficial empeora demasiado.')
        oldcheck=BRepAlgoAPI_Check(shape.wrapped);oldcheck.Perform()
        newcheck=BRepAlgoAPI_Check(converted.wrapped);newcheck.Perform()
        if oldcheck.IsValid() and not newcheck.IsValid():
            raise ValueError('La prueba booleana es peor que en la pieza original.')
        return {'aplicado':True,'caras_antes':len(shape.Faces()),
                'caras_despues':len(converted.Faces()),
                'franjas_reconocidas':len(chain),
                'tolerancia_max_arista_antes_mm':round(edge0,6),
                'tolerancia_max_arista_despues_mm':round(edge1,6),
                'volumen_variacion_relativa_pct':round(100*volume_change,5),
                'topologia':topologia_convertida,
                'nota':'Move face debe verificarse en Onshape; la validez B-Rep no garantiza todas las operaciones de edición.'}
    except Exception as exc:
        report['motivo']=f'Candidato descartado: {exc}'
        return report
    finally:
        # Conservar únicamente archivos que sean aprobados por quien llama.
        pass
