"""Verificación independiente de las piezas aportadas: STEP, geometría y material.

Uso: python verificar_casos_usuario.py --casos CARPETA --resultados CARPETA
Lee bateria.json. Un caso rechazado sigue siendo pendiente, nunca se cuenta
como conversión aprobada. No envía piezas a servicios externos.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np


def verificar(source,step,row):
    import cadquery as cq
    import trimesh
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN,TopAbs_OUT
    from preprocesador_stl import cargar_exacto,componentes
    from verificacion_reparacion import union_independiente,malla_cad,distancia_malla
    from validacion_local import _esparcir,_distancias_cad,_puntos_brep
    from saneamiento_cad import comprobar_interferencias
    from motor_v2 import _calidad,_estadisticas

    assert hashlib.sha256(source.read_bytes()).hexdigest()==row['sha256']
    assert hashlib.sha256(step.read_bytes()).hexdigest()==row['sha256_step']
    original=cargar_exacto(source)
    prep=row['informe_motor']['preprocesamiento']
    reference_path=step.with_suffix('.reparado.stl') if prep['reparado'] else source
    if prep['reparado']:
        assert hashlib.sha256(reference_path.read_bytes()).hexdigest()==prep['reparado_sha256']
    mesh=cargar_exacto(reference_path)
    q=_calidad(reference_path,step,mesh)
    solid=cq.importers.importStep(str(step)).solids().val()
    clean,issues=comprobar_interferencias(solid)
    if not clean:raise ValueError(f'El STEP conserva {issues} interferencias OCC.')
    # Referencia de material obtenida desde los componentes ORIGINALES.
    ref=union_independiente(componentes(original)).Solids()[0]
    refmesh=malla_cad(ref.copy())
    masses=[]
    for epsilon in (1e-6,1e-8):
        g=GProp_GProps();BRepGProp.VolumeProperties_s(solid.wrapped,g,epsilon);masses.append(float(g.Mass()))
    refmass=float(ref.Volume())
    if (not np.isfinite(masses).all() or abs(masses[0]-masses[1])/refmass>1e-5
            or abs(masses[-1]-refmass)/refmass>.005):
        raise ValueError('Volumen adaptativo no convergente o fuera del límite original.')
    area,_=trimesh.sample.sample_surface(mesh,1000,seed=20261023)
    points=np.vstack((_esparcir(np.vstack((mesh.vertices,mesh.triangles_center)),2000),area))
    a=_distancias_cad(solid,points)
    verts,tris=solid.copy().tessellate(.003,angularTolerance=.04)
    vertices=np.array([p.toTuple() for p in verts]);triangles=np.asarray(tris)
    cad_points=np.vstack((vertices,vertices[triangles].mean(axis=1),_puntos_brep(solid,10000)))
    b=distancia_malla(mesh,cad_points)
    dense={'stl_a_cad_denso_mm':_estadisticas(a),'cad_a_stl_denso_mm':_estadisticas(b),
           'stl_hotspots':[{'xyz_mm':points[k].tolist(),'distancia_mm':float(a[k])} for k in np.argsort(-a)[:10]],
           'cad_hotspots':[{'xyz_mm':cad_points[k].tolist(),'distancia_mm':float(b[k])} for k in np.argsort(-b)[:10]]}
    step.with_suffix('.denso.json').write_text(json.dumps(dense,indent=2))
    limit=q['limites_validacion']['p95_superficie_max_mm']
    if (not np.isfinite(a).all() or not np.isfinite(b).all()
            or max(np.percentile(a,95),np.percentile(b,95))>limit or max(a.max(),b.max())>.060):
        raise ValueError('La inspección densa no pasa los límites originales: '
                         f'p95 {max(np.percentile(a,95),np.percentile(b,95)):.6f} mm; '
                         f'máximo {max(a.max(),b.max()):.6f} mm. Ver .denso.json.')
    # Comparación de ocupación, lejos de la banda máxima permitida de 0,060 mm.
    rng=np.random.default_rng(23102026)
    probes=rng.uniform(original.bounds[0],original.bounds[1],size=(2000,3))
    distances=distancia_malla(refmesh,probes)
    probes=probes[distances>.060]
    special=[]
    if source.name=='Pieza ambigua.stl':
        for x in (-12.,-4.,4.,12.):
            special.extend([(x,0.,10.4),(x+2.,0.,10.4)])
        probes=np.vstack((probes,np.asarray(special)))
    mismatch=[];states=[]
    for p in probes:
        expected=BRepClass3d_SolidClassifier(ref.wrapped,gp_Pnt(*map(float,p)),1e-7).State()
        actual=BRepClass3d_SolidClassifier(solid.wrapped,gp_Pnt(*map(float,p)),1e-7).State()
        states.append((expected,actual))
        if expected not in (TopAbs_IN,TopAbs_OUT) or expected!=actual:
            mismatch.append({'xyz_mm':p.tolist(),'referencia':str(expected),'step':str(actual)})
    if mismatch:raise ValueError(f'El CAD cambia la ocupación en {len(mismatch)} puntos de control; ejemplo {mismatch[0]}.')
    holes=[]
    if special:
        for i,(p,(expected,actual)) in enumerate(zip(special,states[-len(special):])):
            desired=TopAbs_OUT if i%2==0 else TopAbs_IN
            if expected!=desired or actual!=desired:raise ValueError('No se conservan cavidades o paredes de los salientes.')
            holes.append({'xyz_mm':p,'esperado':str(desired),'obtenido':str(actual)})
    return {'ok':True,'sha256_stl':row['sha256'],'sha256_step':row['sha256_step'],
            'calidad_repetida':q,'autointerferencias_occ':False,'solidos':len(solid.Solids()),
            'volumen_adaptativo_mm3':masses,'volumen_referencia_mm3':refmass,
            'volumen_adaptativo_error_pct':100*abs(masses[-1]-refmass)/refmass,
            'stl_a_cad_denso_mm':_estadisticas(a),'cad_a_stl_denso_mm':_estadisticas(b),
            'ocupacion_puntos':len(probes),'ocupacion_discrepancias':0,
            'cavidades_y_paredes':holes,
            'nota':'Muestreo determinista; no garantía Hausdorff global ni prueba Move face en Onshape.'}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--casos',type=Path,required=True)
    ap.add_argument('--resultados',type=Path,required=True)
    ap.add_argument('--solo',nargs='*')
    args=ap.parse_args();battery=json.loads((args.resultados/'bateria.json').read_text())
    previous=args.resultados/'verificacion_independiente.json'
    results=json.loads(previous.read_text()) if args.solo and previous.exists() else {}
    for row in battery['resultados']:
        name=row['archivo']
        if args.solo and name not in args.solo:continue
        if not row['ok']:
            results[name]={'ok':False,'pendiente':True,'error':row['informe_motor'].get('error')}
        else:
            try:results[name]=verificar(args.casos/name,args.resultados/(Path(name).stem+'.step'),row)
            except Exception as exc:results[name]={'ok':False,'error':str(exc)}
        print(name,results[name]['ok'],results[name].get('error',''),flush=True)
        (args.resultados/'verificacion_independiente.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
    return 0 if results and all(r['ok'] for r in results.values()) else 1


if __name__=='__main__':raise SystemExit(main())
