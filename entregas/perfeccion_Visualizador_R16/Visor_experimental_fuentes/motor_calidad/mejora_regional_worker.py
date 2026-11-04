"""Bounded R14 worker: propose, serialize, and validate against original STL."""
from pathlib import Path
import hashlib,json,os,sys,tempfile,time,traceback


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ejecutar(source,prepared,base,destination,spec_path,report_path):
    source,prepared,base,destination,spec_path,report_path=map(Path,(source,prepared,base,destination,spec_path,report_path))
    if destination.exists() or report_path.exists() or len({p.resolve() for p in (base,destination,spec_path,report_path)})!=4:
        raise ValueError('La propuesta y su informe deben ser archivos nuevos y distintos')
    if any(destination.resolve()==p.resolve() or report_path.resolve()==p.resolve() for p in (source,prepared)):
        raise ValueError('No se sobrescriben entradas')
    record=dict(ok=False);start=time.monotonic();identity=tuple(map(sha,(source,prepared,base)))
    def phase(name):
        record.setdefault('fases',[]).append(dict(fase=name,segundos=time.monotonic()-start))
        report_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print('[R14]',name,round(time.monotonic()-start,2),flush=True)
    phase('lectura_y_comprobacion_de_entradas')
    try:
        spec=json.loads(spec_path.read_text(encoding='utf-8'))
        if identity!=(spec['source_sha256'],spec['prepared_sha256'],spec['base_sha256']):raise ValueError('La petición no corresponde a las entradas')
        sys.path.insert(0,str(Path(__file__).parent/'motor_superficies'))
        from preprocesador_stl import cargar_exacto
        from calidad_topologica import leer_solido_step_estricto
        from exportacion_solida import exportar
        from motor_v2 import _calidad
        from invariantes_material import InvariantesMaterial
        from validacion_reconstruccion import certificar_topologia_step
        from reconstruccion_curvas import certificar_mallado
        from prueba_cad import REVISION
        original=cargar_exacto(source);working=cargar_exacto(prepared);previous=leer_solido_step_estricto(base)
        if not working.is_watertight or not working.is_winding_consistent:raise ValueError('Se requiere una referencia preparada cerrada')
        fine=None
        if spec['mode']=='regiones':
            import numpy as np
            from reconstruccion_regional import proponer
            from reconstruccion_curvas import InterseccionesMalladoFino
            from cilindros_contiguos import cilindros,certificar_recortes
            blocked=set();retractions=[]
            support_limit=.0005 if len(previous.Faces())<=500 else min(.0005,max(1e-7,spec['previous_quality']['desviacion_max_verificada_mm']*.05))
            record['cota_propuesta_local_mm']=support_limit
            for attempt in range(4):
                result,proof=proponer(previous,reference_volume=abs(original.volume),blocked_faces=blocked,support_limit=support_limit)
                if cilindros(previous):record['cilindros_preservados']=certificar_recortes(previous,result)
                record['exportacion_solida']=exportar(result,destination)
                shape=leer_solido_step_estricto(destination)
                try:
                    with tempfile.TemporaryDirectory(prefix='visor_r14_control_') as directory:
                        fine=certificar_mallado(shape,working,Path(directory)/'frontera.off',spec['previous_quality'],referencia_superficie=original)
                    break
                except InterseccionesMalladoFino as exc:
                    read_faces=shape.Faces();affected=set()
                    for index in exc.caras_cad:
                        face=read_faces[index];center=np.array(face.Center().toTuple());area=face.Area()
                        matches=[p for p in proof if 'new_face_signature' in p and np.linalg.norm(center-np.array(p['new_face_signature']['center']))<5e-6 and abs(area-p['new_face_signature']['area'])<max(1e-6,area*1e-7)]
                        if len(matches)==1:affected.update(matches[0]['faces'])
                    if not affected or not affected-blocked or attempt==3:raise
                    retractions.append(dict(cad_faces=exc.caras_cad,source_regions_retracted=sorted(affected),resolution_mm=exc.resolucion_mm,pairs=exc.pares,step_sha256=sha(destination)))
                    blocked.update(affected);destination.unlink()
                    print('[Retroacción CGAL] regiones retiradas',sorted(affected),flush=True)
            record['retroacciones_cgal']=retractions
        elif spec['mode']=='operaciones':
            if len(working.faces)>160000 or len(previous.Faces())>25000:raise ValueError('Fuera del presupuesto de operaciones medidas')
            from meshfit_detect import detect
            from segmentacion_cilindrica_local import propuestas
            from operaciones_cilindricas_medidas import proponer
            phase('deteccion_medida_en_STL')
            detected,working=detect(str(prepared),mesh_input=working)
            extra,record['segmentacion_local']=propuestas(working,detected)
            phase('operaciones_CAD_locales')
            result,proof=proponer(previous,working,detected['primitives']+extra)
        else:raise ValueError('Modo no reconocido')
        if len(result.Faces())>=len(previous.Faces()):raise ValueError('La propuesta no reduce la fragmentación')
        record['construccion']=proof
        if not destination.exists():
            phase('exportacion_y_reapertura_STEP')
            record['exportacion_solida']=exportar(result,destination)
        shape=leer_solido_step_estricto(destination)
        from OCP.BRep import BRep_Tool
        tolerance_before=max(BRep_Tool.Tolerance_s(e.wrapped) for e in previous.Edges())
        tolerance_after=max(BRep_Tool.Tolerance_s(e.wrapped) for e in shape.Edges())
        # New Boolean edges carry OCCT's own numerical bounds. Never lower
        # these labels to disguise a geometric disagreement. The original
        # exact-CAD, STL and non-regression acceptance limits stay unchanged.
        record['tolerancias_nativas']=dict(antes_mm=tolerance_before,despues_mm=tolerance_after,asignadas_por_occt=True,limites_geometricos_R13_modificados=False)
        os.environ['VISOR_VERIFICAR_INTERFERENCIAS_CAD']='1';os.environ['VISOR_PERFIL']='precision'
        phase('CAD_exacto_interferencias_y_distancia_original')
        quality=_calidad(source,destination,original,control_avanzado=True)
        prior=spec['previous_quality']
        if quality['desviacion_max_verificada_mm']>prior['desviacion_max_verificada_mm']+1e-6:raise ValueError('La propuesta medida empeora el máximo anterior; se conserva la conversión validada')
        if quality['caja_error_mm']>prior['caja_error_mm']+1e-6 or quality['volumen_error_pct']>prior['volumen_error_pct']+1e-6:raise ValueError('La propuesta medida empeora dimensiones o volumen')
        topology=certificar_topologia_step(shape,working,InvariantesMaterial(working))
        if fine is None:
            phase('tres_mallados_finos')
            with tempfile.TemporaryDirectory(prefix='visor_r14_frontera_') as directory:
                fine=certificar_mallado(shape,working,Path(directory)/'frontera.off',quality,referencia_superficie=original)
        if source.resolve()==prepared.resolve():
            from verificar_original_calidad import comprobar_material_original
            phase('material_del_original')
            def material_progress(done,total):
                record['progreso_material']=dict(puntos_comprobados=done,puntos_previstos=total,segundos=time.monotonic()-start)
                report_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
            record['material_original']=comprobar_material_original(original,shape,progress=material_progress)
        if identity!=tuple(map(sha,(source,prepared,base))):raise ValueError('Una entrada cambió durante la mejora')
        phase('validacion_completada')
        record.update(ok=True,original_sha256=identity[1],original_usuario_sha256=identity[0],base_sha256=identity[2],step_sha256=sha(destination),
                      calidad=quality,topologia_material=topology,mallado_fino=fine,brep_exacto=True,revision_cad=REVISION,
                      mode=spec['mode'],caras_antes=len(previous.Faces()),caras_despues=len(shape.Faces()),limites_aceptacion_modificados=False)
    except Exception as exc:
        record['error']=str(exc);destination.unlink(missing_ok=True);traceback.print_exc()
    record['seconds']=time.monotonic()-start
    report_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if record['ok'] else 2


if __name__=='__main__':raise SystemExit(ejecutar(*sys.argv[1:]))
