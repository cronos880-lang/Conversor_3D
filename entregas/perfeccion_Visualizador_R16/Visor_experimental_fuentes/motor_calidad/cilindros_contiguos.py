"""Propuesta conservadora de reunión de cilindros; requiere QA final independiente.

No ajusta radios ni aproxima geometría. Comprueba el área común de cada recorte
nuevo con sus recortes originales sobre el mismo cilindro. No toca el archivo
base. El llamante debe comprobar STEP reimportado, fuente, BOP y mallado fino.
"""
import numpy as np
import cadquery as cq
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain

COTA_SOPORTE_MM=1e-8
COTA_AREA_MM2=1e-7


def cilindros(shape):
    return [f for f in shape.Faces() if BRepAdaptor_Surface(f.wrapped).GetType()==GeomAbs_Cylinder]


def mismo_soporte(first,second):
    a=BRepAdaptor_Surface(first.wrapped).Cylinder();b=BRepAdaptor_Surface(second.wrapped).Cylinder()
    axis=np.asarray(a.Axis().Direction().Coord());other=np.asarray(b.Axis().Direction().Coord())
    center=np.asarray(a.Location().Coord());p=np.asarray(b.Location().Coord())
    return (abs(a.Radius()-b.Radius())<=COTA_SOPORTE_MM and
            np.linalg.norm(np.cross(axis,other))<=1e-10 and
            np.linalg.norm(np.cross(center-p,axis))<=COTA_SOPORTE_MM)


def certificar_recortes(original,result):
    old,new=cilindros(original),cilindros(result)
    if not old or not new:raise ValueError('No hay cilindros para comparar')
    records=[];old_covered=np.zeros(len(old))
    for i,f in enumerate(new):
        matches=[]
        for j,g in enumerate(old):
            if not mismo_soporte(f,g):continue
            common=BRepAlgoAPI_Common(f.wrapped,g.wrapped);common.SetNonDestructive(True);common.SetFuzzyValue(0.);common.Build()
            if not common.IsDone():raise ValueError('No se verifica la intersección de recortes cilíndricos')
            area=cq.Shape.cast(common.Shape()).Area()
            old_covered[j]+=area
            if area>1e-10:matches.append(dict(cara_fuente=j,area_interseccion_mm2=area))
        covered=sum(x['area_interseccion_mm2'] for x in matches)
        if abs(f.Area()-covered)>COTA_AREA_MM2:raise ValueError('El recorte cilíndrico nuevo altera su dominio')
        records.append(dict(cara_resultado=i,area_mm2=f.Area(),cobertura_fuente_mm2=covered,fuentes=matches))
    for j,g in enumerate(old):
        if abs(g.Area()-old_covered[j])>COTA_AREA_MM2:raise ValueError('Un recorte cilíndrico original se pierde o se duplica')
    return records


def proponer(shape):
    if len(shape.Solids())!=1 or not BRepCheck_Analyzer(shape.wrapped,True,False,True).IsValid():
        raise ValueError('Se requiere un sólido exacto válido')
    previous=cilindros(shape)
    if len(previous)<2:raise ValueError('No hay caras cilíndricas que reunir')
    unify=ShapeUpgrade_UnifySameDomain(shape.wrapped,True,True,False)
    unify.SetSafeInputMode(True);unify.SetLinearTolerance(1e-7);unify.SetAngularTolerance(1e-8)
    for f in shape.Faces():
        if BRepAdaptor_Surface(f.wrapped).GetType()!=GeomAbs_Cylinder:
            for edge in f.Edges():unify.KeepShape(edge.wrapped)
    unify.Build();result=cq.Shape.cast(unify.Shape())
    if len(result.Faces())>=len(shape.Faces()):raise ValueError('No se eliminan divisiones cilíndricas')
    if len(result.Solids())!=1 or not BRepCheck_Analyzer(result.wrapped,True,False,True).IsValid():
        raise ValueError('La reunión no conserva un sólido exacto')
    other=certificar_otras_caras(shape,result)
    proof=certificar_recortes(shape,result)
    return result,dict(caras_antes=len(shape.Faces()),caras_despues=len(result.Faces()),
                       cilindros_antes=len(previous),cilindros_despues=len(cilindros(result)),
                       recortes=proof,otras_caras=other,requiere_qa_final_independiente=True)


def certificar_otras_caras(original,result):
    # El volumen integrado por defecto de NURBS no es un invariante exacto.
    # Exigir, en cambio, los mismos soportes y dominios de TODAS las otras caras.
    old=[f for f in original.Faces() if BRepAdaptor_Surface(f.wrapped).GetType()!=GeomAbs_Cylinder]
    new=[f for f in result.Faces() if BRepAdaptor_Surface(f.wrapped).GetType()!=GeomAbs_Cylinder]
    if len(old)!=len(new):raise ValueError('Se ha cambiado el número de caras no cilíndricas')
    seen=set();records=[]
    for i,f in enumerate(old):
        candidates=[(j,g) for j,g in enumerate(new) if j not in seen and f.wrapped.IsSame(g.wrapped)]
        if candidates:
            j,_=candidates[0];seen.add(j);continue
        candidates=[(j,g) for j,g in enumerate(new) if j not in seen and BRep_Tool.Surface_s(f.wrapped)==BRep_Tool.Surface_s(g.wrapped)]
        if len(candidates)!=1:raise ValueError('No se conserva el soporte de una cara no cilíndrica')
        j,g=candidates[0];seen.add(j)
        common=BRepAlgoAPI_Common(f.wrapped,g.wrapped);common.SetNonDestructive(True);common.SetFuzzyValue(0.);common.Build()
        if not common.IsDone():raise ValueError('No se certifica el dominio no cilíndrico')
        area=cq.Shape.cast(common.Shape()).Area()
        if max(abs(f.Area()-area),abs(g.Area()-area))>COTA_AREA_MM2:raise ValueError('Se ha cambiado un dominio no cilíndrico')
        records.append(dict(cara_original=i,cara_resultado=j,area_original_mm2=f.Area(),area_nueva_mm2=g.Area(),area_comun_mm2=area))
    return dict(caras=len(old),identicas=len(old)-len(records),dominios_comprobados=records)


def ejecutar(source,base,destination,report):
    """Archivo nuevo únicamente; ante rechazo se conserva base y se borra candidato."""
    from pathlib import Path
    import sys,hashlib,json,time,tempfile,traceback,os
    source,base,destination,report=map(Path,(source,base,destination,report));paths=(source,base,destination,report)
    if len({p.resolve() for p in paths})!=4 or destination.exists() or report.exists():
        raise ValueError('Las cuatro rutas deben ser distintas y las salidas nuevas')
    if any(a.exists() and b.exists() and a.samefile(b) for i,a in enumerate(paths) for b in paths[i+1:]):
        raise ValueError('Las rutas no pueden apuntar al mismo archivo')
    sys.path.insert(0,str(Path(__file__).resolve().parent/'motor_superficies'))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();before=(sha(source),sha(base));record=dict(ok=False);start=time.monotonic()
    try:
        from preprocesador_stl import cargar_exacto
        from topologia_vertices import inspeccionar_vertices
        from reparador_exacto_aislado import ControlExacto
        from meshfit_detect import detect
        from reconstruccion_curvas import cilindros_respaldados,validar_cilindros_y_frontera
        from calidad_topologica import leer_solido_step_estricto
        original=cargar_exacto(source)
        if not original.is_watertight or not original.is_winding_consistent or inspeccionar_vertices(original)['vertices_no_manifold'] or len(original.split(only_watertight=False))!=1:
            raise ValueError('Se requiere una entrada cerrada, orientada y sin contactos ambiguos')
        with tempfile.TemporaryDirectory(prefix='visor_cilindros_contiguos_') as tmp:
            if ControlExacto(original,Path(tmp)/'fuente.off').pares():raise ValueError('La entrada tiene intersecciones')
        previous=leer_solido_step_estricto(base)
        result,proof=proponer(previous)
        cq.exporters.export(result,str(destination))
        detected,working=detect(str(source),angle_tol_deg=32.,rms_tol_rel=.01,flat_tol_deg=8.,scan_mode=False,mesh_input=original.copy())
        required=cilindros_respaldados(detected,working)
        shape,cylinders,quality,topology,boundary=validar_cilindros_y_frontera(source,destination,original,required)
        # Comprobar de nuevo los recortes tras escribir y volver a leer STEP.
        proof['recortes_reimportados']=certificar_recortes(previous,shape)
        if before!=(sha(source),sha(base)):raise ValueError('Se ha modificado una entrada')
        record.update(ok=True,metodo='reunion_cilindros_sin_ajuste',original_sha256=before[0],base_sha256=before[1],step_sha256=sha(destination),propuesta=proof,calidad=quality,topologia_material=topology,mallado_fino=boundary,cilindros_respaldados=cylinders)
    except Exception as exc:
        record['error']=str(exc);destination.unlink(missing_ok=True);traceback.print_exc()
    if before!=(sha(source),sha(base)):raise RuntimeError('Se ha modificado una entrada')
    record['segundos']=time.monotonic()-start
    report.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
    return 0 if record['ok'] else 2


if __name__=='__main__':
    import sys
    if len(sys.argv)!=5:raise SystemExit('Uso: python cilindros_contiguos.py original.stl base.step candidato.step informe.json')
    raise SystemExit(ejecutar(*sys.argv[1:]))
