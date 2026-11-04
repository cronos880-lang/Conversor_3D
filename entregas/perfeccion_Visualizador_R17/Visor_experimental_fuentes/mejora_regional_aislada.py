"""R14 refinement after a complete R13 conversion, with atomic fallback."""
from pathlib import Path
import contextlib,hashlib,json,os,shutil,sys,tempfile,time


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def elegible(payload):
    from respaldo_conversion import calidad_aprobada
    if not calidad_aprobada(payload):return None
    q=payload.get('resultado',{}).get('calidad',{});types=q.get('tipos_caras',{});count=int(q.get('caras_step',0))
    if 120<=count<=2500 and types.get('GeomAbs_BSplineSurface',0)>=2:return 'regiones'
    if 5000<=count<=25000 and not types.get('GeomAbs_Cylinder',0) and not payload.get('preprocesamiento',{}).get('reparado'):return 'operaciones'
    return None


def comparar_calidad(previous,current):
    """No geometric-profile or previous-result limit is loosened."""
    maximum=float(previous['desviacion_max_verificada_mm'])+1e-6
    if current['desviacion_max_verificada_mm']>maximum:
        raise ValueError('La propuesta empeora la desviación máxima respecto al STEP anterior')
    for key in ('caja_error_mm','volumen_error_pct'):
        if current[key]>previous[key]+1e-6:raise ValueError('La propuesta empeora '+key)
    if current['caras_step']>=previous['caras_step']:raise ValueError('No reduce caras')
    return dict(max_anterior_mm=previous['desviacion_max_verificada_mm'],max_actual_mm=current['desviacion_max_verificada_mm'],
                margen_numerico_mm=1e-6,limites_perfil_modificados=False)


def entrada_preparada(source,step,payload):
    prep=payload.get('preprocesamiento',{})
    if not prep.get('reparado'):return source
    proof=payload.get('resultado',{}).get('mejora_superficies',{})
    normalized=step.with_suffix('.calidad_preparado.stl')
    if proof.get('entrada_calidad_sha256') and normalized.is_file() and sha(normalized)==proof['entrada_calidad_sha256']:return normalized
    from perfeccion_calidad import entrada_preparada as reparada
    return reparada(source,step,prep)


def intentar(source,step,payload,validar,log):
    from perfeccion_calidad import ejecutar_subproceso,NUCLEO,EntradaCambiada
    from preprocesador_stl import cargar_exacto
    from prueba_cad import desde_trabajador
    from respaldo_conversion import guardar
    from avance_conversion import avance
    mode=elegible(payload)
    if not mode:return None
    source,step=map(Path,(source,step));prepared=entrada_preparada(source,step,payload)
    identity=tuple(map(sha,(source,prepared,step)));prior=payload['resultado']['calidad'];start=time.monotonic()
    prep=payload.get('preprocesamiento',{})
    if prep.get('original_sha256') not in (None,identity[0]):raise EntradaCambiada('La mejora no corresponde al original')
    guardar(source,step,payload,etapa='r14')
    def immutable():
        if identity!=tuple(map(sha,(source,prepared,step))):raise EntradaCambiada('Cambió una entrada durante la reconstrucción regional')
    with tempfile.TemporaryDirectory(prefix='visor_r14_verificado_',dir=step.parent) as directory:
        directory=Path(directory);candidate=directory/'candidato.step';report=directory/'trabajador.json';spec=directory/'peticion.json'
        spec.write_text(json.dumps(dict(mode=mode,source_sha256=identity[0],prepared_sha256=identity[1],base_sha256=identity[2],previous_quality=prior)),encoding='utf-8')
        avance(78,'Reconstruyendo regiones CAD medidas; se conserva la conversión anterior')
        try:
            peak=ejecutar_subproceso(NUCLEO/'mejora_regional_worker.py',[source,prepared,step,candidate,spec,report],420 if mode=='regiones' else 2100,log)
        except Exception:
            if report.is_file():shutil.copyfile(report,step.with_suffix('.r14_propuesta.json'))
            raise
        shutil.copyfile(report,step.with_suffix('.r14_propuesta.json'))
        record=json.loads(report.read_text(encoding='utf-8'));immutable()
        if not record.get('ok') or record.get('original_usuario_sha256')!=identity[0] or record.get('original_sha256')!=identity[1] or record.get('base_sha256')!=identity[2] or record.get('step_sha256')!=sha(candidate):raise ValueError('La propuesta no coincide con sus archivos')
        original_proof=None
        if source.resolve()!=prepared.resolve():
            original_report=directory/'original.json'
            peak=max(peak,ejecutar_subproceso(NUCLEO/'verificar_original_calidad.py',[source,prepared,candidate,report,original_report],240,log))
            original_proof=json.loads(original_report.read_text(encoding='utf-8'))
            if original_proof.get('ok') is not True or original_proof.get('original_sha256')!=identity[0] or original_proof.get('step_sha256')!=sha(candidate):raise ValueError('La validación original no coincide con la propuesta')
        quality=validar(source,candidate,cargar_exacto(source),control_avanzado=True,prueba_cad=desde_trabajador(record,candidate))
        comparison=comparar_calidad(prior,quality);immutable()
        if sha(candidate)!=record['step_sha256']:raise EntradaCambiada('El candidato cambió después de validarse')
        proof=dict(aplicado=True,mode=mode,caras_antes=prior['caras_step'],caras_despues=quality['caras_step'],original_sha256=identity[0],step_anterior_sha256=identity[2],step_sha256=record['step_sha256'],
                   comparacion_no_regresion=comparison,seconds=time.monotonic()-start,ram_pico_mb=peak,limites_aceptacion_modificados=False,
                   topologia_material=record['topologia_material'],mallado_fino=record['mallado_fino'],construccion=record['construccion'])
        proof['retroacciones_cgal']=record.get('retroacciones_cgal',[])
        proof['material_original']=original_proof['material_original'] if original_proof is not None else record['material_original']
        shutil.copyfile(report,step.with_suffix('.r14_nucleo.json'))
        if original_proof is not None:shutil.copyfile(original_report,step.with_suffix('.r14_original.json'))
        candidate.replace(step)
        step.with_suffix('.r14_propuesta.json').unlink(missing_ok=True)
        return quality,proof


def ejecutar(legacy,output_type,validar):
    if len(sys.argv)!=3:return legacy()
    output=output_type(sys.stdout)
    with contextlib.redirect_stdout(output):code=legacy()
    lines=output.getvalue().splitlines()
    try:payload=json.loads(lines[-1])
    except (ValueError,IndexError):raise RuntimeError('El motor anterior no emitió un resultado verificable')
    if code==0 and payload.get('ok') and os.environ.get('VISOR_RECONSTRUCCION_REGIONAL','1')=='1' and elegible(payload):
        source,step=map(Path,sys.argv[1:])
        try:
            with step.with_suffix('.motor.log').open('a',encoding='utf-8',buffering=1) as log:
                changed=intentar(source,step,payload,validar,log)
            if changed is not None:
                quality,proof=changed;result=payload['resultado'];result['calidad']=quality;result['reconstruccion_regional']=proof
                if 'calidad_original' in result:result['calidad_original']=quality
                result['estrategia']='regiones_y_operaciones_cad_verificadas';result['motor']='Reconstrucción regional CAD verificada'
                result['modo']='cilindros_locales_y_facetas' if proof['mode']=='operaciones' else 'superficies'
        except Exception as exc:
            from perfeccion_calidad import EntradaCambiada
            if isinstance(exc,EntradaCambiada):payload.update(ok=False,error=str(exc));code=2
            else:payload['reconstruccion_regional']=dict(aplicado=False,motivo=str(exc),conservado_resultado_anterior=True)
    print(json.dumps(payload,ensure_ascii=True));return code
