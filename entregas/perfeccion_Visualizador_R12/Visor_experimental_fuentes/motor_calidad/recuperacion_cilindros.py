"""Refinamiento opcional y aislado de una recuperación facetada ya verificada.

El STEP previo permanece intacto si faltan pruebas, falla el trabajador o se
agota su presupuesto. No se usa para sustituir salidas analíticas aceptadas.
"""
from pathlib import Path
import hashlib,json,os,sys,tempfile,subprocess,shutil,time,traceback

def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def trabajador(source,base,destination,report):
    from recuperacion_numerica import _rutas_seguras
    source,base,destination,report=map(Path,(source,base,destination,report))
    if not _rutas_seguras(source,base,destination,report):
        print('Las entradas y salidas deben ser distintas.',flush=True);return 2
    record={'ok':False};start=time.monotonic()
    try:
        import numpy as np
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_BSplineSurface
        sys.path.insert(0,str(Path(__file__).parent/'motor_superficies'))
        from meshfit_detect import detect
        from cilindros_locales import propuestas,reconstruir
        from preprocesador_stl import cargar_exacto
        from normalizacion_referencia import normalizar_cierre
        from calidad_topologica import leer_solido_step_estricto
        from reconstruccion_curvas import inventario,comprobar_cilindros,certificar_mallado
        from invariantes_material import InvariantesMaterial
        from reparador_exacto_aislado import ControlExacto
        from validacion_reconstruccion import certificar_topologia_step
        from motor_v2 import _calidad
        from prueba_cad import REVISION
        hashes=[_sha(source),_sha(base)];original=cargar_exacto(source)
        if len(original.faces)>12000:raise ValueError('Entrada fuera del presupuesto local de cilindros')
        if not original.is_watertight or not original.is_winding_consistent:
            original,record['normalizacion_referencia']=normalizar_cierre(original)
        invariants=InvariantesMaterial(original)
        shape=leer_solido_step_estricto(base);before=inventario(shape)
        if before['cilindros'] or not 150<=before['caras']<=3500:
            raise ValueError('Sólo se refina una base facetada dentro del presupuesto')
        with tempfile.TemporaryDirectory(prefix='visor_cilindros_control_') as directory:
            directory=Path(directory)
            if ControlExacto(original,directory/'original.off').pares():raise ValueError('El original presenta intersecciones')
            detection,mesh=detect(str(source),angle_tol_deg=32.,rms_tol_rel=.01,flat_tol_deg=8.,scan_mode=False,mesh_input=original)
            patches=propuestas(mesh,detection)
            if not patches:raise ValueError('No hay paredes cilíndricas completas respaldadas por el STL')
            from avance_conversion import avance
            avance(93,'Reconstruyendo paredes cilíndricas locales; se conservará el STEP previo si no mejoran')
            rebuilt,operations=reconstruir(shape,patches)
            rebuilt.exportStep(str(destination));back=leer_solido_step_estricto(destination);after=inventario(back)
            if not after['cilindros'] or after['caras']>.90*before['caras']:
                raise ValueError('La reconstrucción local no reduce suficientemente las caras')
            if any(BRepAdaptor_Surface(f.wrapped).GetType()==GeomAbs_BSplineSurface for f in back.Faces()):
                raise ValueError('No se sustituyen las facetas por nuevos parches B-spline')
            required=[];index={p['region_fuente']:p for p in patches}
            for operation in operations:
                p=index[operation['region_fuente']];ids=p['caras_indices']
                points=np.vstack((mesh.vertices[p['vertices_fuente']],mesh.triangles_center[ids]))
                required.append({'puntos':points,'radio':p['radio'],'eje':p['eje'],'centro':p['centro'],'max_entrada_mm':p['cota_radial_mm']})
            cylinders=comprobar_cilindros(required,back)
            quality=_calidad(source,destination,original,control_avanzado=True)
            topology=certificar_topologia_step(back,original,invariants)
            fine=certificar_mallado(back,original,directory/'frontera.off',quality)
        if hashes!=[_sha(source),_sha(base)]:raise ValueError('Una entrada cambió durante la verificación')
        record.update(ok=True,original_sha256=hashes[0],base_sha256=hashes[1],step_sha256=_sha(destination),
                      brep_exacto=True,revision_cad=REVISION,calidad=quality,antes=before,despues=after,
                      paredes_confirmadas=len(patches),paredes_reconstruidas=len(operations),operaciones=operations,
                      cilindros_respaldados=cylinders,topologia_material=topology,mallado_fino=fine,
                      otras_zonas_conservan_facetas=True,limites_aceptacion_modificados=False)
    except Exception as exc:
        record['error']=str(exc);destination.unlink(missing_ok=True);traceback.print_exc()
    record['segundos']=time.monotonic()-start
    report.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if record['ok'] else 2


def intentar(source,step,original,log,*,timeout=360):
    """Publicar una candidata sólo tras comprobar bytes, fuentes y geometría."""
    import psutil
    from control_recursos import comunicar_vigilado
    from motor_v2 import _calidad
    from prueba_cad import desde_trabajador
    source,step=map(Path,(source,step));hashes=[_sha(source),_sha(step)]
    def stop(proc):
        try:
            parent=psutil.Process(proc.pid)
            for child in parent.children(recursive=True):
                try:child.kill()
                except psutil.NoSuchProcess:pass
            parent.kill()
        except psutil.NoSuchProcess:pass
    with tempfile.TemporaryDirectory(prefix='visor_cilindros_locales_',dir=step.parent) as directory:
        directory=Path(directory);base=directory/'base.step';candidate=directory/'candidato.step';report=directory/'informe.json'
        shutil.copyfile(step,base)
        with subprocess.Popen([sys.executable,str(Path(__file__).resolve()),str(source),str(base),str(candidate),str(report)],
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',
                env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','PYTHONUNBUFFERED':'1'}) as proc:
            out,_,peak=comunicar_vigilado(proc,timeout,stop)
        if out:print(out,file=log,flush=True)
        if proc.returncode!=0 or not report.exists():raise ValueError('El refinamiento local no produjo un STEP aprobado')
        proof=json.loads(report.read_text(encoding='utf-8'))
        if (not proof.get('ok') or not candidate.is_file() or proof.get('original_sha256')!=hashes[0]
                or proof.get('base_sha256')!=hashes[1] or proof.get('step_sha256')!=_sha(candidate)
                or hashes!=[_sha(source),_sha(step)] or _sha(base)!=hashes[1]):
            raise ValueError('El refinamiento no corresponde a los archivos verificados')
        quality=_calidad(source,candidate,original,control_avanzado=True,prueba_cad=desde_trabajador(proof,candidate))
        payload=candidate.read_bytes()
        if hashlib.sha256(payload).hexdigest()!=proof['step_sha256'] or hashes!=[_sha(source),_sha(step)]:
            raise ValueError('Un archivo cambió antes de publicar el refinamiento')
        candidate.replace(step);proof['ram_pico_mb']=peak;proof['aplicado']=True
        return quality,proof


if __name__=='__main__':
    if len(sys.argv)!=5:raise SystemExit('Uso: recuperacion_cilindros.py original.stl base.step salida.step informe.json')
    raise SystemExit(trabajador(*sys.argv[1:]))
